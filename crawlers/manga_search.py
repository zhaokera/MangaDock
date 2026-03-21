"""Manga search contracts and registry."""

import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Type
from urllib.parse import quote, urljoin

from .manhuagui import (
    is_manhuagui_chapter_url,
    manhuagui_chapter_sort_key,
    normalize_manhuagui_comic_url,
)


@dataclass
class MangaSearchResult:
    title: str
    url: str
    platform: str
    platform_display: str
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "platform": self.platform,
            "platform_display": self.platform_display,
            "extra": self.extra,
        }


@dataclass
class MangaChapterResult:
    title: str
    url: str

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
        }


@dataclass
class MangaChapterCatalog:
    title: str
    platform: str
    platform_display: str
    url: str
    chapters: List[MangaChapterResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "platform": self.platform,
            "platform_display": self.platform_display,
            "url": self.url,
            "chapters": [chapter.to_dict() for chapter in self.chapters],
        }


class BaseMangaSearcher:
    PLATFORM_NAME: str = ""
    PLATFORM_DISPLAY: str = ""

    async def search(self, keyword: str, limit: int = 10) -> List[MangaSearchResult]:
        raise NotImplementedError

    async def get_chapters(self, url: str) -> MangaChapterCatalog:
        raise NotImplementedError

    def _normalize_text(self, value: Optional[str]) -> str:
        if not value:
            return ""

        return re.sub(r"\s+", " ", unescape(value).replace("\u200b", " ")).strip()

    def _resolve_candidate_url(self, candidate: Dict[str, Any]) -> str:
        return self._normalize_text(candidate.get("url"))

    def _build_results_from_candidates(
        self,
        keyword: str,
        candidates: List[Dict[str, Any]],
        limit: int = 10,
    ) -> List[MangaSearchResult]:
        results: List[MangaSearchResult] = []
        seen_urls = set()
        keyword_norm = self._normalize_text(keyword).lower()

        for candidate in candidates:
            title = self._normalize_text(candidate.get("title") or candidate.get("text"))
            url = self._resolve_candidate_url(candidate)

            if not title or not url or url in seen_urls:
                continue

            if keyword_norm and keyword_norm not in title.lower():
                continue

            seen_urls.add(url)
            results.append(
                MangaSearchResult(
                    title=title,
                    url=url,
                    platform=self.PLATFORM_NAME,
                    platform_display=self.PLATFORM_DISPLAY,
                )
            )

            if len(results) >= limit:
                break

        return results


_manga_searchers: Dict[str, Type[BaseMangaSearcher]] = {}


def register_manga_searcher(searcher_class: Type[BaseMangaSearcher]) -> Type[BaseMangaSearcher]:
    if not searcher_class.PLATFORM_NAME:
        raise ValueError(f"漫画搜索器 {searcher_class.__name__} 必须定义 PLATFORM_NAME")

    _manga_searchers[searcher_class.PLATFORM_NAME] = searcher_class
    return searcher_class


@register_manga_searcher
class ManhuaguiMangaSearcher(BaseMangaSearcher):
    PLATFORM_NAME = "manhuagui"
    PLATFORM_DISPLAY = "漫画柜"

    def _resolve_candidate_url(self, candidate: Dict[str, Any]) -> str:
        return normalize_manhuagui_comic_url(super()._resolve_candidate_url(candidate))

    def _extract_title_from_html(self, html: str) -> str:
        patterns = [
            r'<h1[^>]*>(.*?)</h1>',
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<title[^>]*>(.*?)</title>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html or "", re.IGNORECASE | re.DOTALL)
            if match:
                title = self._normalize_text(re.sub(r"<[^>]+>", "", match.group(1)))
                if title:
                    return title

        return ""

    def _extract_chapters_from_html(self, html: str) -> List[MangaChapterResult]:
        class _AnchorCollector(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.anchors: List[Dict[str, str]] = []
                self._current: Optional[Dict[str, str]] = None

            def handle_starttag(self, tag, attrs):
                if tag.lower() != "a":
                    return

                attr_map = dict(attrs)
                self._current = {
                    "href": attr_map.get("href", ""),
                    "title": attr_map.get("title", ""),
                    "text": "",
                }

            def handle_data(self, data):
                if self._current is not None:
                    self._current["text"] += data

            def handle_endtag(self, tag):
                if tag.lower() != "a" or self._current is None:
                    return

                self.anchors.append(self._current)
                self._current = None

        parser = _AnchorCollector()
        parser.feed(html or "")

        chapters: List[MangaChapterResult] = []
        seen_urls = set()

        for anchor in parser.anchors:
            href = self._normalize_text(anchor.get("href"))
            if not href:
                continue

            url = urljoin("https://www.manhuagui.com", href)
            if not is_manhuagui_chapter_url(url):
                continue

            title = self._normalize_text(anchor.get("title") or anchor.get("text"))
            if not title or url in seen_urls:
                continue

            seen_urls.add(url)
            chapters.append(MangaChapterResult(title=title, url=url))

        chapters.sort(key=lambda chapter: manhuagui_chapter_sort_key(chapter.title, chapter.url))
        return chapters

    async def search(self, keyword: str, limit: int = 10) -> List[MangaSearchResult]:
        from playwright.async_api import async_playwright

        search_url = f"https://www.manhuagui.com/s/{quote(keyword)}.html"
        candidates: List[Dict[str, Any]] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(1200)
                candidates = await page.evaluate(
                    """
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
                        }))
                        .filter((item) => /\\/comic\\/\\d+\\/?$/.test(item.url))
                    """
                )
            finally:
                await browser.close()

        return self._build_results_from_candidates(keyword, candidates, limit)

    async def get_chapters(self, url: str) -> MangaChapterCatalog:
        from playwright.async_api import async_playwright

        detail_url = normalize_manhuagui_comic_url(url)
        html = ""

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(detail_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(1200)
                html = await page.content()
                title = ""

                try:
                    title_elem = await page.query_selector("h1, .book-title, .comic-title")
                    if title_elem:
                        title = self._normalize_text(await title_elem.inner_text())
                except Exception:
                    title = ""

                if not title:
                    title = self._extract_title_from_html(html)
            finally:
                await browser.close()

        chapters = self._extract_chapters_from_html(html)

        return MangaChapterCatalog(
            title=title,
            platform=self.PLATFORM_NAME,
            platform_display=self.PLATFORM_DISPLAY,
            url=detail_url,
            chapters=chapters,
        )


def get_manga_searcher(platform: str) -> Optional[BaseMangaSearcher]:
    searcher_class = _manga_searchers.get(platform)
    if searcher_class:
        return searcher_class()
    return None
