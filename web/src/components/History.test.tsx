import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { getHistory } from '../api/client';
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
}));

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
