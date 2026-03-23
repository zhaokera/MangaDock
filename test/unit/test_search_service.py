from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from crawlers.search import SearchResult
from services.search import ensure_manga_searcher, serialize_search_results


def test_serialize_search_results_clamps_limit_and_preserves_platform():
    results = [
        SearchResult(
            title="测试视频",
            url="https://example.com/video",
            platform="tencent",
            platform_display="腾讯视频",
            score=88.0,
        )
    ]

    payload = serialize_search_results(results, platform="tencent")

    assert payload == {
        "results": [results[0].to_dict()],
        "total": 1,
        "platform": "tencent",
    }


def test_ensure_manga_searcher_rejects_unsupported_platform():
    with pytest.raises(HTTPException) as exc_info:
        ensure_manga_searcher("unknown", None)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "不支持的漫画搜索平台: unknown"
