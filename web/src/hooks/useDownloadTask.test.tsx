import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { TaskStatus } from '../api/client';
import { useDownloadTask } from './useDownloadTask';

const { startDownloadMock, subscribeProgressMock, unsubscribeMock } = vi.hoisted(() => ({
  startDownloadMock: vi.fn(),
  subscribeProgressMock: vi.fn(),
  unsubscribeMock: vi.fn(),
}));

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');

  return {
    ...actual,
    startDownload: startDownloadMock,
    subscribeProgress: subscribeProgressMock,
  };
});

function HookHarness({
  shouldAcceptStatus,
}: {
  shouldAcceptStatus?: (status: TaskStatus) => boolean;
}) {
  const { currentTask, downloading, startForUrl, retry, reset, trackTask } = useDownloadTask({
    pendingMessage: '准备下载视频...',
    shouldAcceptStatus,
  });

  return (
    <div>
      <div data-testid="state">
        {currentTask?.status ?? 'idle'}:{currentTask?.task_id ?? 'none'}:{downloading ? 'busy' : 'idle'}
      </div>
      <button type="button" onClick={() => void startForUrl('https://example.com/video')}>
        开始
      </button>
      <button type="button" onClick={() => void retry()}>
        重试
      </button>
      <button
        type="button"
        onClick={() =>
          trackTask('task-existing', {
            task_id: 'task-existing',
            status: 'pending',
            progress: 0,
            total: 1,
            message: '准备下载视频...',
            platform: 'dl_expo',
            manga_info: null,
            zip_path: null,
            error: null,
          })
        }
      >
        跟踪
      </button>
      <button type="button" onClick={reset}>
        重置
      </button>
    </div>
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  startDownloadMock.mockResolvedValue({ task_id: 'task-1', platform: 'iqiyi' });
  subscribeProgressMock.mockImplementation(() => unsubscribeMock);
});

it('starts a download, sets a pending task immediately, and updates with progress events', async () => {
  const user = userEvent.setup();
  let progressHandler: ((status: TaskStatus) => void) | null = null;

  subscribeProgressMock.mockImplementation((_taskId: string, onProgress: (status: TaskStatus) => void) => {
    progressHandler = onProgress;
    return unsubscribeMock;
  });

  render(<HookHarness />);

  await user.click(screen.getByRole('button', { name: '开始' }));

  await waitFor(() => {
    expect(screen.getByTestId('state')).toHaveTextContent('pending:task-1:busy');
  });
  expect(startDownloadMock).toHaveBeenCalledWith('https://example.com/video');
  expect(subscribeProgressMock).toHaveBeenCalledWith('task-1', expect.any(Function));

  if (!progressHandler) {
    throw new Error('expected progress handler to be registered');
  }

  const firstHandler = progressHandler as (status: TaskStatus) => void;

  firstHandler({
    task_id: 'task-1',
    status: 'completed',
    progress: 1,
    total: 1,
    message: '下载完成',
    platform: 'iqiyi',
    manga_info: null,
    zip_path: '/tmp/video.zip',
    error: null,
  });

  await waitFor(() => {
    expect(screen.getByTestId('state')).toHaveTextContent('completed:task-1:idle');
  });
});

it('retries with the last requested url', async () => {
  const user = userEvent.setup();

  render(<HookHarness />);

  await user.click(screen.getByRole('button', { name: '开始' }));
  await waitFor(() => {
    expect(startDownloadMock).toHaveBeenCalledTimes(1);
  });

  await user.click(screen.getByRole('button', { name: '重试' }));

  await waitFor(() => {
    expect(startDownloadMock).toHaveBeenCalledTimes(2);
  });
  expect(startDownloadMock).toHaveBeenNthCalledWith(1, 'https://example.com/video');
  expect(startDownloadMock).toHaveBeenNthCalledWith(2, 'https://example.com/video');
});

it('tracks an existing task, filters out mismatched platform events, and unsubscribes on reset', async () => {
  const user = userEvent.setup();
  let progressHandler: ((status: TaskStatus) => void) | null = null;

  subscribeProgressMock.mockImplementation((_taskId: string, onProgress: (status: TaskStatus) => void) => {
    progressHandler = onProgress;
    return unsubscribeMock;
  });

  render(
    <HookHarness
      shouldAcceptStatus={(status) => !status.platform || status.platform === 'dl_expo'}
    />,
  );

  await user.click(screen.getByRole('button', { name: '跟踪' }));

  expect(screen.getByTestId('state')).toHaveTextContent('pending:task-existing:busy');

  if (!progressHandler) {
    throw new Error('expected progress handler to be registered');
  }

  const trackedHandler = progressHandler as (status: TaskStatus) => void;

  trackedHandler({
    task_id: 'task-existing',
    status: 'downloading',
    progress: 1,
    total: 2,
    message: '下载中',
    platform: 'tencent',
    manga_info: null,
    zip_path: null,
    error: null,
  });

  expect(screen.getByTestId('state')).toHaveTextContent('pending:task-existing:busy');

  trackedHandler({
    task_id: 'task-existing',
    status: 'completed',
    progress: 2,
    total: 2,
    message: '下载完成',
    platform: 'dl_expo',
    manga_info: null,
    zip_path: '/tmp/dl-expo.zip',
    error: null,
  });

  await waitFor(() => {
    expect(screen.getByTestId('state')).toHaveTextContent('completed:task-existing:idle');
  });

  await user.click(screen.getByRole('button', { name: '重置' }));

  expect(unsubscribeMock).toHaveBeenCalled();
  expect(screen.getByTestId('state')).toHaveTextContent('idle:none:idle');
});
