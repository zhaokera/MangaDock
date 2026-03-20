"""
爬虫工具函数
提供共享的辅助功能，避免代码重复
"""

import re
import asyncio
import time
from typing import Optional

# 默认等待配置
DEFAULT_LOW_WAIT = 0.5  # 低优先级等待 (0.5秒)
DEFAULT_MEDIUM_WAIT = 1.0  # 中等优先级等待 (1秒)
DEFAULT_HIGH_WAIT = 2.0  # 高优先级等待 (2秒)
DEFAULT_MAX_WAIT = 5.0  # 最大等待时间 (5秒)
DEFAULT_CHECK_INTERVAL = 0.2  # 条件检查间隔 (0.2秒)

# 视频网站平台名称 (B站视频已移除，仅保留漫画支持)
VIDEO_PLATFORMS = {
    "tencent": "腾讯视频",
    "iqiyi": "爱奇艺",
    "youku": "优酷",
    "mango": "芒果TV"
}


async def wait_for_page_ready(page, max_wait: float = DEFAULT_MAX_WAIT, check_interval: float = DEFAULT_CHECK_INTERVAL) -> bool:
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
        # 检查页面是否加载完成
        ready = await page.evaluate('''() => {
            return document.readyState === 'complete' ||
                   document.readyState === 'interactive';
        }''')
        if ready:
            return True
        await asyncio.sleep(check_interval)
    return True  # 超时也返回 True（后续操作会处理）


async def wait_for_element(page, selector: str, timeout: float = DEFAULT_MAX_WAIT) -> bool:
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
        await asyncio.sleep(DEFAULT_CHECK_INTERVAL)
    return False


async def wait_for_navigation(page, timeout: float = DEFAULT_MAX_WAIT) -> bool:
    """
    等待页面导航完成

    Args:
        page: Playwright page 对象
        timeout: 超时时间

    Returns:
        bool: 导航是否完成
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        # 检查页面是否加载完成
        ready = await page.evaluate('''() => {
            return document.readyState === 'complete';
        }''')
        if ready:
            return True
        await asyncio.sleep(DEFAULT_CHECK_INTERVAL)
    return False


async def wait_for_images_loaded(page, timeout: float = DEFAULT_MAX_WAIT) -> bool:
    """
    等待页面图片加载完成

    Args:
        page: Playwright page 对象
        timeout: 超时时间

    Returns:
        bool: 图片是否加载完成
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        # 检查是否有未加载的图片
        all_loaded = await page.evaluate('''() => {
            const imgs = document.querySelectorAll('img');
            if (imgs.length === 0) return true;
            return Array.from(imgs).every(img => img.complete);
        }''')
        if all_loaded:
            return True
        await asyncio.sleep(DEFAULT_CHECK_INTERVAL)
    return True


def extract_comic_id(url: str) -> Optional[str]:
    """
    从 URL 提取 comic_id

    Args:
        url: 漫画 URL

    Returns:
        str 或 None: comic_id
    """
    match = re.search(r'/comic/(\d+)', url)
    return match.group(1) if match else None


def extract_episode_id(url: str) -> Optional[str]:
    """
    从 URL 提取 episode_id

    Args:
        url: 漫画 URL

    Returns:
        str 或 None: episode_id
    """
    # 支持多种后缀: .html, .shtml
    match = re.search(r'/comic/\d+/(.+)\.(?:html|shtml)', url)
    if match:
        episode_str = match.group(1)
        try:
            return int(episode_str)
        except ValueError:
            return episode_str
    return None


def get_image_extension(url: str) -> str:
    """
    根据 URL 获取图片扩展名

    Args:
        url: 图片 URL

    Returns:
        str: 扩展名
    """
    url_lower = url.lower()
    if ".webp" in url_lower:
        return ".webp"
    elif ".png" in url_lower:
        return ".png"
    elif ".gif" in url_lower:
        return ".gif"
    return ".jpg"


def sanitize_filename(name: str, max_length: int = 80) -> str:
    """
    清理文件名，移除非法字符

    Args:
        name: 原始文件名
        max_length: 最大长度

    Returns:
        str: 清理后的文件名
    """
    # 移除非法字符
    safe_name = re.sub(r'[\\/*?:"<>|]', "", name)
    # 截断超长名称
    return safe_name[:max_length]
