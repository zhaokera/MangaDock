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
from typing import Optional, List
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Body
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
from crawlers.auth import get_auth_manager, AuthManager
from crawlers.resume import get_resume_manager, ResumeInfo
from crawlers.registry import get_crawler_by_platform

# 导入配置管理
import config

# 加载配置
CONFIG = config.get_config()


# ============== 数据模型 ==============

class DownloadRequest(BaseModel):
    url: str


class BatchDownloadRequest(BaseModel):
    urls: List[str]


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

# 下载队列 - 任务优先级队列
_download_queue: dict[str, DownloadTask] = {}
_download_queue_priority: dict[str, int] = {}
_download_queue_lock = asyncio.Lock()

# 初始化数据库
init_db()

# 下载目录（从配置获取）
DOWNLOADS_DIR = Path(CONFIG.download.output_dir)
DOWNLOADS_DIR.mkdir(exist_ok=True)


async def get_browser_for_platform(platform: str) -> dict:
    """
    获取指定平台的浏览器实例（从池中获取或创建新实例）

    浏览器池管理策略：
    - 每个平台最多保留 N 个浏览器实例（可配置）
    - 空闲超时（默认 5 分钟）后自动关闭
    - 使用计数器追踪活跃连接

    Args:
        platform: 平台名称

    Returns:
        dict: 包含 browser, context, page 的字典
    """
    import config
    from playwright.async_api import async_playwright

    async with _browser_pool_lock:
        if platform in _browser_pool:
            # 更新最后使用时间
            _browser_pool[platform]["last_used"] = asyncio.get_event_loop().time()
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

        current_time = asyncio.get_event_loop().time()
        browser_info = {
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
            "platform": platform,
            "used_count": 0,
            "created_at": current_time,
            "last_used": current_time
        }

        _browser_pool[platform] = browser_info
        logger.info(f"为平台 {platform} 创建新浏览器实例")
        return browser_info


async def release_browser_for_platform(platform: str):
    """
    释放指定平台的浏览器实例

    优化策略：
    - 不立即关闭浏览器，而是标记为可清理
    - 通过 cleanup_browser_pool 定期清理空闲浏览器
    - 避免频繁创建/销毁浏览器实例

    Args:
        platform: 平台名称
    """
    async with _browser_pool_lock:
        if platform in _browser_pool:
            browser_info = _browser_pool[platform]
            browser_info["used_count"] = max(0, browser_info["used_count"] - 1)
            browser_info["last_used"] = asyncio.get_event_loop().time()

            # 记录使用状态
            logger.debug(f"平台 {platform} 浏览器使用次数: {browser_info['used_count']}")


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
    """
    清理浏览器池中长时间未使用的浏览器

    策略：
    - 遍历所有平台的浏览器
    - 如果 used_count <= 0 且最后使用时间超过空闲超时，则关闭
    - 默认空闲超时：5 分钟

    Returns:
        list: 已关闭的平台列表
    """
    import config
    async with _browser_pool_lock:
        closed_platforms = []
        cfg = config.get_config()
        # 空闲超时（秒），从配置读取，默认 300 秒（5 分钟）
        idle_timeout = getattr(cfg.crawler, 'browser_idle_timeout', 300)

        current_time = asyncio.get_event_loop().time()

        for platform, browser_info in list(_browser_pool.items()):
            if browser_info["used_count"] <= 0:
                last_used = browser_info.get("last_used", browser_info["created_at"])
                idle_time = current_time - last_used

                if idle_time > idle_timeout:
                    try:
                        logger.info(f"清理空闲浏览器 [平台: {platform}, 空闲时间: {idle_time:.1f}s]")

                        if browser_info["page"]:
                            await browser_info["page"].close()
                        if browser_info["context"]:
                            await browser_info["context"].close()
                        if browser_info["browser"]:
                            await browser_info["browser"].close()
                        if browser_info["playwright"]:
                            await browser_info["playwright"].stop()

                        del _browser_pool[platform]
                        closed_platforms.append(platform)
                    except Exception as e:
                        logger.error(f"清理平台 {platform} 浏览器失败: {e}")

        return closed_platforms


async def schedule_browser_cleanup(interval: float = 60.0):
    """
    定期调度浏览器池清理任务（后台运行）

    Args:
        interval: 清理检查间隔（秒），默认 60 秒
    """
    import time
    while True:
        await asyncio.sleep(interval)
        try:
            closed = await cleanup_browser_pool()
            if closed:
                logger.info(f"浏览器池清理完成: {len(closed)} 个平台")
        except Exception as e:
            logger.error(f"浏览器池清理调度失败: {e}")


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


