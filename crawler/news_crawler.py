"""
农业新闻爬虫 - 使用 urllib + lxml
"""
import hashlib, json, random, re, time, logging, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, quote, urlparse

from lxml import html as lxml_html

from config import config
from .sources import NewsSource, NEWS_SOURCES

logger = logging.getLogger(__name__)


def safe_url(url):
    """对URL中的中文进行百分号编码"""
    return quote(url, safe=":/?#[]@!$&'()*+,;=-_.~%")


class AgriculturalNewsCrawler:
    def __init__(self, sources=None, known_ids=None):
        self.sources = sources or NEWS_SOURCES
        self.known_ids = known_ids or set()  # 已知文章ID集合，用于增量爬取跳过
        self.raw_dir = config.RAW_DIR / "news"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _request(self, url, retry_on_404=False):
        for attempt in range(config.MAX_RETRIES):
            try:
                req = urllib.request.Request(
                    safe_url(url),
                    headers={"User-Agent": config.USER_AGENT,
                             "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
                )
                with urllib.request.urlopen(req, timeout=config.REQUEST_TIMEOUT) as resp:
                    html_bytes = resp.read()
                    ct = resp.headers.get("Content-Type", "")
                    enc = "utf-8"
                    if "charset=" in ct:
                        enc = ct.split("charset=")[-1].split(";")[0].strip()
                    return html_bytes.decode(enc, errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 404 and not retry_on_404:
                    # 404直接返回，不重试（404不会变成200）
                    logger.warning(f"请求失败 (404): {url}")
                    return None  # None 表示"页面不存在"
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.REQUEST_DELAY * (attempt + 1))
                    continue
                logger.warning(f"请求失败: {url} - {e}")
                return None
            except Exception as e:
                if attempt < config.MAX_RETRIES - 1:
                    time.sleep(config.REQUEST_DELAY * (attempt + 1))
                    continue
                logger.warning(f"请求失败: {url} - {e}")
                return None

    def _extract_content(self, url):
        html = self._request(url)
        if not html:
            return ""
        try:
            doc = lxml_html.fromstring(html)
        except Exception:
            return ""
        for tag in doc.xpath("//script|//style|//nav|//footer"):
            if tag.getparent() is not None:
                tag.getparent().remove(tag)
        for xp in ["//div[contains(@class,'article-content')]",
                    "//div[contains(@class,'content')]",
                    "//div[contains(@class,'text')]",
                    "//article", "//div[@id='content']"]:
            els = doc.xpath(xp)
            if els:
                return "\n".join(els[0].text_content().split())
        ps = doc.xpath("//p")
        texts = [p.text_content().strip() for p in ps if len(p.text_content().strip()) > 20]
        return "\n".join(texts[:20]) if texts else ""

    @staticmethod
    def _parse_date_from_url(url):
        """从URL路径中提取日期，支持多种格式"""
        if not url:
            return None
        # tYYYYMMDD pattern (e.g., t20260702_xxx) — agri.cn 常用格式
        m = re.search(r't(\d{4})(\d{2})(\d{2})', url)
        if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # /YYYYMMDD pattern (e.g., /20260702/xxx)
        m = re.search(r'/(\d{4})(\d{2})(\d{2})(?=[/_\\.-])', url)
        if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # /YYYY/MMDD/ pattern (e.g., /2026/0702/xxx)
        m = re.search(r'/(\d{4})/(\d{2})(\d{2})/', url)
        if m: return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None

    def _parse_date(self, s, url=None):
        now = datetime.now()
        # 优先从URL提取日期（agri.cn的URL中tYYYYMMDD是可靠的发布日期）
        if url:
            url_date = self._parse_date_from_url(url)
            if url_date:
                return url_date
        # 没有URL或URL无日期时，回退到文本解析
        if not s:
            return now.strftime("%Y-%m-%d")
        s = s.strip()
        pats = [
            # "2026-07-01" or "2026年07月01日"
            (r"(\d{4})-(\d{1,2})-(\d{1,2})", r"\1-\2-\3"),
            (r"(\d{4})年(\d{1,2})月(\d{1,2})日?", r"\1-\2-\3"),
            # "07-02" (short date), "07月02日"
            (r"(\d{1,2})-(\d{1,2})", lambda m: f"{now.year}-{m.group(1)}-{m.group(2)}"),
            (r"(\d{1,2})月(\d{1,2})日?", lambda m: f"{now.year}-{m.group(1)}-{m.group(2)}"),
            # "今天", "昨天"
            ("今天", lambda _: now.strftime("%Y-%m-%d")),
            ("昨天", lambda _: (now.replace(day=now.day-1)).strftime("%Y-%m-%d")),
        ]
        for pat, rep in pats:
            if re.search(pat, s):
                try:
                    return re.sub(pat, rep, s, count=1)
                except Exception:
                    continue
        return now.strftime("%Y-%m-%d")

    def _gen_id(self, url, title):
        return hashlib.md5(f"{url}_{title}".encode("utf-8", errors="replace")).hexdigest()

    def crawl_source(self, source):
        articles = []
        # 构建分页URL列表
        urls = [source.url]
        if source.page_url_template:
            for page in range(1, 31):  # 最多爬取30个分页
                urls.append(source.page_url_template.replace("{page}", str(page)))
        # 智能停止：连续失败/空页码计数
        consecutive_empty = 0
        max_consecutive_empty = 3  # 连续3次无结果则停止该来源
        for page_url in urls:
            if len(articles) >= config.MAX_NEWS_PER_SOURCE:
                break
            if consecutive_empty >= max_consecutive_empty:
                logger.info(f"  {source.name}: 连续{consecutive_empty}页无结果，提前停止分页")
                break
            html = self._request(page_url)
            if html is None:
                # None = 404（页面不存在），加速停止
                consecutive_empty += 1
                continue
            try:
                doc = lxml_html.fromstring(html)
            except Exception as e:
                logger.warning(f"HTML parse error: {e}")
                continue
            items = doc.cssselect(source.article_selector) if source.article_selector else doc.xpath("//li")
            if not items:
                # 没有匹配的文章
                consecutive_empty += 1
                logger.debug(f"  无匹配文章 (selector={source.article_selector}): {page_url}")
                continue
            # 成功获取到文章，重置计数器
            page_has_new = False  # 当前页是否发现新文章
            for item in items:
                if len(articles) >= config.MAX_NEWS_PER_SOURCE:
                    break
                try:
                    el = None
                    if source.title_selector:
                        found = item.cssselect(source.title_selector)
                        if found: el = found[0]
                    elif item.tag == "a":
                        el = item
                    elif item.xpath(".//a"):
                        el = item.xpath(".//a")[0]
                    if el is None:
                        continue
                    title = el.text_content().strip()
                    link = el.get("href", "")
                    # 跳过非文章链接（短文本、导航关键词、无效链接）
                    skip_keywords = ["农业要闻","中心动态","全国信息联播","通知公告","更多","首页",
                                     "机构","资讯","数据","生产","信息化","专题","视频","设为首页",
                                     "加入收藏","联系我们","网站地图","登录","注册","搜索","返回"]
                    if not title or len(title) < 5 or title.strip() in skip_keywords:
                        continue
                    # 跳过没有有效链接的项
                    if not link or link.startswith("#") or link.startswith("javascript"):
                        continue
                    # 跳过非新闻链接（如图片、附件下载等）
                    if link.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".png")):
                        continue
                    if link and not link.startswith("http"):
                        link = urljoin(source.url, link)
                    # Fix CMA double-path: links are root-relative, strip source dir prefix
                    import urllib.parse
                    _parsed = urllib.parse.urlparse(link)
                    _src_path = urllib.parse.urlparse(source.url).path.rstrip("/")
                    if _parsed.path.startswith(_src_path + "/2011"):
                        link = "https://www.cma.gov.cn/" + _parsed.path[len(_src_path)+1:].lstrip("/")
                    if not self._is_valid_news_item(source, title, link):
                        continue
                    # 增量模式：跳过已知文章
                    article_id = self._gen_id(link, title)
                    if article_id in self.known_ids:
                        continue
                    page_has_new = True
                    self.known_ids.add(article_id)
                    ds = ""
                    if source.date_selector:
                        de = item.cssselect(source.date_selector)
                        if de:
                            ds = de[0].text_content().strip()
                    articles.append({
                        "id": article_id,
                        "title": title, "url": link,
                        "source": source.name,
                        "date": self._parse_date(ds, link),  # 传入link以便从URL提取日期
                        "content": "", "summary": "",
                        "category": "", "sentiment": "",
                        "sentiment_score": 0.5, "risk_score": 0.0,
                        "crawled_at": datetime.now().isoformat(),
                    })
                except Exception:
                    continue
            # 整页都是已知文章 → 视为空页，触发提前终止分页
            if not page_has_new:
                consecutive_empty += 1
                logger.debug(f"  第{urls.index(page_url)}页全部为已知文章 ({len(items)}条)")
            else:
                consecutive_empty = 0
            # 分页之间延迟
            if source.page_url_template and urls.index(page_url) < len(urls) - 1:
                time.sleep(config.REQUEST_DELAY)
        for a in articles:
            # Use title as summary (skip content fetching for speed)
            a["content"] = a["title"]
            a["summary"] = a["title"]
        logger.info(f"{source.name}: {len(articles)} articles")
        return articles

    def crawl_all(self):
        all_articles = []
        for src in self.sources:
            all_articles.extend(self.crawl_source(src))
            time.sleep(config.REQUEST_DELAY)
        seen = set()
        uniq = []
        for a in all_articles:
            if a["id"] not in seen:
                seen.add(a["id"])
                uniq.append(a)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        p = self.raw_dir / f"news_{ts}.json"
        with open(p, "w", encoding="utf-8") as f:
            json.dump(uniq, f, ensure_ascii=False, indent=2)
        logger.info(f"Crawl done: {len(uniq)} articles")
        return uniq
    def _is_valid_news_item(self, source, title, link):
        """严格校验爬取到的条目是否为真实新闻文章"""
        title = title.strip()
        link = link.strip()
        if not title or not link:
            return False
        if len(title) < 5:
            return False
        skip_full_titles = [
            "关于水利部", "水利部领导", "新闻发布会", "政府信息公开",
            "水利部公报", "重大会议信息", "行政审批事项", "审批服务大厅",
            "查询码查询", "水利易sou", "访问量统计", "中共中央国务院文件",
            "行政法规和法规性文件", "规范性文件",
            "第一次全国水利普查公报", "水利发展统计公报", "水资源公报",
            "中国水文年报", "中国河流泥沙公报", "中国水旱灾害防御公报",
            "中国水土保持公报", "三峡工程公报", "地下水动态月报",
            "乡村振兴水利保障工作简报", "水旱灾害防御",
            "古代著名水利工程", "著名防洪工程", "水情教育基地", "水利风景区",
            "省（区、市）气象局",
            "国新办举行新闻发布会",
        ]
        for sk in skip_full_titles:
            if sk in title:
                return False
        if link.startswith("#") or link.startswith("javascript"):
            return False
        try:
            parsed = urlparse(link)
        except Exception:
            return False
        if parsed.path in ("", "/", "//"):
            return False
        # Skip CMA special topic pages (/ztbd/ URLs)
        if "/ztbd/" in parsed.path:
            return False
        path_parts = [p for p in parsed.path.split("/") if p]
        if len(path_parts) <= 1:
            return False
        if len(path_parts) <= 2 and not parsed.path.endswith((".htm", ".html", ".shtml")):
            return False
        try:
            src_domain = urlparse(source.url).netloc
            link_domain = parsed.netloc
            if src_domain and link_domain and link_domain != src_domain:
                known_domains = ["agri.cn", "moa.gov.cn", "cma.gov.cn",
                    "mwr.gov.cn", "mnr.gov.cn", "xinhuanet.com",
                    "weather.com.cn", "gov.cn"]
                src_is_known = any(d in src_domain for d in known_domains)
                if src_is_known:
                    is_subdomain = link_domain.endswith("." + src_domain)
                    if not is_subdomain and link_domain != src_domain:
                        return False
        except Exception:
            pass
        has_date = bool(re.search(r'/\d{4}/\d{2}\d{2}/', parsed.path) or
                        re.search(r'/[tT]\d{8}', parsed.path) or
                        re.search(r'/\d{8}', parsed.path))
        if has_date:
            return True
        if parsed.path.endswith((".htm", ".html", ".shtml")):
            return True
        if len(path_parts) >= 4:
            return True
        return False
