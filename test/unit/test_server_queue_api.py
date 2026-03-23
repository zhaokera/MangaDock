from fastapi.testclient import TestClient

import server
from server import app


client = TestClient(app)


class TestQueueApi:
    def setup_method(self):
        server._download_queue.clear()
        server._download_queue_priority.clear()

    def teardown_method(self):
        server._download_queue.clear()
        server._download_queue_priority.clear()

    def test_get_queue_sorts_by_priority(self):
        first = server.DownloadTask("task-1", "https://example.com/1", platform="tencent")
        second = server.DownloadTask("task-2", "https://example.com/2", platform="iqiyi")
        server._download_queue[first.task_id] = first
        server._download_queue[second.task_id] = second
        server._download_queue_priority[first.task_id] = 1
        server._download_queue_priority[second.task_id] = 5

        response = client.get("/api/queue")

        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert [item["task_id"] for item in response.json()["queue"]] == ["task-2", "task-1"]

    def test_queue_mutation_endpoints_update_task_state(self):
        task = server.DownloadTask("task-1", "https://example.com/1", platform="youku")
        server._download_queue[task.task_id] = task
        server._download_queue_priority[task.task_id] = 0

        priority_response = client.post(
            "/api/queue/priority",
            json={"task_id": task.task_id, "priority": 9},
        )
        pause_response = client.post("/api/queue/pause", params={"task_id": task.task_id})
        resume_response = client.post("/api/queue/resume", params={"task_id": task.task_id})
        delete_response = client.delete(f"/api/queue/{task.task_id}")

        assert priority_response.status_code == 200
        assert priority_response.json() == {"status": "updated", "task_id": "task-1", "priority": 9}
        assert pause_response.status_code == 200
        assert pause_response.json() == {"status": "paused", "task_id": "task-1"}
        assert resume_response.status_code == 200
        assert resume_response.json() == {"status": "resumed", "task_id": "task-1"}
        assert delete_response.status_code == 200
        assert delete_response.json() == {"status": "removed", "task_id": "task-1"}
        assert task.task_id not in server._download_queue
        assert task.task_id not in server._download_queue_priority
