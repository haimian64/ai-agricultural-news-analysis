"""
全局配置
"""
from pathlib import Path


class Config:
    """应用配置 - 集中管理所有配置参数"""

    # 服务
    HOST = "0.0.0.0"
    PORT = 8000
    DEBUG = True

    # 数据库
    DB_PATH = "data/agricultural_news.db"

    # 爬虫
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    REQUEST_TIMEOUT = 15
    REQUEST_DELAY = 2.0
    MAX_RETRIES = 3
    MAX_NEWS_PER_SOURCE = 500

    # NLP
    MODEL_MODE = "local"  # "mock"=规则引擎 或 "local"=GPU深度学习模型
    NUM_CLASSES = 6
    CATEGORY_LABELS = ["政策法规", "市场行情", "农业科技", "灾害预警", "国际农业", "综合资讯"]
    MAX_INPUT_LENGTH = 512
    MAX_SUMMARY_LENGTH = 128
    HOT_TOPIC_WINDOW_DAYS = 7
    TOP_K_KEYWORDS = 20

    # 灾害提取
    DISASTER_NEWS_WINDOW_DAYS = 7       # AI 灾害提取的时间窗口（天）
    DISASTER_EXTRACTION_ENABLED = True  # 是否启用 AI 灾害提取

    # 聊天机器人
    CHATBOT_ENABLED = True
    GRADIO_PORT = 7860
    CHATBOT_MODEL = "Qwen2.5-3B-Instruct"

    # 路径
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    DB_DIR = DATA_DIR
    MODEL_DIR = BASE_DIR / "models"                      # 深度学习模型目录
    SENTIMENT_MODEL = "bert-base-chinese-sentiment"      # 中文情感三分类（GPU）
    ZERO_SHOT_MODEL = "mDeBERTa-v3-base-xnli"            # 多语言零样本分类（GPU）

    @classmethod
    def ensure_dirs(cls):
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "models").mkdir(parents=True, exist_ok=True)


config = Config()
