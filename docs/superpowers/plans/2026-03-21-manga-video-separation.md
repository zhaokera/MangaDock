# Manga / Video Separation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the current mixed downloader UI into dedicated `/manga` and `/video` pages, with route-level navigation and page-specific platform/history/progress behavior.

**Architecture:** Add client-side routing to the Vite app, make `/` redirect to `/manga`, and move mixed UI into two focused page containers. Introduce a single source of truth for platform type mapping so route rendering, history filtering, task filtering, and cross-type validation all use the same rules. Add minimal web test infrastructure first, then drive the split with route- and filtering-focused tests.

**Tech Stack:** React 18, TypeScript, Vite, react-router-dom, Vitest, Testing Library, existing FastAPI APIs

---

## File Structure

### Existing files to modify

- `web/package.json` - add router/test dependencies and scripts
- `web/vite.config.ts` - keep dev server config and add/shared Vitest config if preferred
- `web/src/main.tsx` - mount router-aware app entry if needed
- `web/src/App.tsx` - convert from mixed single-page UI to route shell
- `web/src/components/AppShell.tsx` - shared top navigation + page outlet layout
- `web/src/api/client.ts` - add shared content type helpers/types if kept close to API models
- `web/src/components/UrlInput.tsx` - parameterize by content type and update wrong-page validation messaging
- `web/src/components/SearchInput.tsx` - accept page-provided video platforms only and remove internal platform fetch
- `web/src/components/History.tsx` - filter displayed items by content type
- `web/src/components/DownloadProgress.tsx` - render only page-matching task state and page-specific copy

### New files to create

- `web/src/pages/MangaPage.tsx` - manga-only page composition
- `web/src/pages/VideoPage.tsx` - video-only page composition
- `web/src/components/AppNav.tsx` - top navigation for `/manga` and `/video`
- `web/src/components/AppShell.tsx` - shared shell with sticky header/nav and `<Outlet />`
- `web/src/lib/contentType.ts` - single source of truth for `platform -> manga|video`
- `web/src/test/setup.ts` - Testing Library + jest-dom setup
- `web/src/test/renderWithRouter.tsx` - shared test render helper
- `web/src/App.test.tsx` - route rendering and redirect coverage
- `web/src/lib/contentType.test.ts` - mapping/filtering coverage
- `web/src/components/History.test.tsx` - history filtering coverage
- `web/src/components/UrlInput.test.tsx` - wrong-page validation coverage

---

### Task 1: Add Web Routing and Test Harness

**Files:**
- Create: `web/src/test/setup.ts`
- Create: `web/src/test/renderWithRouter.tsx`
- Modify: `web/package.json`
- Modify: `web/package-lock.json`
- Modify: `web/vite.config.ts`
- Test: `web/src/App.test.tsx`

- [ ] **Step 1: Add the minimal dependencies and scripts required for red/green work**

