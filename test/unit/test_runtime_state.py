import asyncio

from server import AppRuntime, create_runtime


def test_create_runtime_initializes_state_containers():
    runtime = create_runtime()

    assert isinstance(runtime, AppRuntime)
    assert runtime.tasks == {}
    assert runtime.task_last_sse_state == {}
    assert runtime.browser_pool == {}
    assert runtime.download_queue == {}
    assert runtime.download_queue_priority == {}
    assert isinstance(runtime.state_lock, asyncio.Lock)
    assert isinstance(runtime.browser_pool_lock, asyncio.Lock)
    assert isinstance(runtime.download_queue_lock, asyncio.Lock)
    assert runtime.browser_cleanup_task is None
