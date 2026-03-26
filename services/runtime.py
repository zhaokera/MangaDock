"""启动与命令行运行时辅助。"""

from __future__ import annotations

import argparse
import asyncio
import config as app_config
import logging
from pathlib import Path

from typing import Any, Callable, Optional, Protocol, TypedDict

from config import Config
from services.state import AppRuntime


GetSearcher = Callable[[str], Any]
SearchAllPlatforms = Callable[[str, int], Any]
GetCrawlerForUrl = Callable[[str], Any]


class SupportsInfo(Protocol):
    def info(self, message: str) -> Any: ...


class RuntimeAliases(TypedDict):
    tasks: dict[str, Any]
    task_last_sse_state: dict[str, dict]
    _state_lock: Any
    _browser_pool: dict[str, dict]
    _browser_pool_lock: Any
    _download_queue: dict[str, Any]
    _download_queue_priority: dict[str, int]
    _download_queue_lock: Any


class ServerEntrypointKwargs(TypedDict):
    argv: Optional[list[str]]
    app: Any
    logger: Any
    config: Config
    downloads_dir: str
    get_searcher: GetSearcher
    search_all_platforms: SearchAllPlatforms
    get_crawler_for_url: GetCrawlerForUrl


def configure_server_logging(logger_name: str) -> logging.Logger:
    """配置服务启动日志并返回模块 logger。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(logger_name)
    logging.getLogger("crawlers").setLevel(logging.INFO)
    logging.getLogger("crawlers.tencent").setLevel(logging.INFO)
    logging.getLogger("crawlers.iqiyi").setLevel(logging.INFO)
    return logger


def build_runtime_aliases(runtime: AppRuntime) -> RuntimeAliases:
    """Build legacy module-level aliases from AppRuntime."""
    return {
        "tasks": runtime.tasks,
        "task_last_sse_state": runtime.task_last_sse_state,
        "_state_lock": runtime.state_lock,
        "_browser_pool": runtime.browser_pool,
        "_browser_pool_lock": runtime.browser_pool_lock,
        "_download_queue": runtime.download_queue,
        "_download_queue_priority": runtime.download_queue_priority,
        "_download_queue_lock": runtime.download_queue_lock,
    }


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


def initialize_server_state(
    *,
    get_config: Callable[[], Config] = app_config.get_config,
    create_runtime_fn: Callable[[], AppRuntime],
) -> tuple[Config, AppRuntime, Path]:
    """初始化服务配置、运行时和下载目录路径。"""
    config = get_config()
    runtime = create_runtime_fn()
    downloads_dir = Path(config.download.output_dir)
    return config, runtime, downloads_dir


def prepare_server_environment(
    *,
    init_db_fn: Callable[[], None],
    downloads_dir: Path,
) -> None:
    """执行数据库初始化和下载目录准备。"""
    init_db_fn()
    downloads_dir.mkdir(exist_ok=True)


def build_cli_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(description="漫画下载器")
    parser.add_argument("--search", "-s", help="搜索视频（按名称）")
    parser.add_argument("--platform", "-p", help="搜索平台（tencent/iqiyi/youku/mango）")
    parser.add_argument("--limit", "-l", type=int, default=10, help="搜索结果数量")
    parser.add_argument("--download", "-d", help="下载视频（通过 URL）")
    return parser


def build_server_entrypoint_kwargs(
    *,
    app: Any,
    logger: Any,
    config: Config,
    downloads_dir: str,
    get_searcher: GetSearcher,
    search_all_platforms: SearchAllPlatforms,
    get_crawler_for_url: GetCrawlerForUrl,
) -> ServerEntrypointKwargs:
    """Build a stable kwargs mapping for run_entrypoint()."""
    return {
        "argv": None,
        "app": app,
        "logger": logger,
        "config": config,
        "downloads_dir": downloads_dir,
        "get_searcher": get_searcher,
        "search_all_platforms": search_all_platforms,
        "get_crawler_for_url": get_crawler_for_url,
    }


def run_entrypoint(
    *,
    argv: Optional[list[str]],
    app: Any,
    logger: Any,
    config: Config,
    downloads_dir: str,
    get_searcher: GetSearcher,
    search_all_platforms: SearchAllPlatforms,
    get_crawler_for_url: GetCrawlerForUrl,
    run_search: Callable[..., Any] = run_search_cli,
    run_download: Callable[..., Any] = run_download_cli,
    run_server_fn: Optional[Callable[..., None]] = None,
    asyncio_run: Callable[[Any], Any] = asyncio.run,
) -> Optional[int]:
    """解析 CLI 参数并分发到搜索、下载或 Web 服务模式。"""
    if run_server_fn is None:
        run_server_fn = run_server
    args = build_cli_parser().parse_args(argv)

    if args.search:
        return asyncio_run(
            run_search(
                keyword=args.search,
                platform=args.platform,
                limit=args.limit,
                get_searcher=get_searcher,
                search_all_platforms=search_all_platforms,
            )
        )

    if args.download:
        return asyncio_run(
            run_download(
                url=args.download,
                downloads_dir=downloads_dir,
                get_crawler_for_url=get_crawler_for_url,
            )
        )

    run_server_fn(
        app=app,
        logger=logger,
        config=config,
    )
    return None


def run_server(
    *,
    app: Any,
    logger: SupportsInfo,
    config: Config,
    config_module: Optional[Any] = None,
    get_platforms: Optional[Callable[[], list[dict[str, Any]]]] = None,
    uvicorn_run: Optional[Callable[..., None]] = None,
    log_startup: Optional[Callable[..., None]] = None,
    watcher_interval: float = 5.0,
) -> None:
    """运行 Web 服务启动流程。"""
    if config_module is None:
        config_module = app_config
    if get_platforms is None:
        from services.platforms import list_supported_platforms

        get_platforms = list_supported_platforms
    if log_startup is None:
        log_startup = log_startup_summary
    if uvicorn_run is None:
        import uvicorn

        uvicorn_run = uvicorn.run
    platforms = get_platforms()
    log_startup(
        logger=logger,
        config=config,
        platforms=platforms,
    )
    config_module.start_config_watcher(
        callback=lambda: logger.info("配置已热重载"),
        interval=watcher_interval,
    )
    logger.info("配置热重载已启用")
    uvicorn_run(app, host=config.host, port=config.port)


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
