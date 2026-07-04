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
    db.clear_demo_data()

    # 如果有新闻但缺少分析结果，自动补齐分析（仅计算，不爬取）
    stats = db.get_statistics()
    analysis = db.get_recent_analysis("trend")
    if stats["total_news"] > 0 and (not analysis or not analysis[0].get("trend")):
        logger.info("检测到新闻数据但缺少分析结果，正在自动生成...")
        run_analysis_on_existing(db)

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