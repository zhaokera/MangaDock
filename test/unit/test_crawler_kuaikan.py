"""快看漫画爬虫单元测试"""

import pytest
from unittest.mock import MagicMock, patch

from crawlers.kuaikanmanhua import KuaikanmanhuaCrawler


class TestKuaikanCrawler:
    """快看漫画爬虫测试"""

    def test_can_handle(self):
        """测试 URL 匹配"""
        url = "https://www.kuaikanmanhua.com/comic/12345/67890"
        assert KuaikanmanhuaCrawler.can_handle(url)

    def test_can_handle_with_kuaikanmanhua_com(self):
        """测试.kuaikanmanhua.com 域名"""
        url = "https://www.kuaikanmanhua.com/comic/12345/67890"
        assert KuaikanmanhuaCrawler.can_handle(url)

    def test_can_handle_with_kkmh_com(self):
        """测试.kkmh.com 域名"""
        url = "https://www.kkmh.com/comic/12345/67890"
        assert KuaikanmanhuaCrawler.can_handle(url)

    def test_cannot_handle(self):
        """测试不匹配 URL"""
        url = "https://example.com/comic/123"
        assert not KuaikanmanhuaCrawler.can_handle(url)

    def test_platform_name(self):
        """测试平台名称"""
        assert KuaikanmanhuaCrawler.PLATFORM_NAME == "kuaikanmanhua"
        assert KuaikanmanhuaCrawler.PLATFORM_DISPLAY_NAME == "快看漫画"


class TestKuaikanURLParsing:
    """URL 解析测试"""

    def test_extract_ids(self):
        """测试 ID 提取"""
        crawler = KuaikanmanhuaCrawler()
        url = "https://www.kuaikanmanhua.com/comic/12345/67890"

        comic_id, episode_id = crawler._extract_ids(url)

        assert comic_id == 12345
        assert episode_id == 67890

    def test_extract_ids_various_urls(self):
        """测试多种 URL 格式"""
        crawler = KuaikanmanhuaCrawler()

        test_cases = [
            ("https://www.kuaikanmanhua.com/comic/12345/67890", 12345, 67890),
            ("https://www.kuaikanmanhua.com/comic/123/456.html", 123, 456),
        ]

        for url, expected_comic, expected_episode in test_cases:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id == expected_comic, f"URL: {url}"
            assert episode_id == expected_episode, f"URL: {url}"

    def test_extract_ids_returns_none_on_invalid(self):
        """测试无效 URL 返回 None"""
        crawler = KuaikanmanhuaCrawler()

        invalid_urls = [
            "https://www.kuaikanmanhua.com/comic/abc/def",
            "https://example.com/comic/123",
            "",
            "https://www.kuaikanmanhua.com/",
        ]

        for url in invalid_urls:
            comic_id, episode_id = crawler._extract_ids(url)
            assert comic_id is None, f"Expected None for URL: {url}"
            assert episode_id is None, f"Expected None for URL: {url}"


class TestKuaikanCrawlerInit:
    """快看漫画爬虫初始化测试"""

    def test_initial_state(self):
        """测试初始状态"""
        crawler = KuaikanmanhuaCrawler()
        assert crawler.browser is None
        assert crawler.context is None
        assert crawler.page is None
        assert crawler.playwright is None
        assert crawler.http_client is None
        assert crawler.cfg is None


class TestKuaikanURLPatterns:
    """URL 模式测试"""

    def test_url_patterns_defined(self):
        """测试 URL 模式已定义"""
        assert len(KuaikanmanhuaCrawler.URL_PATTERNS) > 0

    def test_pattern_matches_kuaikanmanhua(self):
        """测试模式匹配快看漫画"""
        assert any("kuaikanmanhua" in pattern for pattern in KuaikanmanhuaCrawler.URL_PATTERNS)

    def test_pattern_matches_kkmh(self):
        """测试模式匹配 kkmh"""
        assert any("kkmh" in pattern for pattern in KuaikanmanhuaCrawler.URL_PATTERNS)


class TestKuaikanGetInfo:
    """get_info 方法测试"""

    def test_get_info_exists(self):
        """测试 get_info 方法存在"""
        crawler = KuaikanmanhuaCrawler()
        assert hasattr(crawler, 'get_info')


class TestKuaikanDownload:
    """download 方法测试"""

    def test_download_exists(self):
        """测试 download 方法存在"""
        crawler = KuaikanmanhuaCrawler()
        assert hasattr(crawler, 'download')


class TestKuaikanImageServers:
    """图片服务器测试"""

    def test_image_servers_defined(self):
        """测试图片服务器已定义"""
        crawler = KuaikanmanhuaCrawler()
        assert hasattr(crawler, 'IMAGE_SERVERS')
        assert len(crawler.IMAGE_SERVERS) > 0

    def test_image_servers_are_valid_urls(self):
        """测试图片服务器是有效的 URL"""
        crawler = KuaikanmanhuaCrawler()
        for server in crawler.IMAGE_SERVERS:
            assert server.startswith("https://")
            assert "kuaikanmanhua.com" in server
