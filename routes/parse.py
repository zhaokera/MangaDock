from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.parse import serialize_parse_result


class ParseRequest(BaseModel):
    url: str


def build_parse_router(*, get_crawler_for_url: Callable[[str], Any]) -> APIRouter:
    router = APIRouter()

    @router.post("/api/parse")
    async def parse_url(request: ParseRequest):
        """解析 URL 返回平台和内容信息"""
        try:
            crawler = get_crawler_for_url(request.url)
            info = await crawler.get_info(request.url)
            return serialize_parse_result(crawler, info, request.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"解析失败: {exc}") from exc

    return router
