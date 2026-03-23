from types import SimpleNamespace

from services.runtime import format_cli_search_results


def test_format_cli_search_results_renders_expected_lines():
    results = [
        SimpleNamespace(
            title="灌篮高手",
            platform_display="腾讯视频",
            score=99.0,
            url="https://v.qq.com/demo",
        )
    ]

    rendered = format_cli_search_results(results)

    assert "找到 1 个结果" in rendered
    assert "1. 灌篮高手" in rendered
    assert "平台: 腾讯视频" in rendered
    assert "匹配度: 99.0" in rendered
    assert "URL: https://v.qq.com/demo" in rendered
