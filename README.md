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
- **可视化仪表盘** — ECharts 驱动的交互式数据大屏，含饼图、柱状图、折线图、词云，内置浮动聊天助手
- **天气预报集成** — 接入 Open-Meteo 免费 API，无需注册即可获取全国 ~350+ 城市天气预报
- **AI 聊天助手** — Gradio 驱动的 Qwen2.5-3B-Instruct 对话助手，支持工具调用（查询统计、搜索新闻、查看灾害、天气查询等），通过悬浮按钮在仪表盘上直接使用
- **农产品价格查询** — 实时爬取农业农村部批发市场价格，支持涨跌排行、全国价格走势、分省对比

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

> 模型文件需另外下载放入 `models/` 目录，详见下方「NLP 模式」章节。如不需要聊天助手，可在 `config.py` 中设置 `CHATBOT_ENABLED = False`（gradio 仍会被安装但不影响运行）。

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
│   ├── sources.py                   # 新闻源定义（13 个条目，含 1 对重复配置，实际覆盖 5 个机构/4 个域名）
│   └── news_crawler.py              # 新闻爬取器 + 正文提取
│
├── nlp/                             # NLP 分析模块
│   ├── classifier.py                # 规则新闻分类器（6 分类关键词词典）
│   ├── sentiment.py                 # 规则情感分析与风险评分
│   ├── analyzer.py                  # 热点话题与趋势分析（jieba 分词）
│   ├── preprocessor.py              # 文本预处理（字符二元语法分词，主流程未使用）
│   ├── summarizer.py                # 规则新闻摘要（已实现，主流程未使用）
│   └── model_inference.py           # GPU 深度学习模型推理（懒加载单例）
│
├── models/                          # 预训练模型文件（.gitignore，需手动下载）
│   ├── bert-base-chinese-sentiment/ # 中文情感三分类
│   ├── mDeBERTa-v3-base-xnli/       # 多语言零样本分类
│   └── Qwen2.5-3B-Instruct/         # 灾害提取 + 聊天助手（共享同一实例）
│
├── backend/                         # 后端服务
│   ├── __init__.py                  # 导出 DatabaseManager, create_app, set_db_manager
│   ├── database.py                  # SQLite 数据库管理（WAL 模式，懒连接）
│   ├── api.py                       # aiohttp 路由 + 爬取/NLP 编排 + 价格/天气数据
│   ├── chatbot.py                   # Gradio AI 聊天助手（工具调用 + 会话管理）
│   └── disaster_extraction.py       # AI 灾害信息提取（复用 chatbot 的 Qwen 模型）
│
├── frontend/                        # 前端
│   ├── templates/dashboard.html     # 仪表盘页面（4 标签页 + 浮动聊天组件）
│   └── static/
│       ├── css/dashboard.css        # 仪表盘样式
│       ├── css/chatbot.css          # 浮动聊天组件样式
│       ├── js/dashboard.js          # ECharts 图表逻辑 + 天气/市场/爬取控制
│       ├── js/chatbot.js            # 浮动聊天面板控制（iframe 加载 Gradio）
│       └── logo/                    # 网站图标（4 种尺寸 ICO 文件）
│
├── data/                            # 运行时数据
│   ├── agricultural_dict.txt        # jieba 自定义词典（69 个农业术语）
│   ├── agricultural_news.db         # SQLite 数据库（自动生成，唯一数据存储）
│   ├── raw/                         # 原始爬取数据备份
│   ├── processed/                   # 已处理数据
│   ├── analysis/                    # 分析结果导出
│   └── models/                      # 模型缓存
│
└── tests/                           # 测试脚本（手动运行，无测试框架）
    ├── test_crawler.py
    ├── test_database.py             # ⚠️ 已损坏 — API 与当前实现不一致
    └── test_nlp.py
