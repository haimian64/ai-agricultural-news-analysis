"""Agricultural News Analysis System - Main Entry"""
import logging, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    from backend.database import DatabaseManager
    from backend.api import create_app, set_db_manager, run_analysis_on_existing

    config.ensure_dirs()
    logger.info("=== Agri News Analysis System ===")

    # Init DB
    db = DatabaseManager()
    db.conn
    set_db_manager(db)

    # 清理旧数据库文件中残留的演示数据（source='demo'）
    # 注意：不会清除 article_model_results（保留已分析结果）
    db.clear_demo_data()

    # 仅对未分析的新闻自动补齐分析（已分析过的跳过，不重复计算）
    stats = db.get_statistics()
    unanalyzed = db.count_unanalyzed_articles()
    if stats["total_news"] > 0 and unanalyzed > 0:
        logger.info(f"检测到 {unanalyzed} 条未分析的新闻，正在自动补齐...")
        run_analysis_on_existing(db)
    elif stats["total_news"] > 0:
        logger.info(f"全部 {stats['total_news']} 条新闻均已分析，跳过。")
    else:
        logger.info("数据库中没有新闻，请点击「爬取实时新闻」获取数据。")

    # 始终从已有数据重新生成聚合分析（趋势/热词/综合报告）
    # 因为 clear_demo_data() 会清空 analysis_results
    if stats["total_news"] > 0:
        from nlp import HotTopicAnalyzer
        from backend.api import get_db
        _db = get_db()
        all_arts = _db.get_all_news(500)
        if all_arts:
            ha = HotTopicAnalyzer()
            trend_data = ha.trend_over_time(all_arts)
            _db.save_analysis("full_analysis", ha.full_analysis(all_arts))
            _db.save_analysis("hot_keywords", {"keywords": ha.extract_keywords(
                [a.get("title", "") for a in all_arts if a.get("title")], 30)})
            _db.save_analysis("trend", {"trend": trend_data})
            logger.info("聚合分析已从已有数据重新生成。")

    logger.info("系统已就绪，点击「爬取实时新闻」按钮获取最新农业新闻数据。")

    # Start server
    import socket
    for port in range(8000, 8010):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try: s.bind(("0.0.0.0", port)); s.close(); break
        except: s.close()
    else: port = 8000

    app = create_app()
    import asyncio
    from aiohttp import web
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    runner = web.AppRunner(app)
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, "0.0.0.0", port)
    loop.run_until_complete(site.start())

    logger.info(f"Server: http://localhost:{port}")
    logger.info(f"Dashboard: http://localhost:{port}/dashboard")
    print(f"\n  >>> http://localhost:{port}/dashboard <<<\n")

    # 自动打开浏览器
    import webbrowser
    try:
        webbrowser.open(f"http://localhost:{port}/dashboard")
    except Exception:
        pass

    print("  >>> 按 Ctrl+C 停止服务器 <<<\n")
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在关闭服务器...")
    finally:
        loop.run_until_complete(runner.cleanup())
        logger.info("服务器已停止。")

if __name__ == "__main__":
    main()