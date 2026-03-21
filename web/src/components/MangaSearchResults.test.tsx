import { afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';

import MangaSearchResults from './MangaSearchResults';

afterEach(() => {
  cleanup();
});

it('uses a configurable action label for each result', async () => {
  const user = userEvent.setup();
  const onSelect = vi.fn();

  render(
    <MangaSearchResults
      results={[
        {
          title: '海贼王',
          url: 'https://www.manhuagui.com/comic/1/',
          platform: 'manhuagui',
          platform_display: '漫画柜',
        },
      ]}
      actionLabel={(result) => `查看章节 ${result.title}`}
      onSelect={onSelect}
    />,
  );

  await user.click(screen.getByRole('button', { name: '查看章节 海贼王' }));

  expect(onSelect).toHaveBeenCalledWith(
    expect.objectContaining({
      title: '海贼王',
      platform: 'manhuagui',
    }),
  );
});
