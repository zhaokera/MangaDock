"""爱奇艺爬虫回归测试"""

from crawlers.iqiyi import IqiyiCrawler


class TestIqiyiVideoUrlExtraction:
    """Test extracting playable video URLs from page content."""

    def test_extract_video_urls_strips_trailing_javascript(self):
        crawler = IqiyiCrawler()
        page_content = '''
            "video":"https://static-d.iqiyi.com/lequ/20250926/e030ccddd25146628f9bf832cac18db2.mp4":i(96215),className:s.alertVideo
        '''

        assert crawler._extract_video_urls_from_content(page_content) == [
            "https://static-d.iqiyi.com/lequ/20250926/e030ccddd25146628f9bf832cac18db2.mp4"
        ]
