"""
AI Chatbot — Qwen2.5-3B-Instruct + Gradio ChatInterface

Lazy-loads the Qwen model on first use (follows nlp/model_inference.py pattern).
Provides database-aware chat with tool calling for news/disaster/market queries.
"""
import json
import logging
import re
import time
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache (lazy singleton — same pattern as model_inference.py)
# ---------------------------------------------------------------------------
_model_cache: dict = {}
_conversations: dict = {}  # {session_hash: {"messages": [...], "last_active": timestamp}}
_cleanup_thread_started = False

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def _get_device():
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def _ensure_model_loaded():
    """Lazy-load Qwen2.5-3B-Instruct. Cached in _model_cache["qwen"]."""
    if "qwen" in _model_cache:
        return _model_cache["qwen"]

    from config import config
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    model_path = config.MODEL_DIR / config.CHATBOT_MODEL
    logger.info(f"[Chatbot] 加载模型: {model_path}")

    device = _get_device()
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = "<|endoftext|>"

    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()

    _model_cache["qwen"] = (model, tokenizer)
    logger.info(f"[Chatbot] 模型加载完成 (device: {device})")
    return model, tokenizer


def unload_chatbot_model():
    """Release chatbot model VRAM."""
    import gc
    import torch
    _model_cache.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("[Chatbot] 模型已卸载")

# ---------------------------------------------------------------------------
# System prompt builder (injects DB context)
# ---------------------------------------------------------------------------

def _build_system_prompt(db) -> str:
    """Build system prompt with live database context."""
    try:
        stats = db.get_statistics()
        total_news = stats.get("total_news", 0)
        total_disasters = stats.get("total_disasters", 0)
        analyzed = stats.get("analyzed_articles", 0)
        category_counts = stats.get("category_counts", {})

        # Category summary
        cat_parts = []
        for cat, count in (category_counts or {}).items():
            cat_parts.append(f"{cat}: {count}条")
        cat_summary = "、".join(cat_parts) if cat_parts else "暂无数据"

        # Sentiment summary
        sentiment_text = "暂无"
        try:
            sent = db.get_sentiment_summary()
            if sent:
                score = sent.get("score_10", "N/A")
                label = sent.get("label", "N/A")
                sentiment_text = f"{score}/10分，整体偏{label}"
        except Exception:
            pass

        # Recent 5 news
        recent_news_text = "暂无"
        try:
            recent = db.get_all_news(limit=5, offset=0)
            if recent:
                lines = []
                for i, n in enumerate(recent, 1):
                    title = n.get("title", "")[:80]
                    date = n.get("date", "")[:10]
                    cat = n.get("category", "")
                    sent = n.get("sentiment", "")
                    lines.append(f"  {i}. [{date}] {title}（{cat}/{sent}）")
                recent_news_text = "\n".join(lines)
        except Exception:
            pass

        # Active disasters
        disasters_text = "暂无活跃预警"
        try:
            disasters = db.get_active_disasters(limit=5)
            if disasters:
                lines = []
                for i, d in enumerate(disasters, 1):
                    title = d.get("title", "")[:80]
                    region = d.get("region", "")
                    level = d.get("alert_level", "")
                    dtype = d.get("disaster_type", "")
                    lines.append(f"  {i}. [{level}] {region} — {title}（{dtype}）")
                disasters_text = "\n".join(lines)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[Chatbot] 构建系统提示失败: {e}")
        total_news = total_disasters = analyzed = 0
        cat_summary = sentiment_text = recent_news_text = disasters_text = "获取失败"

    prompt = f"""你是一个专业的农业新闻分析助手。你可以帮助用户了解最新的农业新闻、灾害预警、市场动态和舆情分析。

## 当前数据库统计
- 新闻总数：{total_news} 条（已分析 {analyzed} 条）
- 灾害预警数：{total_disasters} 条
- 舆情综合评分：{sentiment_text}
- 分类分布：{cat_summary}

## 最近新闻
{recent_news_text}

## 活跃灾害预警
{disasters_text}

## 可用工具
当用户需要更具体的数据时，你可以使用以下工具格式调用：
<tool_call>
{{"name": "<函数名>", "arguments": {{"<参数>": "<值>"}}}}
</tool_call>

可用的工具函数：
- get_statistics：获取完整统计信息（无参数）
- search_news：按关键词搜索新闻（参数：keyword）
- get_recent_news：获取最近新闻（参数：limit，默认10）
- get_disasters：获取活跃灾害预警（无参数）
- get_sentiment_summary：获取舆情分析总结（无参数）
- get_news_by_category：按分类查询新闻（参数：category，可选值：政策法规、市场行情、农业科技、灾害预警、国际农业、综合资讯）

## 注意事项
- 回答要简洁、专业，使用中文
- 当用户询问数据库中的信息时，优先基于上方已有的「当前数据库统计」「最近新闻」「活跃灾害预警」回答
- 只有当用户要求更详细的搜索、或查询的信息不在已有上下文中时，才使用工具调用
- 不要编造数据，如果数据库中没有相关信息，诚实告知用户
"""
    return prompt


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _make_tool_handlers(db):
    """Create tool dispatch table bound to a DatabaseManager instance."""
    return {
        "get_statistics": lambda **kw: json.dumps(
            db.get_statistics(), ensure_ascii=False, default=str),
        "search_news": lambda keyword="", **kw: json.dumps(
            db.search_news(keyword, limit=10), ensure_ascii=False, default=str),
        "get_recent_news": lambda limit=10, **kw: json.dumps(
            db.get_all_news(limit=int(limit), offset=0), ensure_ascii=False, default=str),
        "get_disasters": lambda **kw: json.dumps(
            db.get_active_disasters(limit=10), ensure_ascii=False, default=str),
        "get_sentiment_summary": lambda **kw: json.dumps(
            db.get_sentiment_summary(), ensure_ascii=False),
        "get_news_by_category": lambda category="", **kw: json.dumps(
            db.get_all_news(limit=10, category=category), ensure_ascii=False, default=str),
    }


