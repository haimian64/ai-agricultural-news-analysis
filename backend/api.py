"""API路由 - 添加搜索/日期筛选/情感摘要/市场数据端点"""
import asyncio, json, logging, random, math, urllib.request
from datetime import datetime, timedelta, date
import aiohttp
from aiohttp import web
from config import config

logger = logging.getLogger(__name__)
_db_manager = None


def set_db_manager(db):
    global _db_manager;
    _db_manager = db


def get_db():
    global _db_manager
    if _db_manager is None:
        from backend.database import DatabaseManager
        _db_manager = DatabaseManager()
        _db_manager.conn
    return _db_manager


def json_resp(data, status=200):
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))


async def handle_statistics(request):
    try:
        return json_resp(get_db().get_statistics())
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_news(request):
    limit = int(request.query.get("limit", "50"))
    offset = int(request.query.get("offset", "0"))
    cat = request.query.get("category", None)
    start = request.query.get("start_date", None)
    end = request.query.get("end_date", None)
    kw = request.query.get("keyword", None)
    try:
        if kw:
            if start and end:
                return json_resp(get_db().get_news_by_keyword_and_date(kw, start, end, limit))
            return json_resp(get_db().search_news(kw, limit))
        if start and end: return json_resp(get_db().get_news_by_date_range(start, end, limit))
        return json_resp(get_db().get_all_news(limit, offset, cat))
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_categories(request):
    return json_resp({"categories": config.CATEGORY_LABELS})


async def handle_disasters(request):
    limit = int(request.query.get("limit", "50"))
    try:
        result = get_db().get_active_disasters(limit)
        if not result:
            # 回退到新闻表中分类为"灾害预警"的文章
            result = get_db().get_all_news(limit, 0, "灾害预警")
        return json_resp(result)
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_analysis(request):
    try:
        results = get_db().get_recent_analysis("full_analysis")
        return json_resp(results[0] if results else {"message": "暂无分析结果"})
    except:
        return json_resp({"error": "分析失败"}, 500)


async def handle_keywords(request):
    try:
        results = get_db().get_recent_analysis("hot_keywords")
        data = results[0] if results else {"keywords": []}
        logger.info(f"[DEBUG] handle_keywords 返回: {{'keywords_count': {len(data.get('keywords', []))}}}")
        return json_resp(data)
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_trend(request):
    try:
        results = get_db().get_recent_analysis("trend")
        data = results[0] if results else {"trend": {}}
        trend_keys = list(data.get("trend", {}).keys()) if data.get("trend") else []
        logger.info(f"[DEBUG] handle_trend 返回: {{'trend_dates': {trend_keys}}}")
        return json_resp(data)
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_sentiment_summary(request):
    """情感摘要 + 综合得分"""
    start = request.query.get("start_date", None)
    end = request.query.get("end_date", None)
    try:
        summary = get_db().get_sentiment_summary(start, end)
        # Add comparison
        summary["analysis"] = f"今日农业舆情综合得分 {summary['score_10']} 分，整体偏向{summary['label']}"
        return json_resp(summary)
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_market(request):
    """市场数据 — 从数据库 market_data 表读取"""
    try:
        limit = int(request.query.get("limit", "30"))
        items = get_db().get_market_data(limit)
        return json_resp({
            "total": len(items),
            "items": [{"title": r["title"], "url": r["url"], "source": r.get("source", "") or "农信网"} for r in items],
        })
    except Exception as e:
        return json_resp({"error": str(e), "items": []}, 200)




async def handle_market_categories(request):
    """返回农产品分类树"""
    return json_resp({"categories": [{"name":k, "items":v} for k,v in COMMODITY_CATEGORIES.items()]})


async def handle_market_prices(request):
    """查询具体农产品价格、趋势、排名"""
    commodity = request.query.get("commodity", "稻谷")
    try:
        moa_data = _fetch_moa_api(commodity)
        if moa_data and (moa_data.get("method1") or moa_data.get("method2") or moa_data.get("method3")):
            return json_resp(_build_response(moa_data, commodity))
    except Exception as e:
        logger.warning(f"[MOA PRICE] {commodity}: {e}")
    return json_resp(_gen_fallback_data(commodity))


# 农产品分类数据
COMMODITY_CATEGORIES = {
    "粮食": ["稻谷", "小麦", "玉米", "大豆", "马铃薯"],
    "油料": ["花生", "油菜籽"],
    "棉花": ["棉花"],
    "食糖": ["甘蔗"],
    "蔬菜": ["大白菜", "黄瓜", "大蒜"],
    "水果": ["梨", "香蕉", "柑桔", "葡萄"],
    "畜禽": ["猪", "牛", "绵羊", "鸡", "蛋", "牛奶"]
}

COMMODITY_CODES = {
    "稻谷":"AA01006", "小麦":"AA01002", "玉米":"AA01009", "大豆":"AA02001", "马铃薯":"AE02003",
    "花生":"AB01001", "油菜籽":"AB01002",
    "棉花":"AC010010008",
    "甘蔗":"AD01001",
    "大白菜":"AE01001", "黄瓜":"AE04005", "大蒜":"AE02009",
    "梨":"AF01002", "香蕉":"AF06001", "柑桔":"AF05001", "葡萄":"AF02001",
    "猪":"AL01002001", "牛":"AL01006", "绵羊":"AL01010", "鸡":"AL02001016", "蛋":"AL05001", "牛奶":"12052314117"
}

TREND_CODES = {
    "稻谷":"AA01006", "小麦":"A,AJ,AA,AA01", "玉米":"AA01009,AE99999001", "大豆":"AA02001", "马铃薯":"AE02003",
    "花生":"AB01001", "油菜籽":"AB01002",
    "棉花":"AC010010010,AC010010009,AC010010011,AC010010012,AC010010013",
    "甘蔗":"AD01001",
    "大白菜":"AE01001", "黄瓜":"AE04005,AE04005001", "大蒜":"AE02009",
    "梨":"AF01002,AF01002001,AF01002007,AF01002009", "香蕉":"AF06001", "柑桔":"AF05001", "葡萄":"AF02001",
    "猪":"13191716390,18149414250", "牛":"AL01005008,AL01005009,AL01005007",
    "绵羊":"AL01009005", "鸡":"AL02001005,AL02005005,AL02009002", "蛋":"AL05002,AL05001", "牛奶":""
}

COTTON_SUB_NAMES = {
    "AC010010010": "棉短绒", "AC010010009": "棉纱",
    "AC010010011": "棉粕", "AC010010012": "棉籽", "AC010010013": "棉壳",
}

WHOLESALE_CODES = {
    "稻谷":"AA01006", "小麦":"AA01002", "玉米":"AA01009", "大豆":"AA02001", "马铃薯":"AE02003",
    "花生":"AB01001", "油菜籽":"AB01002", "棉花":"AC010010008",
    "甘蔗":"AD01001",
    "大白菜":"AE01001", "黄瓜":"AE04005", "大蒜":"AE02009",
    "梨":"AF01002", "香蕉":"AF06001", "柑桔":"AF05001", "葡萄":"AF02001",
    "猪":"AL01002001", "牛":"AL01006", "绵羊":"AL01010", "鸡":"AL02001016", "蛋":"AL05001", "牛奶":"12052314117"
}
PRICE_CODES = WHOLESALE_CODES


