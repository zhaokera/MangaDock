from crawlers.registry import get_supported_platforms


def test_supported_platforms_include_declared_content_type():
    platforms = {item["name"]: item for item in get_supported_platforms()}

    assert platforms["tencent"]["type"] == "video"
    assert platforms["bilibili"]["type"] == "manga"
