#!/usr/bin/env python3
"""
哔哩哔哩漫画爬虫 v4
通过拦截 API 响应获取图片
"""

import asyncio
import os
import re
import json
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("请先安装 httpx: pip install httpx")
    exit(1)

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("请先安装 playwright: pip install playwright")
    print("然后运行: playwright install chromium")
    exit(1)


class BilibiliMangaCrawler:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None

    async def start(self):
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            channel="chrome"
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = await self.context.new_page()

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login_if_needed(self):
        """检查是否需要登录"""
        await self.page.goto("https://manga.bilibili.com", wait_until="networkidle")
        await self.page.wait_for_timeout(2000)

        logged_in = await self.page.evaluate("""
            () => {
                const userAvatar = document.querySelector('.user-avatar, .avatar, [class*="user-info"]');
                return userAvatar !== null;
            }
        """)

        if not logged_in:
            print("检测到未登录状态")
            print("请手动登录哔哩哔哩账号...")
            print("等待登录完成...")

            try:
                await self.page.wait_for_url("**/manga.bilibili.com/**", timeout=120000)
                await self.page.wait_for_timeout(3000)
                print("登录成功!")
            except PlaywrightTimeout:
                print("登录超时，继续尝试下载...")

    def extract_ids(self, url: str) -> tuple:
        """从URL提取 comic_id 和 episode_id"""
        match = re.search(r'/mc(\d+)/(\d+)', url)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None

    async def download_image(self, url: str, filepath: Path) -> bool:
        """下载单张图片"""
        try:
            headers = {
                "Referer": "https://manga.bilibili.com/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(url, headers=headers, follow_redirects=True)
                if response.status_code == 200:
                    filepath.write_bytes(response.content)
                    return True
                else:
                    print(f"下载失败 ({response.status_code})")
                    return False
        except Exception as e:
            print(f"下载出错: {e}")
            return False

    async def download_chapter(self, url: str, output_dir: str = "downloads"):
        """下载漫画章节"""
        await self.start()

        try:
            # 提取 ID
            comic_id, episode_id = self.extract_ids(url)
            if not comic_id or not episode_id:
                print(f"无法解析 URL: {url}")
                return

            print(f"漫画ID: {comic_id}, 章节ID: {episode_id}")

            # 拦截 API 响应
            image_urls = []
            episode_info = {}
            image_index_data = None

            async def handle_response(response):
                nonlocal episode_info, image_index_data
                resp_url = response.url

                # 拦截实际图片请求
                if any(ext in resp_url.lower() for ext in ['.jpg', '.png', '.webp', '.avif']):
                    if ('manga' in resp_url or 'hdslb' in resp_url) and 'token=' in resp_url:
                        image_urls.append(resp_url)

                # 拦截 GetEpisode 响应
                if "GetEpisode" in resp_url:
                    try:
                        data = await response.json()
                        if data.get("code") == 0:
                            episode_info = data.get("data", {})
                    except:
                        pass

                # 拦截 GetImageIndex 响应
                if "GetImageIndex" in resp_url:
                    try:
                        data = await response.json()
                        if data.get("code") == 0:
                            image_index_data = data.get("data", {})
                    except:
                        pass

            self.page.on("response", handle_response)

            # 访问页面
            print("正在访问页面...")
            await self.page.goto(url, wait_until="networkidle")
            await self.page.wait_for_timeout(5000)

            # 等待 GetImageIndex 响应
            for _ in range(10):
                if image_index_data:
                    break
                await self.page.wait_for_timeout(500)

            # 获取图片数量
            total_images = 0
            if image_index_data:
                total_images = len(image_index_data.get("images", []))
                print(f"图片索引: 共 {total_images} 张")

            # 滚动到每个图片容器
            print("加载所有图片...")
            containers = await self.page.query_selector_all('[class*="image-item"], [class*="page-item"]')
            print(f"找到 {len(containers)} 个图片容器")

            for i, container in enumerate(containers):
                try:
                    await container.scroll_into_view_if_needed()
                    await self.page.wait_for_timeout(100)
                    if (i + 1) % 10 == 0:
                        print(f"已滚动到 {i + 1}/{len(containers)} 个容器")
                except:
                    pass

            # 等待图片加载
            print("等待图片加载...")
            await self.page.wait_for_timeout(3000)

            # 获取章节标题
            comic_title = episode_info.get("comic_title", f"漫画{comic_id}")
            chapter_title = episode_info.get("title", f"第{episode_id}话")
            print(f"漫画: {comic_title}")
            print(f"章节: {chapter_title}")
            print(f"成功加载 {len(image_urls)} 张图片")

            if not image_urls:
                print("未找到图片，可能需要登录")
                return

            # 去重并排序
            image_urls = sorted(list(set(image_urls)))

            # 创建保存目录
            safe_title = re.sub(r'[\\/*?:"<>|]', "", f"{comic_title}_{chapter_title}")[:80]
            save_dir = Path(output_dir) / safe_title
            save_dir.mkdir(parents=True, exist_ok=True)

            # 下载图片
            print(f"\n开始下载到: {save_dir}")
            success_count = 0

            for i, img_url in enumerate(image_urls, 1):
                # 确定扩展名
                ext = ".jpg"
                if ".avif" in img_url:
                    ext = ".avif"
                elif ".webp" in img_url:
                    ext = ".webp"
                elif ".png" in img_url:
                    ext = ".png"

                filename = f"{i:03d}{ext}"
                filepath = save_dir / filename

                if await self.download_image(img_url, filepath):
                    print(f"✓ 已下载: {filename}")
                    success_count += 1
                else:
                    print(f"✗ 失败")

            print(f"\n下载完成! 成功: {success_count}/{len(image_urls)}")
            print(f"保存位置: {save_dir.absolute()}")

        finally:
            await self.close()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="哔哩哔哩漫画爬虫 v4")
    parser.add_argument("url", nargs="?", default="https://manga.bilibili.com/mc36091/1656375", help="漫画章节URL")
    parser.add_argument("-o", "--output", default="downloads", help="输出目录")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument("--login", action="store_true", help="启动时检查登录状态")

    args = parser.parse_args()

    crawler = BilibiliMangaCrawler(headless=args.headless)

    if args.login:
        await crawler.start()
        await crawler.login_if_needed()
        await crawler.close()
        crawler = BilibiliMangaCrawler(headless=args.headless)

    await crawler.download_chapter(args.url, args.output)


if __name__ == "__main__":
    asyncio.run(main())