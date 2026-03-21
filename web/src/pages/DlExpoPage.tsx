import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  type Platform,
  type SearchResult,
  type TaskStatus,
  startDownload,
  subscribeProgress,
} from '../api/client';
import DownloadProgress from '../components/DownloadProgress';
import History from '../components/History';
import SearchInput from '../components/SearchInput';
import UrlInput from '../components/UrlInput';

interface DlExpoPageProps {
  platforms: Platform[];
  allPlatforms?: Platform[];
}

const DL_EXPO_PLATFORM = 'dl_expo';

const DlExpoPage: React.FC<DlExpoPageProps> = ({ platforms, allPlatforms = platforms }) => {
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [downloading, setDownloading] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      unsubscribeRef.current?.();
    };
  }, []);

  const beginDownload = useCallback(async (url: string) => {
    try {
      setDownloading(true);
      setCurrentTask(null);
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;

      const result = await startDownload(url);
      setCurrentTask({
        task_id: result.task_id,
        status: 'pending',
        progress: 0,
        total: 0,
        message: '准备下载糯米影视资源...',
        platform: result.platform,
        manga_info: null,
        zip_path: null,
        error: null,
      });

      unsubscribeRef.current = subscribeProgress(result.task_id, (status) => {
        if (status.platform && status.platform !== DL_EXPO_PLATFORM) {
          return;
        }

        setCurrentTask(status);
        if (status.status === 'completed' || status.status === 'failed') {
          setDownloading(false);
        }
      });
    } catch (error) {
      console.error('糯米影视下载失败', error);
      setDownloading(false);
      alert(error instanceof Error ? error.message : '下载失败');
    }
  }, []);

  const handleSearchResultSelect = useCallback(async (result: SearchResult) => {
    await beginDownload(result.url);
  }, [beginDownload]);

  return (
    <>
      <section className="text-center mb-8">
        <h2 className="font-display text-3xl mb-2">
          <span className="gradient-text">糯米影视专站搜索</span>
        </h2>
        <p className="text-gray-400">只搜索 www.dl-expo.com，并支持直接粘贴专站链接下载</p>
      </section>

      <section className="glass-card rounded-3xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/10 to-secondary/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                />
              </svg>
            </div>
            <h3 className="font-bold text-gray-800">专站说明</h3>
          </div>
        </div>
        <div className="p-6 space-y-3 text-sm text-gray-600">
          <p>此页仅处理来自 www.dl-expo.com 的搜索结果、详情页和播放页链接。</p>
          <p>如果粘贴了其他视频站点链接，页面会提示你切换到对应页面继续下载。</p>
        </div>
      </section>

      {currentTask && (
        <section className="animate-[fadeIn_0.3s_ease]">
          <DownloadProgress
            status={currentTask}
            contentType="video"
            idleLabel="糯米影视下载进度"
          />
        </section>
      )}

      <section className="animate-[fadeIn_0.3s_ease]">
        <SearchInput
          platforms={platforms}
          onSearch={() => {}}
          onResultSelect={handleSearchResultSelect}
          lockedPlatform={DL_EXPO_PLATFORM}
          hidePlatformSelector
          title="搜索糯米影视站内资源"
          placeholder="输入影片名称，搜索糯米影视资源..."
        />
      </section>

      <section className="glass-card rounded-3xl p-6 animate-[fadeIn_0.3s_ease]">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/10 to-secondary/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
              />
            </svg>
          </div>
          <h3 className="font-bold text-gray-800">直接粘贴专站链接</h3>
        </div>
        <UrlInput
          contentType="video"
          onDownload={beginDownload}
          disabled={downloading}
          platforms={platforms}
          allPlatforms={allPlatforms}
          allowedPlatforms={[DL_EXPO_PLATFORM]}
          wrongPageMessage="当前是糯米影视专站页，请切换到对应页面下载"
          exampleUrl="https://www.dl-expo.com/play/101100/1-1.html"
        />
      </section>

      <section>
        <History
          contentType="video"
          emptyTitle="暂无糯米影视下载记录"
          emptyHint="糯米影视下载任务会显示在这里"
          allowedPlatforms={[DL_EXPO_PLATFORM]}
        />
      </section>
    </>
  );
};

export default DlExpoPage;
