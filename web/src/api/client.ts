import type { ContentType } from '../lib/contentType';

const API_BASE = '/api';
const JSON_HEADERS = { 'Content-Type': 'application/json' } as const;

export interface Platform {
  name: string;
  display_name: string;
  patterns: string[];
  type: ContentType;
}

export interface MangaInfo {
  platform?: string;
  comic_id?: string;
  episode_id?: string;
  title?: string;
  chapter?: string;
  page_count?: number;
}

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed';
  progress: number;
  total: number;
  message: string;
  platform?: string;
  manga_info: MangaInfo | null;
  zip_path: string | null;
  error: string | null;
}

export interface HistoryItem {
  task_id: string;
  title: string;
  chapter: string;
  platform?: string;
  zip_path: string;
  page_count: number;
  created_at: string;
}

export interface ParseUrlResponse {
  platform: string;
  platform_name: string;
  comic_id: string;
  episode_id: string;
  url: string;
}

export interface DownloadStartResponse {
  task_id: string;
  platform: string;
}

export interface BatchDownloadResponse {
  total: number;
  success: number;
  failed: number;
  results: Array<{
    url: string;
    task_id?: string;
    status: 'pending' | 'failed';
    platform?: string;
    error?: string;
  }>;
}

type ApiErrorPayload = {
  detail?: string;
};

async function parseApiError(response: Response, fallbackMessage: string): Promise<Error> {
  try {
    const error = (await response.json()) as ApiErrorPayload;
    return new Error(error.detail || fallbackMessage);
  } catch {
    return new Error(fallbackMessage);
  }
}

async function requestJson<T>(url: string, init?: RequestInit, fallbackMessage?: string): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw await parseApiError(response, fallbackMessage || '请求失败');
  }

  return response.json() as Promise<T>;
}

async function requestVoid(url: string, init: RequestInit, fallbackMessage: string): Promise<void> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw await parseApiError(response, fallbackMessage);
  }
}

// 获取支持的平台列表
export async function getPlatforms(): Promise<{ platforms: Platform[] }> {
  return requestJson<{ platforms: Platform[] }>(`${API_BASE}/platforms`);
}

// 解析 URL
export async function parseUrl(url: string): Promise<ParseUrlResponse> {
  return requestJson<ParseUrlResponse>(`${API_BASE}/parse`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ url }),
  }, '解析失败');
}

// 开始下载
export async function startDownload(url: string): Promise<DownloadStartResponse> {
  return requestJson<DownloadStartResponse>(`${API_BASE}/download`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ url }),
  }, '启动下载失败');
}

// 批量下载
export async function startBatchDownload(urls: string[]): Promise<BatchDownloadResponse> {
  return requestJson<BatchDownloadResponse>(`${API_BASE}/batch-download`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ urls }),
  }, '批量下载失败');
}

// 获取任务状态
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  return requestJson(`${API_BASE}/status/${taskId}`, undefined, '获取状态失败');
}

// SSE 进度推送 - 带自动重连
export function subscribeProgress(
  taskId: string,
  onProgress: (status: TaskStatus) => void
): () => void {
  let eventSource: EventSource | null = null;
  let isClosed = false;
  let reconnectDelay = 1000; // 初始重连延迟 1 秒
  const maxReconnectDelay = 10000; // 最大重连延迟 10 秒

  const connect = () => {
    if (isClosed) return;

    eventSource = new EventSource(`${API_BASE}/progress/${taskId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onProgress(data);
        reconnectDelay = 1000; // 成功接收后重置延迟

        if (data.status === 'completed' || data.status === 'failed') {
          close();
        }
      } catch (e) {
        console.error('解析 SSE 数据失败', e);
      }
    };

    eventSource.onerror = () => {
      console.log('SSE 连接中断，准备重连...');
      eventSource?.close();

      if (!isClosed) {
        setTimeout(() => {
          connect();
        }, reconnectDelay);
        // 指数退避延迟
        reconnectDelay = Math.min(reconnectDelay * 2, maxReconnectDelay);
      }
    };
  };

  const close = () => {
    isClosed = true;
    eventSource?.close();
  };

  // 立即连接
  connect();

  return close;
}

// 获取下载文件 URL
export function getDownloadUrl(taskId: string): string {
  return `${API_BASE}/files/${taskId}`;
}

// 获取历史记录
export async function getHistory(): Promise<{ history: HistoryItem[] }> {
  return requestJson<{ history: HistoryItem[] }>(`${API_BASE}/history`);
}

export async function deleteHistoryItem(taskId: string): Promise<void> {
  return requestVoid(`${API_BASE}/history/${taskId}`, {
    method: 'DELETE',
  }, '删除历史失败');
}

export async function clearHistory(platforms?: string[]): Promise<void> {
  const hasPlatforms = Boolean(platforms && platforms.length > 0);
  return requestVoid(`${API_BASE}/history`, {
    method: 'DELETE',
    headers: JSON_HEADERS,
    body: JSON.stringify(hasPlatforms ? { platforms } : {}),
  }, '清空历史失败');
}

// === 搜索 API ===

export interface SearchPlatform {
  name: string;
  display_name: string;
  type: ContentType;
}

export interface SearchResult {
  title: string;
  url: string;
  platform: string;
  platform_display: string;
  score: number;
  extra?: {
    cover?: string;
    duration?: string;
    year?: string;
    director?: string;
    actor?: string;
  };
}

export interface MangaSearchResult {
  title: string;
  url: string;
  platform: string;
  platform_display: string;
  extra?: Record<string, string>;
}

export interface MangaChapter {
  title: string;
  url: string;
}

export interface MangaChapterCatalog {
  title: string;
  platform: string;
  platform_display: string;
  url: string;
  chapters: MangaChapter[];
}

// 搜索视频/漫画
export async function searchVideos(keyword: string, platform?: string, limit: number = 10): Promise<{ results: SearchResult[]; total: number; platform?: string }> {
  return requestJson(`${API_BASE}/search`, {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({
      keyword,
      platform,
      limit,
    }),
  }, '搜索失败');
}

export async function searchManga(keyword: string, platform: string, limit: number = 10): Promise<{ results: MangaSearchResult[]; total: number; platform?: string }> {
  return requestJson(
    `${API_BASE}/search/manga?${new URLSearchParams({
      keyword,
      platform,
      limit: String(limit),
    })}`,
    undefined,
    '搜索失败',
  );
}

export async function getMangaChapters(url: string, platform: string): Promise<MangaChapterCatalog> {
  return requestJson(
    `${API_BASE}/manga/chapters?${new URLSearchParams({
      url,
      platform,
    })}`,
    undefined,
    '获取章节失败',
  );
}

// 获取支持搜索的平台
export async function getSearchPlatforms(): Promise<{ platforms: SearchPlatform[] }> {
  // 从 API 获取平台列表，标记支持搜索的平台
  const data = await requestJson<{ platforms?: Platform[] }>(`${API_BASE}/platforms`);
  const platforms = (data.platforms || []).filter((platform) => platform.type === 'video').map((p): SearchPlatform => ({
    ...p,
    type: p.type,
  }));

  return { platforms };
}
