"""认证服务。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException


def ensure_auth_platform(platform: str, crawler: Optional[Any]) -> Any:
    """校验平台是否支持认证。"""
    if crawler is None:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    if not hasattr(crawler, "login") or not callable(getattr(crawler, "login")):
        raise HTTPException(status_code=400, detail=f"平台 {platform} 不支持登录")

    return crawler


def build_auth_status_payload(platform: str, is_logged_in: bool, user_info: Optional[dict]) -> dict:
    """构造认证状态响应。"""
    if is_logged_in:
        return {
            "status": "logged_in",
            "platform": platform,
            "user_id": user_info.get("user_id") if user_info else None,
            "user_name": user_info.get("user_name") if user_info else None,
        }

    return {
        "status": "logged_out",
        "platform": platform,
        "user_id": None,
        "user_name": None,
    }
