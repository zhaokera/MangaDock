import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import VideoPage from './VideoPage';

const { startDownloadMock, subscribeProgressMock } = vi.hoisted(() => ({
  startDownloadMock: vi.fn(),
  subscribeProgressMock: vi.fn(),
}));

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');

  return {
    ...actual,
    startDownload: startDownloadMock,
    subscribeProgress: subscribeProgressMock,
  };
});

vi.mock('../components/SearchInput', () => ({
  default: ({
    onResultSelect,
  }: {
    platforms?: unknown[];
    onSearch: (keyword: string, platform?: string) => void;
    onResultSelect: (result: {
      title: string;
      url: string;
      platform: string;
      platform_display: string;
      score: number;
    }) => void;
  }) => (
    <div data-testid="search-input">
      <button
        type="button"
        onClick={() =>
          onResultSelect({
            title: '灌篮高手',
            url: 'https://example.com/video',
            platform: 'iqiyi',
            platform_display: '爱奇艺',
            score: 100,
          })
        }
      >
        触发下载
      </button>
    </div>
  ),
}));

vi.mock('../components/History', () => ({
  default: () => <div data-testid="history">history</div>,
}));

vi.mock('../components/DownloadProgress', () => ({
  default: ({
    status,
    contentType,
    idleLabel,
    onRetry,
  }: {
    status: {
      task_id: string;
      status: string;
      message: string;
      platform?: string;
    } | null;
    contentType: string;
    idleLabel?: string;
    onRetry?: () => void;
  }) => (
    <div data-testid="download-progress">
      {contentType}:{idleLabel}:{status?.status ?? 'idle'}:{status?.task_id ?? 'none'}:{status?.message ?? 'none'}
      {status?.status === 'failed' && onRetry && (
        <button type="button" onClick={onRetry}>
          重试当前任务
        </button>
      )}
    </div>
  ),
}));

const videoPlatforms = [
  { name: 'iqiyi', display_name: '爱奇艺', patterns: ['iqiyi\\.com'], type: 'video' as const },
];

beforeEach(() => {
  startDownloadMock.mockResolvedValue({ task_id: 'task-video-1', platform: 'iqiyi' });
  subscribeProgressMock.mockImplementation(() => vi.fn());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it('shows a pending video task immediately after selecting a search result', async () => {
  const user = userEvent.setup();

  render(<VideoPage platforms={videoPlatforms} />);

  await user.click(screen.getByRole('button', { name: '触发下载' }));

  await waitFor(() => {
    expect(startDownloadMock).toHaveBeenCalledWith('https://example.com/video');
  });

  expect(screen.getByTestId('download-progress')).toHaveTextContent(
    'video:视频下载进度:pending:task-video-1',
  );
  expect(subscribeProgressMock).toHaveBeenCalledWith('task-video-1', expect.any(Function));
});

it('renders active download progress before the search section', async () => {
  const user = userEvent.setup();

  render(<VideoPage platforms={videoPlatforms} />);

  await user.click(screen.getByRole('button', { name: '触发下载' }));

  await waitFor(() => {
    expect(screen.getByTestId('download-progress')).toBeInTheDocument();
  });

  const progress = screen.getByTestId('download-progress');
  const searchInput = screen.getByTestId('search-input');

  expect(progress.compareDocumentPosition(searchInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it('retries a failed video task with the last requested url', async () => {
  const user = userEvent.setup();

  subscribeProgressMock.mockImplementation((taskId: string, onProgress: (status: unknown) => void) => {
    onProgress({
      task_id: taskId,
      status: 'failed',
      progress: 0,
      total: 1,
      message: '下载失败',
      platform: 'iqiyi',
      manga_info: null,
      zip_path: null,
      error: 'HTTP 403',
    });

    return vi.fn();
  });

  render(<VideoPage platforms={videoPlatforms} />);

  await user.click(screen.getByRole('button', { name: '触发下载' }));

  await waitFor(() => {
    expect(screen.getByRole('button', { name: '重试当前任务' })).toBeInTheDocument();
  });

  await user.click(screen.getByRole('button', { name: '重试当前任务' }));

  await waitFor(() => {
    expect(startDownloadMock).toHaveBeenCalledTimes(2);
  });

  expect(startDownloadMock).toHaveBeenNthCalledWith(1, 'https://example.com/video');
  expect(startDownloadMock).toHaveBeenNthCalledWith(2, 'https://example.com/video');
});
