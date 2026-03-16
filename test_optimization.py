#!/usr/bin/env python3
"""性能测试脚本"""
import asyncio
import time
import tempfile
from pathlib import Path
from crawlers.manhuagui import ManhuaguiCrawler

async def test():
    url = 'https://www.manhuagui.com/comic/14798/146582.html'
    crawler = ManhuaguiCrawler()
    crawler.headless = True

    with tempfile.TemporaryDirectory() as output_dir:
        start = time.time()
        
        try:
            await crawler.start_browser()
            print(f"开始测试下载: {url}")
            
            result = await asyncio.wait_for(
                crawler.download(url, output_dir),
                timeout=600
            )
            
            total_time = time.time() - start
            print(f"下载完成: {result}")
            print(f"总耗时: {total_time:.2f}秒")
            
            download_path = Path(result)
            files = sorted(download_path.glob("*.webp"))
            print(f"下载的图片文件数: {len(files)}")
            
            await crawler.close_browser()
            return True
            
        except asyncio.TimeoutError:
            print("下载超时")
            return False
        except Exception as e:
            print(f"下载失败: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    asyncio.run(test())
