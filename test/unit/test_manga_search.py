from crawlers.manga_search import (
    MangaChapterResult,
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
