"""
漫画爬虫模块
支持多平台的插件式架构
"""

from .base import BaseCrawler, MangaInfo, DownloadProgress
from .registry import get_crawler, get_supported_platforms, register_crawler
from .db import (
    TaskRecord,
    init_db,
    save_task,
    get_task,
    delete_task,
    get_tasks_by_status,
    get_all_tasks,
    get_history_tasks,
    get_total_count,
    update_task_status,
    update_task_progress,
)

__all__ = [
    'BaseCrawler',
    'MangaInfo',
    'DownloadProgress',
    'get_crawler',
    'get_supported_platforms',
    'register_crawler',
    'TaskRecord',
    'init_db',
    'save_task',
    'get_task',
    'delete_task',
    'get_tasks_by_status',
    'get_all_tasks',
    'get_history_tasks',
    'get_total_count',
    'update_task_status',
    'update_task_progress',
]