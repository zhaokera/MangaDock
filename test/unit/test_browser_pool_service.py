from types import SimpleNamespace

import pytest

from services.browser_pool import (
    attach_browser_to_crawler,
    cleanup_idle_browsers,
    release_browser_for_platform,
)


def test_attach_browser_to_crawler_sets_runtime_and_increments_usage():
    crawler = SimpleNamespace(browser=None, context=None, page=None, playwright=None, cfg=None)
    browser_info = {
        "browser": "browser",
        "context": "context",
        "page": "page",
        "playwright": "playwright",
        "used_count": 0,
    }
    cfg = object()

    attach_browser_to_crawler(crawler, browser_info, cfg)

    assert crawler.browser == "browser"
    assert crawler.context == "context"
    assert crawler.page == "page"
    assert crawler.playwright == "playwright"
    assert crawler.cfg is cfg
    assert browser_info["used_count"] == 1


@pytest.mark.asyncio
async def test_cleanup_idle_browsers_closes_and_removes_only_expired_idle_entries():
    closed = []

    def close_recorder(name):
        async def _close():
            closed.append(name)
        return _close

    pool = {
        "idle": {
            "used_count": 0,
            "created_at": 0.0,
            "last_used": 0.0,
            "page": SimpleNamespace(close=close_recorder("idle-page")),
            "context": SimpleNamespace(close=close_recorder("idle-context")),
            "browser": SimpleNamespace(close=close_recorder("idle-browser")),
            "playwright": SimpleNamespace(stop=close_recorder("idle-playwright")),
        },
        "busy": {
            "used_count": 1,
            "created_at": 0.0,
            "last_used": 0.0,
            "page": SimpleNamespace(close=close_recorder("busy-page")),
            "context": SimpleNamespace(close=close_recorder("busy-context")),
            "browser": SimpleNamespace(close=close_recorder("busy-browser")),
            "playwright": SimpleNamespace(stop=close_recorder("busy-playwright")),
        },
    }

    closed_platforms = await cleanup_idle_browsers(
        browser_pool=pool,
        idle_timeout=10.0,
        current_time=20.0,
    )

    assert closed_platforms == ["idle"]
    assert list(pool.keys()) == ["busy"]
    assert closed == ["idle-page", "idle-context", "idle-browser", "idle-playwright"]


def test_release_browser_for_platform_decrements_usage_and_updates_last_used():
    pool = {
        "tencent": {
            "used_count": 2,
            "last_used": 1.0,
        }
    }

    release_browser_for_platform(pool, "tencent", current_time=10.0)

    assert pool["tencent"]["used_count"] == 1
    assert pool["tencent"]["last_used"] == 10.0
