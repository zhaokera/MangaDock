import pytest

from crawlers.manga_search import (
    MangaChapterResult,
    MangaChapterCatalog,
    ManhuaguiMangaSearcher,
    MangaSearchResult,
    get_manga_searcher,
)
from crawlers.manhuagui import (
    manhuagui_chapter_sort_key,
    normalize_manhuagui_comic_url,
)


def test_get_manga_searcher_returns_manhuagui_searcher():
    searcher = get_manga_searcher("manhuagui")
    assert searcher is not None
    assert searcher.PLATFORM_NAME == "manhuagui"


def test_manga_result_to_dict_keeps_required_fields():
    result = MangaSearchResult(
        title="海贼王",
        url="https://www.manhuagui.com/comic/1/",
        platform="manhuagui",
        platform_display="漫画柜",
    )
    assert result.to_dict()["title"] == "海贼王"


def test_chapter_result_to_dict_keeps_url_and_title():
    chapter = MangaChapterResult(
        title="第1话",
        url="https://www.manhuagui.com/comic/1/100.html",
    )
    assert chapter.to_dict() == {
        "title": "第1话",
        "url": "https://www.manhuagui.com/comic/1/100.html",
    }


def test_chapter_catalog_to_dict_serializes_chapters():
    catalog = MangaChapterCatalog(
        title="海贼王",
        platform="manhuagui",
        platform_display="漫画柜",
        url="https://www.manhuagui.com/comic/1/",
        chapters=[
            MangaChapterResult(
                title="第1话",
                url="https://www.manhuagui.com/comic/1/100.html",
            )
        ],
    )

    payload = catalog.to_dict()

    assert payload["title"] == "海贼王"
    assert payload["chapters"] == [
        {
            "title": "第1话",
            "url": "https://www.manhuagui.com/comic/1/100.html",
        }
    ]


def test_manhuagui_searcher_builds_series_results_from_candidates():
    searcher = ManhuaguiMangaSearcher()
    candidates = [
        {"title": "海贼王", "url": "https://www.manhuagui.com/comic/1/"},
        {"title": "海贼王", "url": "https://www.manhuagui.com/comic/1/"},
        {"title": "其他作品", "url": "https://www.manhuagui.com/comic/2/"},
    ]

    results = searcher._build_results_from_candidates("海贼王", candidates, limit=10)

    assert [item.title for item in results] == ["海贼王"]
    assert results[0].platform == "manhuagui"


@pytest.mark.asyncio
async def test_manhuagui_searcher_returns_sorted_chapter_catalog():
    searcher = ManhuaguiMangaSearcher()
    html = """
    <ul class="chapter-list">
      <li><a href="/comic/1/101.html" title="第2话">第2话</a></li>
      <li><a href="/comic/1/100.html" title="第1话">第1话</a></li>
    </ul>
    """

    chapters = searcher._extract_chapters_from_html(html)

    assert [chapter.title for chapter in chapters] == ["第1话", "第2话"]
    assert chapters[0].url == "https://www.manhuagui.com/comic/1/100.html"


def test_manhuagui_normalizes_series_and_chapter_urls():
    assert normalize_manhuagui_comic_url("https://www.manhuagui.com/comic/1/100.html") == (
        "https://www.manhuagui.com/comic/1/"
    )
    assert normalize_manhuagui_comic_url("/comic/1/") == "https://www.manhuagui.com/comic/1/"


def test_manhuagui_searcher_ignores_non_chapter_comic_links_in_detail_html():
    searcher = ManhuaguiMangaSearcher()
    html = """
    <div class="chapter-list">
      <a href="/comic/1/">作品主页</a>
      <a href="/comic/1/related.html">相关作品</a>
      <a href="/comic/1/100.html" title="第1话">第1话</a>
      <a href="/comic/1/101.html" title="第2话">第2话</a>
      <a href="/comic/2/">其他作品</a>
    </div>
    """

    chapters = searcher._extract_chapters_from_html(html)

    assert [chapter.title for chapter in chapters] == ["第1话", "第2话"]
    assert [chapter.url for chapter in chapters] == [
        "https://www.manhuagui.com/comic/1/100.html",
        "https://www.manhuagui.com/comic/1/101.html",
    ]


def test_manhuagui_chapter_sort_key_prefers_numeric_chapters_before_special_chapters():
    numeric_key = manhuagui_chapter_sort_key("第12话", "https://www.manhuagui.com/comic/1/12.html")
    special_key = manhuagui_chapter_sort_key("番外篇", "https://www.manhuagui.com/comic/1/200.html")

    assert numeric_key < special_key


def test_manhuagui_searcher_sorts_special_chapters_after_numeric_chapters():
    searcher = ManhuaguiMangaSearcher()
    html = """
    <ul class="chapter-list">
      <li><a href="/comic/1/200.html" title="番外篇">番外篇</a></li>
      <li><a href="/comic/1/100.html" title="第1话">第1话</a></li>
    </ul>
    """

    chapters = searcher._extract_chapters_from_html(html)

    assert [chapter.title for chapter in chapters] == ["第1话", "番外篇"]
