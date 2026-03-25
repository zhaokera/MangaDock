"""Project-specific FastAPI bootstrap assembly."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Protocol

from fastapi import FastAPI

from crawlers import BaseCrawler, TaskRecord
from crawlers.manga_search import BaseMangaSearcher
from crawlers.search import BaseSearcher
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
from services.state import AppRuntime, DownloadTask


BrowserPool = dict[str, dict[str, Any]]


class HistoryConfig(Protocol):
    max_items: int


class SseConfig(Protocol):
    heartbeat_interval: float


class CrawlerConfig(Protocol):
    browser_args: list[str]
    user_agent: str | None


class AppConfig(Protocol):
    history: HistoryConfig
    sse: SseConfig
    crawler: CrawlerConfig


class AuthManagerLike(Protocol):
    async def login(self, platform: str, credentials: dict[str, Any]) -> bool: ...
    async def get_user_info(self, platform: str) -> dict[str, Any] | None: ...
    async def logout(self, platform: str) -> bool: ...
    async def is_logged_in(self, platform: str) -> bool: ...


class ResumeManagerLike(Protocol):
    async def load_progress(self, task_id: str) -> Any | None: ...
    async def remove_progress(self, task_id: str) -> bool: ...
    async def get_all_resumes(self) -> list[Any]: ...
    async def cleanup_old_resumes(self, days: int = 7) -> int: ...


class GetTotalCount(Protocol):
    def __call__(self, status: str | None = None, platform: str | None = None) -> int: ...


class InitBrowserForCrawler(Protocol):
    def __call__(
        self,
        *,
        crawler: BaseCrawler,
        platform: str,
        browser_pool: BrowserPool,
        browser_pool_lock: asyncio.Lock,
        get_config: Callable[[], AppConfig],
        logger: logging.Logger,
    ) -> Awaitable[None]: ...


ReleaseBrowserForPlatform = Callable[[BrowserPool, str, float], None]
GetConfig = Callable[[], AppConfig]
GetTaskRecord = Callable[[str], Optional[TaskRecord]]
GetCrawlerForUrl = Callable[[str], BaseCrawler]
GetSearcher = Callable[[str], Optional[BaseSearcher]]
GetMangaSearcher = Callable[[str], Optional[BaseMangaSearcher]]
GetAuthManager = Callable[[], AuthManagerLike]
GetResumeManager = Callable[[], ResumeManagerLike]
GetCrawlerByPlatform = Callable[[str], Optional[BaseCrawler]]
CreateDownloadTask = Callable[[str, str, str], DownloadTask]
AsyncLifecycleHook = Callable[[], Awaitable[None]]


def create_server_application(
    *,
    runtime: AppRuntime,
    logger: logging.Logger,
    downloads_dir: Path,
    get_config: GetConfig,
    get_task_record: GetTaskRecord,
    save_task_record: Callable[..., Any],
    delete_task_record: Callable[[str], bool],
    delete_history_tasks: Callable[..., Any],
    get_history_tasks: Callable[..., Any],
    get_total_count: GetTotalCount,
    get_crawler_for_url: GetCrawlerForUrl,
    get_searcher: GetSearcher,
    search_all_platforms: Callable[..., Any],
    get_manga_searcher: GetMangaSearcher,
    get_auth_manager: GetAuthManager,
    get_resume_manager: GetResumeManager,
    get_crawler_by_platform: GetCrawlerByPlatform,
    init_browser_for_crawler: InitBrowserForCrawler,
    release_browser_for_platform: ReleaseBrowserForPlatform,
    add_history_item: Callable[..., Any],
    create_download_task: CreateDownloadTask,
    on_startup: AsyncLifecycleHook,
    on_shutdown: AsyncLifecycleHook,
) -> FastAPI:
    def _history_max_items() -> int:
        value = get_config().history.max_items
        return value if value > 0 else 100

    async def _add_history_record(history_item: dict) -> bool:
        return await add_history_item(
            history_item,
            state_lock=runtime.state_lock,
            get_task_record=get_task_record,
            save_task_record=save_task_record,
            get_total_completed_count=lambda: get_total_count(status="completed"),
            get_history_tasks=lambda limit: get_history_tasks(limit=limit),
            delete_task_record=delete_task_record,
            get_history_max_items=_history_max_items,
        )

    async def _bind_crawler_browser(crawler: Any, platform: str) -> None:
        await init_browser_for_crawler(
            crawler=crawler,
            platform=platform,
            browser_pool=runtime.browser_pool,
            browser_pool_lock=runtime.browser_pool_lock,
            get_config=get_config,
            logger=logger,
        )

    def _release_platform_browser(platform: str) -> None:
        release_browser_for_platform(
            runtime.browser_pool,
            platform,
            asyncio.get_running_loop().time(),
        )

    def _build_downloader(task: Any) -> MangaDownloader:
        return MangaDownloader(
            task,
            downloads_dir=downloads_dir,
            get_crawler_for_url=get_crawler_for_url,
            init_browser_for_crawler=_bind_crawler_browser,
            release_browser_for_platform=_release_platform_browser,
            save_task_record=save_task_record,
            add_history_item=_add_history_record,
            task_last_sse_state=runtime.task_last_sse_state,
            tasks=runtime.tasks,
        )

    def _build_download_router():
        return build_download_router(
            get_crawler_for_url=get_crawler_for_url,
            create_download_task=create_download_task,
            create_downloader=_build_downloader,
            get_task_record=get_task_record,
            task_last_sse_state=runtime.task_last_sse_state,
            get_heartbeat_interval=lambda: get_config().sse.heartbeat_interval,
        )

    def _build_history_router():
        return build_history_router(
            get_history_tasks=lambda limit: get_history_tasks(limit=limit),
            get_history_max_items=_history_max_items,
            get_task_record=get_task_record,
            delete_task_record=delete_task_record,
            delete_history_tasks=delete_history_tasks,
        )

    def _build_queue_router():
        return build_queue_router(
            download_queue=runtime.download_queue,
            priorities=runtime.download_queue_priority,
            queue_lock=runtime.download_queue_lock,
        )

    def _build_search_router():
        return build_search_router(
            search_all_platforms=search_all_platforms,
            get_searcher=get_searcher,
            get_manga_searcher=get_manga_searcher,
        )

    def _build_parse_router():
        return build_parse_router(
            get_crawler_for_url=get_crawler_for_url,
        )

    def _build_auth_router():
        return build_auth_router(
            get_auth_manager=get_auth_manager,
            get_crawler_by_platform=get_crawler_by_platform,
        )

    def _build_resume_router():
        return build_resume_router(
            get_resume_manager=get_resume_manager,
        )

    return create_application(
        title="漫画下载器",
        description="支持多平台的漫画下载服务",
        platforms_router=platforms_router,
        download_router_factory=_build_download_router,
        history_router_factory=_build_history_router,
        queue_router_factory=_build_queue_router,
        search_router_factory=_build_search_router,
        parse_router_factory=_build_parse_router,
        auth_router_factory=_build_auth_router,
        resume_router_factory=_build_resume_router,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )
