"""API路由 - 添加搜索/日期筛选/情感摘要/市场数据端点"""
import json, logging, re
from datetime import datetime
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

def run_analysis_on_existing(db):
    """对 DB 中已有新闻运行 NLP 分析（不爬取新数据）。
    当 analysis_results 为空但 news_articles 有数据时使用。
    """
    from nlp import NewsClassifier, SentimentAnalyzer, HotTopicAnalyzer

    arts = db.get_all_news(2000)
    if not arts:
        logger.info("[ANALYSIS] 数据库中没有新闻，跳过分析")
        return

    clf = NewsClassifier()
    sa = SentimentAnalyzer()
    ha = HotTopicAnalyzer()

    # 对尚未有分类的打上分类标签
    for a in arts:
        if not a.get("category") or a.get("category") == "综合资讯":
            a["category"] = clf.classify(a.get("title", ""))["category"]
        if not a.get("sentiment_score") or a.get("sentiment_score") == 0.5:
            r = sa.analyze(a.get("title", ""))
            a["sentiment"] = r["label"]
            a["sentiment_score"] = r["score"]
            a["risk_score"] = r.get("risk_score", 0.0)

    # 趋势 + 热词 + 全量分析
    trend_data = ha.trend_over_time(arts)
    db.save_analysis("full_analysis", ha.full_analysis(arts))
    db.save_analysis("hot_keywords", {"keywords": ha.extract_keywords(
        [a.get("title", "") for a in arts if a.get("title")], 30)})
    db.save_analysis("trend", {"trend": trend_data})
    logger.info(f"[ANALYSIS] 已完成 {len(arts)} 条新闻的分析")


def run_crawl_pipeline(db):
    """执行完整的爬取+NLP+分析流水线（增量追加，不清除旧数据）。
    返回本次爬取到的文章数量。
    """
    from nlp import NewsClassifier, SentimentAnalyzer, HotTopicAnalyzer
    from crawler.news_crawler import AgriculturalNewsCrawler

    # 查询已有文章ID，传给爬虫实现增量跳过
    existing = db.conn.execute("SELECT id FROM news_articles").fetchall()
    known_ids = set(r[0] for r in existing) if existing else set()
    logger.info(f"[CRAWL] 已知 {len(known_ids)} 篇文章，增量模式跳过重复")

    crawler = AgriculturalNewsCrawler(known_ids=known_ids)
    all_a = crawler.crawl_all()

    if not all_a:
        logger.info("[CRAWL] 未爬取到新文章")
        return 0

    clf2 = NewsClassifier()
    sa2 = SentimentAnalyzer()
    ha2 = HotTopicAnalyzer()

    for a in all_a:
        a["category"] = clf2.classify(a.get("title", ""))["category"]
        r2 = sa2.analyze(a.get("title", ""))
        a["sentiment"] = r2["label"]
        a["sentiment_score"] = r2["score"]
        a["risk_score"] = r2.get("risk_score", 0.0)

    # INSERT OR IGNORE 实现增量追加，相同 ID 的文章自动跳过
    saved = db.save_news(all_a)
    arts = db.get_all_news(500)
    logger.info(f"[CRAWL] 爬取 {len(all_a)} 条, 新增保存 {saved} 条, DB中累计 {len(arts)} 条")

    # 检查日期分布
    dates_found = sorted(set(a.get("date", "")[:10] for a in arts if a.get("date", "")))
    logger.info(f"[CRAWL] 日期分布: {dates_found}")
    cats_found = {}
    for a in arts:
        c = a.get("category", "")
        cats_found[c] = cats_found.get(c, 0) + 1
    logger.info(f"[CRAWL] 类别分布: {cats_found}")

    # 对 DB 中全部文章重新做趋势分析
    trend_data = ha2.trend_over_time(arts)
    db.save_analysis("full_analysis", ha2.full_analysis(arts))
    db.save_analysis("hot_keywords", {"keywords": ha2.extract_keywords([a.get("title", "") for a in arts], 30)})
    db.save_analysis("trend", {"trend": trend_data})

    return len(all_a)


async def handle_crawl(request):
    """Manual crawl trigger - 增量追加模式，不清除已有数据"""
    count = run_crawl_pipeline(get_db())
    return json_resp({"crawled": count, "total": get_db().get_statistics()["total_news"]})
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
    app.router.add_get("/dashboard", handle_dashboard)
    sd = str(config.BASE_DIR / "frontend" / "static")
    app.router.add_static("/static/", sd)
    return app