"""
Classifier - Rule-based news category classifier for agricultural news
"""
import logging

logger = logging.getLogger(__name__)

CATEGORIES = ["政策法规", "市场行情", "农业科技", "灾害预警", "国际农业", "综合资讯"]

CATEGORY_KEYWORDS = {
    "政策法规": ["政策", "规定", "条例", "办法", "通知", "农业部", "国务院", "补贴", "扶持", "乡村振兴", "十四五", "农村改革", "土地流转"],
    "市场行情": ["价格", "市场", "行情", "上涨", "下跌", "收购", "批发", "交易", "供应", "需求", "销量", "出口", "进口", "贸易"],
    "农业科技": ["技术", "科技", "智能", "数字化", "育种", "无人机", "物联网", "大数据", "AI", "人工智能", "机器人", "智慧农业"],
    "灾害预警": ["预警", "灾害", "暴雨", "台风", "干旱", "洪涝", "冰雹", "冻害", "病虫害", "高温", "低温", "天气", "气象"],
    "国际农业": ["国际", "全球", "世界", "美国", "欧盟", "东盟", "WTO", "贸易战", "关税", "进口", "出口", "海外", "一带一路"],
}

class NewsClassifier:
    """Rule-based agricultural news classifier"""

    def __init__(self):
        pass

    def classify(self, title, content=""):
        text = f"{title} {content}"
        scores = {}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            score = sum(2 if kw in title else 1 for kw in keywords if kw in text)
            scores[cat] = score
        total = sum(scores.values()) or 1
        # 归一化为概率分布
        probs = {c: round(s / total, 4) for c, s in scores.items()}
        if all(v == 0 for v in scores.values()):
            probs = {c: 0.0 for c in CATEGORIES}
            probs["综合资讯"] = 1.0
            return {"category": "综合资讯", "scores": probs}
        best = max(scores, key=scores.get)
        return {"category": best, "scores": probs}

    def classify_batch(self, articles):
        for article in articles:
            result = self.classify(article.get("title", ""), article.get("content", ""))
            article["category"] = result["category"]
            article["classifier_scores"] = result.get("scores", {})
        return articles
