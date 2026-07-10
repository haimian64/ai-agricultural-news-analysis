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
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache (lazy singleton — same pattern as model_inference.py)
# ---------------------------------------------------------------------------
_model_cache: dict = {}
_conversations: dict = {}  # {session_hash: {"messages": [...], "last_active": timestamp}}
_cleanup_thread_started = False

# ---------------------------------------------------------------------------
# 城市→省份映射（从 CITY_COORDS 构建，用于地区层级推理）
# ---------------------------------------------------------------------------
_city_to_province: dict[str, str] = {}


def _init_city_province_map():
    """从 backend/api.py 的 CITY_COORDS 注释中解析城市→省份映射"""
    global _city_to_province
    if _city_to_province:
        return
    import re
    from pathlib import Path
    api_path = Path(__file__).parent / "api.py"
    if not api_path.exists():
        return
    content = api_path.read_text(encoding="utf-8")
    start = content.find("CITY_COORDS = {")
    if start < 0:
        return
    # Find matching closing brace
    depth = 0
    end = start
    for i, ch in enumerate(content[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    block = content[start:end]
    current_province = ""
    for line in block.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            current_province = stripped[2:].strip()
        else:
            m = re.match(r'"(.+?)"\s*:', stripped)
            if m and current_province:
                city_full = m.group(1)
                _city_to_province[city_full] = current_province
                # Also map without common suffixes (市/县/区/州/盟/地区/林区)
                base = re.sub(r'[市县区州盟]$', '', city_full)
                if base and base != city_full and base not in _city_to_province:
                    _city_to_province[base] = current_province
                # Handle 地区/林区 suffix
                base2 = re.sub(r'(地区|林区)$', '', city_full)
                if base2 and base2 != city_full and base2 not in _city_to_province:
                    _city_to_province[base2] = current_province


_init_city_province_map()

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

        # --- 农产品价格概览 ---
        price_text = "暂无价格数据（请点击「手动提取所有价格」获取）"
        price_fetched_at = ""
        try:
            all_prices = []
            from backend.api import COMMODITY_CATEGORIES
            for cat, items in COMMODITY_CATEGORIES.items():
                cat_prices = []
                for commodity in items:
                    cached = db.get_commodity_price(commodity)
                    if cached:
                        p = cached.get("current_price", 0)
                        chg = cached.get("change", 0)
                        dir_sign = "↑" if chg > 0 else ("↓" if chg < 0 else "→")
                        cat_prices.append(f"{commodity} {p}元 {dir_sign}")
                if cat_prices:
                    all_prices.append(f"  {cat}：" + " | ".join(cat_prices))
            if all_prices:
                # Get the latest fetched_at from any commodity
                first = db.get_commodity_price(list(COMMODITY_CATEGORIES.values())[0][0])
                if first:
                    price_fetched_at = first.get("updated_at", "")
                price_text = "\n".join(all_prices)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"[Chatbot] 构建系统提示失败: {e}")
        total_news = total_disasters = analyzed = 0
        cat_summary = sentiment_text = recent_news_text = disasters_text = price_text = "获取失败"
        price_fetched_at = ""

    now = datetime.now()
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    day_labels = ["今天", "明天", "后天", "三天后", "四天后", "五天后", "六天后", "七天后"]

    date_lines = []
    for i, label in enumerate(day_labels):
        d = now + timedelta(days=i)
        date_lines.append(f"- {label}：{d.strftime('%Y年%m月%d日')}（星期{weekdays[d.weekday()]}）")
    date_table = "\n".join(date_lines)
    tomorrow_iso = (now + timedelta(days=1)).strftime("%Y-%m-%d")  # for format hint

    prompt = f"""你是一个专业的农业新闻分析助手。你可以帮助用户了解最新的农业新闻、灾害预警、市场动态、农产品价格和舆情分析。

## 日期速查表
{date_table}

查询天气时，请根据用户提到的相对日期（如「明天」「三天后」），在上表中查出对应的准确日期，然后在 get_weather 返回的天气预报中找到该日期的数据回答。
get_weather 的 daily.time 字段使用 YYYY-MM-DD 格式，例如上表中「明天」对应 {tomorrow_iso}。

## 当前数据库统计
- 新闻总数：{total_news} 条（已分析 {analyzed} 条）
- 灾害预警数：{total_disasters} 条
- 舆情综合评分：{sentiment_text}
- 分类分布：{cat_summary}

## 最近新闻
{recent_news_text}

## 活跃灾害预警
{disasters_text}

## 农产品价格概览{" (更新时间: " + price_fetched_at + ")" if price_fetched_at else ""}
{price_text}

## 可用工具
当用户需要更具体的数据时，你可以使用以下工具格式调用：
<tool_call>
{{"name": "<函数名>", "arguments": {{"<参数>": "<值>"}}}}
</tool_call>

可用的工具函数：
- get_statistics：获取完整统计信息（无参数）
- search_news：按关键词搜索新闻（参数：keyword）
- get_recent_news：获取最近新闻（参数：limit，默认10）
- get_disasters：获取活跃灾害预警（参数：region，可选，如"广东"、"河南"、"全国"。不传region则返回所有灾害）
- get_sentiment_summary：获取舆情分析总结（无参数）
- get_news_by_category：按分类查询新闻（参数：category，可选值：政策法规、市场行情、农业科技、灾害预警、国际农业、综合资讯）
- get_weather：查询指定城市的天气（参数：city，如"北京"、"上海"、"广州"等）
- get_price_overview：获取所有农产品价格概览（无参数），返回每个品种的当前价格和涨跌
- get_price_detail：查询某个农产品的详细价格数据（参数：commodity，如"稻谷"、"生猪"、"玉米"），返回价格、趋势、各省均价、批发市场排名
- get_price_region：查询某个品种在特定地区的价格（参数：commodity（品种名）、region（地区名，如"全国"、"广东"、"广州"）），自动处理全国→省→市的地域层级关系

## 地区层级推理
价格数据包含全国均价、各省均价和批发市场价格，具有天然的地域层级关系：
**全国 > 省/直辖市/自治区 > 城市/批发市场**

- 「全国」「中国」「国内」→ 使用 national_avg（全国均价），包含所有省份和批发市场数据
- 「广东省」「广东」→ 查找 provinces 中 province 为「广东省」的条目，以及该省所有批发市场
- 「广州」「广州市」「广州江南」→ 自动识别为广东省的城市，查找广东省下 matching 的市场或省份数据
- 各省份之间互不包含（如「广东」不包含「广西」）
- 回答地区价格时，需同时给出**全国均价作为参照**，并标注该地区价格与全国均价的差值
- 举例（多工具组合）：用户问「广州天气+农业建议」→ 同时调用 get_weather(city="广州") + get_disasters(region="广东") → 如天气失败则用灾害数据 + get_price_region 查广州主要农产品 → 基于实际灾害类型和受影响品种给出针对性建议

## 灾害地区查询
- 用户问「广东有什么灾害」「河南近期灾害」→ 调用 get_disasters(region="广东") 获取该地区灾害
- 用户问特定地区的灾害影响和补救措施 → 先查灾害，再查该地区主要农产品价格（get_price_region），结合两者分析影响
- **综合查询模式**：当用户问「天气+农业」类问题时，应同时调用天气和灾害工具。如果天气工具失败，用灾害数据 + 价格数据 + 地区信息综合分析
- **不要**把其他地区的灾害说成是用户询问地区的灾害（如不要把「呼伦贝尔」的暴雨说成是广东的）
- 如果没有该地区的灾害数据，诚实告知「目前系统中没有XX地区的活跃灾害预警」
- region 参数支持模糊匹配（如传"广东"可匹配"广东"、"广东省"、"云南、贵州、广西、广东..."等多值字段）

## 价格分析能力
- 用户问「哪个品种价格最高/最低」→ 基于上方价格概览直接回答
- 用户问「稻谷多少钱」「玉米什么价」→ 价格概览中查找，直接回答
- 用户问「价格趋势」「涨跌」→ 概览中 ↑/↓ 箭头 + 调用 get_price_detail 查看趋势
- 用户问「广州猪价」「广东玉米价」→ 调用 get_price_region
- 用户问「某个品种详细分析」「各省对比」→ 调用 get_price_detail

## 工具调用格式（重要！）
当你需要调用工具时，必须严格按照以下 XML 格式输出，不要输出裸 JSON：

<tool_call>
{{"name": "函数名", "arguments": {{"参数名": "参数值"}}}}
</tool_call>

## 时间感知
- 上方「日期速查表」列出了今天及未来七天的准确日期，请直接用它来查日期，不要自己计算
- 用户说「今天」「明天」「三天后」→ 在速查表中找到对应的准确日期
- 回答天气问题时，必须明确说出完整的年月日，例如「今天是2026年07月09日」「三天后是2026年07月12日」
- get_weather 返回的 daily.time 字段使用 YYYY-MM-DD 格式（如 2026-07-09），查询结果后按日期匹配对应的预报数据
- 如果用户问的日期超出了七天范围（如「下个月」），诚实告知天气预报最多只能查询未来七天

## 注意事项
- 回答要简洁、专业、使用中文
- **当用户询问特定地区（如「广东」「广州」）的信息时，必须调用带 region 参数的工具获取该地区的真实数据**。系统提示词中的「活跃灾害预警」是无过滤的全部数据，不能替代地区查询
- **工具调用失败时的降级策略**：如果某个工具返回错误（如天气查询失败），应尝试调用其他相关工具获取数据。例如天气失败时 → 调用 get_disasters(region="广东") 获取该地区灾害 → 结合价格数据分析影响
- **农业建议必须基于实际数据**：不要给出「注意排水」「加固设施」等泛泛而谈的建议，而是根据该地区实际灾害类型（暴雨/台风/干旱）和受影响农产品，给出针对性措施
- 工具调用必须用 <tool_call> 标签包裹，不要直接输出 JSON
- 不要编造数据，如果数据库中没有相关信息，诚实告知用户
"""
    return prompt


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def _query_weather(city: str) -> str:
    """Query Open-Meteo API for city weather. Returns JSON string."""
    import urllib.request
    from backend.api import CITY_COORDS

    if not city or not city.strip():
        return json.dumps({"error": "请提供城市名称，例如：北京、上海、广州"}, ensure_ascii=False)

    # Fuzzy match: try exact match first, then partial match
    coords = CITY_COORDS.get(city.strip())
    if not coords:
        # Try with "市" suffix
        coords = CITY_COORDS.get(city.strip() + "市")
    if not coords:
        # Try partial match (city name contains query or vice versa)
        for name, c in CITY_COORDS.items():
            if city.strip() in name or name in city.strip():
                coords = c
                break

    if not coords:
        return json.dumps(
            {"error": f"暂不支持查询「{city}」的天气。请使用具体城市名，如：北京、上海、广州、成都等。",
             "city": city},
            ensure_ascii=False,
        )

    try:
        params = f"latitude={coords['lat']}&longitude={coords['lon']}"
        api_url = (
            "https://api.open-meteo.com/v1/forecast?" + params +
            "&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum"
            "&current_weather=true&timezone=Asia/Shanghai"
        )
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        current = data.get("current_weather", {})
        daily = data.get("daily", {})

        # Build a readable summary for the chatbot
        weather_info = {
            "city": city.strip(),
            "当前天气": {
                "温度": f"{current.get('temperature', 'N/A')}°C",
                "风速": f"{current.get('windspeed', 'N/A')} km/h",
                "风向": f"{current.get('winddirection', 'N/A')}°",
                "天气代码": current.get("weathercode", "N/A"),
            },
        }

        if daily:
            days = len(daily.get("time", []))
            if days > 0:
                weather_info["未来天气预报"] = []
                for i in range(min(days, 7)):
                    day_info = {
                        "日期": daily["time"][i],
                        "最高温": f"{daily.get('temperature_2m_max', [None])[i]}°C",
                        "最低温": f"{daily.get('temperature_2m_min', [None])[i]}°C",
                        "降水量": f"{daily.get('precipitation_sum', [None])[i]} mm",
                    }
                    weather_info["未来天气预报"].append(day_info)

        return json.dumps(weather_info, ensure_ascii=False, default=str)
    except Exception as e:
        logger.error(f"[Chatbot] 天气查询失败 ({city}): {e}")
        return json.dumps({"error": f"天气查询失败: {e}", "city": city}, ensure_ascii=False)


def _get_price_overview(db) -> str:
    """获取所有农产品价格概览（紧凑格式）"""
    from backend.api import COMMODITY_CATEGORIES
    all_prices = []
    for cat, items in COMMODITY_CATEGORIES.items():
        cat_data = {"category": cat, "items": []}
        for commodity in items:
            cached = db.get_commodity_price(commodity)
            if cached:
                cat_data["items"].append({
                    "commodity": commodity,
                    "current_price": cached.get("current_price", 0),
                    "change": cached.get("change", 0),
                    "change_pct": cached.get("change_pct", 0),
                    "national_avg": cached.get("national_avg", 0),
                    "unit": cached.get("unit", "元/公斤"),
                })
        if cat_data["items"]:
            all_prices.append(cat_data)
    return json.dumps({
        "total_categories": len(all_prices),
        "total_commodities": sum(len(c["items"]) for c in all_prices),
        "categories": all_prices,
    }, ensure_ascii=False)


def _get_price_detail(db, commodity: str) -> str:
    """获取单个农产品的详细价格数据"""

    def _resolve_region(cached, region: str) -> dict | None:
        """根据地区名称（全国/省/市）从价格数据中提取相关子集。
        返回 None 表示未匹配到任何数据。
        """
        if not cached or not region:
            return None

        region = region.strip()
        provinces = cached.get("provinces", [])
        wholesale = cached.get("wholesale", [])

        # 全国/整体 → 返回全部
        if region in ("全国", "整体", "全部", "所有", "中国", "国内"):
            return cached

        # 先尝试在省份数据中匹配
        matched_provinces = [p for p in provinces if region in p.get("province", "")]
        if not matched_provinces:
            # 尝试用 city→province 映射
            actual_province = _city_to_province.get(region, region)
            if actual_province != region:
                matched_provinces = [p for p in provinces if actual_province in p.get("province", "")]

        # 匹配批发市场（城市/市场名）
        matched_markets = []
        for w in wholesale:
            mkt = w.get("market", "")
            prov = w.get("province", "")
            if region in mkt or region in prov:
                matched_markets.append(w)

        # 如果省份匹配到了，也收集该省份的批发市场
        if matched_provinces:
            prov_names = {p.get("province", "") for p in matched_provinces}
            for w in wholesale:
                if w.get("province", "") in prov_names and w not in matched_markets:
                    matched_markets.append(w)

        if matched_provinces or matched_markets:
            result = {"commodity": cached.get("commodity", commodity)}
            if matched_provinces:
                result["provinces"] = matched_provinces
            if matched_markets:
                result["wholesale"] = matched_markets[:20]  # limit to top 20
            # 计算该地区的均价
            all_prices = [p.get("price", 0) for p in matched_provinces if p.get("price")]
            if matched_markets:
                all_prices.extend([m.get("price", 0) for m in matched_markets if m.get("price")])
            if all_prices:
                result["region_avg"] = round(sum(all_prices) / len(all_prices), 2)
                result["region"] = region
            return result

        return None

    cached = db.get_commodity_price(commodity)
    if not cached:
        # Try fuzzy match
        from backend.api import COMMODITY_CATEGORIES
        for items in COMMODITY_CATEGORIES.values():
            for item in items:
                if commodity in item or item in commodity:
                    cached = db.get_commodity_price(item)
                    if cached:
                        break
            if cached:
                break
    if not cached:
        return json.dumps({"error": f"未找到「{commodity}」的价格数据。请使用具体品种名如：稻谷、小麦、玉米、猪、大白菜等"}, ensure_ascii=False)

    # Include geographic context
    response = dict(cached)
    response["_geo_hint"] = (
        "该数据包含全国各省均价(provinces)和主要批发市场价格(wholesale)。"
        "省份数据约27条，批发市场数据约60条。每个批发市场都有province字段标明所属省份。"
        "如果要查询特定地区（如'广东'、'广州'），请使用 get_price_region 工具。"
    )
    return json.dumps(response, ensure_ascii=False)


def _get_price_region(db, commodity: str, region: str) -> str:
    """按地区查询价格：支持全国、省名、城市名/市场名"""
    if not commodity or not region:
        return json.dumps({"error": "请提供品种名和地区名，例如：commodity=猪, region=广州"}, ensure_ascii=False)

    cached = db.get_commodity_price(commodity)
    if not cached:
        from backend.api import COMMODITY_CATEGORIES
        for items in COMMODITY_CATEGORIES.values():
            for item in items:
                if commodity in item or item in commodity:
                    cached = db.get_commodity_price(item)
                    break
            if cached:
                break

    if not cached:
        return json.dumps({"error": f"未找到「{commodity}」的价格数据"}, ensure_ascii=False)

    # Build result with geographic reasoning
    region = region.strip()
    provinces = cached.get("provinces", [])
    wholesale = cached.get("wholesale", [])

    # Determine geographic scope
    if region in ("全国", "整体", "全部", "所有", "中国", "国内"):
        return json.dumps({
            "region": "全国",
            "commodity": cached.get("commodity", commodity),
            "national_avg": cached.get("national_avg", cached.get("current_price", 0)),
            "current_price": cached.get("current_price", 0),
            "change": cached.get("change", 0),
            "change_pct": cached.get("change_pct", 0),
            "province_count": len(provinces),
            "market_count": len(wholesale),
            "unit": cached.get("unit", "元/公斤"),
            "note": "全国数据汇总了所有省份和批发市场的价格信息",
        }, ensure_ascii=False)

    # Try province match first
    matched_provinces = []
    actual_province = _city_to_province.get(region, region)
    # Also try with common suffixes
    if actual_province == region:
        for suffix in ("市", "省", "县"):
            alt = _city_to_province.get(region + suffix, "")
            if alt:
                actual_province = alt
                break
    for p in provinces:
        pname = p.get("province", "")
        if region in pname or actual_province in pname or pname in actual_province:
            matched_provinces.append(p)

    # Try market/city match
    matched_markets = []
    for w in wholesale:
        mkt = w.get("market", "")
        prov = w.get("province", "")
        if region in mkt or region in prov or region + "市" in mkt:
            matched_markets.append(w)

    # If city→province mapping found, also include province data
    if actual_province != region and matched_provinces:
        pass  # already matched via province
    elif actual_province != region and not matched_provinces:
        # Try matching by resolved province
        for p in provinces:
            if actual_province in p.get("province", ""):
                matched_provinces.append(p)
        # Also add markets from that province
        if matched_provinces:
            prov_names = {p.get("province", "") for p in matched_provinces}
            for w in wholesale:
                if w.get("province", "") in prov_names and w not in matched_markets:
                    matched_markets.append(w)

    if not matched_provinces and not matched_markets:
        # Last resort: suggest similar regions
        all_region_names = set()
        for p in provinces:
            all_region_names.add(p.get("province", ""))
        for w in wholesale:
            all_region_names.add(w.get("market", ""))
        suggestions = [r for r in sorted(all_region_names) if region[:2] in r][:5]
        return json.dumps({
            "error": f"未找到「{region}」的价格数据",
            "hint": f"请使用省份全名（如「{actual_province}」）或者批发市场名查询",
            "suggestions": suggestions or list(sorted(all_region_names))[:10],
        }, ensure_ascii=False)

    # Build result
    result = {
        "region": region,
        "resolved_to": actual_province if actual_province != region else None,
        "commodity": cached.get("commodity", commodity),
        "national_avg": cached.get("national_avg", cached.get("current_price", 0)),
        "unit": cached.get("unit", "元/公斤"),
    }
    if matched_provinces:
        result["provinces"] = matched_provinces
    if matched_markets:
        result["wholesale"] = matched_markets[:15]

    # Compute region average
    all_prices = [p.get("price", 0) for p in matched_provinces if p.get("price")]
    all_prices.extend([m.get("price", 0) for m in matched_markets if m.get("price")])
    if all_prices:
        result["region_avg_price"] = round(sum(all_prices) / len(all_prices), 2)
        # Compare with national average
        national = cached.get("national_avg", 0) or cached.get("current_price", 0)
        if national > 0:
            diff = round(result["region_avg_price"] - national, 2)
            result["vs_national"] = f"{'+' if diff>0 else ''}{diff}元 ({'+' if diff>0 else ''}{round(diff/national*100,1)}%)"

    return json.dumps(result, ensure_ascii=False)


def _make_tool_handlers(db):
    """Create tool dispatch table bound to a DatabaseManager instance."""
    return {
        "get_statistics": lambda **kw: json.dumps(
            db.get_statistics(), ensure_ascii=False, default=str),
        "search_news": lambda keyword="", **kw: json.dumps(
            db.search_news(keyword, limit=10), ensure_ascii=False, default=str),
        "get_recent_news": lambda limit=10, **kw: json.dumps(
            db.get_all_news(limit=int(limit), offset=0), ensure_ascii=False, default=str),
        "get_disasters": lambda region="", **kw: json.dumps(
            db.get_active_disasters(limit=10, region=region if region else None),
            ensure_ascii=False, default=str),
        "get_sentiment_summary": lambda **kw: json.dumps(
            db.get_sentiment_summary(), ensure_ascii=False),
        "get_news_by_category": lambda category="", **kw: json.dumps(
            db.get_all_news(limit=10, category=category), ensure_ascii=False, default=str),
        "get_weather": lambda city="", **kw: _query_weather(city),
        "get_price_overview": lambda **kw: _get_price_overview(db),
        "get_price_detail": lambda commodity="", **kw: _get_price_detail(db, commodity),
        "get_price_region": lambda commodity="", region="", **kw: _get_price_region(db, commodity, region),
    }


def _parse_tool_calls(text: str) -> list[dict]:
    """Parse tool calls from model output (XML-wrapped or bare JSON)."""
    tools = []

    # Method 1: <tool_call>{json}</tool_call> XML blocks
    xml_pattern = r"<tool_call>\s*(.*?)\s*</tool_call>"
    for m in re.findall(xml_pattern, text, re.DOTALL):
        try:
            tool = json.loads(m.strip())
            if "name" in tool:
                tools.append(tool)
        except json.JSONDecodeError:
            logger.warning(f"[Chatbot] 无法解析 XML 工具调用: {m[:200]}")

    if tools:
        return tools

    # Method 2: bare JSON tool calls like {"name": "get_weather", "arguments": {...}}
    # Use brace counting to find JSON objects, then check if they are valid tool calls
    known_tools = {
        "get_statistics", "search_news", "get_recent_news", "get_disasters",
        "get_sentiment_summary", "get_news_by_category", "get_weather",
        "get_price_overview", "get_price_detail", "get_price_region",
    }
    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        end = start
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        candidate = text[start:end]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and "name" in obj and obj["name"] in known_tools:
                tools.append(obj)
        except (json.JSONDecodeError, ValueError):
            pass

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
# DeepSeek API 调用
# ---------------------------------------------------------------------------

def _chat_via_deepseek(messages: list[dict], db) -> str:
    """通过 DeepSeek API 进行对话，支持工具调用"""
    from config import config
    from openai import OpenAI

    client = OpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
    )

    max_rounds = 10
    for round_num in range(max_rounds + 1):
        response = client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=102400,
        )
        content = response.choices[0].message.content or ""

        # Check for tool calls
        tool_calls = _parse_tool_calls(content)
        if tool_calls and round_num < max_rounds:
            tool_results = []
            for tc in tool_calls:
                name = tc.get("name", "")
                args = tc.get("arguments", {})
                result = _execute_tool(db, name, args)
                tool_results.append(f"[{name}]: {result}")

            messages.append({"role": "assistant", "content": content})
            tool_result_msg = "工具执行结果：\n" + "\n".join(tool_results)
            messages.append({"role": "system", "content": tool_result_msg})
            logger.info(f"[DeepSeek] 第{round_num+1}轮工具调用: {[t.get('name') for t in tool_calls]}")
            continue

        # Final response — strip tool call tags
        display_text = re.sub(r"<tool_call>.*?</tool_call>", "", content, flags=re.DOTALL)
        known_tool_names = (
            "get_statistics|search_news|get_recent_news|get_disasters"
            "|get_sentiment_summary|get_news_by_category|get_weather"
            "|get_price_overview|get_price_detail|get_price_region"
        )
        display_text = re.sub(
            r'\{\s*"name"\s*:\s*"(' + known_tool_names + r')"[^}]*\}',
            "", display_text
        ).strip()
        return display_text or "抱歉，我暂时无法回答这个问题。"

    return "抱歉，处理超时，请重新提问。"


