"""
芒果TV (mgtv.com) 爬虫

芒果TV网站特点：
- URL 格式: https://www.mgtv.com/b/{channel_id}/{video_id}.html
- 使用 hls/flv 视频格式
- 需要处理反爬机制
"""

import re
import logging
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config

logger = logging.getLogger(__name__)


# ============== 模块级常量 ==============

# URL 模式
_MGTV_PATTERN = re.compile(r'mgtv\.com/b/[a-zA-Z0-9]+/[a-zA-Z0-9]+\.html')
_MGTV_V_PATTERN = re.compile(r'mgtv\.com/v/[a-zA-Z0-9]+\.html')

# 节芒TV API
_MGTV_API_BASE = "https://www.mgtv.com"


@register_crawler
class MgtvCrawler(BaseCrawler):
    """芒果TV爬虫"""

    PLATFORM_NAME = "mango"
    PLATFORM_DISPLAY_NAME = "芒果TV"
    URL_PATTERNS = [
        r"mgtv\.com/b/[a-zA-Z0-9]+/[a-zA-Z0-9]+\.html",
        r"mgtv\.com/v/[a-zA-Z0-9]+\.html",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 video_id"""
        # 尝试提取 b 格式
        match = re.search(r'mgtv\.com/b/[a-zA-Z0-9]+/([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        # 尝试提取 v 格式
        match = re.search(r'mgtv\.com/v/([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        return None, None

    def _is_video_url(self, url: str) -> bool:
        """判断是否为视频 URL"""
        return bool(_MGTV_PATTERN.search(url) or _MGTV_V_PATTERN.search(url))

    async def get_info(self, url: str) -> MangaInfo:
        """获取视频信息"""
        if not self._is_video_url(url):
            raise ValueError("无效的芒果TV URL")

        video_id = self._extract_ids(url)[1]
        if not video_id:
            raise ValueError("无法提取视频 ID")

        await self.start_browser(headless=True)

        try:
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 等待页面加载
            await asyncio.sleep(3)

            # 获取视频标题
            title = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('.video-title, h1, .title');
                    return titleElem ? titleElem.innerText.trim() : null;
                }
            ''')

            # 获取频道/频道信息
            channel = await self.page.evaluate('''
                () => {
                    let channelElem = document.querySelector('.channel-name, .source, [class*="channel"]');
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

    async def get_video_urls(self, url: str) -> List[str]:
        """获取视频播放地址"""
        if not self._is_video_url(url):
            return []

        video_id = self._extract_ids(url)[1]
        if not video_id:
            return []

        # 芒果TV视频地址通常在页面的 JavaScript 中
        page_content = await self.page.content()

        # 尝试从页面中提取视频 URL
        video_urls = re.findall(r'https?://[^\s]+(?:\.flv|\.ts|\.mp4)[^\s]*', page_content)

        return video_urls[:5]  # 返回前5个候选地址

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载芒果TV视频

        Args:
            url: 视频 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        if not self._is_video_url(url):
            raise ValueError("无效的芒果TV URL")

        video_id = self._extract_ids(url)[1]
        if not video_id:
            raise ValueError("无法提取视频 ID")

        await self.start_browser(headless=True)

        try:
            await self.page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)

            # 获取视频信息
            title = await self.page.evaluate('''
                () => {
                    let elem = document.querySelector('.video-title, h1, .title');
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
                # 尝试第一个视频地址
                video_url = video_urls[0]
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
