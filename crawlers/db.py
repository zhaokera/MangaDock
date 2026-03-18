"""
数据库模块 - SQLite 任务持久化
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime

from .base import MangaInfo, DownloadProgress

# 数据库文件路径
DB_DIR = Path.home() / ".comic_downloader"
DB_PATH = DB_DIR / "tasks.db"


@dataclass
class TaskRecord:
    """任务记录数据类"""
    task_id: str
    url: str
    platform: str
    status: str = "pending"
    progress: int = 0
    total: int = 0
    message: str = ""
    manga_info: Optional[Dict] = None
    output_path: Optional[str] = None
    zip_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "url": self.url,
            "platform": self.platform,
            "status": self.status,
            "progress": self.progress,
            "total": self.total,
            "message": self.message,
            "manga_info": self.manga_info,
            "output_path": self.output_path,
            "zip_path": self.zip_path,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TaskRecord":
        """从数据库行创建"""
        return cls(
            task_id=row["task_id"],
            url=row["url"],
            platform=row["platform"],
            status=row["status"],
            progress=row["progress"],
            total=row["total"],
            message=row["message"],
            manga_info=json.loads(row["manga_info"]) if row["manga_info"] else None,
            output_path=row["output_path"],
            zip_path=row["zip_path"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# 线程-local 的连接
_thread_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """获取线程-local 的数据库连接"""
    conn = getattr(_thread_local, "conn", None)
    if conn is None:
        # 确保目录存在
        DB_DIR.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            str(DB_PATH),
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row

        # 启用 WAL 模式以提高并发性能
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")

        _thread_local.conn = conn

    return conn


def close_connection():
    """关闭线程-local 的数据库连接"""
    conn = getattr(_thread_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        finally:
            _thread_local.conn = None


def init_db():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            platform TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            message TEXT DEFAULT '',
            manga_info TEXT,
            output_path TEXT,
            zip_path TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # 创建索引以提高查询性能
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_status
        ON tasks(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_platform
        ON tasks(platform)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_tasks_created_at
        ON tasks(created_at)
    """)

    conn.commit()


def serialize_manga_info(info: Optional[Union[Dict, MangaInfo]]) -> Optional[str]:
    """序列化 MangaInfo 为 JSON 字符串"""
    if info is None:
        return None
    if isinstance(info, MangaInfo):
        info = info.to_dict()
    return json.dumps(info, ensure_ascii=False)


def deserialize_manga_info(json_str: Optional[str]) -> Optional[Dict]:
    """反序列化 JSON 字符串为 MangaInfo 字典"""
    if json_str is None:
        return None
    return json.loads(json_str)


def save_task(record: TaskRecord) -> None:
    """保存任务记录"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    if not record.created_at:
        record.created_at = now
    record.updated_at = now

    cursor.execute("""
        INSERT OR REPLACE INTO tasks
        (task_id, url, platform, status, progress, total, message,
         manga_info, output_path, zip_path, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.task_id,
        record.url,
        record.platform,
        record.status,
        record.progress,
        record.total,
        record.message,
        serialize_manga_info(record.manga_info),
        record.output_path,
        record.zip_path,
        record.error,
        record.created_at,
        record.updated_at,
    ))

    conn.commit()


def get_task(task_id: str) -> Optional[TaskRecord]:
    """获取任务记录"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
    row = cursor.fetchone()

    if row:
        return TaskRecord.from_row(row)
    return None


def delete_task(task_id: str) -> bool:
    """删除任务记录"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
    conn.commit()

    return cursor.rowcount > 0


def get_tasks_by_status(status: str, limit: int = 50, offset: int = 0) -> List[TaskRecord]:
    """根据状态获取任务记录"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (status, limit, offset)
    )
    rows = cursor.fetchall()

    return [TaskRecord.from_row(row) for row in rows]


def get_all_tasks(limit: int = 100, offset: int = 0) -> List[TaskRecord]:
    """获取所有任务记录"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    )
    rows = cursor.fetchall()

    return [TaskRecord.from_row(row) for row in rows]


def get_history_tasks(platform: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[TaskRecord]:
    """获取历史任务（已完成或失败）"""
    conn = get_connection()
    cursor = conn.cursor()

    if platform:
        cursor.execute(
            """SELECT * FROM tasks
               WHERE status IN ('completed', 'failed') AND platform = ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (platform, limit, offset)
        )
    else:
        cursor.execute(
            "SELECT * FROM tasks WHERE status IN ('completed', 'failed') ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )

    rows = cursor.fetchall()
    return [TaskRecord.from_row(row) for row in rows]


def get_total_count(status: Optional[str] = None, platform: Optional[str] = None) -> int:
    """获取任务总数"""
    conn = get_connection()
    cursor = conn.cursor()

    if status and platform:
        cursor.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = ? AND platform = ?",
            (status, platform)
        )
    elif status:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (status,))
    elif platform:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE platform = ?", (platform,))
    else:
        cursor.execute("SELECT COUNT(*) FROM tasks")

    return cursor.fetchone()[0]


def update_task_status(task_id: str, status: str, message: str = "") -> bool:
    """更新任务状态"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    cursor.execute(
        "UPDATE tasks SET status = ?, message = ?, updated_at = ? WHERE task_id = ?",
        (status, message, now, task_id)
    )

    conn.commit()
    return cursor.rowcount > 0


def update_task_progress(task_id: str, progress: int, total: int, message: str = "") -> bool:
    """更新任务进度"""
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    cursor.execute(
        "UPDATE tasks SET progress = ?, total = ?, message = ?, updated_at = ? WHERE task_id = ?",
        (progress, total, message, now, task_id)
    )

    conn.commit()
    return cursor.rowcount > 0
