from types import SimpleNamespace

from services.downloader import build_history_item, clear_crawler_runtime


def test_clear_crawler_runtime_resets_browser_related_fields():
    crawler = SimpleNamespace(
        browser=object(),
        context=object(),
        page=object(),
        playwright=object(),
    )

    clear_crawler_runtime(crawler)

    assert crawler.browser is None
    assert crawler.context is None
    assert crawler.page is None
    assert crawler.playwright is None


def test_build_history_item_returns_expected_payload():
    task = SimpleNamespace(
        task_id="task-1",
        manga_info={"title": "海贼王", "chapter": "第1话"},
        platform="manhuagui",
        zip_path="/tmp/onepiece.zip",
        total=12,
        created_at=SimpleNamespace(isoformat=lambda: "2026-03-24T12:00:00"),
    )

    assert build_history_item(task) == {
        "task_id": "task-1",
        "title": "海贼王",
        "chapter": "第1话",
        "platform": "manhuagui",
        "zip_path": "/tmp/onepiece.zip",
        "page_count": 12,
        "created_at": "2026-03-24T12:00:00",
    }


def test_build_history_item_returns_none_when_manga_info_missing():
    task = SimpleNamespace(manga_info=None)

    assert build_history_item(task) is None
