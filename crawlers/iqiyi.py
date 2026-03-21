"""
爱奇艺 (iqiyi.com) 爬虫

爱奇艺网站特点：
- URL 格式: https://www.iqiyi.com/v_{video_id}.html
- 使用 flv/f4v 视频格式
- 需要处理反爬机制
"""

import re
import asyncio
import logging
from typing import Optional, List
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config

logger = logging.getLogger(__name__)


# ============== 模块级常量 ==============

# URL 模式
_IQIYI_PATTERN = re.compile(r'iqiyi\.com/v_[a-zA-Z0-9]+\.html')
_IQIYI_COMIC_PATTERN = re.compile(r'iqiyi\.com[/a-zA-Z]*[_-]([a-zA-Z0-9]+)\.html')
_IQIYI_REDIRECT_PATTERN = re.compile(r'iqiyi\.com/tvg/to_page_url\?.+')

# 爱奇艺 API
_IQIYI_API_BASE = "https://www.iqiyi.com"
_IQIYI_PREVIEW_ASSET_PATTERN = re.compile(r"https?://static-d\.iqiyi\.com/lequ/", re.IGNORECASE)


@register_crawler
class IqiyiCrawler(BaseCrawler):
    """爱奇艺爬虫"""

    PLATFORM_NAME = "iqiyi"
    PLATFORM_DISPLAY_NAME = "爱奇艺"
    URL_PATTERNS = [
        r"iqiyi\.com/v_[a-zA-Z0-9]+\.html",
        r"iqiyi\.com/d_[a-zA-Z0-9]+\.html",
        r"iqiyi\.com/p/[a-zA-Z0-9]+\.html",
        r"iqiyi\.com/tvg/to_page_url\?.+",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 video_id"""
        # 尝试提取标准 URL 格式 v_id
        match = re.search(r'iqiyi\.com/v_([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        # 尝试提取 d_id 格式
        match = re.search(r'iqiyi\.com/d_([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        # 尝试提取 p 格式
        match = re.search(r'iqiyi\.com/p/([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        if "iqiyi.com/tvg/to_page_url" in url:
            parsed = parse_qs(urlparse(url).query)
            return None, parsed.get("album_id", [None])[0] or parsed.get("tv_id", [None])[0]

        return None, None

    def _is_video_url(self, url: str) -> bool:
        """判断是否为视频 URL"""
        return bool(_IQIYI_PATTERN.search(url) or _IQIYI_COMIC_PATTERN.search(url) or _IQIYI_REDIRECT_PATTERN.search(url))

    async def get_info(self, url: str) -> MangaInfo:
        """获取视频信息"""
        if not self._is_video_url(url):
            raise ValueError("无效的爱奇艺 URL")

        await self.start_browser(headless=True)

        try:
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 等待页面加载
            await asyncio.sleep(3)

            video_id = self._extract_ids(self.page.url)[1] or self._extract_ids(url)[1]
            if not video_id:
                raise ValueError("无法提取视频 ID")

            # 获取视频标题
            title = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('.video-title, h1, .MalbumTit');
                    return titleElem ? titleElem.innerText.trim() : null;
                }
            ''')

            # 获取频道/频道信息
            channel = await self.page.evaluate('''
                () => {
                    let channelElem = document.querySelector('.m-picinfo-channel, .channel-name, [class*="channel"]');
                    return channelElem ? channelElem.innerText.trim() : null;
                }
            ''')

            return MangaInfo(
                title=title or "",
                chapter=channel or "",
                page_count=1,
                platform=self.PLATFORM_NAME,
                comic_id=video_id,
                episode_id="1",
            )
        finally:
            await self.close_browser()

    async def get_image_urls(self, url: str) -> List[str]:
        """提取图片URL列表"""
        return []

    def _extract_video_urls_from_content(self, page_content: str) -> List[str]:
        pattern = re.compile(r'https?://[^\s"\'<>]+?(?:\.flv|\.f4v|\.mp4)(?:\?[^\s"\'<>]*)?')
        seen = set()
        urls = []

        for match in pattern.findall(page_content):
            if match in seen:
                continue
            seen.add(match)
            urls.append(match)

        return urls[:5]

    def _clean_video_url(self, url: str) -> str:
        cleaned = url.strip()
        cleaned = re.sub(r'(%22|["\']).*$', '', cleaned, flags=re.IGNORECASE)
        media_match = re.search(r'https?://[^\s"\'<>]+?\.(?:flv|f4v|mp4)(?:\?[^\s"\'<>]*)?', cleaned, re.IGNORECASE)
        if media_match:
            return media_match.group(0)
        return cleaned

    def _select_download_url(self, urls: List[str]) -> Optional[str]:
        for url in urls:
            cleaned = self._clean_video_url(url)
            if not cleaned:
                continue
            if _IQIYI_PREVIEW_ASSET_PATTERN.search(cleaned):
                continue
            return cleaned

        return None

    async def get_video_urls(self, url: str) -> List[str]:
        """获取视频播放地址"""
        if not self._is_video_url(url):
            return []

        # 爱奇艺视频地址通常在页面的 JavaScript 中
        page_content = await self.page.content()

        return self._extract_video_urls_from_content(page_content)

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载爱奇艺视频

        Args:
            url: 视频 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        if not self._is_video_url(url):
            raise ValueError("无效的爱奇艺 URL")

        await self.start_browser(headless=True)

        try:
            await self.page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)

            video_id = self._extract_ids(self.page.url)[1] or self._extract_ids(url)[1]
            if not video_id:
                raise ValueError("无法提取视频 ID")

            # 获取视频信息
            title = await self.page.evaluate('''
                () => {
                    let elem = document.querySelector('.video-title, h1, .MalbumTit');
                    return elem ? elem.innerText.trim().replace(/[<>:"|?*]/g, '_') : 'video';
                }
            ''')

            # 获取视频 URL
            video_urls = await self.get_video_urls(url)

            if not video_urls:
                raise ValueError("未找到视频播放地址")

            # 下载视频
            save_dir = Path(output_dir) / f"{title}_{video_id}"
            save_dir.mkdir(parents=True, exist_ok=True)

            output_file = save_dir / f"{title}.mp4"

            # 使用 httpx 下载
            import httpx

            async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
                video_url = self._select_download_url(video_urls)
                if not video_url:
                    raise ValueError("未找到可下载的爱奇艺正片地址")

                resp = await client.get(video_url)
                resp.raise_for_status()

                with open(output_file, 'wb') as f:
                    f.write(resp.content)

            logger.info(f"视频已下载到: {output_file}")

            if progress_callback:
                await self._emit_progress(progress_callback, DownloadProgress(
                    current=1,
                    total=1,
                    message="下载完成",
                    status="completed"
                ))

            return str(save_dir)

        finally:
            await self.close_browser()
