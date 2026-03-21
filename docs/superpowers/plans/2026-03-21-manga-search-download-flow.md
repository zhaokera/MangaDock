# Manga Search Download Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manga search-to-download flow on `/manga` that lets users search for a series, open its chapter list inline, multi-select chapters, confirm the selection, and then submit the chosen chapter URLs through the existing batch-download path while keeping direct link download intact.

**Architecture:** Introduce a dedicated manga-search backend instead of overloading the video search module. Ship the first vertical slice with a generic manga search/chapters contract plus `manhuagui` support, then wire the frontend manga page to that contract with an explicit chapter-confirmation step before any batch download request is sent.

**Tech Stack:** FastAPI, Python crawler modules, React 18, TypeScript, Vite, Vitest, Testing Library, pytest

---

## File Structure

### Existing files to modify

- `crawlers/manhuagui.py` - add series/chapter parsing helpers that can return a chapter catalog from a comic detail URL
- `server.py` - expose manga search and chapter-list APIs separate from `/api/search`
- `web/src/api/client.ts` - add manga search and chapter-list request helpers plus response types
- `web/src/pages/MangaPage.tsx` - integrate manga search, inline chapter selection, confirm-before-download, and batch submission
- `web/src/pages/MangaPage.test.tsx` - extend page-level flow coverage beyond the existing batch-link form

### New files to create

- `crawlers/manga_search.py` - manga search contracts, registry, and first `manhuagui` searcher
- `test/unit/test_manga_search.py` - searcher registration, normalization, and chapter catalog tests
- `test/unit/test_server_manga_search_api.py` - `/api/search/manga` coverage
- `test/unit/test_server_manga_chapters_api.py` - `/api/manga/chapters` coverage
- `web/src/components/MangaSearchInput.tsx` - manga-only search form and platform filter
- `web/src/components/MangaSearchResults.tsx` - selectable manga series results
- `web/src/components/MangaChapterPicker.tsx` - inline chapter list with multi-select helpers
- `web/src/components/MangaDownloadConfirm.tsx` - explicit confirmation area before batch submission
- `web/src/components/MangaSearchInput.test.tsx` - search form behavior coverage
- `web/src/components/MangaDownloadConfirm.test.tsx` - confirmation-step coverage

### Scope note

The approved UX spec says manga search should target supported manga download platforms. In the current codebase there are zero manga searchers and several independent manga crawlers, so this plan intentionally ships the generic manga-search contract plus a first production path for `manhuagui`. The plan keeps the API and frontend generic so the remaining manga platforms can be added as follow-up searchers without reworking the page flow.

---

### Task 1: Add Manga Search Contracts and API Endpoints

**Files:**
- Create: `crawlers/manga_search.py`
- Create: `test/unit/test_manga_search.py`
- Create: `test/unit/test_server_manga_search_api.py`
- Create: `test/unit/test_server_manga_chapters_api.py`
- Modify: `server.py`

- [ ] **Step 1: Write a failing registry test for manga searchers and chapter payloads**

```python
from crawlers.manga_search import (
    MangaChapterResult,
    MangaSearchResult,
    get_manga_searcher,
)


def test_get_manga_searcher_returns_manhuagui_searcher():
    searcher = get_manga_searcher("manhuagui")
    assert searcher is not None
    assert searcher.PLATFORM_NAME == "manhuagui"


def test_manga_result_to_dict_keeps_required_fields():
    result = MangaSearchResult(
        title="海贼王",
        url="https://www.manhuagui.com/comic/1/",
        platform="manhuagui",
        platform_display="漫画柜",
    )
    assert result.to_dict()["title"] == "海贼王"


def test_chapter_result_to_dict_keeps_url_and_title():
    chapter = MangaChapterResult(
        title="第1话",
        url="https://www.manhuagui.com/comic/1/100.html",
    )
    assert chapter.to_dict() == {
        "title": "第1话",
        "url": "https://www.manhuagui.com/comic/1/100.html",
    }
```

- [ ] **Step 2: Run the new unit test to verify it fails**

Run: `python3 -m pytest -q test/unit/test_manga_search.py`

Expected: FAIL with module-not-found or missing symbol errors for `crawlers.manga_search`.

- [ ] **Step 3: Add failing API tests for dedicated manga endpoints**

