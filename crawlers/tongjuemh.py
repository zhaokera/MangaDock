"""
番茄漫画 (tongjuemh.com) 爬虫

番茄漫画网站特点：
- URL 格式: https://www.tongjuemh.com/comic/{comic_id}/{episode_id}.html
- 图片通过 JavaScript 加载
- 与其他平台类似
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
_EPISODE_ID_PATTERN = re.compile(r'/comic/\d+/\d+\.html')
_TJMH_PATTERN = re.compile(r'https?://[^.]+\.tongjuemh\.com')


@register_crawler
class TongjuemhCrawler(BaseCrawler):
    """番茄漫画爬虫"""

    PLATFORM_NAME = "tongjuemh"
    PLATFORM_DISPLAY_NAME = "番茄漫画"
    URL_PATTERNS = [
        r"tongjuemh\.com/comic/\d+/\d+\.html",
        r"www\.tongjuemh\.com/comic/\d+/\d+\.html",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 和 episode_id"""
        comic_match = _COMIC_ID_PATTERN.search(url)
        if comic_match:
            # 番茄漫画的episode_id在URL中可能格式不同
            episode_match = re.search(r'/comic/\d+/(.+)\.html', url)
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
            raise ValueError("无效的番茄漫画 URL")

        await self.start_browser(headless=True)

        try:
            # 访问页面
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 等待页面加载
            await asyncio.sleep(2)

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
                    // 尝试从页码选择器获取
                    let pageSelect = document.querySelector('select, .page-select, [class*="page'] select');
                    if (pageSelect && pageSelect.options.length > 0) {
                        return pageSelect.options.length;
                    }
                    // 尝试从页码文本获取
                    let pageText = document.querySelector('[class*="page"], .page-count, [class*="page"] span');
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
                episode_id=str(episode_id) if isinstance(episode_id, int) else episode_id,
            )
        finally:
            await self.close_browser()

    async def _do_download(
        self,
        url: str,
        comic_id,
        episode_id,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """执行下载"""
        save_dir = Path(output_dir) / f"{comic_id}_{episode_id}"
        save_dir.mkdir(parents=True, exist_ok=True)

        total = 0
        image_urls = []

        # 获取图片URL列表
        try:
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
        下载番茄漫画

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
            return await self._do_download(url, comic_id, episode_id, output_dir, progress_callback)
        finally:
            await self.close_browser()
