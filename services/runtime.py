"""启动与命令行运行时辅助。"""

from __future__ import annotations

from typing import Any, Callable


def format_cli_search_results(results: list[Any]) -> str:
    """格式化 CLI 搜索结果。"""
    lines = [f"\n找到 {len(results)} 个结果:"]
    for index, item in enumerate(results, 1):
        lines.extend(
            [
                f"\n{index}. {item.title}",
                f"   平台: {item.platform_display}",
                f"   匹配度: {item.score:.1f}",
                f"   URL: {item.url}",
            ]
        )
    return "\n".join(lines)


async def run_search_cli(
    *,
    keyword: str,
    platform: str | None,
    limit: int,
    get_searcher: Callable[[str], Any],
    search_all_platforms: Callable[[str, int], Any],
    print_fn: Callable[[str], None] = print,
) -> int:
    """运行 CLI 搜索模式。"""
    try:
        if platform:
            searcher = get_searcher(platform)
            if searcher is None:
                print_fn(f"错误: 不支持的平台: {platform}")
                print_fn("支持的平台: tencent, iqiyi, youku, mango")
                return 1
            results = await searcher.search(keyword, limit=limit)
        else:
            results = await search_all_platforms(keyword, limit_per_platform=limit)

        if not results:
            print_fn("未找到结果")
            return 0

        print_fn(format_cli_search_results(results))
        return 0
    except Exception as exc:
        print_fn(f"搜索失败: {exc}")
        return 1


async def run_download_cli(
    *,
    url: str,
    downloads_dir: str,
    get_crawler_for_url: Callable[[str], Any],
    print_fn: Callable[[str], None] = print,
) -> int:
    """运行 CLI 下载模式。"""
    try:
        crawler = get_crawler_for_url(url)
        info = await crawler.get_info(url)
        print_fn(f"准备下载: {info.title}")
        output = await crawler.download(url, downloads_dir)
        print_fn(f"下载完成: {output}")
        return 0
    except Exception as exc:
        print_fn(f"下载失败: {exc}")
        return 1


def log_startup_summary(*, logger: Any, config: Any, platforms: list[dict[str, Any]]) -> None:
    """输出服务启动摘要。"""
    logger.info("启动漫画下载服务...")
    logger.info(f"API: http://{config.host}:{config.port}")
    logger.info(f"文档: http://{config.host}:{config.port}/docs")
    logger.info("支持的平台:")
    for platform in platforms:
        logger.info(f"  - {platform['display_name']}")

    logger.info("配置:")
    logger.info(f"  - 下载目录: {config.download.output_dir}")
    logger.info(f"  - 并发数: {config.download.concurrency}")
    logger.info(f"  - 日志级别: {config.logging.level}")

    cleanup_interval = getattr(config.crawler, "browser_cleanup_interval", 60)
    idle_timeout = getattr(config.crawler, "browser_idle_timeout", 300)
    logger.info(f"  - 浏览器池清理间隔: {cleanup_interval}s")
    logger.info(f"  - 浏览器空闲超时: {idle_timeout}s")
