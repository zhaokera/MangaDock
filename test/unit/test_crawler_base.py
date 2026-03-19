"""BaseCrawler 基类测试"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typing import List
from crawlers.base import BaseCrawler, MangaInfo, DownloadProgress, DEFAULT_USER_AGENT, DEFAULT_IMAGE_HEADERS


# 创建一个用于测试的最小实现子类
class TestCrawlerImpl(BaseCrawler):
    """用于测试的 BaseCrawler 实现"""

    PLATFORM_NAME = "test"
    PLATFORM_DISPLAY_NAME = "Test"
    URL_PATTERNS = [r"test\.com.*comic"]

    async def get_info(self, url: str) -> MangaInfo:
        return MangaInfo(title="Test", platform="test")

    async def get_image_urls(self, url: str) -> List[str]:
        return []

    async def download(self, url: str, output_dir: str, progress_callback=None) -> str:
        return output_dir


class TestBaseCrawlerCanHandle:
    """BaseCrawler.can_handle() 测试"""

    class TestCrawler(BaseCrawler):
        PLATFORM_NAME = "test"
        PLATFORM_DISPLAY_NAME = "Test"
        URL_PATTERNS = [r"test\.com.*comic"]

    def test_can_match_pattern(self):
        """测试匹配 URL 模式"""
        assert self.TestCrawler.can_handle("https://test.com/comic/123")

    def test_cannot_match_pattern(self):
        """测试不匹配 URL 模式"""
        assert not self.TestCrawler.can_handle("https://other.com/123")

    def test_empty_patterns(self):
        """测试空模式列表"""
        class NoPatternCrawler(BaseCrawler):
            PLATFORM_NAME = "nopattern"
            PLATFORM_DISPLAY_NAME = "No Pattern"
            URL_PATTERNS = []

        assert not NoPatternCrawler.can_handle("https://anything.com")

    def test_multiple_patterns(self):
        """测试多个模式匹配"""
        class MultiPatternCrawler(BaseCrawler):
            PLATFORM_NAME = "multi"
            PLATFORM_DISPLAY_NAME = "Multi"
            URL_PATTERNS = [r"test1\.com", r"test2\.com"]

        assert MultiPatternCrawler.can_handle("https://test1.com/123")
        assert MultiPatternCrawler.can_handle("https://test2.com/123")
        assert not MultiPatternCrawler.can_handle("https://test3.com/123")


class TestBaseCrawlerSanitizeFilename:
    """BaseCrawler.sanitize_filename() 测试"""

    def test_clean_filename(self):
        """测试清理正常文件名"""
        crawler = TestCrawlerImpl()
        result = crawler.sanitize_filename("normal-filename_123")
        assert result == "normal-filename_123"

    def test_remove_special_chars(self):
        """测试移除特殊字符"""
        crawler = TestCrawlerImpl()
        result = crawler.sanitize_filename('aaa/bb*c?d:e"f<g>h|i')
        assert "\\" not in result
        assert "*" not in result
        assert "?" not in result
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result

    def test_max_length_truncation(self):
        """测试最大长度截断"""
        crawler = TestCrawlerImpl()
        long_name = "a" * 100
        result = crawler.sanitize_filename(long_name, max_length=50)
        assert len(result) <= 50

    def test_max_length_default(self):
        """测试默认最大长度"""
        crawler = TestCrawlerImpl()
        long_name = "a" * 100
        result = crawler.sanitize_filename(long_name)
        assert len(result) <= 80  # 默认 max_length=80

    def test_replacement_char(self):
        """测试特殊字符替换"""
        crawler = TestCrawlerImpl()
        result = crawler.sanitize_filename('file"name')
        # 引号应该被替换为空字符串
        assert '"' not in result


class TestBaseCrawlerMangaInfo:
    """MangaInfo 数据类测试"""

    def test_to_dict(self):
        """测试 MangaInfo to_dict"""
        info = MangaInfo(
            title="Test Comic",
            chapter="Chapter 1",
            page_count=20,
            platform="test",
            comic_id="123",
            episode_id="456",
        )
        result = info.to_dict()

        assert result["title"] == "Test Comic"
        assert result["page_count"] == 20
        assert result["extra"] == {}

    def test_extra_field(self):
        """测试 extra 字段"""
        info = MangaInfo(extra={"key": "value"})
        result = info.to_dict()
        assert result["extra"] == {"key": "value"}

    def test_to_dict_complete(self):
        """测试完整的 to_dict"""
        info = MangaInfo(
            title="Complete Comic",
            chapter="Complete Chapter",
            page_count=50,
            platform="manhuagui",
            comic_id="12345",
            episode_id="67890",
            extra={"extra_key": "extra_value"},
        )
        result = info.to_dict()

        assert result["title"] == "Complete Comic"
        assert result["chapter"] == "Complete Chapter"
        assert result["page_count"] == 50
        assert result["platform"] == "manhuagui"
        assert result["comic_id"] == "12345"
        assert result["episode_id"] == "67890"
        assert result["extra"] == {"extra_key": "extra_value"}


class TestBaseCrawlerDownloadProgress:
    """DownloadProgress 数据类测试"""

    def test_to_dict(self):
        """测试 DownloadProgress to_dict"""
        progress = DownloadProgress(
            current=5,
            total=10,
            message="Downloading...",
            status="downloading",
        )
        result = progress.to_dict()

        assert result["current"] == 5
        assert result["total"] == 10
        assert result["message"] == "Downloading..."
        assert result["status"] == "downloading"

    def test_to_dict_status_completed(self):
        """测试完成状态的 to_dict"""
        progress = DownloadProgress(
            current=100,
            total=100,
            message="Completed",
            status="completed",
        )
        result = progress.to_dict()
        assert result["status"] == "completed"

    def test_to_dict_status_failed(self):
        """测试失败状态的 to_dict"""
        progress = DownloadProgress(
            current=50,
            total=100,
            message="Failed",
            status="failed",
        )
        result = progress.to_dict()
        assert result["status"] == "failed"

    def test_to_dict_status_pending(self):
        """测试待处理状态的 to_dict"""
        progress = DownloadProgress(
            current=0,
            total=100,
            message="Pending",
            status="pending",
        )
        result = progress.to_dict()
        assert result["status"] == "pending"


class TestBaseCrawlerInit:
    """BaseCrawler 初始化测试"""

    def test_initial_state(self):
        """测试初始状态"""
        crawler = TestCrawlerImpl()
        assert crawler.browser is None
        assert crawler.context is None
        assert crawler.page is None
        assert crawler.playwright is None
        assert crawler.http_client is None
        assert crawler.cfg is None

    def test_platform_attributes(self):
        """测试平台属性必须定义"""
        class ValidCrawler(BaseCrawler):
            PLATFORM_NAME = "valid"
            PLATFORM_DISPLAY_NAME = "Valid"
            URL_PATTERNS = [r"valid\.com"]

        assert ValidCrawler.PLATFORM_NAME == "valid"
        assert ValidCrawler.PLATFORM_DISPLAY_NAME == "Valid"
        assert ValidCrawler.URL_PATTERNS == [r"valid\.com"]


class TestBaseCrawlerAbstractMethods:
    """BaseCrawler 抽象方法测试"""

    def test_get_info_must_be_implemented(self):
        """测试 get_info 必须被实现"""
        # 验证 BaseCrawler.get_info 是抽象方法
        import inspect
        assert inspect.isabstract(BaseCrawler)

    def test_download_must_be_implemented(self):
        """测试 download 必须被实现"""
        # 验证 BaseCrawler 是抽象类
        import abc
        assert abc.ABC in BaseCrawler.__mro__

    def test_crawler_impl_can_be_instantiated(self):
        """测试实现类可以被实例化"""
        crawler = TestCrawlerImpl()
        assert crawler is not None
        assert crawler.PLATFORM_NAME == "test"


class TestDefaultConstants:
    """默认常量测试"""

    def test_default_user_agent(self):
        """测试默认 User-Agent"""
        assert DEFAULT_USER_AGENT != ""
        assert "Mozilla" in DEFAULT_USER_AGENT

    def test_default_image_headers(self):
        """测试默认图片请求头"""
        assert isinstance(DEFAULT_IMAGE_HEADERS, dict)
        assert "User-Agent" in DEFAULT_IMAGE_HEADERS
        assert "Accept" in DEFAULT_IMAGE_HEADERS
        assert "Accept-Language" in DEFAULT_IMAGE_HEADERS
        assert "Accept-Encoding" in DEFAULT_IMAGE_HEADERS
