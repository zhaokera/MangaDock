# Factory Signature Typing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the public type signatures of the factory functions in `services/bootstrap.py` and `services/lifecycle.py` without changing runtime behavior, module boundaries, or exports.

**Architecture:** Keep both modules structurally unchanged and improve only their public contracts. Add minimal in-file type aliases where needed so `create_server_application(...)` and `create_server_lifecycle(...)` clearly communicate their required dependencies and return values, then verify behavior remains unchanged with the existing targeted test suite.

**Tech Stack:** Python 3, FastAPI, pytest, existing `services/bootstrap.py`, existing `services/lifecycle.py`

---

## File Structure

### Existing files to modify

- `services/lifecycle.py` - tighten the public lifecycle factory parameter and return types using only in-file aliases
- `services/bootstrap.py` - tighten the public bootstrap factory parameter types and keep the return type explicit as `FastAPI`

### Existing files to verify

- `test/unit/test_lifecycle.py` - existing lifecycle contract coverage
- `test/unit/test_bootstrap.py` - existing bootstrap contract coverage
- `test/unit/test_app_factory.py` - existing server/bootstrap/lifecycle wiring coverage
- `test/unit/test_runtime_state.py` - existing runtime-state compatibility coverage

---

### Task 1: Tighten `create_server_lifecycle(...)` Public Types

**Files:**
- Modify: `services/lifecycle.py`
- Test: `test/unit/test_lifecycle.py`
- Test: `test/unit/test_app_factory.py`

- [ ] **Step 1: Read the current lifecycle factory signature and identify the minimum public aliases needed**

Target the public surface only:
- runtime type
- logger type
- async cleanup callback type
- async browser-close callback type
- async scheduler callback type
- config getter type
- browser pool value shape
- lifecycle hook type
- lifecycle hook tuple return type

Do not change the internal control flow or rename any function.

- [ ] **Step 2: Replace the broad public signature with explicit aliases and return tuple typing**

Use the existing file only. A target shape is:

```python
import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeAlias

from services.state import AppRuntime

BrowserPool: TypeAlias = dict[str, dict[str, Any]]
AsyncLifecycleHook: TypeAlias = Callable[[], Awaitable[None]]
CleanupBrowserPool: TypeAlias = Callable[..., Awaitable[Any]]
CloseAllBrowsers: TypeAlias = Callable[..., Awaitable[Any]]
ScheduleBrowserCleanup: TypeAlias = Callable[..., Awaitable[Any]]
GetConfig: TypeAlias = Callable[[], Any]
LifecycleHooks: TypeAlias = tuple[
    AsyncLifecycleHook,
    AsyncLifecycleHook,
    AsyncLifecycleHook,
    AsyncLifecycleHook,
]


def create_server_lifecycle(
    *,
    runtime: AppRuntime,
    browser_pool: BrowserPool,
    browser_pool_lock: asyncio.Lock,
    cleanup_browser_pool: CleanupBrowserPool,
    close_all_browsers: CloseAllBrowsers,
    schedule_browser_cleanup: ScheduleBrowserCleanup,
    get_config: GetConfig,
    logger: logging.Logger,
) -> LifecycleHooks:
    ...
```

Keep the implementation body behavior unchanged.

Acceptance matrix for this task:
- Must become specific: `runtime`, `browser_pool`, `browser_pool_lock`, `get_config`, `logger`, returned lifecycle hook tuple
- May remain broad: async callback internals such as `cleanup_browser_pool`, `close_all_browsers`, `schedule_browser_cleanup`
- Must not change: tuple return order, lifecycle behavior, internal helper structure

- [ ] **Step 3: Run the lifecycle-focused regression tests**

Run: `python3 -m pytest test/unit/test_lifecycle.py test/unit/test_app_factory.py -v`

Expected: PASS with no lifecycle behavior changes.

- [ ] **Step 4: Commit the lifecycle typing-only change**

```bash
git add services/lifecycle.py
git commit -m "refactor: tighten lifecycle factory typing"
```

### Task 2: Tighten `create_server_application(...)` Public Types

