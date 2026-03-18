#!/usr/bin/env python3
"""
漫画下载 Web 服务
FastAPI 后端 + SSE 进度推送
支持多平台漫画下载
"""

import asyncio
import json
import os
import re
import zipfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, StreamingResponse
    from pydantic import BaseModel
except ImportError:
    print("请先安装 fastapi: pip install fastapi uvicorn")
    exit(1)

# 导入爬虫模块
from crawlers import get_crawler, get_supported_platforms, BaseCrawler
from crawlers.base import MangaInfo as CrawlerMangaInfo, DownloadProgress

# 导入配置管理
import config

# 加载配置
CONFIG = config.get_config()


# ============== 数据模型 ==============

class DownloadRequest(BaseModel):
    url: str


class PlatformInfo(BaseModel):
    name: str
    display_name: str
    patterns: list[str]


class MangaInfoResponse(BaseModel):
    platform: str
    comic_id: str = ""
    episode_id: str = ""
    title: str = ""
    chapter: str = ""
    page_count: int = 0


class DownloadTask:
    def __init__(self, task_id: str, url: str, platform: str = ""):
        self.task_id = task_id
        self.url = url
        self.platform = platform
        self.status: str = "pending"  # pending, downloading, completed, failed
        self.progress: int = 0
        self.total: int = 0
        self.message: str = ""
        self.manga_info: Optional[dict] = None
        self.output_path: Optional[str] = None
        self.zip_path: Optional[str] = None
        self.error: Optional[str] = None
        self.created_at: datetime = datetime.now()


# ============== 全局状态 ==============

app = FastAPI(title="漫画下载器", description="支持多平台的漫画下载服务")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任务存储
tasks: dict[str, DownloadTask] = {}
download_history: list[dict] = []

# SSE 连接管理 - 存储每个任务的最后发送状态
task_last_sse_state: dict[str, dict] = {}

# 全局状态锁 - 保护并发访问
_state_lock = asyncio.Lock()

# 下载目录（从配置获取）
DOWNLOADS_DIR = Path(CONFIG.download.output_dir)
DOWNLOADS_DIR.mkdir(exist_ok=True)

# 历史记录文件
HISTORY_FILE = DOWNLOADS_DIR / "history.json"


def load_history() -> list[dict]:
    """从文件加载历史记录"""
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"加载历史记录失败: {e}")
    return []


def save_history(history: list[dict]) -> None:
    """保存历史记录到文件（同步版本，用于线程池执行）"""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"保存历史记录失败: {e}")


