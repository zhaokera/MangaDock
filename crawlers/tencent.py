"""
腾讯视频 (v.qq.com) 爬虫

腾讯视频网站特点：
- URL 格式: https://v.qq.com/x/cover/{cover_id}/{video_id}.html
- 使用 FLV/F4V 视频格式
- 需要处理反爬机制
"""

import re
import asyncio
import logging
import json
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config

logger = logging.getLogger(__name__)


# ============== 模块级常量 ==============

# URL 模式
# 支持带 .html 和不带 .html 的 URL（有的 URL 可能以 / 结尾）
_TENCENT_VIDEO_PATTERN = re.compile(r'v\.qq\.com/x/cover/[a-zA-Z0-9]+/[a-zA-Z0-9]+(?:\.html)?')
_TENCENT_COVER_PATTERN = re.compile(r'v\.qq\.com/x/cover/[a-zA-Z0-9]+(?:\.html)?')
_TENCENT_TMXJ_PATTERN = re.compile(r'v\.qq\.com/tmxj/[a-zA-Z0-9]+(?:\.html)?')
_TENCENT_BTNV_PATTERN = re.compile(r'v\.qq\.com/btnv/[a-zA-Z0-9]+(?:\.html)?')

# 腾讯视频 API
_TENCENT_API_BASE = "https://v.qq.com/x"


