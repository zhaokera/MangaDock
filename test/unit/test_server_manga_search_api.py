from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from crawlers.manga_search import MangaSearchResult
from server import app


client = TestClient(app)


def test_manga_search_endpoint_returns_results_for_platform():
    mocked_results = [
        MangaSearchResult(
            title="海贼王",
            url="https://www.manhuagui.com/comic/1/",
            platform="manhuagui",
            platform_display="漫画柜",
        )
    ]

    with patch("server.get_manga_searcher") as mock_get_searcher:
        mock_searcher = AsyncMock()
        mock_searcher.search.return_value = mocked_results
        mock_get_searcher.return_value = mock_searcher

        response = client.get(
            "/api/search/manga",
            params={"keyword": "海贼王", "platform": "manhuagui", "limit": 5},
        )

    assert response.status_code == 200
    assert response.json()["results"] == [mocked_results[0].to_dict()]


def test_manga_search_endpoint_returns_not_implemented_for_real_manhuagui_stub():
    response = client.get(
        "/api/search/manga",
        params={"keyword": "海贼王", "platform": "manhuagui", "limit": 5},
    )

    assert response.status_code == 501
    assert "尚未实现" in response.json()["detail"]
