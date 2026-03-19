"""
搜狗漫画 (sogou.dmzj.com) 爬虫

搜狗漫画网站特点：
- URL 格式: https://sogou.dmzj.com/comic/{comic_id}/{episode_id}.shtml
- 使用国际域名 dmzj.com
- 图片通过 JavaScript 加载
"""

import re
import json
import asyncio
import time
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config


# ============== 模块级常量 ==============

# 模块级预编译正则表达式
_IMG_PATTERN = re.compile(r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)')
_COMIC_ID_PATTERN = re.compile(r'/comic/(\d+)')
_EPISODE_ID_PATTERN = re.compile(r'/comic/\d+/(.+)\.shtml')
_SOGOU_PATTERN = re.compile(r'https?://[^.]+\.dmzj\.com')

# 默认等待配置
_SOGOU_LOW_WAIT = 0.5  # 低优先级等待 (0.5秒)
_SOGOU_MEDIUM_WAIT = 1.0  # 中等优先级等待 (1秒)
_SOGOU_HIGH_WAIT = 2.0  # 高优先级等待 (2秒)
_SOGOU_MAX_WAIT = 5.0  # 最大等待时间 (5秒)
_SOGOU_CHECK_INTERVAL = 0.2  # 条件检查间隔 (0.2秒)


# ============== 智能等待辅助函数 ==============

async def wait_for_page_ready(page, max_wait: float = _SOGOU_MAX_WAIT, check_interval: float = _SOGOU_CHECK_INTERVAL) -> bool:
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


async def wait_for_element(page, selector: str, timeout: float = _SOGOU_MAX_WAIT) -> bool:
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
        await asyncio.sleep(_SOGOU_CHECK_INTERVAL)
    return False


@register_crawler
class SogouCrawler(BaseCrawler):
    """搜狗漫画爬虫"""

    PLATFORM_NAME = "sogou"
    PLATFORM_DISPLAY_NAME = "搜狗漫画"
    URL_PATTERNS = [
        r"sogou\.dmzj\.com/comic/\d+/\d+\.shtml",
        r"www\.sogou\.dmzj\.com/comic/\d+/\d+\.shtml",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 和 episode_id"""
        comic_match = _COMIC_ID_PATTERN.search(url)
        if comic_match:
            # 搜狗漫画的episode_id在URL中可能格式不同
            episode_match = re.search(r'/comic/\d+/(.+)\.shtml', url)
            if episode_match:
                episode_str = episode_match.group(1)
                # 尝试转换为数字
                try:
                    return int(comic_match.group(1)), int(episode_str)
                except ValueError:
                    return int(comic_match.group(1)), episode_str
        return None, None

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画信息"""
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的搜狗漫画 URL")

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
        下载搜狗漫画

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
            # 使用基类的并发下载方法
            return await self._download_sequential(url, output_dir, progress_callback, max_retries=3)
        finally:
            await self.close_browser()
