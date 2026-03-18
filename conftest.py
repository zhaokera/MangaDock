"""pytest 全局配置和 fixtures"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture(scope="session")
def test_config():
    """测试配置 - 使用临时目录"""
    return {
        ".download_dir": tempfile.mkdtemp(),
        "output_dir": tempfile.mkdtemp(),
    }


@pytest.fixture
def temp_dir():
    """临时目录 fixture"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(scope="module")
def event_loop():
    """异步测试的事件循环"""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db_path(temp_dir):
    """临时数据库路径 fixture"""
    return temp_dir / "test.db"


@pytest.fixture
def temp_download_dir(temp_dir):
    """临时下载目录 fixture"""
    dir_path = temp_dir / "downloads"
    dir_path.mkdir()
    return str(dir_path)
