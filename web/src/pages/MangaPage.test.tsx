import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MangaPage from './MangaPage';
import type { TaskStatus } from '../api/client';

const {
  getPlatformsMock,
  getHistoryMock,
  getDownloadUrlMock,
  searchMangaMock,
  getMangaChaptersMock,
  startBatchDownloadMock,
  subscribeProgressMock,
} = vi.hoisted(() => ({
  getPlatformsMock: vi.fn(),
  getHistoryMock: vi.fn(),
  getDownloadUrlMock: vi.fn((taskId: string) => `/api/files/${taskId}`),
  searchMangaMock: vi.fn(),
  getMangaChaptersMock: vi.fn(),
  startBatchDownloadMock: vi.fn(),
  subscribeProgressMock: vi.fn(),
}));

vi.mock('../api/client', async () => {
  const actual = await vi.importActual<typeof import('../api/client')>('../api/client');

  return {
    ...actual,
    getPlatforms: getPlatformsMock,
    getHistory: getHistoryMock,
    getDownloadUrl: getDownloadUrlMock,
    searchManga: searchMangaMock,
    getMangaChapters: getMangaChaptersMock,
    startBatchDownload: startBatchDownloadMock,
    subscribeProgress: subscribeProgressMock,
  };
});

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

  expect(startBatchDownloadMock).toHaveBeenCalledWith(['https://www.manhuagui.com/comic/1/100.html']);
});

const mangaPlatforms = [
  { name: 'manhuagui', display_name: '漫画柜', patterns: ['manhuagui\\.com'] },
];

const allPlatforms = [
  ...mangaPlatforms,
  { name: 'tencent', display_name: '腾讯视频', patterns: ['v\\.qq\\.com'] },
];

let progressHandler: ((status: TaskStatus) => void) | null = null;

beforeEach(() => {
  progressHandler = null;
  getPlatformsMock.mockResolvedValue({ platforms: allPlatforms });
  getHistoryMock.mockResolvedValue({ history: [] });
  startBatchDownloadMock.mockResolvedValue({
    total: 2,
    success: 2,
    failed: 0,
    results: [
      {
        url: 'https://www.manhuagui.com/comic/1/1.html',
        task_id: 'task-1',
        status: 'pending',
        platform: 'manhuagui',
      },
      {
        url: 'https://www.manhuagui.com/comic/2/2.html',
        task_id: 'task-2',
        status: 'pending',
        platform: 'manhuagui',
      },
    ],
  });
  subscribeProgressMock.mockImplementation((_taskId: string, onProgress: (status: TaskStatus) => void) => {
    progressHandler = onProgress;
    return vi.fn();
  });
  vi.stubGlobal('alert', vi.fn());
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

it('keeps the manga batch form disabled until the tracked task finishes', async () => {
  const user = userEvent.setup();

  render(<MangaPage platforms={mangaPlatforms} />);

  await user.click(screen.getByRole('button', { name: '批量下载' }));

  const textarea = screen.getByPlaceholderText('粘贴多个漫画链接，每行一个...');
  await user.type(
    textarea,
    'https://www.manhuagui.com/comic/1/1.html\nhttps://www.manhuagui.com/comic/2/2.html',
  );
  await user.click(screen.getByRole('button', { name: '批量开始下载' }));

  await waitFor(() => {
    expect(startBatchDownloadMock).toHaveBeenCalledWith([
      'https://www.manhuagui.com/comic/1/1.html',
      'https://www.manhuagui.com/comic/2/2.html',
    ]);
  });

  await waitFor(() => {
    expect(textarea).toBeDisabled();
    expect(screen.getByText('处理中')).toBeInTheDocument();
  });

  expect(subscribeProgressMock).toHaveBeenCalledWith('task-1', expect.any(Function));
  expect(progressHandler).not.toBeNull();

  progressHandler?.({
    task_id: 'task-1',
    status: 'completed',
    progress: 2,
    total: 2,
    message: '已完成',
    platform: 'manhuagui',
    manga_info: null,
    zip_path: '/tmp/task-1.zip',
    error: null,
  });

  await waitFor(() => {
    expect(textarea).not.toBeDisabled();
    expect(screen.getByRole('button', { name: '批量开始下载' })).toBeEnabled();
  });
});
