import logging
from pathlib import Path
from typing import Any, Callable, Optional, get_type_hints

from fastapi import FastAPI

import services.bootstrap as bootstrap
from crawlers import BaseCrawler, TaskRecord
from crawlers.auth import AuthManager
from crawlers.manga_search import BaseMangaSearcher
from crawlers.resume import ResumeManager
from crawlers.search import BaseSearcher
from services.bootstrap import create_server_application
from services.state import AppRuntime
from services.state import create_runtime


def test_create_server_application_registers_core_routes():
    runtime = create_runtime()
    app = create_server_application(
        runtime=runtime,
        logger=logging.getLogger("test"),
        downloads_dir=Path("downloads"),
        get_config=lambda: type(
            "Cfg",
            (),
            {
                "history": type("HistoryCfg", (), {"max_items": 100})(),
                "sse": type("SseCfg", (), {"heartbeat_interval": 1.0})(),
            },
        )(),
        get_task_record=lambda task_id: None,
        save_task_record=lambda *args, **kwargs: None,
        delete_task_record=lambda task_id: None,
        delete_history_tasks=lambda: 0,
        get_history_tasks=lambda limit: [],
        get_total_count=lambda status=None: 0,
        get_crawler_for_url=lambda url: type("Crawler", (), {"PLATFORM_NAME": "dummy"})(),
        get_searcher=lambda platform: None,
        search_all_platforms=lambda keyword, limit_per_platform: [],
        get_manga_searcher=lambda platform: None,
        get_auth_manager=lambda: None,
        get_resume_manager=lambda: None,
        get_crawler_by_platform=lambda platform: None,
        init_browser_for_crawler=lambda **kwargs: None,
        release_browser_for_platform=lambda *args, **kwargs: None,
        add_history_item=lambda *args, **kwargs: True,
        create_download_task=lambda task_id, url, platform: None,
        on_startup=lambda: None,
        on_shutdown=lambda: None,
    )

    routes = {route.path for route in app.routes}
    assert "/" in routes
    assert "/api/download" in routes
    assert "/api/history" in routes
    assert "/api/queue" in routes
    assert "/api/search" in routes
    assert "/api/parse" in routes
    assert "/api/platforms" in routes
    assert "/api/auth/login" in routes
    assert "/api/auth/platforms" in routes
    assert "/api/resume/list" in routes


def test_create_server_application_public_signature_stays_lightweight():
    hints = get_type_hints(bootstrap.create_server_application)

    assert hints["runtime"] is AppRuntime
    assert hints["logger"] is logging.Logger
    assert hints["downloads_dir"] is Path
    assert hints["get_task_record"] == Callable[[str], Optional[TaskRecord]]
    assert hints["delete_task_record"] == Callable[[str], bool]
    assert hints["get_total_count"] == Callable[..., int]
    assert hints["get_crawler_for_url"] == Callable[[str], BaseCrawler]
    assert hints["get_searcher"] == Callable[[str], Optional[BaseSearcher]]
    assert hints["get_manga_searcher"] == Callable[[str], Optional[BaseMangaSearcher]]
    assert hints["get_auth_manager"] == Callable[[], AuthManager]
    assert hints["get_resume_manager"] == Callable[[], ResumeManager]
    assert hints["get_crawler_by_platform"] == Callable[[str], Optional[BaseCrawler]]
    assert hints["create_download_task"] == Callable[[str, str, str], Any]
    assert hints["on_startup"] == Callable[[], Any]
    assert hints["on_shutdown"] == Callable[[], Any]
    assert hints["return"] is FastAPI