async def save_history_async(history: list[dict]) -> None:
    """保存历史记录到文件（异步版本，使用线程池）"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_history, history)


async def add_history_item(history_item: dict) -> bool:
    """
    添加历史记录项（线程安全）

    Returns:
        bool: 是否成功添加（False 表示已存在）
    """
    async with _state_lock:
        if any(h.get("task_id") == history_item["task_id"] for h in download_history):
            return False
        download_history.append(history_item)
        await save_history_async(download_history)  # 异步保存

        # 限制历史记录数量
        history_config = config.get_config().history
        if history_config.max_items and len(download_history) > history_config.max_items:
            download_history[:] = download_history[-history_config.max_items:]
            await save_history_async(download_history)  # 异步保存
        return True


def cleanup_old_history():
    """清理过期的历史记录"""
    try:
        history_config = CONFIG.history
        if history_config.auto_cleanup_days > 0:
            cutoff_date = datetime.now() - timedelta(days=history_config.auto_cleanup_days)
            global download_history
            download_history = [h for h in download_history if datetime.fromisoformat(h.get('created_at', datetime.now().isoformat())) > cutoff_date]
            save_history(download_history)
    except Exception as e:
        print(f"清理历史记录失败: {e}")


# 加载历史记录
download_history = load_history()


# ============== 下载器 ==============

class MangaDownloader:
    """漫画下载器 - 使用爬虫注册表"""

    def __init__(self, task: DownloadTask):
        self.task = task
        self.crawler: Optional[BaseCrawler] = None

    def _cleanup_task(self):
        """清理任务相关的资源"""
        tasks.pop(self.task.task_id, None)
        task_last_sse_state.pop(self.task.task_id, None)

    async def run(self):
        """执行下载"""
        try:
            # 根据 URL 获取爬虫
            self.crawler = get_crawler(self.task.url)
            self.task.platform = self.crawler.PLATFORM_NAME

            await self._do_download()
        except ValueError as e:
            self.task.status = "failed"
            self.task.error = str(e)
            self.task.message = f"错误: {e}"
        except Exception as e:
            self.task.status = "failed"
            self.task.error = str(e)
            self.task.message = f"下载失败: {e}"
            import traceback
            traceback.print_exc()
        finally:
            # 任务完成或失败后清理 tasks 字典和 SSE 状态
            self._cleanup_task()

    def _update_manga_info(self):
        """更新漫画信息（合并重复逻辑）"""
        if self.crawler and hasattr(self.crawler, 'manga_info'):
            info = self.crawler.manga_info
            if info:
                self.task.manga_info = info.to_dict()
        elif self.crawler and hasattr(self.crawler, '_manga_info'):
            info = self.crawler._manga_info
            if info:
                self.task.manga_info = info.to_dict()

    async def _do_download(self):
        """执行下载"""
        url = self.task.url

        self.task.message = "解析漫画信息..."
        self.task.status = "downloading"

        # 获取漫画信息
        try:
            info = await self.crawler.get_info(url)
            self.task.manga_info = info.to_dict()
            self.task.platform = info.platform
        except Exception as e:
            # 如果获取信息失败，继续尝试下载
            pass

        # 定义进度回调
        def on_progress(progress: DownloadProgress):
            self.task.progress = progress.current
            self.task.total = progress.total
            self.task.message = progress.message
            if progress.status:
                self.task.status = progress.status

        # 执行下载
        output_path = await self.crawler.download(
            url,
            str(DOWNLOADS_DIR),
            progress_callback=on_progress
        )

        self.task.output_path = output_path

        # 更新漫画信息（合并逻辑）
        self._update_manga_info()

        # 打包 zip（使用线程池异步执行）
        self.task.message = "正在打包..."
        if output_path and Path(output_path).exists():
            save_dir = Path(output_path)
            zip_name = save_dir.name
            zip_path = DOWNLOADS_DIR / f"{zip_name}.zip"

            # 异步打包
            loop = asyncio.get_event_loop()
            def zip_folder_sync():
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for file in sorted(save_dir.iterdir()):
                        if file.is_file():
                            zf.write(file, file.name)
            await loop.run_in_executor(None, zip_folder_sync)

            self.task.zip_path = str(zip_path)

        self.task.status = "completed"
        self.task.message = f"下载完成! 共 {self.task.total} 张图片"

        # 添加到历史（使用线程安全的方法）
        if self.task.manga_info:
            history_item = {
                "task_id": self.task.task_id,
                "title": self.task.manga_info.get("title", "未知漫画"),
                "chapter": self.task.manga_info.get("chapter", ""),
                "platform": self.task.platform,
                "zip_path": self.task.zip_path,
                "page_count": self.task.total,
                "created_at": self.task.created_at.isoformat()
            }
            await add_history_item(history_item)


# ============== API 端点 ==============

@app.get("/")
async def root():
    return {
        "message": "漫画下载器 API",
        "version": "2.0",
        "description": "支持多平台漫画下载"
    }


@app.get("/api/platforms")
async def list_platforms():
    """获取支持的平台列表"""
    platforms = get_supported_platforms()
    return {"platforms": platforms}


@app.post("/api/parse")
async def parse_url(request: DownloadRequest):
    """解析 URL 返回平台和漫画信息"""
    url = request.url

    try:
        crawler = get_crawler(url)
        info = await crawler.get_info(url)

        return {
            "platform": crawler.PLATFORM_NAME,
            "platform_name": crawler.PLATFORM_DISPLAY_NAME,
            "comic_id": info.comic_id,
            "episode_id": info.episode_id,
            "url": url
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {e}")


@app.post("/api/download")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """启动下载任务"""
    url = request.url

    # 验证 URL 并获取爬虫
    try:
        crawler = get_crawler(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 创建任务
    task_id = str(uuid.uuid4())[:8]
    task = DownloadTask(task_id, url, platform=crawler.PLATFORM_NAME)
    tasks[task_id] = task

    # 后台执行下载
    downloader = MangaDownloader(task)
    background_tasks.add_task(downloader.run)

    return {
        "task_id": task_id,
        "status": "pending",
        "platform": crawler.PLATFORM_NAME,
        "message": "任务已创建"
    }


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """获取任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "total": task.total,
        "message": task.message,
        "platform": task.platform,
        "manga_info": task.manga_info,
        "zip_path": task.zip_path,
        "error": task.error
    }


