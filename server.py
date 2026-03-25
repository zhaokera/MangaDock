#!/usr/bin/env python3
"""
漫画下载 Web 服务
FastAPI 后端 + SSE 进度推送
支持多平台漫画下载
"""

import asyncio
import logging
from pathlib import Path

try:
    from fastapi import FastAPI
except ImportError:
    print("请先安装 fastapi: pip install fastapi uvicorn")
    exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 获取所有相关 logger
logger = logging.getLogger(__name__)
logging.getLogger("crawlers").setLevel(logging.INFO)
logging.getLogger("crawlers.tencent").setLevel(logging.INFO)
logging.getLogger("crawlers.iqiyi").setLevel(logging.INFO)

# 导入爬虫模块
from crawlers import (
    get_crawler,
    init_db,
    get_task,
    save_task,
    delete_task,
    delete_history_tasks,
    get_history_tasks,
    get_total_count,
)
from crawlers.auth import get_auth_manager
from crawlers.resume import get_resume_manager
from crawlers.search import search_all_platforms, get_searcher
from crawlers.manga_search import get_manga_searcher
from crawlers.registry import get_crawler_by_platform
from routes.auth import build_auth_router
from routes.downloads import build_download_router
from routes.history import build_history_router
from routes.parse import build_parse_router
from routes.platforms import router as platforms_router
from routes.queue import build_queue_router
from routes.resume import build_resume_router
from routes.search import build_search_router
from services.app_factory import create_application
from services.browser_pool import (
    cleanup_browser_pool,
    close_all_browsers,
    init_browser_for_crawler,
    release_browser_for_platform,
    schedule_browser_cleanup,
)
from services.bootstrap import create_server_application
from services.downloader import MangaDownloader, add_history_item
from services.lifecycle import create_server_lifecycle
from services.state import AppRuntime, DownloadTask, create_runtime
from services.runtime import log_startup_summary, run_download_cli, run_search_cli
from services.platforms import list_supported_platforms

# 导入配置管理
import config

# 加载配置
CONFIG = config.get_config()


# ============== 全局状态 ==============

runtime = create_runtime()

# 兼容现有测试与调用方的模块级状态别名
tasks = runtime.tasks
task_last_sse_state = runtime.task_last_sse_state
_state_lock = runtime.state_lock
_browser_pool = runtime.browser_pool
_browser_pool_lock = runtime.browser_pool_lock
_download_queue = runtime.download_queue
_download_queue_priority = runtime.download_queue_priority
_download_queue_lock = runtime.download_queue_lock

# 初始化数据库
init_db()

# 下载目录（从配置获取）
DOWNLOADS_DIR = Path(CONFIG.download.output_dir)
DOWNLOADS_DIR.mkdir(exist_ok=True)


(
    start_browser_cleanup_scheduler,
    stop_browser_cleanup_scheduler,
    on_startup,
    on_shutdown,
) = create_server_lifecycle(
    runtime=runtime,
    browser_pool=_browser_pool,
    browser_pool_lock=_browser_pool_lock,
    cleanup_browser_pool=cleanup_browser_pool,
    close_all_browsers=close_all_browsers,
    schedule_browser_cleanup=schedule_browser_cleanup,
    get_config=config.get_config,
    logger=logger,
)


def create_app() -> FastAPI:
    return create_server_application(
        runtime=runtime,
        logger=logger,
        downloads_dir=DOWNLOADS_DIR,
        get_config=config.get_config,
        get_task_record=get_task,
        save_task_record=save_task,
        delete_task_record=delete_task,
        delete_history_tasks=delete_history_tasks,
        get_history_tasks=get_history_tasks,
        get_total_count=get_total_count,
        get_crawler_for_url=get_crawler,
        get_searcher=get_searcher,
        search_all_platforms=search_all_platforms,
        get_manga_searcher=get_manga_searcher,
        get_auth_manager=get_auth_manager,
        get_resume_manager=get_resume_manager,
        get_crawler_by_platform=get_crawler_by_platform,
        init_browser_for_crawler=init_browser_for_crawler,
        release_browser_for_platform=release_browser_for_platform,
        add_history_item=add_history_item,
        create_download_task=DownloadTask,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )


app = create_app()


# ============== 启动 ==============

if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="漫画下载器")
    parser.add_argument("--search", "-s", help="搜索视频（按名称）")
    parser.add_argument("--platform", "-p", help="搜索平台（tencent/iqiyi/youku/mango）")
    parser.add_argument("--limit", "-l", type=int, default=10, help="搜索结果数量")
    parser.add_argument("--download", "-d", help="下载视频（通过 URL）")
    args = parser.parse_args()

    if args.search:
        raise SystemExit(
            asyncio.run(
                run_search_cli(
                    keyword=args.search,
                    platform=args.platform,
                    limit=args.limit,
                    get_searcher=get_searcher,
                    search_all_platforms=search_all_platforms,
                )
            )
        )

    if args.download:
        raise SystemExit(
            asyncio.run(
                run_download_cli(
                    url=args.download,
                    downloads_dir=str(DOWNLOADS_DIR),
                    get_crawler_for_url=get_crawler,
                )
            )
        )

    log_startup_summary(
        logger=logger,
        config=CONFIG,
        platforms=list_supported_platforms(),
    )

    # 启动配置监听器（热重载）
    import config as server_config
    server_config.start_config_watcher(
        callback=lambda: logger.info("配置已热重载"),
        interval=5.0
    )
    logger.info("配置热重载已启用")

    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port)
