#!/usr/bin/env python3
"""
漫画下载 Web 服务
FastAPI 后端 + SSE 进度推送
支持多平台漫画下载
"""

import logging

try:
    from fastapi import FastAPI
except ImportError:
    print("请先安装 fastapi: pip install fastapi uvicorn")
    exit(1)

from services.runtime import (
    build_server_entrypoint_kwargs,
    build_runtime_aliases,
    configure_server_logging,
    initialize_server_state,
    log_startup_summary,
    prepare_server_environment,
    run_download_cli,
    run_entrypoint,
    run_search_cli,
)

logger = configure_server_logging(__name__)

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
from services.bootstrap import build_server_application_kwargs
from services.downloader import MangaDownloader, add_history_item
from services.lifecycle import build_server_lifecycle_kwargs
from services.lifecycle import create_server_lifecycle
from services.state import AppRuntime, DownloadTask, create_runtime
from services.platforms import list_supported_platforms

# 导入配置管理
import config

# ============== 全局状态 ==============

CONFIG, runtime, DOWNLOADS_DIR = initialize_server_state(
    get_config=config.get_config,
    create_runtime_fn=create_runtime,
)

# 兼容现有测试与调用方的模块级状态别名
globals().update(build_runtime_aliases(runtime))

prepare_server_environment(
    init_db_fn=init_db,
    downloads_dir=DOWNLOADS_DIR,
)


(
    start_browser_cleanup_scheduler,
    stop_browser_cleanup_scheduler,
    on_startup,
    on_shutdown,
) = create_server_lifecycle(
    **build_server_lifecycle_kwargs(
        runtime=runtime,
        browser_pool=_browser_pool,
        browser_pool_lock=_browser_pool_lock,
        cleanup_browser_pool=cleanup_browser_pool,
        close_all_browsers=close_all_browsers,
        schedule_browser_cleanup=schedule_browser_cleanup,
        get_config=config.get_config,
        logger=logger,
    )
)


def create_app() -> FastAPI:
    return create_server_application(**build_server_application_kwargs(
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
    ))


app = create_app()


# ============== 启动 ==============

if __name__ == "__main__":
    exit_code = run_entrypoint(**build_server_entrypoint_kwargs(
        app=app,
        logger=logger,
        config=CONFIG,
        downloads_dir=str(DOWNLOADS_DIR),
        get_searcher=get_searcher,
        search_all_platforms=search_all_platforms,
        get_crawler_for_url=get_crawler,
    ))
    if exit_code is not None:
        raise SystemExit(exit_code)