def _parse_tool_calls(text: str) -> list[dict]:
    """Parse <tool_call>{json}</tool_call> blocks from model output."""
    pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
    matches = re.findall(pattern, text, re.DOTALL)
    tools = []
    for m in matches:
        try:
            tool = json.loads(m.strip())
            if "name" in tool:
                tools.append(tool)
        except json.JSONDecodeError:
            logger.warning(f"[Chatbot] 无法解析工具调用: {m[:200]}")
    return tools


def _execute_tool(db, tool_name: str, arguments: dict) -> str:
    """Execute a tool and return the JSON result string (truncated)."""
    handlers = _make_tool_handlers(db)
    handler = handlers.get(tool_name)
    if handler is None:
        return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)
    try:
        result = handler(**arguments)
        if len(result) > 3000:
            result = result[:3000] + f"\n...(结果已截断，共{len(result)}字符)"
        return result
    except Exception as e:
        logger.error(f"[Chatbot] 工具执行失败 {tool_name}: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

# ---------------------------------------------------------------------------
# Conversation management
# ---------------------------------------------------------------------------

def _cleanup_stale_sessions():
    """Background thread: remove sessions inactive for > 60 minutes."""
    global _cleanup_thread_started
    _cleanup_thread_started = True
    while True:
        time.sleep(600)  # every 10 minutes
        now = time.time()
        stale = [
            k for k, v in list(_conversations.items())
            if now - v.get("last_active", 0) > 3600
        ]
        for k in stale:
            del _conversations[k]
        if stale:
            logger.info(f"[Chatbot] 清理了 {len(stale)} 个过期会话")

# ---------------------------------------------------------------------------
# Main chat function (for Gradio ChatInterface)
# ---------------------------------------------------------------------------

def chat_fn(message: str, history: list, request: any = None):
    """
    Chat function for Gradio ChatInterface.

    Args:
        message: Latest user message (str)
        history: List of {"role": "user"|"assistant", "content": "..."} dicts
        request: gr.Request (injected by Gradio)

    Yields:
        str chunks for streaming (final yield is the complete response)
    """
    # Get database instance
    from backend.api import get_db
    db = get_db()

    # Get or create session
    session_hash = "default"
    if request and hasattr(request, "session_hash"):
        session_hash = request.session_hash

    if session_hash not in _conversations:
        _conversations[session_hash] = {"messages": [], "last_active": time.time()}
    session = _conversations[session_hash]
    session["last_active"] = time.time()

    # Start cleanup thread if needed
    global _cleanup_thread_started
    if not _cleanup_thread_started:
        t = threading.Thread(target=_cleanup_stale_sessions, daemon=True)
        t.start()

    # Build messages for the model
    messages = []
    # Inject system prompt at the start
    messages.append({"role": "system", "content": _build_system_prompt(db)})

    # Add conversation history from Gradio (last N turns to stay within context)
    max_history = 20  # 10 turns of user+assistant pairs
    recent_history = history[-max_history:] if len(history) > max_history else history
    for h in recent_history:
        if isinstance(h, dict):
            # New format: {"role": "user"|"assistant", "content": "..."}
            role = h.get("role", "user")
            content = h.get("content", "")
        elif isinstance(h, (list, tuple)) and len(h) >= 2:
            # Old format: [user_msg, assistant_msg]
            role = "user"
            content = h[0]
        else:
            continue
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Add current message if not already in history
    last_is_current = False
    if recent_history:
        last = recent_history[-1]
        if isinstance(last, dict):
            last_is_current = (last.get("role") == "user" and last.get("content") == message)
        elif isinstance(last, (list, tuple)) and len(last) >= 1:
            last_is_current = (last[0] == message)
    if not last_is_current:
        messages.append({"role": "user", "content": message})

    # Load model
    try:
        model, tokenizer = _ensure_model_loaded()
    except Exception as e:
        logger.error(f"[Chatbot] 模型加载失败: {e}")
        yield "抱歉，AI 模型加载失败，请稍后重试。"
        return

    # Tool calling loop (max 3 rounds)
    max_tool_rounds = 3
    for round_num in range(max_tool_rounds + 1):
        # Apply chat template
        try:
            text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        except Exception:
            # Fallback: simple concatenation
            parts = []
            for m in messages:
                role = m["role"]
                content = m["content"]
                if role == "system":
                    parts.append(f"<|im_start|>system\n{content}<|im_end|>")
                elif role == "user":
                    parts.append(f"<|im_start|>user\n{content}<|im_end|>")
                elif role == "assistant":
                    parts.append(f"<|im_start|>assistant\n{content}<|im_end|>")
            parts.append("<|im_start|>assistant\n")
            text = "\n".join(parts)

        # Tokenize
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        # Generate
        import torch
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )

        # Decode only the generated part
        input_len = inputs.input_ids.shape[1]
        generated_ids = outputs[0][input_len:]
        response_text = tokenizer.decode(generated_ids, skip_special_tokens=False)

        # Clean up special tokens for display
        clean_response = response_text.replace("<|im_end|>", "").replace("<|im_start|>", "").strip()

        # Check for tool calls in this round
        tool_calls = _parse_tool_calls(clean_response)
        if tool_calls and round_num < max_tool_rounds:
            # Execute tools and inject results
            tool_results = []
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                result = _execute_tool(db, name, args)
                tool_results.append(f"[{name}]: {result}")

            # Add assistant response (with tool calls) and tool results to messages
            messages.append({"role": "assistant", "content": clean_response})
            tool_result_msg = "工具执行结果：\n" + "\n".join(tool_results)
            messages.append({"role": "system", "content": tool_result_msg})
            logger.info(f"[Chatbot] 第{round_num+1}轮工具调用: {[t.get('name') for t in tool_calls]}")
            continue  # loop again with tool results injected

        # No tool calls or max rounds reached — yield final response
        # Strip any remaining tool call tags for display
        display_text = re.sub(r"<tool_call>.*?</tool_call>", "", clean_response, flags=re.DOTALL).strip()
        if not display_text:
            display_text = "抱歉，我暂时无法回答这个问题。请换个方式提问试试。"

        # Update session history
        messages.append({"role": "assistant", "content": display_text})

        # Trim session messages (remove system prompt + keep last N)
        session_msgs = [m for m in messages if m["role"] != "system"]
        session["messages"] = session_msgs[-40:]  # keep last 20 turns
        session["last_active"] = time.time()

        yield display_text
        return

    # Should not reach here, but fallback
    yield "抱歉，处理超时，请重新提问。"


