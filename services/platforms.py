"""平台目录与认证平台服务。"""

from __future__ import annotations

from typing import Any

from crawlers import get_supported_platforms
from crawlers.registry import get_crawler_by_platform


def list_supported_platforms() -> list[dict[str, Any]]:
    """返回已注册的平台目录。"""
    return get_supported_platforms()


def list_auth_platforms() -> list[dict[str, str]]:
    """返回支持认证的平台目录。"""
    supported: list[dict[str, str]] = []

    for platform in list_supported_platforms():
        crawler = get_crawler_by_platform(platform["name"])
        if crawler and hasattr(crawler, "login") and callable(getattr(crawler, "login")):
            supported.append({
                "name": platform["name"],
                "display_name": platform["display_name"],
            })

    return supported
