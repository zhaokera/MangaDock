"""
哔哩哔哩漫画爬虫
"""

import re
from typing import Optional
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler


@register_crawler
class BilibiliCrawler(BaseCrawler):
    """哔哩哔哩漫画爬虫"""

    PLATFORM_NAME = "bilibili"
    PLATFORM_DISPLAY_NAME = "哔哩哔哩漫画"
    URL_PATTERNS = [
        r"manga\.bilibili\.com/mc\d+/\d+",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 和 episode_id"""
        match = re.search(r'/mc(\d+)/(\d+)', url)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画信息"""
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id or not episode_id:
            raise ValueError("无效的哔哩哔哩漫画 URL")

        return MangaInfo(
            title="",
            chapter="",
            page_count=0,
            platform=self.PLATFORM_NAME,
            comic_id=str(comic_id),
            episode_id=str(episode_id),
        )

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载漫画章节

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        await self.start_browser(headless=True)

        try:
            return await self._do_download(url, output_dir, progress_callback)
        finally:
            await self.close_browser()

    async def _do_download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """执行下载"""

        def report(progress: DownloadProgress):
            if progress_callback:
                progress_callback(progress)

        # 提取 ID
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id or not episode_id:
            raise ValueError("无效的 URL 格式")

        report(DownloadProgress(message="解析漫画信息...", status="downloading"))

        manga_info = MangaInfo(
            platform=self.PLATFORM_NAME,
            comic_id=str(comic_id),
            episode_id=str(episode_id),
        )

        # 拦截响应
        image_urls = []
        episode_info = {}
        image_index_data = None

        async def handle_response(response):
            nonlocal episode_info, image_index_data
            resp_url = str(response.url)

            # 拦截图片请求
            if any(ext in resp_url.lower() for ext in ['.jpg', '.png', '.webp', '.avif']):
                if ('manga' in resp_url or 'hdslb' in resp_url) and 'token=' in resp_url:
                    image_urls.append(resp_url)

            # 拦截 GetEpisode 响应
            if "GetEpisode" in resp_url:
                try:
                    data = await response.json()
                    if data.get("code") == 0:
                        episode_info = data.get("data", {})
                except:
                    pass

            # 拦截 GetImageIndex 响应
            if "GetImageIndex" in resp_url:
                try:
                    data = await response.json()
                    if data.get("code") == 0:
                        image_index_data = data.get("data", {})
                except:
                    pass

        self.page.on("response", handle_response)

        # 访问页面
        report(DownloadProgress(message="正在加载页面...", status="downloading"))
        await self.page.goto(url, wait_until="networkidle")
        await self.page.wait_for_timeout(5000)

        # 等待 GetImageIndex
        for _ in range(10):
            if image_index_data:
                break
            await self.page.wait_for_timeout(500)

        # 获取图片数量
        total_images = 0
        if image_index_data:
            total_images = len(image_index_data.get("images", []))

        # 滚动加载所有图片
        report(DownloadProgress(message="加载图片列表...", status="downloading"))
        containers = await self.page.query_selector_all('[class*="image-item"], [class*="page-item"]')

        for container in containers:
            try:
                await container.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(100)
            except:
                pass

        await self.page.wait_for_timeout(3000)

        # 获取标题
        comic_title = episode_info.get("comic_title", f"漫画{comic_id}")
        chapter_title = episode_info.get("title", f"第{episode_id}话")

        manga_info.title = comic_title
        manga_info.chapter = chapter_title

        if not image_urls:
            raise Exception("未找到图片，可能需要登录")

        # 去重排序
        image_urls = sorted(list(set(image_urls)))
        total = len(image_urls)

        manga_info.page_count = total

        # 创建保存目录
        safe_title = self.sanitize_filename(f"{comic_title}_{chapter_title}")
        save_dir = Path(output_dir) / safe_title
        save_dir.mkdir(parents=True, exist_ok=True)

        # 下载图片
        success_count = 0
        for i, img_url in enumerate(image_urls, 1):
            ext = ".jpg"
            if ".avif" in img_url:
                ext = ".avif"
            elif ".webp" in img_url:
                ext = ".webp"
            elif ".png" in img_url:
                ext = ".png"

            filename = f"{i:03d}{ext}"
            filepath = save_dir / filename

            headers = {
                "Referer": "https://manga.bilibili.com/",
            }

            if await self.download_image(img_url, filepath, headers):
                success_count += 1

            report(DownloadProgress(
                current=i,
                total=total,
                message=f"下载中 {i}/{total}",
                status="downloading"
            ))

        report(DownloadProgress(
            current=total,
            total=total,
            message=f"下载完成! 共 {success_count} 张图片",
            status="completed"
        ))

        return str(save_dir)