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
import asyncio
import time
import datetime
from typing import Optional, List
from pathlib import Path

from .base import BaseCrawler, MangaInfo, DownloadProgress, ProgressCallback
from .registry import register_crawler
import config


# ============== 模块级常量 ==============

# 模块级预编译正则表达式
_IMG_PATTERN = re.compile(r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)')
_LZ_PATTERN = re.compile(r'LZString\.decompressFromBase64\(["\']([^"\']+)["\']\)')
_JSON_PATTERN = re.compile(r'"files"\s*:\s*\[(.*?)\]', re.DOTALL)
_IMG_SERVER_PATTERN = re.compile(r'https?://[^.]+\.hamreus\.com')


# LZString 解密实现 - 使用正确的算法
def lzstring_decompress(input_str: str) -> str:
    """
    LZString 解压缩算法 implementation
    这是 LZString.decompressFromBase64() 的 Python 实现

    LZString 是一种基于 LZW 的压缩算法，使用可变位宽
    """
    if not input_str:
        return ""

    # Base64 字符集
    key_str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="

    # URL 安全的 Base64 字符集
    key_str_url = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_="

    # 尝试两种字符集
    for keys in [key_str, key_str_url]:
        try:
            # 反向映射：字符 -> 数值
            reverse_key = {c: i for i, c in enumerate(keys)}

            # 使用列表推导替代循环+append，避免重复查找
            nums = [reverse_key[char] for char in input_str if char in reverse_key]

            if not nums:
                continue

            # 使用 reverse() 替代 pop(0)，将 O(n^2) 复杂度降为 O(n)
            nums.reverse()

            # LZString 解压缩
            dictionary = {i: chr(i) for i in range(256)}
            next_code = 256
            num_bits = 9  # 初始位宽

            # 解码位流
            bit_buffer = 0
            bits_in_buffer = 0
            result = []

            def get_bits(count):
                """从位流中获取指定数量的位"""
                nonlocal bit_buffer, bits_in_buffer
                while bits_in_buffer < count:
                    if not nums:
                        return None
                    bit_buffer |= (nums.pop() << bits_in_buffer)  # pop() 是 O(1)
                    bits_in_buffer += 6
                result_val = bit_buffer & ((1 << count) - 1)
                bit_buffer >>= count
                bits_in_buffer -= count
                return result_val

            try:
                # 初始化
                num_bits = 9
                dictionary = {i: chr(i) for i in range(256)}
                next_code = 256

                # 读取第一个码字
                first_code = get_bits(num_bits)
                if first_code is None:
                    continue

                w = dictionary[first_code]
                result.append(w)
                next_code = 256

                while True:
                    code = get_bits(num_bits)
                    if code is None:
                        break

                    if code in dictionary:
                        entry = dictionary[code]
                    elif code == next_code:
                        # 这是 LZW 的特殊情况：码字不在字典中
                        entry = w + w[0]
                    else:
                        break

                    result.append(entry)

                    # 添加新条目到字典
                    dictionary[next_code] = w + entry[0]
                    next_code += 1

                    # 增加位数
                    if next_code == (1 << num_bits) and num_bits < 16:
                        num_bits += 1

                    w = entry

                return ''.join(result)
            except Exception:
                continue

        except Exception:
            continue

    return ""


# 模块级预编译正则表达式
_IMG_PATTERN = re.compile(r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp|gif)')
_LZ_PATTERN = re.compile(r'LZString\.decompressFromBase64\(["\']([^"\']+)["\']\)')
_JSON_PATTERN = re.compile(r'"files"\s*:\s*\[(.*?)\]', re.DOTALL)


def extract_images_from_page(page_content: str) -> List[str]:
    """
    从页面内容中提取图片 URL

    漫画柜的图片数据通常存储在页面的 JavaScript 变量中
    格式可能为:
    - window["\\x65\\x78\\x74\\x65\\x6e\\x64\\x43\\x6f\\x6e\\x66\\x69\\x67"] = {...}
    - 或者某个加密的配置字符串
    """
    images = []

    # 使用预编译的正则表达式
    direct_images = _IMG_PATTERN.findall(page_content)
    images.extend(direct_images)

    # 模式2: 在 script 标签中查找配置
    # 漫画柜通常使用 LZString 加密的配置
    lz_matches = _LZ_PATTERN.findall(page_content)

    for lz_data in lz_matches:
        try:
            # 尝试解密
            decoded = decompress_lzstring(lz_data)
            if decoded:
                # 从解密后的数据中提取图片 URL
                found_images = _IMG_PATTERN.findall(decoded)
                images.extend(found_images)
        except Exception:
            # 解密失败属于可恢复错误，继续尝试其他模式
            pass

    # 模式3: 查找 JSON 配置
    json_matches = _JSON_PATTERN.findall(page_content)

    for match in json_matches:
        try:
            # 解析文件列表
            files = json.loads(f'[{match}]')
            for f in files:
                if isinstance(f, str) and any(ext in f.lower() for ext in ['.jpg', '.png', '.webp']):
                    images.append(f)
        except Exception:
            # JSON 解析失败属于可恢复错误，继续尝试其他模式
            pass

    # 去重
    return list(set(images))


# ============== 常量定义 ==============

