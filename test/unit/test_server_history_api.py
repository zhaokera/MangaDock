from fastapi.testclient import TestClient

from crawlers.db import TaskRecord, get_task, get_total_count, save_task
from server import app


client = TestClient(app)


class TestHistoryApi:
    def setup_method(self):
        import crawlers.db as db_module

        self._db_module = db_module
        self._original_path = db_module.DB_PATH

    def teardown_method(self):
        self._db_module.close_connection()
        self._db_module.DB_PATH = self._original_path
        self._db_module.close_connection()

    def _use_temp_db(self, tmp_path):
        self._db_module.DB_PATH = tmp_path / "tasks.db"
        self._db_module.close_connection()
        self._db_module.init_db()

    def _save_task(self, task_id: str, platform: str, status: str):
        save_task(
            TaskRecord(
                task_id=task_id,
                url=f"https://example.com/{task_id}",
                platform=platform,
                status=status,
                created_at="2026-03-23T10:00:00",
                updated_at="2026-03-23T10:00:00",
            )
        )

    def test_delete_history_item_removes_only_target_record(self, tmp_path):
        self._use_temp_db(tmp_path)
        self._save_task("task-1", "tencent", "completed")
        self._save_task("task-2", "iqiyi", "failed")

        response = client.delete("/api/history/task-1")

        assert response.status_code == 200
        assert response.json() == {"deleted": True, "task_id": "task-1"}
        assert get_task("task-1") is None
        assert get_task("task-2") is not None

    def test_clear_history_can_limit_by_platforms(self, tmp_path):
        self._use_temp_db(tmp_path)
        self._save_task("task-1", "manhuagui", "completed")
        self._save_task("task-2", "tencent", "failed")
        self._save_task("task-3", "iqiyi", "completed")
        self._save_task("task-4", "manhuagui", "pending")

        response = client.request("DELETE", "/api/history", json={"platforms": ["tencent", "iqiyi"]})

        assert response.status_code == 200
        assert response.json() == {"deleted": 2}
        assert get_task("task-1") is not None
        assert get_task("task-2") is None
        assert get_task("task-3") is None
        assert get_task("task-4") is not None
        assert get_total_count() == 2
