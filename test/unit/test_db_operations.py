"""数据库操作单元测试"""

import sqlite3

import pytest
from crawlers.db import (
    TaskRecord,
    close_connection,
    save_task,
    get_task,
    delete_task,
    update_task_status,
    get_all_tasks,
    get_history_tasks,
    init_db,
    serialize_manga_info,
    deserialize_manga_info,
)


class TestTaskRecord:
    """TaskRecord 数据类测试"""

    def test_to_dict(self):
        """测试 to_dict 方法"""
        record = TaskRecord(
            task_id="test-123",
            url="https://example.com",
            platform="manhuagui",
            status="completed",
            progress=100,
            total=10,
        )
        result = record.to_dict()

        assert result["task_id"] == "test-123"
        assert result["url"] == "https://example.com"
        assert result["platform"] == "manhuagui"
        assert result["status"] == "completed"
        assert result["progress"] == 100
        assert result["total"] == 10

    def test_to_dict_with_none_values(self):
        """测试包含 None 值的 to_dict"""
        record = TaskRecord(
            task_id="test-456",
            url="https://example.com",
            platform="kuaikan",
        )
        result = record.to_dict()

        assert result["manga_info"] is None
        assert result["error"] is None

    def test_to_dict_with_manga_info(self):
        """测试包含 manga_info 的 to_dict"""
        from crawlers.base import MangaInfo
        info = MangaInfo(title="Test Comic", chapter="Chapter 1")
        record = TaskRecord(
            task_id="test-789",
            url="https://example.com",
            platform="test",
            manga_info=info,
        )
        result = record.to_dict()

        # manga_info 保持为 MangaInfo 对象
        assert result["manga_info"].title == "Test Comic"
        assert result["manga_info"].chapter == "Chapter 1"


class TestSerializeMangaInfo:
    """序列化函数测试"""

    def test_serialize_dict(self):
        """序列化字典"""
        data = {"title": "Test Comic", "chapter": "Chapter 1"}
        result = serialize_manga_info(data)

        assert result is not None
        assert "Test Comic" in result

    def test_serialize_none(self):
        """序列化 None"""
        result = serialize_manga_info(None)
        assert result is None

    def test_serialize_manga_info_object(self):
        """序列化 MangaInfo 对象"""
        from crawlers.base import MangaInfo
        info = MangaInfo(title="Test Comic", chapter="Chapter 1")
        result = serialize_manga_info(info)

        assert result is not None
        assert "Test Comic" in result


class TestDeserializeMangaInfo:
    """反序列化函数测试"""

    def test_deserialize_json(self):
        """反序列化 JSON 字符串"""
        json_str = '{"title": "Test Comic", "chapter": "Chapter 1"}'
        result = deserialize_manga_info(json_str)

        assert result is not None
        assert result["title"] == "Test Comic"

    def test_deserialize_none(self):
        """反序列化 None"""
        result = deserialize_manga_info(None)
        assert result is None

    def test_deserialize_empty_string_returns_none(self):
        """测试反序列化空字符串返回 None"""
        result = deserialize_manga_info("")
        assert result is None


class TestDatabaseOperations:
    """数据库操作测试"""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """临时数据库路径"""
        return tmp_path / "test.db"

    @pytest.fixture
    def db_with_path(self, temp_db_path):
        """设置数据库路径"""
        import crawlers.db as db_module
        original_path = db_module.DB_PATH
        db_module.DB_PATH = temp_db_path
        init_db()
        yield temp_db_path
        # 清理
        db_module.DB_PATH = original_path
        # 关闭连接
        db_module.close_connection()

    def test_save_and_get_task(self, db_with_path):
        """测试保存和获取任务"""
        task_id = "test-task-123"
        url = "https://www.manhuagui.com/comic/123/456.html"

        record = TaskRecord(
            task_id=task_id,
            url=url,
            platform="manhuagui",
            status="pending",
        )
        save_task(record)

        retrieved = get_task(task_id)
        assert retrieved is not None
        assert retrieved.task_id == task_id
        assert retrieved.url == url
        assert retrieved.platform == "manhuagui"
        assert retrieved.status == "pending"

    def test_reopens_connection_when_db_path_changes(self, tmp_path):
        """测试切换 DB_PATH 时会重新打开连接而不是复用旧连接"""
        import crawlers.db as db_module

        original_path = db_module.DB_PATH
        first_db_path = tmp_path / "first.db"
        second_db_path = tmp_path / "second.db"

        try:
            close_connection()

            db_module.DB_PATH = first_db_path
            init_db()
            save_task(
                TaskRecord(
                    task_id="task-first",
                    url="https://example.com/first",
                    platform="test",
                )
            )

            db_module.DB_PATH = second_db_path
            init_db()
            save_task(
                TaskRecord(
                    task_id="task-second",
                    url="https://example.com/second",
                    platform="test",
                )
            )

            with sqlite3.connect(first_db_path) as first_conn:
                first_task_ids = {
                    row[0]
                    for row in first_conn.execute("SELECT task_id FROM tasks")
                }

            with sqlite3.connect(second_db_path) as second_conn:
                second_task_ids = {
                    row[0]
                    for row in second_conn.execute("SELECT task_id FROM tasks")
                }

            assert first_task_ids == {"task-first"}
            assert second_task_ids == {"task-second"}
        finally:
            close_connection()
            db_module.DB_PATH = original_path

    def test_delete_task(self, db_with_path):
        """测试删除任务"""
        task_id = "test-delete-task"

        record = TaskRecord(
            task_id=task_id,
            url="https://example.com",
            platform="test",
            status="pending",
        )
        save_task(record)

        # 验证任务存在
        assert get_task(task_id) is not None

        # 删除任务
        result = delete_task(task_id)
        assert result is True

        # 验证任务已删除
        assert get_task(task_id) is None

    def test_update_task_status(self, db_with_path):
        """测试更新任务状态"""
        task_id = "test-status-update"

        record = TaskRecord(
            task_id=task_id,
            url="https://example.com",
            platform="test",
            status="pending",
        )
        save_task(record)

        # 更新状态
        result = update_task_status(task_id, "downloading", "Downloading...")
        assert result is True

        retrieved = get_task(task_id)
        assert retrieved.status == "downloading"
        assert retrieved.message == "Downloading..."

    def test_get_all_tasks(self, db_with_path):
        """测试获取所有任务"""
        # 创建多个任务
        for i in range(3):
            record = TaskRecord(
                task_id=f"task-{i}",
                url=f"https://example.com/{i}",
                platform="test",
                status="pending",
            )
            save_task(record)

        tasks = get_all_tasks()
        assert len(tasks) >= 3

    def test_get_history_tasks(self, db_with_path):
        """测试获取历史任务"""
        # 创建已完成任务
        for i in range(3):
            record = TaskRecord(
                task_id=f"completed-{i}",
                url=f"https://example.com/completed-{i}",
                platform="test",
                status="completed",
            )
            save_task(record)

        # 创建进行中任务
        record = TaskRecord(
            task_id="in-progress",
            url="https://example.com/in-progress",
            platform="test",
            status="downloading",
        )
        save_task(record)

        history = get_history_tasks()
        # 至少有 3 个已完成任务
        assert len(history) >= 3

        # 验证所有历史任务都是完成或失败状态
        for task in history:
            assert task.status in ("completed", "failed")
