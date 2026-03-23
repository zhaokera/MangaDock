"""历史记录服务。"""

from __future__ import annotations

from typing import Iterable, Optional

from fastapi import HTTPException

from crawlers.db import TaskRecord


def paginate_history_records(records: Iterable[TaskRecord], page: int, page_size: int) -> dict:
    """按现有 API 约定分页历史记录。"""
    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1 if page_size > 0 else 50), 200)
    if page_size < 1:
        normalized_page_size = 50

    items = list(records)
    total = len(items)
    start = (normalized_page - 1) * normalized_page_size
    end = start + normalized_page_size
    page_tasks = items[start:end]

    return {
        "history": [task.to_dict() for task in page_tasks],
        "total": total,
        "page": normalized_page,
        "page_size": normalized_page_size,
        "has_more": end < total,
    }


def ensure_history_task_exists(task: Optional[TaskRecord]) -> TaskRecord:
    """确保记录属于可删除的历史项。"""
    if not task or task.status not in {"completed", "failed"}:
        raise HTTPException(status_code=404, detail="历史记录不存在")
    return task
