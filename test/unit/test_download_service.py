from pathlib import Path

import pytest
from fastapi import HTTPException

from crawlers.db import TaskRecord
from services.downloads import build_download_file_response, serialize_task_record


def test_serialize_task_record_returns_api_payload():
    record = TaskRecord(
        task_id="task-1",
        url="https://example.com/comic/1",
        platform="tencent",
        status="completed",
        progress=10,
        total=10,
        message="下载完成",
        manga_info={"title": "测试漫画"},
        output_path="/tmp/output",
        zip_path="/tmp/output.zip",
        error=None,
    )

    assert serialize_task_record(record) == {
        "task_id": "task-1",
        "status": "completed",
        "progress": 10,
        "total": 10,
        "message": "下载完成",
        "platform": "tencent",
        "manga_info": {"title": "测试漫画"},
        "zip_path": "/tmp/output.zip",
        "output_path": "/tmp/output",
        "error": None,
    }


def test_build_download_file_response_rejects_unfinished_task():
    record = TaskRecord(
        task_id="task-2",
        url="https://example.com/comic/2",
        platform="tencent",
        status="downloading",
    )

    with pytest.raises(HTTPException) as exc_info:
        build_download_file_response(record)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "任务尚未完成"


def test_build_download_file_response_rejects_missing_zip(tmp_path: Path):
    record = TaskRecord(
        task_id="task-3",
        url="https://example.com/comic/3",
        platform="tencent",
        status="completed",
        zip_path=str(tmp_path / "missing.zip"),
    )

    with pytest.raises(HTTPException) as exc_info:
        build_download_file_response(record)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "文件不存在"


def test_build_download_file_response_returns_zip_file(tmp_path: Path):
    zip_path = tmp_path / "download.zip"
    zip_path.write_bytes(b"zip-data")

    record = TaskRecord(
        task_id="task-4",
        url="https://example.com/comic/4",
        platform="tencent",
        status="completed",
        zip_path=str(zip_path),
    )

    response = build_download_file_response(record)

    assert response.path == str(zip_path)
    assert response.filename == "download.zip"
    assert response.media_type == "application/zip"
