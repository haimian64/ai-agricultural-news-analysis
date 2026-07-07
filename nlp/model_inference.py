"""
GPU 模型推理模块 — 基于 transformers 的深度学习新闻分类与情感分析。

替代规则引擎（MODEL_MODE="local" 时生效），提供与 NewsClassifier /
SentimentAnalyzer 相同的调用接口，便于无缝切换。

模型：
- bert-base-chinese-sentiment → 中文情感三分类（正面/中性/负面）
- mDeBERTa-v3-base-xnli    → 多语言零样本分类（6 个农业新闻类别）
"""
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================
# 风险评分 — 保留规则匹配（灾害术语无歧义，关键词匹配最可靠）
# ============================================================
RISK_PATTERNS = [
    (re.compile(r"预警|灾害|暴雨|台风|干旱|洪涝|冰雹|冻害"), 0.8),
    (re.compile(r"病虫害|疫情|感染|传播|爆发"), 0.7),
    (re.compile(r"下降|下跌|减产|亏损|滞销"), 0.5),
    (re.compile(r"紧张|短缺|危机|冲击"), 0.6),
]


def _calc_risk(text: str) -> float:
    """基于关键词的风险评分（0.0-1.0），保留规则引擎逻辑"""
    return round(min(sum(w for pat, w in RISK_PATTERNS if pat.search(text)), 1.0), 2)


# ============================================================
# 模型路径（相对于项目根目录）
# ============================================================
BASE_DIR = Path(__file__).parent.parent
SENTIMENT_MODEL_PATH = str(BASE_DIR / "models" / "bert-base-chinese-sentiment")
ZERO_SHOT_MODEL_PATH = str(BASE_DIR / "models" / "mDeBERTa-v3-base-xnli")

# 零样本分类标签（与 config.CATEGORY_LABELS 保持一致）
CATEGORY_LABELS = ["政策法规", "市场行情", "农业科技", "灾害预警", "国际农业", "综合资讯"]

# 情感标签：模型输出顺序为 [负面, 正面, 中性]，映射到内部英文 key
# config.json: id2label = {'0': '負面', '1': '正面', '2': '中性'}
SENTIMENT_LABEL_ORDER = ["negative", "positive", "neutral"]

# ============================================================
# 懒加载单例（避免 import 时加载模型，也避免重复加载）
# ============================================================
_models: dict[str, tuple] = {}


def _get_device():
    """返回 torch device 对象，优先 GPU"""
    import torch
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def _load_sentiment_model():
    """加载 BERT 中文情感模型 → (model, tokenizer, device)"""
    if "sentiment" not in _models:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        device = _get_device()
        logger.info(f"[MODEL] 加载情感模型: {SENTIMENT_MODEL_PATH} → {device}")
        tokenizer = AutoTokenizer.from_pretrained(SENTIMENT_MODEL_PATH)
        model = AutoModelForSequenceClassification.from_pretrained(SENTIMENT_MODEL_PATH)
        model.eval()
        model = model.to(device)
        _models["sentiment"] = (model, tokenizer, device)
    return _models["sentiment"]


def _load_zeroshot_pipeline():
    """加载零样本分类 pipeline"""
    if "zeroshot" not in _models:
        from transformers import pipeline

        device = _get_device()
        device_int = 0 if str(device).startswith("cuda") else -1
        logger.info(f"[MODEL] 加载零样本模型: {ZERO_SHOT_MODEL_PATH} (device={device_int})")
        _models["zeroshot"] = pipeline(
            "zero-shot-classification",
            model=ZERO_SHOT_MODEL_PATH,
            tokenizer=ZERO_SHOT_MODEL_PATH,
            device=device_int,
        )
    return _models["zeroshot"]


# ============================================================
# 公开接口 — 与规则版 NewsClassifier / SentimentAnalyzer 保持一致
# ============================================================

