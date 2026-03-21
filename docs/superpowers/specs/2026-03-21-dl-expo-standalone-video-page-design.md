# dl-expo 专站视频页设计文档

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `www.dl-expo.com` 增加一个独立的专站视频页 `/dl-expo`，支持站内搜索和专站视频下载，同时不污染现有 `/video` 通用视频页。

**Architecture:** 前端新增第三个页面入口 `/dl-expo`，页面只服务 `dl-expo.com`。后端新增 `dl_expo` 平台实现，包含 URL 匹配、专站搜索、播放页解析和视频下载。现有历史记录、下载进度和下载 API 继续复用，但通过 `platform=dl_expo` 与其他平台自然分流。

**Tech Stack:**
- React 18
- TypeScript
- Vite
- FastAPI
- 现有 crawler / searcher 注册体系
- Vitest + Testing Library
- pytest

---

## 背景与目标

当前系统已将漫画页和通用视频页拆开，但用户又提出一个新的使用场景：`dl-expo.com` 需要专门支持，而且不希望继续塞进 `/video` 通用页。

这个要求的重点不是单纯新增一个平台名，而是：

- 专站能力有独立入口，避免和腾讯、爱奇艺、优酷、芒果混在一起
- 专站搜索只搜索这个站，不进入通用视频聚合搜索
- 专站失败信息、帮助文案和下载路径都可以独立处理
- 后续如果这个站需要特殊提示、特殊解析或特殊交互，不会破坏现有视频页

本次设计采用“专站独立页”，不做通用 MacCMS 站点框架。

## 用户确认过的设计决策

- 新增独立页面 `/dl-expo`
- 页面是专站支持，不并入现有 `/video`
- 该页面同时支持“站内搜索”和“直接粘贴链接下载”
- 后端只为 `dl-expo.com` 增加专用支持，不顺手抽象成通用站点框架

## 当前站点事实

基于对 `https://www.dl-expo.com/` 的抓取，当前站点首页表现为一个 MacCMS 风格的视频站，具备以下特征：

- 首页标题和描述为视频站文案
- 存在站内搜索表单
- 搜索入口为 `/search/-------------.html`
- 内容详情页路径为 `/voddetail/{id}.html`
- 播放页路径为 `/play/{vod_id}/{source-index}-{episode-index}.html`

需要注意的是，这个站对不同访问方式存在不稳定响应：

- 某些路径的 `https` 抓取可能失败
- 某些 `play/search` 路径在命令行抓取时可能返回与首页不一致的内容

因此实现必须容忍“站点响应不稳定”，并给出明确错误而不是吞掉失败。

## 路由与导航

### 路由

- `/` 继续保持当前行为，不因本次改动改变默认落点
- `/manga` 保持漫画页
- `/video` 保持通用视频页
- `/dl-expo` 新增为 `dl-expo.com` 专站页

### 导航行为

- 顶部导航新增一个明确入口，例如 `糯米影视` 或 `dl-expo 专站`
- 当前导航项必须有激活态
- 从 `/video` 切到 `/dl-expo` 后，页面文案、平台提示、搜索范围和帮助说明全部切换为专站语义

## 页面结构

`/dl-expo` 页面推荐结构如下：

1. 专站 Hero
2. 站点说明卡
3. 专站搜索区
4. 专站搜索结果列表
5. 专站链接下载区
6. 专站下载进度
7. 专站下载历史

### Hero

- 明确说明这是 `dl-expo.com` 专站支持页
- 文案直接告诉用户支持“站内搜索”和“播放页链接下载”
- 不展示其他视频平台名称，避免误解为聚合搜索

### 站点说明卡

- 展示专站域名 `www.dl-expo.com`
- 给出支持的链接形态示例
- 明确指出此页只处理该站链接

### 搜索区

- 搜索只请求 `dl_expo` 专用搜索逻辑
- 结果列表只展示来自该站的结果
- 结果项点击后直接进入下载流程

### 链接下载区

- 支持粘贴 `dl-expo.com` 的播放页或详情页链接
- 若用户输入其他平台链接，应提示“当前是 dl-expo 专站页，请切换到对应页面”

### 下载进度与历史

- 继续复用现有下载进度和历史组件
- 仅显示 `platform=dl_expo` 的任务
- 空状态和失败状态改成专站语义

## 后端设计

### 新平台标识

- 新增平台名：`dl_expo`
- 平台显示名：`糯米影视`
- `/api/platforms` 返回里新增该平台，并标记为 `video`

### 新 crawler

新增 `crawlers/dl_expo.py`，负责：

- 匹配 `www.dl-expo.com`
- 识别播放页 URL，例如 `/play/{vod_id}/{source}-{episode}.html`
- 兼容可能的详情页 URL，例如 `/voddetail/{id}.html`
- 获取标题、当前分集、平台信息
- 从播放页提取真实播放地址

