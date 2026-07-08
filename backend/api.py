"""API路由 - 添加搜索/日期筛选/情感摘要/市场数据端点"""
import asyncio, json, logging, re
from datetime import datetime
import aiohttp
from aiohttp import web
from config import config

logger = logging.getLogger(__name__)
_db_manager = None

def set_db_manager(db):
    global _db_manager; _db_manager = db

def get_db():
    global _db_manager
    if _db_manager is None:
        from backend.database import DatabaseManager
        _db_manager = DatabaseManager(); _db_manager.conn
    return _db_manager

def json_resp(data, status=200):
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, ensure_ascii=False, default=str))

async def handle_index(request): return json_resp({"name":"农业新闻分析与预警系统","version":"1.0.0","status":"running"})
async def handle_statistics(request):
    try: return json_resp(get_db().get_statistics())
    except Exception as e: return json_resp({"error":str(e)},500)
async def handle_news(request):
    limit = int(request.query.get("limit","50"))
    offset = int(request.query.get("offset","0"))
    cat = request.query.get("category",None)
    start = request.query.get("start_date",None)
    end = request.query.get("end_date",None)
    kw = request.query.get("keyword",None)
    try:
        if kw:
            if start and end:
                return json_resp(get_db().get_news_by_keyword_and_date(kw, start, end, limit))
            return json_resp(get_db().search_news(kw, limit))
        if start and end: return json_resp(get_db().get_news_by_date_range(start, end, limit))
        return json_resp(get_db().get_all_news(limit, offset, cat))
    except Exception as e: return json_resp({"error":str(e)},500)
async def handle_categories(request):
    return json_resp({"categories":config.CATEGORY_LABELS})
async def handle_disasters(request):
    limit = int(request.query.get("limit","50"))
    try:
        result = get_db().get_active_disasters(limit)
        if not result:
            # 回退到新闻表中分类为"灾害预警"的文章
            result = get_db().get_all_news(limit, 0, "灾害预警")
        return json_resp(result)
    except Exception as e:
        return json_resp({"error":str(e)},500)
async def handle_analysis(request):
    try:
        results = get_db().get_recent_analysis("full_analysis")
        return json_resp(results[0] if results else {"message":"暂无分析结果"})
    except: return json_resp({"error":"分析失败"},500)
async def handle_keywords(request):
    try:
        results = get_db().get_recent_analysis("hot_keywords")
        data = results[0] if results else {"keywords":[]}
        logger.info(f"[DEBUG] handle_keywords 返回: {{'keywords_count': {len(data.get('keywords',[]))}}}")
        return json_resp(data)
    except Exception as e: return json_resp({"error":str(e)},500)
async def handle_trend(request):
    try:
        results = get_db().get_recent_analysis("trend")
        data = results[0] if results else {"trend":{}}
        trend_keys = list(data.get("trend",{}).keys()) if data.get("trend") else []
        logger.info(f"[DEBUG] handle_trend 返回: {{'trend_dates': {trend_keys}}}")
        return json_resp(data)
    except Exception as e: return json_resp({"error":str(e)},500)
async def handle_sentiment_summary(request):
    """情感摘要 + 综合得分"""
    start = request.query.get("start_date",None)
    end = request.query.get("end_date",None)
    try:
        summary = get_db().get_sentiment_summary(start, end)
        # Add comparison
        summary["analysis"] = f"今日农业舆情综合得分 {summary['score_10']} 分，整体偏向{summary['label']}"
        return json_resp(summary)
    except Exception as e: return json_resp({"error":str(e)},500)
async def handle_market(request):
    """市场数据"""
    try:
        from urllib.parse import urljoin
        from lxml import html as lxml_html
        import urllib.request
        base_url = "https://www.agri.cn/sj/"
        items = []
        with urllib.request.urlopen(urllib.request.Request(base_url, headers={"User-Agent":"Mozilla/5.0"}), timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        doc = lxml_html.fromstring(html)
        for sel in [".trends_list li", ".sj_news_list li", ".dynamic_content_list li"]:
            for item in doc.cssselect(sel):
                a = item.cssselect("a")
                if not a: continue
                title = a[0].text_content().strip()
                href = a[0].get("href","")
                if len(title) > 5:
                    # 用 urljoin 正确解析相对路径
                    items.append({"title":title, "url":urljoin(base_url, href), "source":"农信网-数据"})
        return json_resp({"total":len(items), "items":items[:30]})
    except Exception as e: return json_resp({"error":str(e), "items":[]},200)
async def handle_health(request):
    return json_resp({"status":"healthy","timestamp":datetime.now().isoformat()})
async def handle_dashboard(request):
    tp = config.BASE_DIR / "frontend" / "templates" / "dashboard.html"
    try: return web.Response(text=tp.read_text(encoding="utf-8"), content_type="text/html")
    except: return web.Response(text="Template not found", status=404)


async def handle_weather(request):
    """Weather API using Open-Meteo"""
    import urllib.request, json
    city = request.query.get("city", "")
    # 扩展城市经纬度数据库（覆盖全国主要城市）
    cities = {
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
    coords = cities.get(city)
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
    json_path = db.export_model_results_json()
    logger.info(f"[ANALYSIS] 聚合分析已更新，JSON → {json_path}")

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

    stats = db.get_statistics()
    return json_resp({
        "crawled": new_count,
        "total": stats["total_news"],
        "analyzed": stats.get("analyzed_articles", 0),
    })


async def handle_model_results(request):
    """获取模型推理结果详情。
    支持 ?article_id=xxx 查询单条，否则返回汇总列表。
    支持 ?export=1 触发 JSON 导出。
    """
    try:
        article_id = request.query.get("article_id", None)
        do_export = request.query.get("export", None)

        if do_export:
            path = get_db().export_model_results_json()
            return json_resp({"exported": True, "path": path})

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
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/weather", handle_weather)
    app.router.add_get("/api/crawl", handle_crawl)
    app.router.add_get("/api/model-results", handle_model_results)
    app.router.add_get("/dashboard", handle_dashboard)
    sd = str(config.BASE_DIR / "frontend" / "static")
    app.router.add_static("/static/", sd)

    # Chatbot proxy to Gradio (WebSocket-capable)
    app.router.add_route("*", "/chat_app", handle_chat_proxy)
    app.router.add_route("*", "/chat_app/{path:.*}", handle_chat_proxy)

    return app