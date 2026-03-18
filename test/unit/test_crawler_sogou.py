"""搜狗漫画爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.sogou import SogouCrawler


class TestSogouCrawler:
    """搜狗漫画爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://sogou.dmzj.com/comic/123/456.shtml"
        assert SogouCrawler.can_handle(url)

    def test_can_handle_with_www(self):
        """测试 www 域名"""
        url = "https://www.sogou.dmzj.com/comic/123/456.shtml"
        assert SogouCrawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not SogouCrawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert SogouCrawler.PLATFORM_NAME == "sogou"
        assert SogouCrawler.PLATFORM_DISPLAY_NAME == "搜狗漫画"


class TestSogouURLParsing:
    """搜狗漫画 URL 解析测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = SogouCrawler()
        url = "https://sogou.dmzj.com/comic/123/456.shtml"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 123
        assert episode_id == 456

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = SogouCrawler()

        test_cases = [
            ("https://sogou.dmzj.com/comic/123/456.shtml", 123, 456),
            ("https://www.sogou.dmzj.com/comic/1234/5678.shtml", 1234, 5678),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"


class TestSogouURLPatterns:
    """搜狗漫画 URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(SogouCrawler.URL_PATTERNS) > 0

    def test_pattern_matches_sogou(self):
        """测试模式匹配搜狗漫画"""
        assert any("dmzj" in pattern for pattern in SogouCrawler.URL_PATTERNS)


class TestSogouGetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = SogouCrawler()
        assert hasattr(crawler, 'get_info')


class TestSogouDownload:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = SogouCrawler()
        assert hasattr(crawler, 'download')