# ---------------------------------------------------------------------------
# Main chat function (for Gradio ChatInterface)
# ---------------------------------------------------------------------------

def chat_fn(message: str, history: list):
    """
    Chat function for Gradio ChatInterface.
    默认使用 DeepSeek API，失败时自动回退到本地 Qwen 模型。
    """
    # Get database instance
    from backend.api import get_db
    db = get_db()

    # Get or create session
    session_hash = "default"

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

    # Try DeepSeek API first, fall back to local Qwen on failure
    from config import config
    deepseek_failed = False
    if config.DEEPSEEK_API_KEY:
        try:
            result = _chat_via_deepseek(messages, db)
            messages.append({"role": "assistant", "content": result})
            session_msgs = [m for m in messages if m["role"] != "system"]
            session["messages"] = session_msgs[-40:]
            session["last_active"] = time.time()
            yield result
            return
        except Exception as e:
            logger.warning(f"[Chatbot] DeepSeek API 失败，回退到本地模型: {e}")
            deepseek_failed = True
    else:
        deepseek_failed = True  # No key configured, go straight to local

    # Fallback: load local Qwen model
    if deepseek_failed:
        try:
            model, tokenizer = _ensure_model_loaded()
        except Exception as e:
            logger.error(f"[Chatbot] 本地模型加载失败: {e}")
            yield "抱歉，AI 服务暂时不可用（DeepSeek API 和本地模型均失败），请稍后重试。"
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
        # Strip tool call tags and bare JSON tool calls for display
        display_text = re.sub(r"<tool_call>.*?</tool_call>", "", clean_response, flags=re.DOTALL)
        known_tool_names = (
            "get_statistics|search_news|get_recent_news|get_disasters"
            "|get_sentiment_summary|get_news_by_category|get_weather"
            "|get_price_overview|get_price_detail|get_price_region"
        )
        display_text = re.sub(
            r'\{\s*"name"\s*:\s*"(' + known_tool_names + r')"[^}]*\}',
            "", display_text
        ).strip()
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
# Gradio CSS (must be at module level for import by main.py)
# ---------------------------------------------------------------------------