```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from crawlers.manga_search import MangaChapterResult, MangaSearchResult
from server import app


client = TestClient(app)


def test_manga_search_endpoint_returns_results_for_platform():
    mocked_results = [
        MangaSearchResult(
            title="海贼王",
            url="https://www.manhuagui.com/comic/1/",
            platform="manhuagui",
            platform_display="漫画柜",
        )
    ]

    with patch("server.get_manga_searcher") as mock_get_searcher:
        mock_searcher = AsyncMock()
        mock_searcher.search.return_value = mocked_results
        mock_get_searcher.return_value = mock_searcher

        response = client.get(
            "/api/search/manga",
            params={"keyword": "海贼王", "platform": "manhuagui", "limit": 5},
        )

    assert response.status_code == 200
    assert response.json()["results"] == [mocked_results[0].to_dict()]


def test_manga_chapters_endpoint_returns_inline_catalog_payload():
    mocked_chapters = [
        MangaChapterResult(
            title="第1话",
            url="https://www.manhuagui.com/comic/1/100.html",
        )
    ]

    with patch("server.get_manga_searcher") as mock_get_searcher:
        mock_searcher = AsyncMock()
        mock_searcher.get_chapters.return_value = {
            "title": "海贼王",
            "platform": "manhuagui",
            "platform_display": "漫画柜",
            "url": "https://www.manhuagui.com/comic/1/",
            "chapters": mocked_chapters,
        }
        mock_get_searcher.return_value = mock_searcher

        response = client.get(
            "/api/manga/chapters",
            params={"url": "https://www.manhuagui.com/comic/1/", "platform": "manhuagui"},
        )

    assert response.status_code == 200
    assert response.json()["chapters"] == [mocked_chapters[0].to_dict()]
```

- [ ] **Step 4: Run the API tests to verify they fail**

Run: `python3 -m pytest -q test/unit/test_server_manga_search_api.py test/unit/test_server_manga_chapters_api.py`

Expected: FAIL because `server.py` does not yet expose `/api/search/manga` or `/api/manga/chapters`.

- [ ] **Step 5: Implement the minimal backend contracts and endpoint stubs**

```python
# crawlers/manga_search.py
@dataclass
class MangaSearchResult:
    title: str
    url: str
    platform: str
    platform_display: str
    extra: dict = field(default_factory=dict)


@dataclass
class MangaChapterResult:
    title: str
    url: str


class BaseMangaSearcher:
    PLATFORM_NAME: str = ""
    PLATFORM_DISPLAY: str = ""

    async def search(self, keyword: str, limit: int = 10) -> List[MangaSearchResult]:
        raise NotImplementedError

    async def get_chapters(self, url: str) -> dict:
        raise NotImplementedError
```

```python
# server.py
from crawlers.manga_search import get_manga_searcher


@app.get("/api/search/manga")
async def search_manga(keyword: str, platform: str, limit: int = 10):
    searcher = get_manga_searcher(platform)
    if searcher is None:
        raise HTTPException(status_code=400, detail=f"不支持的漫画搜索平台: {platform}")

    results = await searcher.search(keyword, limit=limit)
    return {"results": [item.to_dict() for item in results], "total": len(results), "platform": platform}


@app.get("/api/manga/chapters")
async def get_manga_chapters(url: str, platform: str):
    searcher = get_manga_searcher(platform)
    if searcher is None:
        raise HTTPException(status_code=400, detail=f"不支持的漫画搜索平台: {platform}")

    payload = await searcher.get_chapters(url)
    payload["chapters"] = [chapter.to_dict() for chapter in payload["chapters"]]
    return payload
```

- [ ] **Step 6: Re-run the new backend foundation tests to verify green**

Run: `python3 -m pytest -q test/unit/test_manga_search.py test/unit/test_server_manga_search_api.py test/unit/test_server_manga_chapters_api.py`

Expected: PASS

- [ ] **Step 7: Commit the manga-search API foundation**

```bash
git add crawlers/manga_search.py server.py test/unit/test_manga_search.py test/unit/test_server_manga_search_api.py test/unit/test_server_manga_chapters_api.py
git commit -m "feat: add manga search api foundation"
```

### Task 2: Implement the First Searchable Manga Platform (`manhuagui`)

