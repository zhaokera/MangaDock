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
import logging
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
    logger.error("请先安装 fastapi: pip install fastapi uvicorn")
    exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# 导入爬虫模块
from crawlers import (
    get_crawler,
    get_supported_platforms,
    BaseCrawler,
    init_db,
    TaskRecord,
    get_task,
    save_task,
    delete_task,
    get_all_tasks,
    get_history_tasks,
    get_total_count,
    update_task_status,
    update_task_progress,
)
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

# 浏览器池 - 存储每个爬虫类型的浏览器实例
_browser_pool: dict[str, dict] = {}
_browser_pool_lock = asyncio.Lock()

# 初始化数据库
init_db()

# 下载目录（从配置获取）
DOWNLOADS_DIR = Path(CONFIG.download.output_dir)
DOWNLOADS_DIR.mkdir(exist_ok=True)


async def get_browser_for_platform(platform: str) -> dict:
    """
    获取指定平台的浏览器实例（从池中获取或创建新实例）

    Args:
        platform: 平台名称

    Returns:
        dict: 包含 browser, context, page 的字典
    """
    import config
    from playwright.async_api import async_playwright

    async with _browser_pool_lock:
        if platform in _browser_pool:
            return _browser_pool[platform]

        # 创建新的浏览器实例
        cfg = config.get_config()
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            channel="chrome",
            args=cfg.crawler.browser_args
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=cfg.crawler.user_agent or "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        browser_info = {
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
            "platform": platform,
            "used_count": 0
        }

        _browser_pool[platform] = browser_info
        logger.info(f"为平台 {platform} 创建新浏览器实例")
        return browser_info


async def release_browser_for_platform(platform: str):
    """
    释放指定平台的浏览器实例

    Args:
        platform: 平台名称
    """
    async with _browser_pool_lock:
        if platform in _browser_pool:
            browser_info = _browser_pool[platform]
            browser_info["used_count"] = max(0, browser_info["used_count"] - 1)

            # 如果使用次数为0且距离上次使用超过5分钟，关闭浏览器
            logger.debug(f"平台 {platform} 浏览器使用次数: {browser_info['used_count']}")

            if browser_info["used_count"] <= 0:
                try:
                    if browser_info["page"]:
                        await browser_info["page"].close()
                    if browser_info["context"]:
                        await browser_info["context"].close()
                    if browser_info["browser"]:
                        await browser_info["browser"].close()
                    if browser_info["playwright"]:
                        await browser_info["playwright"].stop()
                except Exception as e:
                    logger.error(f"释放平台 {platform} 浏览器失败: {e}")
                finally:
                    del _browser_pool[platform]
                    logger.info(f"平台 {platform} 浏览器已释放")


async def init_browser_for_crawler(crawler: BaseCrawler, platform: str):
    """
    初始化爬虫的浏览器实例（从池中获取）

    Args:
        crawler: 爬虫实例
        platform: 平台名称
    """
    browser_info = await get_browser_for_platform(platform)
    crawler.browser = browser_info["browser"]
    crawler.context = browser_info["context"]
    crawler.page = browser_info["page"]
    crawler.playwright = browser_info["playwright"]
    crawler.cfg = config.get_config()  # 设置配置
    browser_info["used_count"] += 1


async def cleanup_browser_pool():
    """清理浏览器池中长时间未使用的浏览器"""
    import time
    async with _browser_pool_lock:
        for platform, browser_info in list(_browser_pool.items()):
            if browser_info["used_count"] <= 0:
                # 标记为待清理
                browser_info["used_count"] = -1


def load_history() -> list[dict]:
    """从文件加载历史记录"""
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text(encoding='utf-8'))
    except Exception as e:
        logger.error(f"加载历史记录失败: {e}")
    return []


def save_history(history: list[dict]) -> None:
    """保存历史记录到文件（同步版本，用于线程池执行）"""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        logger.error(f"保存历史记录失败: {e}")


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
        # 检查是否已存在
        existing = get_task(history_item["task_id"])
        if existing:
            return False

        # 保存到数据库
        record = TaskRecord(
            task_id=history_item["task_id"],
            url=history_item.get("url", ""),
            platform=history_item["platform"],
            status="completed",
            message=history_item.get("message", ""),
            manga_info=history_item.get("manga_info"),
            zip_path=history_item.get("zip_path"),
            created_at=history_item.get("created_at", datetime.now().isoformat()),
            updated_at=datetime.now().isoformat(),
        )
        save_task(record)

        # 限制历史记录数量 - 删除最早的记录
        history_config = config.get_config().history
        max_items = history_config.max_items if history_config.max_items > 0 else 100
        total = get_total_count(status="completed")
        if total > max_items:
            # 获取需要删除的 task_ids
            old_tasks = get_history_tasks(limit=total - max_items)
            for t in old_tasks:
                delete_task(t.task_id)
        return True


