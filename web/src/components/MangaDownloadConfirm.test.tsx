import { afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';

import MangaDownloadConfirm from './MangaDownloadConfirm';

afterEach(() => {
  cleanup();
});

it('does not submit until the final confirm button is clicked', async () => {
  const user = userEvent.setup();
  const onConfirm = vi.fn();

  render(
    <MangaDownloadConfirm
      title="海贼王"
      platformDisplay="漫画柜"
      chapters={[
        { title: '第1话', url: 'https://www.manhuagui.com/comic/1/100.html' },
      ]}
      pending={false}
      onConfirm={onConfirm}
      onBack={vi.fn()}
    />,
  );

  expect(onConfirm).not.toHaveBeenCalled();
  await user.click(screen.getByRole('button', { name: '确认下载 1 个章节' }));
  expect(onConfirm).toHaveBeenCalledTimes(1);
});
