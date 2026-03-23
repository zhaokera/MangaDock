"""搜索服务。"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException


def clamp_search_limit(limit: int) -> int:
    """限制搜索条数范围。"""
    return min(max(limit, 1), 50)


def serialize_search_results(results: list[Any], platform: Optional[str]) -> dict:
    """统一搜索返回格式。"""
    return {
        "results": [item.to_dict() for item in results],
        "total": len(results),
        "platform": platform,
    }


def ensure_manga_searcher(platform: str, searcher: Optional[Any]) -> Any:
    """确保漫画搜索平台可用。"""
    if searcher is None:
        raise HTTPException(status_code=400, detail=f"不支持的漫画搜索平台: {platform}")
    return searcher


def raise_manga_not_implemented(platform: str, action: str) -> None:
    raise HTTPException(
        status_code=501,
        detail=f"漫画搜索平台 {platform} 尚未实现{action}",
    )
