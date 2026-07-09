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
    from backend.api import create_app, set_db_manager, refresh_aggregate_analysis, sync_disaster_and_market_from_news

    config.ensure_dirs()
    logger.info("=== Agri News Analysis System ===")

    db = DatabaseManager()
    db.conn
    set_db_manager(db)

    db.clear_demo_data()

    stats = db.get_statistics()
    if stats["total_news"] > 0:
        # 启动时基于已有数据生成聚合分析
        refresh_aggregate_analysis(db)
        # 同步灾害预警和市场数据
        sync_disaster_and_market_from_news(db)
        # AI 灾害信息提取（可选，首次加载模型需数秒）
        if config.DISASTER_EXTRACTION_ENABLED:
            try:
                from backend.disaster_extraction import extract_disaster_info_from_ai
                extract_result = extract_disaster_info_from_ai(db)
                logger.info(f"AI 灾害提取完成: {extract_result}")
            except Exception as e:
                logger.error(f"AI 灾害提取失败 (非致命): {e}")
        logger.info("聚合分析和数据同步已完成。")
    else:
        logger.info("数据库中没有新闻，请点击「爬取实时新闻」获取数据。")

    # 启动 Gradio 聊天机器人在后台线程
    if config.CHATBOT_ENABLED:
        import threading
        from backend.chatbot import create_chatbot_app
        chatbot_app = create_chatbot_app(db)
        def _run_gradio():
            chatbot_app.launch(
                server_name="0.0.0.0",
                server_port=config.GRADIO_PORT,
                prevent_thread_lock=False,
                share=False,
                show_error=True,
                quiet=True,
            )
        gradio_thread = threading.Thread(target=_run_gradio, daemon=True)
        gradio_thread.start()
        # 等待 Gradio 绑定端口
        time.sleep(2)
        logger.info(f"AI 助手 (Gradio): http://localhost:{config.GRADIO_PORT}")

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
        # 释放聊天机器人模型显存
        try:
            from backend.chatbot import unload_chatbot_model
            unload_chatbot_model()
        except Exception:
            pass
        logger.info("服务器已停止。")

if __name__ == "__main__":
    main()