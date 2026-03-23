from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from services.downloads import (
    build_download_file_response,
    create_pending_task_record,
    create_task_id,
    serialize_progress_payload,
    serialize_task_record,
)


class DownloadStartRequest(BaseModel):
    url: str


class BatchDownloadStartRequest(BaseModel):
    urls: list[str]


def build_download_router(
    *,
    get_crawler_for_url: Callable[[str], Any],
    create_download_task: Callable[[str, str, str], Any],
    create_downloader: Callable[[Any], Any],
    get_task_record: Callable[[str], Any],
    task_last_sse_state: dict[str, dict[str, Any]],
    get_heartbeat_interval: Callable[[], float],
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/download")
    async def start_download(request: DownloadStartRequest, background_tasks: BackgroundTasks):
        """启动下载任务"""
        url = request.url

        try:
            crawler = get_crawler_for_url(url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        task_id = create_task_id()
        task = create_download_task(task_id, url, crawler.PLATFORM_NAME)
        create_pending_task_record(
            task_id=task.task_id,
            url=task.url,
            platform=task.platform,
            created_at=task.created_at,
        )
        background_tasks.add_task(create_downloader(task).run)

        return {
            "task_id": task_id,
            "status": "pending",
            "platform": crawler.PLATFORM_NAME,
            "message": "任务已创建",
        }

    @router.post("/api/batch-download")
    async def start_batch_download(
        request: BatchDownloadStartRequest,
        background_tasks: BackgroundTasks,
    ):
        """批量下载 - 一次下载多个漫画"""
        urls = request.urls

        if not urls:
            raise HTTPException(status_code=400, detail="至少需要提供一个 URL")

        if len(urls) > 20:
            raise HTTPException(status_code=400, detail="单次最多支持 20 个 URL")

        tasks_info: list[dict[str, Any]] = []
        for url in urls:
            try:
                crawler = get_crawler_for_url(url)
                tasks_info.append(
                    {
                        "url": url,
                        "platform": crawler.PLATFORM_NAME,
                    }
                )
            except ValueError as exc:
                tasks_info.append(
                    {
                        "url": url,
                        "error": str(exc),
                        "platform": None,
                    }
                )

        results = []
        for info in tasks_info:
            if info.get("error"):
                results.append(
                    {
                        "url": info["url"],
                        "status": "failed",
                        "error": info["error"],
                    }
                )
                continue

            task_id = create_task_id()
            task = create_download_task(task_id, info["url"], info["platform"])
            create_pending_task_record(
                task_id=task.task_id,
                url=task.url,
                platform=task.platform,
                created_at=task.created_at,
            )
            background_tasks.add_task(create_downloader(task).run)

            results.append(
                {
                    "url": info["url"],
                    "task_id": task_id,
                    "status": "pending",
                    "platform": info["platform"],
                }
            )

        return {
            "total": len(results),
            "success": sum(1 for item in results if item.get("status") == "pending"),
            "failed": sum(1 for item in results if item.get("status") == "failed"),
            "results": results,
        }

    @router.get("/api/status/{task_id}")
    async def get_status(task_id: str):
        """获取任务状态"""
        task_record = get_task_record(task_id)
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")

        return serialize_task_record(task_record)

    @router.get("/api/progress/{task_id}")
    async def stream_progress(task_id: str, timeout: float = Query(300.0)):
        """SSE 进度推送"""
        task_record = get_task_record(task_id)
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")

        heartbeat_interval = max(0.5, get_heartbeat_interval())

        async def event_generator():
            start_time = time.time()
            last_state = task_last_sse_state.get(task_id, {})
            last_progress_percent = 0

            def is_important_change(current: dict[str, Any], last: dict[str, Any]) -> bool:
                nonlocal last_progress_percent

                if current.get("status") != last.get("status"):
                    return True
                if current.get("error") != last.get("error"):
                    return True
                if current.get("total") != last.get("total"):
                    return True

                current_total = current.get("total", 0)
                current_progress = current.get("progress", 0)
                if current_total > 0:
                    current_percent = (current_progress / current_total) * 100
                    if current_percent - last_progress_percent >= 5:
                        last_progress_percent = current_percent
                        return True

                if current.get("message") != last.get("message"):
                    important_keywords = ["检测到", "解码", "读取", "完成", "失败", "错误", "加载", "打包"]
                    message = current.get("message", "")
                    return any(keyword in message for keyword in important_keywords)

                return False

            yield f"data: {serialize_progress_payload(task_record)}\n\n"

            while True:
                if time.time() - start_time > timeout:
                    task_last_sse_state.pop(task_id, None)
                    break

                current_record = get_task_record(task_id)
                if not current_record:
                    task_last_sse_state.pop(task_id, None)
                    break

                current_state = {
                    "status": current_record.status,
                    "progress": current_record.progress,
                    "total": current_record.total,
                    "message": current_record.message,
                    "error": current_record.error,
                }

                if is_important_change(current_state, last_state):
                    yield f"data: {serialize_progress_payload(current_record)}\n\n"
                    last_state = current_state.copy()
                    task_last_sse_state[task_id] = last_state

                if current_record.status in {"completed", "failed"}:
                    task_last_sse_state.pop(task_id, None)
                    break

                await asyncio.sleep(heartbeat_interval)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    @router.get("/api/files/{task_id}")
    async def download_file(task_id: str):
        """下载打包文件"""
        task_record = get_task_record(task_id)
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")

        return build_download_file_response(task_record)

    return router