def cleanup_old_history():
    """清理过期的历史记录"""
    try:
        history_config = CONFIG.history
        if history_config.auto_cleanup_days > 0:
            cutoff_date = datetime.now() - timedelta(days=history_config.auto_cleanup_days)
            # 获取所有历史任务并筛选
            all_history = get_all_tasks()
            to_keep = [
                h for h in all_history
                if datetime.fromisoformat(h.created_at) > cutoff_date
            ]
            # 删除需要清理的任务
            kept_ids = {h.task_id for h in to_keep}
            all_ids = {h.task_id for h in all_history}
            to_delete = all_ids - kept_ids
            for task_id in to_delete:
                delete_task(task_id)
    except Exception as e:
        logger.error(f"清理历史记录失败: {e}")


# 删除旧的历史记录处理（已迁移到数据库）


# ============== 下载器 ==============

class MangaDownloader:
    """漫画下载器 - 使用爬虫注册表"""

    def __init__(self, task: DownloadTask):
        self.task = task
        self.crawler: Optional[BaseCrawler] = None
        self.task_record: Optional[TaskRecord] = None

    def _cleanup_task(self):
        """清理任务相关的资源"""
        task_last_sse_state.pop(self.task.task_id, None)

    async def run(self):
        """执行下载"""
        try:
            # 根据 URL 获取爬虫
            self.crawler = get_crawler(self.task.url)
            self.task.platform = self.crawler.PLATFORM_NAME

            # 初始化爬虫的浏览器实例（从池中获取）
            await init_browser_for_crawler(self.crawler, self.task.platform)

            # 创建任务记录并保存到数据库
            self.task_record = TaskRecord(
                task_id=self.task.task_id,
                url=self.task.url,
                platform=self.task.platform,
                status="pending",
                created_at=self.task.created_at.isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            save_task(self.task_record)

            await self._do_download()
        except ValueError as e:
            self.task.status = "failed"
            self.task.error = str(e)
            self.task.message = f"错误: {e}"
            if self.task_record:
                self.task_record.status = "failed"
                self.task_record.error = str(e)
                self.task_record.message = f"错误: {e}"
                save_task(self.task_record)
        except Exception as e:
            self.task.status = "failed"
            self.task.error = str(e)
            self.task.message = f"下载失败: {e}"
            import traceback
            traceback.print_exc()
            if self.task_record:
                self.task_record.status = "failed"
                self.task_record.error = str(e)
                self.task_record.message = f"下载失败: {e}"
                save_task(self.task_record)
        finally:
            # 任务完成或失败后清理浏览器引用
            if self.crawler:
                # 释放浏览器引用，不立即关闭（浏览器池会管理）
                self.crawler.browser = None
                self.crawler.context = None
                self.crawler.page = None
                self.crawler.playwright = None
            # 任务完成或失败后清理 tasks 字典和 SSE 状态
            self._cleanup_task()
            # 保存任务到数据库
            save_task(self.task_record)

    def _update_manga_info(self):
        """更新漫画信息（合并重复逻辑）"""
        if self.crawler and hasattr(self.crawler, 'manga_info'):
            info = self.crawler.manga_info
            if info:
                self.task.manga_info = info.to_dict()
                if self.task_record:
                    self.task_record.manga_info = info.to_dict()
        elif self.crawler and hasattr(self.crawler, '_manga_info'):
            info = self.crawler._manga_info
            if info:
                self.task.manga_info = info.to_dict()
                if self.task_record:
                    self.task_record.manga_info = info.to_dict()

    async def _do_download(self):
        """执行下载"""
        url = self.task.url

        self.task.message = "解析漫画信息..."
        self.task.status = "downloading"
        if self.task_record:
            self.task_record.status = "downloading"
            self.task_record.message = "解析漫画信息..."
            save_task(self.task_record)

        # 获取漫画信息
        try:
            info = await self.crawler.get_info(url)
            self.task.manga_info = info.to_dict()
            self.task.platform = info.platform
            if self.task_record:
                self.task_record.manga_info = info.to_dict()
                self.task_record.platform = info.platform
                save_task(self.task_record)
        except Exception as e:
            # 如果获取信息失败，继续尝试下载
            if self.task_record:
                save_task(self.task_record)

        # 定义进度回调
        def on_progress(progress: DownloadProgress):
            self.task.progress = progress.current
            self.task.total = progress.total
            self.task.message = progress.message
            if progress.status:
                self.task.status = progress.status
            if self.task_record:
                self.task_record.status = progress.status
                self.task_record.progress = progress.current
                self.task_record.total = progress.total
                self.task_record.message = progress.message
                save_task(self.task_record)

        # 执行下载
        output_path = await self.crawler.download(
            url,
            str(DOWNLOADS_DIR),
            progress_callback=on_progress
        )

        self.task.output_path = output_path
        if self.task_record:
            self.task_record.output_path = output_path

        # 更新漫画信息（合并逻辑）
        self._update_manga_info()

        # 打包 zip（使用线程池异步执行）
        self.task.message = "正在打包..."
        if self.task_record:
            self.task_record.message = "正在打包..."
            save_task(self.task_record)
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
            if self.task_record:
                self.task_record.zip_path = str(zip_path)

        self.task.status = "completed"
        self.task.message = f"下载完成! 共 {self.task.total} 张图片"
        if self.task_record:
            self.task_record.status = "completed"
            self.task_record.message = f"下载完成! 共 {self.task.total} 张图片"
            save_task(self.task_record)

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
    """获取任务状态（从数据库）"""
    # 首先检查内存中的任务（正在进行中）
    task_record = get_task(task_id)
    if not task_record:
        raise HTTPException(status_code=404, detail="任务不存在")

    return {
        "task_id": task_record.task_id,
        "status": task_record.status,
        "progress": task_record.progress,
        "total": task_record.total,
        "message": task_record.message,
        "platform": task_record.platform,
        "manga_info": task_record.manga_info,
        "zip_path": task_record.zip_path,
        "output_path": task_record.output_path,
        "error": task_record.error
    }


@app.get("/api/progress/{task_id}")
async def stream_progress(task_id: str, timeout: float = 300.0):
    """SSE 进度推送 - 优化版，仅在重要状态变化时发送，带超时控制"""
    # 检查任务是否存在（从数据库或内存中）
    task_record = get_task(task_id)
    if not task_record:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 只读取一次配置，避免每次循环都读取
    sse_config = config.get_config().sse
    heartbeat_interval = max(0.5, sse_config.heartbeat_interval)

    import time

    async def event_generator():
        start_time = time.time()

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
        yield f"data: {get_task_data(task_record)}\n\n"

        while True:
            # 检查超时
            elapsed = time.time() - start_time
            if elapsed > timeout:
                task_last_sse_state.pop(task_id, None)
                break

            # 获取最新任务状态（从数据库）
            current_record = get_task(task_id)
            if not current_record:
                task_last_sse_state.pop(task_id, None)
                break

            current_state = {
                "status": current_record.status,
                "progress": current_record.progress,
                "total": current_record.total,
                "message": current_record.message,
                "error": current_record.error,
            }

            # 只有重要状态变化时才发送
            if is_important_change(current_state, last_state):
                yield f"data: {get_task_data(current_record)}\n\n"
                last_state = current_state.copy()
                task_last_sse_state[task_id] = last_state

            # 任务完成或失败，结束连接
            if current_record.status in ("completed", "failed"):
                task_last_sse_state.pop(task_id, None)
                break

            # 使用缓存的配置值，避免重复读取
            await asyncio.sleep(heartbeat_interval)

    def get_task_data(record: TaskRecord):
        """获取任务数据的 JSON 字符串"""
        data = {
            "task_id": record.task_id,
            "status": record.status,
            "progress": record.progress,
            "total": record.total,
            "message": record.message,
            "platform": record.platform,
            "manga_info": record.manga_info,
            "zip_path": record.zip_path,
            "error": record.error
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
    task_record = get_task(task_id)
    if not task_record:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task_record.status != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成")

    if not task_record.zip_path or not Path(task_record.zip_path).exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    filename = Path(task_record.zip_path).name
    return FileResponse(
        task_record.zip_path,
        media_type="application/zip",
        filename=filename
    )


@app.get("/api/history")
async def get_history(page: int = 1, page_size: int = 50):
    """获取下载历史（支持分页，从数据库）"""
    history_config = config.get_config().history
    max_items = history_config.max_items if history_config.max_items > 0 else 100

    # 分页参数验证
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 50

    # 限制最大页大小，防止过多数据传输
    page_size = min(page_size, 200)

    # 从数据库获取历史任务
    all_history = get_history_tasks(limit=max_items)
    total = len(all_history)

    # 计算分页索引
    start = (page - 1) * page_size
    end = start + page_size
    page_tasks = all_history[start:end]

    return {
        "history": [t.to_dict() for t in page_tasks],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": end < total
    }


# ============== 启动 ==============

if __name__ == "__main__":
    import uvicorn

    logger.info("启动漫画下载服务...")
    logger.info(f"API: http://{CONFIG.host}:{CONFIG.port}")
    logger.info(f"文档: http://{CONFIG.host}:{CONFIG.port}/docs")

    # 显示支持的平台
    platforms = get_supported_platforms()
    logger.info("支持的平台:")
    for p in platforms:
        logger.info(f"  - {p['display_name']}")

    # 显示配置信息
    logger.info(f"配置:")
    logger.info(f"  - 下载目录: {CONFIG.download.output_dir}")
    logger.info(f"  - 并发数: {CONFIG.download.concurrency}")
    logger.info(f"  - 日志级别: {CONFIG.logging.level}")

    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port)
