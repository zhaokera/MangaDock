"""爱奇艺爬虫回归测试"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawlers.iqiyi import IqiyiCrawler


class TestIqiyiVideoUrlExtraction:
    """Test extracting playable video URLs from page content."""

    def test_extract_video_urls_strips_trailing_javascript(self):
        crawler = IqiyiCrawler()
        page_content = '''
            "video":"https://static-d.iqiyi.com/lequ/20250926/e030ccddd25146628f9bf832cac18db2.mp4":i(96215),className:s.alertVideo
        '''

        assert crawler._extract_video_urls_from_content(page_content) == [
            "https://static-d.iqiyi.com/lequ/20250926/e030ccddd25146628f9bf832cac18db2.mp4"
        ]

    def test_select_download_url_rejects_static_preview_assets(self):
        crawler = IqiyiCrawler()
        urls = [
            "https://static-d.iqiyi.com/lequ/20250926/e030ccddd25146628f9bf832cac18db2.mp4",
        ]

        assert crawler._select_download_url(urls) is None

    def test_select_download_url_strips_trailing_encoded_javascript(self):
        crawler = IqiyiCrawler()
        urls = [
            "https://video.example.com/main.mp4%22:i(96215),className:s.alertVideo",
        ]

        assert crawler._select_download_url(urls) == "https://video.example.com/main.mp4"


@pytest.mark.asyncio
async def test_download_uses_browser_context_headers_for_real_video_urls(tmp_path):
    crawler = IqiyiCrawler()
    captured_handlers = {}

    async def emit_video_api_response(*_args, **_kwargs):
        response = SimpleNamespace(
            url="https://data.video.iqiyi.com/v.f4v?random=1",
            status=200,
            json=AsyncMock(return_value={
                "l": "https://n1cloudcdnct.inter.71edge.com/v.f4v?uuid=test",
            }),
        )
        await captured_handlers["response"](response)

    crawler.page = MagicMock()
    crawler.page.on = MagicMock(side_effect=lambda event, handler: captured_handlers.setdefault(event, handler))
    crawler.page.remove_listener = MagicMock()
    crawler.page.goto = AsyncMock(side_effect=emit_video_api_response)
    crawler.page.url = "https://www.iqiyi.com/v_124xt5vkn24.html"
    crawler.page.evaluate = AsyncMock(return_value="video")
    crawler.close_browser = AsyncMock()
    crawler.context = SimpleNamespace(
        request=SimpleNamespace(
            get=AsyncMock(
                return_value=SimpleNamespace(
                    status=200,
                    body=AsyncMock(return_value=b"x" * 120000),
                )
            )
        )
    )

    with patch.object(crawler, "start_browser", AsyncMock()), patch("crawlers.iqiyi.asyncio.sleep", new=AsyncMock()):
        output_dir = await crawler.download(
            "https://www.iqiyi.com/tvg/to_page_url?album_id=test",
            str(tmp_path),
        )

    crawler.context.request.get.assert_awaited_once()
    request_url = crawler.context.request.get.await_args.args[0]
    request_headers = crawler.context.request.get.await_args.kwargs["headers"]

    assert request_url == "https://n1cloudcdnct.inter.71edge.com/v.f4v?uuid=test"
    assert request_headers["Referer"] == "https://www.iqiyi.com/v_124xt5vkn24.html"
    assert request_headers["Origin"] == "https://www.iqiyi.com"
    assert request_headers["Range"] == "bytes=0-"
    assert Path(output_dir).name == "video_124xt5vkn24"
