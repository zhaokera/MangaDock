import logging
from pathlib import Path

from services.bootstrap import create_server_application
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
