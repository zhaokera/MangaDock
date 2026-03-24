from fastapi import FastAPI

import server


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


create_app = server.create_app


def test_create_app_registers_core_routes():
    app = create_app()
    routes = {route.path for route in app.routes}

    assert "/" in routes
    assert "/api/download" in routes
    assert "/api/search" in routes
    assert "/api/parse" in routes
    assert "/api/auth/login" in routes
