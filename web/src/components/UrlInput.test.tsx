import { afterEach } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import UrlInput from './UrlInput';

const platforms = [
  { name: 'manhuagui', display_name: '漫画柜', patterns: ['manhuagui\\.com'] },
];

const allPlatforms = [
  { name: 'manhuagui', display_name: '漫画柜', patterns: ['manhuagui\\.com'] },
  { name: 'tencent', display_name: '腾讯视频', patterns: ['v\\.qq\\.com'] },
];

afterEach(() => {
  cleanup();
});

it('tells the user to switch to video when a video link is pasted on the manga page', async () => {
  const user = userEvent.setup();
  const onDownload = vi.fn();

  const { getByPlaceholderText, getByRole } = render(
    <UrlInput
      contentType="manga"
      disabled={false}
      onDownload={onDownload}
      platforms={platforms}
      allPlatforms={allPlatforms}
    />,
  );

  await user.type(getByPlaceholderText('粘贴漫画章节链接...'), 'https://v.qq.com/x/cover/abc/xyz.html');
  await user.click(getByRole('button', { name: '开始下载' }));

  expect(await screen.findByText('当前是漫画下载页，请切换到视频下载')).toBeInTheDocument();
  expect(onDownload).not.toHaveBeenCalled();
});

it('submits trimmed manga urls in single mode', async () => {
  const user = userEvent.setup();
  const onDownload = vi.fn();

  const { getByPlaceholderText, getByRole } = render(
    <UrlInput
      contentType="manga"
      disabled={false}
      onDownload={onDownload}
      platforms={platforms}
      allPlatforms={allPlatforms}
    />,
  );

  await user.type(getByPlaceholderText('粘贴漫画章节链接...'), '  https://www.manhuagui.com/comic/58667/868543.html  ');
  await user.click(getByRole('button', { name: '开始下载' }));

  expect(onDownload).toHaveBeenCalledWith('https://www.manhuagui.com/comic/58667/868543.html');
});

it('tells the user to switch to manga when a manga link is pasted on the video page', async () => {
  const user = userEvent.setup();
  const onDownload = vi.fn();

  const { getByPlaceholderText, getByRole } = render(
    <UrlInput
      contentType="video"
      disabled={false}
      onDownload={onDownload}
      platforms={[{ name: 'tencent', display_name: '腾讯视频', patterns: ['v\\.qq\\.com'] }]}
      allPlatforms={allPlatforms}
    />,
  );

  await user.type(getByPlaceholderText('粘贴视频章节链接...'), 'https://www.manhuagui.com/comic/58667/868543.html');
  await user.click(getByRole('button', { name: '开始下载' }));

  expect(await screen.findByText('当前是视频下载页，请切换到漫画下载')).toBeInTheDocument();
  expect(onDownload).not.toHaveBeenCalled();
});

it('shows switch guidance for mixed batch input when any url belongs to the opposite page', async () => {
  const user = userEvent.setup();
  const onBatchDownload = vi.fn();

  const { getByPlaceholderText, getByRole } = render(
    <UrlInput
      contentType="manga"
      disabled={false}
      onDownload={vi.fn()}
      onBatchDownload={onBatchDownload}
      platforms={platforms}
      allPlatforms={allPlatforms}
    />,
  );

  await user.click(getByRole('button', { name: '批量下载' }));
  await user.type(
    getByPlaceholderText('粘贴多个漫画链接，每行一个...'),
    'https://www.manhuagui.com/comic/58667/868543.html\nhttps://v.qq.com/x/cover/abc/xyz.html',
  );
  await user.click(getByRole('button', { name: '批量开始下载' }));

  expect(await screen.findByText('当前是漫画下载页，请切换到视频下载')).toBeInTheDocument();
  expect(onBatchDownload).not.toHaveBeenCalled();
});

it('shows dedicated wrong-page guidance for other video platforms on the dl-expo page', async () => {
  const user = userEvent.setup();
  const onDownload = vi.fn();

  const { getByPlaceholderText, getByRole } = render(
    <UrlInput
      {...({
        contentType: 'video',
        disabled: false,
        onDownload,
        platforms: [{ name: 'dl_expo', display_name: '糯米影视', patterns: ['dl-expo\\.com'] }],
        allPlatforms: [
          { name: 'dl_expo', display_name: '糯米影视', patterns: ['dl-expo\\.com'] },
          { name: 'tencent', display_name: '腾讯视频', patterns: ['v\\.qq\\.com'] },
        ],
        allowedPlatforms: ['dl_expo'],
        wrongPageMessage: '该链接属于其他站点，请切换到对应页面下载',
      } as const)}
    />,
  );

  await user.type(getByPlaceholderText('粘贴视频章节链接...'), 'https://v.qq.com/x/cover/abc/xyz.html');
  await user.click(getByRole('button', { name: '开始下载' }));

  expect(await screen.findByText('该链接属于其他站点，请切换到对应页面下载')).toBeInTheDocument();
  expect(onDownload).not.toHaveBeenCalled();
});
