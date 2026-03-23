from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.search import (
    clamp_search_limit,
    ensure_manga_searcher,
    raise_manga_not_implemented,
    serialize_search_results,
)


class SearchRequest(BaseModel):
    keyword: str
    platform: Optional[str] = None
    limit: int = 10


def build_search_router(
    *,
    search_all_platforms: Callable[[str, int], Any],
    get_searcher: Callable[[str], Any],
    get_manga_searcher: Callable[[str], Any],
) -> APIRouter:
    router = APIRouter()

    async def run_search(keyword: str, platform: Optional[str], limit: int) -> dict:
        if not keyword:
            raise HTTPException(status_code=400, detail="缺少 keyword 参数")

        normalized_limit = clamp_search_limit(limit)

        try:
            if platform:
                searcher = get_searcher(platform)
                if searcher is None:
                    raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")
                results = await searcher.search(keyword, limit=normalized_limit)
            else:
                results = await search_all_platforms(keyword, normalized_limit)

            return serialize_search_results(results, platform)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"搜索失败: {exc}") from exc

    @router.post("/api/search")
    async def search_videos(request: SearchRequest):
        """搜索视频"""
        return await run_search(
            keyword=request.keyword,
            platform=request.platform,
            limit=request.limit,
        )

    @router.get("/api/search")
    async def search_videos_get(
        keyword: str = Query(...),
        platform: Optional[str] = Query(None),
        limit: int = Query(10),
    ):
        """兼容 GET 搜索接口"""
        return await run_search(keyword=keyword, platform=platform, limit=limit)

    @router.get("/api/search/manga")
    async def search_manga(keyword: str, platform: str, limit: int = 10):
        searcher = ensure_manga_searcher(platform, get_manga_searcher(platform))

        try:
            results = await searcher.search(keyword, limit=limit)
        except NotImplementedError:
            raise_manga_not_implemented(platform, "漫画搜索")

        return serialize_search_results(results, platform)

    @router.get("/api/manga/chapters")
    async def get_manga_chapters(url: str, platform: str):
        searcher = ensure_manga_searcher(platform, get_manga_searcher(platform))

        try:
            payload = await searcher.get_chapters(url)
        except NotImplementedError:
            raise_manga_not_implemented(platform, "章节目录")

        return payload.to_dict()

    return router
