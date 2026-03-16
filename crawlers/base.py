"""
漫画爬虫基类
定义所有平台爬虫的通用接口
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MangaInfo:
    """漫画信息"""
    title: str = ""
    chapter: str = ""
    page_count: int = 0
    platform: str = ""
    comic_id: str = ""
    episode_id: str = ""
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "chapter": self.chapter,
            "page_count": self.page_count,
            "platform": self.platform,
            "comic_id": self.comic_id,
            "episode_id": self.episode_id,
            "extra": self.extra,
        }


@dataclass
class DownloadProgress:
    """下载进度"""
    current: int = 0
    total: int = 0
    message: str = ""
    status: str = "pending"  # pending, downloading, completed, failed

    def to_dict(self) -> dict:
        return {
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "status": self.status,
        }


# 进度回调类型
ProgressCallback = Callable[[DownloadProgress], None]


class BaseCrawler(ABC):
    """漫画爬虫基类"""

    # 平台标识 (子类必须覆盖)
    PLATFORM_NAME: str = ""
    # 平台显示名称
    PLATFORM_DISPLAY_NAME: str = ""
    # URL 匹配模式 (子类必须覆盖)
    URL_PATTERNS: List[str] = []

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """
        检查是否可以处理此 URL

        Args:
            url: 漫画章节 URL

        Returns:
            bool: 是否支持该 URL
        """
        import re
        for pattern in cls.URL_PATTERNS:
            if re.search(pattern, url):
                return True
        return False

    @abstractmethod
    async def get_info(self, url: str) -> MangaInfo:
        """
        获取漫画信息

        Args:
            url: 漫画章节 URL

        Returns:
            MangaInfo: 漫画信息
        """
        pass

    @abstractmethod
    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载漫画

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调函数

        Returns:
            str: 保存路径
        """
        pass

    async def start_browser(self, headless: bool = True):
        """启动浏览器"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("请先安装 playwright: pip install playwright && playwright install chromium")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            channel="chrome"
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()

    async def close_browser(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def download_image(self, url: str, filepath: Path, headers: Optional[dict] = None, max_retries: int = 3) -> bool:
        """
        下载单张图片（带重试机制）

        Args:
            url: 图片 URL
            filepath: 保存路径
            headers: 请求头
            max_retries: 最大重试次数

        Returns:
            bool: 是否成功
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("请先安装 httpx: pip install httpx")

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # 浏览器级别的请求头
                default_headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"macOS"',
                    "Sec-Fetch-Dest": "image",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "cross-site",
                }
                if headers:
                    default_headers.update(headers)

                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    response = await client.get(url, headers=default_headers)
                    if response.status_code == 200 and len(response.content) > 0:
                        filepath.write_bytes(response.content)
                        return True
            except Exception as e:
                last_error = e
                print(f"下载图片失败 (尝试 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5)  # 等待0.5秒后重试
        print(f"图片下载最终失败: {last_error}")
        return False

    async def download_image_via_browser(self, url: str, filepath: Path, referer: str = "", max_retries: int = 3) -> bool:
        """
        使用浏览器上下文下载图片（保持会话状态，带重试机制）

        Args:
            url: 图片 URL
            filepath: 保存路径
            referer: 来源页面 URL
            max_retries: 最大重试次数

        Returns:
            bool: 是否成功
        """
        if not self.page:
            return False

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # 方法1: 使用 page.request (Playwright 的请求上下文)
                # 这会共享浏览器的 cookies 和存储
                from playwright.async_api import Request

                # 使用 context.request 发送请求
                response = await self.context.request.get(url, headers={
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Referer': referer
                }, timeout=60000)  # 60 seconds timeout (针对 hamreus.com 服务器慢的问题)

                if response.ok:
                    body = await response.body()
                    if len(body) > 0:
                        filepath.write_bytes(body)
                        return True
                else:
                    print(f"浏览器请求下载失败 (尝试 {attempt}/{max_retries}): status={response.status}")

            except Exception as e:
                last_error = e
                print(f"浏览器下载异常 (尝试 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(0.5)  # 等待0.5秒后重试

        print(f"浏览器下载最终失败: {last_error}")
        return False

    def sanitize_filename(self, name: str, max_length: int = 80) -> str:
        """清理文件名"""
        import re
        safe_name = re.sub(r'[\\/*?:"<>|]', "", name)
        return safe_name[:max_length]