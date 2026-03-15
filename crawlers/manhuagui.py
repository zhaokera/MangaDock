"""
漫画柜 (manhuagui.com) 爬虫

漫画柜网站特点：
- URL 格式: https://www.manhuagui.com/comic/{comic_id}/{chapter_id}.html
- 图片通过 JavaScript 加密，需要解析页面中的配置数据
- 使用 LZString 加密，需要解密
"""

import re
import json
import base64
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler


# LZString 解密实现
class LZString:
    """LZString 解压缩算法"""

    @staticmethod
    def decompress_from_base64(input_str: str) -> str:
        """从 Base64 解压缩"""
        if not input_str:
            return ""

        # 字符映射表
        key_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="

        # 反向映射
        reverse_key = {c: i for i, c in enumerate(key_str)}

        # 解码
        result = []
        bits = 0
        value = 0
        index = 0

        # Base64 解码到数值序列
        nums = []
        for char in input_str:
            if char in reverse_key:
                nums.append(reverse_key[char])

        # LZString 解压缩核心逻辑
        dictionary = {i: chr(i) for i in range(256)}
        next_code = 256
        w = ""
        enlarge_in = 4
        num_bits = 3
        result_str = ""

        data = nums
        if not data:
            return ""

        bits = 0
        max_bits = 32
        power = 1

        def get_next_value():
            nonlocal bits, value, index
            if index >= len(data):
                return None
            res = (data[index] >> bits) & 1
            bits += 1
            if bits == 6:
                bits = 0
                index += 1
            return res

        def get_bits(n):
            nonlocal bits, value, index
            result = 0
            power = 1
            for _ in range(n):
                if index >= len(data):
                    return None
                res = (data[index] >> bits) & 1
                result += res * power
                power *= 2
                bits += 1
                if bits == 6:
                    bits = 0
                    index += 1
            return result

        # 简化版解压缩 - 直接使用正则提取图片数据
        return ""


def extract_images_from_page(page_content: str) -> List[str]:
    """
    从页面内容中提取图片 URL

    漫画柜的图片数据通常存储在页面的 JavaScript 变量中
    格式可能为:
    - window["\\x65\\x78\\x74\\x65\\x6e\\x64\\x43\\x6f\\x6e\\x66\\x69\\x67"] = {...}
    - 或者某个加密的配置字符串
    """
    images = []

    # 尝试多种匹配模式

    # 模式1: 直接的图片 URL
    img_pattern = r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)'
    direct_images = re.findall(img_pattern, page_content)
    images.extend(direct_images)

    # 模式2: 在 script 标签中查找配置
    # 漫画柜通常使用 LZString 加密的配置
    lz_pattern = r'LZString\.decompressFromBase64\(["\']([^"\']+)["\']\)'
    lz_matches = re.findall(lz_pattern, page_content)

    for lz_data in lz_matches:
        try:
            # 尝试解密
            decoded = simple_lz_decompress(lz_data)
            if decoded:
                # 从解密后的数据中提取图片 URL
                found_images = re.findall(img_pattern, decoded)
                images.extend(found_images)
        except:
            pass

    # 模式3: 查找 JSON 配置
    json_pattern = r'"files"\s*:\s*\[(.*?)\]'
    json_matches = re.findall(json_pattern, page_content, re.DOTALL)

    for match in json_matches:
        try:
            # 解析文件列表
            files = json.loads(f'[{match}]')
            for f in files:
                if isinstance(f, str) and any(ext in f.lower() for ext in ['.jpg', '.png', '.webp']):
                    images.append(f)
        except:
            pass

    # 去重
    return list(set(images))


def simple_lz_decompress(compressed: str) -> str:
    """
    简化的 LZString 解压缩

    漫画柜使用的加密方式可能需要特定实现
    这里提供一个基础版本
    """
    try:
        import base64

        # 尝试直接 base64 解码
        try:
            decoded = base64.b64decode(compressed)
            return decoded.decode('utf-8', errors='ignore')
        except:
            pass

        # 如果失败，尝试 URL safe base64
        try:
            # 替换 URL 安全字符
            safe = compressed.replace('-', '+').replace('_', '/')
            # 补齐 padding
            padding = 4 - len(safe) % 4
            if padding != 4:
                safe += '=' * padding
            decoded = base64.b64decode(safe)
            return decoded.decode('utf-8', errors='ignore')
        except:
            pass

        return ""
    except:
        return ""


