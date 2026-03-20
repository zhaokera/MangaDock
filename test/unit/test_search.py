"""测试搜索功能"""

import pytest
from crawlers.search import (
    SearchResult,
    BaseSearcher,
    TencentSearcher,
    IqiyiSearcher,
    YoukuSearcher,
    MgtvSearcher,
    search_all_platforms,
    get_searcher,
)


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
