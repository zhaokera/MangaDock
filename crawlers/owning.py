"""
Owining 漫画 (owning.com) 爬虫

Owining 漫画网站特点：
- URL 格式: https://www.owning.com/comic/{comic_id}/{episode_id}.html
- 国际漫画平台
- 图片通过 JavaScript 加载
"""

import re
import logging
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
from .utils import wait_for_page_ready, wait_for_element, extract_comic_id, extract_episode_id
import config

logger = logging.getLogger(__name__)

# ============== 模块级常量 ==============

# 模块级预编译正则表达式
_IMG_PATTERN = re.compile(r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)')
_COMIC_ID_PATTERN = re.compile(r'/comic/(\d+)')
_OWNING_PATTERN = re.compile(r'https?://[^.]+\.owning\.com')


@register_crawler
class OwiningCrawler(BaseCrawler):
    """Owining 漫画爬虫"""

    PLATFORM_NAME = "owning"
    PLATFORM_DISPLAY_NAME = "Owining 漫画"
    URL_PATTERNS = [
        r"owning\.com/comic/\d+/\d+\.html",
        r"www\.owning\.com/comic/\d+/\d+\.html",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 和 episode_id"""
        comic_id = extract_comic_id(url)
        if comic_id:
            episode_id = extract_episode_id(url)
            if episode_id:
                try:
                    return int(comic_id), int(episode_id)
                except ValueError:
                    return int(comic_id), episode_id
        return None, None

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画信息"""
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的 Owining 漫画 URL")

        await self.start_browser(headless=True)

        try:
            # 访问页面
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 智能等待页面加载
            await wait_for_page_ready(self.page, max_wait=3.0, check_interval=0.3)

            # 获取漫画标题
            comic_title = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('h1, .comic-title, .title, [class*="title"]');
                    return titleElem ? titleElem.innerText.trim() : null;
                }
            ''')

            # 获取章节标题
            chapter_title = await self.page.evaluate('''
                () => {
                    let chapterElem = document.querySelector('[class*="chapter"], .chapter-name, h2, .quota-name');
                    return chapterElem ? chapterElem.innerText.trim() : null;
                }
            ''')

            # 获取页数
            page_count = await self.page.evaluate('''
                () => {
                    let pageSelect = document.querySelector('select, .page-select, [class*="page"]');
                    if (pageSelect && pageSelect.options.length > 0) {
                        return pageSelect.options.length;
                    }
                    let pageText = document.querySelector('[class*="page"], .page-count');
                    if (pageText) {
                        let match = pageText.innerText.match(/(\d+)/);
                        return match ? parseInt(match[1]) : 0;
                    }
                    return 0;
                }
            ''')

            return MangaInfo(
                title=comic_title or "",
                chapter=chapter_title or "",
                page_count=page_count or 0,
                platform=self.PLATFORM_NAME,
                comic_id=str(comic_id),
                episode_id=str(episode_id),
            )
        finally:
            await self.close_browser()

    async def get_image_urls(self, url: str) -> List[str]:
        """提取图片URL列表"""
        page_content = await self.page.content()
        image_urls = _IMG_PATTERN.findall(page_content)

        # 过滤出实际的图片URL
        image_urls = [
            url for url in image_urls
            if '/images/' in url or '.jpg' in url or '.png' in url or '.webp' in url
        ]

        # 去重
        image_urls = list(dict.fromkeys(image_urls))

        total = len(image_urls)

        if total == 0:
            # 通过JavaScript获取图片
            image_urls = await self.page.evaluate('''
                () => {
                    let imgs = Array.from(document.querySelectorAll('img'));
                    return imgs.map(img => img.src).filter(url => url && (url.includes('.jpg') || url.includes('.png') || url.includes('.webp')));
                }
            ''')
            total = len(image_urls)

        if total == 0:
            raise ValueError("下载失败[NO_IMAGES]: 未找到任何图片，请检查链接是否正确或网站结构是否变化")

        logger.info(f"找到 {total} 张图片")
        return image_urls

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载 Owining 漫画

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的 URL 格式")

        await self.start_browser(headless=True)

        try:
            # 使用基类的顺序下载方法
            return await self._download_sequential(url, output_dir, progress_callback, max_retries=3)
        finally:
            await self.close_browser()
