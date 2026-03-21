"""测试搜索功能"""

from unittest.mock import patch

import pytest
from crawlers.search import (
    SearchResult,
    BaseSearcher,
    TencentSearcher,
    IqiyiSearcher,
    YoukuSearcher,
    MgtvSearcher,
    DlExpoSearcher,
    search_all_platforms,
    get_searcher,
)
from crawlers.tencent import TencentCrawler
from crawlers.iqiyi import IqiyiCrawler


class TestSearchResult:
    """Test SearchResult dataclass"""

    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = SearchResult(
            title="测试视频",
            url="https://example.com/video",
            platform="test",
            platform_display="测试平台",
            score=85.5
        )
        data = result.to_dict()
        assert data["title"] == "测试视频"
        assert data["url"] == "https://example.com/video"
        assert data["platform"] == "test"
        assert data["platform_display"] == "测试平台"
        assert data["score"] == 85.5
        assert "extra" in data

    def test_default_score(self):
        """Test default score is 0.0"""
        result = SearchResult(
            title="测试",
            url="https://example.com",
            platform="test",
            platform_display="测试"
        )
        assert result.score == 0.0

    def test_extra_field(self):
        """Test extra field defaults to empty dict"""
        result = SearchResult(
            title="测试",
            url="https://example.com",
            platform="test",
            platform_display="测试"
        )
        assert result.extra == {}


class TestGetSearcher:
    """Test get_searcher function"""

    def test_get_tencent_searcher(self):
        """Test getting Tencent searcher"""
        searcher = get_searcher("tencent")
        assert isinstance(searcher, TencentSearcher)

    def test_get_iqiyi_searcher(self):
        """Test getting爱奇艺 searcher"""
        searcher = get_searcher("iqiyi")
        assert isinstance(searcher, IqiyiSearcher)

    def test_get_youku_searcher(self):
        """Test getting Youku searcher"""
        searcher = get_searcher("youku")
        assert isinstance(searcher, YoukuSearcher)

    def test_get_mango_searcher(self):
        """Test getting Mango searcher"""
        searcher = get_searcher("mango")
        assert isinstance(searcher, MgtvSearcher)

    def test_get_searcher_returns_dl_expo_searcher(self):
        searcher = get_searcher("dl_expo")
        assert isinstance(searcher, DlExpoSearcher)

    def test_get_invalid_searcher(self):
        """Test getting invalid platform returns None"""
        searcher = get_searcher("invalid_platform")
        assert searcher is None


class TestSearcherInstantiation:
    """Test searcher platform attributes"""

    def test_tencent_attributes(self):
        """Test TencentSearcher attributes"""
        searcher = TencentSearcher()
        assert searcher.PLATFORM_NAME == "tencent"
        assert searcher.PLATFORM_DISPLAY == "腾讯视频"

    def test_iqiyi_attributes(self):
        """Test IqiyiSearcher attributes"""
        searcher = IqiyiSearcher()
        assert searcher.PLATFORM_NAME == "iqiyi"
        assert searcher.PLATFORM_DISPLAY == "爱奇艺"

    def test_youku_attributes(self):
        """Test YoukuSearcher attributes"""
        searcher = YoukuSearcher()
        assert searcher.PLATFORM_NAME == "youku"
        assert searcher.PLATFORM_DISPLAY == "优酷"

    def test_mango_attributes(self):
        """Test MgtvSearcher attributes"""
        searcher = MgtvSearcher()
        assert searcher.PLATFORM_NAME == "mango"
        assert searcher.PLATFORM_DISPLAY == "芒果TV"


class TestScoreCalculation:
    """Test scoring algorithm"""

    @pytest.fixture
    def tencent_searcher(self):
        return TencentSearcher()

    def test_perfect_match(self, tencent_searcher):
        """Test perfect match scoring"""
        score = tencent_searcher._calculate_score("灌篮高手", "灌篮高手")
        # 完全匹配: 50 (包含) + 30 (开头) + 5 (长度适中) = 85
        assert score == 85.0

    def test_contains_match(self, tencent_searcher):
        """Test when keyword is contained in title"""
        score = tencent_searcher._calculate_score("灌篮高手", "灌篮高手 第一季")
        assert score >= 50.0  # 至少有 50 分包含匹配

    def test_prefix_match(self, tencent_searcher):
        """Test when title starts with keyword"""
        score = tencent_searcher._calculate_score("海贼王", "海贼王 珍珠岛")
        assert score >= 80.0  # 开头匹配 30 + 包含 50

    def test_no_match(self, tencent_searcher):
        """Test when keyword not in title"""
        score = tencent_searcher._calculate_score("火影忍者", "进击的巨人")
        # 长度偏好：两个字符串长度都在 5-50 之间，各加 10 分
        assert score == 10.0  # 长度适中各加 10 分

    def test_empty_keyword(self, tencent_searcher):
        """Test with empty keyword"""
        score = tencent_searcher._calculate_score("", "灌篮高手")
        assert score == 0.0

    def test_empty_title(self, tencent_searcher):
        """Test with empty title"""
        score = tencent_searcher._calculate_score("灌篮高手", "")
        assert score == 0.0

    def test_multiple_occurrences(self, tencent_searcher):
        """Test when keyword appears multiple times"""
        score = tencent_searcher._calculate_score("高", "灌篮高手 高三 高校大赛")
        # 50 (包含) + 5 * 3 (出现3次) = 65
        assert score >= 60.0


class TestSearchResultSorting:
    """Test search result sorting behavior"""

    def test_search_result_has_required_fields(self):
        """Test that SearchResult has all required fields"""
        result = SearchResult(
            title="Test",
            url="https://example.com",
            platform="test",
            platform_display="Test",
            score=90.0
        )
        assert hasattr(result, 'title')
        assert hasattr(result, 'url')
        assert hasattr(result, 'platform')
        assert hasattr(result, 'platform_display')
        assert hasattr(result, 'score')
        assert hasattr(result, 'extra')


