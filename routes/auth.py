from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.auth import build_auth_status_payload, ensure_auth_platform


class LoginRequest(BaseModel):
    platform: str
    username: str
    password: str
    credentials: Optional[dict] = None


class LoginResponse(BaseModel):
    status: str
    platform: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    message: Optional[str] = None


def build_auth_router(
    *,
    get_auth_manager: Callable[[], Any],
    get_crawler_by_platform: Callable[[str], Any],
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/auth/login", response_model=LoginResponse)
    async def login(request: LoginRequest):
        """登录平台"""
        platform = request.platform
        credentials = {
            "username": request.username,
            "password": request.password,
        }
        if request.credentials:
            credentials.update(request.credentials)

        ensure_auth_platform(platform, get_crawler_by_platform(platform))

        auth_manager = get_auth_manager()
        result = await auth_manager.login(platform, credentials)
        if not result:
            raise HTTPException(status_code=401, detail="登录失败")

        user_info = await auth_manager.get_user_info(platform)
        return LoginResponse(
            status="success",
            platform=platform,
            user_id=user_info.get("user_id") if user_info else None,
            user_name=user_info.get("user_name") if user_info else None,
            message="登录成功",
        )

    @router.post("/api/auth/logout")
    async def logout(request: dict):
        """登出平台"""
        platform = request.get("platform")
        if not platform:
            raise HTTPException(status_code=400, detail="缺少 platform 参数")

        auth_manager = get_auth_manager()
        result = await auth_manager.logout(platform)
        if not result:
            raise HTTPException(status_code=500, detail="登出失败")

        return {"status": "success", "platform": platform, "message": "登出成功"}

    @router.get("/api/auth/status")
    async def auth_status(platform: str):
        """检查登录状态"""
        auth_manager = get_auth_manager()
        is_logged_in = await auth_manager.is_logged_in(platform)
        user_info = await auth_manager.get_user_info(platform) if is_logged_in else None
        return build_auth_status_payload(platform, is_logged_in, user_info)

    return router
