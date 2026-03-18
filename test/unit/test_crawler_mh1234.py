"""纱雾漫画爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.mh1234 import Mh1234Crawler


class TestMh1234Crawler:
    """纱雾漫画爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://www.mh1234.com/comic/123/456.html"
        assert Mh1234Crawler.can_handle(url)

    def test_can_handle_with_www(self):
        """测试 www 域名"""
        url = "https://www.mh1234.com/comic/123/456.html"
        assert Mh1234Crawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not Mh1234Crawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert Mh1234Crawler.PLATFORM_NAME == "mh1234"
        assert Mh1234Crawler.PLATFORM_DISPLAY_NAME == "纱雾漫画"


class TestMh1234URLParsing:
    """纱雾漫画 URL 解析测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = Mh1234Crawler()
        url = "https://www.mh1234.com/comic/123/456.html"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 123
        assert episode_id == 456

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = Mh1234Crawler()

        test_cases = [
            ("https://www.mh1234.com/comic/123/456.html", 123, 456),
            ("https://mh1234.com/comic/1234/5678.html", 1234, 5678),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"


class TestMh1234URLPatterns:
    """纱雾漫画 URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(Mh1234Crawler.URL_PATTERNS) > 0

    def test_pattern_matches_mh1234(self):
        """测试模式匹配纱雾漫画"""
        assert any("mh1234" in pattern for pattern in Mh1234Crawler.URL_PATTERNS)


class TestMh1234GetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = Mh1234Crawler()
        assert hasattr(crawler, 'get_info')


class TestMh1234Download:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = Mh1234Crawler()
        assert hasattr(crawler, 'download')
