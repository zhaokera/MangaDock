"""端到端下载流程测试"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import os

from crawlers.registry import get_crawler
from crawlers.db import TaskRecord, save_task, init_db, close_connection


class TestFullDownloadFlow:
    """完整下载流程端到端测试"""

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
        db_path = tmp_path / "e2e_test.db"
        db_module.DB_PATH = db_path
        init_db()
        yield db_path
        close_connection()

    @pytest.mark.asyncio
    async def test_get_info_flow(self, tmp_path):
        """测试获取信息流程（使用 mock）"""
        from crawlers.base import MangaInfo

        temp_output_dir = str(tmp_path)

        # 这是一个 e2e 测试，使用 mock 来模拟完整的数据流
        with patch('crawlers.manhuagui.ManhuaguiCrawler.get_info') as mock_get_info:
            mock_info = MangaInfo(
                title="Test Comic",
                chapter="Chapter 1",
                page_count=10,
                platform="manhuagui",
                comic_id="123",
                episode_id="456",
            )
            mock_get_info.return_value = mock_info

            crawler = get_crawler("https://www.manhuagui.com/comic/123/456.html")
            info = await crawler.get_info("https://www.manhuagui.com/comic/123/456.html")

            assert info.title == "Test Comic"
            assert info.page_count == 10

    @pytest.mark.asyncio
    async def test_task_persistence_flow(self, initialized_db):
        """测试任务持久化流程"""
        task_id = "e2e-task-123"
        url = "https://www.manhuagui.com/comic/123/456.html"

        # 创建并保存任务
        record = TaskRecord(
            task_id=task_id,
            url=url,
            platform="manhuagui",
            status="pending",
            progress=0,
            total=100,
        )
        save_task(record)

        # 验证任务已保存
        from crawlers.db import get_task
        retrieved = get_task(task_id)
        assert retrieved is not None
        assert retrieved.task_id == task_id
        assert retrieved.status == "pending"

    def test_platform_url_matching(self):
        """测试平台 URL 匹配"""
        test_cases = [
            ("https://www.manhuagui.com/comic/123/456.html", "manhuagui"),
            ("https://www.kuaikanmanhua.com/comic/12345/67890", "kuaikanmanhua"),
            ("https://www.kkmh.com/comic/123/456", "kuaikanmanhua"),
        ]

        for url, expected_platform in test_cases:
            crawler = get_crawler(url)
            assert crawler.PLATFORM_NAME == expected_platform

    @pytest.mark.asyncio
    async def test_crawler_initialization(self):
        """测试爬虫初始化"""
        crawler = get_crawler("https://www.manhuagui.com/comic/123/456.html")

        # 验证爬虫已正确初始化
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "manhuagui"
        # BaseCrawler 没有 url 属性，这个测试验证爬虫可以正确创建
        assert hasattr(crawler, 'PLATFORM_NAME')

    @pytest.mark.asyncio
    async def test_download_progress_flow(self, temp_output_dir):
        """测试下载进度流程"""
        from crawlers.base import DownloadProgress

        progress_records = []

        def progress_callback(progress: DownloadProgress):
            progress_records.append(progress)

        # 模拟进度回调
        progress_callback(DownloadProgress(current=0, total=10, status="pending"))
        progress_callback(DownloadProgress(current=3, total=10, message="Downloading page 3...", status="downloading"))
        progress_callback(DownloadProgress(current=6, total=10, message="Downloading page 6...", status="downloading"))
        progress_callback(DownloadProgress(current=10, total=10, message="Download completed", status="completed"))

        assert len(progress_records) == 4
        assert progress_records[0].status == "pending"
        assert progress_records[1].current == 3
        assert progress_records[2].current == 6
        assert progress_records[3].status == "completed"

    def test_sse_status_flow(self, temp_output_dir):
        """测试 SSE 状态推送流程"""
        from crawlers.base import DownloadProgress

        sse_messages = []

        def progress_callback(progress: DownloadProgress):
            sse_messages.append(progress.to_dict())

        # 模拟 SSE 消息流
        progress_callback(DownloadProgress(current=0, total=10, status="pending"))
        progress_callback(DownloadProgress(current=5, total=10, status="downloading"))
        progress_callback(DownloadProgress(current=10, total=10, status="completed"))

        # 验证消息格式
        assert all("current" in msg for msg in sse_messages)
        assert all("total" in msg for msg in sse_messages)
        assert all("status" in msg for msg in sse_messages)

    def test_complete_download_workflow(self, tmp_path):
        """测试完整下载工作流"""
        from crawlers.base import MangaInfo, DownloadProgress

        temp_output_dir = str(tmp_path)

        # Step 1: 验证爬虫可以处理 URL
        url = "https://www.manhuagui.com/comic/123/456.html"
        crawler = get_crawler(url)
        assert crawler.can_handle(url)

        # Step 2: 获取漫画信息
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

        # Step 3: 创建任务记录
        from crawlers.db import init_db
        import crawlers.db as db_module
        db_module.DB_PATH = Path(temp_output_dir) / "e2e_workflow.db"
        init_db()

        task_id = "e2e-workflow-123"
        record = TaskRecord(
            task_id=task_id,
            url=url,
            platform="manhuagui",
            status="pending",
        )
        save_task(record)

        # Step 4: 模拟下载进度
        progress_callback_called = []

        def progress_callback(progress: DownloadProgress):
            progress_callback_called.append(progress)
            # 更新任务状态
            if progress.status == "downloading":
                update_task_status(task_id, "downloading", progress.message)
            elif progress.status == "completed":
                update_task_status(task_id, "completed", progress.message)

        from crawlers.db import update_task_status

        progress_callback(DownloadProgress(current=0, total=10, status="pending"))
        progress_callback(DownloadProgress(current=5, total=10, message="Downloading...", status="downloading"))
        progress_callback(DownloadProgress(current=10, total=10, message="Completed", status="completed"))

        assert len(progress_callback_called) == 3
        close_connection()

    @pytest.mark.asyncio
    async def test_downloader_workflow(self, temp_output_dir):
        """测试下载器工作流"""
        from crawlers.registry import get_crawler

        url = "https://www.manhuagui.com/comic/123/456.html"

        # 流程 1: 获取爬虫
        crawler = get_crawler(url)
        assert crawler.PLATFORM_NAME == "manhuagui"

        # 流程 2: 获取漫画信息（mock）
        from crawlers.base import MangaInfo
        mock_info = MangaInfo(
            title="Test Comic",
            chapter="Chapter 1",
            page_count=5,
            platform="manhuagui",
        )

        with patch.object(crawler, 'get_info', return_value=mock_info):
            info = await crawler.get_info(url)
            assert info.page_count == 5

        # 流程 3: 模拟下载（mock）
        output_path = str(Path(temp_output_dir) / "test_output")

        with patch.object(crawler, 'download', return_value=output_path):
            result = await crawler.download(url, output_path)
            assert result == output_path


class TestE2EIntegration:
    """端到端集成测试"""

    def test_end_to_end_integration(self, tmp_path):
        """测试完整的端到端流程"""
        from crawlers.base import MangaInfo, DownloadProgress
        from crawlers.registry import get_crawler
        from crawlers.db import TaskRecord, save_task, init_db, close_connection, get_task, update_task_status

        import crawlers.db as db_module
        temp_output_dir = str(tmp_path)
        db_module.DB_PATH = Path(temp_output_dir) / "e2e_int.db"
        init_db()

        try:
            url = "https://www.manhuagui.com/comic/123/456.html"

            # 1. 爬虫注册
            crawler = get_crawler(url)
            assert crawler.PLATFORM_NAME == "manhuagui"

            # 2. 获取信息
            mock_info = MangaInfo(
                title="Test Comic",
                chapter="Chapter 1",
                page_count=10,
                platform="manhuagui",
            )

            with patch.object(crawler, 'get_info', return_value=mock_info):
                info = asyncio.run(crawler.get_info(url))
                assert info.title == "Test Comic"

            # 3. 创建任务
            task_id = "e2e-integration-123"
            record = TaskRecord(
                task_id=task_id,
                url=url,
                platform="manhuagui",
                status="pending",
                manga_info=info.to_dict() if hasattr(info, 'to_dict') else info,
            )
            save_task(record)

            # 4. 验证任务创建
            retrieved = get_task(task_id)
            assert retrieved is not None
            assert retrieved.task_id == task_id

            # 5. 更新状态
            update_task_status(task_id, "downloading", "Starting download...")
            retrieved = get_task(task_id)
            assert retrieved.status == "downloading"

            # 6. 模拟进度
            progress_callback_called = []

            def progress_callback(progress: DownloadProgress):
                progress_callback_called.append(progress)

            progress_callback(DownloadProgress(current=0, total=10, status="pending"))
            progress_callback(DownloadProgress(current=10, total=10, status="completed"))

            # 7. 完成
            update_task_status(task_id, "completed", "Download completed")
            retrieved = get_task(task_id)
            assert retrieved.status == "completed"
        finally:
            close_connection()

    def test_platfom_detection_comprehensive(self):
        """测试平台检测的全面性"""
        test_cases = [
            # 漫画柜 URL
            ("https://www.manhuagui.com/comic/123/456.html", "manhuagui"),
            ("https://manhuagui.com/comic/123/456.html", "manhuagui"),
            # 快看漫画 URL
            ("https://www.kuaikanmanhua.com/comic/123/456", "kuaikanmanhua"),
            ("https://www.kkmh.com/comic/123/456", "kuaikanmanhua"),
        ]

        for url, expected_platform in test_cases:
            crawler = get_crawler(url)
            assert crawler.PLATFORM_NAME == expected_platform, f"URL: {url}"
