"""
哔哩哔哩漫画 (manga.bilibili.com) 爬虫

哔哩哔哩漫画网站特点：
- URL 格式: https://manga.bilibili.com/m/detail/{comic_id}
- 需要处理反爬机制
- 图片访问需要特定的 headers 和 tokens
"""

import re
import json
import asyncio
import time
import hashlib
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config


# ============== 模块级常量 ==============

# 模块级预编译正则表达式
_COMIC_ID_PATTERN = re.compile(r'/detail/(\d+)')
_BILIBILI_API = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{[^<]+\})')
_IMG_PATTERN = re.compile(r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)')

# 默认等待配置
_BILIBILI_LOW_WAIT = 0.5  # 低优先级等待 (0.5秒)
_BILIBILI_MEDIUM_WAIT = 1.0  # 中等优先级等待 (1秒)
_BILIBILI_HIGH_WAIT = 2.0  # 高优先级等待 (2秒)
_BILIBILI_MAX_WAIT = 5.0  # 最大等待时间 (5秒)
_BILIBILI_CHECK_INTERVAL = 0.2  # 条件检查间隔 (0.2秒)


# ============== 智能等待辅助函数 ==============

async def wait_for_page_ready(page, max_wait: float = _BILIBILI_MAX_WAIT, check_interval: float = _BILIBILI_CHECK_INTERVAL) -> bool:
    """
    智能等待页面就绪，检查关键元素是否存在

    Args:
        page: Playwright page 对象
        max_wait: 最大等待时间
        check_interval: 检查间隔

    Returns:
        bool: 页面是否就绪
    """
    start_time = time.time()
    while time.time() - start_time < max_wait:
        ready = await page.evaluate('''() => {
            return document.readyState === 'complete' ||
                   document.readyState === 'interactive';
        }''')
        if ready:
            return True
        await asyncio.sleep(check_interval)
    return True  # 超时也返回 True（后续操作会处理）


async def wait_for_element(page, selector: str, timeout: float = _BILIBILI_MAX_WAIT) -> bool:
    """
    等待元素出现

    Args:
        page: Playwright page 对象
        selector: CSS 选择器
        timeout: 超时时间

    Returns:
        bool: 元素是否存在
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        exists = await page.evaluate(f'''() => {{
            return !!document.querySelector('{selector}');
        }}''')
        if exists:
            return True
        await asyncio.sleep(_BILIBILI_CHECK_INTERVAL)
    return False


@register_crawler
class BilibiliCrawler(BaseCrawler):
    """哔哩哔哩漫画爬虫"""

    PLATFORM_NAME = "bilibili"
    PLATFORM_DISPLAY_NAME = "哔哩哔哩漫画"
    URL_PATTERNS = [
        r"manga\.bilibili\.com/m/detail/\d+",
        r"www\.manga.bilibili\.com/m/detail/\d+",
    ]

    # B站 manga API 基础URL
    BASE_API = "https://manga.bilibili.com"

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id"""
        comic_match = _COMIC_ID_PATTERN.search(url)
        if comic_match:
            return int(comic_match.group(1)), None
        return None, None

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画信息"""
        comic_id, _ = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的哔哩哔哩漫画 URL")

        await self.start_browser(headless=True)

        try:
            # 访问页面
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 智能等待页面加载
            await wait_for_page_ready(self.page, max_wait=4.0, check_interval=0.3)

            # 获取漫画标题和信息
            result = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('.comic-title, h1, .title');
                    let chapterElem = document.querySelector('.chapter-name, [class*="chapter"], .quota-item');
                    let pageText = document.querySelector('[class*="page"], .page-count');

                    return {
                        title: titleElem ? titleElem.innerText.trim() : null,
                        chapter: chapterElem ? chapterElem.innerText.trim() : null,
                        pageText: pageText ? pageText.innerText : null
                    };
                }
            ''')

            # 尝试从页面中提取章节列表
            chapter_list = await self.page.evaluate('''
                () => {
                    let chapters = Array.from(document.querySelectorAll('[class*="chapter"], .quota-item, [class*="list"] li'));
                    return chapters.length;
                }
            ''')

            page_count = 0
            if result.get('pageText'):
                match = re.search(r'(\d+)', result['pageText'])
                if match:
                    page_count = int(match.group(1))

            return MangaInfo(
                title=result.get('title') or "",
                chapter=result.get('chapter') or f"第1话",
                page_count=page_count,
                platform=self.PLATFORM_NAME,
                comic_id=str(comic_id),
                episode_id="1",
            )
        finally:
            await self.close_browser()

    async def get_image_urls(self, url: str) -> List[str]:
        """提取图片URL列表"""
        page_content = await self.page.content()
        image_urls = _IMG_PATTERN.findall(page_content)
        image_urls = [url for url in image_urls if '/images/' in url or '.jpg' in url or '.png' in url or '.webp' in url]

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
        下载哔哩哔哩漫画

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        comic_id, _ = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的 URL 格式")

        await self.start_browser(headless=True)

        try:
            # 使用基类的顺序下载方法
            return await self._download_sequential(url, output_dir, progress_callback, max_retries=3)
        finally:
            await self.close_browser()
