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
  }: {
    status: {
      task_id: string;
      status: string;
      message: string;
      platform?: string;
    } | null;
    contentType: string;
    idleLabel?: string;
  }) => (
    <div data-testid="download-progress">
      {contentType}:{idleLabel}:{status?.status ?? 'idle'}:{status?.task_id ?? 'none'}:{status?.message ?? 'none'}
    </div>
  ),
}));

const videoPlatforms = [
  { name: 'iqiyi', display_name: '爱奇艺', patterns: ['iqiyi\\.com'] },
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
