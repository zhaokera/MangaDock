"""
爱奇艺 (iqiyi.com) 爬虫

爱奇艺网站特点：
- URL 格式: https://www.iqiyi.com/v_{video_id}.html
- 使用 HLS (M3U8) 分段视频流
- 需要处理反爬机制和 DRM 保护

注意事项：
- 爱奇艺的完整视频需要通过 API 获取播放地址
- 视频流是分段的 TS 文件，需要使用 ffmpeg 进行下载和拼接
"""

import re
import asyncio
import logging
from typing import Optional, List
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import aiofiles

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config

logger = logging.getLogger(__name__)


# ============== 模块级常量 ==============

# URL 模式
_IQIYI_PATTERN = re.compile(r'iqiyi\.com/v_[a-zA-Z0-9]+\.html')
_IQIYI_COMIC_PATTERN = re.compile(r'iqiyi\.com[/a-zA-Z]*[_-]([a-zA-Z0-9]+)\.html')
_IQIYI_REDIRECT_PATTERN = re.compile(r'iqiyi\.com/tvg/to_page_url\?.+')

# 爱奇艺 API
_IQIYI_API_BASE = "https://www.iqiyi.com"
_IQIYI_PREVIEW_ASSET_PATTERN = re.compile(r"https?://static-d\.iqiyi\.com/lequ/", re.IGNORECASE)


