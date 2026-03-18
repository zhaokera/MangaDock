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

            # 等待页面加载
            await asyncio.sleep(3)

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

    async def _do_download(
        self,
        url: str,
        comic_id: int,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """执行下载"""
        save_dir = Path(output_dir) / f"bili_{comic_id}"
        save_dir.mkdir(parents=True, exist_ok=True)

        total = 0
        image_urls = []

        try:
            page_content = await self.page.content()

            # 解析图片URL
            image_urls = _IMG_PATTERN.findall(page_content)
            image_urls = [url for url in image_urls if '/images/' in url or '.jpg' in url or '.png' in url]

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

        except Exception as e:
            logger.error(f"解析图片URL失败: {e}")

        if total == 0:
            raise ValueError("未找到任何图片")

        logger.info(f"找到 {total} 张图片")

        # 发送进度回调
        if progress_callback:
            progress_callback(DownloadProgress(
                current=0,
                total=total,
                message=f"准备下载 {total} 张图片...",
                status="downloading"
            ))

        # 下载图片
        success_count = 0
        for i, img_url in enumerate(image_urls, 1):
            try:
                ext = ".jpg"
                if ".webp" in img_url.lower():
                    ext = ".webp"
                elif ".png" in img_url.lower():
                    ext = ".png"

                filepath = save_dir / f"{i:03d}{ext}"

                if await self.download_image(img_url, filepath, max_retries=3):
                    success_count += 1

                # 发送进度回调
                if progress_callback:
                    progress_callback(DownloadProgress(
                        current=i,
                        total=total,
                        message=f"下载中 {i}/{total}",
                        status="downloading"
                    ))

            except Exception as e:
                logger.error(f"下载失败 {img_url}: {e}")

        logger.info(f"下载完成: {success_count}/{total}")

        return str(save_dir)

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
            return await self._do_download(url, comic_id, output_dir, progress_callback)
        finally:
            await self.close_browser()
