from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from services.resume import serialize_resume_info, serialize_resume_list


def build_resume_router(*, get_resume_manager: Callable[[], Any]) -> APIRouter:
    router = APIRouter()

    @router.get("/api/resume/status/{task_id}")
    async def get_resume_status(task_id: str):
        """获取断点续传状态"""
        resume_manager = get_resume_manager()
        info = await resume_manager.load_progress(task_id)
        if info is None:
            raise HTTPException(status_code=404, detail="未找到断点续传记录")
        return serialize_resume_info(info)

    @router.delete("/api/resume/{task_id}")
    async def delete_resume(task_id: str):
        """删除断点续传记录"""
        resume_manager = get_resume_manager()
        result = await resume_manager.remove_progress(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="未找到断点续传记录")
        return {"status": "deleted", "task_id": task_id}

    @router.get("/api/resume/list")
    async def list_resumes():
        """列出所有断点续传记录"""
        resume_manager = get_resume_manager()
        infos = await resume_manager.get_all_resumes()
        return serialize_resume_list(infos)

    @router.post("/api/resume/cleanup")
    async def cleanup_resumes(days: int = 7):
        """清理旧的断点续传记录"""
        resume_manager = get_resume_manager()
        count = await resume_manager.cleanup_old_resumes(days)
        return {"cleaned": count, "days": days}

    return router
