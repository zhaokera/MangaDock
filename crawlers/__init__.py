"""
漫画爬虫模块
支持多平台的插件式架构
"""

from .base import BaseCrawler, MangaInfo, DownloadProgress
from .registry import get_crawler, get_supported_platforms, register_crawler

__all__ = [
    'BaseCrawler',
    'MangaInfo',
    'DownloadProgress',
    'get_crawler',
    'get_supported_platforms',
    'register_crawler',
]