### 播放地址提取策略

第一版按以下顺序尝试：

1. 提取页面 HTML / 内嵌脚本中的直链 `mp4`
2. 提取 `m3u8`
3. 提取播放器配置中的 iframe / 二次播放器地址，再追一层真实地址

如果三层都失败：

- 返回明确错误：`未找到 dl-expo 播放地址`
- 错误保留在 `dl_expo` 平台语义下，不与其他视频站共用模糊文案

### 下载策略

- 若拿到 `mp4`，沿用现有 `httpx` 下载路径
- 若拿到 `m3u8`，第一版允许采用“明确失败 + 待后续支持”的保守策略，或者如果仓库里已有可复用能力则接入
- 本次设计不要求顺手重构整个视频下载基类

### 新 searcher

在现有 `crawlers/search.py` 体系中新增 `dl_expo` 搜索器，负责：

- 走该站自己的搜索入口
- 解析搜索结果标题、详情页链接或播放页链接
- 转成现有 `SearchResult` 结构
- `platform` 固定为 `dl_expo`
- `platform_display` 固定为 `糯米影视`

### 搜索结果 URL 归一化

优先输出可直接下载的播放页 URL；若搜索结果只有详情页：

- 先输出详情页 URL
- crawler 在下载阶段再解析默认播放源和首个分集

这样可以降低搜索器的站点耦合。

## 前端设计

### 新页面

新增 `web/src/pages/DlExpoPage.tsx`。

职责：

- 渲染专站 Hero 和帮助文案
- 调用专站搜索
- 处理结果点击后的下载启动
- 展示 `dl_expo` 专属下载进度
- 展示 `dl_expo` 专属历史

### 与现有组件的关系

优先复用现有组件，但通过参数把页面语义收紧：

- `SearchInput`
  - 允许复用视觉结构
  - 但不展示多平台筛选
  - 文案改为专站搜索
- `UrlInput`
  - 仅接受 `dl-expo.com` 链接
  - 错页输入时给出明确提示
- `DownloadProgress`
  - 过滤 `platform=dl_expo`
  - 空状态和标题改成专站文案
- `History`
  - 过滤 `platform=dl_expo`
  - 空状态改成专站文案

如果 `SearchInput` 现有多平台逻辑太重，本次允许创建轻量专用封装组件，而不是继续硬塞条件分支。

## 数据与状态设计

### 平台类型

- `dl_expo` 归类为 `video`
- 但不进入 `/video` 页内部的通用平台展示或通用平台筛选
- 它是“视频类型”中的“专站页特例”

### 当前任务状态

- 页面只订阅和展示 `platform=dl_expo` 的任务
- 任务启动后立即在前端显示 `pending` 状态，避免用户感觉按钮没反应

### 历史记录

- 继续走 `/api/history`
- 通过 `platform=dl_expo` 过滤
- 页面只展示该站历史

## 错误处理

### 错链接

- 在 `/dl-expo` 输入非 `dl-expo.com` 链接时，提示：
  - “当前是 dl-expo 专站页，请切换到对应平台页面”

### 搜索失败

- 若站内搜索入口不可用，提示：
  - “dl-expo 站内搜索暂时不可用”

### 下载失败

- 若无法解析真实播放地址，提示：
  - “未找到 dl-expo 播放地址”
- 若站点响应异常，提示：
  - “dl-expo 页面解析失败，请稍后重试”

## 实施边界

### 本次范围内

- 新增 `/dl-expo` 页面
- 顶部导航新增专站入口
- 后端新增 `dl_expo` crawler
- 后端新增 `dl_expo` searcher
- `/api/platforms` 暴露 `dl_expo`
- 前端专站搜索、专站下载、专站历史和进度过滤
- 对应前后端测试

### 本次范围外

- 抽象通用 MacCMS 站点框架
- 改造现有 `/video` 聚合搜索逻辑去支持站点分组
- 为所有同类站自动复用一套 crawler / searcher
- 完整支持所有 `m3u8` 播放清单变体

## 验证要求

### 手工验证

- 顶部导航可进入 `/dl-expo`
- 页面只显示 `dl-expo` 专站文案
- 搜索关键词能返回该站结果
- 点击搜索结果后，页面立即出现 `pending` 下载状态
- 粘贴 `dl-expo.com` 播放页链接可启动下载
- 粘贴其他平台链接会给出明确切页提示
- 历史与进度只显示 `dl_expo` 任务

### 自动化验证

后端至少覆盖：

- URL 匹配
- 搜索结果解析
- 播放地址提取
- `/api/platforms` 返回 `dl_expo`

前端至少覆盖：

- 导航可进入 `/dl-expo`
- 专站页不复用通用视频平台筛选
- 点击搜索结果后立即显示 `pending` 状态
- 历史与进度按 `dl_expo` 过滤