class ModelNewsClassifier:
    """基于 mDeBERTa 零样本推理的新闻分类器。

    接口兼容 nlp.classifier.NewsClassifier：
        classify(title) → {"category": str, "scores": dict}
    """

    def __init__(self):
        self._pipe = None

    def _ensure_loaded(self):
        if self._pipe is None:
            self._pipe = _load_zeroshot_pipeline()

    def classify(self, title: str, content: str = "") -> dict:
        """对单条新闻标题做零样本分类"""
        self._ensure_loaded()
        text = f"{title} {content}".strip() if content else title
        if not text:
            return {"category": "综合资讯", "scores": {}}
        try:
            result = self._pipe(
                text, candidate_labels=CATEGORY_LABELS, multi_label=False
            )
            best_label = result["labels"][0]
            scores = dict(zip(result["labels"], result["scores"]))
            return {"category": best_label, "scores": scores}
        except Exception as e:
            logger.warning(f"[MODEL] 分类失败，回退综合资讯: {e}")
            return {"category": "综合资讯", "scores": {}}

    def classify_batch(self, articles: list[dict]) -> list[dict]:
        """批量分类（逐条推理）"""
        self._ensure_loaded()
        for a in articles:
            result = self.classify(a.get("title", ""), a.get("content", ""))
            a["category"] = result["category"]
        return articles

    @staticmethod
    def get_categories() -> list[str]:
        return CATEGORY_LABELS


class ModelSentimentAnalyzer:
    """基于 BERT 中文情感模型 + 规则风险评分的分析器。

    使用 AutoModelForSequenceClassification 手动推理（非 pipeline），
    支持 GPU 批量推理以获得更高吞吐量。

    接口兼容 nlp.sentiment.SentimentAnalyzer：
        analyze(text) → {"label": "positive"|"neutral"|"negative",
                          "score": float, "risk_score": float}
    """

    def __init__(self):
        self._model = None
        self._tokenizer = None
        self._device = None

    def _ensure_loaded(self):
        if self._model is None:
            self._model, self._tokenizer, self._device = _load_sentiment_model()

    def analyze(self, text: str) -> dict:
        """单条文本情感分析"""
        if not text:
            return {"label": "neutral", "score": 0.5, "risk_score": 0.0}

        self._ensure_loaded()
        import torch

        try:
            inputs = self._tokenizer(
                text, return_tensors="pt", truncation=True, max_length=512
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                logits = self._model(**inputs).logits
                probs = torch.nn.functional.softmax(logits, dim=-1)[0]

            best_idx = int(torch.argmax(probs).item())
            label = SENTIMENT_LABEL_ORDER[best_idx]
            score = round(float(probs[best_idx].item()), 4)
            risk = _calc_risk(text)

            return {"label": label, "score": score, "risk_score": risk}
        except Exception as e:
            logger.warning(f"[MODEL] 情感分析失败，回退中性: {e}")
            return {"label": "neutral", "score": 0.5, "risk_score": 0.0}

    def analyze_batch(self, articles: list[dict], batch_size: int = 64) -> list[dict]:
        """批量情感分析（GPU 批量推理）"""
        self._ensure_loaded()
        import torch

        texts = [
            f"{a.get('title', '')} {a.get('content', '')}".strip()
            for a in articles
        ]

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            try:
                inputs = self._tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                    padding=True,
                )
                inputs = {k: v.to(self._device) for k, v in inputs.items()}

                with torch.no_grad():
                    logits = self._model(**inputs).logits
                    probs = torch.nn.functional.softmax(logits, dim=-1)

                best_idxs = torch.argmax(probs, dim=-1)
                for j, (idx, prob_row) in enumerate(zip(best_idxs, probs)):
                    a = articles[i + j]
                    a["sentiment"] = SENTIMENT_LABEL_ORDER[int(idx.item())]
                    a["sentiment_score"] = round(float(prob_row[int(idx.item())].item()), 4)
                    a["risk_score"] = _calc_risk(texts[i + j])
            except Exception as e:
                logger.warning(f"[MODEL] 批量情感分析失败 (batch {i}-{i+batch_size}): {e}")
                # 回退逐条处理
                for j in range(len(batch_texts)):
                    r = self.analyze(texts[i + j])
                    a = articles[i + j]
                    a["sentiment"] = r["label"]
                    a["sentiment_score"] = r["score"]
                    a["risk_score"] = r.get("risk_score", 0.0)

        return articles


def unload_models():
    """释放模型显存（调试/测试用）"""
    import gc
    import torch

    global _models
    _models.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    logger.info("[MODEL] 已释放所有模型")
