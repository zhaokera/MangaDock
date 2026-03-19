"""
快看漫画 (kuaikanmanhua.com) 爬虫

快看漫画网站特点：
- URL 格式: https://www.kuaikanmanhua.com/comic/{comic_id}/{episode_id}
- 图片通过 JavaScript 加载
- 使用 Progressive Web App (PWA) 技术
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
_KEPIC_ID_PATTERN = re.compile(r'/comic/(\d+)')
_EPISODE_ID_PATTERN = re.compile(r'/comic/\d+/(\d+)')
_API_PATTERN = re.compile(r'window\.__INITIAL_STATE__\s*=\s*(\{[^<]+\})')

# 默认等待配置
_KUAIKAN_LOW_WAIT = 0.5  # 低优先级等待 (0.5秒)
_KUAIKAN_MEDIUM_WAIT = 1.0  # 中等优先级等待 (1秒)
_KUAIKAN_HIGH_WAIT = 2.0  # 高优先级等待 (2秒)
_KUAIKAN_MAX_WAIT = 5.0  # 最大等待时间 (5秒)
_KUAIKAN_CHECK_INTERVAL = 0.2  # 条件检查间隔 (0.2秒)


# ============== 智能等待辅助函数 ==============

async def wait_for_page_ready(page, max_wait: float = _KUAIKAN_MAX_WAIT, check_interval: float = _KUAIKAN_CHECK_INTERVAL) -> bool:
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


async def wait_for_element(page, selector: str, timeout: float = _KUAIKAN_MAX_WAIT) -> bool:
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
        await asyncio.sleep(_KUAIKAN_CHECK_INTERVAL)
    return False


def _is_kuaikanmanhua_image(url: str) -> bool:
    """
    检查 URL 是否为快看漫画的图片

    Args:
        url: 图片 URL

    Returns:
        bool: 是否为快看漫画图片
    """
    url_lower = url.lower()
    if not any(ext in url_lower for ext in ['.jpg', '.png', '.webp']):
        return False
    return 'kuaikanmanhua' in url_lower or 'kkmh' in url_lower


@register_crawler
class KuaikanmanhuaCrawler(BaseCrawler):
    """快看漫画爬虫"""

    PLATFORM_NAME = "kuaikanmanhua"
    PLATFORM_DISPLAY_NAME = "快看漫画"
    URL_PATTERNS = [
        r"kuaikanmanhua\.com/comic/\d+/\d+",
        r"kkmh\.com/comic/\d+/\d+",  # 备用域名
    ]

    # 图片服务器域名
    IMAGE_SERVERS = [
        "https://images.kuaikanmanhua.com",
        "https://images2.kuaikanmanhua.com",
        "https://images3.kuaikanmanhua.com",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 和 episode_id"""
        comic_match = _COMIC_ID_PATTERN.search(url)
        episode_match = _EPISODE_ID_PATTERN.search(url)
        if comic_match and episode_match:
            return int(comic_match.group(1)), int(episode_match.group(1))
        return None, None

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画信息"""
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id or not episode_id:
            raise ValueError("无效的快看漫画 URL")

        await self.start_browser(headless=True)

        try:
            # 访问页面
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 智能等待页面加载
            await wait_for_page_ready(self.page, max_wait=3.0, check_interval=0.3)

            # 获取漫画标题
            comic_title = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('[class*="comicTitle"], h1, .title, .comic-title');
                    return titleElem ? titleElem.innerText.trim() : null;
                }
            ''')

            # 获取章节标题
            chapter_title = await self.page.evaluate('''
                () => {
                    let chapterElem = document.querySelector('[class*="episodeTitle"], .chapter-title, [class*="chapter"] h2');
                    return chapterElem ? chapterElem.innerText.trim() : null;
                }
            ''')

            # 获取页数（通过检查页面上的翻页元素）
            page_count = await self.page.evaluate('''
                () => {
                    // 尝试从页码选择器获取总页数
                    let pageSelect = document.querySelector('select, .page-select, [class*="page"] select');
                    if (pageSelect && pageSelect.options.length > 0) {
                        return pageSelect.options.length;
                    }

                    // 尝试从页码文本获取
                    let pageText = document.querySelector('[class*="page"], .page-count, #pageCount');
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
        """
        提取图片URL列表（使用网络拦截）

        快看漫画使用特殊的图片加载方式，需要通过网络拦截捕获图片URL。
        注意：此方法需要在页面加载前设置拦截器。
        """
        # 收集图片 URL（使用网络拦截）
        image_urls = []

        async def capture_image(response):
            resp_url = str(response.url)
            if _is_kuaikanmanhua_image(resp_url):
                image_urls.append(resp_url)

        self.page.on("response", capture_image)

        try:
            # 模拟滚动加载更多图片
            # 多次滚动触发懒加载
            for i in range(10):
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(_KUAIKAN_LOW_WAIT)

            # 等待图片加载完成 - 智能等待
            await wait_for_page_ready(self.page, max_wait=2.0, check_interval=0.2)

            # 去重但保持顺序
            unique_urls = list(dict.fromkeys(image_urls))

            # 过滤掉非图片请求（如 favicon 等）
            image_urls = [url for url in unique_urls if _is_kuaikanmanhua_image(url)]

            total = len(image_urls)

            if total == 0:
                # 尝试从页面元素直接获取
                image_urls = await self.page.evaluate('''
                    () => {
                        let imgs = Array.from(document.querySelectorAll('img'));
                        return imgs
                            .filter(img => img.src && /kuaikanmanhua|kkmh/.test(img.src))
                            .map(img => img.src);
                    }
                ''')
                image_urls = list(dict.fromkeys(image_urls))
                total = len(image_urls)

        finally:
            try:
                self.page.off("response", capture_image)
            except Exception:
                pass

        if not image_urls:
            raise Exception("下载失败[NO_IMAGES]: 未找到图片，网站结构可能已变化，请检查链接是否正确")

        logger.info(f"找到 {total} 张图片")
        return image_urls

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载快看漫画

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        comic_id, episode_id = self._extract_ids(url)
        if not comic_id or not episode_id:
            raise ValueError("无效的 URL 格式")

        await self.start_browser(headless=True)

        try:
            return await self._do_download(url, comic_id, episode_id, output_dir, progress_callback)
        finally:
            await self.close_browser()

    async def _do_download(
        self,
        url: str,
        comic_id: int,
        episode_id: int,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """执行下载"""

        def report(progress: DownloadProgress):
            if progress_callback:
                progress_callback(progress)

        # 访问页面
        report(DownloadProgress(message="正在加载页面...", status="downloading"))
        await self.page.goto(url, wait_until="networkidle", timeout=60000)

        # 智能等待页面加载完成
        await wait_for_page_ready(self.page, max_wait=4.0, check_interval=0.3)

        # 获取章节信息
        chapter_title = await self.page.evaluate('''
            () => {
                let chapterElem = document.querySelector('[class*="episodeTitle"], .chapter-title, [class*="chapter"] h2');
                return chapterElem ? chapterElem.innerText.trim() : null;
            }
        ''')

        if not chapter_title:
            chapter_title = f"第{episode_id}话"

        # 收集图片 URL（使用网络拦截）
        image_urls = []

        async def capture_image(response):
            resp_url = str(response.url)
            if _is_kuaikanmanhua_image(resp_url):
                image_urls.append(resp_url)

        self.page.on("response", capture_image)

        try:
            # 模拟滚动加载更多图片
            report(DownloadProgress(message="正在加载所有图片...", status="downloading"))

            # 多次滚动触发懒加载
            for i in range(10):
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(_KUAIKAN_LOW_WAIT)

            # 等待图片加载完成 - 智能等待
            await wait_for_page_ready(self.page, max_wait=2.0, check_interval=0.2)

            # 去重但保持顺序
            unique_urls = list(dict.fromkeys(image_urls))

            # 过滤掉非图片请求（如 favicon 等）
            image_urls = [url for url in unique_urls if _is_kuaikanmanhua_image(url)]

            total = len(image_urls)

            if total == 0:
                # 尝试从页面元素直接获取
                image_urls = await self.page.evaluate('''
                    () => {
                        let imgs = Array.from(document.querySelectorAll('img'));
                        return imgs
                            .filter(img => img.src && /kuaikanmanhua|kkmh/.test(img.src))
                            .map(img => img.src);
                    }
                ''')
                image_urls = list(dict.fromkeys(image_urls))
                total = len(image_urls)

        finally:
            try:
                self.page.off("response", capture_image)
            except Exception:
                pass

        if not image_urls:
            raise Exception("下载失败[NO_IMAGES]: 未找到图片，网站结构可能已变化，请检查链接是否正确")

        # 设置漫画标题
        manga_info = MangaInfo(
            title=f"漫画{comic_id}",
            chapter=chapter_title,
            page_count=total,
            platform=self.PLATFORM_NAME,
            comic_id=str(comic_id),
            episode_id=str(episode_id),
        )

        # 创建保存目录
        safe_title = self.sanitize_filename(f"{kuaikanmanhua}_{chapter_title}")
        save_dir = Path(output_dir) / safe_title
        save_dir.mkdir(parents=True, exist_ok=True)

        # 报告准备开始下载
        report(DownloadProgress(
            current=0,
            total=total,
            message=f"准备下载 {total} 张图片...",
            status="downloading"
        ))

        # 从配置获取并发数
        cfg = self.cfg or config.get_config()
        concurrency = cfg.download.concurrency
        max_retries = cfg.network.retry_max_attempts

        # 创建 Semaphore 限制并发数
        semaphore = asyncio.Semaphore(concurrency)

        # 使用可变对象存储计数器
        progress_counter = {'value': 0}
        progress_lock = asyncio.Lock()

        async def download_with_semaphore(img_url: str, filepath: Path, i: int, total: int) -> bool:
            """带并发限制的下载函数"""
            async with semaphore:
                ext = ".jpg"
                if ".webp" in img_url.lower():
                    ext = ".webp"
                elif ".png" in img_url.lower():
                    ext = ".png"

                headers = {
                    "Referer": url,
                }

                success = await self.download_image(
                    img_url, filepath, headers, max_retries=max_retries
                )

                # 下载完成后立即报告进度
                async with progress_lock:
                    progress_counter['value'] += 1
                    report(DownloadProgress(
                        current=progress_counter['value'],
                        total=total,
                        message=f"下载中 {progress_counter['value']}/{total}",
                        status="downloading"
                    ))

                return success

        # 创建下载任务
        tasks = []
        for i, img_url in enumerate(image_urls, 1):
            temp_filename = f"{i:03d}.tmp"
            temp_filepath = save_dir / temp_filename
            tasks.append(download_with_semaphore(img_url, temp_filepath, i, total))

        # 并发执行所有下载任务
        results = await asyncio.gather(*tasks)

        success_count = sum(results)

        # 按原始序号重命名文件
        renamed_count = 0
        for i, img_url in enumerate(image_urls, 1):
            temp_filename = f"{i:03d}.tmp"
            temp_path = save_dir / temp_filename
            if temp_path.exists():
                ext = ".jpg"
                if ".webp" in img_url.lower():
                    ext = ".webp"
                elif ".png" in img_url.lower():
                    ext = ".png"
                new_filename = f"{i:03d}{ext}"
                new_path = save_dir / new_filename
                try:
                    temp_path.rename(new_path)
                    renamed_count += 1
                except OSError as e:
                    logger.warning(f"文件重命名失败 [{temp_filename} -> {new_filename}]: {e}")
                    # 继续处理其他文件

        # 最终进度报告
        report(DownloadProgress(
            current=total,
            total=total,
            message=f"下载完成! 共 {success_count} 张图片",
            status="completed"
        ))

        return str(save_dir)

    async def _wait_for_page_ready(self, max_wait: float = 5.0, check_interval: float = 0.2) -> bool:
        """
        快看漫画特殊的页面等待逻辑
        检查页面上的关键元素是否存在
        """
        start_time = time.time()
        while time.time() - start_time < max_wait:
            elements_exist = await self.page.evaluate('''
                () => {
                    // 检查图片容器或章节内容是否存在
                    return !!document.querySelector('[class*="comicContent"], .chapter-content, #comicContainer, img.mangaFile');
                }
            ''')
            if elements_exist:
                return True
            await asyncio.sleep(check_interval)
        return True
