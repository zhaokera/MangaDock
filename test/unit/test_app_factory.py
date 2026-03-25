import builtins
import importlib
from pathlib import Path
import runpy
from types import SimpleNamespace

from fastapi import FastAPI
import pytest

import server
import services.bootstrap
import services.lifecycle
import services.runtime
from crawlers import get_crawler as get_crawler_for_url
from crawlers.search import get_searcher, search_all_platforms
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
from services.platforms import list_supported_platforms
from services.runtime import log_startup_summary, run_download_cli, run_search_cli


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
    assert server.run_search_cli is run_search_cli
    assert server.run_download_cli is run_download_cli
    assert server.log_startup_summary is log_startup_summary
    assert server.list_supported_platforms is list_supported_platforms


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


def test_server_configures_logging_before_crawler_imports(monkeypatch):
    original_import = builtins.__import__
    events = []
    state = {"configured": False}

    def fake_configure_server_logging(name):
        state["configured"] = True
        events.append(("configure", name))
        return server.logger

    def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("crawlers"):
            events.append(("crawlers", name, state["configured"]))
        return original_import(name, globals, locals, fromlist, level)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(services.runtime, "configure_server_logging", fake_configure_server_logging)
            patch.setattr(builtins, "__import__", tracking_import)
            importlib.reload(server)
    finally:
        importlib.reload(server)

    crawler_events = [event for event in events if event[0] == "crawlers"]
    assert crawler_events
    assert crawler_events[0][2] is True


create_app = server.create_app


def test_create_app_registers_core_routes():
    app = create_app()
    routes = {route.path for route in app.routes}

    assert "/" in routes
    assert "/api/download" in routes
    assert "/api/search" in routes
    assert "/api/parse" in routes
    assert "/api/auth/login" in routes


def test_server_main_delegates_to_runtime_entrypoint(monkeypatch, tmp_path):
    sentinel_app = object()
    sentinel_config = object()
    sentinel_downloads_dir = tmp_path / "downloads"
    sentinel_runtime = SimpleNamespace(
        tasks={},
        task_last_sse_state={},
        state_lock=object(),
        browser_pool={},
        browser_pool_lock=object(),
        download_queue={},
        download_queue_priority={},
        download_queue_lock=object(),
    )
    captured = {}

    monkeypatch.setattr(
        services.runtime,
        "initialize_server_state",
        lambda **kwargs: (sentinel_config, sentinel_runtime, sentinel_downloads_dir),
    )
    monkeypatch.setattr(
        services.lifecycle,
        "create_server_lifecycle",
        lambda **kwargs: (object(), object(), object(), object()),
    )
    monkeypatch.setattr(
        services.bootstrap,
        "create_server_application",
        lambda **kwargs: sentinel_app,
    )

    def fake_run_entrypoint(**kwargs):
        captured.update(kwargs)
        return 7

    monkeypatch.setattr(services.runtime, "run_entrypoint", fake_run_entrypoint)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "server.py"),
            run_name="__main__",
        )

    assert exc_info.value.code == 7
    assert captured["argv"] is None
    assert captured["app"] is sentinel_app
    assert captured["config"] is sentinel_config
    assert captured["downloads_dir"] == str(sentinel_downloads_dir)
    assert captured["get_searcher"] is get_searcher
    assert captured["search_all_platforms"] is search_all_platforms
    assert captured["get_crawler_for_url"] is get_crawler_for_url
