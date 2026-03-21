# dl-expo Standalone Video Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `/dl-expo` page that supports `www.dl-expo.com` search and video downloads without mixing this site into the generic `/video` experience.

**Architecture:** Extend the existing platform registry and search registry with a new `dl_expo` video platform, then add a dedicated frontend route and page container for the site. Reuse the existing download APIs, history store, and progress UI where possible, but keep routing, copy, search behavior, and filtering isolated to the new page.

**Tech Stack:** FastAPI, Python crawler/search registry, React 18, TypeScript, Vite, react-router-dom, Vitest, Testing Library, pytest

---

## File Structure

### Existing files to modify

- `crawlers/search.py` - register a `dl_expo` searcher and add any small base helpers needed for MacCMS-style result parsing
- `crawlers/registry.py` - no behavioral change expected, but plan assumes new crawler auto-registers through the existing import path
- `server.py` - include `dl_expo` in the video platform set exposed by `/api/platforms`
- `web/src/App.tsx` - add `/dl-expo` route and platform filtering for the dedicated page
- `web/src/components/AppNav.tsx` - add the dedicated nav entry
- `web/src/components/UrlInput.tsx` - allow site-specific accepted platforms and wrong-page messaging
- `web/src/lib/contentType.ts` - classify `dl_expo` as `video`
- `web/src/App.test.tsx` - extend route and nav coverage
- `web/src/components/UrlInput.test.tsx` - extend wrong-page validation coverage
- `test/unit/test_search.py` - extend registry/search parsing coverage
- `test/unit/test_server_search_api.py` - add `/api/search` coverage for `platform=dl_expo`

### New files to create

- `crawlers/dl_expo.py` - dedicated crawler for URL matching, metadata extraction, and video URL extraction
- `test/unit/test_crawler_dl_expo.py` - crawler parsing and extraction regression tests
- `test/unit/test_server_platforms_api.py` - API coverage for `/api/platforms` exposing `dl_expo`
- `web/src/pages/DlExpoPage.tsx` - dedicated standalone site page
- `web/src/pages/DlExpoPage.test.tsx` - page-level pending-state and site-specific UI coverage

---

### Task 1: Add the `dl_expo` Platform to Shared Classification and Routing

**Files:**
- Modify: `web/src/lib/contentType.ts`
- Modify: `web/src/lib/contentType.test.ts`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/AppNav.tsx`
- Modify: `web/src/App.test.tsx`
- Create: `web/src/pages/DlExpoPage.tsx`

- [ ] **Step 1: Extend the shared content-type test with the new platform**

```ts
it('classifies dl_expo as a video platform', () => {
  expect(getContentTypeForPlatform('dl_expo')).toBe('video');
});
```

- [ ] **Step 2: Run the mapping test to verify it fails**

Run: `cd web && npm test -- --run src/lib/contentType.test.ts`

Expected: FAIL because `dl_expo` is not yet in the video platform set.

- [ ] **Step 3: Add `dl_expo` to the shared platform mapping**

```ts
const VIDEO_PLATFORMS = new Set(['tencent', 'iqiyi', 'youku', 'mango', 'bilibili', 'dl_expo']);
```

- [ ] **Step 4: Add a failing route test for the new dedicated page**

```tsx
it('navigates to the dl-expo standalone page', async () => {
  const user = userEvent.setup();
  renderWithRouter(<App />, ['/manga']);

  await user.click(screen.getByRole('link', { name: '糯米影视' }));

  expect(await screen.findByText('糯米影视专站搜索')).toBeInTheDocument();
  expect(screen.queryByText('搜索动漫 / 视频名称')).not.toBeInTheDocument();
});
```

- [ ] **Step 5: Run the route test to verify it fails**

Run: `cd web && npm test -- --run src/App.test.tsx`

Expected: FAIL because the nav and route do not exist yet.

- [ ] **Step 6: Implement the minimal route, nav entry, and page shell**

```tsx
// web/src/App.tsx
<Route path="dl-expo" element={<DlExpoPage platforms={dlExpoPlatforms} />} />
```

```tsx
// web/src/components/AppNav.tsx
<NavLink to="/dl-expo">糯米影视</NavLink>
```

```tsx
// web/src/pages/DlExpoPage.tsx
export default function DlExpoPage() {
  return <h2>糯米影视专站搜索</h2>;
}
```

- [ ] **Step 7: Run both route and mapping tests to verify green**

Run: `cd web && npm test -- --run src/lib/contentType.test.ts src/App.test.tsx`

Expected: PASS

- [ ] **Step 8: Commit the shared route/classification foundation**

```bash
git add web/src/lib/contentType.ts web/src/lib/contentType.test.ts web/src/App.tsx web/src/components/AppNav.tsx web/src/pages/DlExpoPage.tsx web/src/App.test.tsx
git commit -m "feat: add dl-expo standalone route"
```

### Task 2: Add Backend Platform Exposure for `dl_expo`

**Files:**
- Modify: `server.py`
- Create: `test/unit/test_server_platforms_api.py`

- [ ] **Step 1: Write a failing API test for `/api/platforms`**

```python
from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