# 字母数字到数字的映射（用于解码文件名）
_FILENAME_MAP = {
    # 小写字母
    'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, 'f': 5, 'g': 6, 'h': 7, 'i': 8, 'j': 9, 'k': 10, 'l': 11,
    'm': 12, 'n': 13, 'o': 14, 'p': 15, 'q': 16, 'r': 17, 's': 18, 't': 19, 'u': 20, 'v': 21, 'w': 22,
    'x': 23, 'y': 24, 'z': 25,
    # 大写字母
    'A': 0, 'B': 1, 'C': 2, 'D': 3, 'E': 4, 'F': 5, 'G': 6, 'H': 7, 'I': 8, 'J': 9, 'K': 10, 'L': 11,
    'M': 12, 'N': 13, 'O': 14, 'P': 15, 'Q': 16, 'R': 17, 'S': 18, 'T': 19, 'U': 20, 'V': 21, 'W': 22,
    'X': 23, 'Y': 24, 'Z': 25,
}

# 扩展名映射
_EXT_MAP = {
    '2.3': '.webp',
    '1.2': '.jpg',
    '1.3': '.png',
    '0.1': '.gif',
}


def _decode_filename(filename: str, comic_id: int, chapter_id: int) -> str:
    """
    解码混淆的文件名

    漫画柜使用混淆的文件名格式：
    - 如 "l.2.3" 或 "K.2.3" 解码为实际的图片文件名
    - 字母或大写字母对应页码
    - 数字后缀对应文件扩展名
    """
    if not filename or '%' in filename:
        return filename  # 未编码或已包含特殊字符

    parts = filename.split('.')
    if len(parts) < 2:
        return filename

    # 使用模块级常量
    ext_key = '.'.join(parts[-2:]) if len(parts) >= 3 else parts[-1]
    ext = _EXT_MAP.get(ext_key, '.webp')

    # 解码页码
    char = parts[0]
    # 使用模块级常量 _FILENAME_MAP
    if char in _FILENAME_MAP:
        page_num = _FILENAME_MAP[char]
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


