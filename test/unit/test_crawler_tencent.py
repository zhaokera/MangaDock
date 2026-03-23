"""腾讯视频爬虫回归测试"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawlers.tencent import TencentCrawler


@pytest.mark.asyncio
async def test_get_info_uses_domcontentloaded_for_cover_pages():
    crawler = TencentCrawler()
    crawler.page = AsyncMock()
    crawler.page.goto = AsyncMock()
    crawler.page.url = "https://v.qq.com/x/cover/mzc00200nc1cbum.html"
    crawler.page.evaluate = AsyncMock(side_effect=["火影忍者", "腾讯视频"])
    crawler.close_browser = AsyncMock()

    with patch.object(crawler, "start_browser", AsyncMock()):
        info = await crawler.get_info("https://v.qq.com/x/cover/mzc00200nc1cbum.html")

    crawler.page.goto.assert_awaited_once_with(
        "https://v.qq.com/x/cover/mzc00200nc1cbum.html",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    assert info.title == "火影忍者"
    assert info.comic_id == "mzc00200nc1cbum"


@pytest.mark.asyncio
async def test_download_uses_domcontentloaded_before_extracting_video_urls(tmp_path):
    crawler = TencentCrawler()
    crawler.page = MagicMock()
    crawler.page.goto = AsyncMock()
    crawler.page.url = "https://v.qq.com/x/cover/mzc00200nc1cbum.html"
    crawler.page.evaluate = AsyncMock(return_value="火影忍者")
    crawler.page.on = MagicMock()
    crawler.page.remove_listener = MagicMock()
    crawler.close_browser = AsyncMock()
    crawler.get_video_urls = AsyncMock(return_value=["https://cdn.example.com/main.mp4"])

    mock_response = MagicMock()
    mock_response.content = b"video-bytes"
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_process = MagicMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    with patch.object(crawler, "start_browser", AsyncMock()), patch("httpx.AsyncClient", return_value=mock_client), patch(
        "asyncio.create_subprocess_exec",
        AsyncMock(return_value=mock_process),
    ):
        output_dir = await crawler.download(
            "https://v.qq.com/x/cover/mzc00200nc1cbum.html",
            str(tmp_path),
        )

    crawler.page.goto.assert_awaited_once_with(
        "https://v.qq.com/x/cover/mzc00200nc1cbum.html",
        wait_until="domcontentloaded",
        timeout=60000,
    )
    crawler.get_video_urls.assert_awaited_once_with("https://v.qq.com/x/cover/mzc00200nc1cbum.html")
    assert Path(output_dir).name == "火影忍者_mzc00200nc1cbum"
