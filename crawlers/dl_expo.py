"""
dl-expo (www.dl-expo.com) 爬虫

站点特征：
- 播放页: /play/{vod_id}/{source-index}-{episode-index}.html
- 详情页: /voddetail/{vod_id}.html
"""

import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import config

from .base import BaseCrawler, DownloadProgress, MangaInfo, ProgressCallback
from .registry import register_crawler

logger = logging.getLogger(__name__)

_DL_EXPO_BASE_URL = "https://www.dl-expo.com"
_VIDEO_URL_PATTERN = re.compile(r'https?://[^\s"\'<>]+?(?:\.mp4|\.m3u8)(?:\?[^\s"\'<>]*)?')


@register_crawler
class DlExpoCrawler(BaseCrawler):
    PLATFORM_NAME = "dl_expo"
    PLATFORM_DISPLAY_NAME = "糯米影视"
    URL_PATTERNS = [
        r"dl-expo\.com/play/\d+/\d+-\d+\.html",
        r"dl-expo\.com/voddetail/\d+\.html",
    ]

    def _extract_ids(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        match = re.search(r"dl-expo\.com/play/(\d+)/(\d+-\d+)\.html", url)
        if match:
            return match.group(1), match.group(2)

        match = re.search(r"dl-expo\.com/voddetail/(\d+)\.html", url)
        if match:
            return match.group(1), None

        return None, None

    def _resolve_play_url(self, url: str) -> str:
        if "/play/" in url:
            return url

        vod_id, _ = self._extract_ids(url)
        if vod_id:
            return f"{_DL_EXPO_BASE_URL}/play/{vod_id}/1-1.html"

        return url

    def _extract_video_urls_from_content(self, page_content: str) -> List[str]:
        seen = set()
        urls: List[str] = []

        for match in _VIDEO_URL_PATTERN.findall(page_content or ""):
            if match in seen:
                continue
            seen.add(match)
            urls.append(match)

        return urls

    def _is_video_url(self, url: str) -> bool:
        return self.can_handle(url)

    async def get_info(self, url: str) -> MangaInfo:
        if not self._is_video_url(url):
            raise ValueError("无效的 dl-expo URL")

        await self.start_browser(headless=True)
        try:
            play_url = self._resolve_play_url(url)
            await self.page.goto(play_url, wait_until="networkidle", timeout=60000)

            vod_id, episode_id = self._extract_ids(play_url)
            if not vod_id:
                vod_id, episode_id = self._extract_ids(url)
            if not vod_id:
                raise ValueError("无法提取视频 ID")

            title = await self.page.evaluate(
                """
                () => {
                    const titleElem = document.querySelector('h1, .title, .video-title');
                    return titleElem ? titleElem.innerText.trim() : document.title.trim();
                }
                """
            )

            return MangaInfo(
                title=title or "",
                chapter=episode_id or "",
                page_count=1,
                platform=self.PLATFORM_NAME,
                comic_id=vod_id,
                episode_id=episode_id or "",
            )
        finally:
            await self.close_browser()

    async def get_image_urls(self, url: str) -> List[str]:
        return []

    async def get_video_urls(self, url: str) -> List[str]:
        if not self._is_video_url(url):
            return []

        page_content = await self.page.content()
        return self._extract_video_urls_from_content(page_content)

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> str:
        if not self._is_video_url(url):
            raise ValueError("无效的 dl-expo URL")

        await self.start_browser(headless=True)
        try:
            play_url = self._resolve_play_url(url)
            await self.page.goto(play_url, wait_until="networkidle", timeout=60000)

            vod_id, episode_id = self._extract_ids(play_url)
            if not vod_id:
                vod_id, episode_id = self._extract_ids(url)
            if not vod_id:
                raise ValueError("无法提取视频 ID")

            title = await self.page.evaluate(
                """
                () => {
                    const titleElem = document.querySelector('h1, .title, .video-title');
                    return titleElem ? titleElem.innerText.trim().replace(/[<>:"|?*]/g, '_') : 'video';
                }
                """
            )

            page_content = await self.page.content()
            video_urls = self._extract_video_urls_from_content(page_content)

            mp4_url = next((video_url for video_url in video_urls if video_url.endswith(".mp4") or ".mp4?" in video_url), None)
            if not mp4_url:
                raise ValueError("未找到 dl-expo 可下载视频地址")

            save_dir = Path(output_dir) / f"{title}_{vod_id}"
            save_dir.mkdir(parents=True, exist_ok=True)

            output_file = save_dir / f"{title}.mp4"

            import httpx

            async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
                resp = await client.get(mp4_url)
                resp.raise_for_status()
                output_file.write_bytes(resp.content)

            logger.info("视频已下载到: %s", output_file)

            await self._emit_progress(
                progress_callback,
                DownloadProgress(
                    current=1,
                    total=1,
                    message="下载完成",
                    status="completed",
                ),
            )

            return str(save_dir)
        finally:
            await self.close_browser()
