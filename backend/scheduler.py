"""
定时任务调度器 - 基于 threading.Timer
"""
import logging
import threading
import time
from datetime import datetime

from config import config

logger = logging.getLogger(__name__)


class NewsScheduler:
    """轻量定时调度器 (threading-based)"""

    def __init__(self, db, crawler=None, nlp_modules=None):
        self.db = db
        self.news_crawler = crawler
        self.nlp = nlp_modules or {}
        self._running = False
        self._timers = []

    def set_crawler(self, news_crawler):
        self.news_crawler = news_crawler

    def _crawl_news_task(self):
        logger.info("[定时] 抓取新闻...")
        try:
            if self.news_crawler:
                articles = self.news_crawler.crawl_all()
                if articles:
                    if self.nlp.get("classifier"):
                        articles = self.nlp["classifier"].classify_batch(articles)
                    if self.nlp.get("sentiment"):
                        articles = self.nlp["sentiment"].analyze_batch(articles)
                    self.db.save_news(articles)
                logger.info(f"[定时] 新闻: {len(articles)} 条")
        except Exception as e:
            logger.error(f"[定时] 新闻抓取失败: {e}")

    def _analyze_task(self):
        logger.info("[定时] 分析数据...")
        try:
            articles = self.db.get_all_news(limit=500)
            if not articles:
                return
            from nlp.analyzer import HotTopicAnalyzer
            az = HotTopicAnalyzer()
            analysis = az.full_analysis(articles)
            self.db.save_analysis("full_analysis", analysis)
            keywords = az.extract_keywords([a.get("title","") for a in articles], top_k=20)
            self.db.save_analysis("hot_keywords", {"keywords": keywords})
            trend = az.trend_over_time(articles)
            self.db.save_analysis("trend", {"trend": trend})
            logger.info("[定时] 分析完成")
        except Exception as e:
            logger.error(f"[定时] 分析失败: {e}")

    def _schedule(self, func, interval_minutes):
        """递归调度任务"""
        if not self._running:
            return
        try:
            func()
        except Exception as e:
            logger.error(f"任务异常: {e}")
        if self._running:
            t = threading.Timer(interval_minutes * 60, self._schedule, args=[func, interval_minutes])
            t.daemon = True
            t.start()
            self._timers.append(t)

    def start(self):
        if self._running:
            return
        self._running = True
        logger.info(f"调度器启动: 新闻({config.CRAWL_INTERVAL_MINUTES}min), 分析({config.ANALYSIS_INTERVAL_MINUTES}min)")
        self._schedule(self._crawl_news_task, config.CRAWL_INTERVAL_MINUTES)
        self._schedule(self._analyze_task, config.ANALYSIS_INTERVAL_MINUTES)

    def run_once(self):
        logger.info("[手动] 全量任务开始...")
        self._crawl_news_task()
        self._analyze_task()
        logger.info("[手动] 全量任务完成")

    def stop(self):
        self._running = False
        for t in self._timers:
            t.cancel()
        self._timers.clear()
        logger.info("调度器已停止")
