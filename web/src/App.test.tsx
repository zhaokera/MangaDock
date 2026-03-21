import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import App from './App';
import DownloadProgress from './components/DownloadProgress';
import { renderWithRouter } from './test/renderWithRouter';

vi.mock('./api/client', () => ({
  getPlatforms: vi.fn().mockResolvedValue({ platforms: [] }),
  getHistory: vi.fn().mockResolvedValue({ history: [] }),
  getDownloadUrl: vi.fn((taskId: string) => `/api/files/${taskId}`),
  startDownload: vi.fn().mockResolvedValue({ task_id: 'task-1', platform: 'tencent' }),
  subscribeProgress: vi.fn((taskId: string, onProgress: (status: unknown) => void) => {
    onProgress({
      task_id: taskId,
      status: 'downloading',
      progress: 1,
      total: 3,
      message: '下载中',
      platform: 'tencent',
      manga_info: null,
      zip_path: null,
      error: null,
    });

    return vi.fn();
  }),
}));

vi.mock('./components/SearchInput', () => ({
  default: ({
    onResultSelect,
  }: {
    platforms?: unknown[];
    onResultSelect: (result: { title: string; url: string; platform: string; platform_display: string; score: number }) => void;
  }) => (
    <button
      type="button"
      onClick={() =>
        onResultSelect({
          title: '视频示例',
          url: 'https://example.com/video',
          platform: 'tencent',
          platform_display: '腾讯视频',
          score: 100,
        })
      }
    >
      触发下载
    </button>
  ),
}));

it('redirects / to /manga and renders the manga page navigation state', async () => {
  renderWithRouter(<App />, ['/']);

  expect(await screen.findByRole('link', { name: '漫画下载' })).toHaveAttribute('aria-current', 'page');
  expect(screen.getByText('粘贴漫画章节链接')).toBeInTheDocument();
});

it('navigates from manga to video and swaps page-specific hero text', async () => {
  const user = userEvent.setup();
  renderWithRouter(<App />, ['/manga']);

  const inactiveVideoLink = screen
    .getAllByRole('link', { name: '视频下载' })
    .find((link) => link.getAttribute('aria-current') !== 'page');

  expect(inactiveVideoLink).toBeDefined();
  await user.click(inactiveVideoLink!);

  expect(await screen.findByText('搜索动漫 / 视频名称')).toBeInTheDocument();
  const activeVideoLink = screen
    .getAllByRole('link', { name: '视频下载' })
    .find((link) => link.getAttribute('aria-current') === 'page');

  expect(activeVideoLink).toBeDefined();
});

it('navigates to the dl-expo standalone page', async () => {
  const user = userEvent.setup();
  const { container } = renderWithRouter(<App />, ['/manga']);
  const scoped = within(container);

  await user.click(scoped.getAllByRole('link', { name: '糯米影视' })[0]);

  expect(await scoped.findByText('糯米影视专站搜索')).toBeInTheDocument();
  expect(scoped.queryByText('搜索动漫 / 视频名称')).not.toBeInTheDocument();
});

it('renders arbitrary UI inside a memory router', () => {
  renderWithRouter(<div>router smoke</div>, ['/video']);

  expect(screen.getByText('router smoke')).toBeInTheDocument();
});

it('clears video progress after navigating back to manga', async () => {
  const user = userEvent.setup();
  const { container } = renderWithRouter(<App />, ['/video']);
  const scoped = within(container);

  await user.click(scoped.getAllByRole('button', { name: '触发下载' })[0]);
  expect(await scoped.findByText('下载中')).toBeInTheDocument();

  await user.click(scoped.getAllByRole('link', { name: '漫画下载' })[0]);

  expect(scoped.queryByText('下载中')).not.toBeInTheDocument();
});

it('hides a mismatched task in DownloadProgress', () => {
  const { container } = render(
    <DownloadProgress
      contentType="manga"
      status={{
        task_id: 'task-1',
        status: 'downloading',
        progress: 1,
        total: 3,
        message: '下载中',
        platform: 'tencent',
        manga_info: null,
        zip_path: null,
        error: null,
      }}
    />,
  );

  expect(container).toBeEmptyDOMElement();
  expect(within(container).queryByText('下载中')).not.toBeInTheDocument();
});