@register_crawler
class IqiyiCrawler(BaseCrawler):
    """爱奇艺爬虫"""

    PLATFORM_NAME = "iqiyi"
    PLATFORM_DISPLAY_NAME = "爱奇艺"
    URL_PATTERNS = [
        r"iqiyi\.com/v_[a-zA-Z0-9]+\.html",
        r"iqiyi\.com/d_[a-zA-Z0-9]+\.html",
        r"iqiyi\.com/p/[a-zA-Z0-9]+\.html",
        r"iqiyi\.com/tvg/to_page_url\?.+",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 video_id"""
        # 尝试提取标准 URL 格式 v_id
        match = re.search(r'iqiyi\.com/v_([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        # 尝试提取 d_id 格式
        match = re.search(r'iqiyi\.com/d_([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        # 尝试提取 p 格式
        match = re.search(r'iqiyi\.com/p/([a-zA-Z0-9]+)\.html', url)
        if match:
            return None, match.group(1)

        if "iqiyi.com/tvg/to_page_url" in url:
            parsed = parse_qs(urlparse(url).query)
            return None, parsed.get("album_id", [None])[0] or parsed.get("tv_id", [None])[0]

        return None, None

    def _is_video_url(self, url: str) -> bool:
        """判断是否为视频 URL"""
        return bool(_IQIYI_PATTERN.search(url) or _IQIYI_COMIC_PATTERN.search(url) or _IQIYI_REDIRECT_PATTERN.search(url))

    async def get_info(self, url: str) -> MangaInfo:
        """获取视频信息"""
        if not self._is_video_url(url):
            raise ValueError("无效的爱奇艺 URL")

        await self.start_browser(headless=True)

        try:
            await self.page.goto(url, wait_until="networkidle", timeout=60000)

            # 等待页面加载
            await asyncio.sleep(3)

            video_id = self._extract_ids(self.page.url)[1] or self._extract_ids(url)[1]
            if not video_id:
                raise ValueError("无法提取视频 ID")

            # 获取视频标题
            title = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('.video-title, h1, .MalbumTit');
                    return titleElem ? titleElem.innerText.trim() : null;
                }
            ''')

            # 获取频道/频道信息
            channel = await self.page.evaluate('''
                () => {
                    let channelElem = document.querySelector('.m-picinfo-channel, .channel-name, [class*="channel"]');
                    return channelElem ? channelElem.innerText.trim() : null;
                }
            ''')

            return MangaInfo(
                title=title or "",
                chapter=channel or "",
                page_count=1,
                platform=self.PLATFORM_NAME,
                comic_id=video_id,
                episode_id="1",
            )
        finally:
            await self.close_browser()

    async def get_image_urls(self, url: str) -> List[str]:
        """提取图片URL列表"""
        return []

    def _extract_video_urls_from_content(self, page_content: str) -> List[str]:
        pattern = re.compile(r'https?://[^\s"\'<>]+?(?:\.flv|\.f4v|\.mp4)(?:\?[^\s"\'<>]*)?')
        seen = set()
        urls = []

        for match in pattern.findall(page_content):
            if match in seen:
                continue
            seen.add(match)
            urls.append(match)

        return urls[:5]

    def _clean_video_url(self, url: str) -> str:
        cleaned = url.strip()
        cleaned = re.sub(r'(%22|["\']).*$', '', cleaned, flags=re.IGNORECASE)
        media_match = re.search(r'https?://[^\s"\'<>]+?\.(?:flv|f4v|mp4)(?:\?[^\s"\'<>]*)?', cleaned, re.IGNORECASE)
        if media_match:
            return media_match.group(0)
        return cleaned

    def _select_download_url(self, urls: List[str]) -> Optional[str]:
        logger.info(f"_select_download_url 收到 {len(urls)} 个 URL")
        for i, url in enumerate(urls):
            logger.info(f"检查 URL {i}: {url[:100]}...")
            cleaned = self._clean_video_url(url)
            logger.info(f"  - 清理后: {cleaned[:100]}..." if cleaned else "  - 清理后为空")
            if not cleaned:
                logger.info(f"  - 跳过: 空 URL")
                continue
            if _IQIYI_PREVIEW_ASSET_PATTERN.search(cleaned):
                logger.info("  - 跳过: 预览静态资源")
                continue
            logger.info(f"  - 选择此 URL: {cleaned[:80]}...")
            return cleaned

        logger.info("_select_download_url 未找到可用 URL")
        return None

    def _build_video_request_headers(self, referer: str) -> dict:
        parsed = urlparse(referer)
        origin = _IQIYI_API_BASE
        if parsed.scheme and parsed.netloc:
            origin = f"{parsed.scheme}://{parsed.netloc}"

        user_agent = config.DEFAULT_HEADERS["User-Agent"]
        if self.cfg and self.cfg.crawler.user_agent:
            user_agent = self.cfg.crawler.user_agent

        return {
            "User-Agent": user_agent,
            "Accept": "*/*",
            "Accept-Language": config.DEFAULT_HEADERS["Accept-Language"],
            "Referer": referer,
            "Origin": origin,
            "Range": "bytes=0-",
        }

    async def get_video_urls(self, url: str) -> List[str]:
        """获取视频播放地址"""
        if not self._is_video_url(url):
            return []

        logger.info(f"开始捕获爱奇艺视频 URL: {url}")

        video_urls = []

        # 设置页面请求拦截，捕获所有响应
        async def handle_response(response):
            try:
                resp_url = response.url
                # 检查是否为视频 URL
                if '.flv' in resp_url or '.f4v' in resp_url or '.mp4' in resp_url:
                    # 排除广告和样式文件
                    if not any(x in resp_url for x in ['ad_', 'ads', 'style', 'asset', 'static', 'index.html', 'preview']):
                        # 排除预览素材
                        if not _IQIYI_PREVIEW_ASSET_PATTERN.search(resp_url):
                            final_url = resp_url
                            if final_url and final_url.startswith('http'):
                                video_urls.append(final_url)
                                logger.info(f"捕获到视频 URL: {final_url[:80]}...")
            except Exception as e:
                logger.debug(f"处理响应时出错: {e}")

        # 注册响应处理器
        self.page.on('response', handle_response)

        try:
            # 等待页面加载并执行
            await asyncio.sleep(8)

            # 移除处理器
            self.page.remove_listener('response', handle_response)
        except Exception:
            try:
                self.page.remove_listener('response', handle_response)
            except Exception:
                pass

        # 去重
        unique_urls = list(dict.fromkeys(video_urls))

        logger.info(f"捕获到 {len(unique_urls)} 个唯一的视频 URL")
        for u in unique_urls[:3]:
            logger.info(f"视频 URL 示例: {u[:80]}...")

        return unique_urls[:10]

    async def _get_video_url_with_ffmpeg(self, url: str) -> Optional[str]:
        """
        使用 Playwright 获取视频 URL，然后使用 ffmpeg 下载

        爱奇艺使用两层重定向系统：
        1. data.video.iqiyi.com 返回 JSON 重定向信息
        2. JSON 中的 'l' 字段指向真正的视频文件
        """
        logger.info("开始获取爱奇艺视频 URL...")

        try:
            # 导航到页面
            await self.page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(8)

            # 捕获所有响应，查找视频文件
            video_urls = []

            def handle_response(response):
                try:
                    resp_url = response.url
                    # 检查是否为视频文件
                    if any(ext in resp_url for ext in ['.f4v', '.ts', '.flv', '.mp4']):
                        # 排除广告和预览
                        if not any(x in resp_url for x in ['ad_', 'ads', 'preview', 'asset', 'static-d']):
                            video_urls.append(resp_url)
                            logger.info(f"捕获到视频 URL: {resp_url[:80]}...")
                except Exception as e:
                    logger.debug(f"处理响应时出错: {e}")

            self.page.on('response', handle_response)

            # 等待页面加载和视频资源加载
            await asyncio.sleep(2)
            self.page.remove_listener('response', handle_response)

            if not video_urls:
                logger.warning("未找到视频 URL")
                return None

            logger.info(f"捕获到 {len(video_urls)} 个视频 URL")

            # 获取视频 URL 的重定向信息
            # 第一次请求返回 JSON，包含 'l' 字段指向真实视频 URL
            first_url = video_urls[0]
            logger.info(f"获取重定向信息: {first_url[:60]}...")

            try:
                response = await self.page.request.get(first_url, timeout=10000)
                if response.ok:
                    data = await response.json()
                    logger.info(f"重定向响应: {str(data)[:200]}")

                    # 从 JSON 中获取真实视频 URL
                    real_url = data.get('l') or data.get('location') or data.get('redirect')
                    if real_url:
                        logger.info(f"真实视频 URL: {real_url[:60]}...")
                        return real_url
                else:
                    logger.error(f"重定向请求失败: {response.status}")
            except Exception as e:
                logger.error(f"获取重定向信息失败: {e}")

            # 如果上述方法失败，返回第一个捕获的 URL
            logger.warning("使用原始 URL（可能无法直接下载）")
            return video_urls[0]

        except Exception as e:
            logger.error(f"获取视频 URL 失败: {e}")
            return None

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载爱奇艺视频

        直接通过浏览器下载视频流，避免时间限制问题

        Args:
            url: 视频 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        if not self._is_video_url(url):
            raise ValueError("无效的爱奇艺 URL")

        logger.info(f"开始下载爱奇艺视频: {url}")

        await self.start_browser(headless=True)

        try:
            # 在goto之前就设置拦截器，捕获data.video.iqiyi.com的响应
            video_responses = []

            async def handle_response(resp):
                try:
                    u = resp.url
                    if '.f4v' in u or '.flv' in u:
                        if 'data.video.iqiyi.com' in u:
                            video_responses.append(resp)
                            logger.info(f"捕获到爱奇艺视频响应: {u[:80]}...")
                except:
                    pass

            self.page.on('response', handle_response)

            logger.info("正在导航到页面...")
            await self.page.goto(url, wait_until="networkidle", timeout=60000)
            await asyncio.sleep(3)
            logger.info(f"页面加载完成，当前 URL: {self.page.url}")

            # 移除处理器
            self.page.remove_listener('response', handle_response)

            video_id = self._extract_ids(self.page.url)[1] or self._extract_ids(url)[1]
            if not video_id:
                raise ValueError("无法提取视频 ID")

            # 获取视频标题
            title = await self.page.evaluate('''
                () => {
                    let elem = document.querySelector('.video-title, h1, .MalbumTit');
                    return elem ? elem.innerText.trim().replace(/[<>:"|?*]/g, '_') : 'video';
                }
            ''')
            logger.info(f"视频标题: {title}")

            # 获取视频 URL（使用 Playwright 捕获）
            logger.info("开始获取视频 URL...")

            logger.info(f"捕获到 {len(video_responses)} 个爱奇艺视频响应")

            # Get redirect info from video APIs
            # 爱奇艺有多个API endpoint：
            # 1. data.video.iqiyi.com - 返回直接视频URL，但容易过期
            # 2. pcw-data.video.iqiyi.com - 返回重定向URL，更稳定
            # 优先使用pcw-data API
            redirect_data = None
            for resp in video_responses:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        # 优先选择pcw-data.video.iqiyi.com的响应
                        if 'pcw-data.video.iqiyi.com' in resp.url and data.get('l'):
                            redirect_data = data
                            logger.info(f"使用 pcw-data.video.iqiyi.com API")
                            break
                        elif 'data.video.iqiyi.com' in resp.url and data.get('l') and not redirect_data:
                            # data.video.iqiyi.com 作为备选
                            redirect_data = data
                            logger.info(f"使用 data.video.iqiyi.com API (备选)")
                    except:
                        continue

            if not redirect_data:
                raise ValueError("无法获取视频播放地址")

            # 从重定向数据中获取真实视频URL
            # 该URL是时间限制的，所以我们需要立即通过浏览器下载
            real_video_url = redirect_data.get('l')
            if not real_video_url:
                raise ValueError("无法获取真实视频URL")

            logger.info(f"真实视频 URL: {real_video_url[:60]}...")

            # 下载视频 - 直接通过浏览器下载
            save_dir = Path(output_dir) / f"{title}_{video_id}"
            save_dir.mkdir(parents=True, exist_ok=True)

            output_file = save_dir / f"{title}.mp4"

            logger.info(f"开始下载视频到: {output_file}")
            logger.info(f"视频URL: {real_video_url[:80]}...")

            # 真实媒体地址会校验来源站点，下载时必须保留浏览器上下文和请求头。
            try:
                if not self.context:
                    raise ValueError("浏览器上下文不可用")

                download_headers = self._build_video_request_headers(self.page.url)
                logger.info("使用 context.request.get 下载视频内容...")
                video_resp = await self.context.request.get(
                    real_video_url,
                    headers=download_headers,
                    timeout=120000,
                )

                if video_resp.status in (200, 206):
                    video_bytes = await video_resp.body()
                    logger.info(f"获取到视频内容，大小: {len(video_bytes)} 字节")

                    # 检查文件大小是否合理（至少应该有几百KB）
                    if len(video_bytes) < 100000:
                        logger.warning(f"视频文件大小异常: {len(video_bytes)} 字节，可能是错误页面")

                    # 保存视频文件
                    async with aiofiles.open(output_file, 'wb') as f:
                        await f.write(video_bytes)
                    logger.info(f"视频已下载到: {output_file}")
                else:
                    logger.error(f"获取视频失败: {video_resp.status}")
                    raise ValueError(f"视频下载失败: HTTP {video_resp.status}")
            except Exception as e:
                logger.error(f"使用 context.request.get 失败: {e}")
                raise ValueError(f"视频下载失败: {e}")

            if progress_callback:
                await self._emit_progress(progress_callback, DownloadProgress(
                    current=1,
                    total=1,
                    message="下载完成",
                    status="completed"
                ))

            return str(save_dir)

        finally:
            await self.close_browser()
