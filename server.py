#!/usr/bin/env python3
"""
漫画下载 Web 服务
FastAPI 后端 + SSE 进度推送
支持多平台漫画下载
"""

import asyncio
import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
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
from services.browser_pool import (
    cleanup_browser_pool,
    close_all_browsers,
    init_browser_for_crawler,
    release_browser_for_platform,
    schedule_browser_cleanup,
)
from services.downloader import MangaDownloader, add_history_item
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

def _history_max_items() -> int:
    value = config.get_config().history.max_items
    return value if value > 0 else 100


def _get_crawler_for_url(url: str):
    return get_crawler(url)


def _get_searcher_for_platform(platform: str):
    return get_searcher(platform)


def _search_all_platforms(keyword: str, limit: int):
    return search_all_platforms(keyword, limit_per_platform=limit)


def _get_manga_searcher_for_platform(platform: str):
    return get_manga_searcher(platform)


def _get_auth_manager_instance():
    return get_auth_manager()


def _get_resume_manager_instance():
    return get_resume_manager()


def _get_crawler_by_platform_name(platform: str):
    return get_crawler_by_platform(platform)


async def _bind_crawler_browser(crawler, platform: str) -> None:
    await init_browser_for_crawler(
        crawler=crawler,
        platform=platform,
        browser_pool=_browser_pool,
        browser_pool_lock=_browser_pool_lock,
        get_config=config.get_config,
        logger=logger,
    )


def _release_platform_browser(platform: str) -> None:
    release_browser_for_platform(
        _browser_pool,
        platform,
        asyncio.get_running_loop().time(),
    )


async def _add_history_record(history_item: dict) -> bool:
    return await add_history_item(
        history_item,
        state_lock=_state_lock,
        get_task_record=get_task,
        save_task_record=save_task,
        get_total_completed_count=lambda: get_total_count(status="completed"),
        get_history_tasks=lambda limit: get_history_tasks(limit=limit),
        delete_task_record=delete_task,
        get_history_max_items=_history_max_items,
    )


def _build_downloader(task: DownloadTask) -> MangaDownloader:
    return MangaDownloader(
        task,
        downloads_dir=DOWNLOADS_DIR,
        get_crawler_for_url=_get_crawler_for_url,
        init_browser_for_crawler=_bind_crawler_browser,
        release_browser_for_platform=_release_platform_browser,
        save_task_record=save_task,
        add_history_item=_add_history_record,
        task_last_sse_state=task_last_sse_state,
        tasks=tasks,
    )


def _register_root_route(app: FastAPI) -> None:
    @app.get("/")
    async def root():
        return {
            "message": "漫画下载器 API",
            "version": "2.0",
            "description": "支持多平台漫画下载",
        }


def _register_routes(app: FastAPI) -> None:
    app.include_router(platforms_router)
    app.include_router(
        build_download_router(
            get_crawler_for_url=_get_crawler_for_url,
            create_download_task=lambda task_id, url, platform: DownloadTask(task_id, url, platform),
            create_downloader=_build_downloader,
            get_task_record=get_task,
            task_last_sse_state=task_last_sse_state,
            get_heartbeat_interval=lambda: config.get_config().sse.heartbeat_interval,
        )
    )
    app.include_router(
        build_history_router(
            get_history_tasks=lambda limit: get_history_tasks(limit=limit),
            get_history_max_items=_history_max_items,
            get_task_record=get_task,
            delete_task_record=delete_task,
            delete_history_tasks=delete_history_tasks,
        )
    )
    app.include_router(
        build_queue_router(
            download_queue=_download_queue,
            priorities=_download_queue_priority,
            queue_lock=_download_queue_lock,
        )
    )
    app.include_router(
        build_search_router(
            search_all_platforms=_search_all_platforms,
            get_searcher=_get_searcher_for_platform,
            get_manga_searcher=_get_manga_searcher_for_platform,
        )
    )
    app.include_router(
        build_parse_router(
            get_crawler_for_url=_get_crawler_for_url,
        )
    )
    app.include_router(
        build_auth_router(
            get_auth_manager=_get_auth_manager_instance,
            get_crawler_by_platform=_get_crawler_by_platform_name,
        )
    )
    app.include_router(
        build_resume_router(
            get_resume_manager=_get_resume_manager_instance,
        )
    )
    _register_root_route(app)


# ============== 启动 ==============
async def start_browser_cleanup_scheduler():
    """启动浏览器池清理调度器（后台任务）"""
    # 从配置获取清理间隔，默认 60 秒
    cfg = config.get_config()
    cleanup_interval = getattr(cfg.crawler, 'browser_cleanup_interval', 60)

    runtime.browser_cleanup_task = asyncio.create_task(
        schedule_browser_cleanup(
            interval=cleanup_interval,
            cleanup_browser_pool=lambda: cleanup_browser_pool(
                browser_pool=_browser_pool,
                browser_pool_lock=_browser_pool_lock,
                get_config=config.get_config,
                logger=logger,
            ),
            logger=logger,
        )
    )
    logger.info(f"浏览器池清理调度器已启动 (interval={cleanup_interval}s)")


async def stop_browser_cleanup_scheduler():
    """停止浏览器池清理调度器"""
    if runtime.browser_cleanup_task:
        runtime.browser_cleanup_task.cancel()
        try:
            await runtime.browser_cleanup_task
        except asyncio.CancelledError:
            pass
        runtime.browser_cleanup_task = None


async def on_startup():
    """应用启动时的初始化"""
    await start_browser_cleanup_scheduler()


async def on_shutdown():
    """应用关闭时的清理"""
    await close_all_browsers(
        browser_pool=_browser_pool,
        browser_pool_lock=_browser_pool_lock,
        logger=logger,
    )

    # 停止清理调度器
    await stop_browser_cleanup_scheduler()


def _register_lifecycle(app: FastAPI) -> None:
    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def create_app() -> FastAPI:
    app = FastAPI(title="漫画下载器", description="支持多平台的漫画下载服务")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _register_routes(app)
    _register_lifecycle(app)
    return app


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
