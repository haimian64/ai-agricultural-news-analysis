# 农业新闻分析与预警系统

Agricultural News Analysis & Early Warning System

基于规则 NLP + 深度学习（可选）的农业新闻智能分析平台，支持多源爬取、自动分类、情感分析、热点提取、AI 灾害信息提取与可视化仪表盘。默认无需 GPU、无需外部 API Key、无需 Docker，开箱即用。

## 功能特性

- **多源新闻爬取** — 自动抓取农信网、农业农村部、中国气象网、水利部等官方渠道的实时新闻
- **智能分类** — 支持规则关键词匹配（默认）与 mDeBERTa 多语言零样本分类（GPU），六类：政策法规、市场行情、农业科技、灾害预警、国际农业、综合资讯
- **情感分析** — 支持规则引擎（默认）与 BERT 中文深度学习情感三分类（GPU），含风险评分
- **AI 灾害信息提取** — 使用 Qwen2.5-3B-Instruct 从灾害新闻正文中自动提取：发生时间、地点、灾害类型、严重程度、防灾建议，并写入数据库
- **热点提取** — 基于 TF 的关键词提取，支持词云展示
- **趋势分析** — 按时间维度统计各类别新闻分布与情感变化
- **可视化仪表盘** — ECharts 驱动的交互式数据大屏，含饼图、柱状图、折线图、词云
- **天气预报集成** — 接入 Open-Meteo 免费 API，无需注册即可获取全国 ~350+ 城市天气预报
- **AI 聊天助手** — Gradio 驱动的 Qwen2.5-3B-Instruct 对话助手，支持工具调用（查询统计、搜索新闻、查看灾害等）

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 语言 | Python 3.10+ |
| Web 框架 | aiohttp（异步 HTTP 服务） |
| 爬虫 | urllib + lxml + cssselect |
| 数据库 | SQLite3（WAL 模式，增量写入） |
| 前端 | 原生 HTML/CSS/JS + ECharts 5 |
| NLP | 规则引擎（默认）/ transformers 深度学习模型（可选 GPU） |
| GPU 模型 | mDeBERTa-v3-base-xnli（零样本分类）+ bert-base-chinese-sentiment（情感分析） |
| AI 提取 | Qwen2.5-3B-Instruct（灾害信息结构化提取） |
| 天气 | Open-Meteo（免费，无需 API Key） |

## 快速开始

### 环境要求

- Python 3.10 或更高版本
- pip 包管理器

### 安装与运行

**第一步：安装依赖**

```bash
# 克隆项目
git clone https://github.com/haimian64/ai-agricultural-news-analysis.git
cd ai-agricultural-news-analysis

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装核心依赖（含 Gradio 聊天助手）
pip install -r requirements.txt

# 可选：如需启用 GPU 深度学习模型
pip install transformers torch
```

> 模型文件需另外下载放入 `models/` 目录，详见下方「NLP 模式」章节。如不需要聊天助手，可在 `config.py` 中设置 `CHATBOT_ENABLED = False` 并跳过 `gradio` 安装。

**第二步：启动服务**

```bash
python main.py
```

浏览器访问 `http://localhost:8000/dashboard` 即可打开仪表盘。

## 项目结构