```json
{
  "dependencies": {
    "react-router-dom": "^6.30.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.3.0",
    "@testing-library/user-event": "^14.6.1",
    "jsdom": "^25.0.1",
    "vitest": "^2.1.8"
  },
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 2: Configure Vitest setup before touching routing code**

```ts
// web/src/test/setup.ts
import '@testing-library/jest-dom';
```

```ts
// web/src/test/renderWithRouter.tsx
export function renderWithRouter(initialEntries = ['/']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <App />
    </MemoryRouter>,
  );
}
```

```ts
// web/vite.config.ts
test: {
  environment: 'jsdom',
  setupFiles: './src/test/setup.ts',
}
```

- [ ] **Step 3: Write the first failing route smoke test**

```tsx
// web/src/App.test.tsx
it('redirects / to /manga and renders the manga page navigation state', async () => {
  renderWithRouter(['/']);

  expect(await screen.findByRole('link', { name: '漫画下载' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByText('粘贴漫画章节链接')).toBeInTheDocument();
});
```

- [ ] **Step 4: Run the smoke test to verify it fails for the right reason**

Run: `cd web && npm test -- src/App.test.tsx`

Expected: FAIL because the current `App.tsx` has no router, no `/manga` redirect, and no route-aware navigation state.

- [ ] **Step 5: Commit the tooling baseline**

```bash
git add web/package.json web/package-lock.json web/vite.config.ts web/src/test/setup.ts web/src/test/renderWithRouter.tsx web/src/App.test.tsx
git commit -m "test: add web app test harness"
```

### Task 2: Create a Single Source of Truth for Content Type Mapping

**Files:**
- Create: `web/src/lib/contentType.ts`
- Create: `web/src/lib/contentType.test.ts`
- Modify: `web/src/api/client.ts`

- [ ] **Step 1: Write a failing test for platform-to-type mapping and collection filtering**

```ts
import { describe, expect, it } from 'vitest';
import { filterByContentType, getContentTypeForPlatform } from './contentType';

describe('content type mapping', () => {
  it('classifies known manga and video platforms', () => {
    expect(getContentTypeForPlatform('manhuagui')).toBe('manga');
    expect(getContentTypeForPlatform('tencent')).toBe('video');
  });

  it('filters mixed history records by page type', () => {
    const history = [
      { task_id: '1', platform: 'manhuagui' },
      { task_id: '2', platform: 'tencent' },
    ];

    expect(filterByContentType(history, 'manga')).toHaveLength(1);
    expect(filterByContentType(history, 'video')).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run the mapping test to verify it fails**

Run: `cd web && npm test -- src/lib/contentType.test.ts`

Expected: FAIL with module-not-found or missing export errors for `contentType.ts`.

- [ ] **Step 3: Implement the minimal shared mapper**

```ts
export type ContentType = 'manga' | 'video';

const VIDEO_PLATFORMS = new Set(['tencent', 'iqiyi', 'youku', 'mango', 'bilibili']);

export function getContentTypeForPlatform(platform?: string): ContentType {
  return VIDEO_PLATFORMS.has(platform || '') ? 'video' : 'manga';
}

export function filterByContentType<T extends { platform?: string }>(
  items: T[],
  contentType: ContentType,
) {
  return items.filter((item) => getContentTypeForPlatform(item.platform) === contentType);
}

export function getPlatformsForContentType<T extends { name: string }>(
  platforms: T[],
  contentType: ContentType,
) {
  return platforms.filter((platform) => getContentTypeForPlatform(platform.name) === contentType);
}
```

- [ ] **Step 4: Make API-derived platform helpers call the shared mapper instead of hardcoding lists again**

```ts
export interface SearchPlatform {
  name: string;
  display_name: string;
  type: ContentType;
}
```

```ts
// web/src/api/client.ts
const platforms = (data.platforms || []).map((p): SearchPlatform => ({
  ...p,
  type: getContentTypeForPlatform(p.name),
}));
```

- [ ] **Step 5: Run the mapping test again to verify green**

Run: `cd web && npm test -- src/lib/contentType.test.ts`

Expected: PASS

- [ ] **Step 6: Commit the shared content-type foundation**

```bash
git add web/src/lib/contentType.ts web/src/lib/contentType.test.ts web/src/api/client.ts
git commit -m "feat: add shared content type mapping"
```

### Task 3: Replace the Single-Page App with a Routed Shell

**Files:**
- Create: `web/src/components/AppNav.tsx`
- Create: `web/src/components/AppShell.tsx`
- Create: `web/src/pages/MangaPage.tsx`
- Create: `web/src/pages/VideoPage.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/main.tsx`
- Test: `web/src/App.test.tsx`

- [ ] **Step 1: Expand the route test to cover both pages before writing route code**

```tsx
it('navigates from manga to video and swaps page-specific hero text', async () => {
  const user = userEvent.setup();
  renderWithRouter(['/manga']);

  await user.click(screen.getByRole('link', { name: '视频下载' }));

  expect(await screen.findByText('搜索动漫 / 视频名称')).toBeInTheDocument();
  expect(screen.queryByText('粘贴漫画章节链接')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the route test to verify it fails**

Run: `cd web && npm test -- src/App.test.tsx`

Expected: FAIL because `App.tsx` still renders a mixed UI with no routed shell.

- [ ] **Step 3: Implement the minimal router shell and nav**

```tsx
// web/src/main.tsx
<BrowserRouter>
  <App />
</BrowserRouter>
```

```tsx
// web/src/components/AppShell.tsx
<header>
  <AppNav />
</header>
<main>
  <Outlet />
</main>
```

```tsx
// web/src/App.tsx
<Routes>
  <Route path="/" element={<Navigate to="/manga" replace />} />
  <Route element={<AppShell />}>
    <Route path="/manga" element={<MangaPage />} />
    <Route path="/video" element={<VideoPage />} />
  </Route>
</Routes>
```

```tsx
// web/src/components/AppNav.tsx
<NavLink to="/manga">漫画下载</NavLink>
<NavLink to="/video">视频下载</NavLink>
```

- [ ] **Step 4: Move page-specific layout into `MangaPage` and `VideoPage`**

```tsx
// MangaPage: hero + manga platforms + UrlInput + manga progress/history/help
// VideoPage: hero + video platforms + SearchInput + UrlInput + video progress/history
```

```tsx
// Page container data flow
const [allPlatforms, setAllPlatforms] = useState<Platform[]>([]);
const mangaPlatforms = getPlatformsForContentType(allPlatforms, 'manga');
const videoPlatforms = getPlatformsForContentType(allPlatforms, 'video');

<MangaPage allPlatforms={allPlatforms} platforms={mangaPlatforms} />
<VideoPage allPlatforms={allPlatforms} platforms={videoPlatforms} />
```

- [ ] **Step 5: Re-run route tests to verify green**

Run: `cd web && npm test -- src/App.test.tsx`

Expected: PASS

- [ ] **Step 6: Commit the routed shell**

```bash
git add web/src/App.tsx web/src/main.tsx web/src/components/AppNav.tsx web/src/components/AppShell.tsx web/src/pages/MangaPage.tsx web/src/pages/VideoPage.tsx web/src/App.test.tsx
git commit -m "feat: split app into manga and video routes"
```

### Task 4: Filter History and Progress by Page Type

**Files:**
- Modify: `web/src/components/History.tsx`
- Modify: `web/src/components/DownloadProgress.tsx`
- Create: `web/src/components/History.test.tsx`
- Modify: `web/src/pages/MangaPage.tsx`
- Modify: `web/src/pages/VideoPage.tsx`
- Modify: `web/src/App.test.tsx`

- [ ] **Step 1: Write a failing history filtering test**

```tsx
vi.mock('../api/client', () => ({
  getHistory: vi.fn().mockResolvedValue({
    history: [
      { task_id: '1', platform: 'manhuagui', title: 'A', chapter: '1', page_count: 12, created_at: '2026-03-21T00:00:00Z' },
      { task_id: '2', platform: 'tencent', title: 'B', chapter: 'EP1', page_count: 1, created_at: '2026-03-21T00:00:00Z' },
    ],
  }),
  getDownloadUrl: vi.fn(),
}));

it('shows only manga history on the manga page', async () => {
  render(<History contentType="manga" />);

  expect(await screen.findByText('A')).toBeInTheDocument();
  expect(screen.queryByText('B')).not.toBeInTheDocument();
});
```

- [ ] **Step 2: Run the history test to verify it fails**

Run: `cd web && npm test -- src/components/History.test.tsx`

Expected: FAIL because `History` currently has no `contentType` prop and renders all items.

- [ ] **Step 3: Add `contentType` props and filter logic**

```tsx
interface HistoryProps {
  contentType: ContentType;
}

const filteredHistory = filterByContentType(history, contentType);
```

```tsx
interface DownloadProgressProps {
  status: TaskStatus | null;
  contentType: ContentType;
}
```

Also make page-specific copy explicit in the component contract:

```tsx
<History contentType="manga" emptyTitle="暂无漫画下载记录" emptyHint="下载的漫画会显示在这里" />
<History contentType="video" emptyTitle="暂无视频下载记录" emptyHint="下载的视频会显示在这里" />
```

```tsx
<DownloadProgress contentType="manga" idleLabel="漫画下载进度" />
<DownloadProgress contentType="video" idleLabel="视频下载进度" />
```

- [ ] **Step 4: Keep one task slot per page type at the page-container level**

```tsx
function MangaPage() {
  const [task, setTask] = useState<TaskStatus | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => () => unsubscribeRef.current?.(), []);
}
```

Do the same in `VideoPage.tsx`, so each page owns its own task state and subscription cleanup.

```tsx
it('does not keep video progress visible after navigating back to manga', async () => {
  renderWithRouter(['/video']);

  startFakeVideoTask();
  await screen.findByText('下载中');

  await user.click(screen.getByRole('link', { name: '漫画下载' }));

  expect(screen.queryByText('下载中')).not.toBeInTheDocument();
});
```

- [ ] **Step 5: Re-run filtering tests**

Run: `cd web && npm test -- src/components/History.test.tsx src/App.test.tsx`

Expected: PASS

- [ ] **Step 6: Add one assertion for page-specific empty-state copy**

```tsx
it('shows video-specific empty copy on the video page', async () => {
  mockGetHistory([]);
  render(<History contentType="video" emptyTitle="暂无视频下载记录" emptyHint="下载的视频会显示在这里" />);

  expect(await screen.findByText('暂无视频下载记录')).toBeInTheDocument();
  expect(screen.getByText('下载的视频会显示在这里')).toBeInTheDocument();
});
```

- [ ] **Step 7: Commit page-scoped history/progress behavior**

```bash
git add web/src/components/History.tsx web/src/components/DownloadProgress.tsx web/src/components/History.test.tsx web/src/pages/MangaPage.tsx web/src/pages/VideoPage.tsx
git commit -m "feat: scope history and progress by content type"
```

### Task 5: Add Wrong-Page Validation and Keep Video Search Video-Only

**Files:**
- Modify: `web/src/components/UrlInput.tsx`
- Modify: `web/src/components/SearchInput.tsx`
- Create: `web/src/components/UrlInput.test.tsx`
- Modify: `web/src/pages/MangaPage.tsx`
- Modify: `web/src/pages/VideoPage.tsx`

- [ ] **Step 1: Write failing wrong-page validation tests**

```tsx
it('tells the user to switch to video when a video link is pasted on the manga page', async () => {
  render(
    <UrlInput
      contentType="manga"
      disabled={false}
      onDownload={vi.fn()}
      platforms={[
        { name: 'manhuagui', display_name: '漫画柜', patterns: ['manhuagui\\.com'] },
        { name: 'tencent', display_name: '腾讯视频', patterns: ['v\\.qq\\.com'] },
      ]}
    />
  );

  await user.type(screen.getByRole('textbox'), 'https://v.qq.com/x/cover/abc/xyz.html');
  await user.click(screen.getByRole('button', { name: '开始下载' }));

  expect(await screen.findByText('当前是漫画下载页，请切换到视频下载')).toBeInTheDocument();
});
```

- [ ] **Step 2: Run the validation test to verify it fails**

Run: `cd web && npm test -- src/components/UrlInput.test.tsx`

Expected: FAIL because `UrlInput` currently validates against an undifferentiated platform list and cannot produce type-aware guidance.

- [ ] **Step 3: Update `UrlInput` to accept page type and page-filtered platforms**

```tsx
interface UrlInputProps {
  contentType: ContentType;
  platforms: Platform[];
  allPlatforms: Platform[];
}
```

```ts
const matchedPlatform = findMatchingPlatform(url, allPlatforms);

if (matchedPlatform && getContentTypeForPlatform(matchedPlatform.name) !== contentType) {
  setError(contentType === 'manga'
    ? '当前是漫画下载页，请切换到视频下载'
    : '当前是视频下载页，请切换到漫画下载');
  return;
}
```

- [ ] **Step 4: Ensure `SearchInput` is mounted only in `VideoPage` and only receives video platforms**

```tsx
// VideoPage.tsx
<SearchInput
  platforms={getPlatformsForContentType(allPlatforms, 'video')}
  onSearch={...}
  onResultSelect={...}
/>
```

```tsx
// SearchInput.tsx
interface SearchInputProps {
  platforms: SearchPlatform[];
  onSearch: (keyword: string, platform?: string) => void;
  onResultSelect: (result: SearchResult) => void;
}
```

`MangaPage.tsx` must not import or render `SearchInput`, and `SearchInput.tsx` must remove its internal `getSearchPlatforms()` fetch and use only the `platforms` prop provided by `VideoPage`.

- [ ] **Step 5: Re-run validation and route tests**

Run: `cd web && npm test -- src/components/UrlInput.test.tsx src/App.test.tsx`

Expected: PASS

- [ ] **Step 6: Commit page-type validation and video-only search**

```bash
git add web/src/components/UrlInput.tsx web/src/components/SearchInput.tsx web/src/components/UrlInput.test.tsx web/src/pages/MangaPage.tsx web/src/pages/VideoPage.tsx
git commit -m "feat: enforce page specific download flows"
```

### Task 6: Verify Build and Run the Manual Acceptance Checklist

**Files:**
- Modify: `docs/superpowers/specs/2026-03-21-manga-video-separation-design.md` (only if implementation reveals a spec mismatch)

- [ ] **Step 1: Run the full web test suite**

Run: `cd web && npm test`

Expected: PASS

- [ ] **Step 2: Run a production build**

Run: `cd web && npm run build`

Expected: PASS with no TypeScript or Vite errors

- [ ] **Step 3: Manually verify the approved spec behaviors**

Run the dev server and check:

```bash
cd web && npm run dev -- --host 0.0.0.0
```

Checklist:
- `/` redirects to `/manga`
- nav switches between `/manga` and `/video`
- manga page contains only manga platforms and manga download UI
- video page contains video search plus video direct-link download UI
- video page filter chips contain only video platforms
- manga page empty/history/help copy uses manga wording; video page uses video wording
- wrong-page links show explicit switch-page guidance
- history and progress do not leak across page types

- [ ] **Step 4: Commit the verified feature**

```bash
git add web
git commit -m "feat: separate manga and video pages"
```
