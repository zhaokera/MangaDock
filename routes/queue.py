from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException

from services.queue import (
    list_queue_items,
    remove_queue_task,
    set_queue_task_status,
    update_queue_priority,
)


def build_queue_router(
    *,
    download_queue: dict[str, Any],
    priorities: dict[str, int],
    queue_lock: asyncio.Lock,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/queue/pause")
    async def pause_download(task_id: str):
        """暂停下载任务"""
        async with queue_lock:
            try:
                return set_queue_task_status(download_queue, task_id, "paused")
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="任务不存在") from exc

    @router.post("/api/queue/resume")
    async def resume_download(task_id: str):
        """恢复下载任务"""
        async with queue_lock:
            try:
                return set_queue_task_status(download_queue, task_id, "pending")
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="任务不存在") from exc

    @router.delete("/api/queue/{task_id}")
    async def remove_from_queue(task_id: str):
        """从下载队列移除任务"""
        async with queue_lock:
            try:
                return remove_queue_task(download_queue, priorities, task_id)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="任务不存在") from exc

    @router.get("/api/queue")
    async def get_download_queue():
        """获取下载队列"""
        async with queue_lock:
            return list_queue_items(download_queue, priorities)

    @router.post("/api/queue/priority")
    async def set_priority(request: dict):
        """更新任务优先级"""
        task_id = request.get("task_id")
        priority = request.get("priority", 0)
        async with queue_lock:
            try:
                return update_queue_priority(download_queue, priorities, task_id, priority)
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="任务不存在") from exc

    return router
