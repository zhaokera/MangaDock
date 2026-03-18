"""爬虫与数据库集成测试"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from crawlers.db import (
    TaskRecord,
    save_task,
    get_task,
    update_task_status,
    init_db,
    close_connection,
    get_all_tasks,
    get_history_tasks,
)
from crawlers.registry import get_crawler


class TestCrawlerWithDatabase:
    """爬虫与数据库集成测试"""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """临时数据库路径"""
        return tmp_path / "test_tasks.db"

    @pytest.fixture
    def initialized_db(self, temp_db_path):
        """初始化数据库"""
        import crawlers.db as db_module
        db_module.DB_PATH = temp_db_path
        init_db()
        yield temp_db_path
        close_connection()

    def test_save_and_retrieve_task(self, initialized_db):
        """测试保存和检索任务"""
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

    def test_update_task_progress(self, initialized_db):
        """测试更新任务进度"""
        task_id = "test-task-progress"

        record = TaskRecord(
            task_id=task_id,
            url="https://example.com",
            platform="test",
            status="pending",
            progress=0,
            total=100,
        )
        save_task(record)

        # 更新进度
        from crawlers.db import update_task_progress
        result = update_task_progress(task_id, 50, 100, "Downloading 50%...")
        assert result is True

        retrieved = get_task(task_id)
        assert retrieved.progress == 50
        assert retrieved.total == 100
        assert retrieved.message == "Downloading 50%..."

    def test_update_task_status(self, initialized_db):
        """测试更新任务状态"""
        task_id = "test-task-update"

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

        # 再次更新为完成
        result = update_task_status(task_id, "completed", "Download completed")
        assert result is True

        retrieved = get_task(task_id)
        assert retrieved.status == "completed"
        assert retrieved.message == "Download completed"

    def test_delete_task(self, initialized_db):
        """测试删除任务"""
        task_id = "test-task-delete"

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
        from crawlers.db import delete_task
        result = delete_task(task_id)
        assert result is True

        # 验证任务已删除
        assert get_task(task_id) is None

    def test_get_all_tasks(self, initialized_db):
        """测试获取所有任务"""
        # 创建多个任务
        for i in range(5):
            record = TaskRecord(
                task_id=f"task-{i}",
                url=f"https://example.com/{i}",
                platform="test",
                status="pending" if i < 3 else "completed",
            )
            save_task(record)

        tasks = get_all_tasks()
        assert len(tasks) >= 5

        # 验证所有任务都可以被检索
        for i in range(5):
            task = get_task(f"task-{i}")
            assert task is not None
            assert task.task_id == f"task-{i}"

    def test_get_history_tasks(self, initialized_db):
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

        # 创建失败任务
        record = TaskRecord(
            task_id="failed",
            url="https://example.com/failed",
            platform="test",
            status="failed",
            error="Connection timeout",
        )
        save_task(record)

        history = get_history_tasks()
        # 至少有 4 个历史任务 (3 completed + 1 failed)
        assert len(history) >= 4

        # 验证所有历史任务都是完成或失败状态
        for task in history:
            assert task.status in ("completed", "failed")

    def test_get_history_tasks_by_platform(self, initialized_db):
        """测试按平台获取历史任务"""
        # 创建不同平台的任务
        for i in range(2):
            record = TaskRecord(
                task_id=f"manhuagui-completed-{i}",
                url=f"https://example.com/manhuagui-{i}",
                platform="manhuagui",
                status="completed",
            )
            save_task(record)

        for i in range(2):
            record = TaskRecord(
                task_id=f"kuaikan-completed-{i}",
                url=f"https://example.com/kuaikan-{i}",
                platform="kuaikan",
                status="completed",
            )
            save_task(record)

        # 只获取 manhuagui 的历史任务
        history = get_history_tasks(platform="manhuagui")
        assert len(history) >= 2

        # 验证所有返回的任务都是 manhuagui 平台
        for task in history:
            assert task.platform == "manhuagui"


class TestCrawlerRegistration:
    """爬虫注册测试"""

    def test_get_crawler_by_platform(self):
        """测试按平台获取爬虫"""
        from crawlers.registry import get_crawler_by_platform

        # 测试漫画柜
        crawler = get_crawler_by_platform("manhuagui")
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "manhuagui"

        # 测试快看漫画
        crawler = get_crawler_by_platform("kuaikanmanhua")
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "kuaikanmanhua"

    def test_get_crawler_by_url(self):
        """测试按 URL 获取爬虫"""
        # 漫画柜 URL
        crawler = get_crawler("https://www.manhuagui.com/comic/123/456.html")
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "manhuagui"

    def test_get_crawler_invalid_url(self):
        """测试无效 URL 应抛出异常"""
        from crawlers.registry import get_crawler

        with pytest.raises(ValueError) as exc_info:
            get_crawler("https://invalid-domain.com/comic/123")

        assert "不支持的 URL" in str(exc_info.value)


class TestCrawlerIntegrationFlow:
    """爬虫集成流程测试"""

    def test_complete_flow_with_mock(self, temp_db_path, temp_download_dir):
        """测试完整流程（使用 mock）"""
        import crawlers.db as db_module
        db_module.DB_PATH = temp_db_path
        init_db()

        try:
            # 1. 创建任务
            task_id = "integration-flow-123"
            url = "https://www.manhuagui.com/comic/123/456.html"

            record = TaskRecord(
                task_id=task_id,
                url=url,
                platform="manhuagui",
                status="pending",
                progress=0,
                total=10,
            )
            save_task(record)

            # 2. 模拟爬虫处理
            from crawlers.base import MangaInfo
            from crawlers.registry import get_crawler

            crawler = get_crawler(url)

            # Mock get_info 方法
            mock_info = MangaInfo(
                title="Test Comic",
                chapter="Chapter 1",
                page_count=10,
                platform="manhuagui",
                comic_id="123",
                episode_id="456",
            )

            with patch.object(crawler, 'get_info', return_value=mock_info):
                info = asyncio.run(crawler.get_info(url))
                assert info.title == "Test Comic"

                # 3. 更新任务状态
                update_task_status(task_id, "downloading", f"Downloading {info.title}")
                retrieved = get_task(task_id)
                assert retrieved.status == "downloading"

                # 4. 完成下载
                update_task_status(task_id, "completed", "Download completed")
                retrieved = get_task(task_id)
                assert retrieved.status == "completed"
        finally:
            close_connection()
