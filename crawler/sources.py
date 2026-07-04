from dataclasses import dataclass

@dataclass
class NewsSource:
    name: str
    url: str
    encoding: str = "utf-8"
    article_selector: str = ""
    title_selector: str = "a"
    date_selector: str = ""
    page_start: int = 1
    page_url_template: str = ""  # 分页模板，如 "https://www.agri.cn/zx/nyyw/index_{page}.htm"

@dataclass  
class DisasterSource:
    name: str
    url: str
    encoding: str = "utf-8"
    region: str = ""
    selector: str = ""

# === 农业新闻源（实测可用）===
# 使用更通用的选择器，匹配多种常见的列表页HTML结构
NEWS_SOURCES = [
    # ===== 农信网首页精选（各栏目最新文章） =====
    NewsSource(name="农信网-要闻", url="https://www.agri.cn/",
               article_selector="div.news_content a[href*=nyyw]",
               title_selector="",
               date_selector="span.time"),
    NewsSource(name="农信网-生产", url="https://www.agri.cn/",
               article_selector="div.sc_box_list a[href*=scdt]",
               title_selector="",
               date_selector="span.time"),
    NewsSource(name="农信网-气象", url="https://www.agri.cn/",
               article_selector="div.sc_box_list a[href*=nyqx]",
               title_selector="",
               date_selector="span.time"),

    # ===== 农信网栏目列表页（带分页，获取大量历史文章） =====
    # 使用通用选择器 ul li 匹配列表结构
    NewsSource(name="农信网-要闻列表", url="https://www.agri.cn/zx/nyyw/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.agri.cn/zx/nyyw/index_{page}.htm"),
    NewsSource(name="农信网-生产列表", url="https://www.agri.cn/sc/scdt/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.agri.cn/sc/scdt/index_{page}.htm"),
    NewsSource(name="农信网-气象列表", url="https://www.agri.cn/sc/nyqx/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.agri.cn/sc/nyqx/index_{page}.htm"),
    NewsSource(name="农信网-通知公告", url="https://www.agri.cn/zx/hxgg/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.agri.cn/zx/hxgg/index_{page}.htm"),
    NewsSource(name="农信网-全国联播", url="https://www.agri.cn/zx/xxlb/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.agri.cn/zx/xxlb/index_{page}.htm"),

    # ===== 农业农村部 =====
    NewsSource(name="农业农村部", url="https://www.moa.gov.cn/xw/zwdt/",
               article_selector="li.ztlb",
               title_selector="a",
               date_selector="span"),

    # ===== 新增数据源：中国农业信息网 =====
    NewsSource(name="中国农业信息网", url="http://www.agri.cn/",
               article_selector="a[href*=nyyw], a[href*=scdt], a[href*=nyqx]",
               title_selector="",
               date_selector="span.time"),

    # ===== 中国气象网 - 农业气象专栏 =====
    # 每日发布农业专项预警、农田渍涝、春播冻害、秋收连阴雨风险等
    NewsSource(name="中国气象网-农业气象", url="https://www.cma.gov.cn/2011xwzx/2011xqxxw/2011xqxyw/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.cma.gov.cn/2011xwzx/2011xqxxw/2011xqxyw/index_{page}.htm"),
    NewsSource(name="中国气象网-气象要闻", url="https://www.cma.gov.cn/2011xwzx/2011xqxxw/2011xqxyw/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="https://www.cma.gov.cn/2011xwzx/2011xqxxw/2011xqxyw/index_{page}.htm"),

    # ===== 中国水利部 - 防汛抗旱/水旱灾害 =====
    # 江河洪水、涝灾、农田积水灾情通报、防汛抗旱预警
    NewsSource(name="水利部-防汛抗旱", url="http://www.mwr.gov.cn/xw/slyw/",
               article_selector="ul li",
               title_selector="a",
               date_selector="span",
               page_url_template="http://www.mwr.gov.cn/xw/slyw/index_{page}.htm"),
    

    
]

DISASTER_SOURCES = [
    DisasterSource(name="中国天气网灾害预警", url="http://www.weather.com.cn/alarm/",
                   region="全国", selector="ul.alarm-list li"),
    # 中国气象网 - 气象灾害预警
    DisasterSource(name="中国气象网-灾害预警", url="https://www.cma.gov.cn/2011xwzx/2011xqxxw/2011xyj/",
                   region="全国", selector="ul li"),
    # 水利部 -  flood warnings
    DisasterSource(name="水利部-水旱灾害防御", url="http://www.mwr.gov.cn/xw/slyw/",
                   region="全国", selector="ul li"),
    # 自然资源部 - 地质灾害预警
    DisasterSource(name="自然资源部-地质灾害", url="http://www.mnr.gov.cn/dt/zhfp/",
                   region="全国", selector="ul li"),
]
