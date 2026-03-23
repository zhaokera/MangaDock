"""浏览器池运行时服务。"""

from __future__ import annotations

import asyncio
from typing import Any, Callable


BrowserInfo = dict[str, Any]


def attach_browser_to_crawler(crawler: Any, browser_info: BrowserInfo, cfg: Any) -> None:
    """将浏览器实例挂到爬虫，并更新使用计数。"""
    crawler.browser = browser_info["browser"]
    crawler.context = browser_info["context"]
    crawler.page = browser_info["page"]
    crawler.playwright = browser_info["playwright"]
    crawler.cfg = cfg
    browser_info["used_count"] += 1


def release_browser_for_platform(browser_pool: dict[str, BrowserInfo], platform: str, current_time: float) -> None:
    """释放平台浏览器的占用计数。"""
    browser_info = browser_pool.get(platform)
    if browser_info is None:
        return

    browser_info["used_count"] = max(0, browser_info["used_count"] - 1)
    browser_info["last_used"] = current_time


async def close_browser_info(browser_info: BrowserInfo) -> None:
    """关闭单个平台的浏览器资源。"""
    if browser_info.get("page"):
        await browser_info["page"].close()
    if browser_info.get("context"):
        await browser_info["context"].close()
    if browser_info.get("browser"):
        await browser_info["browser"].close()
    if browser_info.get("playwright"):
        await browser_info["playwright"].stop()


async def cleanup_idle_browsers(
    *,
    browser_pool: dict[str, BrowserInfo],
    idle_timeout: float,
    current_time: float,
    logger: Any = None,
) -> list[str]:
    """关闭并移除已超时的空闲浏览器。"""
    closed_platforms: list[str] = []

    for platform, browser_info in list(browser_pool.items()):
        if browser_info["used_count"] > 0:
            continue

        last_used = browser_info.get("last_used", browser_info["created_at"])
        idle_time = current_time - last_used
        if idle_time <= idle_timeout:
            continue

        try:
            if logger:
                logger.info(f"清理空闲浏览器 [平台: {platform}, 空闲时间: {idle_time:.1f}s]")
            await close_browser_info(browser_info)
            del browser_pool[platform]
            closed_platforms.append(platform)
        except Exception as exc:
            if logger:
                logger.error(f"清理平台 {platform} 浏览器失败: {exc}")

    return closed_platforms


async def get_browser_for_platform(
    *,
    platform: str,
    browser_pool: dict[str, BrowserInfo],
    browser_pool_lock: asyncio.Lock,
    get_config: Callable[[], Any],
    logger: Any,
) -> BrowserInfo:
    """获取或创建平台浏览器实例。"""
    from playwright.async_api import async_playwright

    async with browser_pool_lock:
        if platform in browser_pool:
            browser_pool[platform]["last_used"] = asyncio.get_running_loop().time()
            return browser_pool[platform]

        cfg = get_config()
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            channel="chrome",
            args=cfg.crawler.browser_args,
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=cfg.crawler.user_agent
            or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        )
        page = await context.new_page()

        current_time = asyncio.get_running_loop().time()
        browser_info = {
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
            "platform": platform,
            "used_count": 0,
            "created_at": current_time,
            "last_used": current_time,
        }
        browser_pool[platform] = browser_info
        logger.info(f"为平台 {platform} 创建新浏览器实例")
        return browser_info


async def init_browser_for_crawler(
    *,
    crawler: Any,
    platform: str,
    browser_pool: dict[str, BrowserInfo],
    browser_pool_lock: asyncio.Lock,
    get_config: Callable[[], Any],
    logger: Any,
) -> None:
    """为爬虫绑定浏览器实例。"""
    browser_info = await get_browser_for_platform(
        platform=platform,
        browser_pool=browser_pool,
        browser_pool_lock=browser_pool_lock,
        get_config=get_config,
        logger=logger,
    )
    attach_browser_to_crawler(crawler, browser_info, get_config())


async def cleanup_browser_pool(
    *,
    browser_pool: dict[str, BrowserInfo],
    browser_pool_lock: asyncio.Lock,
    get_config: Callable[[], Any],
    logger: Any,
) -> list[str]:
    """按配置清理空闲浏览器。"""
    async with browser_pool_lock:
        idle_timeout = getattr(get_config().crawler, "browser_idle_timeout", 300)
        return await cleanup_idle_browsers(
            browser_pool=browser_pool,
            idle_timeout=idle_timeout,
            current_time=asyncio.get_running_loop().time(),
            logger=logger,
        )


async def schedule_browser_cleanup(
    *,
    interval: float,
    cleanup_browser_pool: Callable[[], Any],
    logger: Any,
) -> None:
    """按固定间隔调度浏览器池清理。"""
    while True:
        await asyncio.sleep(interval)
        try:
            closed = await cleanup_browser_pool()
            if closed:
                logger.info(f"浏览器池清理完成: {len(closed)} 个平台")
        except Exception as exc:
            logger.error(f"浏览器池清理调度失败: {exc}")


async def close_all_browsers(
    *,
    browser_pool: dict[str, BrowserInfo],
    browser_pool_lock: asyncio.Lock,
    logger: Any,
) -> None:
    """关闭浏览器池内全部浏览器。"""
    async with browser_pool_lock:
        for platform, browser_info in list(browser_pool.items()):
            try:
                logger.info(f"关闭平台 {platform} 的浏览器")
                await close_browser_info(browser_info)
            except Exception as exc:
                logger.error(f"关闭平台 {platform} 浏览器失败: {exc}")
        browser_pool.clear()