@register_crawler
class TencentCrawler(BaseCrawler):
    """腾讯视频爬虫"""

    PLATFORM_NAME = "tencent"
    PLATFORM_DISPLAY_NAME = "腾讯视频"
    URL_PATTERNS = [
        r"v\.qq\.com/x/cover/[a-zA-Z0-9]+/[a-zA-Z0-9]+(?:\.html)?",
        r"v\.qq\.com/x/cover/[a-zA-Z0-9]+(?:\.html)?",
        r"v\.qq\.com/tmxj/[a-zA-Z0-9]+(?:\.html)?",
        r"v\.qq\.com/btnv/[a-zA-Z0-9]+(?:\.html)?",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 video_id"""
        # 尝试提取标准 URL 格式（支持带或不带 .html）
        match = re.search(r'v\.qq\.com/x/cover/([a-zA-Z0-9]+)(?:/([a-zA-Z0-9]+))?(?:\.html)?', url)
        if match:
            return match.group(1), match.group(2)

        # 尝试提取 tmxj 格式
        match = re.search(r'v\.qq\.com/tmxj/([a-zA-Z0-9]+)(?:\.html)?', url)
        if match:
            return None, match.group(1)

        # 尝试提取 btnv 格式
        match = re.search(r'v\.qq\.com/btnv/([a-zA-Z0-9]+)(?:\.html)?', url)
        if match:
            return None, match.group(1)

        return None, None

    def _is_video_url(self, url: str) -> bool:
        """判断是否为视频 URL"""
        return bool(_TENCENT_VIDEO_PATTERN.search(url) or
                   _TENCENT_COVER_PATTERN.search(url) or
                   _TENCENT_TMXJ_PATTERN.search(url) or
                   _TENCENT_BTNV_PATTERN.search(url))

    async def get_info(self, url: str) -> MangaInfo:
        """获取视频信息"""
        if not self._is_video_url(url):
            raise ValueError("无效的腾讯视频 URL")

        await self.start_browser(headless=True)

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # 等待页面加载
            await asyncio.sleep(3)

            cover_id, video_id = self._extract_ids(self.page.url)
            video_id = video_id or self._extract_ids(url)[1] or cover_id or self._extract_ids(url)[0]
            if not video_id:
                raise ValueError("无法提取视频 ID")

            # 获取视频标题
            title = await self.page.evaluate('''
                () => {
                    let titleElem = document.querySelector('.video_title, h1, .video-name');
                    return titleElem ? titleElem.innerText.trim() : null;
                }
            ''')

            # 获取频道/频道信息
            channel = await self.page.evaluate('''
                () => {
                    let channelElem = document.querySelector('.video_author, .video-source, [class*="channel"]');
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

    async def get_video_urls(self, url: str) -> List[str]:
        """获取视频播放地址"""
        if not self._is_video_url(url):
            return []

        logger.info(f"开始捕获腾讯视频 URL: {url}")

        # 腾讯视频使用腾讯视频云播放器
        # 视频地址通过 API 动态加载，需要捕获网络请求
        video_urls = []

        # 设置页面请求拦截，捕获所有响应
        async def handle_response(response):
            try:
                resp_url = response.url
                # 检查是否为视频 URL (包括 HLS 流 .m3u8)
                if any(x in resp_url for x in ['.flv', '.f4v', '.mp4', '.m3u8']):
                    # 排除广告和样式文件
                    if not any(x in resp_url for x in ['ad_', 'ads', 'style', 'asset', 'static', 'index.html']):
                        # 尝试获取真实 URL（处理重定向后的）
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
            await asyncio.sleep(5)

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

        return unique_urls[:10]  # 返回前10个候选地址

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载腾讯视频

        Args:
            url: 视频 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        if not self._is_video_url(url):
            raise ValueError("无效的腾讯视频 URL")

        await self.start_browser(headless=True)

        try:
            # 在 goto 之前先设置 proxyhttp 响应拦截器
            proxy_responses = []

            def handle_proxy_response(response):
                try:
                    if 'proxyhttp' in response.url:
                        proxy_responses.append(response)
                        logger.info(f"捕获到 proxyhttp 响应: {response.url[:60]}...")
                except:
                    pass

            self.page.on('response', handle_proxy_response)

            # 导航到页面
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(5)  # 增加等待时间确保 API 响应完成

            # 移除处理器
            self.page.remove_listener('response', handle_proxy_response)

            cover_id, video_id = self._extract_ids(self.page.url)
            video_id = video_id or self._extract_ids(url)[1] or cover_id or self._extract_ids(url)[0]
            if not video_id:
                raise ValueError("无法提取视频 ID")

            # 获取视频信息
            title = await self.page.evaluate('''
                () => {
                    let elem = document.querySelector('.video_title, h1, .video-name');
                    return elem ? elem.innerText.trim().replace(/[<>:"|?*]/g, '_') : 'video';
                }
            ''')

            # 获取视频 URL
            logger.info("调用 get_video_urls...")
            video_urls = await self.get_video_urls(url)
            logger.info(f"get_video_urls 返回 {len(video_urls)} 个 URL")

            if not video_urls:
                logger.info("get_video_urls 返回空，尝试从 script 标签提取...")
                try:
                    # 额外尝试：获取页面中所有 script 标签的内容
                    script_urls = await self.page.evaluate('''
                        () => {
                            const scripts = Array.from(document.querySelectorAll('script'));
                            const urls = [];
                            for (const script of scripts) {
                                const content = script.innerHTML || script.textContent;
                                if (content) {
                                    // 查找包含视频 URL 的 JS 变量
                                    const matches = content.match(/["']url["']\\s*[:=]\\s*["']([^"']+(?:\\.flv|\\.f4v|\\.mp4)[^"']*)["']/g);
                                    if (matches) {
                                        matches.forEach(m => {
                                            const urlMatch = m.match(/["']([^"']+(?:\\.flv|\\.f4v|\\.mp4)[^"']*)["']/);
                                            if (urlMatch) urls.push(urlMatch[1]);
                                        });
                                    }
                                }
                            }
                            return [...new Set(urls)];
                        }
                    ''')
                    logger.info(f"script 标签提取完成，结果类型: {type(script_urls)}, 结果: {str(script_urls)[:200]}")
                    if script_urls and isinstance(script_urls, list):
                        video_urls = script_urls
                        logger.info(f"从 script 标签提取到 {len(video_urls)} 个视频 URL")
                except Exception as e:
                    logger.error(f"从 script 标签提取失败: {e}")

            # 尝试从腾讯视频 API 获取视频 URL
            logger.info("尝试从腾讯视频 API 获取视频 URL...")

            # 处理之前捕获到的 proxyhttp 响应
            if proxy_responses:
                logger.info(f"捕获到 {len(proxy_responses)} 个 proxyhttp 响应")
                for resp in proxy_responses:
                    if resp.status == 200:
                        try:
                            content = await resp.text()
                            logger.info(f"API响应长度: {len(content)}, 前100字符: {content[:100]}")

                            # 腾讯 API 返回 JSONP 格式，需要提取 JSON
                            if content.startswith('OTVPlayer.getVideoInfo'):
                                json_str = content[22:-1]  # Remove wrapper
                            else:
                                json_str = content
                            data = json.loads(json_str)

                            logger.info(f"API响应数据: errCode={data.get('errCode')}")

                            if data.get('errCode') == 0:
                                vinfo = data.get('vinfo', '{}')
                                if vinfo:
                                    vdata = json.loads(vinfo) if isinstance(vinfo, str) else vinfo

                                    # Look for video URLs in vl.vi.ul.ui.url
                                    if 'vl' in vdata and 'vi' in vdata['vl']:
                                        videos = vdata['vl']['vi']
                                        for v in videos:
                                            ul = v.get('ul', {}).get('ui', [])
                                            if ul:
                                                video_url = ul[0].get('url')
                                                if video_url:
                                                    video_urls.append(video_url)
                                                    logger.info(f"从腾讯 API 获取到视频 URL: {video_url[:60]}...")
                                                    break
                                        if video_urls:
                                            break
                        except Exception as e:
                            logger.debug(f"处理响应失败: {e}")
            else:
                logger.info("未捕获到 proxyhttp 响应")

            if not video_urls:
                raise ValueError("未找到视频播放地址")

            # 下载视频
            save_dir = Path(output_dir) / f"{title}_{video_id}"
            save_dir.mkdir(parents=True, exist_ok=True)

            output_file = save_dir / f"{title}.mp4"

            # 使用 httpx 下载
            import httpx

            # 尝试使用 ffmpeg 下载 - 更可靠
            import shlex

            # 获取第一个视频 URL
            video_url = video_urls[0]

            # 构建 ffmpeg 命令，使用 -referer 和 -user-agent
            ffmpeg_cmd = [
                'ffmpeg',
                '-user_agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                '-referer', 'https://v.qq.com/',
                '-i', video_url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                '-y',  # 覆盖输出文件
                str(output_file)
            ]

            logger.info(f"使用 ffmpeg 下载到: {output_file}")
            logger.info(f"执行 ffmpeg 命令: {' '.join(shlex.quote(x) for x in ffmpeg_cmd)}")

            # 运行 ffmpeg
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"视频已下载到: {output_file}")
            else:
                logger.error(f"ffmpeg 失败: {stderr.decode()}")
                # 如果 ffmpeg 失败，尝试回退到 httpx
                logger.info("尝试回退到 httpx 下载...")
                async with httpx.AsyncClient(headers=config.DEFAULT_HEADERS) as client:
                    resp = await client.get(video_url)
                    resp.raise_for_status()

                    with open(output_file, 'wb') as f:
                        f.write(resp.content)
                logger.info(f"视频已下载到 (httpx): {output_file}")

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
