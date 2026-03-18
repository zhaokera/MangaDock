# 测试架构设计文档

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 MangaDock 项目建立完整的测试架构，包括单元测试、集成测试和端到端测试

**Architecture:** 采用分层测试策略：
1. **unit/** - 爬虫逻辑的单元测试（使用 mock 模拟浏览器和网络）
2. **integration/** - 爬虫与数据库协同的集成测试
3. **e2e/** - 完整下载流程的端到端测试（使用 Playwright）

**Tech Stack:**
- pytest - 测试框架
- pytest-asyncio - 异步测试支持
- unittest.mock - 对象模拟
- pytest-mock - Mock API
- httpx mock - 网络请求拦截

---

## 目录结构

```
test/
├── unit/                     # 单元测试
│   ├── __init__.py
│   ├── test_crawler_base.py      # BaseCrawler 基类测试
│   ├── test_crawler_manhuagui.py # 漫画柜爬虫测试
│   ├── test_crawler_kuaikan.py   # 快看漫画爬虫测试
│   ├── test_db_operations.py     # 数据库操作测试
│   └── test_config.py            # 配置管理测试
├── integration/              # 集成测试
│   ├── __init__.py
│   ├── test_crawler_with_db.py   # 爬虫与数据库集成测试
│   └── test_downloader.py        # 下载器集成测试
└── e2e/                      # 端到端测试
    ├── __init__.py
    └── test_full_download_flow.py # 完整下载流程测试

conftest.py                   # pytest 全局配置和 fixtures
requirements-test.txt         # 测试依赖
```

---

## 测试范围

### 单元测试 (unit/)

**test_crawler_base.py**
- ✅ BaseCrawler 初始化和配置
- ✅ can_handle() URL 匹配
- ✅ get_http_client() 连接池管理
- ✅ sanitize_filename() 文件名清理
- ✅ download_image() 重试机制（mock 网络）

**test_crawler_manhuagui.py**
- ✅ _extract_ids() URL 解析
- ✅ _normalize_image_url() URL 规范化
- ✅ lzstring_decompress() 解密算法
- ✅ _get_image_urls_via_js() JS 解析逻辑（mock DOM）
- ✅ _wait_for_page_ready() 等待逻辑（mock 时间）

**test_crawler_kuaikan.py**
- ✅ _extract_ids() URL 解析
- ✅ _do_download() 图片捕获流程（mock response）

**test_db_operations.py**
- ✅ TaskRecord 数据序列化
- ✅ save_task() 保存任务
- ✅ get_task() 查询任务
- ✅ update_task_status() 更新状态
- ✅ get_history_tasks() 历史查询

**test_config.py**
- ✅ get_config() 配置加载
- ✅ ConfigManager.validate() 配置验证
- ✅ 环境变量覆盖

### 集成测试 (integration/)

**test_crawler_with_db.py**
- 完整的爬虫 - 数据库交互流程
- 任务状态更新持久化
- 历史记录保存

**test_downloader.py**
- MangaDownloader 完整流程
- 进度回调触发
- 文件保存验证

### 端到端测试 (e2e/)

**test_full_download_flow.py**
- 完整的下载流程（真实浏览器）
- 从 URL 输入到 ZIP 文件生成
- SSE 进度推送验证

---

## conftest.py 全局配置

```python
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
```

---

## requirements-test.txt

```
pytest>=7.0.0
pytest-asyncio>=0.21.0
pytest-mock>=3.10.0
httpx>=0.24.0
playwright>=1.40.0
```

---

## 测试运行

### 运行所有测试
```bash
pytest -v
```

### 运行特定测试
```bash
pytest test/unit/test_crawler_base.py -v
pytest test/unit/test_db_operations.py -v
pytest test/integration/test_downloader.py -v
pytest test/e2e/test_full_download_flow.py -v
```

### 生成覆盖率报告
```bash
pytest --cov=crawlers --cov-report=html
```

### 仅运行失败的测试
```bash
pytest --lf
```