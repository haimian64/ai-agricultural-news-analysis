"""
Hot Topic Analyzer - Keyword extraction, category/sentiment distribution, trend analysis
"""
import logging
import re
import jieba
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class HotTopicAnalyzer:
    """Hot topic and trend analyzer"""

    def __init__(self):
        dict_path = Path(__file__).parent.parent / "data" / "agricultural_dict.txt"
        if dict_path.exists():
            jieba.load_userdict(str(dict_path))
            logger.info(f"已加载农业自定义词典: {dict_path}")
        else:
            logger.warning(f"农业词典未找到: {dict_path}")

    def extract_keywords(self, texts, top_k=20):
        """TF-based keyword extraction using jieba segmentation"""
        combined = " ".join(texts) if isinstance(texts, list) else texts
        if not combined:
            return []

        words = []
        for w in re.split(r"[\s,.!?;:　、，。！？；：、（）〔〕【】]+", combined):
            if not w:
                continue
            # Jieba word segmentation (proper Chinese word boundaries)
            if re.match(r"^[\u4e00-\u9fff]+$", w):
                for seg in jieba.cut(w):
                    if len(seg) >= 2:
                        words.append(seg)
            elif len(w) > 2:
                words.append(w)

        counter = Counter(words)
        total = sum(counter.values()) or 1
        return [{"word": w, "weight": round(c / total, 4)}
                for w, c in counter.most_common(top_k) if len(w) > 1]

    def category_distribution(self, articles):
        counter = Counter(a.get("category", "综合资讯") for a in articles)
        total = len(articles) or 1
        return {cat: {"count": cnt, "percentage": round(cnt / total * 100, 1)}
                for cat, cnt in counter.most_common()}

    def sentiment_distribution(self, articles):
        counter = Counter(a.get("sentiment", "neutral") for a in articles)
        total = len(articles) or 1
        return {label: {"count": cnt, "percentage": round(cnt / total * 100, 1)}
                for label, cnt in counter.most_common()}

    def trend_over_time(self, articles, days=7):
        trend = defaultdict(lambda: defaultdict(int))
        for a in articles:
            date = (a.get("date", "") or "")[:10]
            cat = a.get("category", "综合资讯")
            if date:
                trend[date][cat] += 1
        return {date: dict(cats) for date, cats in sorted(trend.items())}

    def risk_warnings(self, articles):
        warnings = []
        for a in articles:
            risk = a.get("risk_score", 0.0)
            if risk > 0.3:
                warnings.append({
                    "title": a.get("title", ""),
                    "date": a.get("date", ""),
                    "category": a.get("category", ""),
                    "risk_score": round(risk, 2),
                    "sentiment": a.get("sentiment", "neutral"),
                    "summary": (a.get("summary", "") or "")[:150],
                })
        warnings.sort(key=lambda x: x["risk_score"], reverse=True)
        return warnings

    def full_analysis(self, articles):
        return {
            "total_articles": len(articles),
            "category_distribution": self.category_distribution(articles),
            "sentiment_distribution": self.sentiment_distribution(articles),
            "trend": self.trend_over_time(articles),
            "hot_keywords": self.extract_keywords(
                [a.get("title", "") for a in articles if a.get("title")], top_k=20
            ),
            "risk_warnings": self.risk_warnings(articles),
            "analyzed_at": datetime.now().isoformat(),
        }
