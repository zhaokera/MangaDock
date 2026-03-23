from types import SimpleNamespace

from services.parse import serialize_parse_result


def test_serialize_parse_result_returns_expected_payload():
    crawler = SimpleNamespace(
        PLATFORM_NAME="tencent",
        PLATFORM_DISPLAY_NAME="腾讯视频",
    )
    info = SimpleNamespace(
        comic_id="cid-1",
        episode_id="ep-2",
    )

    payload = serialize_parse_result(crawler, info, "https://v.qq.com/x/cover/demo.html")

    assert payload == {
        "platform": "tencent",
        "platform_name": "腾讯视频",
        "comic_id": "cid-1",
        "episode_id": "ep-2",
        "url": "https://v.qq.com/x/cover/demo.html",
    }
