"""下载路由共享服务。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse

from crawlers import TaskRecord, save_task


def create_task_id() -> str:
    """创建短任务 ID。"""
    return str(uuid.uuid4())[:8]


def create_pending_task_record(*, task_id: str, url: str, platform: str, created_at: datetime) -> TaskRecord:
    """创建并持久化待执行任务记录。"""
    record = TaskRecord(
        task_id=task_id,
        url=url,
        platform=platform,
        status="pending",
        message="任务已创建",
        created_at=created_at.isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    save_task(record)
    return record


def serialize_task_record(record: TaskRecord) -> dict:
    """转换任务记录为 API 返回格式。"""
    return {
        "task_id": record.task_id,
        "status": record.status,
        "progress": record.progress,
        "total": record.total,
        "message": record.message,
        "platform": record.platform,
        "manga_info": record.manga_info,
        "zip_path": record.zip_path,
        "output_path": record.output_path,
        "error": record.error,
    }


def serialize_progress_payload(record: TaskRecord) -> str:
    """生成 SSE 所需的 JSON 数据。"""
    return json.dumps(serialize_task_record(record), ensure_ascii=False) + "\n\n"


def build_download_file_response(record: TaskRecord) -> FileResponse:
    """校验任务结果并返回可下载文件响应。"""
    if record.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not record.zip_path or not Path(record.zip_path).exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    filename = Path(record.zip_path).name
    return FileResponse(
        record.zip_path,
        media_type="application/zip",
        filename=filename,
    )