```

## 配置说明

编辑 `config.py` 即可调整系统行为：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 服务监听地址 |
| `PORT` | `8000` | 服务端口（被占用时自动递增至 8009） |
| `DEBUG` | `True` | 调试模式 |
| `DB_PATH` | `data/agricultural_news.db` | SQLite 数据库路径 |
| `MODEL_MODE` | `"local"` | NLP 模式：`"mock"` 规则引擎 / `"local"` GPU 深度学习（**注意：默认值是 `"local"`，如只需规则引擎请改为 `"mock"`**） |
| `MODEL_DIR` | `BASE_DIR/"models"` | 预训练模型存放目录 |
| `SENTIMENT_MODEL` | `"bert-base-chinese-sentiment"` | 情感分析模型名称 |
| `ZERO_SHOT_MODEL` | `"mDeBERTa-v3-base-xnli"` | 零样本分类模型名称 |
| `REQUEST_DELAY` | `2.0` | 爬虫请求间隔（秒） |
| `REQUEST_TIMEOUT` | `15` | HTTP 请求超时（秒） |
| `MAX_RETRIES` | `3` | 请求失败最大重试次数 |
| `MAX_NEWS_PER_SOURCE` | `500` | 每个新闻源最大抓取条数 |
| `MAX_INPUT_LENGTH` | `512` | NLP 模型最大输入长度 |
| `MAX_SUMMARY_LENGTH` | `128` | 摘要最大长度（字符） |
| `HOT_TOPIC_WINDOW_DAYS` | `7` | 热点分析时间窗口（天） |
| `TOP_K_KEYWORDS` | `20` | 热词提取数量 |
| `DISASTER_NEWS_WINDOW_DAYS` | `7` | AI 灾害提取时间窗口（天） |
| `DISASTER_EXTRACTION_ENABLED` | `True` | 是否启用 AI 灾害提取（需 Qwen 模型） |
| `CHATBOT_ENABLED` | `True` | 是否启用 AI 聊天助手（需 Qwen 模型 + gradio） |
| `GRADIO_PORT` | `7860` | Gradio 聊天界面端口（内部使用，不对外暴露） |
| `CHATBOT_MODEL` | `"Qwen2.5-3B-Instruct"` | 聊天/提取模型名称 |
| `MOA_MAX_CONCURRENT` | `3` | 批量抓取农产品价格时的最大并发数 |

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
| `/api/market/prices` | GET | 实时农产品价格，参数 `commodity`，优先从缓存读取，缓存未命中时实时抓取 ncpscxx.moa.gov.cn |
| `/api/market/prices/fetch-all` | GET | 批量抓取全部 22 种商品价格并写入缓存 |
| `/api/market/categories` | GET | 商品分类树（谷物/油料/棉花/食糖/蔬菜/水果/畜禽） |
| `/api/weather` | GET | 天气预报，参数 `city`（默认 `郑州`，支持 ~350+ 城市） |
| `/api/crawl` | GET | 手动触发增量爬取 + NLP 分析 + AI 灾害提取（五步流程） |
| `/api/model-results` | GET | 模型推理结果详情，支持 `?article_id=xxx` 查单条 |
| `/dashboard` | GET | 仪表盘页面 |
| `/chat_app` 及 `/chat_app/{path}` | GET/POST | 反向代理至 Gradio 聊天助手（含 WebSocket 升级支持，内部端口 7860） |

## 数据库

使用 SQLite 文件存储（WAL 模式），位于 `data/agricultural_news.db`，包含以下表：

- `news_articles` — 新闻文章（标题、来源、分类、情感、风险评分等）
- `disaster_warnings` — 灾害预警（区域、等级、灾害类型、AI 提取的结构化信息）
- `analysis_results` — 聚合分析结果缓存（趋势、热词、综合报告）
- `article_model_results` — 每条新闻的 NLP 模型推理详情
- `market_data` — 市场行情数据
- `commodity_prices` — 农产品价格缓存（22 种商品的完整 JSON 响应，优先于实时抓取）

所有数据仅存储在数据库中，不产生额外的 JSON 文件。

## 运行测试

```bash
python tests/test_crawler.py
python tests/test_nlp.py
```

> 注意：`tests/test_database.py` 使用的 API 与当前 `DatabaseManager` 实现不一致，暂时无法通过。

## 重要说明

- **增量爬取**：每次调用 `/api/crawl` 均为增量模式，根据文章 ID（URL+标题的 MD5）自动跳过已存在的文章。支持通过前端日期选择器过滤爬取范围。分页爬取时连续 3 页无新文章则提前终止。
- **五步爬取流程**：爬取新文章 → 补分析未分析旧文章 → 生成聚合分析 → 同步灾害/市场数据 → AI 灾害信息提取。第 4 步对 `disaster_warnings` 使用 **增量 upsert**（已存在的记录保留 AI 提取字段，仅新增/删除的记录会被插入/清理），`market_data` 仍为清空重建（无 AI 字段需保留）。第 5 步对窗口内**尚未分析**的文章（`severity = 99`）执行 AI 提取，已分析的文章跳过。
- **AI 灾害提取（增量）**：从分类为「灾害预警」的新闻中按需抓取正文，使用 Qwen2.5-3B-Instruct 自动提取发生时间、地点、灾害类型、严重程度和防灾建议。仅处理 `DISASTER_NEWS_WINDOW_DAYS` 时间窗口内的文章，且通过 `severity` 字段判断是否已分析（`!= 99` 则跳过），避免重复推理。提取到有效信息时 `severity` 设为 1-4（对应红/橙/黄/蓝预警等级），无灾害信息时设为 0（已尝试标记）。正文抓取后持久保存到 `news_articles.content`。
- **Qwen 模型共享与加载时机**：聊天助手（`chatbot.py`）和灾害提取（`disaster_extraction.py`）共享同一个 Qwen 模型实例（~5.8 GB 显存），通过 `chatbot.py` 的模块级 `_model_cache` 字典实现懒加载。模型在以下时机之一首次加载：① 用户发送第一条聊天消息；② 启动或爬取时窗口内存在未分析的灾害文章。如果窗口内文章均已分析，启动时**不会加载 Qwen**，启动耗时 < 1 秒。加载后常驻内存直到进程退出，`unload_chatbot_model()` 可手动释放。
- **价格数据缓存**：`commodity_prices` 表缓存所有 22 种商品的完整价格数据，`/api/market/prices` 优先从缓存读取（毫秒级响应），仅缓存未命中时才实时抓取。首次启动时后台自动预抓取全部价格。仪表盘「手动提取所有价格」按钮触发批量刷新。
- **正文按需抓取**：爬虫阶段仅保存标题（content = title），NLP 分类/情感分析基于标题进行。正文抓取仅在 AI 灾害提取时按需触发（仅针对「灾害预警」类文章），抓取后回写到 `news_articles.content`。
- **启动行为**：`main.py` 启动后立即展示最近一次的分析结果，不在启动时自动爬取。点击仪表盘「爬取实时新闻」按钮触发完整五步流程。
- **纯数据库存储**：所有数据读写均通过 SQLite，不产生 JSON 中间文件。`analysis_results` 表在每次启动时被清空并由 `refresh_aggregate_analysis()` 重建。
- **价格数据单位转换**：`_normalize_price()` 对爬取到的价格进行单位标准化：原始值 > 100 视为「元/吨」，除以 1000 转换为「元/公斤」；≤ 100 视为已是「元/公斤」，保持不变。
- **`MODEL_MODE` 默认值**：`config.py` 中 `MODEL_MODE` 默认为 `"local"`（GPU 深度学习模式）。如果未安装 `transformers` 和 `torch`，模型加载会自动回退到规则引擎，但 `_classify_and_sentiment_batch()` 中有无条件 `import torch` 会导致爬取崩溃。如不使用 GPU 模型，建议将 `MODEL_MODE` 改为 `"mock"`。

## NLP 模式

### Mock 模式（规则引擎，推荐默认使用）

编辑 `config.py` 设置 `MODEL_MODE = "mock"` 使用纯规则引擎：
- 分类基于关键词词典匹配（6 分类，~100 个关键词）
- 分词基于 jieba 中文分词（加载自定义农业词典 `data/agricultural_dict.txt`）
- 情感分析基于正负面词表（字符级匹配 + 比例计算）
- 风险评分基于正则关键词（灾害术语 = 0.8，病虫害 = 0.7 等）

> **注意**：`config.py` 中 `MODEL_MODE` 的默认值是 `"local"`，需要手动改为 `"mock"`。如果在 `"local"` 模式下未安装 `torch`，爬取时会因 `_classify_and_sentiment_batch()` 中的无条件 `import torch` 而崩溃。

### Local 模式（GPU 深度学习，可选）

`MODEL_MODE = "local"` 启用深度学习模型，需将模型文件放入 `models/` 目录：

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
| Qwen2.5-3B-Instruct | `backend/chatbot.py` | 灾害信息提取 + AI 聊天助手（**共享同一实例**） |

**技术细节：**

- NLP 模型（BERT + mDeBERTa）采用**懒加载单例**：首次调用才加载到 GPU 显存，不影响启动速度
- Qwen 模型同样懒加载，且由 `chatbot.py` 和 `disaster_extraction.py` **共享同一实例**（通过 `_ensure_model_loaded()` 导入），不重复占显存（~5.8 GB）。启动时如果窗口内灾害文章均已分析，则**不加载模型**。
- 灾害提取支持**增量模式**：通过 `severity` 字段判断文章是否已分析，跳过已处理的文章，仅对新增/未分析的文章执行推理
- 情感分析支持 **GPU 批量推理**（batch_size=64）
- 风险评分保留**规则匹配**（灾害术语几乎无歧义，关键词匹配比模型更可靠）
- NLP 模型加载失败时自动回退规则引擎，不影响服务可用性
