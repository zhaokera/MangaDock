import pytest

from crawlers.manga_search import (
    MangaChapterResult,
    MangaChapterCatalog,
    ManhuaguiMangaSearcher,
    MangaSearchResult,
    get_manga_searcher,
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
