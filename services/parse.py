"""URL 解析服务。"""

from __future__ import annotations

from typing import Any


def serialize_parse_result(crawler: Any, info: Any, url: str) -> dict:
    """统一 URL 解析返回格式。"""
    return {
        "platform": crawler.PLATFORM_NAME,
        "platform_name": crawler.PLATFORM_DISPLAY_NAME,
        "comic_id": info.comic_id,
        "episode_id": info.episode_id,
        "url": url,
    }
