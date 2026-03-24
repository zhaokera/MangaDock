import asyncio
import logging

import pytest

from services.lifecycle import create_server_lifecycle
from services.state import create_runtime


async def _idle_cleanup_loop(*, interval, cleanup_browser_pool, logger):
    while True:
        await asyncio.sleep(3600)


def _config_with_interval(interval: int = 60):
    return type(
        "Cfg",
        (),
        {"crawler": type("CrawlerCfg", (), {"browser_cleanup_interval": interval})()},
    )()


@pytest.mark.asyncio
async def test_start_scheduler_creates_runtime_cleanup_task():
    runtime = create_runtime()
    logger = logging.getLogger("test")

    recorded = {}

    async def recording_cleanup_loop(*, interval, cleanup_browser_pool, logger):
        recorded["interval"] = interval
        recorded["cleanup_browser_pool"] = cleanup_browser_pool
        recorded["logger"] = logger
        while True:
            await asyncio.sleep(3600)

    start_browser_cleanup_scheduler, _, _, _ = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=lambda: None,
        close_all_browsers=lambda **kwargs: None,
        schedule_browser_cleanup=recording_cleanup_loop,
        get_config=lambda: _config_with_interval(12),
        logger=logger,
    )

    await start_browser_cleanup_scheduler()
    await asyncio.sleep(0)

    assert runtime.browser_cleanup_task is not None
    assert recorded["interval"] == 12
    assert callable(recorded["cleanup_browser_pool"])
    assert recorded["logger"] is logger
    runtime.browser_cleanup_task.cancel()


@pytest.mark.asyncio
async def test_on_shutdown_closes_browsers_before_stopping_scheduler():
    runtime = create_runtime()
    logger = logging.getLogger("test")
    calls = []

    async def fake_close_all_browsers(**kwargs):
        calls.append("close")

    (
        start_browser_cleanup_scheduler,
        _stop_browser_cleanup_scheduler,
        _on_startup,
        on_shutdown,
    ) = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=lambda: None,
        close_all_browsers=fake_close_all_browsers,
        schedule_browser_cleanup=_idle_cleanup_loop,
        get_config=lambda: _config_with_interval(),
        logger=logger,
    )

    await start_browser_cleanup_scheduler()

    original_task = runtime.browser_cleanup_task
    assert original_task is not None
    original_cancel = original_task.cancel

    def wrapped_cancel():
        calls.append("stop")
        return original_cancel()

    original_task.cancel = wrapped_cancel
    await on_shutdown()

    assert calls == ["close", "stop"]
    assert runtime.browser_cleanup_task is None
