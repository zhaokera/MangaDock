# Server Assembly Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract FastAPI application assembly code from `server.py` into a dedicated bootstrap module while preserving existing imports, routes, and runtime behavior.

**Architecture:** Add a project-level bootstrap module under `services/` that accepts explicit runtime, database, crawler, config, and router dependencies, then owns the project-specific router binding and FastAPI assembly using the existing `services/app_factory.py` helper. Drive the change with tests that lock route registration and import compatibility before moving `server.create_app()` to the new assembly entrypoint.

**Tech Stack:** Python 3, FastAPI, pytest, existing `routes/*` router factories, existing `services/app_factory.py`

---

## File Structure

### Existing files to modify

- `server.py` - keep runtime state, lifecycle, CLI entrypoint, and compatibility exports while delegating app assembly to the new bootstrap module
- `test/unit/test_app_factory.py` - keep the compatibility-level `server.create_app()` route registration assertion, expanding it only if needed for route coverage

### New files to create

- `services/bootstrap.py` - explicit dependency binding, router factory assembly, and project-level FastAPI creation entrypoint
- `test/unit/test_bootstrap.py` - focused bootstrap-level tests that verify route registration through the new assembly API with stubbed dependencies

---

### Task 1: Lock the Bootstrap Contract with a Route Registration Test

**Files:**
- Create: `test/unit/test_bootstrap.py`
- Test: `test/unit/test_bootstrap.py`

- [ ] **Step 1: Write a failing bootstrap-level test for route registration through explicit dependencies**

```python
import logging
from pathlib import Path

from services.bootstrap import create_server_application
from services.state import create_runtime


def test_create_server_application_registers_core_routes():
    runtime = create_runtime()
    app = create_server_application(
        runtime=runtime,
        logger=logging.getLogger("test"),
        downloads_dir=Path("downloads"),
        get_config=lambda: type("Cfg", (), {"history": type("HistoryCfg", (), {"max_items": 100})(), "sse": type("SseCfg", (), {"heartbeat_interval": 1.0})()})(),
        get_task_record=lambda task_id: None,
        save_task_record=lambda *args, **kwargs: None,
        delete_task_record=lambda task_id: None,
        delete_history_tasks=lambda: 0,
        get_history_tasks=lambda limit: [],
        get_total_count=lambda status=None: 0,
        get_crawler_for_url=lambda url: type("Crawler", (), {"PLATFORM_NAME": "dummy"})(),
        get_searcher=lambda platform: None,
        search_all_platforms=lambda keyword, limit_per_platform: [],
        get_manga_searcher=lambda platform: None,
        get_auth_manager=lambda: None,
        get_resume_manager=lambda: None,
        get_crawler_by_platform=lambda platform: None,
        init_browser_for_crawler=lambda **kwargs: None,
        release_browser_for_platform=lambda *args, **kwargs: None,
        add_history_item=lambda *args, **kwargs: True,
        create_download_task=lambda task_id, url, platform: None,
        on_startup=lambda: None,
        on_shutdown=lambda: None,
    )

    routes = {route.path for route in app.routes}
    assert "/" in routes
    assert "/api/download" in routes
    assert "/api/search" in routes
    assert "/api/parse" in routes
    assert "/api/auth/login" in routes
```

- [ ] **Step 2: Run the bootstrap test to verify it fails before implementation**

Run: `pytest test/unit/test_bootstrap.py -v`

Expected: FAIL with `ModuleNotFoundError` for `services.bootstrap` or a signature/implementation error because the assembly entrypoint does not exist yet.

- [ ] **Step 3: Commit the red test**

```bash
git add test/unit/test_bootstrap.py
git commit -m "test: cover server bootstrap assembly"
```

### Task 2: Add the Dedicated Bootstrap Module and Move Router Binding Into It

**Files:**
- Create: `services/bootstrap.py`
- Test: `test/unit/test_bootstrap.py`

- [ ] **Step 1: Implement the bootstrap module with explicit dependency inputs**

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI

from services.app_factory import create_application
from services.downloader import MangaDownloader
from routes.auth import build_auth_router
from routes.downloads import build_download_router
from routes.history import build_history_router
from routes.parse import build_parse_router
from routes.platforms import router as platforms_router
from routes.queue import build_queue_router
from routes.resume import build_resume_router
from routes.search import build_search_router


