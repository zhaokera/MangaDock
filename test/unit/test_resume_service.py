from crawlers.resume import ResumeInfo
from services.resume import serialize_resume_info, serialize_resume_list


def test_serialize_resume_info_returns_api_payload():
    info = ResumeInfo(
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

    assert serialize_resume_info(info) == {
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


def test_serialize_resume_list_includes_total():
    infos = [
        ResumeInfo(task_id="task-1", url="https://example.com/1", platform="tencent"),
        ResumeInfo(task_id="task-2", url="https://example.com/2", platform="iqiyi"),
    ]

    payload = serialize_resume_list(infos)

    assert payload["total"] == 2
    assert [item["task_id"] for item in payload["resumes"]] == ["task-1", "task-2"]
