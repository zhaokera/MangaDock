"""Manga search contracts and registry."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type


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

    async def search(self, keyword: str, limit: int = 10) -> List[MangaSearchResult]:
        raise NotImplementedError

    async def get_chapters(self, url: str) -> dict:
        raise NotImplementedError


def get_manga_searcher(platform: str) -> Optional[BaseMangaSearcher]:
    searcher_class = _manga_searchers.get(platform)
    if searcher_class:
        return searcher_class()
    return None
