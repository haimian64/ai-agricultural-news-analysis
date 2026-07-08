"""Agricultural News Analysis System - Main Entry"""
import logging, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import config
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# main.py 核心修改部分
def main():
    from backend.database import DatabaseManager
    from backend.api import create_app, set_db_manager, refresh_aggregate_analysis

    config.ensure_dirs()
    logger.info("=== Agri News Analysis System ===")

    db = DatabaseManager()
    db.conn
    set_db_manager(db)

    # 清理旧数据库中残留的演示数据（source='demo'）
    db.clear_demo_data()

    stats = db.get_statistics()
    logger.info(f"数据库现有 {stats['total_news']} 条新闻，{stats.get('analyzed_articles', 0)} 条已分析。")
    logger.info("系统已就绪，点击「爬取实时新闻」按钮获取最新农业新闻数据并进行分析。")

    stats = db.get_statistics()
    if stats["total_news"] > 0:
        # 启动时基于已有数据生成聚合分析（不涉及爬取和单条NLP）
        refresh_aggregate_analysis(db)
        logger.info("聚合分析已基于现有数据生成。")
    else:
        logger.info("数据库中没有新闻，请点击「爬取实时新闻」获取数据。")

    # 启动服务器（以下代码不变）
    import socket
    for port in range(8000, 8010):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("0.0.0.0", port))
            s.close()
            break
        except:
            s.close()
    else:
        port = 8000

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