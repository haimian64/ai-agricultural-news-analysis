"""
AI 灾害信息提取模块

从分类为"灾害预警"的新闻中，使用 Qwen2.5-3B-Instruct 模型提取结构化灾害信息：
发生时间、地点、灾害类型、严重程度、防灾建议。

流程：查询灾害新闻 → 按需抓取正文 → Qwen 分析 → 写入 disaster_warnings
复用 backend/chatbot.py 的 Qwen 模型实例（共享 _model_cache），不重复加载。
"""
import json, logging, re, time, urllib.request, urllib.error
from datetime import datetime, timedelta

from lxml import html as lxml_html
from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一个专业的农业灾害信息提取助手。你的任务是从新闻标题中提取灾害相关的结构化信息。

## 灾害类型参考
- 台风/热带气旋
- 暴雨洪涝
- 干旱
- 冰雹
- 霜冻/冻害
- 病虫害（蝗虫、稻飞虱、草地贪夜蛾等）
- 高温热害
- 倒春寒
- 大风
- 雪灾
- 地质灾害（滑坡、泥石流）
- 其他灾害

## 灾害严重程度映射
根据标题中的气象预警信号判断：
- 1（特别重大）: "红色预警" / "I级响应" / "特别重大"
- 2（重大）:     "橙色预警" / "II级响应" / "重大"
- 3（较重）:     "黄色预警" / "III级响应" / "较重"
- 4（一般）:     "蓝色预警" / "IV级响应" / "一般"
- 99（未知）:    标题中无预警级别信息

## 发生时间判断
- 如果标题中明确提到了日期（如"6月25日"），请结合当前日期推断年份，输出为 YYYY-MM-DD 格式
- 如果标题中使用了相对时间（如"今日"、"明天"、"近日"），请结合给定的文章日期推断
- 如果无法判断，填写 null

## 输出格式
对于每一条新闻，输出一个 JSON 对象。将所有对象放入一个 JSON 数组中。
每个对象包含以下字段：

```
{
  "article_id": "原始新闻的 id",
  "occurrence_time": "YYYY-MM-DD 或 null",
  "region": "省/市/县名称 或 null",
  "disaster_type": "灾害类型（从参考列表选最匹配的）或 null",
  "severity": 1 到 4 或 99,
  "alert_level": "红/橙/黄/蓝 或 null",
  "suggestions": "针对该灾害的农业防灾建议（1-2句话，如果没有灾害信息则为 null）"
}
```

