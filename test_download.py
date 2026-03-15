#!/usr/bin/env python3
import asyncio
import re
from crawlers.manhuagui import ManhuaguiCrawler

async def test():
    url = 'https://www.manhuagui.com/comic/58426/865091.html'
    crawler = ManhuaguiCrawler()
    crawler.headless = True

    try:
        await crawler.start_browser()
        await crawler.page.goto(url, wait_until='domcontentloaded', timeout=60000)
        await asyncio.sleep(4)

        # 获取页面内容
        content = await crawler.page.content()

        # 保存页面以便检查
        with open('/Users/zhaok/Desktop/漫画/page.html', 'w') as f:
            f.write(content)
        print("页面已保存到 page.html")

        # 检查 SMH 变量
        smh_info = await crawler.page.evaluate('''
            () => {
                if (typeof SMH === 'undefined') {
                    return { exists: false };
                }
                return {
                    exists: true,
                    has_imgData: typeof SMH.imgData !== 'undefined',
                    has_utils: typeof SMH.utils !== 'undefined',
                    has_goPage: typeof SMH.utils?.goPage === 'function',
                    imgData_type: typeof SMH.imgData,
                    utils_keys: SMH.utils ? Object.keys(SMH.utils) : null,
                    all_keys: Object.keys(SMH)
                };
            }
        ''')

        print(f"SMH 信息: {smh_info}")

        # 查找任何包含 files 或 path 的 JavaScript 对象
        patterns = [
            r'(?:window|SMH)\s*\[\s*"[^"]+"\s*\]\s*=\s*(\{[^}]*"files"[^}]*\})',
            r'V\.S\s*\(\s*(\{[^}]*"p"[^}]*\})',
            r'(?:chapterImages|imgData)\s*=\s*(\[[^\]]+\])',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            for i, match in enumerate(matches):
                if 'files' in str(match) or '"p"' in str(match):
                    print(f'Pattern: {pattern[:50]}...')
                    print(f'Match: {str(match)[:300]}')
                    print('---')

        # 获取当前页面的图片
        current_img = await crawler.page.evaluate('''
            () => {
                let img = document.querySelector('img.mangaFile');
                return img ? img.src : null;
            }
        ''')
        print(f"当前图片 URL: {current_img[:100] if current_img else 'None'}...")

        # 获取页数信息
        page_info = await crawler.page.evaluate('''
            () => {
                let pageSpan = document.querySelector('#page');
                let totalPages = document.querySelector('h1 + em + h2 + em + span');
                return {
                    currentPage: pageSpan ? pageSpan.innerText : 'unknown',
                    totalPagesHTML: totalPages ? totalPages.innerText : 'unknown'
                };
            }
        ''')
        print(f"页数信息: {page_info}")

        print('\n=== 测试 SMH.utils.goPage ===')
        # 测试 goPage 函数
        for i in range(2, 5):
            try:
                # 记录翻页前的页码
                before_page = await crawler.page.evaluate('() => document.querySelector("#page")?.innerText')
                print(f"翻页前第 {i} 页: 当前页码 = {before_page}")

                await crawler.page.evaluate(f'SMH.utils.goPage({i})')
                await asyncio.sleep(2)

                # 验证翻页后
                after_page = await crawler.page.evaluate('() => document.querySelector("#page")?.innerText')
                current_img = await crawler.page.evaluate('() => document.querySelector("img.mangaFile")?.src')
                print(f"翻页后: 实际页码 = {after_page}, 图片 = {current_img[:80] if current_img else None}...")
            except Exception as e:
                print(f"翻页到第 {i} 页失败: {e}")

        await crawler.close_browser()
    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()

asyncio.run(test())
