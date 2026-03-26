import sys
from types import SimpleNamespace
from typing import Any, Callable, Optional, get_type_hints

from config import Config
import services.platforms
import services.runtime as runtime
from services.runtime import build_cli_parser
from services.runtime import build_runtime_aliases
from services.runtime import build_server_entrypoint_kwargs
from services.runtime import configure_server_logging
from services.runtime import format_cli_search_results
from services.runtime import initialize_server_state
from services.runtime import prepare_server_environment
from services.runtime import run_entrypoint
from services.runtime import run_server
from services.state import AppRuntime


def test_runtime_helper_public_signatures_are_typed():
    init_hints = get_type_hints(initialize_server_state)
    prepare_hints = get_type_hints(prepare_server_environment)
    run_entrypoint_hints = get_type_hints(run_entrypoint)
    run_server_hints = get_type_hints(run_server)
    logging_hints = get_type_hints(configure_server_logging)
    parser_hints = get_type_hints(build_cli_parser)

    assert logging_hints["logger_name"] is str
    assert logging_hints["return"] is runtime.logging.Logger

    alias_hints = get_type_hints(build_runtime_aliases)
    assert alias_hints["runtime"] is AppRuntime
    assert alias_hints["return"] is runtime.RuntimeAliases

    assert init_hints["get_config"] == Callable[[], Config]
    assert init_hints["create_runtime_fn"] == Callable[[], AppRuntime]
    assert init_hints["return"] == tuple[Config, AppRuntime, runtime.Path]

    assert prepare_hints["init_db_fn"] == Callable[[], None]
    assert prepare_hints["downloads_dir"] is runtime.Path
    assert prepare_hints["return"] is type(None)

    assert parser_hints["return"] is runtime.argparse.ArgumentParser

    entrypoint_builder_hints = get_type_hints(build_server_entrypoint_kwargs)
    assert entrypoint_builder_hints["config"] is Config
    assert entrypoint_builder_hints["downloads_dir"] is str
    assert entrypoint_builder_hints["get_searcher"] == Callable[[str], Any]
    assert entrypoint_builder_hints["search_all_platforms"] == Callable[[str, int], Any]
    assert entrypoint_builder_hints["get_crawler_for_url"] == Callable[[str], Any]
    assert entrypoint_builder_hints["return"] is runtime.ServerEntrypointKwargs

    assert run_entrypoint_hints["argv"] == Optional[list[str]]
    assert run_entrypoint_hints["config"] is Config
    assert run_entrypoint_hints["downloads_dir"] is str
    assert run_entrypoint_hints["get_searcher"] == Callable[[str], Any]
    assert run_entrypoint_hints["search_all_platforms"] == Callable[[str, int], Any]
    assert run_entrypoint_hints["get_crawler_for_url"] == Callable[[str], Any]
    assert run_entrypoint_hints["return"] == Optional[int]

    assert run_server_hints["logger"] is runtime.SupportsInfo
    assert run_server_hints["config"] is Config
    assert run_server_hints["watcher_interval"] is float
    assert run_server_hints["return"] is type(None)


