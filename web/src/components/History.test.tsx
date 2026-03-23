import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { clearHistory, deleteHistoryItem, getHistory } from '../api/client';
import History from './History';

vi.mock('../api/client', () => ({
  getHistory: vi.fn().mockResolvedValue({
    history: [
      {
        task_id: '1',
        platform: 'manhuagui',
        title: 'A',
        chapter: '1',
        page_count: 12,
        created_at: '2026-03-21T00:00:00Z',
        zip_path: '/files/1.zip',
      },
      {
        task_id: '2',
        platform: 'tencent',
        title: 'B',
        chapter: 'EP1',
        page_count: 1,
        created_at: '2026-03-21T00:00:00Z',
        zip_path: '/files/2.zip',
      },
    ],
  }),
  getDownloadUrl: vi.fn((taskId: string) => `/download/${taskId}`),
  deleteHistoryItem: vi.fn().mockResolvedValue(undefined),
  clearHistory: vi.fn().mockResolvedValue(undefined),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal('confirm', vi.fn(() => true));

  vi.mocked(getHistory).mockResolvedValue({
    history: [
      {
        task_id: '1',
        platform: 'manhuagui',
        title: 'A',
        chapter: '1',
        page_count: 12,
        created_at: '2026-03-21T00:00:00Z',
        zip_path: '/files/1.zip',
      },
      {
        task_id: '2',
        platform: 'tencent',
        title: 'B',
        chapter: 'EP1',
        page_count: 1,
        created_at: '2026-03-21T00:00:00Z',
        zip_path: '/files/2.zip',
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('shows only manga history on the manga page', async () => {
  render(
    <History
      contentType="manga"
      emptyTitle="暂无漫画下载记录"
      emptyHint="下载的漫画会显示在这里"
    />,
  );

  expect(await screen.findByText('A')).toBeInTheDocument();
  expect(screen.queryByText('B')).not.toBeInTheDocument();
});

it('shows video-specific empty copy on the video page', async () => {
  vi.mocked(getHistory).mockResolvedValueOnce({ history: [] });

  render(
    <History
      contentType="video"
      emptyTitle="暂无视频下载记录"
      emptyHint="下载的视频会显示在这里"
    />,
  );

  expect(await screen.findByText('暂无视频下载记录')).toBeInTheDocument();
  expect(screen.getByText('下载的视频会显示在这里')).toBeInTheDocument();
});

it('deletes one history item after confirmation', async () => {
  const user = userEvent.setup();

  render(
    <History
      contentType="manga"
      emptyTitle="暂无漫画下载记录"
      emptyHint="下载的漫画会显示在这里"
    />,
  );

  expect(await screen.findByText('A')).toBeInTheDocument();

  await user.click(screen.getAllByRole('button', { name: '删除 A' })[0]);

  expect(globalThis.confirm).toHaveBeenCalledWith('确认删除这条下载记录吗？');
  expect(deleteHistoryItem).toHaveBeenCalledWith('1');
  await waitFor(() => expect(getHistory).toHaveBeenCalledTimes(2));
});

it('clears visible history after confirmation', async () => {
  const user = userEvent.setup();

  render(
    <History
      contentType="video"
      emptyTitle="暂无视频下载记录"
      emptyHint="下载的视频会显示在这里"
      allowedPlatforms={['tencent']}
    />,
  );

  expect(await screen.findByText('B')).toBeInTheDocument();

  await user.click(screen.getAllByRole('button', { name: '清空历史' })[0]);

  expect(globalThis.confirm).toHaveBeenCalledWith('确认清空当前历史记录吗？');
  expect(clearHistory).toHaveBeenCalledWith(['tencent']);
  await waitFor(() => expect(getHistory).toHaveBeenCalledTimes(2));
});
