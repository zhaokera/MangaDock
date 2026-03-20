"""
视频搜索工具
支持通过名称搜索各大视频网站的动漫资源
"""

import re
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    platform: str
    platform_display: str
    score: float = 0.0  # 匹配度评分
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "platform": self.platform,
            "platform_display": self.platform_display,
            "score": self.score,
            "extra": self.extra,
        }


class BaseSearcher:
    """视频搜索基类"""

    PLATFORM_NAME: str = ""
    PLATFORM_DISPLAY: str = ""
    SEARCH_URL: str = ""

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        """搜索视频"""
        raise NotImplementedError


class TencentSearcher(BaseSearcher):
    """腾讯视频搜索"""

    PLATFORM_NAME = "tencent"
    PLATFORM_DISPLAY = "腾讯视频"
    SEARCH_URL = "https://v.qq.com/x/search/"

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        # 腾讯视频搜索需要通过浏览器模拟
        from playwright.async_api import async_playwright

        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 腾讯视频搜索 URL
            search_url = f"https://v.qq.com/x/search/?q={keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # 提取搜索结果
            items = await page.evaluate('''
                () => {
                    let items = [];
                    let wrapper = document.querySelector('.result__wrapper') ||
                                  document.querySelector('.search_result') ||
                                  document.querySelector('.mod_search_result');

                    if (wrapper) {
                        let elements = wrapper.querySelectorAll('.result-item, .item, .link');
                        elements.forEach((el, idx) => {
                            if (idx >= 10) return;

                            let titleEl = el.querySelector('.title, h3, a');
                            let urlEl = el.querySelector('a');

                            if (titleEl && urlEl) {
                                let title = titleEl.innerText.trim();
                                let url = urlEl.href;

                                if (url && url.includes('v.qq.com')) {
                                    items.push({
                                        title: title,
                                        url: url,
                                        platform: 'tencent',
                                        platform_display: '腾讯视频'
                                    });
                                }
                            }
                        });
                    }

                    return items;
                }
            ''')

            for item in items:
                # 计算匹配度
                score = self._calculate_score(keyword, item['title'])
                results.append(SearchResult(
                    title=item['title'],
                    url=item['url'],
                    platform=item['platform'],
                    platform_display=item['platform_display'],
                    score=score
                ))

            await browser.close()

        # 按匹配度排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _calculate_score(self, keyword: str, title: str) -> float:
        """计算关键词匹配度"""
        if not keyword or not title:
            return 0.0

        keyword_lower = keyword.lower()
        title_lower = title.lower()

        score = 0.0

        # 完全匹配
        if keyword_lower in title_lower:
            score += 50.0

        # 开头匹配
        if title_lower.startswith(keyword_lower):
            score += 30.0

        # 关键词出现次数
        score += title_lower.count(keyword_lower) * 5.0

        # 长度偏好（适中的标题更相关）
        if 5 <= len(title) <= 50:
            score += 10.0

        return min(score, 100.0)


