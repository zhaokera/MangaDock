# Tests

## 测试架构

本项目使用 pytest 进行测试，采用分层测试策略：

### 单元测试 (test/unit/)
测试单个组件的功能，使用 mock 模拟外部依赖。

运行：`pytest test/unit/ -v`

### 集成测试 (test/integration/)
测试组件之间的协同工作。

运行：`pytest test/integration/ -v`

### 端到端测试 (test/e2e/)
测试完整的用户流程。

运行：`pytest test/e2e/ -v`

## 运行所有测试

```bash
pytest -v
```

## 生成覆盖率报告

```bash
pytest --cov=crawlers --cov-report=html --cov-report=term
```

## 仅运行失败的测试

```bash
pytest --lf
```

## 仅运行特定测试

```bash
pytest test/unit/test_db_operations.py -v
pytest test/integration/test_downloader.py -v
pytest test/e2e/test_full_download_flow.py -v
```

## 测试文件结构

```
test/
├── __init__.py
├── conftest.py              # pytest 全局配置和 fixtures
├── requirements-test.txt    # 测试依赖
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── test_crawler_base.py      # BaseCrawler 基类测试
│   ├── test_crawler_manhuagui.py # 漫画柜爬虫测试
│   ├── test_crawler_kuaikan.py   # 快看漫画爬虫测试
│   ├── test_db_operations.py     # 数据库操作测试
│   └── test_config.py            # 配置管理测试
├── integration/             # 集成测试
│   ├── __init__.py
│   ├── test_crawler_with_db.py   # 爬虫与数据库集成测试
│   └── test_downloader.py        # 下载器集成测试
└── e2e/                     # 端到端测试
    ├── __init__.py
    └── test_full_download_flow.py # 完整下载流程测试
```

## 测试范围

### 单元测试
- BaseCrawler 初始化和配置
- can_handle() URL 匹配
- sanitize_filename() 文件名清理
- lzstring_decompress() 解密算法
- TaskRecord 数据序列化
- save_task()/get_task()/update_task_status() 数据库操作
- ConfigManager 配置验证
- 环境变量覆盖

### 集成测试
- 爬虫与数据库交互
- 任务状态更新持久化
- 进度回调触发
- 爬虫注册和检索

### 端到端测试
- 完整下载流程
- 平台 URL 匹配
- SSE 进度推送
- 任务持久化

## 依赖

安装测试依赖：

```bash
pip install -r requirements-test.txt
```

测试依赖包括：
- pytest - 测试框架
- pytest-asyncio - 异步测试支持
- pytest-mock - Mock API
- httpx - HTTP 客户端
- playwright - 浏览器自动化

## 运行特定测试类型

```bash
# 仅运行单元测试
pytest test/unit/ -v

# 仅运行集成测试
pytest test/integration/ -v

# 仅运行 e2e 测试
pytest test/e2e/ -v
```

## CI/CD 集成

在 CI/CD pipeline 中运行测试：

```bash
# 安装依赖
pip install -r requirements-test.txt

# 运行所有测试
pytest -v --tb=short

# 生成覆盖率报告
pytest --cov=crawlers --cov-report=html
```

## 注意事项

旧测试文件（如 `test/test_download.py`）使用原生 async/await，需要安装 `pytest-asyncio` 插件。新测试文件使用标准的 pytest-asyncio 装饰器。
