"""下载任务运行时服务。"""

from __future__ import annotations

import asyncio
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from crawlers import BaseCrawler, TaskRecord
from crawlers.base import DownloadProgress


def clear_crawler_runtime(crawler: Any) -> None:
    """清理挂在爬虫上的浏览器运行时引用。"""
    crawler.browser = None
    crawler.context = None
    crawler.page = None
    crawler.playwright = None


def build_history_item(task: Any) -> Optional[dict]:
    """由任务结果生成历史记录项。"""
    if not getattr(task, "manga_info", None):
        return None

    return {
        "task_id": task.task_id,
        "title": task.manga_info.get("title", "未知漫画"),
        "chapter": task.manga_info.get("chapter", ""),
        "platform": task.platform,
        "zip_path": task.zip_path,
        "page_count": task.total,
        "created_at": task.created_at.isoformat(),
    }


async def add_history_item(
    history_item: dict,
    *,
    state_lock: asyncio.Lock,
    get_task_record: Callable[[str], Optional[TaskRecord]],
    save_task_record: Callable[[TaskRecord], None],
    get_total_completed_count: Callable[[], int],
    get_history_tasks: Callable[[int], list[TaskRecord]],
    delete_task_record: Callable[[str], bool],
    get_history_max_items: Callable[[], int],
) -> bool:
    """线程安全地写入历史记录，并按上限裁剪。"""
    async with state_lock:
        if get_task_record(history_item["task_id"]):
            return False

        record = TaskRecord(
            task_id=history_item["task_id"],
            url=history_item.get("url", ""),
            platform=history_item["platform"],
            status="completed",
            message=history_item.get("message", ""),
            manga_info=history_item.get("manga_info"),
            zip_path=history_item.get("zip_path"),
            created_at=history_item.get("created_at", datetime.now().isoformat()),
            updated_at=datetime.now().isoformat(),
        )
        save_task_record(record)

        total = get_total_completed_count()
        max_items = get_history_max_items()
        if total > max_items:
            for task_record in get_history_tasks(total - max_items):
                delete_task_record(task_record.task_id)
        return True


class MangaDownloader:
    """下载任务编排器。"""

    def __init__(
        self,
        task: Any,
        *,
        downloads_dir: Path,
        get_crawler_for_url: Callable[[str], BaseCrawler],
        init_browser_for_crawler: Callable[[BaseCrawler, str], Awaitable[None]],
        release_browser_for_platform: Callable[[str], None],
        save_task_record: Callable[[TaskRecord], None],
        add_history_item: Callable[[dict], Awaitable[bool]],
        task_last_sse_state: dict[str, dict],
        tasks: dict[str, Any],
    ):
        self.task = task
        self.downloads_dir = downloads_dir
        self.get_crawler_for_url = get_crawler_for_url
        self.init_browser_for_crawler = init_browser_for_crawler
        self.release_browser_for_platform = release_browser_for_platform
        self.save_task_record = save_task_record
        self.add_history_item = add_history_item
        self.task_last_sse_state = task_last_sse_state
        self.tasks = tasks
        self.crawler: Optional[BaseCrawler] = None
        self.task_record: Optional[TaskRecord] = None

    def _cleanup_task(self) -> None:
        self.task_last_sse_state.pop(self.task.task_id, None)
        self.tasks.pop(self.task.task_id, None)

    def _persist_task_record(self) -> None:
        if self.task_record is not None:
            self.save_task_record(self.task_record)

    def _persist_failure(self, message: str, error: str) -> None:
        self.task.status = "failed"
        self.task.error = error
        self.task.message = message
        if self.task_record:
            self.task_record.status = "failed"
            self.task_record.error = error
            self.task_record.message = message
            self.save_task_record(self.task_record)

    def _update_manga_info(self) -> None:
        if self.crawler and hasattr(self.crawler, "manga_info"):
            info = self.crawler.manga_info
            if info:
                self.task.manga_info = info.to_dict()
                if self.task_record:
                    self.task_record.manga_info = info.to_dict()
                return
        if self.crawler and hasattr(self.crawler, "_manga_info"):
            info = self.crawler._manga_info
            if info:
                self.task.manga_info = info.to_dict()
                if self.task_record:
                    self.task_record.manga_info = info.to_dict()

    async def run(self) -> None:
        try:
            self.crawler = self.get_crawler_for_url(self.task.url)
            self.task.platform = self.crawler.PLATFORM_NAME
            await self.init_browser_for_crawler(self.crawler, self.task.platform)

            self.task_record = TaskRecord(
                task_id=self.task.task_id,
                url=self.task.url,
                platform=self.task.platform,
                status="pending",
                created_at=self.task.created_at.isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            self.save_task_record(self.task_record)
            await self._do_download()
        except ValueError as exc:
            self._persist_failure(f"错误: {exc}", str(exc))
        except Exception as exc:
            import traceback

            traceback.print_exc()
            self._persist_failure(f"下载失败: {exc}", str(exc))
        finally:
            if self.crawler:
                clear_crawler_runtime(self.crawler)
            if self.task.platform:
                self.release_browser_for_platform(self.task.platform)
            self._cleanup_task()
            self._persist_task_record()

    async def _do_download(self) -> None:
        url = self.task.url

        self.task.message = "解析漫画信息..."
        self.task.status = "downloading"
        if self.task_record:
            self.task_record.status = "downloading"
            self.task_record.message = "解析漫画信息..."
            self.save_task_record(self.task_record)

        try:
            info = await self.crawler.get_info(url)
            self.task.manga_info = info.to_dict()
            self.task.platform = info.platform
            if self.task_record:
                self.task_record.manga_info = info.to_dict()
                self.task_record.platform = info.platform
                self.save_task_record(self.task_record)
        except Exception:
            if self.task_record:
                self.save_task_record(self.task_record)

        def on_progress(progress: DownloadProgress) -> None:
            self.task.progress = progress.current
            self.task.total = progress.total
            self.task.message = progress.message
            if progress.status:
                self.task.status = progress.status
            if self.task_record:
                self.task_record.status = progress.status
                self.task_record.progress = progress.current
                self.task_record.total = progress.total
                self.task_record.message = progress.message
                self.save_task_record(self.task_record)

        output_path = await self.crawler.download(
            url,
            str(self.downloads_dir),
            progress_callback=on_progress,
        )

        self.task.output_path = output_path
        if self.task_record:
            self.task_record.output_path = output_path

        self._update_manga_info()

        self.task.message = "正在打包..."
        if self.task_record:
            self.task_record.message = "正在打包..."
            self.save_task_record(self.task_record)
        if output_path and Path(output_path).exists():
            save_dir = Path(output_path)
            zip_name = save_dir.name
            zip_path = self.downloads_dir / f"{zip_name}.zip"

            loop = asyncio.get_running_loop()

            def zip_folder_sync() -> None:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    for file in sorted(save_dir.iterdir()):
                        if file.is_file():
                            archive.write(file, file.name)

            await loop.run_in_executor(None, zip_folder_sync)

            self.task.zip_path = str(zip_path)
            if self.task_record:
                self.task_record.zip_path = str(zip_path)

        self.task.status = "completed"
        self.task.message = f"下载完成! 共 {self.task.total} 张图片"
        if self.task_record:
            self.task_record.status = "completed"
            self.task_record.message = f"下载完成! 共 {self.task.total} 张图片"
            self.save_task_record(self.task_record)

        history_item = build_history_item(self.task)
        if history_item:
            await self.add_history_item(history_item)
