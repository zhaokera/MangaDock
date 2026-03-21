"""dl-expo 爬虫单元测试"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from crawlers.dl_expo import DlExpoCrawler


def test_can_handle_play_and_detail_urls():
    assert DlExpoCrawler.can_handle("https://www.dl-expo.com/play/101100/2-1.html")
    assert DlExpoCrawler.can_handle("https://www.dl-expo.com/voddetail/101100.html")


def test_extract_ids_from_play_url():
    crawler = DlExpoCrawler()
    assert crawler._extract_ids("https://www.dl-expo.com/play/101100/2-1.html") == ("101100", "2-1")


def test_extract_video_urls_strips_trailing_javascript():
    crawler = DlExpoCrawler()
    html = 'player_aaaa={"url":"https://cdn.example.com/video/index.m3u8","from":"line1"};'
    assert crawler._extract_video_urls_from_content(html) == ["https://cdn.example.com/video/index.m3u8"]


@pytest.mark.asyncio
async def test_download_reports_completion_with_sync_progress_callback(tmp_path):
    crawler = DlExpoCrawler()
    crawler.page = AsyncMock()
    crawler.page.goto = AsyncMock()
    crawler.page.content = AsyncMock(
        return_value=(
            'player_aaaa={"url":"https://cdn.example.com/video/index.mp4","from":"line1"};'
            'player_bbbb={"url":"https://cdn.example.com/video/index.m3u8","from":"line2"};'
        )
    )
    crawler.page.evaluate = AsyncMock(return_value="dl-expo sample title")
    crawler.close_browser = AsyncMock()

    progress_events = []

    def progress_callback(progress):
        progress_events.append(progress.status)

    mock_response = MagicMock()
    mock_response.content = b"video-bytes"
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch.object(crawler, "start_browser", AsyncMock()), patch("httpx.AsyncClient", return_value=mock_client):
        output_dir = await crawler.download(
            "https://www.dl-expo.com/voddetail/101100.html",
            str(tmp_path),
            progress_callback=progress_callback,
        )

    assert Path(output_dir).name == "dl-expo sample title_101100"
    assert progress_events == ["completed"]
    mock_client.get.assert_awaited_once_with("https://cdn.example.com/video/index.mp4")