def _fetch_moa_api(commodity):
    """从 ncpscxx.moa.gov.cn 获取真实价格数据"""
    code = COMMODITY_CODES.get(commodity, "")
    price_code = PRICE_CODES.get(commodity, code)
    trend_code = TREND_CODES.get(commodity, "")
    logger.info(f"[MOA] 查询品种: {commodity}, code={code}")
    if not code:
        logger.warning(f"[MOA] 品种 {commodity} 无对应API编码")
        return None
    from datetime import date as dt_date
    today = dt_date.today()
    week_num = today.isocalendar()[1]
    two_years_ago = (today.replace(year=today.year - 2)).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")
    result = {"method1": None, "method2": None, "method3": None}
    # 方法1: 涨跌排行
    wk_url = f"/product/common-price-info/quote/change/rank/count?varietyCode={price_code}&date={today.year}-{week_num}"
    try:
        wk_req = urllib.request.Request("https://ncpscxx.moa.gov.cn" + wk_url,
            headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
        with urllib.request.urlopen(wk_req, timeout=10) as wk_resp:
            result["method1"] = json.loads(wk_resp.read())
    except Exception as e1:
        logger.warning(f"[MOA] 方法1 失败: {e1}")
    # 方法2: 批发市场价格（日期回退）
    for days_back in range(1, 8):
        try_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        post_url = f"/product/common-price-info/wholesale/price/count?varietyCode={price_code}&date={try_date}"
        try:
            get_req = urllib.request.Request("https://ncpscxx.moa.gov.cn" + post_url,
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json",
                         "Origin":"https://ncpscxx.moa.gov.cn","Referer":"https://ncpscxx.moa.gov.cn/"})
            with urllib.request.urlopen(get_req, timeout=15) as resp2:
                raw = json.loads(resp2.read())
                data_count = len(raw.get("data", [])) if isinstance(raw.get("data"), list) else 0
                if data_count > 0:
                    result["method2"] = raw
                    result["method2_date"] = try_date
                    break
        except Exception as e2:
            pass
    # 方法3: 全国价格走势
    if trend_code:
        trend_url = f"/product/common-price-avg/meat/price/compared/count?dataSource=1&varietyCode={trend_code}&queryStartTime={two_years_ago}&queryEndTime={today_str}"
        try:
            trend_req = urllib.request.Request("https://ncpscxx.moa.gov.cn" + trend_url,
                headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            with urllib.request.urlopen(trend_req, timeout=15) as trend_resp:
                result["method3"] = json.loads(trend_resp.read())
        except Exception as e3:
            logger.warning(f"[MOA] 方法3 失败: {e3}")
    if result["method1"] or result["method2"] or result["method3"]:
        return result
    return None


def _build_response(moa_data, commodity):
    """将MOA API响应数据组装为前端需要的格式"""
    now = datetime.now()
    method1 = moa_data.get("method1", {}) or {}
    method2 = moa_data.get("method2", {}) or {}
    method3 = moa_data.get("method3", {}) or {}
    m2_list = method2.get("data", []) if isinstance(method2.get("data"), list) else []
    m1_data = method1.get("data", {}) if isinstance(method1.get("data"), dict) else {}
    m3_list = method3.get("data", []) if isinstance(method3.get("data"), list) else []
    wholesale, province_map = [], {}
    for item in m2_list:
        if not isinstance(item, dict): continue
        market_name = item.get("MARKET_NAME", "") or item.get("market", "")
        province_name = item.get("PROVINCE_NAME", "") or item.get("province", "")
        price = float(item.get("PRICE_MARKET", 0) or item.get("price", 0))
        prev_price = float(item.get("NEXT_PRICE_MARKET", 0) or item.get("prev", 0) or 0)
        report_time = item.get("REPORT_TIME", "") or item.get("date", "")
        if not market_name and province_name: market_name = province_name
        if market_name and price > 0:
            wholesale.append({"market": market_name, "price": round(price, 2),
                "prev": round(prev_price, 2) if prev_price else price,
                "province": province_name, "date": report_time})
        if province_name and price > 0:
            province_map.setdefault(province_name, []).append(price)
    provinces = []
    for prov, prices in province_map.items():
        provinces.append({"province": prov, "price": round(sum(prices) / len(prices), 2), "market_count": len(prices)})
    provinces.sort(key=lambda x: x["price"], reverse=True)
    wholesale.sort(key=lambda x: x["price"], reverse=True)
    trend, trend_series = [], {}
    trend_code = TREND_CODES.get(commodity, "")
    is_multi_code = "," in trend_code if trend_code else False
    if m3_list:
        if is_multi_code:
            sub_codes = [c.strip() for c in trend_code.split(",") if c.strip()]
            for item in m3_list:
                if isinstance(item, dict):
                    d = item.get("REPORT_TIME", "") or item.get("date", "") or ""
                    date_str = str(d).replace("年","-").replace("月","-").replace("日","")
                    if not date_str: continue
                    for sc in sub_codes:
                        p = float(item.get(f"C_{sc}", 0) or 0)
                        if p > 0:
                            unit_p = p / 1000 if p > 100 else p
                            name = COTTON_SUB_NAMES.get(sc, sc)
                            trend_series.setdefault(name, []).append({"date": date_str, "price": round(unit_p, 2)})
            date_map = {}
            for name, pts in trend_series.items():
                for pt in pts: date_map.setdefault(pt["date"], []).append(pt["price"])
            for d in sorted(date_map.keys()):
                trend.append({"date": d, "price": round(sum(date_map[d]) / len(date_map[d]), 2)})
            if len(trend) > 30: trend = trend[-30:]
        else:
            first_code = trend_code.split(",")[0] if trend_code else ""
            price_key = f"C_{first_code}" if first_code else ""
            for item in m3_list:
                if isinstance(item, dict):
                    d = item.get("REPORT_TIME", "") or item.get("date", "") or ""
                    p = float(item.get(price_key, 0) or 0)
                    if d and p > 0:
                        date_str = str(d).replace("年","-").replace("月","-").replace("日","")
                        trend.append({"date": date_str, "price": round(p / 1000 if p > 100 else p, 2)})
            if len(trend) > 30: trend = trend[-30:]
    # 兜底趋势
    if not trend:
        for src in [m1_data.get("rise", []), m1_data.get("fall", [])]:
            for item in (src if isinstance(src, list) else []):
                if isinstance(item, dict):
                    d = item.get("REPORT_TIME") or item.get("date") or ""
                    p = float(item.get("PRICE_MARKET", 0) or item.get("price", 0))
                    if d and p > 0: trend.append({"date": str(d), "price": round(p, 2)})
    if not trend and wholesale:
        date_map = {}
        for w in wholesale:
            if w.get("date"): date_map.setdefault(w["date"], []).append(w["price"])
        for d in sorted(date_map.keys())[-7:]:
            trend.append({"date": d, "price": round(sum(date_map[d]) / len(date_map[d]), 2)})
    if (not wholesale) and trend_series:
        for name, pts in trend_series.items():
            if pts: wholesale.append({"market": name, "price": pts[-1]["price"], "prev": pts[-1]["price"], "province": "", "date": pts[-1]["date"]})
        wholesale.sort(key=lambda x: x["price"], reverse=True)
    if (not provinces) and trend_series:
        for name, pts in trend_series.items():
            if pts: provinces.append({"province": name, "price": pts[-1]["price"], "market_count": 1})
        provinces.sort(key=lambda x: x["price"], reverse=True)
    all_prices = [p["price"] for p in provinces] if provinces else [w["price"] for w in wholesale]
    current_price = round(sum(all_prices) / len(all_prices), 2) if all_prices else 0
    change, change_pct = 0, 0
    if wholesale:
        prevs = [w["prev"] for w in wholesale if w.get("prev", 0) > 0 and w["prev"] != w["price"]]
        if prevs:
            prev_avg = round(sum(prevs) / len(prevs), 2)
            change = round(current_price - prev_avg, 2)
            change_pct = round(change / prev_avg * 100, 2) if prev_avg else 0
    return {"commodity": commodity, "trend": trend, "trend_series": trend_series if trend_series else None,
        "provinces": provinces, "wholesale": wholesale, "market_rank": wholesale,
        "current_price": current_price, "national_avg": current_price,
        "change": change, "change_pct": change_pct,
        "unit": "元/公斤", "source": "农业农村部批发市场信息系统",
        "updated_at": now.strftime("%Y-%m-%d %H:%M")}


def _gen_fallback_data(commodity):
    """完全模拟数据兜底"""
    bp = {"稻谷":2.78,"小麦":3.10,"玉米":2.72,"大豆":5.45,"马铃薯":2.80,
        "花生":8.60,"油菜籽":5.80,"棉花":16.50,"甘蔗":3.20,
        "大白菜":1.65,"黄瓜":4.50,"大蒜":12.80,"梨":4.80,"香蕉":5.50,
        "柑橘":6.50,"葡萄":9.50,"猪":24.80,"牛":71.50,"绵羊":67.00,"鸡":16.50,"蛋":9.80,"牛奶":12.50}
    base = bp.get(commodity, 5.00)
    now = datetime.now()
    cur = round(base * (0.97 + random.random()*0.06), 2)
    prev = round(base * (0.97 + random.random()*0.06), 2)
    chg = round(cur - prev, 2)
    cpct = round(chg/prev*100, 2) if prev else 0
    trend = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        p = round(base * (1 + math.sin(i*0.3)*0.03 + (random.random()-0.5)*0.02), 2)
        trend.append({"date": d.strftime("%m-%d"), "price": p})
    pv = ["北京","上海","广州","深圳","成都","重庆","武汉","郑州"]
    random.shuffle(pv)
    provinces = [{"province": p, "price": round(base*(0.85+random.random()*0.3),2)} for p in pv[:6]]
    mn = ["北京新发地","上海江桥","广州江南","深圳海吉星","成都驯马桥","武汉四季美","郑州万邦","西安新桥"]
    wholesale = [{"market": m, "price": round(base*(0.9+random.random()*0.2),2)} for m in mn]
    return {"commodity": commodity, "trend": trend, "provinces": provinces, "wholesale": wholesale,
        "current_price": cur, "change": chg, "change_pct": cpct,
        "source": "模拟参考数据（API未响应）", "updated_at": now.strftime("%Y-%m-%d %H:%M")}


async def handle_health(request):
    return json_resp({"status": "healthy", "timestamp": datetime.now().isoformat()})


async def handle_dashboard(request):
    tp = config.BASE_DIR / "frontend" / "templates" / "dashboard.html"
    try:
        return web.Response(text=tp.read_text(encoding="utf-8"), content_type="text/html")
    except:
        return web.Response(text="Template not found", status=404)


# ---------------------------------------------------------------------------
# 城市经纬度数据库（覆盖全国主要城市，供天气查询和 chatbot 共用）
# ---------------------------------------------------------------------------
CITY_COORDS = {
    # 直辖市
    "北京市": {"lat": 39.90, "lon": 116.40},
    "天津市": {"lat": 39.09, "lon": 117.20},
    "上海市": {"lat": 31.23, "lon": 121.47},
    "重庆市": {"lat": 29.56, "lon": 106.55},
    # 河北省
    "石家庄市": {"lat": 38.04, "lon": 114.50},
    "唐山市": {"lat": 39.63, "lon": 118.18},
    "秦皇岛市": {"lat": 39.93, "lon": 119.60},
    "邯郸市": {"lat": 36.62, "lon": 114.49},
    "邢台市": {"lat": 37.07, "lon": 114.50},
    "保定市": {"lat": 38.87, "lon": 115.48},
    "张家口市": {"lat": 40.81, "lon": 114.88},
    "承德市": {"lat": 40.97, "lon": 117.94},
    "沧州市": {"lat": 38.30, "lon": 116.84},
    "廊坊市": {"lat": 39.52, "lon": 116.70},
    "衡水市": {"lat": 37.74, "lon": 115.69},
    # 山西省
    "太原市": {"lat": 37.87, "lon": 112.55},
    "大同市": {"lat": 40.08, "lon": 113.30},
    "阳泉市": {"lat": 37.86, "lon": 113.58},
    "长治市": {"lat": 36.20, "lon": 113.11},
    "晋城市": {"lat": 35.49, "lon": 112.85},
    "朔州市": {"lat": 39.33, "lon": 112.43},
    "晋中市": {"lat": 37.69, "lon": 112.73},
    "运城市": {"lat": 35.03, "lon": 111.01},
    "忻州市": {"lat": 38.42, "lon": 112.73},
    "临汾市": {"lat": 36.08, "lon": 111.52},
    "吕梁市": {"lat": 37.52, "lon": 111.14},
    # 辽宁省
    "沈阳市": {"lat": 41.80, "lon": 123.43},
    "大连市": {"lat": 38.91, "lon": 121.61},
    "鞍山市": {"lat": 41.11, "lon": 122.99},
    "抚顺市": {"lat": 41.88, "lon": 123.96},
    "本溪市": {"lat": 41.33, "lon": 123.77},
    "丹东市": {"lat": 40.12, "lon": 124.39},
    "锦州市": {"lat": 41.10, "lon": 121.13},
    "营口市": {"lat": 40.67, "lon": 122.23},
    "阜新市": {"lat": 42.02, "lon": 121.67},
    "辽阳市": {"lat": 41.27, "lon": 123.17},
    "盘锦市": {"lat": 41.12, "lon": 122.07},
    "铁岭市": {"lat": 42.29, "lon": 123.72},
    "朝阳市": {"lat": 41.57, "lon": 120.45},
    "葫芦岛市": {"lat": 40.71, "lon": 120.84},
    # 吉林省
    "长春市": {"lat": 43.82, "lon": 125.32},
    "吉林市": {"lat": 43.84, "lon": 126.55},
    "四平市": {"lat": 43.17, "lon": 124.35},
    "辽源市": {"lat": 42.89, "lon": 125.14},
    "通化市": {"lat": 41.72, "lon": 125.94},
    "白山市": {"lat": 41.94, "lon": 126.42},
    "松原市": {"lat": 45.14, "lon": 124.82},
    "白城市": {"lat": 45.62, "lon": 122.84},
    "延边朝鲜族自治州": {"lat": 42.89, "lon": 129.51},
    # 黑龙江省
    "哈尔滨市": {"lat": 45.80, "lon": 126.53},
    "齐齐哈尔市": {"lat": 47.35, "lon": 123.92},
    "鸡西市": {"lat": 45.30, "lon": 130.97},
    "鹤岗市": {"lat": 47.35, "lon": 130.30},
    "双鸭山市": {"lat": 46.64, "lon": 131.16},
    "大庆市": {"lat": 46.59, "lon": 125.10},
    "伊春市": {"lat": 47.73, "lon": 128.84},
    "佳木斯市": {"lat": 46.80, "lon": 130.37},
    "七台河市": {"lat": 45.77, "lon": 131.00},
    "牡丹江市": {"lat": 44.55, "lon": 129.60},
    "黑河市": {"lat": 50.25, "lon": 127.53},
    "绥化市": {"lat": 46.65, "lon": 126.99},
    # 江苏省
    "南京市": {"lat": 32.06, "lon": 118.80},
    "无锡市": {"lat": 31.49, "lon": 120.31},
    "徐州市": {"lat": 34.20, "lon": 117.18},
    "常州市": {"lat": 31.81, "lon": 119.97},
    "苏州市": {"lat": 31.30, "lon": 120.58},
    "南通市": {"lat": 31.98, "lon": 120.89},
    "连云港市": {"lat": 34.60, "lon": 119.22},
    "淮安市": {"lat": 33.61, "lon": 119.02},
    "盐城市": {"lat": 33.35, "lon": 120.16},
    "扬州市": {"lat": 32.39, "lon": 119.41},
    "镇江市": {"lat": 32.20, "lon": 119.45},
    "泰州市": {"lat": 32.46, "lon": 119.92},
    "宿迁市": {"lat": 33.96, "lon": 118.28},
    # 浙江省
    "杭州市": {"lat": 30.27, "lon": 120.15},
    "宁波市": {"lat": 29.87, "lon": 121.55},
    "温州市": {"lat": 28.00, "lon": 120.70},
    "嘉兴市": {"lat": 30.75, "lon": 120.76},
    "湖州市": {"lat": 30.87, "lon": 120.10},
    "绍兴市": {"lat": 30.03, "lon": 120.58},
    "金华市": {"lat": 29.10, "lon": 119.65},
    "衢州市": {"lat": 28.97, "lon": 118.87},
    "舟山市": {"lat": 30.02, "lon": 122.20},
    "台州市": {"lat": 28.66, "lon": 121.42},
    "丽水市": {"lat": 28.47, "lon": 119.92},
    # 安徽省
    "合肥市": {"lat": 31.82, "lon": 117.23},
    "芜湖市": {"lat": 31.35, "lon": 118.38},
    "蚌埠市": {"lat": 32.94, "lon": 117.39},
    "淮南市": {"lat": 32.63, "lon": 117.00},
    "马鞍山市": {"lat": 31.67, "lon": 118.51},
    "淮北市": {"lat": 33.97, "lon": 116.80},
    "铜陵市": {"lat": 30.95, "lon": 117.82},
    "安庆市": {"lat": 30.54, "lon": 117.05},
    "黄山市": {"lat": 29.72, "lon": 118.34},
    "滁州市": {"lat": 32.30, "lon": 118.32},
    "阜阳市": {"lat": 32.90, "lon": 115.82},
    "宿州市": {"lat": 33.63, "lon": 116.98},
    "六安市": {"lat": 31.73, "lon": 116.52},
    "亳州市": {"lat": 33.84, "lon": 115.78},
    "池州市": {"lat": 30.66, "lon": 117.49},
    "宣城市": {"lat": 30.95, "lon": 118.76},
    # 福建省
    "福州市": {"lat": 26.08, "lon": 119.30},
    "厦门市": {"lat": 24.48, "lon": 118.09},
    "莆田市": {"lat": 25.45, "lon": 119.01},
    "三明市": {"lat": 26.26, "lon": 117.64},
    "泉州市": {"lat": 24.87, "lon": 118.68},
    "漳州市": {"lat": 24.51, "lon": 117.65},
    "南平市": {"lat": 26.64, "lon": 118.18},
    "龙岩市": {"lat": 25.08, "lon": 117.02},
    "宁德市": {"lat": 26.66, "lon": 119.55},
    # 江西省
    "南昌市": {"lat": 28.68, "lon": 115.86},
    "景德镇市": {"lat": 29.27, "lon": 117.18},
    "萍乡市": {"lat": 27.62, "lon": 113.85},
    "九江市": {"lat": 29.71, "lon": 116.00},
    "新余市": {"lat": 27.81, "lon": 114.94},
    "鹰潭市": {"lat": 28.26, "lon": 117.07},
    "赣州市": {"lat": 25.83, "lon": 114.93},
    "吉安市": {"lat": 27.11, "lon": 114.99},
    "宜春市": {"lat": 27.81, "lon": 114.40},
    "抚州市": {"lat": 27.98, "lon": 116.36},
    "上饶市": {"lat": 28.45, "lon": 117.94},
    # 山东省
    "济南市": {"lat": 36.65, "lon": 117.00},
    "青岛市": {"lat": 36.07, "lon": 120.38},
    "淄博市": {"lat": 36.82, "lon": 118.05},
    "枣庄市": {"lat": 34.81, "lon": 117.32},
    "东营市": {"lat": 37.43, "lon": 118.67},
    "烟台市": {"lat": 37.54, "lon": 121.40},
    "潍坊市": {"lat": 36.71, "lon": 119.16},
    "济宁市": {"lat": 35.41, "lon": 116.59},
    "泰安市": {"lat": 36.19, "lon": 117.09},
    "威海市": {"lat": 37.51, "lon": 122.12},
    "日照市": {"lat": 35.42, "lon": 119.53},
    "临沂市": {"lat": 35.10, "lon": 118.35},
    "德州市": {"lat": 37.45, "lon": 116.36},
    "聊城市": {"lat": 36.45, "lon": 115.98},
    "滨州市": {"lat": 37.38, "lon": 117.97},
    "菏泽市": {"lat": 35.23, "lon": 115.48},
    # 河南省
    "郑州市": {"lat": 34.75, "lon": 113.65},
    "开封市": {"lat": 34.80, "lon": 114.31},
    "洛阳市": {"lat": 34.62, "lon": 112.45},
    "平顶山市": {"lat": 33.74, "lon": 113.30},
    "安阳市": {"lat": 36.10, "lon": 114.35},
    "鹤壁市": {"lat": 35.90, "lon": 114.30},
    "新乡市": {"lat": 35.30, "lon": 113.93},
    "焦作市": {"lat": 35.21, "lon": 113.25},
    "濮阳市": {"lat": 35.76, "lon": 115.03},
    "许昌市": {"lat": 34.03, "lon": 113.85},
    "漯河市": {"lat": 33.58, "lon": 114.02},
    "三门峡市": {"lat": 34.78, "lon": 111.19},
    "南阳市": {"lat": 32.99, "lon": 112.53},
    "商丘市": {"lat": 34.42, "lon": 115.66},
    "信阳市": {"lat": 32.15, "lon": 114.08},
    "周口市": {"lat": 33.63, "lon": 114.65},
    "驻马店市": {"lat": 32.98, "lon": 114.02},
    "济源市": {"lat": 35.08, "lon": 112.60},
    # 湖北省
    "武汉市": {"lat": 30.59, "lon": 114.30},
    "黄石市": {"lat": 30.22, "lon": 115.09},
    "十堰市": {"lat": 32.63, "lon": 110.79},
    "宜昌市": {"lat": 30.69, "lon": 111.29},
    "襄阳市": {"lat": 32.01, "lon": 112.12},
    "鄂州市": {"lat": 30.40, "lon": 114.89},
    "荆门市": {"lat": 31.03, "lon": 112.20},
    "孝感市": {"lat": 30.92, "lon": 113.91},
    "荆州市": {"lat": 30.33, "lon": 112.24},
    "黄冈市": {"lat": 30.45, "lon": 114.88},
    "咸宁市": {"lat": 29.83, "lon": 114.33},
    "随州市": {"lat": 31.69, "lon": 113.37},
    "恩施土家族苗族自治州": {"lat": 30.29, "lon": 109.49},
    # 湖南省
    "长沙市": {"lat": 28.23, "lon": 112.97},
    "株洲市": {"lat": 27.83, "lon": 113.13},
    "湘潭市": {"lat": 27.83, "lon": 112.92},
    "衡阳市": {"lat": 26.89, "lon": 112.60},
    "邵阳市": {"lat": 27.24, "lon": 111.47},
    "岳阳市": {"lat": 29.37, "lon": 113.13},
    "常德市": {"lat": 29.03, "lon": 111.70},
    "张家界市": {"lat": 29.13, "lon": 110.48},
    "益阳市": {"lat": 28.56, "lon": 112.34},
    "郴州市": {"lat": 25.80, "lon": 113.03},
    "永州市": {"lat": 26.42, "lon": 111.62},
    "怀化市": {"lat": 27.55, "lon": 110.00},
    "娄底市": {"lat": 27.70, "lon": 111.99},
    "湘西土家族苗族自治州": {"lat": 28.31, "lon": 109.74},
    # 广东省
    "广州市": {"lat": 23.13, "lon": 113.26},
    "韶关市": {"lat": 24.80, "lon": 113.60},
    "深圳市": {"lat": 22.54, "lon": 114.06},
    "珠海市": {"lat": 22.27, "lon": 113.58},
    "汕头市": {"lat": 23.37, "lon": 116.71},
    "佛山市": {"lat": 23.03, "lon": 113.12},
    "江门市": {"lat": 22.58, "lon": 113.08},
    "湛江市": {"lat": 21.27, "lon": 110.36},
    "茂名市": {"lat": 21.67, "lon": 110.93},
    "肇庆市": {"lat": 23.05, "lon": 112.47},
    "惠州市": {"lat": 23.11, "lon": 114.42},
    "梅州市": {"lat": 24.30, "lon": 116.12},
    "汕尾市": {"lat": 22.79, "lon": 115.38},
    "河源市": {"lat": 23.74, "lon": 114.70},
    "阳江市": {"lat": 21.86, "lon": 111.98},
    "清远市": {"lat": 23.70, "lon": 113.03},
    "东莞市": {"lat": 23.04, "lon": 113.75},
    "中山市": {"lat": 22.52, "lon": 113.39},
    "潮州市": {"lat": 23.66, "lon": 116.63},
    "揭阳市": {"lat": 23.55, "lon": 116.37},
    "云浮市": {"lat": 22.92, "lon": 112.04},
    # 海南省
    "海口市": {"lat": 20.04, "lon": 110.34},
    "三亚市": {"lat": 18.25, "lon": 109.51},
    "三沙市": {"lat": 16.83, "lon": 112.34},
    "儋州市": {"lat": 19.52, "lon": 109.58},
    # 四川省
    "成都市": {"lat": 30.57, "lon": 104.07},
    "自贡市": {"lat": 29.34, "lon": 104.77},
    "攀枝花市": {"lat": 26.58, "lon": 101.72},
    "泸州市": {"lat": 28.87, "lon": 105.44},
    "德阳市": {"lat": 31.13, "lon": 104.40},
    "绵阳市": {"lat": 31.47, "lon": 104.68},
    "广元市": {"lat": 32.43, "lon": 105.82},
    "遂宁市": {"lat": 30.53, "lon": 105.59},
    "内江市": {"lat": 29.59, "lon": 105.06},
    "乐山市": {"lat": 29.55, "lon": 103.76},
    "南充市": {"lat": 30.80, "lon": 106.11},
    "眉山市": {"lat": 30.08, "lon": 103.83},
    "宜宾市": {"lat": 28.75, "lon": 104.64},
    "广安市": {"lat": 30.46, "lon": 106.63},
    "达州市": {"lat": 31.21, "lon": 107.50},
    "雅安市": {"lat": 29.98, "lon": 103.00},
    "巴中市": {"lat": 31.87, "lon": 106.77},
    "资阳市": {"lat": 30.13, "lon": 104.63},
    "阿坝藏族羌族自治州": {"lat": 31.90, "lon": 102.22},
    "甘孜藏族自治州": {"lat": 30.05, "lon": 101.96},
    "凉山彝族自治州": {"lat": 27.88, "lon": 102.27},
    # 贵州省
    "贵阳市": {"lat": 26.65, "lon": 106.63},
    "六盘水市": {"lat": 26.59, "lon": 104.83},
    "遵义市": {"lat": 27.72, "lon": 106.94},
    "安顺市": {"lat": 26.26, "lon": 105.95},
    "毕节市": {"lat": 27.29, "lon": 105.28},
    "铜仁市": {"lat": 27.73, "lon": 109.19},
    "黔西南布依族苗族自治州": {"lat": 25.09, "lon": 104.90},
    "黔东南苗族侗族自治州": {"lat": 26.58, "lon": 107.98},
    "黔南布依族苗族自治州": {"lat": 26.25, "lon": 107.52},
    # 云南省
    "昆明市": {"lat": 25.04, "lon": 102.71},
    "曲靖市": {"lat": 25.49, "lon": 103.80},
    "玉溪市": {"lat": 24.35, "lon": 102.52},
    "保山市": {"lat": 25.11, "lon": 99.16},
    "昭通市": {"lat": 27.33, "lon": 103.72},
    "丽江市": {"lat": 26.86, "lon": 100.23},
    "普洱市": {"lat": 22.83, "lon": 101.00},
    "临沧市": {"lat": 23.88, "lon": 100.09},
    "楚雄彝族自治州": {"lat": 25.04, "lon": 101.55},
    "红河哈尼族彝族自治州": {"lat": 23.37, "lon": 103.38},
    "文山壮族苗族自治州": {"lat": 23.37, "lon": 104.25},
    "西双版纳傣族自治州": {"lat": 22.01, "lon": 100.80},
    "大理白族自治州": {"lat": 25.61, "lon": 100.27},
    "德宏傣族景颇族自治州": {"lat": 24.43, "lon": 98.59},
    "怒江傈僳族自治州": {"lat": 25.85, "lon": 98.86},
    "迪庆藏族自治州": {"lat": 27.83, "lon": 99.70},
    # 陕西省
    "西安市": {"lat": 34.26, "lon": 108.94},
    "铜川市": {"lat": 34.90, "lon": 108.98},
    "宝鸡市": {"lat": 34.36, "lon": 107.24},
    "咸阳市": {"lat": 34.35, "lon": 108.70},
    "渭南市": {"lat": 34.50, "lon": 109.50},
    "延安市": {"lat": 36.60, "lon": 109.49},
    "汉中市": {"lat": 33.07, "lon": 107.02},
    "榆林市": {"lat": 38.29, "lon": 109.74},
    "安康市": {"lat": 32.69, "lon": 109.03},
    "商洛市": {"lat": 33.87, "lon": 109.94},
    # 甘肃省
    "兰州市": {"lat": 36.06, "lon": 103.83},
    "嘉峪关市": {"lat": 39.77, "lon": 98.29},
    "金昌市": {"lat": 38.52, "lon": 102.19},
    "白银市": {"lat": 36.54, "lon": 104.13},
    "天水市": {"lat": 34.58, "lon": 105.72},
    "武威市": {"lat": 37.93, "lon": 102.64},
    "张掖市": {"lat": 38.93, "lon": 100.45},
    "平凉市": {"lat": 35.54, "lon": 106.67},
    "酒泉市": {"lat": 39.74, "lon": 98.50},
    "庆阳市": {"lat": 35.71, "lon": 107.64},
    "定西市": {"lat": 35.58, "lon": 104.62},
    "陇南市": {"lat": 33.39, "lon": 104.92},
    "临夏回族自治州": {"lat": 35.60, "lon": 103.21},
    "甘南藏族自治州": {"lat": 34.98, "lon": 102.91},
    # 青海省
    "西宁市": {"lat": 36.62, "lon": 101.78},
    "海东市": {"lat": 36.50, "lon": 102.12},
    "海北藏族自治州": {"lat": 36.96, "lon": 100.90},
    "黄南藏族自治州": {"lat": 35.52, "lon": 102.03},
    "海南藏族自治州": {"lat": 36.29, "lon": 100.62},
    "果洛藏族自治州": {"lat": 34.47, "lon": 100.25},
    "玉树藏族自治州": {"lat": 33.01, "lon": 97.01},
    "海西蒙古族藏族自治州": {"lat": 37.38, "lon": 97.37},
    # 台湾省
    "台北市": {"lat": 25.03, "lon": 121.56},
    "高雄市": {"lat": 22.63, "lon": 120.31},
    "台中市": {"lat": 24.15, "lon": 120.67},
    "台南市": {"lat": 22.99, "lon": 120.18},
    "基隆市": {"lat": 25.13, "lon": 121.74},
    "新竹市": {"lat": 24.81, "lon": 120.97},
    "嘉义市": {"lat": 23.47, "lon": 120.45},
    # 内蒙古自治区
    "呼和浩特市": {"lat": 40.82, "lon": 111.75},
    "包头市": {"lat": 40.65, "lon": 109.84},
    "乌海市": {"lat": 39.65, "lon": 106.80},
    "赤峰市": {"lat": 42.26, "lon": 118.89},
    "通辽市": {"lat": 43.65, "lon": 122.26},
    "鄂尔多斯市": {"lat": 39.61, "lon": 109.78},
    "呼伦贝尔市": {"lat": 49.21, "lon": 119.75},
    "巴彦淖尔市": {"lat": 40.74, "lon": 107.39},
    "乌兰察布市": {"lat": 40.93, "lon": 113.12},
    "兴安盟": {"lat": 46.08, "lon": 122.07},
    "锡林郭勒盟": {"lat": 43.94, "lon": 116.09},
    "阿拉善盟": {"lat": 38.84, "lon": 105.72},
    # 广西壮族自治区
    "南宁市": {"lat": 22.82, "lon": 108.37},
    "柳州市": {"lat": 24.32, "lon": 109.41},
    "桂林市": {"lat": 25.27, "lon": 110.29},
    "梧州市": {"lat": 23.48, "lon": 111.30},
    "北海市": {"lat": 21.48, "lon": 109.12},
    "防城港市": {"lat": 21.69, "lon": 108.35},
    "钦州市": {"lat": 21.97, "lon": 108.62},
    "贵港市": {"lat": 23.11, "lon": 109.60},
    "玉林市": {"lat": 22.63, "lon": 110.16},
    "百色市": {"lat": 23.90, "lon": 106.62},
    "贺州市": {"lat": 24.41, "lon": 111.55},
    "河池市": {"lat": 24.69, "lon": 108.08},
    "来宾市": {"lat": 23.74, "lon": 109.23},
    "崇左市": {"lat": 22.41, "lon": 107.37},
    # 西藏自治区
    "拉萨市": {"lat": 29.65, "lon": 91.13},
    "日喀则市": {"lat": 29.27, "lon": 88.88},
    "昌都市": {"lat": 31.14, "lon": 97.17},
    "林芝市": {"lat": 29.65, "lon": 94.36},
    "山南市": {"lat": 29.24, "lon": 91.77},
    "那曲市": {"lat": 31.48, "lon": 92.06},
    "阿里地区": {"lat": 30.40, "lon": 81.15},
    # 宁夏回族自治区
    "银川市": {"lat": 38.47, "lon": 106.27},
    "石嘴山市": {"lat": 39.02, "lon": 106.37},
    "吴忠市": {"lat": 37.99, "lon": 106.19},
    "固原市": {"lat": 36.00, "lon": 106.28},
    "中卫市": {"lat": 37.50, "lon": 105.19},
    # 新疆维吾尔自治区
    "乌鲁木齐市": {"lat": 43.82, "lon": 87.61},
    "克拉玛依市": {"lat": 45.58, "lon": 84.86},
    "吐鲁番市": {"lat": 42.95, "lon": 89.18},
    "哈密市": {"lat": 42.83, "lon": 93.51},
    "昌吉回族自治州": {"lat": 44.02, "lon": 87.32},
    "博尔塔拉蒙古自治州": {"lat": 44.91, "lon": 82.06},
    "巴音郭楞蒙古自治州": {"lat": 41.73, "lon": 86.14},
    "阿克苏地区": {"lat": 41.17, "lon": 80.26},
    "克孜勒苏柯尔克孜自治州": {"lat": 39.72, "lon": 76.13},
    "喀什地区": {"lat": 39.47, "lon": 75.99},
    "和田地区": {"lat": 37.11, "lon": 79.93},
    "伊犁哈萨克自治州": {"lat": 43.91, "lon": 81.32},
    "塔城地区": {"lat": 46.76, "lon": 83.00},
    "阿勒泰地区": {"lat": 47.83, "lon": 88.13},
    # 香港特别行政区
    "香港": {"lat": 22.32, "lon": 114.17},
    # 澳门特别行政区
    "澳门": {"lat": 22.20, "lon": 113.54},
}


async def handle_weather(request):
    """Weather API using Open-Meteo"""
    city = request.query.get("city", "")
    coords = CITY_COORDS.get(city)
    if not coords:
        return json_resp({"error": f"暂不支持城市: {city}", "city": city}, 200)
    coords_str = "&".join([f"latitude={coords['lat']}", f"longitude={coords['lon']}"])
    api_url = "https://api.open-meteo.com/v1/forecast?" + coords_str + "&daily=temperature_2m_max,temperature_2m_min,weathercode,precipitation_sum&current_weather=true&timezone=Asia/Shanghai"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result = {"city": city, "current": data.get("current_weather", {}), "daily": data.get("daily", {})}
        return json_resp(result)
    except Exception as e:
        return json_resp({"error": str(e), "city": city}, 200)


def _get_nlp_modules():
    """根据 config.MODEL_MODE 返回 (classifier, sentiment, hot_topic) 实例。

    "mock"  → 规则引擎（NewsClassifier + SentimentAnalyzer）
    "local" → GPU 深度学习模型（ModelNewsClassifier + ModelSentimentAnalyzer）
    """
    from nlp import NewsClassifier, SentimentAnalyzer, HotTopicAnalyzer

    if config.MODEL_MODE == "local":
        try:
            from nlp import ModelNewsClassifier, ModelSentimentAnalyzer
            logger.info("[NLP] 使用 GPU 深度学习模型")
            return ModelNewsClassifier(), ModelSentimentAnalyzer(), HotTopicAnalyzer()
        except Exception as e:
            logger.warning(f"[NLP] 模型加载失败，回退规则引擎: {e}")

    logger.info("[NLP] 使用规则引擎")
    return NewsClassifier(), SentimentAnalyzer(), HotTopicAnalyzer()


def _classify_and_sentiment_batch(articles, classifier, sentiment):
    """对一批文章运行分类和情感分析（原地修改），并收集模型结果。

    分类：逐条处理（零样本 pipeline 不支持批量）
    情感：优先使用 batch 推理（GPU 满载利用）

    每篇文章写入字段：
        category, classifier_scores, sentiment, sentiment_score,
        sentiment_scores, risk_score, sentiment_name, classifier_name
    """
    if not articles:
        return

    import torch
    n = len(articles)
    logger.info(f"[NLP] 对 {n} 条新闻运行分类+情感分析...")

    # 判断分类器/情感分析器类型
    clf_name = type(classifier).__name__
    sent_name = type(sentiment).__name__

    # 分类 — 逐条，保存全部分数
    for i, a in enumerate(articles):
        result = classifier.classify(a.get("title", ""), a.get("content", ""))
        a["category"] = result["category"]
        a["classifier_scores"] = result.get("scores", {})
        a["classifier_name"] = clf_name
        if (i + 1) % max(1, n // 5) == 0:
            logger.info(f"[NLP] 分类进度: {i + 1}/{n}")

    # 情感 — 优先 GPU 批量
    if hasattr(sentiment, "analyze_batch"):
        sentiment.analyze_batch(articles)
    else:
        for a in articles:
            r = sentiment.analyze(a.get("title", ""))
            a["sentiment"] = r["label"]
            a["sentiment_score"] = r["score"]
            a["sentiment_scores"] = r.get("scores", {})
            a["risk_score"] = r.get("risk_score", 0.0)

    # 补充 sentiment_name
    for a in articles:
        a["sentiment_name"] = sent_name
        if "sentiment_scores" not in a:
            a["sentiment_scores"] = {}

    logger.info(f"[NLP] 分类+情感分析完成: {n} 条")


def _save_model_results_batch(db, articles):
    """将分析结果批量写入 article_model_results 表"""
    if not articles:
        return
    rows = []
    ts = datetime.now().isoformat()
    for a in articles:
        rows.append({
            "article_id": a["id"],
            "model_mode": config.MODEL_MODE,
            "classifier_name": a.get("classifier_name", ""),
            "classifier_scores": a.get("classifier_scores", {}),
            "classifier_category": a.get("category", ""),
            "sentiment_name": a.get("sentiment_name", ""),
            "sentiment_scores": a.get("sentiment_scores", {}),
            "sentiment_label": a.get("sentiment", ""),
            "sentiment_score": a.get("sentiment_score", 0.0),
            "risk_score": a.get("risk_score", 0.0),
            "model_params": {
                "model_mode": config.MODEL_MODE,
                "max_length": config.MAX_INPUT_LENGTH,
                "categories": config.CATEGORY_LABELS,
            },
            "analyzed_at": ts,
        })
    db.save_article_model_results_batch(rows)


def run_analysis_on_existing(db):
    """仅对未分析的文章执行 NLP 分析，不生成聚合分析"""
    from nlp import HotTopicAnalyzer

    unanalyzed_ids = db.get_unanalyzed_article_ids(limit=5000)
    if not unanalyzed_ids:
        logger.info("[ANALYSIS] 所有新闻均已分析，跳过")
        return

    placeholders = ",".join("?" for _ in unanalyzed_ids)
    c = db.conn.cursor()
    c.execute(
        f"SELECT * FROM news_articles WHERE id IN ({placeholders})",
        unanalyzed_ids,
    )
    arts = [dict(r) for r in c.fetchall()]
    if not arts:
        logger.info("[ANALYSIS] 未找到需要分析的文章")
        return

    logger.info(f"[ANALYSIS] 待分析旧文章: {len(arts)} 条")
    clf, sa, _ = _get_nlp_modules()
    _classify_and_sentiment_batch(arts, clf, sa)
    _save_model_results_batch(db, arts)

    # 更新 news_articles 表中的分类/情感字段
    for a in arts:
        db.conn.execute(
            "UPDATE news_articles SET category=?, sentiment=?, sentiment_score=?, risk_score=? WHERE id=?",
            (a["category"], a["sentiment"], a["sentiment_score"], a["risk_score"], a["id"]),
        )
    db.conn.commit()
    logger.info(f"[ANALYSIS] 已分析 {len(arts)} 条旧文章")


def refresh_aggregate_analysis(db):
    """基于所有文章重新生成聚合分析（趋势、热词、全量分析）"""
    from nlp import HotTopicAnalyzer
    all_arts = db.get_all_news()  # 获取全部文章
    if not all_arts:
        logger.info("[ANALYSIS] 无文章，跳过聚合分析生成")
        return
    ha = HotTopicAnalyzer()
    trend_data = ha.trend_over_time(all_arts)
    db.save_analysis("full_analysis", ha.full_analysis(all_arts))
    db.save_analysis("hot_keywords", {"keywords": ha.extract_keywords(
        [a.get("title", "") for a in all_arts if a.get("title")], 30)})
    db.save_analysis("trend", {"trend": trend_data})
    logger.info("[ANALYSIS] 聚合分析已更新")


def run_crawl_pipeline(db, start_date=None, end_date=None):
    """执行爬取+分析新文章，支持按日期过滤"""
    from crawler.news_crawler import AgriculturalNewsCrawler

    existing = db.conn.execute("SELECT id FROM news_articles").fetchall()
    known_ids = set(r[0] for r in existing) if existing else set()
    logger.info(f"[CRAWL] 已知 {len(known_ids)} 篇文章，增量模式跳过重复")

    crawler = AgriculturalNewsCrawler(known_ids=known_ids)
    all_a = crawler.crawl_all()

    if not all_a:
        logger.info("[CRAWL] 未爬取到新文章")
        return 0

    # ----- 日期过滤 -----
    if start_date and end_date:
        # 日期格式统一为 YYYY-MM-DD，确保比较准确
        filtered = []
        for a in all_a:
            date_str = a.get("date", "")
            if date_str and len(date_str) >= 10:
                date_str = date_str[:10]  # 只取日期部分
                if start_date <= date_str <= end_date:
                    filtered.append(a)
        all_a = filtered
        logger.info(f"[CRAWL] 日期过滤后保留 {len(all_a)} 条 ({start_date} ~ {end_date})")
        if not all_a:
            logger.info("[CRAWL] 过滤后无新文章")
            return 0

    # ----- 后续分析、保存 -----
    clf, sa, _ = _get_nlp_modules()
    _classify_and_sentiment_batch(all_a, clf, sa)

    saved = db.save_news(all_a)
    # 仅对新保存的文章存储模型结果
    saved_ids = {a["id"] for a in all_a}
    new_articles = [a for a in all_a if a["id"] in saved_ids] if saved != len(all_a) else all_a
    if new_articles:
        _save_model_results_batch(db, new_articles)

    logger.info(f"[CRAWL] 爬取 {len(all_a)} 条, 新增保存 {saved} 条")
    return len(all_a)


async def handle_crawl(request):
    """手动爬取触发器 - 支持日期范围过滤"""
    db = get_db()
    start_date = request.query.get("start_date")
    end_date = request.query.get("end_date")

    # 1. 爬取新文章并分析（按日期过滤）
    new_count = run_crawl_pipeline(db, start_date=start_date, end_date=end_date)

    # 2. 补分析所有未分析的旧文章（不限日期）
    run_analysis_on_existing(db)

    # 3. 重新生成聚合分析（基于全部文章）
    refresh_aggregate_analysis(db)

    sync_disaster_and_market_from_news(db)

    # 5. AI 灾害信息提取（从新闻文本中提取结构化灾害信息）
    if config.DISASTER_EXTRACTION_ENABLED:
        try:
            from backend.disaster_extraction import extract_disaster_info_from_ai
            extract_result = extract_disaster_info_from_ai(db)
            logger.info(f"[CRAWL] AI 灾害提取完成: {extract_result}")
        except Exception as e:
            logger.error(f"[CRAWL] AI 灾害提取失败 (非致命): {e}")

    stats = db.get_statistics()
    return json_resp({
        "crawled": new_count,
        "total": stats["total_news"],
        "analyzed": stats.get("analyzed_articles", 0),
    })


async def handle_disaster_extraction(request):
    """手动触发 AI 灾害信息提取。支持 ?force=1 强制更新所有记录。"""
    if not config.DISASTER_EXTRACTION_ENABLED:
        return json_resp({"error": "灾害提取功能未启用，请在 config.py 中设置 DISASTER_EXTRACTION_ENABLED = True"}, 400)
    try:
        from backend.disaster_extraction import extract_disaster_info_from_ai
        force = request.query.get("force", "0") == "1"
        result = extract_disaster_info_from_ai(get_db(), force=force)
        return json_resp(result)
    except Exception as e:
        logger.error(f"[API] 灾害提取失败: {e}")
        return json_resp({"error": str(e)}, 500)


async def handle_model_results(request):
    """获取模型推理结果详情。
    支持 ?article_id=xxx 查询单条，否则返回汇总列表。
    """
    try:
        article_id = request.query.get("article_id", None)

        if article_id:
            r = get_db().get_article_model_result(article_id)
            if r:
                return json_resp(r)
            return json_resp({"error": "未找到该文章的分析结果"}, 404)

        # 汇总列表
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        articles = get_db().get_articles_with_model_results(limit, offset)
        return json_resp({
            "total": len(articles),
            "limit": limit,
            "offset": offset,
            "articles": articles,
        })
    except Exception as e:
        return json_resp({"error": str(e)}, 500)


async def handle_chat_proxy(request):
    """Reverse-proxy requests to Gradio on localhost:7860 (WebSocket-capable)."""
    gradio_port = config.GRADIO_PORT if hasattr(config, "GRADIO_PORT") else 7860
    path = request.match_info.get("path", "")
    target_url = f"http://localhost:{gradio_port}/{path}"
    if request.query_string:
        target_url += "?" + request.query_string

    # Forward headers (exclude hop-by-hop)
    forward_headers = {}
    for k, v in request.headers.items():
        kl = k.lower()
        if kl in ("host", "content-length", "transfer-encoding", "connection", "upgrade"):
            continue
        forward_headers[k] = v

    try:
        # Handle WebSocket upgrade
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await _proxy_websocket(request, target_url)

        # Regular HTTP proxy
        async with aiohttp.ClientSession() as session:
            async with session.request(
                    method=request.method,
                    url=target_url,
                    headers=forward_headers,
                    data=await request.read(),
                    timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                response = web.StreamResponse(
                    status=resp.status,
                    headers={
                        k: v for k, v in resp.headers.items()
                        if k.lower() not in ("x-frame-options", "content-security-policy")
                    },
                )
                await response.prepare(request)
                async for chunk in resp.content.iter_any():
                    await response.write(chunk)
                await response.write_eof()
                return response
    except aiohttp.ClientError as e:
        logger.warning(f"[Proxy] Gradio 连接失败: {e}")
        return json_resp({"error": "AI 助手服务未启动，请稍后重试"}, 503)


async def _proxy_websocket(request, target_url):
    """Proxy WebSocket connection to Gradio."""
    try:
        async with aiohttp.ClientSession() as ws_client:
            # Connect to Gradio WebSocket
            target_ws = await ws_client.ws_connect(
                target_url.replace("http://", "ws://").replace("https://", "wss://"),
                headers={
                    k: v for k, v in request.headers.items()
                    if k.lower() not in ("host", "content-length", "connection", "upgrade",
                                         "sec-websocket-key", "sec-websocket-version", "sec-websocket-extensions")
                },
                timeout=30,
            )

            # Create WebSocket response to client
            ws_server = web.WebSocketResponse()
            await ws_server.prepare(request)

            async def forward_client_to_target():
                """Forward messages from browser → Gradio."""
                async for msg in ws_server:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await target_ws.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await target_ws.send_bytes(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        break

            async def forward_target_to_client():
                """Forward messages from Gradio → browser."""
                async for msg in target_ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await ws_server.send_str(msg.data)
                    elif msg.type == aiohttp.WSMsgType.BINARY:
                        await ws_server.send_bytes(msg.data)
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        break

            # Run both directions concurrently
            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(forward_client_to_target()),
                    asyncio.ensure_future(forward_target_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

            return ws_server
    except Exception as e:
        logger.warning(f"[Proxy] WebSocket 代理失败: {e}")
        return json_resp({"error": "WebSocket 连接失败"}, 502)


# ==================== 在 api.py 中添加以下函数 ====================

def sync_disaster_and_market_from_news(db):
    """
    从 news_articles 中提取灾害预警和市场行情，同步到专用表。

    灾害预警：增量 upsert，已存在的记录保留 AI 提取字段（region/alert_level/
    severity/disaster_type/description），仅更新基础字段。新记录插入时 AI 字段留空，
    由 extract_disaster_info_from_ai 后续填充。

    市场行情：清空重建（无 AI 提取字段需要保留）。
    """
    logger.info("[SYNC] 开始同步灾害预警和市场数据...")

    # ============================================================
    # 1. 灾害预警 — 增量 upsert
    # ============================================================
    disasters = db.get_all_news(category="灾害预警")
    disaster_ids = {d["id"] for d in disasters}

    # 1a. 读取已存在记录中的 AI 字段，用于后续保留
    existing_ai = {}
    c = db.conn.cursor()
    c.execute("SELECT id, region, alert_level, severity, disaster_type, description FROM disaster_warnings")
    for row in c.fetchall():
        existing_ai[row[0]] = {
            "region": row[1] or "",
            "alert_level": row[2] or "",
            "severity": row[3] if row[3] is not None else 99,
            "disaster_type": row[4] or "",
            "description": row[5] or "",
        }

    # 1b. 删除孤儿记录：id 不再属于灾害预警分类的文章
    if disaster_ids:
        placeholders = ",".join("?" for _ in disaster_ids)
        db.conn.execute(
            f"DELETE FROM disaster_warnings WHERE id NOT IN ({placeholders})",
            list(disaster_ids),
        )
    else:
        db.conn.execute("DELETE FROM disaster_warnings")

    # 1c. Upsert 每条灾害新闻
    inserted_disasters = 0
    updated_disasters = 0
    for news in disasters:
        aid = news["id"]
        if aid in existing_ai:
            # 已存在：保留 AI 字段，更新基础字段
            db.conn.execute(
                """UPDATE disaster_warnings
                   SET source=?, title=?, url=?, date=?, risk_score=?, crawled_at=?
                   WHERE id=?""",
                (
                    news.get("source", ""),
                    news.get("title", ""),
                    news.get("url", ""),
                    news.get("date", ""),
                    news.get("risk_score", 0.0),
                    news.get("crawled_at", ""),
                    aid,
                ),
            )
            updated_disasters += 1
        else:
            # 新记录：AI 字段留空，后续由 extract_disaster_info_from_ai 填充
            db.conn.execute(
                """INSERT INTO disaster_warnings (
                    id, source, region, title, url, date,
                    alert_level, severity, disaster_type, risk_score, description, crawled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    aid,
                    news.get("source", ""),
                    "",  # region — 待 AI 提取
                    news.get("title", ""),
                    news.get("url", ""),
                    news.get("date", ""),
                    "",  # alert_level — 待 AI 提取
                    99,  # severity — 待 AI 提取
                    "",  # disaster_type — 待 AI 提取
                    news.get("risk_score", 0.0),
                    news.get("content", "")[:500],  # description — 后续由 AI 建议覆盖
                    news.get("crawled_at", ""),
                ),
            )
            inserted_disasters += 1

    # ============================================================
    # 2. 市场行情 — 清空重建（无 AI 提取字段需要保留）
    # ============================================================
    db.conn.execute("DELETE FROM market_data")

    markets = db.get_all_news(category="市场行情")
    inserted_markets = 0
    for news in markets:
        try:
            db.conn.execute(
                """INSERT INTO market_data (
                    title, url, source, category, date, content, crawled_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    news.get("title", ""),
                    news.get("url", ""),
                    news.get("source", ""),
                    news.get("category", ""),
                    news.get("date", ""),
                    news.get("content", ""),
                    news.get("crawled_at", ""),
                ),
            )
            inserted_markets += 1
        except Exception as e:
            logger.error(f"插入市场数据失败 ({news.get('id')}): {e}")

    db.conn.commit()
    logger.info(
        f"[SYNC] 同步完成：灾害预警 新增 {inserted_disasters} / 保留 {updated_disasters}，"
        f"市场数据 {inserted_markets} 条"
    )


def create_app():
    app = web.Application()
    app.router.add_get("/", handle_dashboard)
    app.router.add_get("/api/statistics", handle_statistics)
    app.router.add_get("/api/news", handle_news)
    app.router.add_get("/api/news/categories", handle_categories)
    app.router.add_get("/api/disasters", handle_disasters)
    app.router.add_get("/api/analysis", handle_analysis)
    app.router.add_get("/api/analysis/hot-keywords", handle_keywords)
    app.router.add_get("/api/analysis/trend", handle_trend)
    app.router.add_get("/api/analysis/sentiment-summary", handle_sentiment_summary)
    app.router.add_get("/api/market", handle_market)
    app.router.add_get("/api/market/categories", handle_market_categories)
    app.router.add_get("/api/market/prices", handle_market_prices)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/weather", handle_weather)
    app.router.add_get("/api/crawl", handle_crawl)
    app.router.add_get("/api/model-results", handle_model_results)
    app.router.add_get("/api/disasters/extract", handle_disaster_extraction)
    app.router.add_get("/dashboard", handle_dashboard)
    sd = str(config.BASE_DIR / "frontend" / "static")
    app.router.add_static("/static/", sd)

    # Chatbot proxy to Gradio (WebSocket-capable)
    app.router.add_route("*", "/chat_app", handle_chat_proxy)
    app.router.add_route("*", "/chat_app/{path:.*}", handle_chat_proxy)

    return app
