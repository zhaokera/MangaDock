import { afterEach, expect, it, vi } from 'vitest';

import { getMangaChapters, parseUrl } from './client';

it('types manga chapter catalog payloads with the full backend shape', () => {
  const catalog: Awaited<ReturnType<typeof getMangaChapters>> = {
    title: '海贼王',
    platform: 'manhuagui',
    platform_display: '漫画柜',
    url: 'https://www.manhuagui.com/comic/1/',
    chapters: [
      {
        title: '第1话',
        url: 'https://www.manhuagui.com/comic/1/100.html',
      },
    ],
  };

  expect(catalog.platform_display).toBe('漫画柜');
  expect(catalog.chapters).toHaveLength(1);
});

afterEach(() => {
  vi.restoreAllMocks();
});

it('falls back to default message when api error body is not json', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: false,
    json: vi.fn().mockRejectedValue(new Error('invalid json')),
  } as unknown as Response);

  await expect(parseUrl('https://example.com')).rejects.toThrow('解析失败');
});

it('uses detail from api error payload when available', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue({
    ok: false,
    json: vi.fn().mockResolvedValue({ detail: '自定义错误' }),
  } as unknown as Response);

  await expect(getMangaChapters('https://example.com/comic', 'manhuagui')).rejects.toThrow('自定义错误');
});
