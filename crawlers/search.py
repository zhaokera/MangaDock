"""
视频搜索工具
支持通过名称搜索各大视频网站的动漫资源
"""

import re
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin

logger = logging.getLogger(__name__)

_DL_EXPO_BASE_URL = "https://www.dl-expo.com"


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

    def _normalize_text(self, value: Optional[str]) -> str:
        if not value:
            return ""

        return re.sub(r"\s+", " ", value.replace("\u200b", " ")).strip()

    def _resolve_candidate_url(self, candidate: Dict[str, Any]) -> str:
        return self._normalize_text(candidate.get("url"))

    def _should_keep_candidate(
        self,
        candidate: Dict[str, Any],
        title: str,
        url: str,
    ) -> bool:
        return True

    def _build_results_from_candidates(
        self,
        keyword: str,
        candidates: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[SearchResult]:
        results: List[SearchResult] = []
        seen_urls = set()

        for candidate in candidates:
            title = self._normalize_text(candidate.get("title") or candidate.get("text"))
            url = self._resolve_candidate_url(candidate)
            if not title or not url or url in seen_urls:
                continue

            if not self._should_keep_candidate(candidate, title, url):
                continue

            score = self._calculate_score(keyword, title)
            if score <= 0:
                continue

            seen_urls.add(url)
            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    platform=self.PLATFORM_NAME,
                    platform_display=self.PLATFORM_DISPLAY,
                    score=score,
                )
            )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