_CHATBOT_CSS = """
/* 确保 Gradio 填满 iframe */
html, body, #root { height: 100%; margin: 0; padding: 0; }
.gradio-container { height: 100% !important; max-width: 100% !important; padding: 0 !important; }
/* 发送按钮 — 蓝底白字 */
.chat-submit-row button {
    background: #1a5276 !important;
    color: #fff !important;
    border: 1px solid #1a5276 !important;
    border-radius: 6px !important;
    font-weight: 500 !important;
    padding: 6px 16px !important;
    cursor: pointer !important;
    transition: background 0.2s !important;
}
.chat-submit-row button:hover {
    background: #2e86c1 !important;
    border-color: #2e86c1 !important;
}
.chat-submit-row button:active {
    background: #154360 !important;
    transform: scale(0.97);
}
"""

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
    from config import config

    # Log backend mode
    if config.CHATBOT_BACKEND == "deepseek":
        logger.info(f"[Chatbot] 使用 DeepSeek API ({config.DEEPSEEK_MODEL})")
    else:
        logger.info(f"[Chatbot] 使用本地模型 ({config.CHATBOT_MODEL})")

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
            chatbot=gr.Chatbot(height="100%"),
            textbox=gr.Textbox(
                placeholder="问我关于农业新闻、灾害预警、市场动态等问题...",
                container=False,
                scale=7,
                submit_btn="发送",
                elem_classes="chat-submit-row",
            ),
            fill_height=True,
            title=None,
            description=None,
            examples=[
                "当前有多少条新闻？最近有什么灾害？",
                "广东近期有什么灾害，对农户有什么影响和补救建议？",
                "全国猪肉价格怎么样，哪个省最便宜？",
                "广州近期天气如何，对农业生产有什么建议？",
                "最近农产品市场行情如何，哪些品种在涨价？",
                "帮我分析一下近期农业舆情",
            ],
            example_labels=[
                "📊 综合查询",
                "🌧️ 地区灾害分析",
                "💰 价格对比",
                "🌤️ 天气+农业建议",
                "📈 市场行情",
                "📝 舆情分析",
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
