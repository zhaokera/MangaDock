export type ContentType = 'manga' | 'video';

const VIDEO_PLATFORMS = new Set(['tencent', 'iqiyi', 'youku', 'mango', 'bilibili', 'dl_expo']);

export function getContentTypeForPlatform(platform?: string): ContentType {
  return VIDEO_PLATFORMS.has(platform ?? '') ? 'video' : 'manga';
}

export function filterByContentType<T extends { platform?: string }>(
  items: T[],
  contentType: ContentType,
): T[] {
  return items.filter((item) => getContentTypeForPlatform(item.platform) === contentType);
}

export function getPlatformsForContentType<T extends { name: string }>(
  platforms: T[],
  contentType: ContentType,
): T[] {
  return platforms.filter((platform) => getContentTypeForPlatform(platform.name) === contentType);
}
