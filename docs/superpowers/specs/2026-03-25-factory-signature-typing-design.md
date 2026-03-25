# 工厂函数公开签名类型补强设计文档

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变运行行为、模块结构和导出方式的前提下，为 [`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py) 与 [`services/lifecycle.py`](/Users/zhaok/Desktop/MangaDock/services/lifecycle.py) 的公开工厂函数补充清晰的参数与返回值类型，降低误接线风险并提升可读性。

**Architecture:** 保持现有模块边界与调用链不变，仅在原文件内为公开工厂函数补充更明确的类型签名；必要时在同文件中添加最小数量的类型别名或 tuple 返回类型，避免类型定义扩散到其他模块。

**Tech Stack:**
- Python 3
- FastAPI
- 现有 `services/bootstrap.py`
- 现有 `services/lifecycle.py`
- pytest

---

## 背景与问题

当前后端已经完成两轮结构收敛：

- [`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py) 承接了应用装配与 router 绑定
- [`services/lifecycle.py`](/Users/zhaok/Desktop/MangaDock/services/lifecycle.py) 承接了生命周期与浏览器清理调度

这两个模块的职责已经变得清晰，但公开工厂函数的类型签名仍然偏宽：

- `Any` 与 `Callable[..., Any]` 过多
- 调用方不容易从签名直接看出依赖形状
- 返回值虽然稳定，但没有被完整表达成公开契约
- 后续如果参数接错对象，阅读层面不容易提前发现

本轮目标不是继续改结构，而是在当前稳定结构上，把公开接口表达清楚。

## 用户确认过的设计决策

- 本轮优先做“工厂函数公开签名类型补强”
- 优先范围锁定在：
  - [`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py)
  - [`services/lifecycle.py`](/Users/zhaok/Desktop/MangaDock/services/lifecycle.py)
- 只补公开工厂函数的清晰类型
- 不顺手做命名整理
- 不新增独立类型模块
- 不扩散到大范围 Protocol 或全链路类型化
- 不改变运行行为、调用顺序、返回值语义与导出方式

## 重构目标

本次补强完成后，需要满足以下结果：

- 两个公开工厂函数的参数签名明显更可读
- 两个公开工厂函数的返回值契约被明确表达
- 仍然不引入新的结构层或辅助文件
- 现有测试继续通过，证明本轮只有类型表达上的收敛，没有行为变化

## 模块边界设计

### `services/bootstrap.py`

本轮只处理其公开入口：

- `create_server_application(...)`

要求：

- 不调整其内部装配流程
- 不拆内部私有闭包
- 不把内部全部 helper 继续抽成额外类型系统
- 只把“公开函数要什么、返回什么”表达清楚

### `services/lifecycle.py`

本轮只处理其公开入口：

- `create_server_lifecycle(...)`

要求：

- 明确返回值是 4 个生命周期函数的 tuple
- 让调用方能直接看懂它依赖哪些资源
- 不重写内部实现，不改变关闭顺序或日志行为

## 具体实现设计

### 允许的类型工具

本轮只允许在原文件内部使用以下轻量手段：

- `TypeAlias`
- 更具体的 `Callable[[...], ...]`
- tuple 返回类型
- 必要时极少量的局部类型别名

不建议、不需要：

- 新建 `types.py`
- 新建共享 `Protocol` 模块
- 把整个依赖图完整抽象成类型系统

### `services/bootstrap.py` 目标形态

[`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py) 中的 `create_server_application(...)` 应至少明确：

- 返回值为 `FastAPI`
- 关键依赖的 callable 形状
- 与 runtime、路径、logger、配置函数相关的参数类别

允许继续对复杂或历史包袱较重的对象保留有限的 `Any`，但不应维持整片“所有东西都 Any”的状态。

### `services/lifecycle.py` 目标形态

[`services/lifecycle.py`](/Users/zhaok/Desktop/MangaDock/services/lifecycle.py) 中的 `create_server_lifecycle(...)` 应明确：

- 接收的 runtime / browser pool / lock / 配置函数 / logger / async 回调类别
- 返回值是：
  - `start_browser_cleanup_scheduler`
  - `stop_browser_cleanup_scheduler`
  - `on_startup`
  - `on_shutdown`

推荐将返回值表达为明确的 tuple 类型别名，例如生命周期函数 tuple，而不是让调用方靠实现猜测。

## 兼容性要求

### 行为兼容

以下行为必须保持不变：

- `create_server_application(...)` 的装配结果不变
- `create_server_lifecycle(...)` 的生命周期顺序、日志行为和任务管理语义不变
- `server.py` 的现有调用方式保持不变

### 结构兼容

以下结构不应发生变化：

- 文件路径不变
- 公开函数名不变
- 调用方 import 路径不变
- 不新增独立类型文件

## 风险与控制

本轮最主要的风险不是功能回归，而是“看起来只是类型改动，实际上顺手改了行为”。

需要重点防止：

- 为了让类型更好看而改变参数顺序
- 为了减少 `Any` 而错误收窄 callable 形状
- 为了表达 tuple 返回值而改动返回顺序
- 在类型补强过程中顺手重构私有闭包

因此本轮应坚持“只收接口，不动行为”。

## 验证要求

### 自动化验证

至少需要继续通过以下验证：

- [`test/unit/test_lifecycle.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_lifecycle.py)
- [`test/unit/test_bootstrap.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_bootstrap.py)
- [`test/unit/test_app_factory.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_app_factory.py)
- [`test/unit/test_runtime_state.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_runtime_state.py)

本轮默认不新增行为测试；如果测试有改动，应只服务于签名可读性或兼容性验证，而不扩大测试范围。

### 手工检查

至少需要做以下检查：

- 两个工厂函数的签名相比之前更容易阅读
- 返回值契约一眼可见
- 没有引入新的文件或新的类型层
- 内部实现逻辑没有被借机重写

## 实施边界

### 本次范围内

- 补强 [`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py) 公开工厂函数类型
- 补强 [`services/lifecycle.py`](/Users/zhaok/Desktop/MangaDock/services/lifecycle.py) 公开工厂函数类型
- 保持行为与模块边界不变

### 本次范围外

- Protocol 抽象扩散
- 新增共享类型模块
- bootstrap / lifecycle 内部结构调整
- `server.py` 再次重构
- 配置热重载重构
- CLI 重构

## 完成标准

当以下条件同时满足时，本次设计视为完成：

- 两个公开工厂函数的参数和返回值类型明显更清晰
- 没有改变运行行为与模块结构
- 现有相关测试继续通过
- 没有把这轮工作扩张成更大的类型工程