```
agricultural-news-analysis/
├── main.py                          # 主入口
├── config.py                        # 全局配置中心
├── requirements.txt                 # Python 依赖
├── start.bat                        # Windows 启动脚本（激活 venv + 启动服务，不含安装依赖）
│
├── crawler/                         # 爬虫模块
│   ├── sources.py                   # 新闻源定义（12 个源）
│   └── news_crawler.py              # 新闻爬取器 + 正文提取
│
├── nlp/                             # NLP 分析模块
│   ├── classifier.py                # 规则新闻分类器
│   ├── sentiment.py                 # 规则情感分析与风险评分
│   ├── analyzer.py                  # 热点话题与趋势分析
│   ├── preprocessor.py              # 文本预处理（字符二元语法分词）
│   ├── summarizer.py                # 规则新闻摘要（已实现，主流程未使用）
│   └── model_inference.py           # GPU 深度学习模型推理（懒加载）
│
├── models/                          # 预训练模型文件（.gitignore，需手动下载）
│   ├── bert-base-chinese-sentiment/ # 中文情感三分类
│   ├── mDeBERTa-v3-base-xnli/       # 多语言零样本分类
│   └── Qwen2.5-3B-Instruct/         # 灾害提取 + 聊天助手
│
├── backend/                         # 后端服务
│   ├── database.py                  # SQLite 数据库管理
│   ├── api.py                       # aiohttp 路由与业务逻辑
│   ├── chatbot.py                   # Gradio AI 聊天助手
│   └── disaster_extraction.py       # AI 灾害信息提取
│
├── frontend/                        # 前端
│   ├── templates/dashboard.html     # 仪表盘页面
│   └── static/
│       ├── css/dashboard.css        # 样式
│       └── js/dashboard.js          # ECharts 图表逻辑
│
├── data/                            # 运行时数据（自动生成）
│   └── agricultural_news.db         # SQLite 数据库（唯一数据存储）
│
└── tests/                           # 测试脚本
    ├── test_crawler.py
    ├── test_database.py
    └── test_nlp.py
```

## 配置说明

编辑 `config.py` 即可调整系统行为：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 服务监听地址 |
| `PORT` | `8000` | 服务端口（被占用时自动递增） |
| `MODEL_MODE` | `"local"` | NLP 模式：`"mock"` 规则引擎 / `"local"` GPU 深度学习 |
| `MODEL_DIR` | `BASE_DIR/"models"` | 预训练模型存放目录 |
| `SENTIMENT_MODEL` | `"bert-base-chinese-sentiment"` | 情感分析模型名称 |
| `ZERO_SHOT_MODEL` | `"mDeBERTa-v3-base-xnli"` | 零样本分类模型名称 |
| `REQUEST_DELAY` | `2.0` | 爬虫请求间隔（秒） |
| `MAX_NEWS_PER_SOURCE` | `500` | 每个新闻源最大抓取条数 |
| `HOT_TOPIC_WINDOW_DAYS` | `7` | 热点分析时间窗口（天） |
| `DISASTER_NEWS_WINDOW_DAYS` | `7` | AI 灾害提取时间窗口（天） |
| `DISASTER_EXTRACTION_ENABLED` | `True` | 是否启用 AI 灾害提取 |
| `CHATBOT_ENABLED` | `True` | 是否启用 AI 聊天助手 |
| `GRADIO_PORT` | `7860` | Gradio 聊天界面端口 |
| `CHATBOT_MODEL` | `"Qwen2.5-3B-Instruct"` | 聊天/提取模型名称 |

## API 接口