def _normalize_image_url(url: str) -> str:
    """
    规范化图片 URL，确保使用首选服务器

    漫画柜可能会返回不同的 regional 服务器 (eu2, cf, cc, us3 等)，
    但这些服务器可能在某些地区无法访问。
    将所有 URL 规范化为第一优选服务器 (i.hamreus.com)
    """
    if not url or 'hamreus' not in url:
        return url

    # 使用预编译的正则表达式
    return _IMG_SERVER_PATTERN.sub('https://i.hamreus.com', url)


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
        # 等待 JavaScript 执行完成 (增加等待时间让 packer 解码)
        await self.page.wait_for_timeout(5000)

        # 多次尝试读取 SMH.imgData，因为 packer 解码需要时间
        for attempt in range(7):
            img_data = await self.page.evaluate('''
                () => {
                    // 方法1: 尝试 SMH.imgData (主要方式)
                    if (typeof SMH !== 'undefined' && SMH.imgData && SMH.imgData.files) {
                        console.log('Found SMH.imgData');
                        return { source: 'SMH.imgData', files: SMH.imgData.files, path: SMH.imgData.path || '', len: SMH.imgData.len };
                    }

                    // 方法2: 尝试 chapterImages / chapterPath 变量
                    if (typeof chapterImages !== 'undefined' && chapterImages.length > 0) {
                        console.log('Found chapterImages');
                        return {
                            source: 'chapterImages',
                            files: chapterImages,
                            path: typeof chapterPath !== 'undefined' ? chapterPath : ''
                        };
                    }

                    // 方法3: 尝试 window.imgData
                    if (typeof window.imgData !== 'undefined' && window.imgData.files) {
                        console.log('Found window.imgData');
                        return { source: 'window.imgData', files: window.imgData.files, path: window.imgData.path || '' };
                    }

                    // 方法4: 尝试从 window 对象中查找包含 files 数组的配置
                    for (let key in window) {
                        try {
                            let val = window[key];
                            if (val && typeof val === 'object' && Array.isArray(val.files) && val.files.length > 0) {
                                console.log('Found in window.' + key);
                                return { source: 'window.' + key, files: val.files, path: val.path || '' };
                            }
                        } catch(e) {}
                    }

                    // 方法5: 查找页面上已加载的图片
                    let imgs = document.querySelectorAll('img');
                    let hamreusImgs = [];
                    for (let img of imgs) {
                        if (img.src && img.src.includes('hamreus')) {
                            hamreusImgs.push(img.src);
                        }
                    }
                    if (hamreusImgs.length > 0) {
                        console.log('Found ' + hamreusImgs.length + ' images in DOM');
                        return { source: 'DOM', files: hamreusImgs };
                    }

                    // 方法6: 尝试获取 SMH.imgData() 函数的返回值
                    // 新版漫画柜使用函数形式
                    try {
                        if (typeof SMH !== 'undefined' && typeof SMH.imgData === 'function') {
                            let imgData = SMH.imgData();
                            if (imgData && imgData.files) {
                                console.log('Found SMH.imgData() function result');
                                return { source: 'SMH.imgData()',
                                    files: imgData.files,
                                    path: imgData.path || '',
                                    len: imgData.len
                                };
                            }
                        }
                    } catch(e) {}

                    return null;
                }
            ''')

            # 只有当 img_data 包含有效的 files 数组时才返回
            if img_data and isinstance(img_data, dict) and img_data.get('files'):
                files = img_data.get('files', [])
                print(f"[DEBUG] 尝试 {attempt + 1}/7: 从 {img_data.get('source', 'unknown')} 获取到 {len(files)} 个文件")

                # 只有当文件数量足够多时才返回（至少20个或等于总页数）
                # 如果文件太少，继续尝试其他方法
                if len(files) >= 20:
                    print(f"[DEBUG] 文件数量足够 ({len(files)} >= 20)，返回配置")
                    return img_data
                else:
                    print(f"[DEBUG] 文件数量太少 ({len(files)} < 20)，继续尝试...")
                    # 指数退避等待
                    if attempt < 6:
                        delay = 1 * (2 ** attempt)  # 1s, 2s, 4s, 8s, 16s, 32s
                        print(f"[DEBUG] 等待 {delay}s 后重试...")
                        await self.page.wait_for_timeout(delay * 1000)
                    continue

            # 没找到或太少，等待更长时间再试
            print(f"[DEBUG] 尝试 {attempt + 1}/5: 未找到足够的数据，等待...")
            await self.page.wait_for_timeout(1000)

        # 方法6: 从页面 HTML 中解析混淆的 JavaScript 配置
        try:
            page_content = await self.page.content()
            print(f"[DEBUG] 页面内容长度: {len(page_content)}")

            # 查找页面中的页数信息
            page_match = re.search(r'/(\d+)\)\s*</span>', page_content)
            total_pages = int(page_match.group(1)) if page_match else 0
            print(f"[DEBUG] 从页面提取到总页数: {total_pages}")

            # 尝试解析 V.S({...}) 格式的配置
            # 格式: V.S({"w":4,"v":"u","p":["o.2.3",...],"J":"/I/5/6/4/7/",...})
            vs_match = re.search(r'V\.S\(\{[^}]*"p"\s*:\s*\[(.*?)\][^}]*\}\)', page_content, re.DOTALL)
            if vs_match:
                config_str = vs_match.group(0)
                print(f"[DEBUG] 找到 V.S 配置: {config_str[:200]}...")

                # 提取 p 数组（图片文件列表）
                p_match = re.search(r'"p"\s*:\s*\[(.*?)\]', config_str, re.DOTALL)
                j_match = re.search(r'"J"\s*:\s*"([^"]*)"', config_str)

                if p_match:
                    files_str = p_match.group(1)
                    files = re.findall(r'"([^"]+)"', files_str)

                    if files:
                        path = j_match.group(1) if j_match else ""
                        print(f"[DEBUG] 从 V.S 配置提取到 {len(files)} 个文件, path={path}")
                        return {
                            'files': files,
                            'path': path,
                            'total_pages': total_pages or len(files),
                            'is_encoded': True
                        }

            # 尝试直接从页面的 SMH 变量读取（在 JavaScript 执行后）
            # 有时 SMH.imgData 会在页面完全加载后才被设置
            smh_check = await self.page.evaluate('''
                () => {
                    // 检查所有可能的配置位置
                    if (typeof SMH !== 'undefined') {
                        if (SMH.imgData && SMH.imgData.files) {
                            return { source: 'SMH.imgData', ...SMH.imgData };
                        }
                        // 有时配置直接在 SMH 上
                        for (let key in SMH) {
                            let val = SMH[key];
                            if (val && typeof val === 'object' && Array.isArray(val.files)) {
                                return { source: 'SMH.' + key, ...val };
                            }
                        }
                    }
                    return null;
                }
            ''')
            if smh_check and smh_check.get('files'):
                print(f"[DEBUG] 从 {smh_check.get('source')} 获取到 {len(smh_check.get('files', []))} 个文件")
                return smh_check

            # 查找 "n" 数组（图片文件列表）在混淆代码中
            n_match = re.search(r'"n"\s*:\s*\[(.*?)\]', page_content)
            l_match = re.search(r'"L"\s*:\s*"([^"]*)"', page_content)

            if n_match:
                files_str = n_match.group(1)
                files = re.findall(r'"([^"]+)"', files_str)
                path = l_match.group(1) if l_match else ""

                if files:
                    print(f"[DEBUG] 从混淆代码提取到 {len(files)} 个文件, path={path[:50]}...")
                    return {
                        'files': files,
                        'path': path,
                        'total_pages': total_pages,
                        'is_encoded': True
                    }

            # 方法7: 尝试从 window.eval 加密的脚本中提取 LZString 压缩的数据
            # 格式: window["\x65\x76\x61\x6c"](function(p,a,c,k,e,d){...})('Z.X({...}...)')
            # 注意：此方法需要 comic_id 和 chapter_id，在 _extract_img_config 中没有这些变量
            # 因此此方法由 _do_download 中处理
            print(f"[DEBUG] 尝试从 eval 加密脚本中提取图片数据... (跳过，需要 comic_id)")
        except Exception as e:
            print(f"[DEBUG] 解析混淆代码失败: {e}")

        print(f"[DEBUG] 无法从页面提取图片配置")
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
            # 移除监听器 - 使用 page.off 替代 remove_listener
            self.page.off("response", capture_image)

        # 去重并保持顺序
        unique_urls = list(dict.fromkeys(captured_urls))

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

        # 记录开始时间
        start_time = time.time()
        current_time = time.strftime('%H:%M:%S', time.localtime())
        print(f"[DEBUG] 下载任务开始: {current_time}")

        # 访问页面 (带重试机制)
        report(DownloadProgress(message="正在加载页面...", status="downloading"))

        # 指数退避重试页面加载
        page_load_success = False
        for attempt in range(1, 4):
            try:
                await self.page.goto(url, wait_until="load", timeout=90000)
                page_load_success = True
                break
            except Exception as e:
                print(f"页面加载失败 (尝试 {attempt}/3): {type(e).__name__}")
                if attempt < 4:
                    delay = 2 * (2 ** (attempt - 1))  # 2s, 4s, 8s
                    print(f"等待 {delay}s 后重试...")
                    await self.page.wait_for_timeout(delay * 1000)

        # 如果 load 失败，尝试 domcontentloaded
        if not page_load_success:
            try:
                await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page_load_success = True
            except Exception as e:
                report(DownloadProgress(message=f"页面加载警告: {str(e)[:50]}", status="downloading"))

        # 使用动态等待检查页面元素是否存在
        await self._wait_for_page_ready()

        # 尝试从页面获取标题
        try:
            title_elem = await self.page.query_selector('h1, .book-title, .comic-title')
            if title_elem:
                comic_title = await title_elem.inner_text()
                comic_title = comic_title.strip().split('\n')[0]
        except Exception:
            # 获取标题失败属于可恢复错误
            pass

        try:
            chapter_elem = await self.page.query_selector('.chapter-title, .ep-title, h2')
            if chapter_elem:
                chapter_title = await chapter_elem.inner_text()
                chapter_title = chapter_title.strip()
        except Exception:
            # 获取章节标题失败属于可恢复错误
            pass

        # 方法1: 优先从 JavaScript 变量直接提取配置 (最可靠)
        img_config = await self._extract_img_config()

        # 如果图片配置不足20张，尝试直接从页面 Z.X 配置中提取
        if (not img_config or not isinstance(img_config, dict) or
            not img_config.get('files') or len(img_config.get('files', [])) < 20):
            print(f"[DEBUG] 初始配置不足 ({img_config.get('files', []) if img_config else 'None'}), 尝试从 Z.X 配置中提取...")
            try:
                page_content = await self.page.content()
                # 方法8: 尝试从 Z.X({...}) 格式的配置中提取
                zx_match = re.search(r'Z\.X\(\s*(\{[^}]+\})', page_content, re.DOTALL)
                if zx_match:
                    config_str = zx_match.group(1)
                    print(f"[DEBUG] 找到 Z.X 配置，长度: {len(config_str)}")

                    # 尝试从配置中提取 q 数组（文件列表）和 Y 字段（路径）
                    q_match = re.search(r'"q"\s*:\s*\[(.*?)\]', config_str, re.DOTALL)
                    y_match = re.search(r'"Y"\s*:\s*"([^"]+)"', config_str)

                    if q_match:
                        files_str = q_match.group(1)
                        # 提取文件名，格式如 "p.2.3", "o.2.3" 等
                        files = re.findall(r'"([^"]+)"', files_str)

                        if files:
                            # 路径格式如 "/M/L/N/4/5/"，需要转换为实际路径
                            path_raw = y_match.group(1) if y_match else ""
                            print(f"[DEBUG] 从 Z.X 配置提取到 {len(files)} 个文件, path_raw={path_raw}")

                            # 解码路径
                            path_parts = path_raw.strip('/').split('/')
                            decoded_path_parts = []
                            for p in path_parts:
                                if len(p) == 1 and p.isupper():
                                    num = ord(p) - ord('A') + 1
                                    decoded_path_parts.append(str(num))
                                else:
                                    decoded_path_parts.append(p)
                            path = "/" + "/".join(decoded_path_parts) + "/"

                            # 将文件名转换为实际文件名
                            converted_files = []
                            for f in files:
                                converted = _decode_filename(f, comic_id, chapter_id)
                                converted_files.append(converted)

                            # 对文件名进行排序，确保顺序正确
                            def get_page_num(filename):
                                match = re.search(r'(\d+)', filename)
                                return int(match.group(1)) if match else 0
                            converted_files.sort(key=get_page_num)

                            print(f"[DEBUG] 转换后文件: {converted_files[:5]}...")

                            img_config = {
                                'files': converted_files,
                                'path': path,
                                'total_pages': len(converted_files),
                                'is_encoded': True
                            }
            except Exception as e:
                print(f"[DEBUG] 从 Z.X 配置提取失败: {e}")

        if img_config and isinstance(img_config, dict) and 'files' in img_config:
            files = img_config['files']
            path = img_config.get('path', '')
            is_encoded = img_config.get('is_encoded', False)

            if is_encoded:
                # 文件名需要解码
                print(f"[DEBUG] 检测到编码配置，尝试解码或加载 {len(files)} 张图片")
                report(DownloadProgress(message=f"检测到编码配置，尝试解码...", status="downloading"))

                total_pages = img_config.get('total_pages', len(files))
                if total_pages == 0:
                    total_pages = len(files)

                # 首先尝试等待 JavaScript 解码完成后再读取 SMH.imgData
                print(f"[DEBUG] 等待 JavaScript 解码完成...")
                await self.page.wait_for_timeout(5000)

                # 尝试再次读取 SMH.imgData（可能已经被解码）
                decoded_config = await self.page.evaluate('''
                    () => {
                        if (typeof SMH !== 'undefined' && SMH.imgData && SMH.imgData.files) {
                            // 返回完整的 imgData 信息用于调试
                            return {
                                files: SMH.imgData.files,
                                path: SMH.imgData.path || '',
                                len: SMH.imgData.len,
                                cid: SMH.imgData.cid,
                                bid: SMH.imgData.bid,
                                all_keys: Object.keys(SMH.imgData)
                            };
                        }
                        return null;
                    }
                ''')

                print(f"[DEBUG] decoded_config = {decoded_config}")

                if decoded_config and decoded_config.get('files'):
                    decoded_files = decoded_config.get('files', [])
                    decoded_path = decoded_config.get('path', '')
                    print(f"[DEBUG] JavaScript 解码成功! 获取到 {len(decoded_files)} 个文件, path={decoded_path}")

                    # 使用解码后的数据构造 URL
                    for filename in decoded_files:
                        if isinstance(filename, str):
                            if filename.startswith('http'):
                                image_urls.append(filename)
                            else:
                                img_url = f"{self.IMAGE_SERVERS[0]}{decoded_path}{filename}"
                                image_urls.append(img_url)

                    total = len(image_urls)
                    report(DownloadProgress(message=f"解码成功，获取到 {total} 张图片", status="downloading"))

                else:
                    # JavaScript 解码失败，尝试网络拦截捕获
                    print(f"[DEBUG] JavaScript 未解码，尝试触发图片加载...")
                    report(DownloadProgress(message=f"正在加载所有 {total_pages} 页...", status="downloading"))

                    # 使用网络拦截捕获所有图片
                    captured_urls = []

                    async def capture_img(response):
                        resp_url = str(response.url)
                        # 漫画柜图片通常来自 hamreus.com
                        if 'hamreus' in resp_url.lower():
                            # 过滤掉非图片请求
                            if any(ext in resp_url.lower() for ext in ['.jpg', '.png', '.webp', '.gif']):
                                captured_urls.append(resp_url)
                                print(f"[DEBUG] 捕获图片 #{len(captured_urls)}: {resp_url[:80]}...")

                    self.page.on("response", capture_img)

                    try:
                        print(f"[DEBUG] 开始触发图片加载，目标页数: {total_pages}")

                        # 方法1: 点击页面上的下一页按钮
                        for attempt in range(3):
                            try:
                                # 先等待页面稳定
                                await self.page.wait_for_timeout(1000)

                                # 尝试找到图片容器并点击
                                img_container = await self.page.query_selector('#manga, .manga, #img, .comic-img, img[src*="hamreus"]')
                                if img_container:
                                    print(f"[DEBUG] 找到图片容器，尝试点击")
                                    await img_container.click()
                                    await self.page.wait_for_timeout(500)
                            except Exception as e:
                                print(f"[DEBUG] 点击容器失败: {e}")

                        # 方法2: 使用键盘右箭头
                        print(f"[DEBUG] 使用键盘触发加载")
                        # 动态等待：只在捕获新图片时等待，否则跳过
                        base_wait_time = 200  # 减少基础等待时间
                        for page_num in range(max(total_pages + 15, 30)):  # 增加点击次数
                            try:
                                before_count = len(captured_urls)
                                await self.page.keyboard.press('ArrowRight')
                                # 动态等待：如果捕获到新图片，等待多点；否则少点
                                if len(captured_urls) > before_count:
                                    await self.page.wait_for_timeout(300)  # 捕获到新图片，稍微多等
                                else:
                                    await self.page.wait_for_timeout(base_wait_time)  # 没捕获到，少等

                                # 每5页检查一下进度
                                if page_num % 5 == 0 and captured_urls:
                                    print(f"[DEBUG] 已触发 {page_num} 次，捕获 {len(captured_urls)} 张图片")
                            except Exception as e:
                                print(f"[DEBUG] 键盘事件失败: {e}")

                        # 方法3: 滚动触发 - 减少次数和等待时间
                        print(f"[DEBUG] 尝试滚动触发")
                        for _ in range(5):  # 减少到 5 次
                            await self.page.evaluate("window.scrollBy(0, 500)")
                            await self.page.wait_for_timeout(200)  # 减少到 200ms

                        # 额外等待确保最后几张图片加载 - 减少等待时间
                        await self.page.wait_for_timeout(2000)  # 从 5秒 减少到 2秒
                        print(f"[DEBUG] 完成触发，共捕获 {len(captured_urls)} 张图片")

                    finally:
                        try:
                            # 使用 page.off 替代 remove_listener
                            self.page.off("response", capture_img)
                        except Exception:
                            # 移除监听器失败属于可恢复错误
                            pass

                    # 处理捕获的 URL
                    print(f"[DEBUG] 开始处理捕获的 URL...")
                    if captured_urls:
                        # 去重并保持顺序
                        unique_urls = list(dict.fromkeys(captured_urls))

                        # 按文件名排序 (01.jpg, 02.jpg, ...)
                        def get_page_num(url):
                            match = re.search(r'/(\d+)\.(?:jpg|png|webp)', url)
                            return int(match.group(1)) if match else 0

                        unique_urls.sort(key=get_page_num)
                        image_urls = unique_urls
                        total = len(image_urls)
                        print(f"[DEBUG] URL 处理完成，共 {total} 张图片")
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
                            # 去重并规范化 URL（使用 dict.fromkeys 优化）
                            normalized_urls = [_normalize_image_url(u) for u in loaded_images]
                            image_urls = list(dict.fromkeys(normalized_urls))
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
                        # 如果文件名已经是完整 URL，直接使用
                        if filename.startswith('http'):
                            img_url = filename
                        else:
                            img_url = f"{self.IMAGE_SERVERS[0]}{path}{filename}"
                        image_urls.append(img_url)

                total = len(files)
                report(DownloadProgress(message=f"从 JS 配置获取到 {total} 张图片", status="downloading"))

        # 如果 JS 配置获取的图片太少，尝试通过网络拦截获取更多
        print(f"[DEBUG] 检查是否需要补充拦截 (当前 {len(image_urls)} 张)...")
        if image_urls and len(image_urls) < 10:
            print(f"[DEBUG] JS 配置图片太少 ({len(image_urls)}), 尝试网络拦截补充...")

            # 延迟一下让页面加载更多图片
            await self.page.wait_for_timeout(2000)

            # 获取当前已捕获的图片
            current_urls = set(image_urls)

            # 设置响应拦截器
            intercepted_urls = []

            async def handle_response(response):
                resp_url = str(response.url)
                if any(ext in resp_url for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    if 'hamreus' in resp_url:
                        if resp_url not in current_urls:
                            intercepted_urls.append(resp_url)
                            current_urls.add(resp_url)
                            print(f"[DEBUG] 补充拦截图片 #{len(intercepted_urls)}: {resp_url[:60]}...")

            self.page.on("response", handle_response)

            # 触发更多图片加载
            for _ in range(10):
                try:
                    await self.page.keyboard.press('ArrowRight')
                    await self.page.wait_for_timeout(400)
                except Exception:
                    # 键盘操作失败属于可恢复错误
                    pass

            await self.page.wait_for_timeout(3000)

            # 添加补充的图片
            if intercepted_urls:
                image_urls.extend(intercepted_urls)
                print(f"[DEBUG] 网络拦截补充了 {len(intercepted_urls)} 张图片")

            # 移除监听器
            try:
                self.page.off("response", handle_response)
            except Exception:
                # 移除监听器失败属于可恢复错误
                pass

        # 调试输出当前图片数量
        print(f"[DEBUG] 当前图片总数: {len(image_urls)}")
        print(f"[DEBUG] 准备开始下载...")

        # 方法2: 如果 JS 配置获取的图片太少（少于20张），使用 SMH.utils.goPage() 翻页
        # 注意：你的日志显示有 25 张图片，所以这部分应该被跳过
        print(f"[DEBUG] 检查图片数量是否 < 20 (当前 {len(image_urls)} 张)...")
        if image_urls and len(image_urls) < 20:
            print(f"[DEBUG] JS 配置图片数量不足 ({len(image_urls)}), 使用 SMH.utils.goPage() 获取所有图片...")
            report(DownloadProgress(message="使用 SMH 翻页获取所有图片...", status="downloading"))

            # 获取总页数
            total_pages = 27
            try:
                page_content = await self.page.content()
                page_match = re.search(r'/(\d+)\)\s*</span>', page_content)
                total_pages = int(page_match.group(1)) if page_match else 27
            except Exception:
                # 获取总页数失败，使用默认值
                pass

            # 使用 SMH.utils.goPage() 翻页，捕获所有图片 URL
            seen_urls = set(image_urls)
            print(f"[DEBUG] 初始图片数量: {len(image_urls)}, 目标页数: {total_pages}")

            # 先检查 SMH.utils.goPage 函数是否存在
            goPage_exists = await self.page.evaluate('''
                () => {
                    return typeof SMH !== 'undefined' && typeof SMH.utils !== 'undefined' && typeof SMH.utils.goPage === 'function';
                }
            ''')
            print(f"[DEBUG] SMH.utils.goPage 函数存在: {goPage_exists}")

            for page_num in range(2, total_pages + 1):
                try:
                    # 记录翻页前的当前页码
                    prev_page = await self.page.evaluate('''
                        () => {
                            let pageSpan = document.querySelector('#page');
                            return pageSpan ? pageSpan.innerText : 'unknown';
                        }
                    ''')
                    print(f"[DEBUG] 翻页前: 第 {prev_page} 页")

                    await self.page.evaluate(f'SMH.utils.goPage({page_num})')
                    await asyncio.sleep(2)

                    # 验证是否成功翻页到目标页
                    current_page = await self.page.evaluate('''
                        () => {
                            let pageSpan = document.querySelector('#page');
                            return pageSpan ? pageSpan.innerText : 'unknown';
                        }
                    ''')
                    print(f"[DEBUG] 翻页后验证: 实际在第 {current_page} 页 (期望第 {page_num} 页)")

                    # 获取当前页的图片 URL
                    current_img = await self.page.evaluate('''
                        () => {
                            let img = document.querySelector('img.mangaFile');
                            return img ? img.src : null;
                        }
                    ''')

                    # 同时检查页面上的所有图片元素
                    all_imgs = await self.page.evaluate('''
                        () => {
                            let imgs = document.querySelectorAll('img');
                            return Array.from(imgs)
                                .filter(img => img.src && img.src.includes('hamreus'))
                                .map(img => img.src);
                        }
                    ''')
                    print(f"[DEBUG] 页面上发现 {len(all_imgs)} 个 hamreus 图片")

                    if current_img and 'hamreus' in current_img and current_img not in seen_urls:
                        image_urls.append(current_img)
                        seen_urls.add(current_img)
                        print(f"[DEBUG] 翻页到第 {page_num} 页，捕获图片: {current_img.split('/')[-1].split('?')[0]}")
                    else:
                        print(f"[DEBUG] 警告: 第 {page_num} 页未捕获新图片 (current_img exists: {current_img is not None}, in seen: {current_img in seen_urls if current_img else 'N/A'})")

                except Exception as e:
                    print(f"[DEBUG] 翻页到第 {page_num} 页失败: {e}")
                    import traceback
                    traceback.print_exc()
                    break

            print(f"[DEBUG] SMH 翻页后图片数量: {len(image_urls)}")

            # 去重但保持顺序
            seen = set()
            unique_urls = []
            for u in image_urls:
                if u not in seen:
                    seen.add(u)
                    unique_urls.append(u)
            image_urls = unique_urls

            total = len(image_urls)
            print(f"[DEBUG] 去重后图片数量: {total}")
            report(DownloadProgress(message=f"从 SMH 翻页获取到 {total} 张图片", status="downloading"))

        # 方法3: 如果 JS 配置提取失败，尝试从页面内容正则匹配
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
                        except Exception:
                            # 解析失败属于可恢复错误，继续尝试其他方法
                            pass

            except Exception as e:
                print(f"正则解析配置失败: {e}")

        # 方法3: 设置响应拦截器作为最后的后备方案
        if not image_urls:
            print("[DEBUG] 方法3: 使用网络拦截捕获图片...")
            report(DownloadProgress(message="使用网络拦截捕获图片...", status="downloading"))

            intercepted_urls = []

            async def handle_response(response):
                resp_url = str(response.url).lower()
                if any(ext in resp_url for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    if 'hamreus' in resp_url or 'manhua' in resp_url:
                        intercepted_urls.append(str(response.url))
                        print(f"[DEBUG] 拦截图片 #{len(intercepted_urls)}")

            self.page.on("response", handle_response)

            try:
                # 多种触发方式
                print("[DEBUG] 尝试多种触发方式...")

                # 滚动
                for _ in range(15):
                    await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
                    await self.page.wait_for_timeout(400)

                # 键盘
                for _ in range(20):
                    await self.page.keyboard.press('ArrowRight')
                    await self.page.wait_for_timeout(350)

                # 点击
                try:
                    await self.page.click('body')
                except Exception:
                    # 点击失败属于可恢复错误
                    pass

                await self.page.wait_for_timeout(3000)

                image_urls = intercepted_urls
                print(f"[DEBUG] 方法3捕获到 {len(image_urls)} 张图片")
            finally:
                # 移除监听器
                try:
                    self.page.off("response", handle_response)
                except Exception:
                    # 移除监听器失败属于可恢复错误
                    pass

        # 去重但保持顺序（使用 dict.fromkeys 优化）
        image_urls = list(dict.fromkeys(image_urls))

        # 保存原始页面 URL 用于 Referer
        page_url = url

        if not image_urls:
            raise Exception("未找到图片，网站结构可能已变化")

        total = len(image_urls)
        manga_info.title = comic_title
        manga_info.chapter = chapter_title
        manga_info.page_count = total

        # 记录准备开始下载的时间
        prepare_end_time = time.time()
        prepare_duration = prepare_end_time - start_time
        print(f"[DEBUG] 准备阶段耗时: {prepare_duration:.2f}秒")

        # 创建保存目录
        safe_title = self.sanitize_filename(f"{comic_title}_{chapter_title}")
        save_dir = Path(output_dir) / safe_title
        save_dir.mkdir(parents=True, exist_ok=True)

        # 使用 httpx 直接下载（更快，不依赖浏览器）
        report(DownloadProgress(
            current=0,
            total=total,
            message=f"准备下载 {total} 张图片...",
            status="downloading"
        ))
        await asyncio.sleep(0.5)  # 短暂延迟让前端更新

        # 下载图片 - 使用并发下载
        print(f"[DEBUG] 开始并发下载，共 {total} 张图片")

        # 从配置获取并发数
        cfg = config.get_config()
        concurrency = cfg.download.concurrency
        max_retries = cfg.network.retry_max_attempts

        # 使用可变对象存储计数器，避免 nonlocal 问题
        progress_counter = {'value': 0}
        progress_lock = asyncio.Lock()

        # 创建Semaphore限制最大并发数
        semaphore = asyncio.Semaphore(concurrency)

        async def download_with_semaphore(img_url, filepath, page_url, i, total):
            """带并发限制的下载函数 - 使用并发下载策略"""
            async with semaphore:
                ext = ".jpg"
                if ".webp" in img_url.lower():
                    ext = ".webp"
                elif ".png" in img_url.lower():
                    ext = ".png"
                elif ".gif" in img_url.lower():
                    ext = ".gif"

                headers = {
                    "Referer": page_url,
                }

                # 并发下载辅助函数
                async def browser_download():
                    """浏览器下载任务"""
                    return await self.download_image_via_browser(
                        img_url, filepath, page_url, max_retries=max_retries
                    )

                async def http_download():
                    """普通HTTP下载任务"""
                    return await self.download_image(
                        img_url, filepath, {"Referer": page_url}, max_retries=max_retries
                    )

                # 并发执行两个下载任务，使用快速者优先策略
                success = await self._download_with_fastest_strategy(
                    [browser_download(), http_download()]
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

        # 创建所有下载任务 - 使用URL哈希作为临时文件名
        import hashlib
        temp_file_mapping = {}  # {temp_filename: original_index}
        tasks = []
        for i, img_url in enumerate(image_urls, 1):
            ext = ".jpg"
            if ".webp" in img_url.lower():
                ext = ".webp"
            elif ".png" in img_url.lower():
                ext = ".png"
            elif ".gif" in img_url.lower():
                ext = ".gif"

            # 使用URL哈希作为临时文件名，避免序号混乱
            url_hash = hashlib.md5(img_url.encode()).hexdigest()[:8]
            temp_filename = f"{url_hash}{ext}.tmp"
            temp_filepath = save_dir / temp_filename
            temp_file_mapping[temp_filename] = (i, img_url, ext)  # 记录映射关系
            tasks.append(download_with_semaphore(img_url, temp_filepath, page_url, i, total))

        # 并发执行所有下载任务
        results = await asyncio.gather(*tasks)

        success_count = sum(results)

        # 按原始序号重命名文件（只重命名成功的）
        print(f"[DEBUG] 正在重命名文件...")
        renamed_count = 0
        for i, (temp_filename, (orig_idx, img_url, ext)) in enumerate(temp_file_mapping.items()):
            temp_path = save_dir / temp_filename
            if temp_path.exists():
                new_filename = f"{orig_idx:03d}{ext}"
                new_path = save_dir / new_filename
                temp_path.rename(new_path)
                renamed_count += 1

        print(f"[DEBUG] 文件重命名完成: {renamed_count}/{len(temp_file_mapping)}")

        # 输出下载结果
        print(f"[DEBUG] 并发下载完成: {success_count}/{total} 张图片成功")

        # 最终进度报告
        report(DownloadProgress(
            current=total,
            total=total,
            message=f"下载完成! 共 {success_count} 张图片",
            status="completed"
        ))

        # 记录结束时间并输出总耗时
        end_time = time.time()
        total_duration = end_time - start_time
        current_time = time.strftime('%H:%M:%S', time.localtime())
        print(f"[DEBUG] 下载任务结束: {current_time}")
        print(f"[DEBUG] 总耗时: {total_duration:.2f}秒")
        print(f"[DEBUG] 平均速度: {total_duration/total:.2f}秒/张" if total > 0 else "[DEBUG] 无图片下载")

        return str(save_dir)

    async def _wait_for_page_ready(self, max_wait: float = 5.0, check_interval: float = 0.2) -> bool:
        """
        动态等待页面准备就绪
        检查页面上的关键元素是否存在，而不是固定等待

        Args:
            max_wait: 最大等待时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            bool: 是否成功
        """
        try:
            import time
            start_time = time.time()
            while time.time() - start_time < max_wait:
                # 检查关键元素是否存在
                elements_exist = await self.page.evaluate('''
                    () => {
                        // 检查 SMH 对象或页面关键元素是否存在
                        return typeof SMH !== 'undefined' ||
                               document.querySelector('h1') !== null ||
                               document.querySelector('.book-title') !== null;
                    }
                ''')
                if elements_exist:
                    return True
                await asyncio.sleep(check_interval)
            # 超时也继续，避免阻塞
            return True
        except Exception as e:
            print(f"[DEBUG] 动态等待页面就绪异常: {e}")
            # 出错时也继续，避免阻塞
            return True

    async def _download_with_fastest_strategy(self,coroutines: list) -> bool:
        """
        并发下载策略 - 快速者优先
        同时启动多个下载任务，返回第一个完成的结果，取消其他任务

        Args:
            coroutines: 下载 coroutine 列表

        Returns:
            bool: 是否下载成功
        """
        tasks = [asyncio.create_task(coro) for coro in coroutines]

        try:
            # 等待第一个任务完成
            done, pending = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            # 获取第一个完成的结果
            for task in done:
                try:
                    result = task.result()
                    if result:
                        # 成功，取消其他任务
                        for t in pending:
                            t.cancel()
                        return True
                except Exception:
                    continue

            # 第一个完成的任务没有成功，等待所有任务完成
            for task in pending:
                task.cancel()

            # 等待所有任务真正取消
            await asyncio.gather(*tasks, return_exceptions=True)

            # 检查是否有任何任务成功
            for task in done:
                try:
                    if task.result():
                        return True
                except Exception:
                    continue

            return False

        except asyncio.CancelledError:
            # 取消所有任务
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise