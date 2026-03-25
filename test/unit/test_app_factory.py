import importlib

from fastapi import FastAPI

import server
import services.lifecycle
from routes.auth import build_auth_router
from routes.downloads import build_download_router
from routes.history import build_history_router
from routes.parse import build_parse_router
from routes.platforms import router as platforms_router
from routes.queue import build_queue_router
from routes.resume import build_resume_router
from routes.search import build_search_router
from services.app_factory import create_application
from services.downloader import MangaDownloader


def test_create_app_delegates_to_bootstrap_with_runtime_dependencies(monkeypatch):
    sentinel_app = FastAPI()
    captured = {}

    def fake_create_server_application(**kwargs):
        captured.update(kwargs)
        return sentinel_app

    monkeypatch.setattr(server, "create_server_application", fake_create_server_application)

    app = server.create_app()

    assert app is sentinel_app
    assert captured["runtime"] is server.runtime
    assert captured["logger"] is server.logger
    assert captured["downloads_dir"] == server.DOWNLOADS_DIR
    assert captured["get_config"] is server.config.get_config
    assert captured["get_task_record"] is server.get_task
    assert captured["save_task_record"] is server.save_task
    assert captured["delete_task_record"] is server.delete_task
    assert captured["delete_history_tasks"] is server.delete_history_tasks
    assert captured["get_history_tasks"] is server.get_history_tasks
    assert captured["get_total_count"] is server.get_total_count
    assert captured["get_crawler_for_url"] is server.get_crawler
    assert captured["get_searcher"] is server.get_searcher
    assert captured["search_all_platforms"] is server.search_all_platforms
    assert captured["get_manga_searcher"] is server.get_manga_searcher
    assert captured["get_auth_manager"] is server.get_auth_manager
    assert captured["get_resume_manager"] is server.get_resume_manager
    assert captured["get_crawler_by_platform"] is server.get_crawler_by_platform
    assert captured["init_browser_for_crawler"] is server.init_browser_for_crawler
    assert captured["release_browser_for_platform"] is server.release_browser_for_platform
    assert captured["add_history_item"] is server.add_history_item
    assert captured["create_download_task"] is server.DownloadTask
    assert captured["on_startup"] is server.on_startup
    assert captured["on_shutdown"] is server.on_shutdown


def test_server_preserves_assembly_compatibility_exports():
    assert server.build_auth_router is build_auth_router
    assert server.build_download_router is build_download_router
    assert server.build_history_router is build_history_router
    assert server.build_parse_router is build_parse_router
    assert server.platforms_router is platforms_router
    assert server.build_queue_router is build_queue_router
    assert server.build_resume_router is build_resume_router
    assert server.build_search_router is build_search_router
    assert server.create_application is create_application
    assert server.MangaDownloader is MangaDownloader


def test_server_lifecycle_exports_are_bound_from_lifecycle_factory(monkeypatch):
    sentinel_start = object()
    sentinel_stop = object()
    sentinel_on_startup = object()
    sentinel_on_shutdown = object()
    captured = {}

    def fake_create_server_lifecycle(**kwargs):
        captured.update(kwargs)
        return (
            sentinel_start,
            sentinel_stop,
            sentinel_on_startup,
            sentinel_on_shutdown,
        )

    try:
        with monkeypatch.context() as lifecycle_patch:
            lifecycle_patch.setattr(
                services.lifecycle,
                "create_server_lifecycle",
                fake_create_server_lifecycle,
            )

            reloaded_server = importlib.reload(server)
        assert reloaded_server.start_browser_cleanup_scheduler is sentinel_start
        assert reloaded_server.stop_browser_cleanup_scheduler is sentinel_stop
        assert reloaded_server.on_startup is sentinel_on_startup
        assert reloaded_server.on_shutdown is sentinel_on_shutdown
        assert captured["runtime"] is reloaded_server.runtime
        assert captured["browser_pool"] is reloaded_server._browser_pool
        assert captured["browser_pool_lock"] is reloaded_server._browser_pool_lock
        assert captured["cleanup_browser_pool"] is reloaded_server.cleanup_browser_pool
        assert captured["close_all_browsers"] is reloaded_server.close_all_browsers
        assert captured["schedule_browser_cleanup"] is reloaded_server.schedule_browser_cleanup
        assert captured["get_config"] is reloaded_server.config.get_config
        assert captured["logger"] is reloaded_server.logger
    finally:
        importlib.reload(server)


create_app = server.create_app


def test_create_app_registers_core_routes():
    app = create_app()
    routes = {route.path for route in app.routes}

    assert "/" in routes
    assert "/api/download" in routes
    assert "/api/search" in routes
    assert "/api/parse" in routes
    assert "/api/auth/login" in routes