def test_platforms_endpoint_exposes_dl_expo_as_video():
    response = client.get("/api/platforms")

    assert response.status_code == 200
    dl_expo = next(item for item in response.json()["platforms"] if item["name"] == "dl_expo")
    assert dl_expo["display_name"] == "糯米影视"
    assert dl_expo["type"] == "video"
```

- [ ] **Step 2: Run the API test to verify it fails**

Run: `python3 -m pytest -q test/unit/test_server_platforms_api.py`

Expected: FAIL because `dl_expo` is not yet returned by `/api/platforms`.

- [ ] **Step 3: Implement the minimal backend exposure**

```python
# server.py
video_platforms = {'tencent', 'iqiyi', 'youku', 'mango', 'bilibili', 'dl_expo'}
```

This step depends on the crawler in Task 3 existing and auto-registering.

- [ ] **Step 4: Run the API test again to verify green**

Run: `python3 -m pytest -q test/unit/test_server_platforms_api.py`

Expected: PASS

- [ ] **Step 5: Commit the platform exposure**

```bash
git add server.py test/unit/test_server_platforms_api.py
git commit -m "feat: expose dl-expo platform metadata"
```

### Task 3: Implement the `dl_expo` Crawler for URL Parsing and Download Extraction

**Files:**
- Create: `crawlers/dl_expo.py`
- Create: `test/unit/test_crawler_dl_expo.py`

- [ ] **Step 1: Write failing crawler tests for URL matching and metadata extraction**

```python
from crawlers.dl_expo import DlExpoCrawler

def test_can_handle_play_and_detail_urls():
    assert DlExpoCrawler.can_handle("https://www.dl-expo.com/play/101100/2-1.html")
    assert DlExpoCrawler.can_handle("https://www.dl-expo.com/voddetail/101100.html")

def test_extract_ids_from_play_url():
    crawler = DlExpoCrawler()
    assert crawler._extract_ids("https://www.dl-expo.com/play/101100/2-1.html") == ("101100", "2-1")

def test_extract_video_urls_strips_trailing_javascript():
    crawler = DlExpoCrawler()
    html = 'player_aaaa={"url":"https://cdn.example.com/video/index.m3u8","from":"line1"};'
    assert crawler._extract_video_urls_from_content(html) == ["https://cdn.example.com/video/index.m3u8"]
```

- [ ] **Step 2: Run the crawler test to verify it fails**

Run: `python3 -m pytest -q test/unit/test_crawler_dl_expo.py`

Expected: FAIL with module-not-found or missing method errors.

- [ ] **Step 3: Implement the minimal crawler skeleton**

```python
@register_crawler
class DlExpoCrawler(BaseCrawler):
    PLATFORM_NAME = "dl_expo"
    PLATFORM_DISPLAY_NAME = "糯米影视"
    URL_PATTERNS = [
        r"dl-expo\.com/play/\d+/\d+-\d+\.html",
        r"dl-expo\.com/voddetail/\d+\.html",
    ]
