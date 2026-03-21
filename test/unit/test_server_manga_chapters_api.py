from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from crawlers.manga_search import MangaChapterCatalog, MangaChapterResult
from server import app


client = TestClient(app)


def test_manga_chapters_endpoint_returns_inline_catalog_payload():
    mocked_chapters = [
        MangaChapterResult(
            title="第1话",
            url="https://www.manhuagui.com/comic/1/100.html",
        )
    ]

    with patch("server.get_manga_searcher") as mock_get_searcher:
        mock_searcher = AsyncMock()
        mock_searcher.get_chapters.return_value = MangaChapterCatalog(
            title="海贼王",
            platform="manhuagui",
            platform_display="漫画柜",
            url="https://www.manhuagui.com/comic/1/",
            chapters=mocked_chapters,
        )
        mock_get_searcher.return_value = mock_searcher

        response = client.get(
            "/api/manga/chapters",
            params={"url": "https://www.manhuagui.com/comic/1/", "platform": "manhuagui"},
        )

    assert response.status_code == 200
    assert response.json()["chapters"] == [mocked_chapters[0].to_dict()]


def test_manga_chapters_endpoint_uses_real_searcher_payload_shape():
    payload = {
        "title": "海贼王",
        "platform": "manhuagui",
        "platform_display": "漫画柜",
        "url": "https://www.manhuagui.com/comic/1/",
        "chapters": [
            MangaChapterResult(
                title="第1话",
                url="https://www.manhuagui.com/comic/1/100.html",
            ),
        ],
    }

    assert payload["chapters"][0].to_dict()["title"] == "第1话"
