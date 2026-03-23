import { useCallback, useEffect, useRef, useState } from 'react';
import { startDownload, subscribeProgress, type TaskStatus } from '../api/client';

interface UseDownloadTaskOptions {
  pendingMessage: string;
  shouldAcceptStatus?: (status: TaskStatus) => boolean;
  onStartError?: (error: unknown) => void;
}

export function useDownloadTask({
  pendingMessage,
  shouldAcceptStatus,
  onStartError,
}: UseDownloadTaskOptions) {
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [lastRequestedUrl, setLastRequestedUrl] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  const clearSubscription = useCallback(() => {
    unsubscribeRef.current?.();
    unsubscribeRef.current = null;
  }, []);

  useEffect(() => {
    return () => {
      clearSubscription();
    };
  }, [clearSubscription]);

  const trackTask = useCallback((taskId: string, initialTask?: TaskStatus | null) => {
    clearSubscription();

    if (initialTask) {
      setCurrentTask(initialTask);
    }
    setDownloading(true);

    unsubscribeRef.current = subscribeProgress(taskId, (status) => {
      if (shouldAcceptStatus && !shouldAcceptStatus(status)) {
        return;
      }

      setCurrentTask(status);
      if (status.status === 'completed' || status.status === 'failed') {
        setDownloading(false);
      }
    });
  }, [clearSubscription, shouldAcceptStatus]);

  const reset = useCallback(() => {
    clearSubscription();
    setCurrentTask(null);
    setDownloading(false);
  }, [clearSubscription]);

  const startForUrl = useCallback(async (url: string) => {
    try {
      clearSubscription();
      setCurrentTask(null);
      setLastRequestedUrl(url);
      setDownloading(true);

      const result = await startDownload(url);
      trackTask(result.task_id, {
        task_id: result.task_id,
        status: 'pending',
        progress: 0,
        total: 0,
        message: pendingMessage,
        platform: result.platform,
        manga_info: null,
        zip_path: null,
        error: null,
      });
    } catch (error) {
      setDownloading(false);
      onStartError?.(error);
    }
  }, [clearSubscription, onStartError, pendingMessage, trackTask]);

  const retry = useCallback(async () => {
    if (!lastRequestedUrl) {
      return;
    }

    await startForUrl(lastRequestedUrl);
  }, [lastRequestedUrl, startForUrl]);

  return {
    currentTask,
    downloading,
    lastRequestedUrl,
    startForUrl,
    retry,
    reset,
    trackTask,
  };
}