# ---------------------------------------------------------------------------
# Gradio app factory
# ---------------------------------------------------------------------------

def create_chatbot_app(db=None):
    """
    Create a Gradio Blocks app with ChatInterface.

    Args:
        db: DatabaseManager instance (injected from main.py)

    Returns:
        gr.Blocks instance ready for .launch()
    """
    import gradio as gr

    # Inject db into api module so chat_fn can access it
    if db is not None:
        from backend.api import set_db_manager
        set_db_manager(db)

    with gr.Blocks(
        title="农业新闻 AI 助手",
        fill_height=True,
    ) as demo:
        gr.ChatInterface(
            fn=chat_fn,
            api_name="chat",
            chatbot=gr.Chatbot(height=480),
            textbox=gr.Textbox(
                placeholder="问我关于农业新闻、灾害预警、市场动态等问题...",
                container=False,
                scale=7,
            ),
            title=None,
            description=None,
            examples=[
                "当前有多少条新闻？",
                "最近有什么灾害预警？",
                "舆情评分是多少？",
                "搜索关于水稻的新闻",
                "有哪些新闻分类？",
            ],
            cache_examples=False,
        )

    # Remove X-Frame-Options to allow iframe embedding
    # Gradio 6.x uses FastAPI internally — add middleware
    try:
        from starlette.middleware.base import BaseHTTPMiddleware

        class AllowFrameMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                response = await call_next(request)
                # Remove header that blocks iframe embedding
                response.headers.pop("X-Frame-Options", None)
                response.headers["X-Frame-Options"] = "SAMEORIGIN"
                return response

        # Access the underlying FastAPI app
        if hasattr(demo, "app") and hasattr(demo.app, "add_middleware"):
            # Gradio 6.x: demo.app is the FastAPI instance
            demo.app.user_middleware.insert(0, (AllowFrameMiddleware, {},))
            logger.info("[Chatbot] X-Frame-Options middleware 已添加")
    except Exception as e:
        logger.warning(f"[Chatbot] 无法添加 X-Frame-Options middleware: {e}")

    return demo