class IqiyiSearcher(BaseSearcher):
    """爱奇艺搜索"""

    PLATFORM_NAME = "iqiyi"
    PLATFORM_DISPLAY = "爱奇艺"
    SEARCH_URL = "https://so.iqiyi.com/"

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        from playwright.async_api import async_playwright

        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            search_url = f"https://so.iqiyi.com/so/q_{keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            items = await page.evaluate('''
                () => {
                    let items = [];
                    let results = document.querySelectorAll('.result, .search-result, .qy-link-hover');

                    results.forEach((el, idx) => {
                        if (idx >= 10) return;

                        let titleEl = el.querySelector('.title, h3, a');
                        let urlEl = el.querySelector('a');

                        if (titleEl && urlEl) {
                            let title = titleEl.innerText.trim();
                            let url = urlEl.href;

                            if (url && (url.includes('iqiyi.com') || url.includes('iqiyi.com'))) {
                                items.push({
                                    title: title,
                                    url: url,
                                    platform: 'iqiyi',
                                    platform_display: '爱奇艺'
                                });
                            }
                        }
                    });

                    return items;
                }
            ''')

            for item in items:
                score = self._calculate_score(keyword, item['title'])
                results.append(SearchResult(
                    title=item['title'],
                    url=item['url'],
                    platform=item['platform'],
                    platform_display=item['platform_display'],
                    score=score
                ))

            await browser.close()

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _calculate_score(self, keyword: str, title: str) -> float:
        if not keyword or not title:
            return 0.0

        keyword_lower = keyword.lower()
        title_lower = title.lower()

        score = 0.0

        if keyword_lower in title_lower:
            score += 50.0
        if title_lower.startswith(keyword_lower):
            score += 30.0
        score += title_lower.count(keyword_lower) * 5.0

        return min(score, 100.0)


class YoukuSearcher(BaseSearcher):
    """优酷搜索"""

    PLATFORM_NAME = "youku"
    PLATFORM_DISPLAY = "优酷"
    SEARCH_URL = "https://so.youku.com/"

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        from playwright.async_api import async_playwright

        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            search_url = f"https://so.youku.com/search_video/q_{keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            items = await page.evaluate('''
                () => {
                    let items = [];
                    let results = document.querySelectorAll('.search-item, .result-item, .video-item');

                    results.forEach((el, idx) => {
                        if (idx >= 10) return;

                        let titleEl = el.querySelector('.title, h3, a');
                        let urlEl = el.querySelector('a');

                        if (titleEl && urlEl) {
                            let title = titleEl.innerText.trim();
                            let url = urlEl.href;

                            if (url && url.includes('youku.com')) {
                                items.push({
                                    title: title,
                                    url: url,
                                    platform: 'youku',
                                    platform_display: '优酷'
                                });
                            }
                        }
                    });

                    return items;
                }
            ''')

            for item in items:
                score = self._calculate_score(keyword, item['title'])
                results.append(SearchResult(
                    title=item['title'],
                    url=item['url'],
                    platform=item['platform'],
                    platform_display=item['platform_display'],
                    score=score
                ))

            await browser.close()

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _calculate_score(self, keyword: str, title: str) -> float:
        if not keyword or not title:
            return 0.0

        keyword_lower = keyword.lower()
        title_lower = title.lower()

        score = 0.0

        if keyword_lower in title_lower:
            score += 50.0
        if title_lower.startswith(keyword_lower):
            score += 30.0
        score += title_lower.count(keyword_lower) * 5.0

        return min(score, 100.0)


class MgtvSearcher(BaseSearcher):
    """芒果TV搜索"""

    PLATFORM_NAME = "mango"
    PLATFORM_DISPLAY = "芒果TV"
    SEARCH_URL = "https://www.mgtv.com/search"

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        from playwright.async_api import async_playwright

        results = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            search_url = f"https://www.mgtv.com/search/?kw={keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            items = await page.evaluate('''
                () => {
                    let items = [];
                    let results = document.querySelectorAll('.search-item, .video-item, .card');

                    results.forEach((el, idx) => {
                        if (idx >= 10) return;

                        let titleEl = el.querySelector('.title, h3, a');
                        let urlEl = el.querySelector('a');

                        if (titleEl && urlEl) {
                            let title = titleEl.innerText.trim();
                            let url = urlEl.href;

                            if (url && url.includes('mgtv.com')) {
                                items.push({
                                    title: title,
                                    url: url,
                                    platform: 'mango',
                                    platform_display: '芒果TV'
                                });
                            }
                        }
                    });

                    return items;
                }
            ''')

            for item in items:
                score = self._calculate_score(keyword, item['title'])
                results.append(SearchResult(
                    title=item['title'],
                    url=item['url'],
                    platform=item['platform'],
                    platform_display=item['platform_display'],
                    score=score
                ))

            await browser.close()

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _calculate_score(self, keyword: str, title: str) -> float:
        if not keyword or not title:
            return 0.0

        keyword_lower = keyword.lower()
        title_lower = title.lower()

        score = 0.0

        if keyword_lower in title_lower:
            score += 50.0
        if title_lower.startswith(keyword_lower):
            score += 30.0
        score += title_lower.count(keyword_lower) * 5.0

        return min(score, 100.0)


# 搜索器注册表
_searchers: Dict[str, Any] = {}


def register_searcher(searcher_class):
    """注册搜索器"""
    _searchers[searcher_class.PLATFORM_NAME] = searcher_class
    return searcher_class


register_searcher(TencentSearcher)
register_searcher(IqiyiSearcher)
register_searcher(YoukuSearcher)
register_searcher(MgtvSearcher)


def get_searcher(platform: str) -> Optional[BaseSearcher]:
    """获取搜索器"""
    searcher_class = _searchers.get(platform)
    if searcher_class:
        return searcher_class()
    return None


async def search_all_platforms(keyword: str, limit_per_platform: int = 5) -> List[SearchResult]:
    """在所有平台搜索"""
    results = []

    for platform_name, searcher_class in _searchers.items():
        try:
            searcher = searcher_class()
            platform_results = await searcher.search(keyword, limit=limit_per_platform)
            results.extend(platform_results)
        except Exception as e:
            logger.error(f"平台 {platform_name} 搜索失败: {e}")

    # 去重并排序
    seen_urls = set()
    unique_results = []
    for r in results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            unique_results.append(r)

    unique_results.sort(key=lambda x: x.score, reverse=True)
    return unique_results[:limit_per_platform * len(_searchers)]
