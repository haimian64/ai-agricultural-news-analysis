"""
Sentiment - Rule-based sentiment and risk analyzer for agricultural news
"""
import logging
import re

logger = logging.getLogger(__name__)

POSITIVE_WORDS = set("增长上升提高改善丰收增产增收盈利利好突破创新发展振兴繁荣稳定回暖扩大优化")
NEGATIVE_WORDS = set("下降减少亏损减产受灾损失下跌滑坡萎缩恶化紧张短缺危机冲击滞销积压")

RISK_PATTERNS = [
    (re.compile(r"预警|灾害|暴雨|台风|干旱|洪涝|冰雹|冻害"), 0.8),
    (re.compile(r"病虫害|疫情|感染|传播|爆发"), 0.7),
    (re.compile(r"下降|下跌|减产|亏损|滞销"), 0.5),
    (re.compile(r"紧张|短缺|危机|冲击"), 0.6),
]

class SentimentAnalyzer:
    """Rule-based sentiment analyzer"""

    def __init__(self):
        pass

    def analyze(self, text):
        if not text:
            return {"label": "neutral", "score": 0.5,
                    "scores": {"positive": 0.33, "neutral": 0.34, "negative": 0.33},
                    "risk_score": 0.0}

        pos_count = sum(1 for w in POSITIVE_WORDS if w in text)
        neg_count = sum(1 for w in NEGATIVE_WORDS if w in text)
        total = pos_count + neg_count

        if total == 0:
            label = "neutral"
            score = 0.5
            all_scores = {"positive": 0.33, "neutral": 0.34, "negative": 0.33}
        else:
            ratio = pos_count / total
            if ratio > 0.6:
                label = "positive"
                score = ratio
            elif ratio < 0.4:
                label = "negative"
                score = 1 - ratio
            else:
                label = "neutral"
                score = 0.5
            # 规则引擎的概率分布
            all_scores = {
                "positive": round(ratio, 4),
                "neutral": round(0.5 - abs(ratio - 0.5), 4),
                "negative": round(1 - ratio, 4),
            }

        risk_score = min(sum(w for pat, w in RISK_PATTERNS if pat.search(text)), 1.0)

        return {"label": label, "score": score, "scores": all_scores, "risk_score": risk_score}

    def analyze_batch(self, articles):
        for article in articles:
            text = f"{article.get('title', '')} {article.get('content', '')}"
            result = self.analyze(text)
            article["sentiment"] = result["label"]
            article["sentiment_score"] = result["score"]
            article["sentiment_scores"] = result.get("scores", {})
            article["risk_score"] = result.get("risk_score", 0.0)
        return articles
