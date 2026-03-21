import { expect, it } from 'vitest';

import { getMangaChapters } from './client';

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
