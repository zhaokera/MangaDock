from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


class TestResumeApi:
    def test_get_resume_status_returns_serialized_payload(self):
        info = SimpleNamespace(
            task_id="task-1",
            url="https://example.com/1",
            platform="tencent",
            total=10,
            downloaded_count=6,
            success_count=5,
            failed_count=1,
            created_at="2026-03-24T10:00:00",
            last_updated="2026-03-24T10:05:00",
        )

        with patch("server.get_resume_manager") as get_manager:
            get_manager.return_value.load_progress = AsyncMock(return_value=info)
            response = client.get("/api/resume/status/task-1")

        assert response.status_code == 200
        assert response.json() == {
            "task_id": "task-1",
            "url": "https://example.com/1",
            "platform": "tencent",
            "total": 10,
            "downloaded_count": 6,
            "success_count": 5,
            "failed_count": 1,
            "created_at": "2026-03-24T10:00:00",
            "last_updated": "2026-03-24T10:05:00",
        }

    def test_cleanup_resumes_returns_cleaned_count(self):
        with patch("server.get_resume_manager") as get_manager:
            get_manager.return_value.cleanup_old_resumes = AsyncMock(return_value=3)
            response = client.post("/api/resume/cleanup", params={"days": 14})

        assert response.status_code == 200
        assert response.json() == {"cleaned": 3, "days": 14}