class TestCandidateNormalization:
    """Test candidate normalization for live search pages"""

    def test_dl_expo_searcher_builds_results_from_maccms_candidates(self):
        searcher = DlExpoSearcher()
        candidates = [
            {"title": "灌篮高手", "url": "/voddetail/101100.html"},
            {"title": "灌篮高手", "url": "/play/101100/2-1.html"},
        ]

        results = searcher._build_results_from_candidates("灌篮高手", candidates, limit=10)

        assert [result.platform for result in results] == ["dl_expo", "dl_expo"]
        assert [result.url for result in results] == [
            "https://www.dl-expo.com/voddetail/101100.html",
            "https://www.dl-expo.com/play/101100/2-1.html",
        ]

    def test_dl_expo_searcher_keeps_absolute_urls_unchanged(self):
        searcher = DlExpoSearcher()

        results = searcher._build_results_from_candidates(
            "灌篮高手",
            [
                {
                    "title": "灌篮高手",
                    "url": "https://www.dl-expo.com/voddetail/101100.html",
                },
            ],
            limit=10,
        )

        assert [result.url for result in results] == [
            "https://www.dl-expo.com/voddetail/101100.html",
        ]

    @pytest.mark.asyncio
    async def test_dl_expo_searcher_uses_anchor_fallback_when_card_candidates_are_empty(self):
        class FakePage:
            async def goto(self, *args, **kwargs):
                return None

            async def evaluate(self, script):
                if "items.some((item) => item.title && item.url)" in script:
                    return [{"title": "灌篮高手", "url": "/voddetail/101100.html"}]
                return [{"title": "", "url": ""}]

        class FakeBrowser:
            def __init__(self, page):
                self.page = page

            async def new_page(self):
                return self.page

            async def close(self):
                return None

        class FakePlaywright:
            def __init__(self, page):
                self.chromium = self
                self.page = page

            async def launch(self, headless=True):
                return FakeBrowser(self.page)

        class FakeAsyncPlaywrightContext:
            def __init__(self, page):
                self.page = page

            async def __aenter__(self):
                return FakePlaywright(self.page)

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "playwright.async_api.async_playwright",
            return_value=FakeAsyncPlaywrightContext(FakePage()),
        ):
            results = await DlExpoSearcher().search("灌篮高手", limit=10)

        assert [result.url for result in results] == [
            "https://www.dl-expo.com/voddetail/101100.html",
        ]

    def test_tencent_candidates_can_build_cover_urls_from_cid(self):
        """Tencent search pages now expose cid cards instead of direct hrefs"""
        searcher = TencentSearcher()

        results = searcher._build_results_from_candidates(
            "海贼王",
            [
                {"title": "客服", "url": "", "cid": None},
                {"title": "海贼王", "url": "", "cid": "mzc00200emmamia"},
                {"title": "海贼王剧场版", "url": "", "cid": "mzc002006wc0rx0"},
            ],
            limit=10,
        )

        assert {result.title for result in results} == {"海贼王", "海贼王剧场版"}
        assert {result.url for result in results} == {
            "https://v.qq.com/x/cover/mzc00200emmamia.html",
            "https://v.qq.com/x/cover/mzc002006wc0rx0.html",
        }

    def test_iqiyi_candidates_keep_redirect_urls_when_keyword_matches(self):
        """Iqiyi search pages now expose tvg redirect links instead of old result selectors"""
        searcher = IqiyiSearcher()

        results = searcher._build_results_from_candidates(
            "灌篮高手",
            [
                {"title": "客服中心", "url": "https://www.iqiyi.com/help", "cid": None},
                {
                    "title": "灌篮高手 普通话",
                    "url": "https://www.iqiyi.com/tvg/to_page_url?album_id=MjAyOTE4MTAx",
                    "cid": None,
                },
            ],
            limit=10,
        )

        assert len(results) == 1
        assert results[0].title == "灌篮高手 普通话"
        assert results[0].url == "https://www.iqiyi.com/tvg/to_page_url?album_id=MjAyOTE4MTAx"

    def test_iqiyi_candidates_skip_shortvideo_redirect_urls(self):
        searcher = IqiyiSearcher()

        results = searcher._build_results_from_candidates(
            "海贼王",
            [
                {
                    "title": "海贼王 5秒高燃混剪",
                    "url": (
                        "https://www.iqiyi.com/tvg/to_page_url?"
                        "ext_params=s3%3Dpca_115_shortvideo_card&tv_id=MTk4NTc2MjgwMA%3D%3D"
                    ),
                    "cid": None,
                },
                {
                    "title": "海贼王 普通话",
                    "url": (
                        "https://www.iqiyi.com/tvg/to_page_url?"
                        "album_id=MjAyOTE4MTAx&ext_params=s3%3Dpca_115_number_enlarge"
                    ),
                    "cid": None,
                },
            ],
            limit=10,
        )

        assert len(results) == 1
        assert results[0].title == "海贼王 普通话"
        assert "shortvideo_card" not in results[0].url


class TestSearchResultUrlCompatibility:
    """Test that search result URLs are accepted by download crawlers"""

    def test_tencent_cover_urls_from_search_are_supported_by_crawler(self):
        crawler = TencentCrawler()
        assert crawler.can_handle("https://v.qq.com/x/cover/mzc00200emmamia.html")

    def test_iqiyi_redirect_urls_from_search_are_supported_by_crawler(self):
        crawler = IqiyiCrawler()
        assert crawler.can_handle("https://www.iqiyi.com/tvg/to_page_url?album_id=MjAyOTE4MTAx")
