"""服务运行时状态模型。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


class DownloadTask:
    def __init__(self, task_id: str, url: str, platform: str = ""):
        self.task_id = task_id
        self.url = url
        self.platform = platform
        self.status: str = "pending"
        self.progress: int = 0
        self.total: int = 0
        self.message: str = ""
        self.manga_info: Optional[dict] = None
        self.output_path: Optional[str] = None
        self.zip_path: Optional[str] = None
        self.error: Optional[str] = None
        self.created_at: datetime = datetime.now()


@dataclass
class AppRuntime:
    tasks: dict[str, DownloadTask] = field(default_factory=dict)
    task_last_sse_state: dict[str, dict] = field(default_factory=dict)
    state_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    browser_pool: dict[str, dict] = field(default_factory=dict)
    browser_pool_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    download_queue: dict[str, DownloadTask] = field(default_factory=dict)
    download_queue_priority: dict[str, int] = field(default_factory=dict)
    download_queue_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    browser_cleanup_task: Optional[asyncio.Task] = None


def create_runtime() -> AppRuntime:
    return AppRuntime()