## 重要约束
- 输入包含新闻标题和正文内容，请优先从正文中提取详细信息，标题作为补充
- 不要编造文本中没有的信息，不确定的字段填 null
- 建议(suggestions)字段可根据灾害类型给出通用的农业防灾建议
- 如果文章完全不含灾害信息，所有字段留 null 但保留 article_id
- **仅输出 JSON 数组，不要输出任何其他文字、解释或 markdown 标记**"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_extraction_messages(articles_batch: list[dict], today_str: str) -> list[dict]:
    """构造发送给 Qwen 的消息列表（system + user）。"""
    items = []
    for a in articles_batch:
        content = (a.get("content") or "").strip()
        items.append({
            "id": a["id"],
            "title": a.get("title", ""),
            "date": (a.get("date", "") or "")[:10],
            "content": content[:800],  # 截取正文前 800 字符，避免超出模型上下文
        })

    user_text = json.dumps(items, ensure_ascii=False, indent=2)
    user_prompt = (
        f"今天是 {today_str}。请从以下新闻的标题和正文中提取灾害相关信息。\n\n"
        f"```json\n{user_text}\n```\n\n"
        "请直接输出 JSON 数组："
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def _parse_model_output(raw_text: str) -> list[dict]:
    """从模型原始输出中提取 JSON 数组。"""
    # 尝试直接解析
    text = raw_text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # 尝试提取 [...] 块
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # 尝试逐行提取 {...} 对象
    objects = []
    for m in re.finditer(r"\{[^{}]*\}", text):
        try:
            objects.append(json.loads(m.group(0)))
        except json.JSONDecodeError:
            continue
    if objects:
        return objects

    logger.warning(f"[DisasterExtraction] 无法解析模型输出，原始文本前 500 字符: {text[:500]}")
    return []


def _generate_json_from_model(model, tokenizer, messages: list[dict]) -> str:
    """用 Qwen 模型生成输出，返回解码后的文本。"""
    import torch

    # 尝试使用 chat_template，失败则回退到手动拼接
    try:
        prompt_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
    except Exception:
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
        prompt_text = "\n".join(parts)

    inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=1536,
            temperature=0.3,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    input_len = inputs.input_ids.shape[1]
    generated_ids = outputs[0][input_len:]
    response = tokenizer.decode(generated_ids, skip_special_tokens=False)
    # 清理特殊 token
    response = response.replace("<|im_end|>", "").replace("<|im_start|>", "").strip()
    return response


def _update_disaster_record(db, article_id: str, extracted: dict):
    """用提取结果更新 disaster_warnings 表中的一条记录。"""
    db.conn.execute(
        """UPDATE disaster_warnings
           SET region = ?,
               alert_level = ?,
               severity = ?,
               disaster_type = ?,
               description = ?
           WHERE id = ?""",
        (
            (extracted.get("region") or "").strip(),
            (extracted.get("alert_level") or "").strip(),
            _safe_int(extracted.get("severity"), 99),
            (extracted.get("disaster_type") or "").strip(),
            (extracted.get("suggestions") or "")[:500],
            article_id,
        ),
    )


def _safe_int(value, default=99):
    """安全转换为 int，失败时返回默认值。0 表示 AI 已尝试但未发现灾害。"""
    try:
        v = int(value)
        if v in (0, 1, 2, 3, 4, 99):
            return v
        return default
    except (TypeError, ValueError):
        return default


def _fetch_article_content(url: str) -> str:
    """抓取单篇文章的正文内容，失败时返回空字符串。"""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": config.USER_AGENT,
                          "Accept": "text/html,application/xhtml+xml"}
        )
        with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"[DisasterExtraction] 正文抓取失败: {url[:80]}... {e}")
        return ""

    try:
        doc = lxml_html.fromstring(html)
    except Exception:
        return ""

    # 移除无关标签
    for tag in doc.xpath("//script|//style|//nav|//footer"):
        if tag.getparent() is not None:
            tag.getparent().remove(tag)

    # 按优先级尝试正文选择器
    for xp in ["//div[contains(@class,'article-content')]",
               "//div[contains(@class,'content')]",
               "//div[contains(@class,'text')]",
               "//article", "//div[@id='content']",
               "//div[contains(@class,'article')]"]:
        els = doc.xpath(xp)
        if els:
            text = "\n".join(els[0].text_content().split())
            if len(text) > 50:
                return text

    # 回退：提取长段落
    ps = doc.xpath("//p")
    texts = [p.text_content().strip() for p in ps if len(p.text_content().strip()) > 20]
    return "\n".join(texts[:20]) if texts else ""


