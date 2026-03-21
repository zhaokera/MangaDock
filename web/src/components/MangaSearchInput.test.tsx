import { afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';

import MangaSearchInput from './MangaSearchInput';

afterEach(() => {
  cleanup();
});

it('submits keyword and selected platform to the parent callback', async () => {
  const user = userEvent.setup();
  const onSearch = vi.fn();

  render(
    <MangaSearchInput
      platforms={[{ name: 'manhuagui', display_name: '漫画柜' }]}
      loading={false}
      onSearch={onSearch}
    />,
  );

  await user.type(screen.getByPlaceholderText('输入漫画名称...'), '海贼王');
  await user.click(screen.getByRole('button', { name: '搜索' }));

  expect(onSearch).toHaveBeenCalledWith('海贼王', 'manhuagui');
});

it('stays disabled until it has a valid platform and updates when platforms change', async () => {
  const user = userEvent.setup();
  const onSearch = vi.fn();
  const { rerender } = render(<MangaSearchInput platforms={[]} loading={false} onSearch={onSearch} />);

  await user.type(screen.getByPlaceholderText('输入漫画名称...'), '海贼王');
  expect(screen.getByRole('button', { name: '搜索' })).toBeDisabled();

  rerender(
    <MangaSearchInput
      platforms={[
        { name: 'manhuagui', display_name: '漫画柜' },
        { name: 'dmzj', display_name: '动漫之家' },
      ]}
      loading={false}
      onSearch={onSearch}
    />,
  );

  expect(screen.getByRole('button', { name: '搜索' })).toBeEnabled();
  await user.click(screen.getByRole('button', { name: '搜索' }));

  expect(onSearch).toHaveBeenCalledWith('海贼王', 'manhuagui');
});
