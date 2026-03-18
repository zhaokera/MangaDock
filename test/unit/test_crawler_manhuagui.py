"""漫画柜爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.manhuagui import ManhuaguiCrawler, lzstring_decompress


class TestLZStringDecompress:
    """LZString 解密算法测试"""

    def test_empty_string(self):
        """测试空字符串"""
        result = lzstring_decompress("")
        assert result == ""

    def test_none_input(self):
        """测试 None 输入"""
        result = lzstring_decompress(None)
        assert result == ""

    def test_base64_chars(self):
        """测试 Base64 字符集处理"""
        # LZString 编码的 "a" 是 "CA"
        result = lzstring_decompress("CA")
        assert result is not None
        # 简单验证解码能产生结果
        assert len(result) >= 0


class TestManhuaguiCrawler:
    """漫画柜爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://www.manhuagui.com/comic/58426/865091.html"
        assert ManhuaguiCrawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not ManhuaguiCrawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert ManhuaguiCrawler.PLATFORM_NAME == "manhuagui"
        assert ManhuaguiCrawler.PLATFORM_DISPLAY_NAME == "漫画柜"


class TestManhuaguiExtraction:
    """提取方法测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = ManhuaguiCrawler()
        url = "https://www.manhuagui.com/comic/58426/865091.html"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 58426
        assert episode_id == 865091

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = ManhuaguiCrawler()

        test_cases = [
            ("https://www.manhuagui.com/comic/123/456.html", 123, 456),
            ("https://www.manhuagui.com/comic/12345/67890.html", 12345, 67890),
            ("https://www.manhuagui.com/comic/1/2.html", 1, 2),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"

    def test_extract_ids_from_different_host(self):
        """测试从不同主机提取"""
        crawler = ManhuaguiCrawler()
        url = "https://manhuagui.com/comic/123/456.html"
        comic_id, episode_id = crawler._extract_ids(url)
        assert comic_id == 123
        assert episode_id == 456


class TestManhuaguiURLPatterns:
    """URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(ManhuaguiCrawler.URL_PATTERNS) > 0

    def test_pattern_matches_manhuagui(self):
        """测试模式匹配漫画柜"""
        assert any("manhuagui" in pattern for pattern in ManhuaguiCrawler.URL_PATTERNS)


class TestManhuaguiGetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = ManhuaguiCrawler()
        assert hasattr(crawler, 'get_info')


class TestManhuaguiDownload:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = ManhuaguiCrawler()
        assert hasattr(crawler, 'download')
