"""
数据库模块 - 添加搜索、日期筛选、市场数据、模型推理结果存储
"""
import json, sqlite3, logging, re
from datetime import datetime
from pathlib import Path
from config import config

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = str(config.DB_DIR / "agricultural_news.db")
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._init_tables()
        return self._conn

    def _init_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS news_articles (
                id TEXT PRIMARY KEY, title TEXT, url TEXT, source TEXT,
                date TEXT, content TEXT, summary TEXT,
                category TEXT DEFAULT '综合资讯',
                sentiment TEXT DEFAULT 'neutral',
                sentiment_score REAL DEFAULT 0.5,
                risk_score REAL DEFAULT 0.0, crawled_at TEXT
            );
            CREATE TABLE IF NOT EXISTS disaster_warnings (
                id TEXT PRIMARY KEY, source TEXT, region TEXT, title TEXT,
                url TEXT, date TEXT, alert_level TEXT, severity INTEGER DEFAULT 99,
                disaster_type TEXT, risk_score REAL DEFAULT 0.0, description TEXT, crawled_at TEXT
            );
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_type TEXT, result_json TEXT, created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT, url TEXT, category TEXT,
                date TEXT, content TEXT, crawled_at TEXT
            );
            CREATE TABLE IF NOT EXISTS article_model_results (
                article_id TEXT PRIMARY KEY,
                model_mode TEXT NOT NULL,
                classifier_name TEXT,
                classifier_scores TEXT,
                classifier_category TEXT,
                sentiment_name TEXT,
                sentiment_scores TEXT,
                sentiment_label TEXT,
                sentiment_score REAL,
                risk_score REAL,
                model_params TEXT,
                analyzed_at TEXT NOT NULL
            );
        """)
        self.conn.commit()

    # ============================================================
    # 新闻 & 灾害 & 市场 — 不变
    # ============================================================
    def save_news(self, articles):
        c = self.conn.cursor()
        count = 0
        for a in articles:
            try:
                c.execute("INSERT OR IGNORE INTO news_articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (a["id"], a.get("title", ""), a.get("url", ""), a.get("source", ""),
                           a.get("date", ""), a.get("content", ""), a.get("summary", ""),
                           a.get("category", "综合资讯"), a.get("sentiment", "neutral"),
                           a.get("sentiment_score", 0.5), a.get("risk_score", 0.0),
                           a.get("crawled_at", "")))
                if c.rowcount > 0: count += 1
            except Exception as e:
                logger.error(f"保存新闻失败: {e}")
        self.conn.commit()
        return count

    def save_disasters(self, warnings):
        c = self.conn.cursor()
        count = 0
        for w in warnings:
            try:
                c.execute("INSERT OR IGNORE INTO disaster_warnings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                          (w["id"], w.get("source", ""), w.get("region", ""), w.get("title", ""),
                           w.get("url", ""), w.get("date", ""), w.get("alert_level", "未知"),
                           w.get("severity", 99), w.get("disaster_type", "未知"), w.get("risk_score", 0.0),
                           w.get("description", ""), ""))
                if c.rowcount > 0: count += 1
            except:
                pass
        self.conn.commit()
        return count

    def save_market_data(self, items):
        c = self.conn.cursor()
        count = 0
        for item in items:
            try:
                c.execute(
                    "INSERT OR IGNORE INTO market_data (title, url, category, date, content, crawled_at) VALUES (?,?,?,?,?,?)",
                    (item.get("title", ""), item.get("url", ""), item.get("category", ""),
                     item.get("date", ""), item.get("content", ""), datetime.now().isoformat()))
                if c.rowcount > 0: count += 1
            except:
                pass
        self.conn.commit()
        return count

    # ============================================================
    # 模型推理结果 — 每条新闻独立存储
    # ============================================================
    def save_article_model_result(self, article_id: str, result: dict):
        """保存单条新闻的模型推理结果"""
        c = self.conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO article_model_results
            (article_id, model_mode, classifier_name, classifier_scores,
             classifier_category, sentiment_name, sentiment_scores,
             sentiment_label, sentiment_score, risk_score, model_params, analyzed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            article_id,
            result.get("model_mode", ""),
            result.get("classifier_name", ""),
            json.dumps(result.get("classifier_scores", {}), ensure_ascii=False),
            result.get("classifier_category", ""),
            result.get("sentiment_name", ""),
            json.dumps(result.get("sentiment_scores", {}), ensure_ascii=False),
            result.get("sentiment_label", ""),
            result.get("sentiment_score", 0.0),
            result.get("risk_score", 0.0),
            json.dumps(result.get("model_params", {}), ensure_ascii=False),
            result.get("analyzed_at", datetime.now().isoformat()),
        ))
        self.conn.commit()

    def save_article_model_results_batch(self, results: list[dict]):
        """批量保存模型推理结果"""
        c = self.conn.cursor()
        rows = []
        for r in results:
            rows.append((
                r["article_id"],
                r.get("model_mode", ""),
                r.get("classifier_name", ""),
                json.dumps(r.get("classifier_scores", {}), ensure_ascii=False),
                r.get("classifier_category", ""),
                r.get("sentiment_name", ""),
                json.dumps(r.get("sentiment_scores", {}), ensure_ascii=False),
                r.get("sentiment_label", ""),
                r.get("sentiment_score", 0.0),
                r.get("risk_score", 0.0),
                json.dumps(r.get("model_params", {}), ensure_ascii=False),
                r.get("analyzed_at", datetime.now().isoformat()),
            ))
        c.executemany("""
            INSERT OR REPLACE INTO article_model_results
            (article_id, model_mode, classifier_name, classifier_scores,
             classifier_category, sentiment_name, sentiment_scores,
             sentiment_label, sentiment_score, risk_score, model_params, analyzed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        self.conn.commit()
        logger.info(f"[DB] 批量保存 {len(rows)} 条模型结果")

    def get_article_model_result(self, article_id: str) -> dict | None:
        """获取单条新闻的模型推理结果（已解析 JSON）"""
        c = self.conn.cursor()
        c.execute("SELECT * FROM article_model_results WHERE article_id=?", (article_id,))
        row = c.fetchone()
        if not row:
            return None
        d = dict(row)
        for field in ("classifier_scores", "sentiment_scores", "model_params"):
            try:
                d[field] = json.loads(d.get(field, "{}"))
            except (json.JSONDecodeError, TypeError):
                d[field] = {}
        return d

    def get_analyzed_article_ids(self) -> set[str]:
        """获取已分析的新闻 ID 集合"""
        c = self.conn.cursor()
        c.execute("SELECT article_id FROM article_model_results")
        return {r[0] for r in c.fetchall()}

    def get_unanalyzed_article_ids(self, limit: int = 5000) -> list[str]:
        """获取尚未分析的新闻 ID 列表"""
        c = self.conn.cursor()
        c.execute("""
            SELECT n.id FROM news_articles n
            LEFT JOIN article_model_results m ON n.id = m.article_id
            WHERE m.article_id IS NULL
            ORDER BY n.date DESC
            LIMIT ?
        """, (limit,))
        return [r[0] for r in c.fetchall()]

    def count_unanalyzed_articles(self) -> int:
        """统计未分析的新闻数量"""
        c = self.conn.cursor()
        c.execute("""
            SELECT COUNT(*) FROM news_articles n
            LEFT JOIN article_model_results m ON n.id = m.article_id
            WHERE m.article_id IS NULL
        """)
        return c.fetchone()[0]

    def get_all_model_results(self) -> list[dict]:
        """获取所有模型推理结果（含解析后的 JSON）"""
        c = self.conn.cursor()
        c.execute("SELECT * FROM article_model_results ORDER BY analyzed_at DESC")
        results = []
        for row in c.fetchall():
            d = dict(row)
            for field in ("classifier_scores", "sentiment_scores", "model_params"):
                try:
                    d[field] = json.loads(d.get(field, "{}"))
                except (json.JSONDecodeError, TypeError):
                    d[field] = {}
            results.append(d)
        return results

    def export_model_results_json(self, filepath: str = None) -> str:
        """导出所有模型推理结果为 JSON 文件，返回文件路径"""
        if filepath is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_dir = config.DATA_DIR / "analysis"
            export_dir.mkdir(parents=True, exist_ok=True)
            filepath = str(export_dir / f"model_results_{ts}.json")

        results = self.get_all_model_results()
        export = {
            "exported_at": datetime.now().isoformat(),
            "model_mode": config.MODEL_MODE,
            "total": len(results),
            "results": results,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2)
        logger.info(f"[DB] 导出 {len(results)} 条模型结果 → {filepath}")
        return filepath

    def get_articles_with_model_results(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """获取新闻 + 模型结果（JOIN 查询，便于前端展示）"""
        c = self.conn.cursor()
        c.execute("""
            SELECT n.*, m.model_mode, m.classifier_name, m.classifier_scores,
                   m.classifier_category as model_category,
                   m.sentiment_name, m.sentiment_scores,
                   m.sentiment_label as model_sentiment_label,
                   m.sentiment_score as model_sentiment_score,
                   m.risk_score as model_risk_score,
                   m.model_params, m.analyzed_at
            FROM news_articles n
            LEFT JOIN article_model_results m ON n.id = m.article_id
            ORDER BY n.date DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        articles = []
        for row in c.fetchall():
            d = dict(row)
            for field in ("classifier_scores", "sentiment_scores", "model_params"):
                try:
                    d[field] = json.loads(d.get(field, "{}"))
                except (json.JSONDecodeError, TypeError):
                    d[field] = {}
            articles.append(d)
        return articles

    # ============================================================
    # 查询 & 统计 — 不变
    # ============================================================
    # database.py 中修改 get_all_news 方法
    def get_all_news(self, limit=None, offset=0, category=None):
        c = self.conn.cursor()
        sql = "SELECT * FROM news_articles"
        params = []
        if category:
            sql += " WHERE category=?"
            params.append(category)
        sql += " ORDER BY date DESC"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        c.execute(sql, params)
        return [dict(r) for r in c.fetchall()]

    def search_news(self, keyword, limit=50):
        c = self.conn.cursor()
        like = f"%{keyword}%"
        c.execute("SELECT * FROM news_articles WHERE title LIKE ? ORDER BY date DESC LIMIT ?", (like, limit))
        return [dict(r) for r in c.fetchall()]

    def get_news_by_date_range(self, start_date, end_date, limit=200):
        c = self.conn.cursor()
        c.execute("SELECT * FROM news_articles WHERE date >= ? AND date <= ? ORDER BY date DESC LIMIT ?",
                  (start_date, end_date, limit))
        return [dict(r) for r in c.fetchall()]

    def get_news_by_keyword_and_date(self, keyword, start_date=None, end_date=None, limit=50):
        c = self.conn.cursor()
        like = f"%{keyword}%"
        if start_date and end_date:
            c.execute(
                "SELECT * FROM news_articles WHERE title LIKE ? AND date >= ? AND date <= ? ORDER BY date DESC LIMIT ?",
                (like, start_date, end_date, limit))
        else:
            c.execute("SELECT * FROM news_articles WHERE title LIKE ? ORDER BY date DESC LIMIT ?", (like, limit))
        return [dict(r) for r in c.fetchall()]

    def get_sentiment_summary(self, start_date=None, end_date=None):
        c = self.conn.cursor()
        if start_date and end_date:
            c.execute(
                "SELECT COUNT(*), AVG(sentiment_score), SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END), SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) FROM news_articles WHERE date >= ? AND date <= ?",
                (start_date, end_date))
        else:
            c.execute(
                "SELECT COUNT(*), AVG(sentiment_score), SUM(CASE WHEN sentiment='positive' THEN 1 ELSE 0 END), SUM(CASE WHEN sentiment='negative' THEN 1 ELSE 0 END) FROM news_articles")
        row = c.fetchone()
        total = row[0] or 0
        avg = row[1] or 0.5
        pos = row[2] or 0
        neg = row[3] or 0
        score = round(avg * 10, 1)
        label = "正向" if score >= 7 else ("负向" if score <= 4 else "中性")
        return {"total": total, "positive": pos, "negative": neg, "avg_score": avg, "score_10": score, "label": label}

    def get_market_data(self, limit=30):
        c = self.conn.cursor()
        c.execute("SELECT * FROM market_data ORDER BY date DESC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def get_active_disasters(self, limit=50):
        c = self.conn.cursor()
        c.execute("SELECT * FROM disaster_warnings ORDER BY severity ASC LIMIT ?", (limit,))
        return [dict(r) for r in c.fetchall()]

    def save_analysis(self, analysis_type, result):
        c = self.conn.cursor()
        c.execute("INSERT INTO analysis_results (analysis_type, result_json, created_at) VALUES (?,?,?)",
                  (analysis_type, json.dumps(result, ensure_ascii=False), datetime.now().isoformat()))
        self.conn.commit()

    def get_recent_analysis(self, analysis_type, limit=1):
        c = self.conn.cursor()
        c.execute("SELECT * FROM analysis_results WHERE analysis_type=? ORDER BY created_at DESC LIMIT ?",
                  (analysis_type, limit))
        results = []
        for r in c.fetchall():
            d = dict(r)
            d["result"] = json.loads(d.get("result_json", "{}"))
            results.append(d["result"])
        return results

    def get_statistics(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM news_articles");
        tn = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM disaster_warnings");
        td = c.fetchone()[0]
        c.execute("SELECT category, COUNT(*) FROM news_articles GROUP BY category")
        cats = {r[0]: r[1] for r in c.fetchall()}
        # 模型分析覆盖统计
        c.execute("SELECT COUNT(*) FROM article_model_results");
        analyzed = c.fetchone()[0]
        return {"total_news": tn, "total_disasters": td, "category_counts": cats, "analyzed_articles": analyzed}

    def clear_demo_data(self):
        """清除所有演示数据，保留真实爬虫数据。注意：不清除 model_results！"""
        c = self.conn.cursor()
        c.execute("DELETE FROM news_articles WHERE source='demo'")
        c.execute("DELETE FROM disaster_warnings WHERE id LIKE 'w%'")
        c.execute("DELETE FROM analysis_results")
        self.conn.commit()
        logger.info("Demo data cleared.")

    def close(self):
        if self._conn: self._conn.close(); self._conn = None