def test_configure_server_logging_sets_expected_levels(monkeypatch):
    calls = []
    loggers = {}
    original_get_logger = runtime.logging.getLogger

    class FakeLogger:
        def __init__(self, name):
            self.name = name
            self.levels = []

        def setLevel(self, level):
            self.levels.append(level)

    def fake_basic_config(**kwargs):
        calls.append(kwargs)

    def fake_get_logger(name=None):
        if name is None:
            return original_get_logger()
        logger = loggers.setdefault(name, FakeLogger(name))
        return logger

    monkeypatch.setattr(runtime.logging, "basicConfig", fake_basic_config)
    monkeypatch.setattr(runtime.logging, "getLogger", fake_get_logger)

    logger = configure_server_logging("server")

    assert logger is loggers["server"]
    assert calls == [
        {
            "level": runtime.logging.INFO,
            "format": "%(asctime)s [%(levelname)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    ]
    assert loggers["crawlers"].levels == [runtime.logging.INFO]
    assert loggers["crawlers.tencent"].levels == [runtime.logging.INFO]
    assert loggers["crawlers.iqiyi"].levels == [runtime.logging.INFO]


def test_build_runtime_aliases_preserves_compatibility_names():
    runtime_state = runtime.AppRuntime()

    aliases = build_runtime_aliases(runtime_state)

    assert aliases == {
        "tasks": runtime_state.tasks,
        "task_last_sse_state": runtime_state.task_last_sse_state,
        "_state_lock": runtime_state.state_lock,
        "_browser_pool": runtime_state.browser_pool,
        "_browser_pool_lock": runtime_state.browser_pool_lock,
        "_download_queue": runtime_state.download_queue,
        "_download_queue_priority": runtime_state.download_queue_priority,
        "_download_queue_lock": runtime_state.download_queue_lock,
    }


def test_initialize_server_state_loads_config_initializes_db_and_download_dir(tmp_path):
    calls = []
    cfg = Config()
    cfg.download.output_dir = str(tmp_path / "downloads")

    def fake_get_config():
        calls.append("get_config")
        return cfg

    def fake_create_runtime():
        calls.append("create_runtime")
        return "runtime"

    loaded_config, runtime_state, downloads_dir = initialize_server_state(
        get_config=fake_get_config,
        create_runtime_fn=fake_create_runtime,
    )

    assert loaded_config is cfg
    assert runtime_state == "runtime"
    assert downloads_dir == tmp_path / "downloads"
    assert not downloads_dir.exists()
    assert calls == ["get_config", "create_runtime"]


def test_prepare_server_environment_initializes_db_and_download_dir(tmp_path):
    calls = []
    downloads_dir = tmp_path / "downloads"

    def fake_init_db():
        calls.append("init_db")

    runtime.prepare_server_environment(
        init_db_fn=fake_init_db,
        downloads_dir=downloads_dir,
    )

    assert downloads_dir.exists()
    assert calls == ["init_db"]


def test_run_server_uses_default_startup_wiring(monkeypatch):
    logger_calls = []
    summary_calls = []
    watcher_calls = []
    uvicorn_calls = []

    class FakeLogger:
        def info(self, message):
            logger_calls.append(message)

    def fake_log_startup_summary(*, logger, config, platforms):
        summary_calls.append(
            {
                "logger": logger,
                "config": config,
                "platforms": platforms,
            }
        )

    app = object()
    cfg = Config()
    cfg.host = "127.0.0.1"
    cfg.port = 9000
    platforms = [{"display_name": "腾讯视频"}]
    logger = FakeLogger()

    def fake_start_config_watcher(*, callback, interval):
        watcher_calls.append(
            {
                "callback": callback,
                "interval": interval,
            }
        )

    def fake_uvicorn_run(app, *, host, port):
        uvicorn_calls.append(
            {
                "app": app,
                "host": host,
                "port": port,
            }
        )

    monkeypatch.setattr(runtime, "log_startup_summary", fake_log_startup_summary)
    monkeypatch.setattr(services.platforms, "list_supported_platforms", lambda: platforms)
    monkeypatch.setattr(runtime.app_config, "start_config_watcher", fake_start_config_watcher)
    monkeypatch.setitem(
        sys.modules,
        "uvicorn",
        SimpleNamespace(run=fake_uvicorn_run),
    )

    run_server(
        app=app,
        logger=logger,
        config=cfg,
    )

    assert summary_calls == [
        {
            "logger": logger,
            "config": cfg,
            "platforms": platforms,
        }
    ]
    assert watcher_calls[0]["interval"] == 5.0
    watcher_calls[0]["callback"]()
    assert logger_calls == ["配置热重载已启用", "配置已热重载"]
    assert uvicorn_calls == [
        {
            "app": app,
            "host": "127.0.0.1",
            "port": 9000,
        }
    ]


def test_run_entrypoint_dispatches_search_cli():
    calls = []
    searcher_getter = object()
    search_all = object()

    def fake_run_search_cli(**kwargs):
        calls.append(kwargs)
        return 3

    exit_code = run_entrypoint(
        argv=["--search", "海贼王", "--platform", "tencent", "--limit", "4"],
        app=object(),
        logger=object(),
        config=Config(),
        downloads_dir="downloads",
        get_searcher=searcher_getter,
        search_all_platforms=search_all,
        get_crawler_for_url=object(),
        run_search=fake_run_search_cli,
        asyncio_run=lambda result: result,
    )

    assert exit_code == 3
    assert calls == [
        {
            "keyword": "海贼王",
            "platform": "tencent",
            "limit": 4,
            "get_searcher": searcher_getter,
            "search_all_platforms": search_all,
        }
    ]


def test_run_entrypoint_dispatches_download_cli():
    calls = []

    def fake_run_download_cli(**kwargs):
        calls.append(kwargs)
        return 5

    exit_code = run_entrypoint(
        argv=["--download", "https://example.com/demo"],
        app=object(),
        logger=object(),
        config=Config(),
        downloads_dir="downloads",
        get_searcher=object(),
        search_all_platforms=object(),
        get_crawler_for_url="crawler-getter",
        run_download=fake_run_download_cli,
        asyncio_run=lambda result: result,
    )

    assert exit_code == 5
    assert calls == [
        {
            "url": "https://example.com/demo",
            "downloads_dir": "downloads",
            "get_crawler_for_url": "crawler-getter",
        }
    ]


def test_run_entrypoint_starts_server_when_no_cli_mode():
    calls = []
    app = object()
    logger = object()
    cfg = Config()

    def fake_run_server(**kwargs):
        calls.append(kwargs)

    exit_code = run_entrypoint(
        argv=[],
        app=app,
        logger=logger,
        config=cfg,
        downloads_dir="downloads",
        get_searcher=object(),
        search_all_platforms=object(),
        get_crawler_for_url=object(),
        run_server_fn=fake_run_server,
    )

    assert exit_code is None
    assert calls == [
        {
            "app": app,
            "logger": logger,
            "config": cfg,
        }
    ]


def test_build_server_entrypoint_kwargs_preserves_dependency_mapping():
    app = object()
    logger = object()
    config = Config()
    searcher_getter = object()
    search_all = object()
    crawler_getter = object()

    kwargs = build_server_entrypoint_kwargs(
        app=app,
        logger=logger,
        config=config,
        downloads_dir="downloads",
        get_searcher=searcher_getter,
        search_all_platforms=search_all,
        get_crawler_for_url=crawler_getter,
    )

    assert kwargs == {
        "argv": None,
        "app": app,
        "logger": logger,
        "config": config,
        "downloads_dir": "downloads",
        "get_searcher": searcher_getter,
        "search_all_platforms": search_all,
        "get_crawler_for_url": crawler_getter,
    }


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
