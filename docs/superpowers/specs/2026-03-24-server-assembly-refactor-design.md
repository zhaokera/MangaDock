# 后端入口装配层重构设计文档

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有 API、页面行为和外部 import 方式的前提下，将 [`server.py`](/Users/zhaok/Desktop/MangaDock/server.py) 中的应用装配代码提取到独立模块，降低入口文件职责并为后续后端结构优化打基础。

**Architecture:** 保留 `server.py` 作为兼容入口和运行时状态持有者；新增独立装配模块承接依赖绑定和 router factory 组装；继续复用 [`services/app_factory.py`](/Users/zhaok/Desktop/MangaDock/services/app_factory.py) 的通用 FastAPI 注册逻辑。

**Tech Stack:**
- Python 3
- FastAPI
- 现有 `routes/*` 路由工厂
- 现有 `services/app_factory.py`
- pytest

---

## 背景与问题

最近几次提交已经把运行时状态模型和应用工厂从 [`server.py`](/Users/zhaok/Desktop/MangaDock/server.py) 中抽出一部分，但该文件仍然同时承担以下职责：

- 初始化全局运行时状态和兼容别名
- 提供 crawler、searcher、auth、resume 等依赖适配函数
- 构造各个 router factory
- 组装 FastAPI 应用
- 承担生命周期和 CLI 启动入口

这会带来几个直接问题：

- 入口文件职责过多，继续加后端能力时容易重新膨胀
- 应用“怎么装起来”的逻辑和“启动时做什么”的逻辑混在一起，不利于定位问题
- 后续如果继续拆生命周期、配置监听或运行时依赖，缺少明确落点
- 即使不改业务行为，简单的结构调整也需要频繁修改单个重文件，回归风险上升

本次目标不是继续做大范围后端重构，而是先把“应用装配”从入口文件中分离出来。

## 用户确认过的设计决策

- 当前阶段优先解决“后端装配和服务边界”问题
- 本轮只做内部重构，不改现有 API 和页面行为
- 第一阶段只拆 `server.py` 的装配代码
- 保留现有全局状态模式，不引入新的运行时模型
- 保留 `server.py` 现有模块级 import 兼容，尤其是 `app`、`create_app`、`runtime`、`AppRuntime`、`create_runtime`
- 采用“提取独立装配模块”的方案，而不是仅做更小的路由搬迁或更激进的 `AppContext` 重构

## 重构目标

本次重构完成后，需要满足以下结果：

- [`server.py`](/Users/zhaok/Desktop/MangaDock/server.py) 不再直接承载 router factory 和项目级依赖绑定细节
- 项目级应用装配有独立文件承接，方便后续继续拆生命周期或依赖图
- 对外行为不变，包括 API 路径、请求响应结构、启动方式和现有 import 入口
- 现有测试仍能通过兼容入口验证应用创建成功

## 模块边界设计

### `server.py` 保留职责

`server.py` 在本轮重构后继续保留以下职责：

- 创建和暴露 `runtime`
- 暴露兼容别名，例如 `tasks`、`task_last_sse_state`、`_browser_pool`
- 初始化数据库和下载目录
- 定义生命周期逻辑
- 定义 `create_app()`、模块级 `app`
- 保留 CLI 启动入口和启动日志

换句话说，`server.py` 仍是运行入口，但不再直接负责“把每一个 router 和依赖如何拼起来”。

### 新装配模块职责

新增独立装配模块，建议路径为 [`services/bootstrap.py`](/Users/zhaok/Desktop/MangaDock/services/bootstrap.py)。

该模块负责两层内容：

1. 依赖绑定层
- 接收 `runtime`、数据库访问函数、配置函数、logger、下载目录以及各类 crawler/search/auth/resume 提供者
- 构建各个 router factory 需要的闭包与适配函数

2. 应用装配层
- 基于上一步得到的已绑定依赖，调用 [`services/app_factory.py`](/Users/zhaok/Desktop/MangaDock/services/app_factory.py) 的 `create_application(...)`
- 返回最终的 FastAPI 应用实例

这个模块是项目级装配层，不承担业务实现，也不替代现有通用 `app_factory`。

### `services/app_factory.py` 保留职责

[`services/app_factory.py`](/Users/zhaok/Desktop/MangaDock/services/app_factory.py) 继续只负责通用的 FastAPI 组装行为：

- 注册根路由
- 注册 router
- 注册生命周期事件
- 创建 `FastAPI` 实例并配置中间件

它不应开始感知项目级 runtime、crawler 或数据库函数，否则只是把耦合从 `server.py` 转移到另一个通用模块。

## 迁移范围

以下内容属于本次迁移范围：