所有接口均返回 JSON。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/statistics` | GET | 数据统计（总数、分类分布） |
| `/api/news` | GET | 新闻列表，支持 `limit` `offset` `category` `start_date` `end_date` `keyword` |
| `/api/news/categories` | GET | 分类标签列表 |
| `/api/disasters` | GET | 活跃灾害预警（含 AI 提取的结构化字段） |
| `/api/disasters/extract` | GET | 手动触发 AI 灾害信息提取，支持 `?force=1` 重新提取全部 |
| `/api/analysis` | GET | 最新完整分析报告 |
| `/api/analysis/hot-keywords` | GET | 热点关键词及权重 |
| `/api/analysis/trend` | GET | 分类趋势数据 |
| `/api/analysis/sentiment-summary` | GET | 情感摘要及综合评分 |
| `/api/market` | GET | 市场行情数据（从数据库读取） |
| `/api/market/prices` | GET | 实时农产品价格，参数 `commodity`，从 ncpscxx.moa.gov.cn 实时抓取 |
| `/api/market/categories` | GET | 商品分类树（谷物/油料/棉花/食糖/蔬菜/水果/畜禽） |
| `/api/weather` | GET | 天气预报，参数 `city`（默认 `郑州`，支持 ~350+ 城市） |
| `/api/crawl` | GET | 手动触发增量爬取 + NLP 分析 + AI 灾害提取（五步流程） |
| `/api/model-results` | GET | 模型推理结果详情，支持 `?article_id=xxx` 查单条 |
| `/dashboard` | GET | 仪表盘页面 |
| `/chat_app` 及 `/chat_app/{path}` | GET/POST | 反向代理至 Gradio 聊天助手（内部端口 7860） |

## 数据库

使用 SQLite 文件存储（WAL 模式），位于 `data/agricultural_news.db`，包含以下表：

- `news_articles` — 新闻文章（标题、来源、分类、情感、风险评分等）
- `disaster_warnings` — 灾害预警（区域、等级、灾害类型、AI 提取的结构化信息）
- `analysis_results` — 聚合分析结果缓存（趋势、热词、综合报告）
- `article_model_results` — 每条新闻的 NLP 模型推理详情
- `market_data` — 市场行情数据

所有数据仅存储在数据库中，不产生额外的 JSON 文件。

## 运行测试

```bash
python tests/test_crawler.py
python tests/test_nlp.py
```

> 注意：`tests/test_database.py` 使用的 API 与当前 `DatabaseManager` 实现不一致，暂时无法通过。

## 重要说明

- **增量爬取**：每次调用 `/api/crawl` 均为增量模式，根据文章 ID（URL+标题的 MD5）自动跳过已存在的文章。支持通过前端日期选择器过滤爬取范围。
- **五步爬取流程**：爬取新文章 → 补分析未分析旧文章 → 生成聚合分析 → 同步灾害/市场数据 → AI 灾害信息提取（默认启用，可关闭）。
- **AI 灾害提取**：从分类为「灾害预警」的新闻中按需抓取正文，使用 Qwen2.5-3B-Instruct 自动提取发生时间、地点、灾害类型、严重程度和防灾建议，写入 `disaster_warnings` 表。仅处理时间窗口内的文章，正文抓取后持久保存到 `news_articles.content`，避免重复请求。
- **启动行为**：`main.py` 启动后立即展示最近一次的分析结果，不在启动时自动爬取。点击仪表盘「爬取实时新闻」按钮触发完整五步流程。
- **纯数据库存储**：所有数据读写均通过 SQLite，不再产生 JSON 中间文件。

## NLP 模式

### Mock 模式（规则引擎）

编辑 `config.py` 设置 `MODEL_MODE = "mock"` 使用纯规则引擎：
- 分类基于关键词词典匹配
- 分词基于 jieba 中文分词
- 情感分析基于正负面词表

### Local 模式（GPU 深度学习）

`MODEL_MODE = "local"`（默认）启用深度学习模型，需将模型文件放入 `models/` 目录：

```bash
# 1. 安装 GPU 依赖
pip install transformers torch

# 2. 下载模型文件到 models/ 目录
#    - bert-base-chinese-sentiment
#    - mDeBERTa-v3-base-xnli
#    - Qwen2.5-3B-Instruct（用于灾害提取 + 聊天助手）
```

**三种模型：**

| 模型 | 文件 | 任务 |
|------|------|------|
| `ModelNewsClassifier` | `nlp/model_inference.py` | 新闻六分类（mDeBERTa-v3 零样本） |
| `ModelSentimentAnalyzer` | `nlp/model_inference.py` | 情感三分类 + 风险评分（BERT 中文） |
| Qwen2.5-3B-Instruct | `backend/chatbot.py` | 灾害信息提取 + AI 聊天助手 |

**技术细节：**

- 模型采用**懒加载**：首次调用才加载到 GPU 显存，不影响启动速度
- 情感分析支持 **GPU 批量推理**（batch_size=64）
- 风险评分保留**规则匹配**（灾害术语几乎无歧义，关键词匹配比模型更可靠）
- 模型加载失败时自动回退规则引擎，不影响服务可用性
- Qwen 模型由 chatbot 和 disaster_extraction **共享同一实例**，不重复占显存
