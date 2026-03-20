"""
视频爬虫基类
定义所有视频平台爬虫的通用接口
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Dict
from dataclasses import dataclass, field

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback

# 模块级日志记录器
logger = logging.getLogger(__name__)


@dataclass
class VideoInfo:
    """视频信息"""
    title: str = ""
    channel: str = ""
    duration: int = 0  # 秒
    platform: str = ""
    video_id: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "channel": self.channel,
            "duration": self.duration,
            "platform": self.platform,
            "video_id": self.video_id,
            "extra": self.extra,
        }


class BaseVideoCrawler(ABC):
    """视频爬虫基类"""

    # 平台标识 (子类必须覆盖)
    PLATFORM_NAME: str = ""
    # 平台显示名称
    PLATFORM_DISPLAY_NAME: str = ""
    # URL 模式
    URL_PATTERNS: List[str] = []

    def __init__(self):
        self.page = None
        self.browser = None

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """检查是否可以处理该 URL"""
        for pattern in cls.URL_PATTERNS:
            if re.search(pattern, url):
                return True
        return False

    def _extract_video_id(self, url: str) -> Optional[str]:
        """从 URL 提取 video_id"""
        for pattern in self.URL_PATTERNS:
            match = re.search(pattern, url)
            if match:
                # 尝试提取括号中的 ID
                groups = match.groups()
                if groups:
                    return groups[0]
                # 尝试提取 video_id
                video_match = re.search(r'[Bb][Vv][1-9A-HJ-NP-Za-km-z]{10}', url)
                if video_match:
                    return video_match.group(0)
        return None

    @abstractmethod
    async def get_info(self, url: str) -> VideoInfo:
        """获取视频信息"""

    @abstractmethod
    async def get_video_urls(self, url: str) -> List[str]:
        """获取视频播放地址"""

    @abstractmethod
    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """下载视频"""

    async def start_browser(self, headless: bool = True):
        """启动浏览器"""
        if self.browser is None:
            from playwright.async_api import async_playwright
            self.pw = await async_playwright().start()
            self.browser = await self.pw.webkit.launch(headless=headless)
            self.page = await self.browser.new_page()

    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
            self.browser = None
            self.page = None
        if hasattr(self, 'pw'):
            await self.pw.stop()
            self.pw = None
