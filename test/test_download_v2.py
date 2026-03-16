#!/usr/bin/env python3
"""Test download with extended timeout"""
import asyncio
import tempfile
from pathlib import Path
from crawlers.manhuagui import ManhuaguiCrawler


async def test():
    url = 'https://www.manhuagui.com/comic/58426/865091.html'
    crawler = ManhuaguiCrawler()
    crawler.headless = True

    with tempfile.TemporaryDirectory() as output_dir:
        try:
            await crawler.start_browser()
            print(f"开始测试下载: {url}")

            # Use 600 second outer timeout
            result = await asyncio.wait_for(
                crawler.download(url, output_dir),
                timeout=600  # 10 minutes
            )

            print(f"下载完成: {result}")

            # Check how many files were downloaded
            download_path = Path(result)
            files = sorted(download_path.glob("*.webp"))
            print(f"下载的图片文件数: {len(files)}")
            for f in files:
                size = f.stat().st_size
                print(f"  - {f.name} ({size} bytes)")

            await crawler.close_browser()
            return True

        except asyncio.TimeoutError:
            print("下载超时 (超过 600 秒)")
            return False
        except Exception as e:
            print(f"下载失败: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test())
    exit(0 if success else 1)