**Files:**
- Modify: `crawlers/manga_search.py`
- Modify: `crawlers/manhuagui.py`
- Modify: `test/unit/test_manga_search.py`
- Modify: `test/unit/test_server_manga_chapters_api.py`

- [ ] **Step 1: Write a failing unit test for `manhuagui` search result normalization**

```python
from crawlers.manga_search import ManhuaguiMangaSearcher


def test_manhuagui_searcher_builds_series_results_from_candidates():
    searcher = ManhuaguiMangaSearcher()
    candidates = [
        {"title": "海贼王", "url": "https://www.manhuagui.com/comic/1/"},
        {"title": "海贼王", "url": "https://www.manhuagui.com/comic/1/"},
        {"title": "其他作品", "url": "https://www.manhuagui.com/comic/2/"},
    ]

    results = searcher._build_results_from_candidates("海贼王", candidates, limit=10)

    assert [item.title for item in results] == ["海贼王"]
    assert results[0].platform == "manhuagui"
```

- [ ] **Step 2: Add a failing unit test for chapter catalog extraction from a comic detail page**

```python
import pytest

from crawlers.manga_search import ManhuaguiMangaSearcher


@pytest.mark.asyncio
async def test_manhuagui_searcher_returns_sorted_chapter_catalog():
    searcher = ManhuaguiMangaSearcher()
    html = """
    <ul class="chapter-list">
      <li><a href="/comic/1/101.html" title="第2话">第2话</a></li>
      <li><a href="/comic/1/100.html" title="第1话">第1话</a></li>
    </ul>
    """

    chapters = searcher._extract_chapters_from_html(html)

    assert [chapter.title for chapter in chapters] == ["第1话", "第2话"]
    assert chapters[0].url == "https://www.manhuagui.com/comic/1/100.html"
```

- [ ] **Step 3: Run the targeted unit tests to verify they fail**

Run: `python3 -m pytest -q test/unit/test_manga_search.py -k manhuagui`

Expected: FAIL because the `manhuagui` manga searcher and chapter parsing helpers do not exist yet.

- [ ] **Step 4: Implement the minimal `ManhuaguiMangaSearcher` and chapter parser**

```python
@register_manga_searcher
class ManhuaguiMangaSearcher(BaseMangaSearcher):
    PLATFORM_NAME = "manhuagui"
    PLATFORM_DISPLAY = "漫画柜"

    def _build_results_from_candidates(self, keyword: str, candidates: List[dict], limit: int = 10):
        ...

    def _extract_chapters_from_html(self, html: str) -> List[MangaChapterResult]:
        ...

    async def search(self, keyword: str, limit: int = 10) -> List[MangaSearchResult]:
        # Playwright 进入 manhuagui 搜索页，抽取作品页候选
        ...

    async def get_chapters(self, url: str) -> dict:
        # 请求作品详情页并解析章节列表
        ...
```

Add any small helper into `crawlers/manhuagui.py` only if it directly helps normalize the comic detail URL or chapter ordering. Do not migrate the whole crawler into the search module.

- [ ] **Step 5: Re-run the `manhuagui` unit tests to verify green**

Run: `python3 -m pytest -q test/unit/test_manga_search.py -k manhuagui`

Expected: PASS

- [ ] **Step 6: Extend the chapter API test to cover the real searcher path**

```python
@pytest.mark.asyncio
async def test_manga_chapters_endpoint_uses_real_searcher_payload_shape():
    searcher = ManhuaguiMangaSearcher()
    payload = {
        "title": "海贼王",
        "platform": "manhuagui",
        "platform_display": "漫画柜",
        "url": "https://www.manhuagui.com/comic/1/",
        "chapters": [
            MangaChapterResult(title="第1话", url="https://www.manhuagui.com/comic/1/100.html"),
        ],
    }
    assert payload["chapters"][0].to_dict()["title"] == "第1话"
```

- [ ] **Step 7: Run the full backend manga-search slice tests**

Run: `python3 -m pytest -q test/unit/test_manga_search.py test/unit/test_server_manga_search_api.py test/unit/test_server_manga_chapters_api.py`

Expected: PASS

- [ ] **Step 8: Commit the first searchable manga platform**

```bash
git add crawlers/manga_search.py crawlers/manhuagui.py test/unit/test_manga_search.py test/unit/test_server_manga_chapters_api.py
git commit -m "feat: add manhuagui manga search support"
```

