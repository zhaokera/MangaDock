"""断点续传服务。"""

from __future__ import annotations

from typing import Iterable

from crawlers.resume import ResumeInfo


def serialize_resume_info(info: ResumeInfo) -> dict:
    """序列化断点续传信息。"""
    return {
        "task_id": info.task_id,
        "url": info.url,
        "platform": info.platform,
        "total": info.total,
        "downloaded_count": info.downloaded_count,
        "success_count": info.success_count,
        "failed_count": info.failed_count,
        "created_at": info.created_at,
        "last_updated": info.last_updated,
    }


def serialize_resume_list(infos: Iterable[ResumeInfo]) -> dict:
    """序列化断点续传列表。"""
    resumes = [serialize_resume_info(info) for info in infos]
    return {"resumes": resumes, "total": len(resumes)}
