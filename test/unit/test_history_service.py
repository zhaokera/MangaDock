from crawlers.db import TaskRecord
from services.history import paginate_history_records


def test_paginate_history_records_clamps_page_values_and_reports_has_more():
    records = [
        TaskRecord(task_id=f"task-{index}", url=f"https://example.com/{index}", platform="tencent")
        for index in range(5)
    ]

    payload = paginate_history_records(records, page=0, page_size=0)

    assert payload["total"] == 5
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["has_more"] is False
    assert [item["task_id"] for item in payload["history"]] == [f"task-{index}" for index in range(5)]


def test_paginate_history_records_limits_page_size_and_slices_page():
    records = [
        TaskRecord(task_id=f"task-{index}", url=f"https://example.com/{index}", platform="iqiyi")
        for index in range(300)
    ]

    payload = paginate_history_records(records, page=2, page_size=500)

    assert payload["total"] == 300
    assert payload["page"] == 2
    assert payload["page_size"] == 200
    assert payload["has_more"] is False
    assert len(payload["history"]) == 100
    assert payload["history"][0]["task_id"] == "task-200"