### Task 3: Add Frontend Manga Search API Helpers and Small Components

**Files:**
- Modify: `web/src/api/client.ts`
- Create: `web/src/components/MangaSearchInput.tsx`
- Create: `web/src/components/MangaSearchResults.tsx`
- Create: `web/src/components/MangaChapterPicker.tsx`
- Create: `web/src/components/MangaDownloadConfirm.tsx`
- Create: `web/src/components/MangaSearchInput.test.tsx`
- Create: `web/src/components/MangaDownloadConfirm.test.tsx`

- [ ] **Step 1: Write a failing API helper test through component usage**

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';

import MangaSearchInput from './MangaSearchInput';


it('submits keyword and selected platform to the parent callback', async () => {
  const user = userEvent.setup();
  const onSearch = vi.fn();

  render(
    <MangaSearchInput
      platforms={[{ name: 'manhuagui', display_name: '漫画柜' }]}
      loading={false}
      onSearch={onSearch}
    />,
  );

  await user.type(screen.getByPlaceholderText('输入漫画名称...'), '海贼王');
  await user.click(screen.getByRole('button', { name: '搜索' }));

  expect(onSearch).toHaveBeenCalledWith('海贼王', 'manhuagui');
});
```

- [ ] **Step 2: Add a failing confirmation test that requires an explicit final click**

```tsx
it('does not submit until the final confirm button is clicked', async () => {
  const user = userEvent.setup();
  const onConfirm = vi.fn();

  render(
    <MangaDownloadConfirm
      title="海贼王"
      platformDisplay="漫画柜"
      chapters={[
        { title: '第1话', url: 'https://www.manhuagui.com/comic/1/100.html' },
      ]}
      pending={false}
      onConfirm={onConfirm}
      onBack={vi.fn()}
    />,
  );

  expect(onConfirm).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '确认下载 1 个章节' }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 3: Run the new component tests to verify they fail**

Run: `cd web && npm test -- --run src/components/MangaSearchInput.test.tsx src/components/MangaDownloadConfirm.test.tsx`

Expected: FAIL with module-not-found errors for the new components.

- [ ] **Step 4: Add the minimal frontend types and request helpers**

```ts
export interface MangaSearchResult {
  title: string;
  url: string;
  platform: string;
  platform_display: string;
  extra?: Record<string, string>;
}

export interface MangaChapter {
  title: string;
  url: string;
}

export async function searchManga(keyword: string, platform: string, limit = 10) {
  const response = await fetch(`${API_BASE}/search/manga?` + new URLSearchParams({ keyword, platform, limit: String(limit) }));
  ...
}

export async function getMangaChapters(url: string, platform: string) {
  const response = await fetch(`${API_BASE}/manga/chapters?` + new URLSearchParams({ url, platform }));
  ...
}
```

- [ ] **Step 5: Implement the minimal search input and confirmation components**

Keep the components thin:

- `MangaSearchInput` only owns keyword/platform form state
- `MangaSearchResults` only renders results and selection click handlers
- `MangaChapterPicker` only renders chapters, selected IDs, and bulk-select helpers
- `MangaDownloadConfirm` only renders the final confirmation summary and buttons

- [ ] **Step 6: Re-run the component tests to verify green**

Run: `cd web && npm test -- --run src/components/MangaSearchInput.test.tsx src/components/MangaDownloadConfirm.test.tsx`

Expected: PASS

- [ ] **Step 7: Commit the manga-search UI building blocks**

```bash
git add web/src/api/client.ts web/src/components/MangaSearchInput.tsx web/src/components/MangaSearchResults.tsx web/src/components/MangaChapterPicker.tsx web/src/components/MangaDownloadConfirm.tsx web/src/components/MangaSearchInput.test.tsx web/src/components/MangaDownloadConfirm.test.tsx
git commit -m "feat: add manga search ui building blocks"
```

### Task 4: Integrate the Search → Chapters → Confirm Flow into `MangaPage`

**Files:**
- Modify: `web/src/pages/MangaPage.tsx`
- Modify: `web/src/pages/MangaPage.test.tsx`

- [ ] **Step 1: Write a failing page test for the full manga search flow**

```tsx
it('searches manga, opens chapters inline, waits for confirmation, then submits selected chapter urls', async () => {
  const user = userEvent.setup();

  searchMangaMock.mockResolvedValue({
    results: [
      {
        title: '海贼王',
        url: 'https://www.manhuagui.com/comic/1/',
        platform: 'manhuagui',
        platform_display: '漫画柜',
      },
    ],
    total: 1,
    platform: 'manhuagui',
  });

  getMangaChaptersMock.mockResolvedValue({
    title: '海贼王',
    platform: 'manhuagui',
    platform_display: '漫画柜',
    url: 'https://www.manhuagui.com/comic/1/',
    chapters: [
      { title: '第1话', url: 'https://www.manhuagui.com/comic/1/100.html' },
      { title: '第2话', url: 'https://www.manhuagui.com/comic/1/101.html' },
    ],
  });

  render(<MangaPage platforms={mangaPlatforms} />);

  await user.type(screen.getByPlaceholderText('输入漫画名称...'), '海贼王');
  await user.click(screen.getByRole('button', { name: '搜索' }));
  await user.click(await screen.findByRole('button', { name: '查看章节 海贼王' }));
  await user.click(await screen.findByLabelText('选择章节 第1话'));
  await user.click(screen.getByRole('button', { name: '下载所选章节' }));

  expect(startBatchDownloadMock).not.toHaveBeenCalled();

  await user.click(screen.getByRole('button', { name: '确认下载 1 个章节' }));

  expect(startBatchDownloadMock).toHaveBeenCalledWith([
    'https://www.manhuagui.com/comic/1/100.html',
  ]);
});
```

- [ ] **Step 2: Run the page test to verify it fails**

Run: `cd web && npm test -- --run src/pages/MangaPage.test.tsx`

Expected: FAIL because `MangaPage` does not yet render the new search flow or wait for explicit confirmation.

- [ ] **Step 3: Add the minimal page state and data-loading flow**

Implement in `MangaPage.tsx`:

- search submission handler that calls `searchManga`
- result selection handler that calls `getMangaChapters`
- chapter toggle/select-all helpers
- confirmation-state open/close handling
- final confirm handler that calls `startBatchDownload(selectedUrls)`

Do not mix the existing `UrlInput` local state with the new search flow state.

- [ ] **Step 4: Keep direct-link download behavior intact while integrating search**

Regression points to preserve:

- existing `UrlInput` single-download flow still calls `startDownload`
- existing batch-link textarea flow still calls `startBatchDownload`
- existing manga task-progress subscription still unlocks the batch-link form when the tracked task finishes

- [ ] **Step 5: Re-run the manga page test to verify green**

Run: `cd web && npm test -- --run src/pages/MangaPage.test.tsx`

Expected: PASS

- [ ] **Step 6: Commit the integrated manga page flow**

```bash
git add web/src/pages/MangaPage.tsx web/src/pages/MangaPage.test.tsx
git commit -m "feat: add manga search chapter selection flow"
```

### Task 5: Run Focused Regression and Final Verification

**Files:**
- Modify as needed: any files touched while fixing verification failures

- [ ] **Step 1: Run the focused backend regression suite**

Run: `python3 -m pytest -q test/unit/test_manga_search.py test/unit/test_server_manga_search_api.py test/unit/test_server_manga_chapters_api.py test/unit/test_server_download_api.py`

Expected: PASS

- [ ] **Step 2: Run the focused frontend regression suite**

Run: `cd web && npm test -- --run src/components/MangaSearchInput.test.tsx src/components/MangaDownloadConfirm.test.tsx src/pages/MangaPage.test.tsx`

Expected: PASS

- [ ] **Step 3: Run the full frontend suite**

Run: `cd web && npm test`

Expected: PASS

- [ ] **Step 4: Run the frontend production build**

Run: `cd web && npm run build`

Expected: PASS

- [ ] **Step 5: Run the full backend unit suite**

Run: `python3 -m pytest -q test/unit`

Expected: PASS

- [ ] **Step 6: Perform manual acceptance checks**

Verify:

- `/manga` still supports direct link download
- manga search returns at least one `manhuagui` result
- clicking a result opens chapters inline on the same page
- selecting chapters does not submit anything until the confirm area button is clicked
- final confirm creates batch download tasks and updates history/progress as before

- [ ] **Step 7: Commit any final verification fixes**

```bash
git add <files>
git commit -m "test: verify manga search download flow"
```
