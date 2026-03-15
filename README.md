# MangaDock

多平台漫画下载器，支持漫画柜等平台。

## 功能特性

- 🎯 多平台支持（漫画柜）
- 📥 批量下载漫画章节
- 📦 自动打包 ZIP 文件
- 📊 实时下载进度显示
- 📝 下载历史记录

## 项目结构

```
├── server.py           # FastAPI 后端服务
├── crawlers/           # 爬虫模块
│   ├── base.py         # 爬虫基类
│   ├── manhuagui.py    # 漫画柜爬虫
│   └── registry.py     # 爬虫注册表
├── web/                # React 前端
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
└── downloads/          # 下载目录（自动创建）
```

## 环境要求

- Python 3.9+
- Node.js 18+
- Chrome 浏览器

## 运行状态

> 最后更新: 2026-03-15

| 服务 | 端口 | 进程 ID | 状态 |
|------|------|---------|------|
| 后端 (FastAPI) | 8000 | Python (PID: 3290) | ✅ 运行中 |
| 前端 (React/Vite) | 5173 | Node (PID: 76287) | ✅ 运行中 |

- 前端地址: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 快速开始

### 1. 克隆项目

```bash
git clone git@github.com:zhaokera/MangaDock.git
cd MangaDock
```

### 2. 后端启动

```bash
# 安装 Python 依赖
pip install fastapi uvicorn httpx playwright

# 安装 Playwright 浏览器（首次运行需要）
playwright install chromium

# 启动后端服务
python server.py
```

后端服务运行在 http://localhost:8000

API 文档: http://localhost:8000/docs

### 3. 前端启动

```bash
cd web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务运行在 http://localhost:5173

## 支持的平台

| 平台 | URL 格式 |
|------|----------|
| 漫画柜 | `https://www.manhuagui.com/comic/*/`*.html` |

## 使用方法

1. 打开浏览器访问 http://localhost:5173
2. 输入漫画章节链接
3. 点击下载，等待进度完成
4. 下载完成后自动打包 ZIP 文件

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/platforms` | GET | 获取支持的平台列表 |
| `/api/parse` | POST | 解析 URL |
| `/api/download` | POST | 创建下载任务 |
| `/api/status/{task_id}` | GET | 查询任务状态 |
| `/api/progress/{task_id}` | GET | SSE 进度推送 |
| `/api/files/{task_id}` | GET | 下载 ZIP 文件 |
| `/api/history` | GET | 获取下载历史 |

## 技术栈

**后端**
- FastAPI - Web 框架
- Playwright - 浏览器自动化
- httpx - HTTP 客户端

**前端**
- React 18
- Vite
- Tailwind CSS
- TypeScript

## License

MIT