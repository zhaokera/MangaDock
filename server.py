#!/usr/bin/env python3
"""
漫画下载 Web 服务
FastAPI 后端 + SSE 进度推送
支持多平台漫画下载
"""

import asyncio
import os
import re
import zipfile
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field, asdict

try:
    from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
except ImportError:
    print("请先安装 fastapi: pip install fastapi uvicorn")
    exit(1)

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 获取所有相关 logger
logger = logging.getLogger(__name__)
logging.getLogger("crawlers").setLevel(logging.INFO)
logging.getLogger("crawlers.tencent").setLevel(logging.INFO)
logging.getLogger("crawlers.iqiyi").setLevel(logging.INFO)

# 导入爬虫模块
from crawlers import (
    get_crawler,
    BaseCrawler,
    init_db,
    TaskRecord,
    get_task,
    save_task,
    delete_task,
    delete_history_tasks,
    get_history_tasks,
    get_total_count,
)
from crawlers.base import DownloadProgress
from crawlers.auth import get_auth_manager
from crawlers.resume import get_resume_manager
from crawlers.search import search_all_platforms, get_searcher
from crawlers.manga_search import get_manga_searcher
from crawlers.registry import get_crawler_by_platform
from routes.auth import build_auth_router
from routes.downloads import build_download_router
from routes.history import build_history_router
from routes.platforms import router as platforms_router
from routes.queue import build_queue_router
from routes.resume import build_resume_router
from services.platforms import list_supported_platforms

# 导入配置管理
import config

# 加载配置
CONFIG = config.get_config()


# ============== 数据模型 ==============

class DownloadRequest(BaseModel):
    url: str


class BatchDownloadRequest(BaseModel):
    urls: List[str]


class SearchRequest(BaseModel):
    keyword: str
    platform: Optional[str] = None  # 可选，指定平台
    limit: int = 10


class SearchResponse(BaseModel):
    results: List[dict]
    total: int
    platform: Optional[str] = None


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
app.include_router(platforms_router)

