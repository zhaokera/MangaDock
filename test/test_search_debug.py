"""测试搜索功能调试脚本"""
import asyncio
from playwright.async_api import async_playwright


async def test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        page.set_default_timeout(120000)

        keyword = '海贼王'
        search_url = f'https://v.qq.com/x/search/?q={keyword}'
        print(f'访问: {search_url}')

        try:
            await page.goto(search_url, wait_until='domcontentloaded', timeout=120000)
            await asyncio.sleep(4)

            # 截图
            await page.screenshot(path='/tmp/search_full.png')
            print('截图保存成功')

            # 获取页面上的所有链接
            links = await page.evaluate('''
                () => {
                    const allLinks = Array.from(document.querySelectorAll('a'));
                    return allLinks.map(l => ({
                        href: l.href || '',
                        text: l.innerText.trim().substring(0, 50),
                        cls: (l.className || '').substring(0, 40),
                        parentCls: (l.parentElement?.className || '').substring(0, 40)
                    })).filter(l => l.href && l.href.includes('v.qq.com'));
                }
            ''')

            print(f'\n找到 {len(links)} 个 v.qq.com 链接 (前30个):')
            for l in links[:30]:
                print(f'  [{l["href"][:50]}...] {l["text"][:30]}')

            # 保存 HTML
            html = await page.content()
            with open('/tmp/search.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print('\nHTML 保存到 /tmp/search.html')

        except Exception as e:
            print(f'错误: {e}')
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(test())
