#!/usr/bin/env python3
"""Test to verify download_image_via_browser timeout fix"""
import asyncio
import tempfile
from pathlib import Path
from crawlers.manhuagui import ManhuaguiCrawler


async def test_download_timeout():
    """Test that download works with proper timeout"""
    url = 'https://www.manhuagui.com/comic/58426/865091.html'
    crawler = ManhuaguiCrawler()
    crawler.headless = True

    with tempfile.TemporaryDirectory() as output_dir:
        try:
            await crawler.start_browser()
            print(f"开始测试下载: {url}")

            # Run download with 300 second timeout for the whole test
            result = await asyncio.wait_for(
                crawler.download(url, output_dir),
                timeout=300
            )

            print(f"下载完成: {result}")

            # Check how many files were downloaded
            download_path = Path(result)
            files = list(download_path.glob("*.webp"))
            print(f"下载的图片文件数: {len(files)}")
            for f in sorted(files)[:5]:
                print(f"  - {f.name}")
            if len(files) > 5:
                print(f"  ... 和 {len(files) - 5} 个其他文件")

            await crawler.close_browser()
            return True

        except asyncio.TimeoutError:
            print("下载超时 (超过 300 秒)")
            return False
        except Exception as e:
            print(f"下载失败: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    success = asyncio.run(test_download_timeout())
    exit(0 if success else 1)
