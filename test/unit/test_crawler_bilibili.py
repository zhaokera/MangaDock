"""哔哩哔哩漫画爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.bilibili import BilibiliCrawler


class TestBilibiliCrawler:
    """哔哩哔哩漫画爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://manga.bilibili.com/m/detail/123"
        assert BilibiliCrawler.can_handle(url)

    def test_can_handle_with_www(self):
        """测试 www 域名"""
        url = "https://www.manga.bilibili.com/m/detail/123"
        assert BilibiliCrawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not BilibiliCrawler.can_handle(url)

    def test_cannot_handle_invalid_url(self):
        """测试无效 URL 格式"""
        url = "https://manga.bilibili.com/detail/123"  # 缺少 /m/
        assert not BilibiliCrawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert BilibiliCrawler.PLATFORM_NAME == "bilibili"
        assert BilibiliCrawler.PLATFORM_DISPLAY_NAME == "哔哩哔哩漫画"

    def test_is_video_url(self):
        """测试 _is_video_url 始终返回 False (B站不支持视频下载)"""
        crawler = BilibiliCrawler()
        assert not crawler._is_video_url("https://www.bilibili.com/video/BV1MM4y1n7W5")


class TestBilibiliURLParsing:
    """哔哩哔哩漫画 URL 解析测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = BilibiliCrawler()
        url = "https://manga.bilibili.com/m/detail/123"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 123
        assert episode_id is None

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = BilibiliCrawler()

        test_cases = [
            ("https://manga.bilibili.com/m/detail/123", 123, None),
            ("https://www.manga.bilibili.com/m/detail/456", 456, None),
            ("https://manga.bilibili.com/m/detail/999", 999, None),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"

    def test_extract_ids_invalid_url(self):
        """测试无效 URL"""
        crawler = BilibiliCrawler()
        url = "https://manga.bilibili.com/m/detail/abc"  # 非数字 ID

        comic_id, episode_id = crawler._extract_ids(url)

        # 应该返回 None, None 或抛出异常
        assert comic_id is None
        assert episode_id is None


class TestBilibiliURLPatterns:
    """哔哩哔哩漫画 URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(BilibiliCrawler.URL_PATTERNS) > 0

    def test_pattern_matches_bilibili(self):
        """测试模式匹配哔哩哔哩"""
        assert any("bilibili" in pattern for pattern in BilibiliCrawler.URL_PATTERNS)


class TestBilibiliGetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = BilibiliCrawler()
        assert hasattr(crawler, 'get_info')


class TestBilibiliDownload:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = BilibiliCrawler()
        assert hasattr(crawler, 'download')
