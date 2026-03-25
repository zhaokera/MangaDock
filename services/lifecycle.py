"""Server lifecycle helpers for browser cleanup scheduling."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from services.state import AppRuntime


BrowserPool = dict[str, dict[str, Any]]
AsyncLifecycleHook = Callable[[], Awaitable[None]]
CleanupBrowserPool = Callable[..., Awaitable[Any]]
CloseAllBrowsers = Callable[..., Awaitable[Any]]
ScheduleBrowserCleanup = Callable[..., Awaitable[Any]]
GetConfig = Callable[[], Any]
LifecycleHooks = tuple[
    AsyncLifecycleHook,
    AsyncLifecycleHook,
    AsyncLifecycleHook,
    AsyncLifecycleHook,
]


def create_server_lifecycle(
    *,
    runtime: AppRuntime,
    browser_pool: BrowserPool,
    browser_pool_lock: asyncio.Lock,
    cleanup_browser_pool: CleanupBrowserPool,
    close_all_browsers: CloseAllBrowsers,
    schedule_browser_cleanup: ScheduleBrowserCleanup,
    get_config: GetConfig,
    logger: logging.Logger,
) -> LifecycleHooks:
    """Create explicit startup and shutdown hooks for the server."""

    async def run_cleanup_browser_pool() -> Any:
        return await cleanup_browser_pool(
            browser_pool=browser_pool,
            browser_pool_lock=browser_pool_lock,
            get_config=get_config,
            logger=logger,
        )

    async def start_browser_cleanup_scheduler() -> None:
        cfg = get_config()
        cleanup_interval = getattr(cfg.crawler, "browser_cleanup_interval", 60)
        runtime.browser_cleanup_task = asyncio.create_task(
            schedule_browser_cleanup(
                interval=cleanup_interval,
                cleanup_browser_pool=run_cleanup_browser_pool,
                logger=logger,
            )
        )
        logger.info(f"浏览器池清理调度器已启动 (interval={cleanup_interval}s)")

    async def stop_browser_cleanup_scheduler() -> None:
        task = runtime.browser_cleanup_task
        if task is None:
            return

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            runtime.browser_cleanup_task = None

    async def on_startup() -> None:
        await start_browser_cleanup_scheduler()

    async def on_shutdown() -> None:
        await close_all_browsers(
            browser_pool=browser_pool,
            browser_pool_lock=browser_pool_lock,
            logger=logger,
        )
        await stop_browser_cleanup_scheduler()

    return (
        start_browser_cleanup_scheduler,
        stop_browser_cleanup_scheduler,
        on_startup,
        on_shutdown,
    )