@app.post("/api/batch-download")
async def start_batch_download(request: BatchDownloadRequest, background_tasks: BackgroundTasks):
    """批量下载 - 一次下载多个漫画"""
    urls = request.urls

    if not urls or len(urls) == 0:
        raise HTTPException(status_code=400, detail="至少需要提供一个 URL")

    if len(urls) > 20:
        raise HTTPException(status_code=400, detail="单次最多支持 20 个 URL")

    # 验证所有 URL 并获取爬虫
    tasks_info = []
    for url in urls:
        try:
            crawler = get_crawler(url)
            tasks_info.append({
                "url": url,
                "platform": crawler.PLATFORM_NAME,
                "crawler": crawler
            })
        except ValueError as e:
            # 记录失败但继续处理其他 URL
            tasks_info.append({
                "url": url,
                "error": str(e),
                "platform": None
            })

    # 创建任务并启动下载
    results = []
    for info in tasks_info:
        if info.get("error"):
            results.append({
                "url": info["url"],
                "status": "failed",
                "error": info["error"]
            })
            continue

        task_id = str(uuid.uuid4())[:8]
        task = DownloadTask(task_id, info["url"], platform=info["platform"])

        downloader = MangaDownloader(task)
        background_tasks.add_task(downloader.run)

        results.append({
            "url": info["url"],
            "task_id": task_id,
            "status": "pending",
            "platform": info["platform"]
        })

    return {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "pending"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "results": results
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


@app.post("/api/queue/pause")
async def pause_download(task_id: str):
    """暂停下载任务"""
    async with _download_queue_lock:
        if task_id in _download_queue:
            task = _download_queue[task_id]
            task.status = "paused"
            return {"status": "paused", "task_id": task_id}
        raise HTTPException(status_code=404, detail="任务不存在")


@app.post("/api/queue/resume")
async def resume_download(task_id: str):
    """恢复下载任务"""
    async with _download_queue_lock:
        if task_id in _download_queue:
            task = _download_queue[task_id]
            task.status = "pending"
            return {"status": "resumed", "task_id": task_id}
        raise HTTPException(status_code=404, detail="任务不存在")


@app.delete("/api/queue/{task_id}")
async def remove_from_queue(task_id: str):
    """从下载队列移除任务"""
    async with _download_queue_lock:
        if task_id in _download_queue:
            del _download_queue[task_id]
            del _download_queue_priority[task_id]
            return {"status": "removed", "task_id": task_id}
        raise HTTPException(status_code=404, detail="任务不存在")


@app.get("/api/queue")
async def get_download_queue():
    """获取下载队列"""
    async with _download_queue_lock:
        queue_items = []
        for tid, task in _download_queue.items():
            queue_items.append({
                "task_id": tid,
                "url": task.url,
                "platform": task.platform,
                "status": task.status,
                "priority": _download_queue_priority.get(tid, 0),
                "position": len(queue_items),
            })
        # 按优先级排序
        queue_items.sort(key=lambda x: (-x["priority"], x["position"]))
        return {"queue": queue_items, "total": len(queue_items)}


@app.post("/api/queue/priority")
async def update_priority(request: dict):
    """更新任务优先级"""
    task_id = request.get("task_id")
    priority = request.get("priority", 0)

    async with _download_queue_lock:
        if task_id in _download_queue:
            _download_queue_priority[task_id] = priority
            return {"status": "updated", "task_id": task_id, "priority": priority}
        raise HTTPException(status_code=404, detail="任务不存在")


# ============== 认证 API ==============

class LoginRequest(BaseModel):
    platform: str
    username: str
    password: str
    credentials: Optional[dict] = None  # 额外的凭据字段


class LoginResponse(BaseModel):
    status: str
    platform: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    message: Optional[str] = None


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """登录平台"""
    platform = request.platform
    credentials = {
        'username': request.username,
        'password': request.password,
    }
    # 添加额外凭据
    if request.credentials:
        credentials.update(request.credentials)

    # 检查平台是否支持
    crawler = get_crawler_by_platform(platform)
    if crawler is None:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")

    # 检查平台是否实现了登录
    if not hasattr(crawler, 'login') or not callable(getattr(crawler, 'login')):
        raise HTTPException(status_code=400, detail=f"平台 {platform} 不支持登录")

    auth_manager = get_auth_manager()
    result = await auth_manager.login(platform, credentials)

    if result:
        user_info = await auth_manager.get_user_info(platform)
        return LoginResponse(
            status="success",
            platform=platform,
            user_id=user_info.get('user_id') if user_info else None,
            user_name=user_info.get('user_name') if user_info else None,
            message="登录成功"
        )
    else:
        raise HTTPException(status_code=401, detail="登录失败")


@app.post("/api/auth/logout")
async def logout(request: dict):
    """登出平台"""
    platform = request.get("platform")

    if not platform:
        raise HTTPException(status_code=400, detail="缺少 platform 参数")

    auth_manager = get_auth_manager()
    result = await auth_manager.logout(platform)

    if result:
        return {"status": "success", "platform": platform, "message": "登出成功"}
    else:
        raise HTTPException(status_code=500, detail="登出失败")


@app.get("/api/auth/status")
async def auth_status(platform: str):
    """检查登录状态"""
    auth_manager = get_auth_manager()
    is_logged_in = await auth_manager.is_logged_in(platform)

    if is_logged_in:
        user_info = await auth_manager.get_user_info(platform)
        return {
            "status": "logged_in",
            "platform": platform,
            "user_id": user_info.get('user_id') if user_info else None,
            "user_name": user_info.get('user_name') if user_info else None,
        }
    else:
        return {
            "status": "logged_out",
            "platform": platform,
            "user_id": None,
            "user_name": None,
        }


@app.get("/api/auth/platforms")
async def auth_platforms():
    """获取支持认证的平台列表"""
    platforms = get_supported_platforms()
    supported = []

    for p in platforms:
        platform_name = p['name']
        crawler = get_crawler_by_platform(platform_name)
        if crawler and hasattr(crawler, 'login') and callable(getattr(crawler, 'login')):
            supported.append({
                'name': platform_name,
                'display_name': p['display_name'],
            })

    return {"platforms": supported, "total": len(supported)}


# ============== 断点续传 API ==============

class ResumeStatus(BaseModel):
    """断点续传状态"""
    task_id: str
    url: str
    platform: str
    total: int
    downloaded_count: int
    success_count: int
    failed_count: int
    created_at: str
    last_updated: str


@app.get("/api/resume/status/{task_id}")
async def get_resume_status(task_id: str):
    """获取断点续传状态"""
    resume_manager = get_resume_manager()
    info = await resume_manager.load_progress(task_id)

    if info is None:
        raise HTTPException(status_code=404, detail="未找到断点续传记录")

    return ResumeStatus(
        task_id=info.task_id,
        url=info.url,
        platform=info.platform,
        total=info.total,
        downloaded_count=info.downloaded_count,
        success_count=info.success_count,
        failed_count=info.failed_count,
        created_at=info.created_at,
        last_updated=info.last_updated,
    )


@app.delete("/api/resume/{task_id}")
async def delete_resume(task_id: str):
    """删除断点续传记录"""
    resume_manager = get_resume_manager()
    result = await resume_manager.remove_progress(task_id)

    if result:
        return {"status": "deleted", "task_id": task_id}
    else:
        raise HTTPException(status_code=404, detail="未找到断点续传记录")


@app.get("/api/resume/list")
async def list_resumes():
    """列出所有断点续传记录"""
    resume_manager = get_resume_manager()
    infos = await resume_manager.get_all_resumes()

    resumes = []
    for info in infos:
        resumes.append(ResumeStatus(
            task_id=info.task_id,
            url=info.url,
            platform=info.platform,
            total=info.total,
            downloaded_count=info.downloaded_count,
            success_count=info.success_count,
            failed_count=info.failed_count,
            created_at=info.created_at,
            last_updated=info.last_updated,
        ))

    return {"resumes": resumes, "total": len(resumes)}


@app.post("/api/resume/cleanup")
async def cleanup_resumes(days: int = 7):
    """清理旧的断点续传记录"""
    resume_manager = get_resume_manager()
    count = await resume_manager.cleanup_old_resumes(days)
    return {"cleaned": count, "days": days}


# ============== 启动 ==============

# 浏览器池清理任务句柄
_browser_cleanup_task: Optional[asyncio.Task] = None


async def start_browser_cleanup_scheduler():
    """启动浏览器池清理调度器（后台任务）"""
    global _browser_cleanup_task
    # 从配置获取清理间隔，默认 60 秒
    cfg = config.get_config()
    cleanup_interval = getattr(cfg.crawler, 'browser_cleanup_interval', 60)

    _browser_cleanup_task = asyncio.create_task(schedule_browser_cleanup(cleanup_interval))
    logger.info(f"浏览器池清理调度器已启动 (interval={cleanup_interval}s)")


async def stop_browser_cleanup_scheduler():
    """停止浏览器池清理调度器"""
    global _browser_cleanup_task
    if _browser_cleanup_task:
        _browser_cleanup_task.cancel()
        try:
            await _browser_cleanup_task
        except asyncio.CancelledError:
            pass
        _browser_cleanup_task = None


async def on_startup():
    """应用启动时的初始化"""
    await start_browser_cleanup_scheduler()


async def on_shutdown():
    """应用关闭时的清理"""
    # 关闭所有浏览器
    async with _browser_pool_lock:
        for platform, browser_info in list(_browser_pool.items()):
            try:
                logger.info(f"关闭平台 {platform} 的浏览器")
                if browser_info["page"]:
                    await browser_info["page"].close()
                if browser_info["context"]:
                    await browser_info["context"].close()
                if browser_info["browser"]:
                    await browser_info["browser"].close()
                if browser_info["playwright"]:
                    await browser_info["playwright"].stop()
            except Exception as e:
                logger.error(f"关闭平台 {platform} 浏览器失败: {e}")
        _browser_pool.clear()

    # 停止清理调度器
    await stop_browser_cleanup_scheduler()


# 注册生命周期事件
app.add_event_handler("startup", on_startup)
app.add_event_handler("shutdown", on_shutdown)


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

    # 显示浏览器池配置
    cleanup_interval = getattr(CONFIG.crawler, 'browser_cleanup_interval', 60)
    idle_timeout = getattr(CONFIG.crawler, 'browser_idle_timeout', 300)
    logger.info(f"  - 浏览器池清理间隔: {cleanup_interval}s")
    logger.info(f"  - 浏览器空闲超时: {idle_timeout}s")

    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port)