- `_get_crawler_for_url()`
- `_get_searcher_for_platform()`
- `_search_all_platforms()`
- `_get_manga_searcher_for_platform()`
- `_get_auth_manager_instance()`
- `_get_resume_manager_instance()`
- `_get_crawler_by_platform_name()`
- `_bind_crawler_browser()`
- `_release_platform_browser()`
- `_add_history_record()`
- `_build_downloader()`
- `_build_download_router()`
- `_build_history_router()`
- `_build_queue_router()`
- `_build_search_router()`
- `_build_parse_router()`
- `_build_auth_router()`
- `_build_resume_router()`
- `create_app()` 内部的应用装配参数准备

以下内容不属于本次迁移范围：

- `runtime` 结构调整
- 生命周期逻辑拆分
- 配置热重载逻辑重构
- CLI 参数逻辑重构
- 路由行为、请求参数、响应字段调整
- crawler 层大文件治理

## 兼容性要求

### 模块级 import 兼容

外部代码如果当前通过 `from server import ...` 访问以下对象，本次之后应继续可用：

- `app`
- `create_app`
- `runtime`
- `AppRuntime`
- `create_runtime`

如果有其他测试或调用方直接 import `tasks`、`task_last_sse_state` 等兼容别名，本次也不应主动破坏。

### API 兼容

以下行为必须保持不变：

- 所有已存在 API 路径
- 各 API 的请求体、查询参数和响应结构
- 已有下载、搜索、历史、解析、认证、恢复下载等路由注册结果
- 根路由 `/`

### 初始化时序兼容

以下顺序不应变化：

- 创建 runtime
- 初始化模块级兼容别名
- 调用 `init_db()`
- 创建下载目录
- 创建 `app`

保持时序稳定的原因是：现有代码和测试可能隐含依赖这些对象在 import `server` 时已经准备完成。

## 具体实现设计

### 装配模块输入

新模块应以显式参数接收当前装配所需资源，而不是再次从全局模块中偷偷读取。这些输入至少包括：

- `runtime`
- `downloads_dir`
- `logger`
- `get_config`
- `platforms_router`
- `get_crawler`
- `get_searcher`
- `search_all_platforms`
- `get_manga_searcher`
- `get_auth_manager`
- `get_resume_manager`
- `get_crawler_by_platform`
- 数据库存取函数，如 `get_task`、`save_task`、`delete_task`、`delete_history_tasks`、`get_history_tasks`、`get_total_count`
- 浏览器池服务函数，如 `init_browser_for_crawler`、`release_browser_for_platform`
- 历史记录写入辅助，如 `add_history_item`

显式传参的目的是让模块职责清晰、单测更容易写，也避免以后继续把隐藏依赖堆回去。

### 装配模块输出

新模块至少提供一个应用构建入口，例如：

- `create_server_application(...)`

必要时可以在模块内部保留私有辅助函数，但不需要引入新的公开运行时对象。

### `server.py` 调整方式

`server.py` 中的 `create_app()` 将改成薄封装：

- 准备现有全局状态和基础对象
- 把所需依赖传给新装配模块
- 返回构建好的 `FastAPI` 应用

这样既保留了外部兼容入口，也让“应用如何装配”的细节脱离入口文件。

## 错误与风险控制

本次重构的主要风险不在业务逻辑，而在“漏传依赖”或“装配顺序变化”。

需要重点防止：

- 某个 router factory 参数绑定不完整，导致启动后才暴露错误
- 历史记录或浏览器池相关闭包因作用域变化而引用错误对象
- `create_app()` 返回的路由集合与重构前不一致
- import `server` 时的初始化副作用被意外改变

因此本次实现不追求“最漂亮的抽象”，而是优先采用显式参数和薄封装，减少隐式行为。

## 验证要求

### 自动化验证

至少需要覆盖以下验证：

- 现有 [`test_app_factory.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_app_factory.py) 继续通过，证明 `server.create_app()` 兼容入口仍然注册核心路由
- 现有 [`test_runtime_state.py`](/Users/zhaok/Desktop/MangaDock/test/unit/test_runtime_state.py) 继续通过，证明运行时状态导出不受影响
- 新增或调整一个针对装配模块的单测，确认其返回的应用包含预期核心路由

### 手工检查

至少需要做以下检查：

- `server.py` 文件职责明显收窄，不再直接定义各 router factory 的构建细节
- 新装配模块中不存在对业务实现层的额外职责扩张
- 代码阅读者可以从模块命名上直接理解“这里是应用装配层”

## 实施边界

### 本次范围内

- 新增独立装配模块
- 迁移 `server.py` 中的依赖绑定和 router factory 组装代码
- 保持 `create_app()` 和模块级 `app` 兼容
- 补充最小必要测试覆盖装配层

### 本次范围外

- 生命周期重构
- 运行时状态模型重构
- 配置系统重构
- crawler 层重构
- 前端结构优化

## 完成标准

当以下条件同时满足时，本次设计视为完成：

- `server.py` 中的应用装配代码已被提取到独立模块
- 对外 API 和模块级 import 兼容保持不变
- 核心应用创建与运行时状态测试通过
- 没有顺手扩大成运行时模型或生命周期重构