@app.get("/api/progress/{task_id}")
async def stream_progress(task_id: str):
    """SSE 进度推送 - 优化版，仅在重要状态变化时发送"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 只读取一次配置，避免每次循环都读取
    sse_config = config.get_config().sse
    heartbeat_interval = max(0.5, sse_config.heartbeat_interval)

    async def event_generator():
        task = tasks[task_id]

        # 发送初始化状态
        last_state = task_last_sse_state.get(task_id, {})

        # 检查是否是重要变化（模块级函数，便于测试）
        def is_important_change(current, last) -> bool:
            """判断是否是重要变化（过滤掉 message 的微小变化）"""
            # 状态变化是重要事件
            if current.get("status") != last.get("status"):
                return True
            # 错误变化是重要事件
            if current.get("error") != last.get("error"):
                return True
            # progress 变化超过 10% 或跨过重要里程碑
            if current.get("progress") != last.get("progress"):
                return True
            # total 变化（通常只在开始时）
            if current.get("total") != last.get("total"):
                return True
            # message 只在包含关键词时发送（避免下载中 1/50 这种频繁变化）
            msg_changed = current.get("message") != last.get("message")
            if msg_changed:
                important_keywords = ["检测到", "解码", "读取", "完成", "失败", "错误", "加载", "打包"]
                msg = current.get("message", "")
                return any(kw in msg for kw in important_keywords)
            return False

        # 立即发送当前状态
        yield f"data: {get_task_data(task)}\n\n"

        while True:
            # 检查任务状态
            current_state = {
                "status": task.status,
                "progress": task.progress,
                "total": task.total,
                "message": task.message,
                "error": task.error,
            }

            # 只有重要状态变化时才发送
            if is_important_change(current_state, last_state):
                yield f"data: {get_task_data(task)}\n\n"
                last_state = current_state.copy()
                task_last_sse_state[task_id] = last_state

            # 任务完成或失败，结束连接
            if task.status in ("completed", "failed"):
                task_last_sse_state.pop(task_id, None)
                break

            # 使用缓存的配置值，避免重复读取
            await asyncio.sleep(heartbeat_interval)

    def get_task_data(task):
        """获取任务数据的 JSON 字符串"""
        data = {
            "task_id": task.task_id,
            "status": task.status,
            "progress": task.progress,
            "total": task.total,
            "message": task.message,
            "platform": task.platform,
            "manga_info": task.manga_info,
            "zip_path": task.zip_path,
            "error": task.error
        }
        return json.dumps(data, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/files/{task_id}")
async def download_file(task_id: str):
    """下载打包文件"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not task.zip_path or not Path(task.zip_path).exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    filename = Path(task.zip_path).name
    return FileResponse(
        task.zip_path,
        media_type="application/zip",
        filename=filename
    )


@app.get("/api/history")
async def get_history():
    """获取下载历史"""
    history_config = config.get_config().history
    max_items = history_config.max_items if history_config.max_items > 0 else 100
    return {"history": download_history[-max_items:]}


# ============== 启动 ==============

if __name__ == "__main__":
    import uvicorn

    print("启动漫画下载服务...")
    print(f"API: http://{CONFIG.host}:{CONFIG.port}")
    print(f"文档: http://{CONFIG.host}:{CONFIG.port}/docs")

    # 显示支持的平台
    platforms = get_supported_platforms()
    print("\n支持的平台:")
    for p in platforms:
        print(f"  - {p['display_name']}")

    # 显示配置信息
    print(f"\n配置:")
    print(f"  - 下载目录: {CONFIG.download.output_dir}")
    print(f"  - 并发数: {CONFIG.download.concurrency}")
    print(f"  - 日志级别: {CONFIG.logging.level}")

    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port)
