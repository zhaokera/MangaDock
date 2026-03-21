import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DlExpoPage from './DlExpoPage';

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
    lockedPlatform,
    hidePlatformSelector,
  }: {
    platforms?: unknown[];
    onSearch: (keyword: string, platform?: string) => void;
    lockedPlatform?: string;
    hidePlatformSelector?: boolean;
    onResultSelect: (result: {
      title: string;
      url: string;
      platform: string;
      platform_display: string;
      score: number;
    }) => void;
  }) => (
    <div>
      <div data-testid="search-input-props">
        {lockedPlatform ?? 'none'}:{hidePlatformSelector ? 'hidden' : 'visible'}
      </div>
      <button
        type="button"
        onClick={() =>
          onResultSelect({
            title: '糯米影视资源',
            url: 'https://www.dl-expo.com/resource/abc',
            platform: 'dl_expo',
            platform_display: '糯米影视',
            score: 98,
          })
        }
      >
        触发专站下载
      </button>
    </div>
  ),
}));

vi.mock('../components/History', () => ({
  default: ({ allowedPlatforms }: { allowedPlatforms?: string[] }) => (
    <div data-testid="history">{allowedPlatforms?.join(',') ?? 'all'}</div>
  ),
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
      {contentType}:{idleLabel}:{status?.status ?? 'idle'}:{status?.task_id ?? 'none'}:{status?.platform ?? 'none'}
    </div>
  ),
}));

beforeEach(() => {
  startDownloadMock.mockResolvedValue({ task_id: 'task-dl-1', platform: 'dl_expo' });
  subscribeProgressMock.mockImplementation(() => vi.fn());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it('shows a pending dl-expo task immediately after selecting a search result', async () => {
  const user = userEvent.setup();

  render(
    <DlExpoPage
      platforms={[{ name: 'dl_expo', display_name: '糯米影视', patterns: ['dl-expo\\.com'] }]}
    />,
  );

  await user.click(screen.getByRole('button', { name: '触发专站下载' }));

  await waitFor(() => {
    expect(startDownloadMock).toHaveBeenCalledWith('https://www.dl-expo.com/resource/abc');
  });

  expect(screen.getByTestId('download-progress')).toHaveTextContent(
    'video:糯米影视下载进度:pending:task-dl-1:dl_expo',
  );
  expect(subscribeProgressMock).toHaveBeenCalledWith('task-dl-1', expect.any(Function));
});

it('renders dl-expo-specific help and restricts child components to the standalone platform', () => {
  render(
    <DlExpoPage
      platforms={[{ name: 'dl_expo', display_name: '糯米影视', patterns: ['dl-expo\\.com'] }]}
      allPlatforms={[
        { name: 'dl_expo', display_name: '糯米影视', patterns: ['dl-expo\\.com'] },
        { name: 'tencent', display_name: '腾讯视频', patterns: ['v\\.qq\\.com'] },
      ]}
    />,
  );

  expect(screen.getAllByText(/www\.dl-expo\.com/).length).toBeGreaterThan(0);
  expect(screen.getByTestId('search-input-props')).toHaveTextContent('dl_expo:hidden');
  expect(screen.getByTestId('history')).toHaveTextContent('dl_expo');
  expect(screen.getByText(/https:\/\/www\.dl-expo\.com\/play\/101100\/1-1\.html/)).toBeInTheDocument();
});
