import { describe, expect, it } from 'vitest';
import { filterByContentType, getContentTypeForPlatform } from './contentType';

describe('content type mapping', () => {
  it('classifies known manga and video platforms', () => {
    expect(getContentTypeForPlatform('manhuagui')).toBe('manga');
    expect(getContentTypeForPlatform('tencent')).toBe('video');
    expect(getContentTypeForPlatform('unknown-platform')).toBe('manga');
  });

  it('classifies dl_expo as a video platform', () => {
    expect(getContentTypeForPlatform('dl_expo')).toBe('video');
  });

  it('filters mixed history records by page type', () => {
    const history = [
      { task_id: '1', platform: 'manhuagui' },
      { task_id: '2', platform: 'tencent' },
    ];

    expect(filterByContentType(history, 'manga')).toHaveLength(1);
    expect(filterByContentType(history, 'video')).toHaveLength(1);
  });
});
