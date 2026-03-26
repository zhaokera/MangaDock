# Server Lifecycle Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract browser cleanup scheduling and application lifecycle implementation from `server.py` into a dedicated lifecycle module while preserving startup behavior and `server.py` compatibility exports.

**Architecture:** Add a project-level lifecycle module under `services/` that accepts explicit runtime, browser-pool, config, and logger dependencies, and returns the `start_browser_cleanup_scheduler`, `stop_browser_cleanup_scheduler`, `on_startup`, and `on_shutdown` functions that `server.py` continues to export. Drive the refactor with lifecycle-focused tests first, then delegate `server.py` to the new lifecycle factory without touching CLI or config hot-reload logic.

**Tech Stack:** Python 3, FastAPI, pytest, existing `services/browser_pool.py`, existing `services/bootstrap.py`

---

## File Structure

### Existing files to modify

- `server.py` - keep runtime state, compatibility aliases, app assembly, config watcher, and CLI entrypoint while delegating lifecycle implementation to the new module
- `test/unit/test_app_factory.py` - keep compatibility-level checks and extend only if needed to lock lifecycle export compatibility

### New files to create

- `services/lifecycle.py` - explicit lifecycle and browser cleanup scheduler factory functions
- `test/unit/test_lifecycle.py` - focused lifecycle tests for scheduler creation, cancellation, and shutdown ordering

---

### Task 1: Lock the Lifecycle Contract with Focused Tests

**Files:**
- Create: `test/unit/test_lifecycle.py`
- Test: `test/unit/test_lifecycle.py`

- [ ] **Step 1: Write a failing lifecycle test for scheduler creation and task recording**

```python
import asyncio
import logging

from services.lifecycle import create_server_lifecycle
from services.state import create_runtime


async def _idle_cleanup_loop(*, interval, cleanup_browser_pool, logger):
    while True:
        await asyncio.sleep(3600)


def _config_with_interval(interval: int = 60):
    return type(
        "Cfg",
        (),
        {"crawler": type("CrawlerCfg", (), {"browser_cleanup_interval": interval})()},
    )()


@pytest.mark.asyncio
async def test_start_scheduler_creates_runtime_cleanup_task():
    runtime = create_runtime()
    start_browser_cleanup_scheduler, _, _, _ = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=lambda: None,
        close_all_browsers=lambda **kwargs: None,
        schedule_browser_cleanup=_idle_cleanup_loop,
        get_config=lambda: _config_with_interval(12),
        logger=logging.getLogger("test"),
    )

    await start_browser_cleanup_scheduler()

    assert runtime.browser_cleanup_task is not None
    runtime.browser_cleanup_task.cancel()
```

- [ ] **Step 2: Add a failing shutdown-order test before implementation**

```python
@pytest.mark.asyncio
async def test_on_shutdown_closes_browsers_before_stopping_scheduler():
    runtime = create_runtime()
    calls = []

    async def fake_close_all_browsers(**kwargs):
        calls.append("close")

    (
        start_browser_cleanup_scheduler,
        _stop_browser_cleanup_scheduler,
        _on_startup,
        on_shutdown,
    ) = create_server_lifecycle(
        runtime=runtime,
        browser_pool=runtime.browser_pool,
        browser_pool_lock=runtime.browser_pool_lock,
        cleanup_browser_pool=lambda: None,
        close_all_browsers=fake_close_all_browsers,
        schedule_browser_cleanup=_idle_cleanup_loop,
        get_config=lambda: _config_with_interval(),
        logger=logging.getLogger("test"),
    )

    await start_browser_cleanup_scheduler()

    original_task = runtime.browser_cleanup_task
    assert original_task is not None
    original_cancel = original_task.cancel

    def wrapped_cancel():
        calls.append("stop")
        return original_cancel()

    original_task.cancel = wrapped_cancel
    await on_shutdown()

    assert calls == ["close", "stop"]
```

- [ ] **Step 3: Run the lifecycle test file to verify it fails before implementation**

Run: `python3 -m pytest test/unit/test_lifecycle.py -v`

Expected: FAIL with `ModuleNotFoundError` for `services.lifecycle` or missing `create_server_lifecycle`.

- [ ] **Step 4: Commit the red lifecycle tests**

```bash
git add test/unit/test_lifecycle.py
git commit -m "test: cover server lifecycle contract"
```

### Task 2: Add the Dedicated Lifecycle Module

**Files:**
- Create: `services/lifecycle.py`
- Modify: `test/unit/test_lifecycle.py` only if the red tests need small adjustments to match the exact factory signature
- Test: `test/unit/test_lifecycle.py`

- [ ] **Step 1: Implement `services/lifecycle.py` with an explicit lifecycle factory**

