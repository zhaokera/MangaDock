# 后端生命周期层重构设计文档

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 API、启动行为和 `server.py` 导出兼容性的前提下，将浏览器清理调度与应用生命周期实现从 [`server.py`](/Users/zhaok/Desktop/MangaDock/server.py) 提取到独立模块，进一步收窄入口文件职责。

**Architecture:** 新增独立的生命周期模块承接浏览器清理调度与 `startup` / `shutdown` 逻辑；`server.py` 继续持有运行时状态和基础资源，并通过工厂函数拿回同名兼容导出；应用装配链继续复用现有 bootstrap 和 app factory。

**Tech Stack:**
- Python 3
- FastAPI
- 现有 `services/browser_pool.py`
- 现有 `services/bootstrap.py`
- pytest

---

## 背景与问题

第一阶段已经把项目级应用装配从 [`server.py`](/Users/zhaok/Desktop/MangaDock/server.py) 中抽到 [`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py)，但 `server.py` 仍然同时承担以下职责：

- 创建和暴露 runtime 及兼容别名
- 持有浏览器池相关基础资源
- 实现浏览器池清理调度启动与停止
- 实现应用 `startup` / `shutdown` 生命周期逻辑
- 暴露 `create_app()`、模块级 `app`
- 持有配置热重载和 CLI 启动入口

在当前阶段，最适合继续收窄的不是 CLI 或配置热重载，而是生命周期实现层：

- 这部分逻辑已经和应用装配层一样，属于“项目级拼装”
- 它依赖显式资源，可以自然做成独立工厂
- 迁移后能继续减轻入口文件复杂度，但不会扩大成更高风险的启动层重构

## 用户确认过的设计决策

- 第二阶段继续优化 `server.py`，优先拆启动层而不是收紧 bootstrap 类型
- 本轮只拆生命周期函数和浏览器清理调度
- 不碰配置热重载逻辑
- 不碰 CLI 启动入口
- 继续保留 `server.py` 中现有同名生命周期函数可直接 import：
  - `start_browser_cleanup_scheduler`
  - `stop_browser_cleanup_scheduler`
  - `on_startup`
  - `on_shutdown`
- 采用“新增 `services/lifecycle.py` 并由 `server.py` 重新导出兼容函数”的方案

## 重构目标

本次重构完成后，需要满足以下结果：

- [`server.py`](/Users/zhaok/Desktop/MangaDock/server.py) 不再直接承载浏览器清理调度与生命周期实现细节
- 项目级生命周期逻辑有独立文件承接，便于后续继续拆配置监听或启动入口
- 对外行为不变，包括清理调度启动时机、关闭顺序、日志行为和 `server.py` 的兼容函数名
- 现有应用装配链继续工作，不引入新的生命周期注册方式

## 模块边界设计

### `server.py` 保留职责

`server.py` 在本轮重构后继续保留以下职责：

- 创建和暴露 `runtime`
- 暴露模块级兼容别名
- 初始化数据库和下载目录
- 调用生命周期工厂并在模块级暴露兼容函数
- 定义 `create_app()`、模块级 `app`
- 保留配置热重载和 CLI 启动入口

换句话说，`server.py` 仍然是兼容入口和资源持有者，但不再直接实现生命周期逻辑。

### 新生命周期模块职责

新增独立模块，建议路径为 [`services/lifecycle.py`](/Users/zhaok/Desktop/MangaDock/services/lifecycle.py)。

该模块负责：

- 构造 `start_browser_cleanup_scheduler`
- 构造 `stop_browser_cleanup_scheduler`
- 构造 `on_startup`
- 构造 `on_shutdown`

它应通过显式依赖注入接收运行时状态、browser pool 相关对象、调度函数、关闭函数、配置函数和 logger，而不是从 `server.py` 或全局模块中隐式读取状态。

### `services/bootstrap.py` 保留职责

[`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py) 继续只负责应用装配和 router 绑定。

本轮不把生命周期工厂继续塞进 bootstrap，避免让 bootstrap 从“装配模块”膨胀成“完整启动层”。

## 兼容性要求

### `server.py` 导出兼容

以下函数名在本次之后应继续可以通过 `from server import ...` 方式访问：

- `start_browser_cleanup_scheduler`
- `stop_browser_cleanup_scheduler`
- `on_startup`
- `on_shutdown`

