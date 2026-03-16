#!/usr/bin/env python3
"""
漫画下载器优化测试脚本 v2
测试 URL: https://www.manhuagui.com/comic/14798/146582.html
"""

import asyncio
import time
from crawlers.manhuagui import ManhuaguiCrawler
from crawlers.base import DownloadProgress


async def test_download():
    url = "https://www.manhuagui.com/comic/14798/146582.html"
    output_dir = "/tmp/manga_test"

    crawler = ManhuaguiCrawler()

    # 启动浏览器
    print("正在启动浏览器...")
    await crawler.start_browser(headless=True)

    download_start = None
    download_end = None

    def progress_callback(progress: DownloadProgress):
        nonlocal download_start, download_end
        print(f"[Progress] {progress.message} [status={progress.status}]")

        if progress.status == "downloading" and download_start is None:
            download_start = time.time()
            print(f"[DEBUG] 下载阶段开始: {time.strftime('%H:%M:%S')}")
        elif progress.status == "completed":
            download_end = time.time()
            if download_start and download_end:
                duration = download_end - download_start
                print(f"[DEBUG] 下载阶段耗时: {duration:.2f}秒")

    try:
        # 获取漫画信息
        print(f"正在获取漫画信息: {url}")
        info_start = time.time()
        manga_info = await crawler.get_info(url)
        info_end = time.time()

        print(f"\n=== 漫画信息 ===")
        print(f"标题: {manga_info.title}")
        print(f"章节: {manga_info.chapter}")
        print(f"页数: {manga_info.page_count}")
        print(f"平台: {manga_info.platform}")
        print(f"\n[DEBUG] 获取信息耗时: {info_end - info_start:.2f}秒")

        # 下载漫画
        print(f"\n=== 开始下载 ===")
        result = await crawler.download(
            url, output_dir, progress_callback=progress_callback
        )

        print(f"\n=== 下载完成 ===")
        print(f"保存路径: {result}")

    finally:
        # 关闭浏览器
        await crawler.close_browser()
        print("\n浏览器已关闭")

    # 总结
    print(f"\n=== 优化测试完成 ===")
    print(f"目标: 速度提升 50%")
    print(f"当前配置:")
    print(f"  - Timeout: 60秒")
    print(f"  - 并发数: 3")
    print(f"  - 重试次数: 2")


if __name__ == "__main__":
    asyncio.run(test_download())
