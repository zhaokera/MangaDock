import { afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';

import MangaChapterPicker from './MangaChapterPicker';

afterEach(() => {
  cleanup();
});

it('exposes accessible checkbox labels for each chapter', async () => {
  const user = userEvent.setup();
  const onToggleChapter = vi.fn();

  render(
    <MangaChapterPicker
      chapters={[
        { title: '第1话', url: 'https://www.manhuagui.com/comic/1/100.html' },
      ]}
      selectedUrls={[]}
      onToggleChapter={onToggleChapter}
      onSelectAll={vi.fn()}
      onClearAll={vi.fn()}
      chapterLabelPrefix="选择章节"
    />,
  );

  await user.click(screen.getByRole('checkbox', { name: '选择章节 第1话' }));

  expect(onToggleChapter).toHaveBeenCalledWith('https://www.manhuagui.com/comic/1/100.html');
});