它们可以来自生命周期模块工厂返回的闭包，但在 `server.py` 中应继续以同名对象暴露。

### 行为兼容

以下行为必须保持不变：

- `on_startup()` 继续启动浏览器池清理调度
- `on_shutdown()` 继续先关闭浏览器池，再停止清理调度
- 浏览器池清理调度的 interval 继续从 `config.get_config().crawler.browser_cleanup_interval` 读取，默认值仍为 `60`
- 启动日志内容和调用时机保持等价
- 生命周期函数继续通过现有应用装配链挂到 FastAPI

### 初始化与资源所有权兼容

以下原则不变：

- `runtime` 仍在 `server.py` 中创建
- browser pool 及其 lock 仍由 `server.py` 持有并暴露兼容别名
- 生命周期模块只消费这些资源，不接管它们的所有权

## 具体实现设计

### 生命周期工厂输入

新模块中的工厂至少需要显式接收：

- `runtime`
- `browser_pool`
- `browser_pool_lock`
- `cleanup_browser_pool`
- `close_all_browsers`
- `schedule_browser_cleanup`
- `get_config`
- `logger`

如果实现中需要保持与现有 `server.py` 相同的调用形式，也可以将 `browser_pool` 和 `browser_pool_lock` 直接从 `runtime` 读取，但这应是显式、可读的，不应隐式耦合外部全局变量。

### 生命周期工厂输出

模块应提供一组清晰的工厂函数，例如：

- `create_browser_cleanup_scheduler(...)`
- `create_app_lifecycle(...)`

或单一组合工厂，例如：

- `create_server_lifecycle(...)`

关键要求不是名字，而是返回值需要让 `server.py` 可以直接拿回 4 个同名兼容函数并绑定到模块级变量。

### `server.py` 调整方式

`server.py` 中当前的生命周期实现将被替换成：

- 导入生命周期工厂
- 用现有 `runtime`、browser pool、config、logger 等资源构造生命周期函数
- 将返回的函数绑定为：
  - `start_browser_cleanup_scheduler`
  - `stop_browser_cleanup_scheduler`
  - `on_startup`
  - `on_shutdown`

这样既能继续从 `server.py` 导入这些名字，也能把实现细节移出入口文件。

## 错误与风险控制

本次重构的主要风险不是业务逻辑，而是生命周期顺序和资源引用关系变化。

需要重点防止：

- `shutdown` 顺序改变，导致先取消调度器再关闭浏览器池
- 生命周期闭包错误引用了旧对象或错误的 lock
- `runtime.browser_cleanup_task` 的读写位置变化导致取消逻辑失效
- `create_app()` 仍然引用旧的生命周期函数或未正确挂载新函数

因此本次实现应优先保持调用顺序与参数传递一一对应，不追求更激进的抽象。

## 验证要求

### 自动化验证

至少需要覆盖以下验证：

- 现有 [`test/unit/test_app_factory.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_app_factory.py) 继续通过，证明 `server.create_app()` 和兼容导出入口不回归
- 现有 [`test/unit/test_runtime_state.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_runtime_state.py) 继续通过，证明 runtime 导出不受影响
- 新增生命周期模块单测，覆盖：
  - `start_browser_cleanup_scheduler` 会创建并记录 `runtime.browser_cleanup_task`
  - `stop_browser_cleanup_scheduler` 会取消并清空该任务
  - `on_shutdown` 的调用顺序仍为“先关闭浏览器池，再停止清理调度”

### 手工检查

至少需要做以下检查：

- `server.py` 明显减少生命周期实现细节
- `services/lifecycle.py` 只承担生命周期和调度逻辑，不开始承载配置热重载或 CLI
- `server.py` 仍然对外暴露同名生命周期函数

## 实施边界

### 本次范围内

- 新增独立生命周期模块
- 迁移浏览器清理调度和 `startup` / `shutdown` 实现
- 保留 `server.py` 同名兼容导出
- 增加最小必要测试覆盖生命周期模块

### 本次范围外

- 配置热重载重构
- CLI 启动入口重构
- runtime 模型重构
- bootstrap 类型系统收紧
- crawler 层重构

## 完成标准

当以下条件同时满足时，本次设计视为完成：

- 生命周期与浏览器清理调度实现已被提取到独立模块
- `server.py` 继续暴露原有同名生命周期函数
- 生命周期顺序与运行行为保持不变
- 相关单测通过，且未扩大成配置或 CLI 重构
