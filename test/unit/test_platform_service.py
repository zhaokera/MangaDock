from types import SimpleNamespace
from unittest.mock import patch

from services.platforms import list_auth_platforms, list_supported_platforms


def test_list_supported_platforms_delegates_to_registry():
    with patch("services.platforms.get_supported_platforms", return_value=[{"name": "tencent"}]) as get_supported:
        result = list_supported_platforms()

    assert result == [{"name": "tencent"}]
    get_supported.assert_called_once_with()


def test_list_auth_platforms_returns_only_platforms_with_callable_login():
    platforms = [
        {"name": "manhuagui", "display_name": "漫画柜"},
        {"name": "tencent", "display_name": "腾讯视频"},
        {"name": "ghost", "display_name": "幽灵站"},
    ]

    with patch("services.platforms.get_supported_platforms", return_value=platforms), patch(
        "services.platforms.get_crawler_by_platform",
        side_effect=[
            SimpleNamespace(login=lambda credentials: credentials),
            SimpleNamespace(),
            None,
        ],
    ):
        result = list_auth_platforms()

    assert result == [{"name": "manhuagui", "display_name": "漫画柜"}]