def extract_disaster_info_from_ai(db, force=False) -> dict:
    """
    从灾害类新闻中提取结构化信息。

    流程：
    1. 查询时间窗口内 category='灾害预警' 的新闻
    2. 按需抓取正文（仅对未抓取过的文章）
    3. 用 Qwen 模型批量提取 structured fields
    4. UPDATE disaster_warnings 表

    返回: {"input_count": N, "extracted_count": M, "fetched_content": N}
    """
    # Step 1: 查询灾害新闻
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=config.DISASTER_NEWS_WINDOW_DAYS)).strftime("%Y-%m-%d")

    articles = db.get_news_by_date_range_and_category(
        start_date, end_date, "灾害预警", limit=500
    )

    if not articles:
        logger.info(f"[DisasterExtraction] 时间窗口 ({start_date} ~ {end_date}) 内无灾害新闻")
        return {"input_count": 0, "extracted_count": 0, "fetched_content": 0}

    logger.info(
        f"[DisasterExtraction] 查询到 {len(articles)} 条灾害新闻 "
        f"({start_date} ~ {end_date})"
    )

    # Step 2: 按需抓取正文（仅对 content 为空或等于 title 的文章）
    fetched = 0
    for a in articles:
        content = (a.get("content") or "").strip()
        title = (a.get("title") or "").strip()
        if not content or content == title:
            body = _fetch_article_content(a["url"])
            if body:
                a["content"] = body
                # 回写到 news_articles，下一次 crawl 无需重复抓取
                try:
                    db.conn.execute(
                        "UPDATE news_articles SET content = ? WHERE id = ?",
                        (body, a["id"]),
                    )
                except Exception:
                    pass
                fetched += 1
                time.sleep(config.REQUEST_DELAY * 0.5)
    if fetched:
        db.conn.commit()
        logger.info(f"[DisasterExtraction] 抓取正文 {fetched} 篇")

    # Step 2.5: 过滤已提取的文章，避免重复 AI 推理
    all_ids = [a["id"] for a in articles]
    already_extracted = db.get_already_extracted_disaster_ids(all_ids)
    unextracted = [a for a in articles if a["id"] not in already_extracted]
    skipped = len(articles) - len(unextracted)

    if skipped > 0:
        logger.info(
            f"[DisasterExtraction] 时间窗口内 {len(articles)} 条灾害新闻，"
            f"已提取 {skipped} 条，待分析 {len(unextracted)} 条"
        )

    if not unextracted:
        logger.info("[DisasterExtraction] 所有窗口内灾害新闻均已提取，跳过 AI 推理")
        return {
            "input_count": len(articles),
            "extracted_count": 0,
            "skipped_count": skipped,
            "fetched_content": fetched,
        }

    # Step 3: 加载模型并批量提取（仅对未提取的文章）
    try:
        from backend.chatbot import _ensure_model_loaded

        model, tokenizer = _ensure_model_loaded()
    except Exception as e:
        logger.error(f"[DisasterExtraction] 模型加载失败: {e}")
        return {
            "input_count": len(articles),
            "extracted_count": 0,
            "skipped_count": skipped,
            "fetched_content": fetched,
        }

    BATCH_SIZE = 8  # 正文模式每批 8 条，避免输出截断
    today_str = datetime.now().strftime("%Y年%m月%d日")
    total_extracted = 0

    for i in range(0, len(unextracted), BATCH_SIZE):
        batch = unextracted[i : i + BATCH_SIZE]
        messages = _build_extraction_messages(batch, today_str)

        try:
            response = _generate_json_from_model(model, tokenizer, messages)
            parsed = _parse_model_output(response)
        except Exception as e:
            logger.error(f"[DisasterExtraction] 批次 {i // BATCH_SIZE + 1} 推理失败: {e}")
            continue

        # 按 article_id 匹配回原始文章，便于后续审计
        id_to_article = {a["id"]: a for a in batch}

        for item in parsed:
            aid = item.get("article_id", "")
            article = id_to_article.get(aid)

            # 跳过无 article_id 或无法匹配的条目
            if not aid or not article:
                continue

            # 判断是否提取到了有效信息
            has_info = any(
                item.get(k)
                for k in ("occurrence_time", "region", "disaster_type", "suggestions")
            )

            # Step 4: 更新数据库（即使未提取到信息也写入，标记为已尝试）
            try:
                if not has_info and not force:
                    # 无灾害信息：标记 severity=0 表示"AI 已尝试，未发现灾害"
                    item["severity"] = 0
                _update_disaster_record(db, aid, item)
                total_extracted += 1
            except Exception as e:
                logger.error(f"[DisasterExtraction] 更新 {aid} 失败: {e}")

        logger.info(
            f"[DisasterExtraction] 批次 {i // BATCH_SIZE + 1}: "
            f"处理 {len(batch)} 条, 提取 {len(parsed)} 条"
        )

    # 提交所有更新
    db.conn.commit()

    logger.info(
        f"[DisasterExtraction] 完成: {len(articles)} 条输入, "
        f"已跳过 {skipped} 条, {total_extracted} 条已更新到数据库"
    )

    return {
        "input_count": len(articles),
        "extracted_count": total_extracted,
        "skipped_count": skipped,
        "fetched_content": fetched,
    }
