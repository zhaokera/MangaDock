"""番茄漫画爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.tongjuemh import TongjuemhCrawler


class TestTongjuemhCrawler:
    """番茄漫画爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://www.tongjuemh.com/comic/123/456.html"
        assert TongjuemhCrawler.can_handle(url)

    def test_can_handle_with_www(self):
        """测试 www 域名"""
        url = "https://www.tongjuemh.com/comic/123/456.html"
        assert TongjuemhCrawler.can_handle(url)

    def test_can_handle_without_www(self):
        """测试非 www 域名"""
        url = "https://tongjuemh.com/comic/123/456.html"
        assert TongjuemhCrawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not TongjuemhCrawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert TongjuemhCrawler.PLATFORM_NAME == "tongjuemh"
        assert TongjuemhCrawler.PLATFORM_DISPLAY_NAME == "番茄漫画"


class TestTongjuemhURLParsing:
    """番茄漫画 URL 解析测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = TongjuemhCrawler()
        url = "https://www.tongjuemh.com/comic/123/456.html"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 123
        assert episode_id == 456

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = TongjuemhCrawler()

        test_cases = [
            ("https://www.tongjuemh.com/comic/123/456.html", 123, 456),
            ("https://tongjuemh.com/comic/1234/5678.html", 1234, 5678),
            ("https://www.tongjuemh.com/comic/999/100.html", 999, 100),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"

    def test_extract_ids_non_numeric_episode(self):
        """测试非数字 episode_id"""
        crawler = TongjuemhCrawler()
        url = "https://www.tongjuemh.com/comic/123/chapter-1.html"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 123
        assert episode_id == "chapter-1"


class TestTongjuemhURLPatterns:
    """番茄漫画 URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(TongjuemhCrawler.URL_PATTERNS) > 0

    def test_pattern_matches_tongjuemh(self):
        """测试模式匹配番茄漫画"""
        assert any("tongjuemh" in pattern for pattern in TongjuemhCrawler.URL_PATTERNS)


class TestTongjuemhGetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = TongjuemhCrawler()
        assert hasattr(crawler, 'get_info')


class TestTongjuemhDownload:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = TongjuemhCrawler()
        assert hasattr(crawler, 'download')
