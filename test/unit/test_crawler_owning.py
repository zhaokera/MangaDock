"""Owining 漫画爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.owning import OwiningCrawler


class TestOwiningCrawler:
    """Owining 漫画爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://www.owning.com/comic/123/456.html"
        assert OwiningCrawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not OwiningCrawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert OwiningCrawler.PLATFORM_NAME == "owning"
        assert OwiningCrawler.PLATFORM_DISPLAY_NAME == "Owining 漫画"


class TestOwiningURLParsing:
    """Owining 漫画 URL 解析测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = OwiningCrawler()
        url = "https://www.owning.com/comic/123/456.html"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 123
        assert episode_id == 456

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = OwiningCrawler()

        test_cases = [
            ("https://www.owning.com/comic/123/456.html", 123, 456),
            ("https://owning.com/comic/1234/5678.html", 1234, 5678),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"


class TestOwiningURLPatterns:
    """Owining 漫画 URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(OwiningCrawler.URL_PATTERNS) > 0

    def test_pattern_matches_owning(self):
        """测试模式匹配 Owining 漫画"""
        assert any("owning" in pattern for pattern in OwiningCrawler.URL_PATTERNS)


class TestOwiningGetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = OwiningCrawler()
        assert hasattr(crawler, 'get_info')


class TestOwiningDownload:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = OwiningCrawler()
        assert hasattr(crawler, 'download')
