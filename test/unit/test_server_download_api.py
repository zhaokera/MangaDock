"""下载 API 回归测试"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


class TestDownloadApi:
    """Test download task creation timing."""

    @pytest.fixture(autouse=True)
    def isolated_db(self, tmp_path):
        import crawlers.db as db_module

        original_path = db_module.DB_PATH
        db_module.DB_PATH = tmp_path / "tasks.db"
        db_module.close_connection()
        db_module.init_db()

        yield

        db_module.close_connection()
        db_module.DB_PATH = original_path
        db_module.close_connection()

    def test_download_task_is_queryable_immediately_after_creation(self):
        fake_crawler = SimpleNamespace(PLATFORM_NAME="tencent")

        with patch("server.get_crawler", return_value=fake_crawler), patch.object(
            __import__("server").MangaDownloader,
            "run",
            new=AsyncMock(return_value=None),
        ):
            response = client.post(
                "/api/download",
                json={"url": "https://v.qq.com/x/cover/sdp001li4k36b23.html"},
            )

            assert response.status_code == 200
            task_id = response.json()["task_id"]

            status_response = client.get(f"/api/status/{task_id}")
            assert status_response.status_code == 200
            assert status_response.json()["status"] == "pending"
            assert status_response.json()["platform"] == "tencent"

            with client.stream("GET", f"/api/progress/{task_id}?timeout=0.01") as progress_response:
                assert progress_response.status_code == 200
                first_event = next(progress_response.iter_text())
                assert task_id in first_event
                assert '"status": "pending"' in first_event

    def test_batch_download_tasks_are_queryable_immediately_after_creation(self):
        fake_crawler = SimpleNamespace(PLATFORM_NAME="manhuagui")

        with patch("server.get_crawler", return_value=fake_crawler), patch.object(
            __import__("server").MangaDownloader,
            "run",
            new=AsyncMock(return_value=None),
        ):
            response = client.post(
                "/api/batch-download",
                json={
                    "urls": [
                        "https://www.manhuagui.com/comic/1/1.html",
                        "https://www.manhuagui.com/comic/2/2.html",
                    ]
                },
            )

            assert response.status_code == 200
            payload = response.json()
            assert payload["success"] == 2

            for item in payload["results"]:
                task_id = item["task_id"]
                status_response = client.get(f"/api/status/{task_id}")
                assert status_response.status_code == 200
                assert status_response.json()["status"] == "pending"
                assert status_response.json()["platform"] == "manhuagui"