def create_server_application(
    *,
    runtime: Any,
    logger: Any,
    downloads_dir: Path,
    get_config: Callable[[], Any],
    get_task_record: Callable[[str], Any],
    save_task_record: Callable[..., Any],
    delete_task_record: Callable[[str], Any],
    delete_history_tasks: Callable[[], Any],
    get_history_tasks: Callable[[int], Any],
    get_total_count: Callable[..., int],
    get_crawler_for_url: Callable[[str], Any],
    get_searcher: Callable[[str], Any],
    search_all_platforms: Callable[..., Any],
    get_manga_searcher: Callable[[str], Any],
    get_auth_manager: Callable[[], Any],
    get_resume_manager: Callable[[], Any],
    get_crawler_by_platform: Callable[[str], Any],
    init_browser_for_crawler: Callable[..., Any],
    release_browser_for_platform: Callable[..., Any],
    add_history_item: Callable[..., Any],
    create_download_task: Callable[[str, str, str], Any],
    on_startup: Callable[[], Any],
    on_shutdown: Callable[[], Any],
) -> FastAPI:
    def _history_max_items() -> int:
        value = get_config().history.max_items
        return value if value > 0 else 100

    async def _add_history_record(history_item: dict) -> bool:
        return await add_history_item(
            history_item,
            state_lock=runtime.state_lock,
            get_task_record=get_task_record,
            save_task_record=save_task_record,
            get_total_completed_count=lambda: get_total_count(status="completed"),
            get_history_tasks=lambda limit: get_history_tasks(limit=limit),
            delete_task_record=delete_task_record,
            get_history_max_items=_history_max_items,
        )

    async def _bind_crawler_browser(crawler, platform: str) -> None:
        await init_browser_for_crawler(
            crawler=crawler,
            platform=platform,
            browser_pool=runtime.browser_pool,
            browser_pool_lock=runtime.browser_pool_lock,
            get_config=get_config,
            logger=logger,
        )

    def _release_platform_browser(platform: str) -> None:
        release_browser_for_platform(
            runtime.browser_pool,
            platform,
            asyncio.get_running_loop().time(),
        )

    def _build_downloader(task):
        return MangaDownloader(
            task,
            downloads_dir=downloads_dir,
            get_crawler_for_url=get_crawler_for_url,
            init_browser_for_crawler=_bind_crawler_browser,
            release_browser_for_platform=_release_platform_browser,
            save_task_record=save_task_record,
            add_history_item=_add_history_record,
            task_last_sse_state=runtime.task_last_sse_state,
            tasks=runtime.tasks,
        )

    def _build_download_router():
        return build_download_router(
            get_crawler_for_url=get_crawler_for_url,
            create_download_task=create_download_task,
            create_downloader=_build_downloader,
            get_task_record=get_task_record,
            task_last_sse_state=runtime.task_last_sse_state,
            get_heartbeat_interval=lambda: get_config().sse.heartbeat_interval,
        )

    def _build_history_router():
        return build_history_router(
            get_history_tasks=lambda limit: get_history_tasks(limit=limit),
            get_history_max_items=_history_max_items,
            get_task_record=get_task_record,
            delete_task_record=delete_task_record,
            delete_history_tasks=delete_history_tasks,
        )

    def _build_queue_router():
        return build_queue_router(
            download_queue=runtime.download_queue,
            priorities=runtime.download_queue_priority,
            queue_lock=runtime.download_queue_lock,
        )

    def _build_search_router():
        return build_search_router(
            search_all_platforms=search_all_platforms,
            get_searcher=get_searcher,
            get_manga_searcher=get_manga_searcher,
        )

    def _build_parse_router():
        return build_parse_router(get_crawler_for_url=get_crawler_for_url)

    def _build_auth_router():
        return build_auth_router(
            get_auth_manager=get_auth_manager,
            get_crawler_by_platform=get_crawler_by_platform,
        )

    def _build_resume_router():
        return build_resume_router(get_resume_manager=get_resume_manager)

    return create_application(
        title="漫画下载器",
        description="支持多平台的漫画下载服务",
        platforms_router=platforms_router,
        download_router_factory=_build_download_router,
        history_router_factory=_build_history_router,
        queue_router_factory=_build_queue_router,
        search_router_factory=_build_search_router,
        parse_router_factory=_build_parse_router,
        auth_router_factory=_build_auth_router,
        resume_router_factory=_build_resume_router,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )
```

- [ ] **Step 2: Fill in the router factory bindings with the exact dependencies currently wired in `server.py`**

Move these responsibilities into `services/bootstrap.py`:

- `_history_max_items()`
- `_add_history_record()`
- `_build_downloader()`
- download/history/queue/search/parse/auth/resume router factory assembly
- browser binding helpers needed by the downloader closure

Keep runtime creation, lifecycle methods, `app = create_app()`, and CLI logic in `server.py`.

- [ ] **Step 3: Run the bootstrap test to verify green**

Run: `pytest test/unit/test_bootstrap.py -v`

Expected: PASS

- [ ] **Step 4: Commit the bootstrap module**

```bash
git add services/bootstrap.py test/unit/test_bootstrap.py
git commit -m "refactor: add server bootstrap module"
```

### Task 3: Move `server.py` Assembly Wiring to the Bootstrap Module

**Files:**
- Modify: `server.py`
- Modify: `services/bootstrap.py`
- Modify: `test/unit/test_app_factory.py` (only if current assertions need to cover the delegated path explicitly)
- Test: `test/unit/test_app_factory.py`
- Test: `test/unit/test_runtime_state.py`
- Test: `test/unit/test_bootstrap.py`

- [ ] **Step 1: Replace the local assembly helpers in `server.py` with imports from the bootstrap module**

```python
from services.bootstrap import create_server_application
```

Delete the now-migrated assembly helpers from `server.py` after their responsibility exists in `services/bootstrap.py`. Do not move runtime creation, lifecycle functions, or CLI logic out of `server.py`.

- [ ] **Step 2: Update `server.create_app()` to pass the existing runtime resources and providers into the bootstrap entrypoint**

```python
from services.bootstrap import create_server_application


def create_app() -> FastAPI:
    return create_server_application(
        runtime=runtime,
        logger=logger,
        downloads_dir=DOWNLOADS_DIR,
        get_config=config.get_config,
        get_task_record=get_task,
        save_task_record=save_task,
        delete_task_record=delete_task,
        delete_history_tasks=delete_history_tasks,
        get_history_tasks=get_history_tasks,
        get_total_count=get_total_count,
        get_crawler_for_url=get_crawler,
        get_searcher=get_searcher,
        search_all_platforms=search_all_platforms,
        get_manga_searcher=get_manga_searcher,
        get_auth_manager=get_auth_manager,
        get_resume_manager=get_resume_manager,
        get_crawler_by_platform=get_crawler_by_platform,
        init_browser_for_crawler=init_browser_for_crawler,
        release_browser_for_platform=release_browser_for_platform,
        add_history_item=add_history_item,
        create_download_task=DownloadTask,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
    )
```

- [ ] **Step 3: Update the compatibility test only if needed to prove the delegated path still exposes the same routes**

Keep [`test/unit/test_app_factory.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_app_factory.py) focused on `from server import create_app`; only add assertions if route coverage is now missing.

- [ ] **Step 4: Run the compatibility and runtime tests**

Run: `pytest test/unit/test_bootstrap.py test/unit/test_app_factory.py test/unit/test_runtime_state.py -v`

Expected: PASS

- [ ] **Step 5: Read the diff for `server.py` and confirm only assembly responsibilities moved**

Run: `git diff -- services/bootstrap.py server.py test/unit/test_bootstrap.py test/unit/test_app_factory.py`

Expected: `server.py` still defines runtime state, lifecycle functions, `create_app()`, module-level `app`, and CLI entrypoint, while dependency binding and router assembly moved into `services/bootstrap.py`.

- [ ] **Step 6: Commit the delegated assembly wiring**

```bash
git add server.py services/bootstrap.py test/unit/test_bootstrap.py test/unit/test_app_factory.py
git commit -m "refactor: extract server assembly wiring"
```

### Task 4: Final Verification and Handoff

**Files:**
- Modify: none
- Test: `test/unit/test_bootstrap.py`
- Test: `test/unit/test_app_factory.py`
- Test: `test/unit/test_runtime_state.py`

- [ ] **Step 1: Run the final targeted verification command from a clean test state**

Run: `pytest test/unit/test_bootstrap.py test/unit/test_app_factory.py test/unit/test_runtime_state.py -q`

Expected: all targeted tests PASS with no route registration regressions.

- [ ] **Step 2: Capture the final worktree state**

Run: `git status --short`

Expected: clean worktree or only the intended implementation changes before the final commit.

- [ ] **Step 3: Summarize the behavior-preserving refactor in the handoff**

Include:
- new bootstrap file path
- confirmation that `server.py` still exports `app`, `create_app`, `runtime`, `AppRuntime`, and `create_runtime`
- exact test command that passed
