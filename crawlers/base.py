"""
漫画爬虫基类
定义所有平台爬虫的通用接口
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, List, Callable, Any, Dict, TYPE_CHECKING, Tuple
from dataclasses import dataclass, field
from pathlib import Path

if TYPE_CHECKING:
    import httpx

# 导入 config 用于 get_http_client
import config

# 导入断点续传模块
from .resume import get_resume_manager, ResumeInfo


# 模块级日志记录器
logger = logging.getLogger(__name__)


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

# 默认 User-Agent
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 默认图片下载请求头（可被外部请求头覆盖）
DEFAULT_IMAGE_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
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


CHUNK_SIZE = 8192  # 文件下载块大小


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
        self.http_client: Optional["httpx.AsyncClient"] = None
        self.cfg = None  # 配置将在 start_browser 中初始化
        # 限速相关
        self._last_download_time: float = 0
        self._download_lock = asyncio.Lock()
        # 断点续传相关
        self._resume_manager = None
        self._resume_info: Optional[ResumeInfo] = None
        # 进度统计相关
        self._start_time: Optional[float] = None
        self._downloaded_bytes: int = 0
        self._speed_samples: List[tuple] = field(default_factory=list)  # (timestamp, bytes, cumulative)

    async def get_http_client(self) -> "httpx.AsyncClient":
        """
        获取共享的 httpx 客户端（连接池优化）
        避免为每个图片请求创建新的客户端
        """
        import httpx
        cfg = self.cfg or config.get_config()

        if self.http_client is None or self.http_client.is_closed:
            # 优化连接池配置：增加大小和 keepalive 超时
            transport = httpx.AsyncHTTPTransport(
                limits=httpx.Limits(
                    max_connections=20,  # 从 10 增加
                    max_keepalive_connections=10,  # 从 5 增加
                    keepalive_expiry=60.0  # 从 30 增加
                )
            )

            # 构建超时配置
            timeout = httpx.Timeout(
                cfg.network.timeout_connect,
                read=cfg.network.timeout_read,
                connect=cfg.network.timeout_connect,
                pool=cfg.network.timeout_connect
            )

            self.http_client = httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                transport=transport,
                headers={
                    "User-Agent": cfg.crawler.user_agent or DEFAULT_USER_AGENT,
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                }
            )
        return self.http_client

    async def close_http_client(self) -> None:
        """关闭共享的 httpx 客户端"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None

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
    async def get_image_urls(self, url: str) -> List[str]:
        """
        提取图片URL列表（子类必须实现）

        Args:
            url: 漫画章节 URL

        Returns:
            List[str]: 图片URL列表
        """
        pass

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载漫画（模板方法，提供默认实现）

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调函数

        Returns:
            str: 保存路径
        """
        # 子类可以覆盖此方法使用自定义逻辑，或使用默认模板方法
        # 默认实现：使用顺序下载策略
        return await self._download_sequential(url, output_dir, progress_callback)

    async def _download_sequential(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None,
        max_retries: int = 3
    ) -> str:
        """
        顺序下载图片（默认实现）

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调函数
            max_retries: 最大重试次数

        Returns:
            str: 保存路径
        """
        # 提取图片URL
        image_urls = await self.get_image_urls(url)
        total = len(image_urls)

        if total == 0:
            raise ValueError("下载失败[NO_IMAGES]: 未找到任何图片，请检查链接是否正确或网站结构是否变化")

        # 发送进度回调
        if progress_callback:
            progress_callback(DownloadProgress(
                current=0,
                total=total,
                message=f"准备下载 {total} 张图片...",
                status="downloading"
            ))

        # 创建保存目录
        save_dir = Path(output_dir) / f"download_{int(time.time())}"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 顺序下载
        success_count = 0
        for i, img_url in enumerate(image_urls, 1):
            try:
                ext = self._get_image_extension(img_url)
                filepath = save_dir / f"{i:03d}{ext}"

                if await self.download_image(img_url, filepath, max_retries=max_retries):
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
                logger.error(f"下载失败 [URL: {img_url[:60]}...]: {type(e).__name__}: {e}")

        logger.info(f"下载完成: {success_count}/{total}")
        return str(save_dir)

    async def _download_concurrent(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None,
        max_concurrent: int = 5,
        max_retries: int = 3
    ) -> str:
        """
        并发下载图片

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调函数
            max_concurrent: 最大并发数
            max_retries: 最大重试次数

        Returns:
            str: 保存路径
        """
        # 提取图片URL
        image_urls = await self.get_image_urls(url)
        total = len(image_urls)

        if total == 0:
            raise ValueError("下载失败[NO_IMAGES]: 未找到任何图片，请检查链接是否正确或网站结构是否变化")

        # 发送进度回调
        if progress_callback:
            progress_callback(DownloadProgress(
                current=0,
                total=total,
                message=f"准备下载 {total} 张图片...",
                status="downloading"
            ))

        # 创建保存目录
        save_dir = Path(output_dir) / f"download_{int(time.time())}"
        save_dir.mkdir(parents=True, exist_ok=True)

        # 并发下载
        success_count = await self.download_images_batch(
            url_filepairs=[
                (img_url, save_dir / f"{i:03d}{self._get_image_extension(img_url)}")
                for i, img_url in enumerate(image_urls, 1)
            ],
            max_concurrent=max_concurrent,
            progress_callback=progress_callback,
            total=total
        )

        logger.info(f"并发下载完成: {success_count}/{total} 张图片")
        return str(save_dir)

    def _get_image_extension(self, url: str) -> str:
        """
        根据URL获取图片扩展名

        Args:
            url: 图片URL

        Returns:
            str: 扩展名
        """
        if ".webp" in url.lower():
            return ".webp"
        elif ".png" in url.lower():
            return ".png"
        elif ".gif" in url.lower():
            return ".gif"
        return ".jpg"

    async def start_browser(self, headless: bool = True) -> None:
        """启动浏览器"""
        import httpx
        import config
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("请先安装 playwright: pip install playwright && playwright install chromium")

        # 从配置获取浏览器启动参数
        cfg = config.get_config()
        browser_args = cfg.crawler.browser_args

        # 先保存到局部变量，成功后再赋值给实例变量
        playwright = None
        browser = None
        context = None
        page = None

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=headless,
                channel="chrome",
                args=browser_args
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=cfg.crawler.user_agent or DEFAULT_USER_AGENT
            )
            page = await context.new_page()
        except Exception:
            # 资源清理：如果后续步骤失败，关闭已创建的资源
            if page:
                await page.close()
            if context:
                await context.close()
            if browser:
                await browser.close()
            if playwright:
                await playwright.stop()
            raise

        # 成功后赋值给实例变量
        self.playwright = playwright
        self.browser = browser
        self.context = context
        self.page = page

        # 保存配置供后续使用
        self.cfg = self.cfg or config.get_config()

        # 初始化 http 客户端（连接池复用）
        self.http_client = await self.get_http_client()

    async def close_browser(self):
        """关闭浏览器"""
        await self.close_http_client()
        # 按相反顺序关闭资源
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None

    async def download_image(self, url: str, filepath: Path, headers: Optional[dict] = None, max_retries: int = 5) -> bool:
        """
        下载单张图片（带重试机制，指数退避，限速）

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
                default_headers = DEFAULT_IMAGE_HEADERS.copy()
                if headers:
                    default_headers.update(headers)

                # 指数退避延迟：使用配置的参数
                if attempt > 1:
                    cfg = self.cfg or config.get_config()
                    delay = cfg.network.retry_initial_delay * (cfg.network.retry_exponential_base ** (attempt - 2))
                    delay = min(delay, cfg.network.retry_max_delay)
                    logger.debug(f"图片下载等待 {delay:.1f}s 后重试 (尝试 {attempt}/{max_retries})...")
                    await asyncio.sleep(delay)

                # 应用下载限速（防止请求过快被封禁）
                await self._apply_rate_limit()

                # 使用共享的 httpx 客户端（连接池优化）
                client = await self.get_http_client()
                async with client.stream("GET", url, headers=default_headers) as response:
                    if response.status_code == 200:
                        # 验证内容类型
                        content_type = response.headers.get("Content-Type", "")
                        if not content_type.startswith(("image/", "application/octet-stream")):
                            logger.warning(f"收到非图片内容 {content_type} (URL: {url[:60]}...)")
                            return False

                        # 流式写入文件
                        with filepath.open('wb') as f:
                            async for chunk in response.aiter_bytes(CHUNK_SIZE):
                                f.write(chunk)
                        return True
                    else:
                        last_error = Exception(f"HTTP {response.status_code}")
                        logger.error(f"图片下载失败 (尝试 {attempt}/{max_retries}): HTTP {response.status_code}, URL: {url[:60]}...")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                logger.error(f"图片下载异常 (尝试 {attempt}/{max_retries}): {type(e).__name__}, URL: {url[:60]}")
        logger.error(f"图片下载最终失败: {last_error}, URL: {url[:60]}")
        return False

    async def download_image_via_browser(self, url: str, filepath: Path, referer: str = "", max_retries: int = 5) -> bool:
        """
        使用浏览器上下文下载图片（保持会话状态，带重试机制，指数退避，限速）

        Args:
            url: 图片 URL
            filepath: 保存路径
            referer: 来源页面 URL
            max_retries: 最大重试次数

        Returns:
            bool: 是否成功
        """
        if not self.page or not self.context:
            return False

        import httpx
        cfg = self.cfg or config.get_config()

        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # 应用下载限速（防止请求过快被封禁）
                await self._apply_rate_limit()

                # 使用关键字参数传递超时（兼容新版 httpx）
                timeout = httpx.Timeout(
                    connect=cfg.network.timeout_connect,
                    read=cfg.network.timeout_read,
                    write=cfg.network.timeout_download,
                    pool=cfg.network.timeout_connect
                )

                # 使用 context.request 发送请求
                browser_headers = DEFAULT_IMAGE_HEADERS.copy()
                browser_headers['Referer'] = referer
                response = await self.context.request.get(url, headers=browser_headers, timeout=timeout)

                if response.ok:
                    # 流式写入文件，不缓存到内存
                    with filepath.open('wb') as f:
                        async for chunk in response.iter_bytes(CHUNK_SIZE):
                            f.write(chunk)
                    return True
                else:
                    last_error = Exception(f"HTTP {response.status}")
                    logger.error(f"浏览器请求下载失败 (尝试 {attempt}/{max_retries}): status={response.status}, URL: {url[:60]}...")

            except asyncio.CancelledError:
                raise
            except Exception as e:
                last_error = e
                logger.error(f"浏览器下载异常 (尝试 {attempt}/{max_retries}): {type(e).__name__}, URL: {url[:60]}")

                # 指数退避延迟：使用配置的参数
                if attempt < max_retries:
                    delay = cfg.network.retry_initial_delay * (cfg.network.retry_exponential_base ** (attempt - 1))
                    delay = min(delay, cfg.network.retry_max_delay)
                    logger.debug(f"浏览器下载等待 {delay:.1f}s 后重试...")
                    await asyncio.sleep(delay)

        logger.error(f"浏览器下载最终失败: {last_error}, URL: {url[:60]}")
        return False

    async def _apply_rate_limit(self) -> None:
        """
        应用下载限速（基于配置的下载间隔）
        防止请求过快被网站封禁
        """
        if not self.cfg:
            return

        # 从配置获取下载间隔，默认 0.3 秒
        download_delay = getattr(self.cfg.crawler, 'download_delay', 0.3)

        async with self._download_lock:
            current_time = time.monotonic()
            elapsed = current_time - self._last_download_time

            if elapsed < download_delay:
                wait_time = download_delay - elapsed
                logger.debug(f"限速等待 {wait_time:.2f}s (间隔: {download_delay}s)")
                await asyncio.sleep(wait_time)

            self._last_download_time = time.monotonic()

    def sanitize_filename(self, name: str, max_length: int = 80) -> str:
        """清理文件名"""
        import re
        safe_name = re.sub(r'[\\/*?:"<>|]', "", name)
        return safe_name[:max_length]

    async def download_images_batch(
        self,
        url_filepairs: List[tuple[str, Path]],
        max_concurrent: int = 5,
        progress_callback=None,
        total=0
    ) -> int:
        """
        批量并行下载图片

        Args:
            url_filepairs: (url, filepath) 元组列表
            max_concurrent: 最大并发数
            progress_callback: 进度回调函数
            total: 总数（用于进度显示）

        Returns:
            int: 成功下载的数量
        """
        if not url_filepairs:
            return 0

        success_count = 0
        semaphore = asyncio.Semaphore(max_concurrent)

        async def download_with_semaphore(url: str, filepath: Path):
            """带信号量的下载"""
            async with semaphore:
                return await self.download_image(url, filepath)

        # 创建所有下载任务
        tasks = [
            download_with_semaphore(url, filepath)
            for url, filepath in url_filepairs
        ]

        # 执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计结果
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"图片下载异常 {url_filepairs[i][0]}: {result}")
            elif result:
                success_count += 1

            # 发送进度回调
            if progress_callback:
                current = i + 1
                progress_stats = {
                    "current": current,
                    "total": total or len(url_filepairs),
                    "message": f"下载中 {current}/{total or len(url_filepairs)}",
                    "success_count": success_count,
                }
                # 添加速度和ETA信息
                progress_stats.update(self._calculate_progress_stats(current, total or len(url_filepairs)))
                progress_callback(progress_stats)

        return success_count

    def _calculate_progress_stats(self, current: int, total: int) -> dict:
        """
        计算进度统计信息（速度、ETA等）

        Args:
            current: 当前完成数
            total: 总数

        Returns:
            dict: 进度统计信息
        """
        result = {}

        if self._start_time is None:
            return result

        elapsed = time.monotonic() - self._start_time

        # 计算平均速度
        if elapsed > 0 and self._downloaded_bytes > 0:
            avg_speed = self._downloaded_bytes / elapsed
            result["avg_speed_bytes"] = avg_speed
            result["avg_speed_str"] = self._format_speed(avg_speed)

            # 计算剩余时间和ETA
            if total > 0 and current > 0:
                eta_seconds = (total - current) * (elapsed / current)
                result["eta_seconds"] = eta_seconds
                result["eta_str"] = self._format_eta(eta_seconds)

        # 添加完成百分比
        if total > 0:
            result["percentage"] = int(current / total * 100)

        return result

    def _format_speed(self, bytes_per_second: float) -> str:
        """格式化速度显示"""
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.1f} B/s"
        elif bytes_per_second < 1024 * 1024:
            return f"{bytes_per_second / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"

    def _format_eta(self, seconds: float) -> str:
        """格式化ETA显示"""
        if seconds <= 0:
            return "--:--"
        elif seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}:{minutes:02d}"

    async def login(
        self,
        credentials: Dict[str, str],
        browser_factory: Optional[Callable] = None
    ) -> bool:
        """
        登录平台（可选方法，子类可覆盖）

        Args:
            credentials: 登录凭据 (username, password等)
            browser_factory: 浏览器工厂函数

        Returns:
            bool: 登录是否成功
        """
        # 默认实现：检查必要的凭据
        if not credentials:
            return False
        username = credentials.get('username') or credentials.get('user_id')
        password = credentials.get('password')
        if not username or not password:
            return False
        # 子类应该覆盖此方法实现具体的登录逻辑
        logger.warning(f"平台 [{self.PLATFORM_NAME}] 未实现登录逻辑，使用默认登录")
        return False

    async def logout(self) -> bool:
        """
        登出平台（可选方法，子类可覆盖）

        Returns:
            bool: 登出是否成功
        """
        # 默认实现：不做任何操作
        return True

    async def enable_resume(self, task_id: str, url: str, platform: str, total: int = 0) -> None:
        """
        启用断点续传

        Args:
            task_id: 任务ID
            url: 漫画URL
            platform: 平台名称
            total: 总页数
        """
        self._resume_manager = get_resume_manager()
        self._resume_info = await self._resume_manager.load_progress(task_id)

        if self._resume_info is None:
            # 创建新的进度记录
            self._resume_info = ResumeInfo(
                task_id=task_id,
                url=url,
                platform=platform,
                total=total,
            )
        else:
            logger.info(f"恢复断点续传: {task_id} (已下载 {self._resume_info.downloaded_count}/{self._resume_info.total})")

    async def get_downloaded_urls(self) -> List[str]:
        """获取已下载的URL列表"""
        if self._resume_info:
            return self._resume_info.downloaded_urls.copy()
        return []

    async def update_resume_progress(self, total: int, downloaded: int, success: int, failed: int,
                                      downloaded_urls: List[str], failed_urls: Dict[str, str]):
        """更新断点续传进度"""
        if self._resume_info and self._resume_manager:
            self._resume_info.update_progress(total, downloaded, success, failed)
            self._resume_info.downloaded_urls = downloaded_urls
            self._resume_info.failed_urls = failed_urls
            await self._resume_manager.save_progress(self._resume_info)

    async def disable_resume(self, task_id: str) -> None:
        """禁用断点续传，清理进度"""
        if self._resume_manager:
            await self._resume_manager.remove_progress(task_id)