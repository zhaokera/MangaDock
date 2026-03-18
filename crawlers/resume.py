"""断点续传模块

支持下载进度保存和恢复，避免重复下载。
"""

import json
import hashlib
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ResumeInfo:
    """断点续传信息"""
    task_id: str
    url: str
    platform: str
    total: int = 0
    downloaded_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    downloaded_urls: List[str] = field(default_factory=list)
    failed_urls: dict = field(default_factory=dict)  # {url: error_msg}
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'task_id': self.task_id,
            'url': self.url,
            'platform': self.platform,
            'total': self.total,
            'downloaded_count': self.downloaded_count,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'downloaded_urls': self.downloaded_urls,
            'failed_urls': self.failed_urls,
            'created_at': self.created_at,
            'last_updated': self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ResumeInfo':
        """从字典创建实例"""
        return cls(
            task_id=data['task_id'],
            url=data['url'],
            platform=data['platform'],
            total=data.get('total', 0),
            downloaded_count=data.get('downloaded_count', 0),
            success_count=data.get('success_count', 0),
            failed_count=data.get('failed_count', 0),
            downloaded_urls=data.get('downloaded_urls', []),
            failed_urls=data.get('failed_urls', {}),
            created_at=data.get('created_at'),
            last_updated=data.get('last_updated'),
        )

    def update_progress(self, total: int, downloaded: int, success: int, failed: int):
        """更新进度信息"""
        self.total = total
        self.downloaded_count = downloaded
        self.success_count = success
        self.failed_count = failed
        self.last_updated = datetime.now().isoformat()


class ResumeManager:
    """断点续传管理器

    负责管理下载进度的保存和恢复。
    """

    def __init__(self, resume_dir: str = "resumes"):
        self.resume_dir = Path(resume_dir)
        self.resume_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, ResumeInfo] = {}

    def _get_resume_path(self, task_id: str) -> Path:
        """获取进度文件路径"""
        task_hash = hashlib.md5(task_id.encode()).hexdigest()[:8]
        return self.resume_dir / f"{task_hash}_{task_id}.json"

    async def save_progress(self, info: ResumeInfo) -> bool:
        """保存进度"""
        try:
            self._cache[info.task_id] = info
            resume_path = self._get_resume_path(info.task_id)
            with open(resume_path, 'w', encoding='utf-8') as f:
                json.dump(info.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"进度已保存: {info.task_id} ({info.downloaded_count}/{info.total})")
            return True
        except Exception as e:
            logger.error(f"保存进度失败 {info.task_id}: {e}")
            return False

    async def load_progress(self, task_id: str) -> Optional[ResumeInfo]:
        """加载进度"""
        if task_id in self._cache:
            return self._cache[task_id]

        resume_path = self._get_resume_path(task_id)
        if not resume_path.exists():
            return None

        try:
            with open(resume_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            info = ResumeInfo.from_dict(data)
            self._cache[info.task_id] = info
            logger.debug(f"进度已加载: {info.task_id} ({info.downloaded_count}/{info.total})")
            return info
        except Exception as e:
            logger.error(f"加载进度失败 {task_id}: {e}")
            return None

    async def remove_progress(self, task_id: str) -> bool:
        """移除进度"""
        if task_id in self._cache:
            del self._cache[task_id]

        resume_path = self._get_resume_path(task_id)
        try:
            if resume_path.exists():
                resume_path.unlink()
            return True
        except Exception as e:
            logger.error(f"移除进度失败 {task_id}: {e}")
            return False

    async def get_all_resumes(self) -> List[ResumeInfo]:
        """获取所有进度记录"""
        resumes = []
        if self.resume_dir.exists():
            for file in self.resume_dir.glob("*.json"):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    resumes.append(ResumeInfo.from_dict(data))
                except Exception:
                    continue
        return resumes

    async def cleanup_old_resumes(self, days: int = 7) -> int:
        """清理旧的进度记录"""
        import time
        current_time = time.time()
        cleaned = 0

        if self.resume_dir.exists():
            for file in self.resume_dir.glob("*.json"):
                try:
                    mtime = file.stat().st_mtime
                    if current_time - mtime > days * 86400:
                        file.unlink()
                        cleaned += 1
                        logger.info(f"清理旧进度: {file.name}")
                except Exception:
                    continue

        return cleaned


# 全局管理器实例
_resume_manager: Optional[ResumeManager] = None


def get_resume_manager(resume_dir: Optional[str] = None) -> ResumeManager:
    """获取全局断点续传管理器"""
    global _resume_manager
    if _resume_manager is None:
        _resume_manager = ResumeManager(resume_dir or "resumes")
    return _resume_manager


def reset_resume_manager():
    """重置全局管理器（测试用）"""
    global _resume_manager
    _resume_manager = None