# 字母数字到数字的映射（用于解码文件名）
_CHAR_MAP = {c: i for i, c in enumerate('0123456789abcdefghijklmnopqrstuvwxyz')}

def _decode_filename(filename: str, comic_id: int, chapter_id: int) -> str:
    """
    解码混淆的文件名

    漫画柜使用混淆的文件名格式：
    - 如 "l.2.3" 解码为实际的图片文件名
    - 字母递减序列对应页码
    - 数字后缀对应文件扩展名
    """
    if not filename or '%' in filename:
        return filename  # 未编码或已包含特殊字符

    parts = filename.split('.')
    if len(parts) < 2:
        return filename

    # 分析格式: X.Y.Z 或 X.Y
    # X 是页码编码（字母递减）
    # Y.Z 是扩展名编码

    # 尝试解码扩展名
    # 常见映射: 2.3 -> webp, 1.2 -> jpg, 1.3 -> png
    ext_map = {
        '2.3': '.webp',
        '1.2': '.jpg',
        '1.3': '.png',
        '0.1': '.gif',
    }

    ext_key = '.'.join(parts[-2:]) if len(parts) >= 3 else parts[-1]
    ext = ext_map.get(ext_key, '.webp')

    # 解码页码
    # 字母递减: l=11, k=10, j=9, ... 表示页码
    # 但实际页码需要从字母转换为数字
    char = parts[0]
    if char in _CHAR_MAP:
        # 从字母计算页码
        page_num = _CHAR_MAP[char]
        # 通常是从高到低排列，所以需要反转
        # 返回数字格式文件名
        return f"{page_num:03d}{ext}"

    return filename


def _decode_path(path: str, comic_id: int, chapter_id: int) -> str:
    """
    解码混淆的路径

    路径格式如: /K/t/S-I/4/5/
    需要解码为实际的漫画路径
    """
    if not path or '%' in path:
        return path

    # 路径解码逻辑
    # 漫画柜的路径通常是 /comic/{comic_id}/{chapter_id}/
    # 但混淆后的路径需要特殊处理

    # 简单替换：如果路径看起来是混淆的，使用已知格式
    if any(c.isupper() for c in path) and '/' in path:
        # 可能是编码的路径，使用默认格式
        return f"/comic/{comic_id}/{chapter_id}/"

    return path