# 任务存储
tasks: dict[str, DownloadTask] = {}

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
            _browser_pool[platform]["last_used"] = asyncio.get_running_loop().time()
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

        current_time = asyncio.get_running_loop().time()
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
            browser_info["last_used"] = asyncio.get_running_loop().time()

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

        current_time = asyncio.get_running_loop().time()

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
    loop = asyncio.get_running_loop()
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
        tasks.pop(self.task.task_id, None)  # 自动清理 tasks 字典

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

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - 自动清理资源"""
        # 任务完成或失败后清理浏览器引用
        if self.crawler:
            self.crawler.browser = None
            self.crawler.context = None
            self.crawler.page = None
            self.crawler.playwright = None
        # 清理 SSE 状态
        self._cleanup_task()
        # 清理任务状态
        tasks.pop(self.task.task_id, None)


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
            loop = asyncio.get_running_loop()
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


app.include_router(
    build_download_router(
        get_crawler_for_url=lambda url: get_crawler(url),
        create_download_task=lambda task_id, url, platform: DownloadTask(task_id, url, platform),
        create_downloader=lambda task: MangaDownloader(task),
        get_task_record=lambda task_id: get_task(task_id),
        task_last_sse_state=task_last_sse_state,
        get_heartbeat_interval=lambda: config.get_config().sse.heartbeat_interval,
    )
)
app.include_router(
    build_history_router(
        get_history_tasks=lambda limit: get_history_tasks(limit=limit),
        get_history_max_items=lambda: (
            config.get_config().history.max_items
            if config.get_config().history.max_items > 0
            else 100
        ),
        get_task_record=lambda task_id: get_task(task_id),
        delete_task_record=lambda task_id: delete_task(task_id),
        delete_history_tasks=lambda platforms: delete_history_tasks(platforms),
    )
)
app.include_router(
    build_queue_router(
        download_queue=_download_queue,
        priorities=_download_queue_priority,
        queue_lock=_download_queue_lock,
    )
)


# ============== API 端点 ==============

@app.get("/")
async def root():
    return {
        "message": "漫画下载器 API",
        "version": "2.0",
        "description": "支持多平台漫画下载"
    }


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


async def _run_search(keyword: str, platform: Optional[str], limit: int) -> dict:
    """执行搜索并统一返回格式。"""
    if not keyword:
        raise HTTPException(status_code=400, detail="缺少 keyword 参数")

    limit = min(max(limit, 1), 50)

    try:
        if platform:
            searcher = get_searcher(platform)
            if searcher is None:
                raise HTTPException(status_code=400, detail=f"不支持的平台: {platform}")
            results = await searcher.search(keyword, limit=limit)
        else:
            results = await search_all_platforms(keyword, limit_per_platform=limit)

        return {
            "results": [r.to_dict() for r in results],
            "total": len(results),
            "platform": platform,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


def _get_manga_searcher_or_400(platform: str):
    searcher = get_manga_searcher(platform)
    if searcher is None:
        raise HTTPException(status_code=400, detail=f"不支持的漫画搜索平台: {platform}")
    return searcher


def _raise_manga_not_implemented(platform: str, action: str) -> None:
    raise HTTPException(
        status_code=501,
        detail=f"漫画搜索平台 {platform} 尚未实现{action}",
    )


@app.post("/api/search")
async def search_videos(request: SearchRequest, background_tasks: BackgroundTasks):
    """搜索视频 - 支持按名称搜索各大视频平台"""
    return await _run_search(
        keyword=request.keyword,
        platform=request.platform,
        limit=request.limit,
    )


@app.get("/api/search")
async def search_videos_get(
    keyword: str = Query(...),
    platform: Optional[str] = Query(None),
    limit: int = Query(10),
):
    """兼容前端 GET 请求的搜索接口。"""
    return await _run_search(keyword=keyword, platform=platform, limit=limit)


@app.get("/api/search/manga")
async def search_manga(keyword: str, platform: str, limit: int = 10):
    searcher = _get_manga_searcher_or_400(platform)

    try:
        results = await searcher.search(keyword, limit=limit)
    except NotImplementedError:
        _raise_manga_not_implemented(platform, "漫画搜索")

    return {
        "results": [item.to_dict() for item in results],
        "total": len(results),
        "platform": platform,
    }


@app.get("/api/manga/chapters")
async def get_manga_chapters(url: str, platform: str):
    searcher = _get_manga_searcher_or_400(platform)

    try:
        payload = await searcher.get_chapters(url)
    except NotImplementedError:
        _raise_manga_not_implemented(platform, "章节目录")

    return payload.to_dict()


# ============== 认证 API ==============

app.include_router(
    build_auth_router(
        get_auth_manager=lambda: get_auth_manager(),
        get_crawler_by_platform=lambda platform: get_crawler_by_platform(platform),
    )
)
app.include_router(
    build_resume_router(
        get_resume_manager=lambda: get_resume_manager(),
    )
)


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
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="漫画下载器")
    parser.add_argument("--search", "-s", help="搜索视频（按名称）")
    parser.add_argument("--platform", "-p", help="搜索平台（tencent/iqiyi/youku/mango）")
    parser.add_argument("--limit", "-l", type=int, default=10, help="搜索结果数量")
    parser.add_argument("--download", "-d", help="下载视频（通过 URL）")
    args = parser.parse_args()

    # 搜索模式
    if args.search:
        async def run_search():
            keyword = args.search
            platform = args.platform
            limit = args.limit

            try:
                if platform:
                    searcher = get_searcher(platform)
                    if searcher is None:
                        print(f"错误: 不支持的平台: {platform}")
                        print("支持的平台: tencent, iqiyi, youku, mango")
                        return
                    results = await searcher.search(keyword, limit=limit)
                else:
                    results = await search_all_platforms(keyword, limit_per_platform=limit)

                if not results:
                    print("未找到结果")
                    return

                print(f"\n找到 {len(results)} 个结果:")
                for i, r in enumerate(results, 1):
                    print(f"\n{i}. {r.title}")
                    print(f"   平台: {r.platform_display}")
                    print(f"   匹配度: {r.score:.1f}")
                    print(f"   URL: {r.url}")

            except Exception as e:
                print(f"搜索失败: {e}")

        asyncio.run(run_search())
        exit(0)

    # 下载模式
    if args.download:
        async def run_download():
            url = args.download
            try:
                crawler = get_crawler(url)
                info = await crawler.get_info(url)
                print(f"准备下载: {info.title}")

                # 执行下载
                output = await crawler.download(url, str(DOWNLOADS_DIR))
                print(f"下载完成: {output}")
            except Exception as e:
                print(f"下载失败: {e}")

        asyncio.run(run_download())
        exit(0)

    # 启动服务模式
    logger.info("启动漫画下载服务...")

    logger.info("启动漫画下载服务...")
    logger.info(f"API: http://{CONFIG.host}:{CONFIG.port}")
    logger.info(f"文档: http://{CONFIG.host}:{CONFIG.port}/docs")

    # 显示支持的平台
    platforms = list_supported_platforms()
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

    # 启动配置监听器（热重载）
    import config as server_config
    server_config.start_config_watcher(
        callback=lambda: logger.info("配置已热重载"),
        interval=5.0
    )
    logger.info("配置热重载已启用")

    uvicorn.run(app, host=CONFIG.host, port=CONFIG.port)
