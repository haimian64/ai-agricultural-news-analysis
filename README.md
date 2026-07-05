# 农业新闻分析与预警系统

Agricultural News Analysis & Early Warning System

基于规则 NLP 的农业新闻智能分析平台，支持多源爬取、自动分类、情感分析、热点提取与可视化仪表盘。无需 GPU、无需外部 API Key、无需 Docker，开箱即用。

## 功能特性

- **多源新闻爬取** — 自动抓取农业农村部、中国农业信息网、天气网等官方渠道的实时新闻与灾害预警
- **智能分类** — 基于关键词规则将新闻分为政策法规、市场行情、农业科技、灾害预警、国际农业、综合资讯六类
- **情感分析** — 规则引擎驱动的情感倾向判断（正面/中性/负面）及风险评分
- **热点提取** — 基于 TF 的二元组关键词提取，支持词云展示
- **趋势分析** — 按时间维度统计各类别新闻分布与情感变化
- **可视化仪表盘** — ECharts 驱动的交互式数据大屏，含饼图、柱状图、折线图、词云
- **天气预报集成** — 接入 Open-Meteo 免费 API，无需注册即可获取城市天气预报
- **定时调度** — 可配置的周期性自动爬取与分析

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 语言 | Python 3.10+ |
| Web 框架 | aiohttp（异步 HTTP 服务） |
| 爬虫 | urllib + lxml + cssselect |
| 数据库 | SQLite3 |
| 前端 | 原生 HTML/CSS/JS + ECharts 5 |
| NLP | 纯规则引擎（可选 transformers 扩展） |
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
cd agricultural-news-analysis

# 创建虚拟环境
python -m venv venv

# 安装依赖
pip install aiohttp lxml cssselect jieba
```

**第二步：启动服务**

**Linux / macOS：**

```bash
source venv/bin/activate
python main.py
```

**Windows：**

```bash
venv\Scripts\activate
python main.py
```

> Windows 用户也可以直接双击 `start.bat`，它会自动调用 `python main.py` 启动服务。

浏览器访问 `http://localhost:8000/dashboard` 即可打开仪表盘。

## 项目结构

```
agricultural-news-analysis/
├── main.py                     # 主入口
├── config.py                   # 全局配置中心
├── requirements.txt            # Python 依赖
├── start.bat                 # Windows 启动脚本
│
├── crawler/                    # 爬虫模块
│   ├── sources.py              # 新闻源与灾害源定义
│   ├── news_crawler.py         # 新闻爬取器
│   └── disaster_crawler.py     # 灾害预警爬取器
│
├── nlp/                        # NLP 分析模块
│   ├── preprocessor.py         # 中文文本预处理与分词
│   ├── classifier.py           # 新闻分类器
│   ├── sentiment.py            # 情感分析与风险评分
│   ├── summarizer.py           # 摘要提取
│   └── analyzer.py             # 热点话题分析
│
├── backend/                    # 后端服务
│   ├── database.py             # SQLite 数据库管理
│   ├── api.py                  # aiohttp 路由与接口
│   └── scheduler.py            # 定时调度器
│
├── frontend/                   # 前端
│   ├── templates/dashboard.html  # 仪表盘页面
│   └── static/
│       ├── css/dashboard.css     # 样式
│       └── js/dashboard.js       # ECharts 图表逻辑
│
├── data/                       # 运行时数据（自动生成）
│   └── agricultural_news.db    # SQLite 数据库
│
└── tests/                      # 测试脚本
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
| `MODEL_MODE` | `"mock"` | NLP 模式：`"mock"` 规则引擎 / `"local"` 本地模型 |
| `SCHEDULER_ENABLED` | `True` | 是否启用定时爬取 |
| `CRAWL_INTERVAL_MINUTES` | `60` | 定时爬取间隔（分钟） |
| `ANALYSIS_INTERVAL_MINUTES` | `30` | 定时分析间隔（分钟） |
| `REQUEST_DELAY` | `2.0` | 爬虫请求间隔（秒） |
| `MAX_NEWS_PER_SOURCE` | `500` | 每个新闻源最大抓取条数 |
| `HOT_TOPIC_WINDOW_DAYS` | `7` | 热点分析时间窗口（天） |

## API 接口

所有接口均返回 JSON。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/statistics` | GET | 数据统计（总数、分类分布） |
| `/api/news` | GET | 新闻列表，支持 `limit` `offset` `category` `start_date` `end_date` `keyword` |
| `/api/news/categories` | GET | 分类标签列表 |
| `/api/disasters` | GET | 活跃灾害预警（无预警时回退到灾害类新闻） |
| `/api/analysis` | GET | 最新完整分析报告 |
| `/api/analysis/hot-keywords` | GET | 热点关键词及权重 |
| `/api/analysis/trend` | GET | 分类趋势数据 |
| `/api/analysis/sentiment-summary` | GET | 情感摘要及综合评分（支持 `start_date` `end_date`） |
| `/api/market` | GET | 市场行情数据（实时抓取 agri.cn，非数据库查询） |
| `/api/weather` | GET | 天气预报，参数 `city`（默认 `郑州`，支持 11 个城市） |
| `/api/crawl` | GET | 手动触发增量爬取 + NLP 流水线（INSERT OR IGNORE，不丢数据） |
| `/dashboard` | GET | 仪表盘页面 |

## 数据库

使用 SQLite 文件存储，位于 `data/agricultural_news.db`，包含以下表：

- `news_articles` — 新闻文章（标题、来源、分类、情感、风险评分等）
- `disaster_warnings` — 灾害预警（区域、等级、灾害类型等）
- `analysis_results` — 分析结果缓存
- `market_data` — 市场行情数据

## 运行测试

```bash
python tests/test_crawler.py
python tests/test_nlp.py
```

> 注意：`tests/test_database.py` 使用的 API 与当前 `DatabaseManager` 实现不一致，暂时无法通过。

## 重要说明

- **增量爬取**：每次点击"爬取实时新闻"或调用 `/api/crawl` 均为增量模式（`INSERT OR IGNORE`），不会删除已有数据。爬虫会根据文章 ID（URL+标题的 MD5）自动跳过已存在的文章。
- **首次启动**：如果数据库中有新闻但缺少分析结果，`main.py` 会自动补齐分析数据，无需手动操作。
- **定时调度**：`NewsScheduler` 类已实现但 `main.py` 默认不启动，爬取需通过仪表盘按钮手动触发。如需定时自动爬取，可在代码中自行启用。

## NLP 模式

### Mock 模式（默认）

`MODEL_MODE = "mock"` 使用纯规则引擎，无需安装额外依赖：
- 分类基于关键词词典匹配
- 分词基于 jieba 中文分词
- 情感分析基于正负面词表
- 摘要基于 TF 关键词评分

### Local 模式（可选）

`MODEL_MODE = "local"` 启用深度学习模型，需额外安装：

```bash
pip install transformers torch
```
