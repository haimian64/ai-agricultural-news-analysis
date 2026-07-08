"""
全局配置
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


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

    # 调度器
    SCHEDULER_ENABLED = True
    CRAWL_INTERVAL_MINUTES = 60
    ANALYSIS_INTERVAL_MINUTES = 30

    # 聊天机器人
    CHATBOT_ENABLED = True
    GRADIO_PORT = 7860
    CHATBOT_MODEL = "Qwen2.5-3B-Instruct"
    MAX_CONVERSATION_TURNS = 20
    MAX_TOOL_CALL_ROUNDS = 3

    # 路径
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / "data"
    RAW_DIR = DATA_DIR / "raw"
    PROCESSED_DIR = DATA_DIR / "processed"
    DB_DIR = DATA_DIR
    MODEL_DIR = BASE_DIR / "models"                      # 深度学习模型目录
    SENTIMENT_MODEL = "bert-base-chinese-sentiment"      # 中文情感三分类（GPU）
    ZERO_SHOT_MODEL = "mDeBERTa-v3-base-xnli"            # 多语言零样本分类（GPU）

    @classmethod
    def ensure_dirs(cls):
        cls.RAW_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        cls.DB_DIR.mkdir(parents=True, exist_ok=True)
        (cls.DATA_DIR / "models").mkdir(parents=True, exist_ok=True)


config = Config()