@register_crawler
class ManhuaguiCrawler(BaseCrawler):
    """漫画柜爬虫"""

    PLATFORM_NAME = "manhuagui"
    PLATFORM_DISPLAY_NAME = "漫画柜"
    URL_PATTERNS = [
        r"manhuagui\.com/comic/\d+/\d+",
        r"mhgui\.com/comic/\d+/\d+",  # 备用域名
    ]

    # 图片服务器域名
    IMAGE_SERVERS = [
        "https://i.hamreus.com",
        "https://eu2.hamreus.com",
        "https://cf.hamreus.com",
        "https://cc.hamreus.com",
    ]

    def _extract_ids(self, url: str) -> tuple:
        """从 URL 提取 comic_id 和 chapter_id"""
        match = re.search(r'/comic/(\d+)/(\d+)', url)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None

    async def _extract_img_config(self) -> Optional[dict]:
        """
        从页面 JavaScript 变量中直接提取图片配置

        漫画柜在页面加载时，所有图片 URL 都嵌入在 JavaScript 变量中：
        - SMH.imgData: 主要配置对象，包含 files 和 path
        - chapterImages / chapterPath: 备用变量

        Returns:
            dict: 包含 files (图片文件列表) 和 path (路径前缀) 的字典
        """
        # 等待 JavaScript 执行完成
        await self.page.wait_for_timeout(1000)

        img_data = await self.page.evaluate('''
            () => {
                // 方法1: 尝试 SMH.imgData (主要方式)
                if (typeof SMH !== 'undefined' && SMH.imgData && SMH.imgData.files) {
                    return SMH.imgData;
                }

                // 方法2: 尝试 chapterImages / chapterPath 变量
                if (typeof chapterImages !== 'undefined' && chapterImages.length > 0) {
                    return {
                        files: chapterImages,
                        path: typeof chapterPath !== 'undefined' ? chapterPath : ''
                    };
                }

                // 方法3: 尝试 window.imgData
                if (typeof window.imgData !== 'undefined' && window.imgData.files) {
                    return window.imgData;
                }

                // 方法4: 尝试从 window 对象中查找包含 files 数组的配置
                for (let key in window) {
                    try {
                        let val = window[key];
                        if (val && typeof val === 'object' && Array.isArray(val.files) && val.files.length > 0) {
                            return val;
                        }
                    } catch(e) {}
                }

                return null;
            }
        ''')

        # 只有当 img_data 包含有效的 files 数组时才返回
        if img_data and isinstance(img_data, dict) and img_data.get('files'):
            return img_data

        # 方法5: 从页面 HTML 中解析混淆的 JavaScript 配置
        # 漫画柜使用 eval + packer 混淆，需要从页面中提取原始数据
        try:
            page_content = await self.page.content()

            # 查找页面中的页数信息
            page_match = re.search(r'/(\d+)\)\s*</span>', page_content)
            if page_match:
                total_pages = int(page_match.group(1))
            else:
                total_pages = 0

            # 查找 "n" 数组（图片文件列表）在混淆代码中
            # 格式: "n":["l.2.3","k.2.3",...] 或 "n": [...]
            n_match = re.search(r'"n"\s*:\s*\[(.*?)\]', page_content)
            # 查找 "L" 路径
            l_match = re.search(r'"L"\s*:\s*"([^"]*)"', page_content)

            if n_match:
                # 解析文件列表
                files_str = n_match.group(1)
                # 提取所有带引号的内容
                files = re.findall(r'"([^"]+)"', files_str)

                # 路径需要解码（可能是混淆的）
                path = l_match.group(1) if l_match else ""

                if files:
                    return {
                        'files': files,
                        'path': path,
                        'total_pages': total_pages,
                        'is_encoded': True  # 标记为编码数据
                    }
        except Exception as e:
            print(f"解析混淆代码失败: {e}")

        return img_data

    async def _get_actual_image_urls(self, url: str) -> List[str]:
        """
        通过触发图片加载来获取实际的图片 URL

        漫画柜的图片 URL 经过混淆，最可靠的方式是让浏览器加载并捕获实际请求

        Returns:
            List[str]: 实际的图片 URL 列表
        """
        captured_urls = []

        async def capture_image(response):
            """捕获图片响应"""
            resp_url = str(response.url).lower()
            if any(ext in resp_url for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                # 过滤出漫画图片
                if 'hamreus' in resp_url or 'comic' in resp_url:
                    captured_urls.append(str(response.url))

        # 设置响应监听
        self.page.on("response", capture_image)

        try:
            # 滚动页面触发所有图片加载
            for scroll_count in range(20):
                await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                await self.page.wait_for_timeout(300)

                # 如果已经捕获了图片，等待更多
                if len(captured_urls) > 0:
                    await self.page.wait_for_timeout(500)

            # 点击下一页按钮尝试加载更多图片
            for _ in range(5):
                next_btn = await self.page.query_selector('#next, .next, a[onclick*="next"]')
                if next_btn:
                    await next_btn.click()
                    await self.page.wait_for_timeout(1000)

            # 等待网络稳定
            await self.page.wait_for_timeout(2000)

        finally:
            # 移除监听器
            self.page.remove_listener("response", capture_image)

        # 去重并保持顺序
        seen = set()
        unique_urls = []
        for u in captured_urls:
            if u not in seen:
                seen.add(u)
                unique_urls.append(u)

        return unique_urls

    async def get_info(self, url: str) -> MangaInfo:
        """获取漫画信息"""
        comic_id, chapter_id = self._extract_ids(url)
        if not comic_id or not chapter_id:
            raise ValueError("无效的漫画柜 URL")

        return MangaInfo(
            title="",
            chapter="",
            page_count=0,
            platform=self.PLATFORM_NAME,
            comic_id=str(comic_id),
            episode_id=str(chapter_id),
        )

    async def download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """
        下载漫画章节

        Args:
            url: 漫画章节 URL
            output_dir: 输出目录
            progress_callback: 进度回调

        Returns:
            str: 保存目录路径
        """
        await self.start_browser(headless=True)

        try:
            return await self._do_download(url, output_dir, progress_callback)
        finally:
            await self.close_browser()

    async def _do_download(
        self,
        url: str,
        output_dir: str,
        progress_callback: Optional[ProgressCallback] = None
    ) -> str:
        """执行下载"""

        def report(progress: DownloadProgress):
            if progress_callback:
                progress_callback(progress)

        # 提取 ID
        comic_id, chapter_id = self._extract_ids(url)
        if not comic_id or not chapter_id:
            raise ValueError("无效的 URL 格式")

        report(DownloadProgress(message="解析漫画信息...", status="downloading"))

        manga_info = MangaInfo(
            platform=self.PLATFORM_NAME,
            comic_id=str(comic_id),
            episode_id=str(chapter_id),
        )

        # 收集图片 URL
        image_urls = []
        chapter_title = f"第{chapter_id}话"
        comic_title = f"漫画{comic_id}"

        # 访问页面 (使用 load 而非 networkidle，避免广告等导致的超时)
        report(DownloadProgress(message="正在加载页面...", status="downloading"))
        try:
            await self.page.goto(url, wait_until="load", timeout=60000)
        except Exception as e:
            # 如果 load 也超时，尝试 domcontentloaded
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e2:
                report(DownloadProgress(message=f"页面加载警告: {str(e2)[:50]}", status="downloading"))
        await self.page.wait_for_timeout(2000)

        # 尝试从页面获取标题
        try:
            title_elem = await self.page.query_selector('h1, .book-title, .comic-title')
            if title_elem:
                comic_title = await title_elem.inner_text()
                comic_title = comic_title.strip().split('\n')[0]
        except:
            pass

        try:
            chapter_elem = await self.page.query_selector('.chapter-title, .ep-title, h2')
            if chapter_elem:
                chapter_title = await chapter_elem.inner_text()
                chapter_title = chapter_title.strip()
        except:
            pass

        # 方法1: 优先从 JavaScript 变量直接提取配置 (最可靠)
        img_config = await self._extract_img_config()

        if img_config and isinstance(img_config, dict) and 'files' in img_config:
            files = img_config['files']
            path = img_config.get('path', '')
            is_encoded = img_config.get('is_encoded', False)

            if is_encoded:
                # 文件名需要解码
                report(DownloadProgress(message=f"检测到编码配置，尝试加载 {len(files)} 张图片", status="downloading"))

                total_pages = img_config.get('total_pages', len(files))
                if total_pages == 0:
                    total_pages = len(files)

                report(DownloadProgress(message=f"正在加载所有 {total_pages} 页...", status="downloading"))

                # 使用网络拦截捕获所有图片
                captured_urls = []

                async def capture_img(response):
                    url = str(response.url)
                    # 漫画柜图片通常来自 hamreus.com
                    if 'hamreus' in url.lower():
                        # 过滤掉非图片请求
                        if any(ext in url.lower() for ext in ['.jpg', '.png', '.webp', '.gif']):
                            captured_urls.append(url)

                self.page.on("response", capture_img)

                try:
                    # 方法1: 快速点击下一页来触发所有图片加载
                    # 漫画柜会在切换页面时加载图片
                    for page_num in range(max(total_pages + 10, 25)):  # 至少点击25次
                        try:
                            # 使用键盘快捷键（更可靠）
                            await self.page.keyboard.press('ArrowRight')
                            await self.page.wait_for_timeout(350)
                        except:
                            pass

                    # 额外等待确保最后几张图片加载
                    await self.page.wait_for_timeout(3000)

                finally:
                    try:
                        self.page.remove_listener("response", capture_img)
                    except:
                        pass

                # 处理捕获的 URL
                if captured_urls:
                    # 去重并按页码排序
                    seen = set()
                    unique = []
                    for u in captured_urls:
                        # 提取文件名中的数字用于排序
                        if u not in seen:
                            seen.add(u)
                            unique.append(u)

                    # 按文件名排序 (01.jpg, 02.jpg, ...)
                    def get_page_num(url):
                        import re
                        match = re.search(r'/(\d+)\.(?:jpg|png|webp)', url)
                        return int(match.group(1)) if match else 0

                    unique.sort(key=get_page_num)
                    image_urls = unique
                    total = len(image_urls)
                    report(DownloadProgress(message=f"捕获到 {total} 张图片", status="downloading"))
                else:
                    report(DownloadProgress(message="未捕获到图片，尝试备用方法...", status="downloading"))

                    # 备用方法：从页面元素获取已加载的图片
                    loaded_images = await self.page.evaluate('''
                        () => {
                            let imgs = document.querySelectorAll('img');
                            return Array.from(imgs)
                                .filter(img => img.src && img.src.includes('hamreus'))
                                .map(img => img.src);
                        }
                    ''')

                    if loaded_images:
                        # 去重
                        seen = set()
                        for u in loaded_images:
                            if u not in seen:
                                seen.add(u)
                                image_urls.append(u)
                        total = len(image_urls)
                    else:
                        # 最后尝试手动构造 URL
                        for i, filename in enumerate(files):
                            if isinstance(filename, str):
                                decoded_name = _decode_filename(filename, comic_id, chapter_id)
                                decoded_path = _decode_path(path, comic_id, chapter_id)
                                img_url = f"{self.IMAGE_SERVERS[0]}{decoded_path}{decoded_name}"
                                image_urls.append(img_url)

                        total = len(files)
            else:
                # 直接使用配置中的 URL
                for filename in files:
                    if isinstance(filename, str):
                        img_url = f"{self.IMAGE_SERVERS[0]}{path}{filename}"
                        image_urls.append(img_url)

                total = len(files)
                report(DownloadProgress(message=f"从 JS 配置获取到 {total} 张图片", status="downloading"))

        # 方法2: 如果 JS 配置提取失败，尝试从页面内容正则匹配
        if not image_urls:
            try:
                page_content = await self.page.content()

                # 查找配置数据
                config_patterns = [
                    r'smh\.imgData\s*=\s*(\{.*?\});',
                    r'window\["[^"]+"\]\s*=\s*(\{.*?"files".*?\});',
                    r'chapterImages\s*=\s*(\[.*?\]);',
                ]

                for pattern in config_patterns:
                    matches = re.findall(pattern, page_content, re.DOTALL)
                    for match in matches:
                        try:
                            data = json.loads(match)
                            if isinstance(data, dict) and 'files' in data:
                                files = data['files']
                                path = data.get('path', '')
                                for f in files:
                                    if isinstance(f, str):
                                        img_url = f"{self.IMAGE_SERVERS[0]}{path}{f}"
                                        image_urls.append(img_url)
                            elif isinstance(data, list):
                                # chapterImages 是数组
                                for f in data:
                                    if isinstance(f, str):
                                        img_url = f"{self.IMAGE_SERVERS[0]}{f}"
                                        image_urls.append(img_url)
                        except:
                            pass

            except Exception as e:
                print(f"正则解析配置失败: {e}")

        # 方法3: 设置响应拦截器作为最后的后备方案
        if not image_urls:
            report(DownloadProgress(message="使用网络拦截捕获图片...", status="downloading"))

            intercepted_urls = []

            async def handle_response(response):
                resp_url = str(response.url).lower()
                if any(ext in resp_url for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    if 'hamreus' in resp_url or 'manhua' in resp_url:
                        intercepted_urls.append(str(response.url))

            self.page.on("response", handle_response)

            # 滚动页面触发加载
            for _ in range(10):
                await self.page.evaluate("window.scrollBy(0, 500)")
                await self.page.wait_for_timeout(500)

            await self.page.wait_for_timeout(2000)

            image_urls = intercepted_urls

        # 去重但保持顺序
        seen = set()
        unique_urls = []
        for img_u in image_urls:
            if img_u not in seen:
                seen.add(img_u)
                unique_urls.append(img_u)
        image_urls = unique_urls

        # 保存原始页面 URL 用于 Referer
        page_url = url

        if not image_urls:
            raise Exception("未找到图片，网站结构可能已变化")

        total = len(image_urls)
        manga_info.title = comic_title
        manga_info.chapter = chapter_title
        manga_info.page_count = total

        # 创建保存目录
        safe_title = self.sanitize_filename(f"{comic_title}_{chapter_title}")
        save_dir = Path(output_dir) / safe_title
        save_dir.mkdir(parents=True, exist_ok=True)

        # 下载图片
        success_count = 0
        for i, img_url in enumerate(image_urls, 1):
            ext = ".jpg"
            if ".webp" in img_url.lower():
                ext = ".webp"
            elif ".png" in img_url.lower():
                ext = ".png"
            elif ".gif" in img_url.lower():
                ext = ".gif"

            filename = f"{i:03d}{ext}"
            filepath = save_dir / filename

            headers = {
                "Referer": page_url,
            }

            # 优先使用浏览器下载（绕过防盗链）
            try:
                success = await self.download_image_via_browser(img_url, filepath, page_url)
                if success:
                    success_count += 1
                else:
                    # 浏览器下载失败，尝试普通下载
                    success = await self.download_image(img_url, filepath, {"Referer": page_url})
                    if success:
                        success_count += 1
            except Exception as e:
                print(f"下载异常: {e}")

            report(DownloadProgress(
                current=i,
                total=total,
                message=f"下载中 {i}/{total}",
                status="downloading"
            ))

        report(DownloadProgress(
            current=total,
            total=total,
            message=f"下载完成! 共 {success_count} 张图片",
            status="completed"
        ))

        return str(save_dir)