class TencentSearcher(BaseSearcher):
    """腾讯视频搜索"""

    PLATFORM_NAME = "tencent"
    PLATFORM_DISPLAY = "腾讯视频"
    SEARCH_URL = "https://v.qq.com/x/search/"

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        # 腾讯视频搜索需要通过浏览器模拟
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # 腾讯视频搜索 URL
            search_url = f"https://v.qq.com/x/search/?q={keyword}"
            # 使用 domcontentloaded 而不是 networkidle，避免等待资源加载
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3)

            # 腾讯搜索页已切到卡片式结构，很多结果不再直接暴露 href，需要从 dt-params 的 cid 回填为 cover URL。
            candidates = await page.evaluate('''
                () => {
                    const items = [];

                    document.querySelectorAll('.root.list-item').forEach((el, idx) => {
                        if (idx >= 20) return;

                        const titleEl = el.querySelector('.info-title, [title], p[title]');
                        const title = (titleEl?.getAttribute('title') || titleEl?.innerText || '').replace(/\\s+/g, ' ').trim();
                        const poster = el.querySelector('.poster[dt-params]');
                        let cid = '';

                        if (poster) {
                            const params = new URLSearchParams(poster.getAttribute('dt-params') || '');
                            cid = params.get('cid') || '';
                        }

                        if (title || cid) {
                            items.push({ title, url: '', cid });
                        }
                    });

                    document.querySelectorAll('a[href]').forEach((anchor) => {
                        const href = anchor.href || '';
                        const title = (
                            anchor.getAttribute('title') ||
                            anchor.getAttribute('aria-label') ||
                            anchor.innerText ||
                            anchor.textContent ||
                            ''
                        ).replace(/\\s+/g, ' ').trim();

                        if (href.includes('v.qq.com') && title) {
                            items.push({ title, url: href, cid: '' });
                        }
                    });

                    return items;
                }
            ''')

            await browser.close()

        return self._build_results_from_candidates(keyword, candidates, limit)

    def _resolve_candidate_url(self, candidate: Dict[str, Any]) -> str:
        direct_url = super()._resolve_candidate_url(candidate)
        if direct_url:
            return direct_url

        cid = self._normalize_text(candidate.get("cid"))
        if cid:
            return f"https://v.qq.com/x/cover/{cid}.html"

        return ""

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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            search_url = f"https://so.iqiyi.com/so/q_{keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            candidates = await page.evaluate('''
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map((anchor) => ({
                        title: (
                            anchor.getAttribute('title') ||
                            anchor.getAttribute('aria-label') ||
                            anchor.innerText ||
                            anchor.textContent ||
                            ''
                        ).replace(/\\s+/g, ' ').trim(),
                        url: anchor.href || '',
                        cid: ''
                    }))
                    .filter((item) => item.url.includes('iqiyi.com') && item.title)
            ''')

            await browser.close()

        return self._build_results_from_candidates(keyword, candidates, limit)

    def _should_keep_candidate(
        self,
        candidate: Dict[str, Any],
        title: str,
        url: str,
    ) -> bool:
        lower_url = url.lower()
        if "shortvideo" in lower_url:
            return False

        return True

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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            search_url = f"https://so.youku.com/search_video/q_{keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            candidates = await page.evaluate('''
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map((anchor) => ({
                        title: (
                            anchor.getAttribute('title') ||
                            anchor.getAttribute('aria-label') ||
                            anchor.innerText ||
                            anchor.textContent ||
                            ''
                        ).replace(/\\s+/g, ' ').trim(),
                        url: anchor.href || '',
                        cid: ''
                    }))
                    .filter((item) => item.url.includes('youku.com') && item.title)
            ''')

            await browser.close()

        return self._build_results_from_candidates(keyword, candidates, limit)

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

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            search_url = f"https://www.mgtv.com/search/?kw={keyword}"
            await page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(2)

            candidates = await page.evaluate('''
                () => Array.from(document.querySelectorAll('a[href]'))
                    .map((anchor) => ({
                        title: (
                            anchor.getAttribute('title') ||
                            anchor.getAttribute('aria-label') ||
                            anchor.innerText ||
                            anchor.textContent ||
                            ''
                        ).replace(/\\s+/g, ' ').trim(),
                        url: anchor.href || '',
                        cid: ''
                    }))
                    .filter((item) => item.url.includes('mgtv.com') && item.title)
            ''')

            await browser.close()

        return self._build_results_from_candidates(keyword, candidates, limit)

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


class DlExpoSearcher(BaseSearcher):
    """糯米影视搜索"""

    PLATFORM_NAME = "dl_expo"
    PLATFORM_DISPLAY = "糯米影视"
    SEARCH_URL = f"{_DL_EXPO_BASE_URL}/search/-------------.html"

    async def search(self, keyword: str, limit: int = 10) -> List[SearchResult]:
        from playwright.async_api import async_playwright

        encoded_keyword = quote(keyword)
        search_url = f"{self.SEARCH_URL}?wd={encoded_keyword}"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)

            candidates = await page.evaluate(
                """
                () => {
                    const selectors = [
                        '.module-card-item',
                        '.module-search-item',
                        '.module-item',
                        '.myui-vodlist__media li',
                        '.searchlilst li',
                        '.fed-list-item',
                    ];
                    const cards = selectors.flatMap((selector) => Array.from(document.querySelectorAll(selector)));
                    const items = cards.map((card) => {
                        const anchor = card.querySelector('a[href]');
                        const titleNode = card.querySelector('[title], .module-card-item-title, .module-card-item-name, .video-info-header h3, h3, h4');
                        const title = (
                            titleNode?.getAttribute('title') ||
                            titleNode?.textContent ||
                            anchor?.getAttribute('title') ||
                            anchor?.textContent ||
                            ''
                        ).replace(/\\s+/g, ' ').trim();
                        const url = anchor?.getAttribute('href') || '';

                        return { title, url };
                    });

                    if (items.some((item) => item.title && item.url)) {
                        return items;
                    }

                    return Array.from(document.querySelectorAll('a[href*="/voddetail/"], a[href*="/play/"]'))
                        .map((anchor) => ({
                            title: (
                                anchor.getAttribute('title') ||
                                anchor.textContent ||
                                ''
                            ).replace(/\\s+/g, ' ').trim(),
                            url: anchor.getAttribute('href') || '',
                        }));
                }
                """
            )

            await browser.close()

        return self._build_results_from_candidates(keyword, candidates, limit)

    def _resolve_candidate_url(self, candidate: Dict[str, Any]) -> str:
        url = super()._resolve_candidate_url(candidate)
        if not url:
            return ""

        return urljoin(f"{_DL_EXPO_BASE_URL}/", url)

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
register_searcher(DlExpoSearcher)


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
