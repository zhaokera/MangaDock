"""下载队列服务。"""

from __future__ import annotations

from typing import Any


def list_queue_items(download_queue: dict[str, Any], priorities: dict[str, int]) -> dict:
    """返回按优先级排序的队列项。"""
    queue_items = []
    for position, (task_id, task) in enumerate(download_queue.items()):
        queue_items.append(
            {
                "task_id": task_id,
                "url": task.url,
                "platform": task.platform,
                "status": task.status,
                "priority": priorities.get(task_id, 0),
                "position": position,
            }
        )

    queue_items.sort(key=lambda item: (-item["priority"], item["position"]))
    return {"queue": queue_items, "total": len(queue_items)}


def set_queue_task_status(download_queue: dict[str, Any], task_id: str, status: str) -> dict:
    """更新队列任务状态。"""
    task = download_queue.get(task_id)
    if task is None:
        raise KeyError(task_id)

    task.status = status
    return {"status": "resumed" if status == "pending" else status, "task_id": task_id}


def remove_queue_task(download_queue: dict[str, Any], priorities: dict[str, int], task_id: str) -> dict:
    """移除队列任务及其优先级。"""
    if task_id not in download_queue:
        raise KeyError(task_id)

    del download_queue[task_id]
    priorities.pop(task_id, None)
    return {"status": "removed", "task_id": task_id}


def update_queue_priority(
    download_queue: dict[str, Any],
    priorities: dict[str, int],
    task_id: str,
    priority: int,
) -> dict:
    """更新任务优先级。"""
    if task_id not in download_queue:
        raise KeyError(task_id)

    priorities[task_id] = priority
    return {"status": "updated", "task_id": task_id, "priority": priority}
