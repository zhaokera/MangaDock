from __future__ import annotations

from typing import Callable, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from services.history import ensure_history_task_exists, paginate_history_records


class ClearHistoryRequest(BaseModel):
    platforms: Optional[List[str]] = None


def build_history_router(
    *,
    get_history_tasks: Callable[[int], list],
    get_history_max_items: Callable[[], int],
    get_task_record: Callable[[str], Optional[object]],
    delete_task_record: Callable[[str], bool],
    delete_history_tasks: Callable[[Optional[List[str]]], int],
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/history")
    async def get_history(page: int = 1, page_size: int = 50):
        """获取下载历史（支持分页）"""
        max_items = get_history_max_items()
        all_history = get_history_tasks(max_items)
        return paginate_history_records(all_history, page=page, page_size=page_size)

    @router.delete("/api/history/{task_id}")
    async def delete_history_item(task_id: str):
        """删除单条历史记录"""
        ensure_history_task_exists(get_task_record(task_id))
        deleted = delete_task_record(task_id)
        return {"deleted": deleted, "task_id": task_id}

    @router.delete("/api/history")
    async def clear_history(request: ClearHistoryRequest = Body(default=ClearHistoryRequest())):
        """清空历史记录"""
        deleted = delete_history_tasks(request.platforms)
        return {"deleted": deleted}

    return router
