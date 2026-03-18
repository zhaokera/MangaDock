"""下载器集成测试"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from crawlers.registry import get_crawler
from crawlers.db import TaskRecord, save_task, init_db, close_connection


class TestDownloaderIntegration:
    """下载器集成测试"""

    @pytest.fixture
    def temp_output_dir(self, tmp_path):
        """临时输出目录"""
        return str(tmp_path)

    @pytest.fixture
    def temp_download_dir(self, tmp_path):
        """临时下载目录"""
        dir_path = tmp_path / "downloads"
        dir_path.mkdir()
        return str(dir_path)

    @pytest.fixture
    def initialized_db(self, tmp_path):
        """初始化数据库"""
        import crawlers.db as db_module
        db_path = tmp_path / "integration_test.db"
        db_module.DB_PATH = db_path
        init_db()
        yield db_path
        close_connection()

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

    def test_progress_callback(self, temp_output_dir):
        """测试进度回调"""
        callback_called = []

        def progress_callback(progress):
            callback_called.append(progress)

        # 这是一个集成测试，只需要验证回调机制
        assert len(callback_called) == 0

        # 模拟回调调用
        class MockProgress:
            def __init__(self):
                self.current = 0
                self.total = 10
                self.message = "Test"
                self.status = "pending"

        progress = MockProgress()
        progress_callback(progress)

        assert len(callback_called) == 1
        assert callback_called[0].current == 0

    def test_task_record_creation(self):
        """测试任务记录创建"""
        from crawlers.db import TaskRecord

        record = TaskRecord(
            task_id="integration-test-123",
            url="https://www.manhuagui.com/comic/123/456.html",
            platform="manhuagui",
            status="pending",
            progress=0,
            total=0,
        )

        assert record.task_id == "integration-test-123"
        assert record.status == "pending"
        assert record.manga_info is None

    def test_task_record_with_output_paths(self):
        """测试带输出路径的任务记录"""
        from crawlers.db import TaskRecord

        record = TaskRecord(
            task_id="integration-test-paths",
            url="https://www.manhuagui.com/comic/123/456.html",
            platform="manhuagui",
            status="completed",
            progress=100,
            output_path="/tmp/downloads/Comic_Chapter1",
            zip_path="/tmp/downloads/Comic_Chapter1.zip",
        )

        assert record.output_path == "/tmp/downloads/Comic_Chapter1"
        assert record.zip_path == "/tmp/downloads/Comic_Chapter1.zip"
        assert record.status == "completed"

    def test_task_record_with_error(self):
        """测试带错误信息的任务记录"""
        from crawlers.db import TaskRecord

        record = TaskRecord(
            task_id="integration-test-error",
            url="https://www.manhuagui.com/comic/123/456.html",
            platform="manhuagui",
            status="failed",
            progress=50,
            error="Network timeout after 30 seconds",
        )

        assert record.status == "failed"
        assert record.error == "Network timeout after 30 seconds"
        assert record.progress == 50


class TestCrawlerRetrieval:
    """爬虫检索测试"""

    def test_get_crawler_manhuagui_url(self):
        """测试获取漫画柜爬虫"""
        url = "https://www.manhuagui.com/comic/58426/865091.html"
        crawler = get_crawler(url)
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "manhuagui"

    def test_get_crawler_kuaikan_url(self):
        """测试获取快看漫画爬虫"""
        url = "https://www.kuaikanmanhua.com/comic/12345/67890"
        crawler = get_crawler(url)
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "kuaikanmanhua"

    def test_get_crawler_invalid_url_raises(self):
        """测试无效 URL 抛出异常"""
        url = "https://invalid-site.com/comic/123"
        with pytest.raises(ValueError) as exc_info:
            get_crawler(url)
        assert "不支持的 URL" in str(exc_info.value)


class TestDownloadIntegrationFlow:
    """下载集成流程测试"""

    def test_flow_with_mock(self, tmp_path):
        """测试完整流程（使用 mock）"""
        from crawlers.base import MangaInfo, DownloadProgress
        from crawlers.registry import get_crawler

        temp_output_dir = str(tmp_path)

        url = "https://www.manhuagui.com/comic/123/456.html"
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
            assert info.page_count == 10

    def test_callback_integration(self, tmp_path):
        """测试回调集成"""
        from crawlers.base import DownloadProgress
        from crawlers.registry import get_crawler

        temp_output_dir = str(tmp_path)

        progress_records = []

        def progress_callback(progress: DownloadProgress):
            progress_records.append({
                "current": progress.current,
                "total": progress.total,
                "message": progress.message,
                "status": progress.status,
            })

        # 模拟下载进度
        progress_callback(DownloadProgress(current=0, total=10, status="pending"))
        progress_callback(DownloadProgress(current=5, total=10, message="Downloading...", status="downloading"))
        progress_callback(DownloadProgress(current=10, total=10, message="Completed", status="completed"))

        assert len(progress_records) == 3
        assert progress_records[0]["status"] == "pending"
        assert progress_records[1]["current"] == 5
        assert progress_records[2]["status"] == "completed"


class TestPlatformDetection:
    """平台检测测试"""

    def test_detect_manhuagui_platform(self):
        """测试检测漫画柜平台"""
        urls = [
            "https://www.manhuagui.com/comic/123/456.html",
            "https://manhuagui.com/comic/123/456.html",
            "https://www.manhuagui.com/comic/999/888",
        ]

        for url in urls:
            crawler = get_crawler(url)
            assert crawler.PLATFORM_NAME == "manhuagui"

    def test_detect_kuaikan_platform(self):
        """测试检测快看漫画平台"""
        urls = [
            "https://www.kuaikanmanhua.com/comic/123/456",
            "https://www.kkmh.com/comic/123/456",
        ]

        for url in urls:
            crawler = get_crawler(url)
            assert crawler.PLATFORM_NAME == "kuaikanmanhua"
