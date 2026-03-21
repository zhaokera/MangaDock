"""搜索 API 回归测试"""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from crawlers.search import SearchResult, DlExpoSearcher
from server import app


client = TestClient(app)


class TestSearchApi:
    """Test search API compatibility."""

    def test_search_api_supports_dl_expo_platform(self):
        mocked_results = [
            SearchResult(
                title="灌篮高手",
                url="https://www.dl-expo.com/voddetail/101100.html",
                platform="dl_expo",
                platform_display="糯米影视",
                score=99.0,
            )
        ]

        with patch.object(DlExpoSearcher, "search", new=AsyncMock(return_value=mocked_results)):
            response = client.get(
                "/api/search",
                params={"keyword": "灌篮高手", "platform": "dl_expo", "limit": 5},
            )

        assert response.status_code == 200
        assert response.json()["platform"] == "dl_expo"
        assert response.json()["results"] == [mocked_results[0].to_dict()]

    def test_search_endpoint_accepts_get_requests(self):
        """前端当前使用 GET，请求不应返回 405。"""
        mocked_results = [
            SearchResult(
                title="测试动画",
                url="https://example.com/video",
                platform="tencent",
                platform_display="腾讯视频",
                score=99.0,
            )
        ]

        with patch("server.search_all_platforms", new=AsyncMock(return_value=[])), patch(
            "server.get_searcher"
        ) as mock_get_searcher:
            mock_searcher = AsyncMock()
            mock_searcher.search.return_value = mocked_results
            mock_get_searcher.return_value = mock_searcher

            response = client.get(
                "/api/search",
                params={"keyword": "测试动画", "platform": "tencent", "limit": 5},
            )

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["results"] == [mocked_results[0].to_dict()]

    def test_search_endpoint_still_accepts_post_requests(self):
        """保留文档中的 POST 调用方式。"""
        mocked_results = [
            SearchResult(
                title="测试动画",
                url="https://example.com/video",
                platform="tencent",
                platform_display="腾讯视频",
                score=99.0,
            )
        ]

        with patch("server.search_all_platforms", new=AsyncMock(return_value=[])), patch(
            "server.get_searcher"
        ) as mock_get_searcher:
            mock_searcher = AsyncMock()
            mock_searcher.search.return_value = mocked_results
            mock_get_searcher.return_value = mock_searcher

            response = client.post(
                "/api/search",
                json={"keyword": "测试动画", "platform": "tencent", "limit": 5},
            )

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["results"] == [mocked_results[0].to_dict()]