```

- [ ] **Step 4: Add helper methods for play/detail URL parsing and candidate extraction**

Implement:

- `_extract_ids(url: str) -> tuple[str | None, str | None]`
- `_extract_video_urls_from_content(page_content: str) -> List[str]`
- detail-page fallback that resolves a default play URL when only `/voddetail/{id}.html` is provided

- [ ] **Step 5: Run the crawler test again to verify green**

Run: `python3 -m pytest -q test/unit/test_crawler_dl_expo.py`

Expected: PASS

- [ ] **Step 6: Add one failing test for completed download progress using a sync callback**

```python
@pytest.mark.asyncio
async def test_download_uses_existing_progress_compatibility(monkeypatch, tmp_path):
    ...
```

This test should assert that `download()` reports completion without raising `NoneType can't be used in 'await' expression`.

- [ ] **Step 7: Implement the minimal download path**

Use the existing video-crawler pattern:

- `start_browser()`
- `page.goto(...)`
- `page.content()`
- `self._emit_progress(...)`

Prefer `mp4` first, then `m3u8`. If only `m3u8` is found and the repository lacks reusable segment support, raise `ValueError("未找到 dl-expo 可下载视频地址")`.

- [ ] **Step 8: Run the crawler suite to verify green**

Run: `python3 -m pytest -q test/unit/test_crawler_dl_expo.py test/unit/test_crawler_base.py -k dl_expo`

Expected: PASS

- [ ] **Step 9: Commit the crawler**

```bash
git add crawlers/dl_expo.py test/unit/test_crawler_dl_expo.py
git commit -m "feat: add dl-expo crawler"
```

### Task 4: Implement the `dl_expo` Searcher and Search API Coverage

**Files:**
- Modify: `crawlers/search.py`
- Modify: `test/unit/test_search.py`
- Modify: `test/unit/test_server_search_api.py`

- [ ] **Step 1: Write a failing unit test for the new searcher registration and result normalization**

```python
def test_get_searcher_returns_dl_expo_searcher():
    searcher = get_searcher("dl_expo")
    assert searcher.PLATFORM_NAME == "dl_expo"

def test_dl_expo_searcher_builds_results_from_maccms_candidates():
    searcher = DlExpoSearcher()
    candidates = [
        {"title": "灌篮高手", "url": "/voddetail/101100.html"},
        {"title": "灌篮高手", "url": "/play/101100/2-1.html"},
    ]

    results = searcher._build_results_from_candidates("灌篮高手", candidates, limit=10)

    assert results[0].platform == "dl_expo"
    assert results[0].url.startswith("https://www.dl-expo.com/")
```

- [ ] **Step 2: Run the search unit test to verify it fails**

Run: `python3 -m pytest -q test/unit/test_search.py -k dl_expo`

Expected: FAIL because the searcher is not registered.

- [ ] **Step 3: Implement the minimal `DlExpoSearcher`**

Add to `crawlers/search.py`:

- `PLATFORM_NAME = "dl_expo"`
- `PLATFORM_DISPLAY = "糯米影视"`
- a dedicated `search()` that fetches the site search page with Playwright
- candidate extraction from MacCMS-style result cards
- URL normalization that prefixes relative URLs with `https://www.dl-expo.com`

- [ ] **Step 4: Add a failing API test for `platform=dl_expo`**

```python
def test_search_api_supports_dl_expo_platform(monkeypatch):
    ...
```

The test should patch `server.get_searcher()` or `DlExpoSearcher.search()` and assert `/api/search` returns `platform == "dl_expo"`.

- [ ] **Step 5: Run the API test to verify it fails**

Run: `python3 -m pytest -q test/unit/test_server_search_api.py -k dl_expo`

Expected: FAIL before the new searcher is available.

- [ ] **Step 6: Wire the searcher into the existing registry and API flow**

No new endpoint is needed. The work is complete when:

- `get_searcher("dl_expo")` resolves
- `/api/search` accepts `platform=dl_expo`
- result URLs are normalized to absolute site URLs

- [ ] **Step 7: Run the search regression suite to verify green**

Run: `python3 -m pytest -q test/unit/test_search.py test/unit/test_server_search_api.py -k dl_expo`

Expected: PASS

- [ ] **Step 8: Commit the search support**

```bash
git add crawlers/search.py test/unit/test_search.py test/unit/test_server_search_api.py
git commit -m "feat: add dl-expo search support"
```

### Task 5: Build the Dedicated `/dl-expo` Page Behavior

