"""
爬虫注册表
管理所有已注册的爬虫，并根据 URL 自动路由到对应平台
"""

from typing import List, Dict, Type, Optional
from pathlib import Path
import logging

from .base import BaseCrawler

logger = logging.getLogger(__name__)


# 爬虫注册表
_crawlers: Dict[str, Type[BaseCrawler]] = {}


def register_crawler(crawler_class: Type[BaseCrawler]) -> Type[BaseCrawler]:
    """
    注册爬虫 (可作为装饰器使用)

    Args:
        crawler_class: 爬虫类

    Returns:
        原始爬虫类
    """
    if not crawler_class.PLATFORM_NAME:
        raise ValueError(f"爬虫 {crawler_class.__name__} 必须定义 PLATFORM_NAME")

    _crawlers[crawler_class.PLATFORM_NAME] = crawler_class
    return crawler_class


def get_crawler(url: str) -> BaseCrawler:
    """
    根据 URL 获取对应爬虫实例

    Args:
        url: 漫画章节 URL

    Returns:
        BaseCrawler: 爬虫实例

    Raises:
        ValueError: 不支持的 URL
    """
    for crawler_class in _crawlers.values():
        if crawler_class.can_handle(url):
            return crawler_class()

    # 构建支持的域名列表
    supported = []
    for c in _crawlers.values():
        for pattern in c.URL_PATTERNS:
            # 提取域名提示
            if "manhuagui" in pattern:
                supported.append("漫画柜 (manhuagui.com)")

    raise ValueError(f"不支持的 URL: {url}\n支持的平台: {', '.join(set(supported)) or '暂无'}")


def get_crawler_by_platform(platform: str) -> Optional[BaseCrawler]:
    """
    根据平台名称获取爬虫实例

    Args:
        platform: 平台标识

    Returns:
        BaseCrawler: 爬虫实例，如果不存在返回 None
    """
    crawler_class = _crawlers.get(platform)
    if crawler_class:
        return crawler_class()
    return None


def get_supported_platforms() -> List[Dict]:
    """
    获取支持的平台列表

    Returns:
        List[Dict]: 平台信息列表
    """
    platforms = []
    for crawler_class in _crawlers.values():
        platforms.append({
            "name": crawler_class.PLATFORM_NAME,
            "display_name": crawler_class.PLATFORM_DISPLAY_NAME,
            "patterns": crawler_class.URL_PATTERNS,
        })
    return platforms


def get_all_crawlers() -> Dict[str, Type[BaseCrawler]]:
    """获取所有已注册的爬虫"""
    return _crawlers.copy()


# 自动导入并注册爬虫
def _auto_register():
    """自动注册 crawlers 目录下的所有爬虫"""
    import importlib
    import pkgutil
    from pathlib import Path

    crawlers_dir = Path(__file__).parent

    for _, module_name, _ in pkgutil.iter_modules([str(crawlers_dir)]):
        if module_name in ('__init__', 'base', 'registry'):
            continue

        try:
            module = importlib.import_module(f'.{module_name}', package='crawlers')
            # 查找模块中的爬虫类
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseCrawler)
                    and attr is not BaseCrawler
                    and attr.PLATFORM_NAME
                ):
                    register_crawler(attr)
        except Exception as e:
            logger.error(f"加载爬虫模块 {module_name} 失败: {e}")


# 模块加载时自动注册
_auto_register()