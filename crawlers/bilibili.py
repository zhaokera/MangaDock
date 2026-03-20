"""
哔哩哔哩漫画/动漫 (manga.bilibili.com /(video.bilibili.com)) 爬虫

哔哩哔哩平台特点：
- 漫画 URL 格式: https://manga.bilibili.com/m/detail/{comic_id}
- 动漫 URL 格式: https://www.bilibili.com/bilibili/video/{bv_id}
- 需要处理反爬机制
- 图片/视频访问需要特定的 headers 和 tokens
"""

import re
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
# BV号/AV号模式
_BV_ID_PATTERN = re.compile(r'[Bb][Vv][Aa]?[1-9A-HJ-NP-Za-km-z]{10}')
_AV_ID_PATTERN = re.compile(r'av(\d+)')
# 动漫视频 API
_BILIBILI_VIDEO_API = "https://api.bilibili.com/x/web-interface/view"
_BILIBILI_PLAY_URL = "https://www.bilibili.com/video/"

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
    """哔哩哔哩漫画/动漫爬虫"""

    PLATFORM_NAME = "bilibili"
    PLATFORM_DISPLAY_NAME = "哔哩哔哩漫画/动漫"
    URL_PATTERNS = [
        r"manga\.bilibili\.com/m/detail/\d+",
        r"www\.manga.bilibili\.com/m/detail/\d+",
        r"bilibili\.com/bilibili/video/[Bb][Vv]",
        r"bilibili\.com/video/[Bb][Vv]",
        r"www\.bilibili\.com/video/[Bb][Vv]",
    ]

    # B站 manga API 基础URL
    BASE_API = "https://manga.bilibili.com"
    # B站视频 API
    VIDEO_API = "https://api.bilibili.com/x/web-interface/view"

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 或 video_id"""
        # 尝试提取漫画 ID
        comic_match = _COMIC_ID_PATTERN.search(url)
        if comic_match:
            return int(comic_match.group(1)), None

        # 尝试提取 BV 号
        bv_match = _BV_ID_PATTERN.search(url)
        if bv_match:
            return None, bv_match.group(0)

        # 尝试提取 AV 号
        av_match = _AV_ID_PATTERN.search(url)
        if av_match:
            return int(av_match.group(1)), None

        return None, None

    def _is_video_url(self, url: str) -> bool:
        """判断是否为视频 URL"""
        return bool(_BV_ID_PATTERN.search(url) or _AV_ID_PATTERN.search(url))

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画或动漫信息"""
        # 检查是否为视频 URL
        if self._is_video_url(url):
            return await self._get_video_info(url)

        comic_id, _ = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的哔哩哔哩 URL")

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

    async def _get_video_info(self, url: str) -> MangaInfo:
        """获取视频信息"""
        import httpx

        video_id = self._extract_ids(url)[1]
        if not video_id:
            raise ValueError("无效的视频 URL")

        async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
            resp = await client.get(f"{self.VIDEO_API}?bvid={video_id}")
            data = resp.json()

            if data.get('code') != 0:
                raise ValueError(f"获取视频信息失败: {data.get('message')}")

            view = data.get('data', {})
            return MangaInfo(
                title=view.get('title', ''),
                chapter=view.get('tname', ''),
                page_count=1,
                platform=self.PLATFORM_NAME,
                comic_id=video_id,
                episode_id="1",
                extra={"video_info": view}
            )

    async def get_image_urls(self, url: str) -> List[str]:
        """提取图片URL列表或视频播放地址"""
        # 如果是视频URL，返回空列表（视频下载单独处理）
        if self._is_video_url(url):
            return []

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

    async def get_video_urls(self, url: str) -> List[str]:
        """获取视频播放地址"""
        if not self._is_video_url(url):
            return []

        import httpx
        import re

        video_id = self._extract_ids(url)[1]
        if not video_id:
            raise ValueError("无效的视频 URL")

        async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
            resp = await client.get(f"{self.VIDEO_API}?bvid={video_id}")
            data = resp.json()

            if data.get('code') != 0:
                raise ValueError(f"获取视频信息失败: {data.get('message')}")

            view = data.get('data', {})
            cid = view.get('cid')

            # 获取播放地址
            play_url = f"https://api.bilibili.com/x/player/wbi/playurl?bvid={video_id}&cid={cid}"
            resp2 = await client.get(play_url)
            play_data = resp2.json()

            if play_data.get('code') != 0:
                raise ValueError(f"获取播放地址失败: {play_data.get('message')}")

            # 获取视频质量
            durls = play_data.get('data', {}).get('durl', [])
            return [d.get('url') for d in durls if d.get('url')]

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载哔哩哔哩漫画或动漫视频

        Args:
            url: 漫画章节或视频 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        # 判断是视频还是漫画
        if self._is_video_url(url):
            return await self._download_video(url, output_dir, progress_callback)

        comic_id, _ = self._extract_ids(url)
        if not comic_id:
            raise ValueError("无效的 URL 格式")

        await self.start_browser(headless=True)

        try:
            # 使用基类的顺序下载方法
            return await self._download_sequential(url, output_dir, progress_callback, max_retries=3)
        finally:
            await self.close_browser()

    async def _download_video(self, url: str, output_dir: str, progress_callback: Optional[ProgressCallback] = None) -> str:
        """
        下载哔哩哔哩视频

        Args:
            url: 视频 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        import httpx
        from pathlib import Path

        video_id = self._extract_ids(url)[1]
        if not video_id:
            raise ValueError("无效的视频 URL")

        await self.start_browser(headless=True)

        try:
            # 获取视频信息
            async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
                resp = await client.get(f"{self.VIDEO_API}?bvid={video_id}")
                data = resp.json()

                if data.get('code') != 0:
                    raise ValueError(f"获取视频信息失败: {data.get('message')}")

                view = data.get('data', {})
                title = view.get('title', 'video')
                cid = view.get('cid')

            # 获取播放地址
            play_url = f"https://api.bilibili.com/x/player/wbi/playurl?bvid={video_id}&cid={cid}"
            async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
                resp2 = await client.get(play_url)
                play_data = resp2.json()

                if play_data.get('code') != 0:
                    raise ValueError(f"获取播放地址失败: {play_data.get('message')}")

                durls = play_data.get('data', {}).get('durl', [])
                if not durls:
                    raise ValueError("未找到视频播放地址")

                video_url = durls[0].get('url')
                size = durls[0].get('size', 0)

            # 下载视频
            save_dir = Path(output_dir) / f"{title}_{video_id}"
            save_dir.mkdir(parents=True, exist_ok=True)

            output_file = save_dir / f"{title}.mp4"

            async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
                resp3 = await client.get(video_url)
                resp3.raise_for_status()

                with open(output_file, 'wb') as f:
                    f.write(resp3.content)

            logger.info(f"视频已下载到: {output_file}")

            if progress_callback:
                await progress_callback(DownloadProgress(
                    current=1,
                    total=1,
                    message="下载完成",
                    status="completed"
                ))

            return str(save_dir)

        finally:
            await self.close_browser()

