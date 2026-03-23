from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from server import app


client = TestClient(app)


class TestParseApi:
    def test_parse_endpoint_returns_normalized_payload(self):
        crawler = SimpleNamespace(
            PLATFORM_NAME="tencent",
            PLATFORM_DISPLAY_NAME="腾讯视频",
            get_info=AsyncMock(
                return_value=SimpleNamespace(
                    comic_id="cid-1",
                    episode_id="ep-1",
                )
            ),
        )

        with patch("server.get_crawler", return_value=crawler):
            response = client.post(
                "/api/parse",
                json={"url": "https://v.qq.com/x/cover/demo.html"},
            )

        assert response.status_code == 200
        assert response.json() == {
            "platform": "tencent",
            "platform_name": "腾讯视频",
            "comic_id": "cid-1",
            "episode_id": "ep-1",
            "url": "https://v.qq.com/x/cover/demo.html",
        }