```python
from __future__ import annotations

import asyncio
from typing import Any, Callable


def create_server_lifecycle(
    *,
    runtime: Any,
    browser_pool: dict[str, dict],
    browser_pool_lock: asyncio.Lock,
    cleanup_browser_pool: Callable[..., Any],
    close_all_browsers: Callable[..., Any],
    schedule_browser_cleanup: Callable[..., Any],
    get_config: Callable[[], Any],
    logger: Any,
):
    async def start_browser_cleanup_scheduler():
        cfg = get_config()
        cleanup_interval = getattr(cfg.crawler, "browser_cleanup_interval", 60)
        runtime.browser_cleanup_task = asyncio.create_task(
            schedule_browser_cleanup(
                interval=cleanup_interval,
                cleanup_browser_pool=lambda: cleanup_browser_pool(
                    browser_pool=browser_pool,
                    browser_pool_lock=browser_pool_lock,
                    get_config=get_config,
                    logger=logger,
                ),
                logger=logger,
            )
        )
        logger.info("浏览器池清理调度器已启动 (interval=%ss)", cleanup_interval)

    async def stop_browser_cleanup_scheduler():
        if runtime.browser_cleanup_task:
            runtime.browser_cleanup_task.cancel()
            try:
                await runtime.browser_cleanup_task
            except asyncio.CancelledError:
                pass
            runtime.browser_cleanup_task = None

    async def on_startup():
        await start_browser_cleanup_scheduler()

    async def on_shutdown():
        await close_all_browsers(
            browser_pool=browser_pool,
            browser_pool_lock=browser_pool_lock,
            logger=logger,
        )
        await stop_browser_cleanup_scheduler()

    return (
        start_browser_cleanup_scheduler,
        stop_browser_cleanup_scheduler,
        on_startup,
        on_shutdown,
    )
```

- [ ] **Step 2: Keep the shutdown-order test stable by observing task cancellation instead of patching function globals**

Use the created `runtime.browser_cleanup_task` as the stop signal:
- wrap the task's `cancel()` method to append `"stop"` to the call list
- keep `fake_close_all_browsers()` appending `"close"`
- assert `["close", "stop"]` after `await on_shutdown()`

This tests the required behavioral contract without rebinding inner function globals.

- [ ] **Step 3: Run the lifecycle tests to verify green**

Run: `python3 -m pytest test/unit/test_lifecycle.py -v`

Expected: PASS

- [ ] **Step 4: Commit the lifecycle module**

```bash
git add services/lifecycle.py test/unit/test_lifecycle.py
git commit -m "refactor: add server lifecycle module"
```

### Task 3: Delegate `server.py` Lifecycle Wiring to the New Module

**Files:**
- Modify: `server.py`
- Modify: `test/unit/test_app_factory.py` only if needed for compatibility coverage
- Test: `test/unit/test_bootstrap.py`
- Test: `test/unit/test_app_factory.py`
- Test: `test/unit/test_runtime_state.py`
- Test: `test/unit/test_lifecycle.py`

- [ ] **Step 1: Replace the inline lifecycle implementation in `server.py` with lifecycle-factory wiring**

```python
from services.lifecycle import create_server_lifecycle


(
    start_browser_cleanup_scheduler,
    stop_browser_cleanup_scheduler,
    on_startup,
    on_shutdown,
) = create_server_lifecycle(
    runtime=runtime,
    browser_pool=_browser_pool,
    browser_pool_lock=_browser_pool_lock,
    cleanup_browser_pool=cleanup_browser_pool,
    close_all_browsers=close_all_browsers,
    schedule_browser_cleanup=schedule_browser_cleanup,
    get_config=config.get_config,
    logger=logger,
)
```

- [ ] **Step 2: Delete the old inline lifecycle function bodies from `server.py`**

Remove only:
- `start_browser_cleanup_scheduler`
- `stop_browser_cleanup_scheduler`
- `on_startup`
- `on_shutdown`

Do not remove:
- runtime creation
- compatibility aliases
- `create_app()`
- module-level `app`
- config watcher startup
- CLI entrypoint

- [ ] **Step 3: Add or adjust a compatibility test only if needed to lock the lifecycle export surface**

If current coverage is insufficient, add assertions like:

```python
def test_server_preserves_lifecycle_exports():
    assert callable(server.start_browser_cleanup_scheduler)
    assert callable(server.stop_browser_cleanup_scheduler)
    assert callable(server.on_startup)
    assert callable(server.on_shutdown)
```

Keep the test focused on compatibility, not implementation details.

- [ ] **Step 4: Run the targeted regression set**

Run: `python3 -m pytest test/unit/test_lifecycle.py test/unit/test_bootstrap.py test/unit/test_app_factory.py test/unit/test_runtime_state.py -v`

Expected: PASS

- [ ] **Step 5: Read the diff and confirm only lifecycle implementation moved**

Run: `git diff -- services/lifecycle.py server.py test/unit/test_lifecycle.py test/unit/test_app_factory.py`

Expected: `server.py` still owns runtime state, app assembly delegation, config watcher startup, and CLI logic, while lifecycle implementation details moved into `services/lifecycle.py`.

- [ ] **Step 6: Commit the lifecycle delegation wiring**

```bash
git add services/lifecycle.py server.py test/unit/test_lifecycle.py test/unit/test_app_factory.py
git commit -m "refactor: extract server lifecycle wiring"
```

### Task 4: Final Verification and Handoff

**Files:**
- Modify: none
- Test: `test/unit/test_lifecycle.py`
- Test: `test/unit/test_bootstrap.py`
- Test: `test/unit/test_app_factory.py`
- Test: `test/unit/test_runtime_state.py`

- [ ] **Step 1: Run the final targeted verification command**

Run: `python3 -m pytest test/unit/test_lifecycle.py test/unit/test_bootstrap.py test/unit/test_app_factory.py test/unit/test_runtime_state.py -q`

Expected: all targeted tests PASS with no lifecycle or compatibility regressions.

- [ ] **Step 2: Capture the final worktree state**

Run: `git status --short`

Expected: clean worktree or only intended untracked planning/spec files outside the implementation change set.

- [ ] **Step 3: Summarize the behavior-preserving lifecycle refactor in the handoff**

Include:
- new lifecycle file path
- confirmation that `server.py` still exports `start_browser_cleanup_scheduler`, `stop_browser_cleanup_scheduler`, `on_startup`, and `on_shutdown`
- exact verification command that passed