**Files:**
- Modify: `web/src/components/UrlInput.tsx`
- Modify: `web/src/components/UrlInput.test.tsx`
- Create: `web/src/pages/DlExpoPage.tsx`
- Create: `web/src/pages/DlExpoPage.test.tsx`

- [ ] **Step 1: Write a failing page test for immediate pending feedback**

```tsx
it('shows a pending task immediately after selecting a dl-expo search result', async () => {
  ...
});
```

The test should mirror the current `VideoPage` pattern:

- mock `startDownload` to resolve `{ task_id: 'task-dl-1', platform: 'dl_expo' }`
- mock `subscribeProgress` without sending any SSE payload
- click a mocked search result
- assert the page renders the pending progress card immediately

- [ ] **Step 2: Run the page test to verify it fails**

Run: `cd web && npm test -- --run src/pages/DlExpoPage.test.tsx`

Expected: FAIL because the page does not exist.

- [ ] **Step 3: Implement the page composition**

`web/src/pages/DlExpoPage.tsx` should:

- render a dedicated hero and site-specific help copy
- trigger search requests with `platform='dl_expo'`
- set a local pending task immediately after `startDownload()`
- subscribe to task progress
- pass `contentType="video"` to the shared progress/history components

- [ ] **Step 4: Extend `UrlInput` with site-specific accepted platforms and messaging**

Add a prop similar to:

```ts
allowedPlatforms?: string[]
wrongPageMessage?: string
```

Then use it in `DlExpoPage` so only `dl_expo` links are accepted there.

- [ ] **Step 5: Add a failing validation test for wrong-site links**

```tsx
it('rejects non dl-expo links on the standalone page', async () => {
  ...
});
```

- [ ] **Step 6: Run the page and URL-input tests to verify they fail for the right reason**

Run: `cd web && npm test -- --run src/pages/DlExpoPage.test.tsx src/components/UrlInput.test.tsx`

Expected: FAIL because the new props and page-specific validation do not exist yet.

- [ ] **Step 7: Implement the minimal validation and site-specific copy**

Required copy:

- Hero title containing `糯米影视专站搜索`
- site help mentioning `www.dl-expo.com`
- wrong-link guidance that tells the user to switch to the matching page

- [ ] **Step 8: Run the frontend regression suite to verify green**

Run: `cd web && npm test -- --run src/App.test.tsx src/pages/DlExpoPage.test.tsx src/components/UrlInput.test.tsx`

Expected: PASS

- [ ] **Step 9: Commit the page behavior**

```bash
git add web/src/pages/DlExpoPage.tsx web/src/pages/DlExpoPage.test.tsx web/src/components/UrlInput.tsx web/src/components/UrlInput.test.tsx web/src/App.tsx web/src/App.test.tsx
git commit -m "feat: add dl-expo standalone page"
```

### Task 6: Run End-to-End Verification for the New Dedicated Flow

**Files:**
- Modify as needed: any files from Tasks 1-5 if verification reveals bugs

- [ ] **Step 1: Run the full backend regression suite for the new platform**

Run:

```bash
python3 -m pytest -q test/unit/test_crawler_base.py test/unit/test_crawler_dl_expo.py test/unit/test_search.py test/unit/test_server_search_api.py test/unit/test_server_platforms_api.py
```

Expected: PASS

- [ ] **Step 2: Run the focused frontend regression suite**

Run:

```bash
cd web && npm test -- --run src/App.test.tsx src/pages/DlExpoPage.test.tsx src/components/UrlInput.test.tsx
```

Expected: PASS

- [ ] **Step 3: Run the frontend production build**

Run:

```bash
cd web && npm run build
```

Expected: PASS

- [ ] **Step 4: Perform manual verification with the running app**

Check:

- `/dl-expo` route loads
- nav highlights the dedicated page
- searching from the page calls only the `dl_expo` platform
- clicking a result immediately shows pending progress
- a valid `dl-expo.com/play/...` link is accepted
- a Tencent / IQIYI link is rejected with the dedicated message

- [ ] **Step 5: Commit any final verification fixes**

```bash
git add .
git commit -m "test: verify dl-expo standalone flow"
```
