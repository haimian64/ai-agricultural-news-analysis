"""爬虫模块测试"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.sources import NEWS_SOURCES


def test_news_sources_configured():
    """测试新闻源配置完整性"""
    assert len(NEWS_SOURCES) > 0, "至少需要一个新闻源"
    for source in NEWS_SOURCES:
        assert source.name, "新闻源必须有名称"
        assert source.url.startswith("http"), f"无效的URL: {source.url}"


def test_crawler_mock_data():
    """测试爬虫在离线模式下的回退行为"""
    from crawler.news_crawler import AgriculturalNewsCrawler
    crawler = AgriculturalNewsCrawler(sources=[])
    articles = crawler.crawl_all()
    assert isinstance(articles, list)


if __name__ == "__main__":
    test_news_sources_configured()
    test_crawler_mock_data()
    print("所有爬虫测试通过!")
