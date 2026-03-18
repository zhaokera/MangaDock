"""元数据管理模块

提供漫画元数据的提取、保存和导出功能。
"""

import json
import zipfile
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MangaMetadata:
    """漫画元数据"""
    # 基本信息
    title: str = ""
    author: str = ""
    description: str = ""
    cover_url: str = ""
    tags: List[str] = field(default_factory=list)

    # 来源信息
    platform: str = ""
    source_url: str = ""
    comic_id: str = ""
    episode_id: str = ""

    # 下载信息
    page_count: int = 0
    download_date: str = field(default_factory=lambda: datetime.now().isoformat())
    download_status: str = "completed"  # completed, partial, failed

    # 导出信息
    exported_cbz: bool = False
    cbz_path: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'title': self.title,
            'author': self.author,
            'description': self.description,
            'cover_url': self.cover_url,
            'tags': self.tags,
            'platform': self.platform,
            'source_url': self.source_url,
            'comic_id': self.comic_id,
            'episode_id': self.episode_id,
            'page_count': self.page_count,
            'download_date': self.download_date,
            'download_status': self.download_status,
            'exported_cbz': self.exported_cbz,
            'cbz_path': self.cbz_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MangaMetadata':
        """从字典创建实例"""
        return cls(
            title=data.get('title', ''),
            author=data.get('author', ''),
            description=data.get('description', ''),
            cover_url=data.get('cover_url', ''),
            tags=data.get('tags', []),
            platform=data.get('platform', ''),
            source_url=data.get('source_url', ''),
            comic_id=data.get('comic_id', ''),
            episode_id=data.get('episode_id', ''),
            page_count=data.get('page_count', 0),
            download_date=data.get('download_date', ''),
            download_status=data.get('download_status', 'completed'),
            exported_cbz=data.get('exported_cbz', False),
            cbz_path=data.get('cbz_path', ''),
        )

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'MangaMetadata':
        """从JSON字符串创建实例"""
        return cls.from_dict(json.loads(json_str))


class MetadataManager:
    """元数据管理器"""

    def __init__(self, metadata_dir: str = "metadata"):
        self.metadata_dir = Path(metadata_dir)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def _get_metadata_path(self, task_id: str) -> Path:
        """获取元数据文件路径"""
        return self.metadata_dir / f"{task_id}_metadata.json"

    async def save_metadata(self, metadata: MangaMetadata) -> bool:
        """保存元数据"""
        try:
            metadata_path = self._get_metadata_path(metadata.comic_id or metadata.title)
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"元数据已保存: {metadata.title}")
            return True
        except Exception as e:
            logger.error(f"保存元数据失败 {metadata.title}: {e}")
            return False

    async def load_metadata(self, task_id: str) -> Optional[MangaMetadata]:
        """加载元数据"""
        metadata_path = self._get_metadata_path(task_id)
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            metadata = MangaMetadata.from_dict(data)
            logger.debug(f"元数据已加载: {metadata.title}")
            return metadata
        except Exception as e:
            logger.error(f"加载元数据失败 {task_id}: {e}")
            return None

    async def delete_metadata(self, task_id: str) -> bool:
        """删除元数据"""
        metadata_path = self._get_metadata_path(task_id)
        try:
            if metadata_path.exists():
                metadata_path.unlink()
            return True
        except Exception as e:
            logger.error(f"删除元数据失败 {task_id}: {e}")
            return False

    async def get_all_metadata(self) -> List[MangaMetadata]:
        """获取所有元数据"""
        metadatas = []
        if self.metadata_dir.exists():
            for file in self.metadata_dir.glob("*_metadata.json"):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    metadatas.append(MangaMetadata.from_dict(data))
                except Exception:
                    continue
        return metadatas


# 全局管理器实例
_metadata_manager: Optional[MetadataManager] = None


def get_metadata_manager(metadata_dir: Optional[str] = None) -> MetadataManager:
    """获取全局元数据管理器"""
    global _metadata_manager
    if _metadata_manager is None:
        _metadata_manager = MetadataManager(metadata_dir or "metadata")
    return _metadata_manager


def reset_metadata_manager():
    """重置全局管理器（测试用）"""
    global _metadata_manager
    _metadata_manager = None


def export_to_cbz(image_dir: Path, output_path: Path, metadata: Optional[MangaMetadata] = None) -> bool:
    """
    将下载的图片导出为CBZ格式（Comic Book ZIP）

    Args:
        image_dir: 图片目录
        output_path: 输出CBZ文件路径
        metadata: 可选的元数据，用于添加封面

    Returns:
        bool: 是否成功
    """
    try:
        # 获取所有图片文件
        image_files = sorted([
            f for f in image_dir.iterdir()
            if f.is_file() and f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp', '.gif']
        ])

        if not image_files:
            logger.error("没有找到图片文件")
            return False

        # 创建CBZ文件
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as cbz:
            # 添加封面（第一张图片）
            if image_files:
                cbz.write(image_files[0], "cover.jpg")

            # 添加所有图片
            for i, image_file in enumerate(image_files, 1):
                # 生成CBZ内部文件名
                ext = image_file.suffix.lower()
                if ext == '.jpeg':
                    ext = '.jpg'
                cbz_filename = f"{i:03d}{ext}"
                cbz.write(image_file, cbz_filename)

            # 添加元数据（如果提供）
            if metadata:
                metadata_json = metadata.to_json().encode('utf-8')
                cbz.writestr("metadata.json", metadata_json)

        logger.info(f"CBZ导出成功: {output_path} ({len(image_files)} 张图片)")
        return True

    except Exception as e:
        logger.error(f"CBZ导出失败: {e}")
        return False


def validate_cbz(cbz_path: Path) -> bool:
    """
    验证CBZ文件是否有效

    Args:
        cbz_path: CBZ文件路径

    Returns:
        bool: 是否有效
    """
    try:
        with zipfile.ZipFile(cbz_path, 'r') as cbz:
            # 检查是否有至少一张图片
            image_files = [f for f in cbz.namelist()
                          if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif'))]
            if not image_files:
                return False

            # 检查文件是否完整（不损坏）
            test_result = cbz.testzip()
            if test_result is not None:
                logger.error(f"CBZ文件损坏: {test_result}")
                return False

        return True
    except zipfile.BadZipFile:
        return False
    except Exception as e:
        logger.error(f"CBZ验证失败: {e}")
        return False
