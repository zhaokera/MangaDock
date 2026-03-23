#!/usr/bin/env python3
"""
漫画下载 Web 服务
FastAPI 后端 + SSE 进度推送
支持多平台漫画下载
"""

import asyncio
import os
import re
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, HTTPException
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
    init_db,
    get_task,
    save_task,
    delete_task,
    delete_history_tasks,
    get_history_tasks,
    get_total_count,
)
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
from routes.search import build_search_router
from services.browser_pool import (
    cleanup_browser_pool,
    close_all_browsers,
    init_browser_for_crawler,
    release_browser_for_platform,
    schedule_browser_cleanup,
)
from services.downloader import MangaDownloader, add_history_item
from services.platforms import list_supported_platforms

# 导入配置管理
import config

# 加载配置
CONFIG = config.get_config()


# ============== 数据模型 ==============

class DownloadRequest(BaseModel):
    url: str


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


app.include_router(
    build_download_router(
        get_crawler_for_url=lambda url: get_crawler(url),
        create_download_task=lambda task_id, url, platform: DownloadTask(task_id, url, platform),
        create_downloader=lambda task: MangaDownloader(
            task,
            downloads_dir=DOWNLOADS_DIR,
            get_crawler_for_url=lambda url: get_crawler(url),
            init_browser_for_crawler=lambda crawler, platform: init_browser_for_crawler(
                crawler=crawler,
                platform=platform,
                browser_pool=_browser_pool,
                browser_pool_lock=_browser_pool_lock,
                get_config=config.get_config,
                logger=logger,
            ),
            release_browser_for_platform=lambda platform: release_browser_for_platform(
                _browser_pool,
                platform,
                asyncio.get_running_loop().time(),
            ),
            save_task_record=save_task,
            add_history_item=lambda history_item: add_history_item(
                history_item,
                state_lock=_state_lock,
                get_task_record=lambda task_id: get_task(task_id),
                save_task_record=save_task,
                get_total_completed_count=lambda: get_total_count(status="completed"),
                get_history_tasks=lambda limit: get_history_tasks(limit=limit),
                delete_task_record=lambda task_id: delete_task(task_id),
                get_history_max_items=lambda: (
                    config.get_config().history.max_items
                    if config.get_config().history.max_items > 0
                    else 100
                ),
            ),
            task_last_sse_state=task_last_sse_state,
            tasks=tasks,
        ),
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
app.include_router(
    build_search_router(
        search_all_platforms=lambda keyword, limit: search_all_platforms(keyword, limit_per_platform=limit),
        get_searcher=lambda platform: get_searcher(platform),
        get_manga_searcher=lambda platform: get_manga_searcher(platform),
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

    _browser_cleanup_task = asyncio.create_task(
        schedule_browser_cleanup(
            interval=cleanup_interval,
            cleanup_browser_pool=lambda: cleanup_browser_pool(
                browser_pool=_browser_pool,
                browser_pool_lock=_browser_pool_lock,
                get_config=config.get_config,
                logger=logger,
            ),
            logger=logger,
        )
    )
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
    await close_all_browsers(
        browser_pool=_browser_pool,
        browser_pool_lock=_browser_pool_lock,
        logger=logger,
    )

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
