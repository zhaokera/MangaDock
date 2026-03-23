import pytest

from server import DownloadTask
from services.queue import (
    list_queue_items,
    remove_queue_task,
    set_queue_task_status,
    update_queue_priority,
)


def test_list_queue_items_sorts_by_priority_descending():
    low = DownloadTask("task-low", "https://example.com/low", platform="tencent")
    high = DownloadTask("task-high", "https://example.com/high", platform="iqiyi")
    queue = {
        low.task_id: low,
        high.task_id: high,
    }
    priorities = {
        low.task_id: 1,
        high.task_id: 10,
    }

    payload = list_queue_items(queue, priorities)

    assert payload["total"] == 2
    assert [item["task_id"] for item in payload["queue"]] == ["task-high", "task-low"]


def test_set_queue_task_status_updates_existing_task():
    task = DownloadTask("task-1", "https://example.com/1", platform="tencent")
    queue = {task.task_id: task}

    result = set_queue_task_status(queue, "task-1", "paused")

    assert result == {"status": "paused", "task_id": "task-1"}
    assert task.status == "paused"


def test_update_queue_priority_requires_existing_task():
    with pytest.raises(KeyError):
        update_queue_priority({}, {}, "missing", 5)


def test_remove_queue_task_removes_priority_too():
    task = DownloadTask("task-1", "https://example.com/1", platform="youku")
    queue = {task.task_id: task}
    priorities = {task.task_id: 3}

    result = remove_queue_task(queue, priorities, task.task_id)

    assert result == {"status": "removed", "task_id": "task-1"}
    assert queue == {}
    assert priorities == {}