**Files:**
- Modify: `services/bootstrap.py`
- Test: `test/unit/test_bootstrap.py`
- Test: `test/unit/test_app_factory.py`

- [ ] **Step 1: Read the current bootstrap factory signature and separate the public parameters into clear groups**

Keep the public function as the only target. The grouped inputs should stay recognizable as:
- runtime / logger / downloads dir / config
- task/history persistence callbacks
- crawler/search/auth/resume providers
- browser/history helpers
- lifecycle hooks

Do not change helper nesting or router assembly structure.

- [ ] **Step 2: Discover the callback arities from downstream call sites before narrowing the bootstrap signature**

Use these existing sources of truth:
- `routes/downloads.py` for `create_download_task`, `create_downloader`, `get_task_record`, heartbeat callback expectations
- `routes/history.py` for history callback shapes
- `routes/search.py` for search and manga-search callback shapes
- `routes/auth.py` for auth callback shapes
- `routes/resume.py` for resume callback shapes
- `services/downloader.py` for downloader-side helper callback expectations

Only narrow what can be justified from those call sites without inventing new abstractions.

- [ ] **Step 3: Replace the widest `Callable[..., Any]` uses with clearer in-file aliases where they help the public signature**

A good end state is:
- return type remains `FastAPI`
- runtime is typed as `AppRuntime`
- logger is typed as `logging.Logger`
- simple getters use explicit `Callable[[...], ...]`
- lifecycle hooks are typed as async zero-arg callables
- creation callbacks like `create_download_task` keep their exact arity
- difficult legacy surfaces may retain limited `Any`, but the whole signature should no longer read as “everything is Any”

Keep all private helper implementations behavior-identical.

Acceptance matrix for this task:
- Must become specific: `runtime`, `logger`, `downloads_dir`, `get_config`, `get_task_record`, `delete_task_record`, `get_total_count`, `get_crawler_for_url`, `get_searcher`, `get_manga_searcher`, `get_auth_manager`, `get_resume_manager`, `get_crawler_by_platform`, `create_download_task`, `on_startup`, `on_shutdown`
- May remain broad for now: `save_task_record`, `delete_history_tasks`, `get_history_tasks`, `search_all_platforms`, `init_browser_for_crawler`, `release_browser_for_platform`, `add_history_item`
- Must not change: parameter order, helper nesting, router assembly behavior

- [ ] **Step 4: Run the bootstrap-focused regression tests**

Run: `python3 -m pytest test/unit/test_bootstrap.py test/unit/test_app_factory.py test/unit/test_runtime_state.py -v`

Expected: PASS with no bootstrap or server wiring regressions.

- [ ] **Step 5: Commit the bootstrap typing-only change**

```bash
git add services/bootstrap.py
git commit -m "refactor: tighten bootstrap factory typing"
```

### Task 3: Final Verification and Handoff

**Files:**
- Modify: none
- Test: `test/unit/test_lifecycle.py`
- Test: `test/unit/test_bootstrap.py`
- Test: `test/unit/test_app_factory.py`
- Test: `test/unit/test_runtime_state.py`

- [ ] **Step 1: Re-read both files and confirm the public signatures are clearer without structural churn**

Check:
- only `services/lifecycle.py` and `services/bootstrap.py` changed
- no new files were introduced
- no helper was renamed or reordered
- tuple return typing for lifecycle hooks is explicit
- `create_server_application(...)` reads more clearly at the call boundary
- `server.py` call sites and lifecycle tuple unpacking are unchanged

- [ ] **Step 2: Run the full targeted verification suite**

Run: `python3 -m pytest test/unit/test_lifecycle.py test/unit/test_bootstrap.py test/unit/test_app_factory.py test/unit/test_runtime_state.py -q`

Expected: all targeted tests PASS and no behavior regressions appear.

- [ ] **Step 3: Capture the final worktree state**

Run: `git status --short`

Expected: clean worktree or only unrelated untracked planning/spec files outside the implementation change set.

- [ ] **Step 4: Summarize the typing-only refactor in the handoff**

Include:
- which public factory signatures were tightened
- confirmation that behavior and module boundaries were unchanged
- exact pytest command that passed
