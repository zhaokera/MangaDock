const API_BASE = '/api';

export interface Platform {
  name: string;
  display_name: string;
  patterns: string[];
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

// 获取支持的平台列表
export async function getPlatforms(): Promise<{ platforms: Platform[] }> {
  const response = await fetch(`${API_BASE}/platforms`);
  return response.json();
}

// 解析 URL
export async function parseUrl(url: string): Promise<{
  platform: string;
  platform_name: string;
  comic_id: string;
  episode_id: string;
  url: string;
}> {
  const response = await fetch(`${API_BASE}/parse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '解析失败');
  }

  return response.json();
}

// 开始下载
export async function startDownload(url: string): Promise<{ task_id: string; platform: string }> {
  const response = await fetch(`${API_BASE}/download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '启动下载失败');
  }

  return response.json();
}

// 批量下载
export async function startBatchDownload(urls: string[]): Promise<{
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
}> {
  const response = await fetch(`${API_BASE}/batch-download`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ urls })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || '批量下载失败');
  }

  return response.json();
}

// 获取任务状态
export async function getTaskStatus(taskId: string): Promise<TaskStatus> {
  const response = await fetch(`${API_BASE}/status/${taskId}`);

  if (!response.ok) {
    throw new Error('获取状态失败');
  }

  return response.json();
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
  const response = await fetch(`${API_BASE}/history`);
  return response.json();
}