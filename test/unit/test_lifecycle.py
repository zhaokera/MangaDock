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
    get_config = lambda: _config_with_interval(12)

    recorded = {}
    cleanup_calls = {}

    async def recording_cleanup_loop(*, interval, cleanup_browser_pool, logger):
        recorded["interval"] = interval
        recorded["cleanup_browser_pool"] = cleanup_browser_pool
        recorded["logger"] = logger
        while True:
            await asyncio.sleep(3600)

    async def recording_cleanup_browser_pool(*, browser_pool, browser_pool_lock, get_config, logger):
        cleanup_calls["browser_pool"] = browser_pool
        cleanup_calls["browser_pool_lock"] = browser_pool_lock
        cleanup_calls["get_config"] = get_config
        cleanup_calls["logger"] = logger

    start_browser_cleanup_scheduler, _, _, _ = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=recording_cleanup_browser_pool,
        close_all_browsers=lambda **kwargs: None,
        schedule_browser_cleanup=recording_cleanup_loop,
        get_config=get_config,
        logger=logger,
    )

    await start_browser_cleanup_scheduler()
    await asyncio.sleep(0)

    assert runtime.browser_cleanup_task is not None
    assert recorded["interval"] == 12
    assert callable(recorded["cleanup_browser_pool"])
    assert recorded["logger"] is logger
    cleanup_result = recorded["cleanup_browser_pool"]()
    if asyncio.iscoroutine(cleanup_result):
        await cleanup_result
    assert cleanup_calls["browser_pool"] is runtime.browser_pool
    assert cleanup_calls["browser_pool_lock"] is runtime.browser_pool_lock
    assert cleanup_calls["get_config"] is get_config
    assert cleanup_calls["logger"] is logger
    runtime.browser_cleanup_task.cancel()


@pytest.mark.asyncio
async def test_stop_browser_cleanup_scheduler_clears_runtime_task_reference():
    runtime = create_runtime()
    logger = logging.getLogger("test")
    get_config = lambda: _config_with_interval()

    (
        start_browser_cleanup_scheduler,
        stop_browser_cleanup_scheduler,
        _on_startup,
        _on_shutdown,
    ) = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=lambda: None,
        close_all_browsers=lambda **kwargs: None,
        schedule_browser_cleanup=_idle_cleanup_loop,
        get_config=get_config,
        logger=logger,
    )

    await start_browser_cleanup_scheduler()

    original_task = runtime.browser_cleanup_task
    assert original_task is not None

    await stop_browser_cleanup_scheduler()

    await asyncio.sleep(0)
    assert runtime.browser_cleanup_task is None
    assert original_task.cancelled() or original_task.done()


@pytest.mark.asyncio
async def test_on_shutdown_closes_browsers_before_stopping_scheduler():
    runtime = create_runtime()
    logger = logging.getLogger("test")
    calls = []
    close_kwargs = {}

    async def fake_close_all_browsers(**kwargs):
        close_kwargs.update(kwargs)
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
    assert close_kwargs["browser_pool"] is runtime.browser_pool
    assert close_kwargs["browser_pool_lock"] is runtime.browser_pool_lock
    assert close_kwargs["logger"] is logger
    assert runtime.browser_cleanup_task is None
