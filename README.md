# MangaDock

多平台漫画下载器，支持漫画柜、快看漫画、B站漫画、搜狗漫画、番茄漫画、纱雾漫画、Owining 等平台。

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18+-blue.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.2+-blue.svg)](https://www.typescriptlang.org/)

</div>

## 功能特性

- 🌐 **多平台支持** - 漫画柜、快看漫画、B站漫画、搜狗漫画、番茄漫画、纱雾漫画、Owining
- 📥 **批量下载** - 支持单个或批量下载漫画章节
- 📦 **自动打包** - 下载完成后自动打包为 ZIP 文件
- 📊 **实时进度** - SSE 进度推送，实时查看下载状态
- 📝 **历史记录** - 数据库存储下载历史，支持分页查询
- 🔐 **断点续传** - 支持中断后继续下载
- ⚙️ **配置管理** - YAML + 环境变量配置，支持热重载
- 🎯 **并发下载** - 高效并发下载，自定义并发数
- 🔄 **自动重试** - 下载失败自动重试，支持指数退避

## 项目结构

```
├── server.py               # FastAPI 后端服务
├── config.py               # 配置管理模块
├── crawlers/               # 爬虫模块
│   ├── __init__.py         # 模块导出
│   ├── base.py             # 爬虫基类
│   ├── registry.py         # 爬虫注册表
│   ├── db.py               # 数据库操作
│   ├── auth.py             # 认证管理
│   ├── resume.py           # 断点续传
│   ├── manhuagui.py        # 漫画柜爬虫
│   ├── kuaikanmanhua.py    # 快看漫画爬虫
│   ├── bilibili.py         # B站漫画爬虫
│   ├── sogou.py            # 搜狗漫画爬虫
│   ├── tongjuemh.py        # 番茄漫画爬虫
│   ├── mh1234.py           # 纱雾漫画爬虫
│   └── owning.py           # Owining 漫画爬虫
├── web/                    # React 前端
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── downloads/              # 下载目录（自动创建）
└── sessions/               # 认证会话目录（自动创建）
```

## 环境要求

- Python 3.9+
- Node.js 18+
- Chrome 浏览器

## 快速开始

### 1. 克隆项目

```bash
git clone git@github.com:zhaokera/MangaDock.git
cd MangaDock
```

### 2. 安装依赖

**后端依赖**

```bash
# 安装 Python 依赖
pip install fastapi uvicorn httpx playwright pyyaml

# 安装 Playwright 浏览器（首次运行需要）
playwright install chromium
```

**前端依赖**

```bash
cd web
npm install
```

### 3. 配置（可选）

创建 `config.yaml` 文件（可选，默认使用配置项）：

```yaml
network:
  proxy: null
  timeout:
    connect: 30
    read: 60
    download: 300
  retry:
    max_attempts: 5
    initial_delay: 1.0
    max_delay: 10.0
    exponential_base: 2

download:
  concurrency: 5
  output_dir: downloads
  enable_zip: true

crawler:
  user_agent: "Mozilla/5.0..."
  browser_args:
    - "--no-sandbox"
    - "--disable-dev-shm-usage"
    - "--disable-gpu"
  browser_idle_timeout: 300
  browser_cleanup_interval: 60

server:
  host: "0.0.0.0"
  port: 8000
```

### 4. 启动服务

**启动后端服务**

```bash
python server.py
```

后端服务默认运行在 http://localhost:8000

**启动前端服务**

```bash
cd web
npm run dev
```

前端服务默认运行在 http://localhost:5173

## 支持的平台

| 平台 | 显示名称 | URL 格式 | 认证 |
|------|----------|----------|------|
| `manhuagui` | 漫画柜 | `https://www.manhuagui.com/comic/*/`*.html` | 可选 |
| `kuaikanmanhua` | 快看漫画 | `https://www.kuaikanmanhua.com/comic/*/` | 可选 |
| `bilibili` | B站漫画 | `https://manga.bilibili.com/mc/*/` | 可选 |
| `sogou` | 搜狗漫画 | `https://mh.sogou.com/comic/*/` | 否 |
| `tongjuemh` | 番茄漫画 | `https://www.tongjuemh.com/comic/*/`*.html` | 否 |
| `mh1234` | 纱雾漫画 | `https://www.mh1234.com/comic/*/`*.html` | 否 |
| `owning` | Owining 漫画 | `https://www.owning.com/comic/*/` | 否 |

## API 接口

### 认证相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 平台登录 |
| `/api/auth/logout` | POST | 平台登出 |
| `/api/auth/status` | GET | 检查登录状态 |
| `/api/auth/platforms` | GET | 获取支持认证的平台列表 |

### 任务管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/platforms` | GET | 获取支持的平台列表 |
| `/api/parse` | POST | 解析 URL |
| `/api/download` | POST | 创建下载任务 |
| `/api/batch-download` | POST | 批量下载任务 |
| `/api/status/{task_id}` | GET | 查询任务状态 |
| `/api/progress/{task_id}` | GET | SSE 进度推送 |
| `/api/files/{task_id}` | GET | 下载 ZIP 文件 |

### 历史记录

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/history` | GET | 获取下载历史（支持分页） |

### 断点续传

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/resume/status/{task_id}` | GET | 查询断点续传状态 |
| `/api/resume/list` | GET | 列出所有断点记录 |
| `/api/resume/{task_id}` | DELETE | 删除断点记录 |
| `/api/resume/cleanup` | POST | 清理旧的断点记录 |

### 队列管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/queue` | GET | 获取下载队列 |
| `/api/queue/pause` | POST | 暂停下载任务 |
| `/api/queue/resume` | POST | 恢复下载任务 |
| `/api/queue/priority` | POST | 更新任务优先级 |
| `/api/queue/{task_id}` | DELETE | 从队列移除 |

API 文档: http://localhost:8000/docs

## 环境变量

所有配置均可通过环境变量覆盖：

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `PROXY_URL` | 代理地址 | `http://localhost:8080` |
| `REQUEST_TIMEOUT` | 请求超时（秒） | `60` |
| `DOWNLOAD_TIMEOUT` | 下载超时（秒） | `300` |
| `CONNECT_TIMEOUT` | 连接超时（秒） | `30` |
| `CONCURRENT_DOWNLOADS` | 下载并发数 | `5` |
| `OUTPUT_DIR` | 输出目录 | `./downloads` |
| `ENABLE_ZIP` | 是否打包 ZIP | `true` |
| `MAX_CONCURRENT_IMAGES` | 单任务图片并发数 | `5` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `LOG_FILE` | 日志文件路径 | `downloads/log.txt` |
| `SSE_HEARTBEAT_INTERVAL` | SSE 心跳间隔 | `2` |
| `SSE_BUFFER_SIZE` | SSE 缓冲大小 | `100` |
| `BROWSER_IDLE_TIMEOUT` | 浏览器空闲超时 | `300` |
| `BROWSER_CLEANUP_INTERVAL` | 浏览器清理间隔 | `60` |
| `HOST` | 服务主机 | `0.0.0.0` |
| `PORT` | 服务端口 | `8000` |

## 技术栈

**后端**
- [FastAPI](https://fastapi.tiangolo.com/) - Python Web 框架
- [Playwright](https://playwright.dev/) - 浏览器自动化
- [httpx](https://www.python-httpx.org/) - 异步 HTTP 客户端
- [PyYAML](https://pyyaml.org/) - YAML 配置解析
- [SQLite](https://www.sqlite.org/) - 轻量级数据库

**前端**
- [React 18](https://react.dev/) - UI 框架
- [Vite](https://vitejs.dev/) - 构建工具
- [TypeScript](https://www.typescriptlang.org/) - 类型系统
- [Tailwind CSS](https://tailwindcss.com/) - CSS 框架
- [SSE](https://developer.mozilla.org/zh-CN/docs/Web/API/Server-sent_events) - 实时进度推送

## 使用方法

1. 打开浏览器访问 http://localhost:5173
2. 输入漫画章节链接（支持多平台）
3. 点击下载，等待进度完成
4. 下载完成后自动打包 ZIP 文件
5. 点击下载按钮获取ZIP文件

## 配置热重载

服务启动后，修改 `config.yaml` 文件会自动重新加载配置，无需重启服务。

## 浏览器池管理

系统会自动管理浏览器池：
- 每个平台最多保留 N 个浏览器实例
- 空闲超时（默认 5 分钟）后自动关闭
- 避免频繁创建/销毁浏览器实例

## 认证支持

部分平台需要登录后才能下载，支持cookie认证。

## License

MIT
