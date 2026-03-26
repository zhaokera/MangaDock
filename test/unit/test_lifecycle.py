import asyncio
import contextlib
import logging
from typing import Any, Awaitable, Callable, get_type_hints

import pytest

from services.lifecycle import build_server_lifecycle_kwargs
from services.lifecycle import create_server_lifecycle
from services.state import AppRuntime, create_runtime


async def _idle_cleanup_loop(*, interval, cleanup_browser_pool, logger):
    while True:
        await asyncio.sleep(3600)


def _config_with_interval(interval: int = 60):
    return type(
        "Cfg",
        (),
        {"crawler": type("CrawlerCfg", (), {"browser_cleanup_interval": interval})()},
    )()


def test_create_server_lifecycle_public_signature_is_typed():
    hints = get_type_hints(create_server_lifecycle)
    builder_hints = get_type_hints(build_server_lifecycle_kwargs)

    assert hints["runtime"] is AppRuntime
    assert hints["browser_pool"] == dict[str, dict]
    assert hints["browser_pool_lock"] is asyncio.Lock
    assert hints["cleanup_browser_pool"] == Callable[..., Awaitable[Any]]
    assert hints["close_all_browsers"] == Callable[..., Awaitable[Any]]
    assert hints["schedule_browser_cleanup"] == Callable[..., Awaitable[Any]]
    assert hints["get_config"] == Callable[[], Any]
    assert hints["logger"] is logging.Logger
    assert hints["return"] == tuple[
        Callable[[], Awaitable[None]],
        Callable[[], Awaitable[None]],
        Callable[[], Awaitable[None]],
        Callable[[], Awaitable[None]],
    ]
    assert builder_hints["runtime"] is AppRuntime
    assert builder_hints["browser_pool"] == dict[str, dict]
    assert builder_hints["browser_pool_lock"] is asyncio.Lock
    assert builder_hints["logger"] is logging.Logger
    assert builder_hints["return"] is build_server_lifecycle_kwargs.__globals__["ServerLifecycleKwargs"]


def test_build_server_lifecycle_kwargs_preserves_dependency_mapping():
    runtime = create_runtime()
    logger = logging.getLogger("test")

    async def cleanup_browser_pool(**kwargs):
        return None

    async def close_all_browsers(**kwargs):
        return None

    async def schedule_browser_cleanup(**kwargs):
        return None

    def get_config():
        return _config_with_interval()

    kwargs = build_server_lifecycle_kwargs(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=cleanup_browser_pool,
        close_all_browsers=close_all_browsers,
        schedule_browser_cleanup=schedule_browser_cleanup,
        get_config=get_config,
        logger=logger,
    )

    assert kwargs["runtime"] is runtime
    assert kwargs["browser_pool"] is runtime.browser_pool
    assert kwargs["browser_pool_lock"] is runtime.browser_pool_lock
    assert kwargs["cleanup_browser_pool"] is cleanup_browser_pool
    assert kwargs["close_all_browsers"] is close_all_browsers
    assert kwargs["schedule_browser_cleanup"] is schedule_browser_cleanup
    assert kwargs["get_config"] is get_config
    assert kwargs["logger"] is logger


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
    with contextlib.suppress(asyncio.CancelledError):
        await runtime.browser_cleanup_task
    assert runtime.browser_cleanup_task.cancelled() or runtime.browser_cleanup_task.done()


@pytest.mark.asyncio
async def test_on_startup_starts_browser_cleanup_scheduler():
    runtime = create_runtime()
    logger = logging.getLogger("test")
    get_config = lambda: _config_with_interval(12)

    recorded = {}

    async def recording_cleanup_loop(*, interval, cleanup_browser_pool, logger):
        recorded["interval"] = interval
        recorded["cleanup_browser_pool"] = cleanup_browser_pool
        recorded["logger"] = logger
        while True:
            await asyncio.sleep(3600)

    async def recording_cleanup_browser_pool(*, browser_pool, browser_pool_lock, get_config, logger):
        recorded["browser_pool"] = browser_pool
        recorded["browser_pool_lock"] = browser_pool_lock
        recorded["get_config"] = get_config
        recorded["cleanup_logger"] = logger

    _start_browser_cleanup_scheduler, _stop_browser_cleanup_scheduler, on_startup, _on_shutdown = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=recording_cleanup_browser_pool,
        close_all_browsers=lambda **kwargs: None,
        schedule_browser_cleanup=recording_cleanup_loop,
        get_config=get_config,
        logger=logger,
    )

    await on_startup()
    await asyncio.sleep(0)

    assert runtime.browser_cleanup_task is not None
    assert recorded["interval"] == 12
    assert callable(recorded["cleanup_browser_pool"])
    assert recorded["logger"] is logger
    cleanup_result = recorded["cleanup_browser_pool"]()
    if asyncio.iscoroutine(cleanup_result):
        await cleanup_result
    assert recorded["browser_pool"] is runtime.browser_pool
    assert recorded["browser_pool_lock"] is runtime.browser_pool_lock
    assert recorded["get_config"] is get_config
    assert recorded["cleanup_logger"] is logger
    runtime.browser_cleanup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await runtime.browser_cleanup_task


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
