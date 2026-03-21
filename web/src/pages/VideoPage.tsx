import React, { useCallback, useEffect, useRef, useState } from 'react';
import { type Platform, type SearchResult, type TaskStatus, startDownload, subscribeProgress } from '../api/client';
import DownloadProgress from '../components/DownloadProgress';
import History from '../components/History';
import SearchInput from '../components/SearchInput';

interface VideoPageProps {
  platforms: Platform[];
}

const PLATFORM_COLORS: Record<string, { primary: string; secondary: string }> = {
  tencent: { primary: '#00AEE1', secondary: '#0066AA' },
  iqiyi: { primary: '#FF5252', secondary: '#D32F2F' },
  youku: { primary: '#FFE600', secondary: '#FFC100' },
  mango: { primary: '#F57C00', secondary: '#E65100' },
  default: { primary: '#6366F1', secondary: '#EC4899' },
};

const getPlatformColor = (platform?: string) => {
  if (!platform) {
    return PLATFORM_COLORS.default;
  }

  return PLATFORM_COLORS[platform] || PLATFORM_COLORS.default;
};

const VideoPage: React.FC<VideoPageProps> = ({ platforms }) => {
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      unsubscribeRef.current?.();
    };
  }, []);

  const handleSearchResultSelect = useCallback(async (result: SearchResult) => {
    try {
      setCurrentTask(null);
      unsubscribeRef.current?.();

      const downloadResult = await startDownload(result.url);
      setCurrentTask({
        task_id: downloadResult.task_id,
        status: 'pending',
        progress: 0,
        total: 0,
        message: '准备下载视频...',
        platform: downloadResult.platform,
        manga_info: null,
        zip_path: null,
        error: null,
      });
      unsubscribeRef.current = subscribeProgress(downloadResult.task_id, (status) => {
        setCurrentTask(status);
      });
    } catch (error) {
      console.error('下载失败', error);
      alert(error instanceof Error ? error.message : '下载失败');
    }
  }, []);

  return (
    <>
      <section className="text-center mb-8">
        <h2 className="font-display text-3xl mb-2">
          <span className="gradient-text">搜索动漫 / 视频名称</span>
          <span className="text-gray-700"> 并开始下载</span>
        </h2>
        <p className="text-gray-400">输入影视名称，筛选平台后选择结果进行下载</p>
      </section>

      {platforms.length > 0 && (
        <section className="flex flex-wrap justify-center gap-2 mb-6">
          {platforms.map((platform) => {
            const colors = getPlatformColor(platform.name);
            return (
              <div
                key={platform.name}
                className="px-3 py-1.5 rounded-full text-xs font-medium bg-gradient-to-r text-gray-600 border border-gray-100"
                style={{
                  background: `linear-gradient(135deg, ${colors.primary}10, ${colors.secondary}10)`,
                }}
              >
                {platform.display_name}
              </div>
            );
          })}
        </section>
      )}

      {currentTask && (
        <section className="animate-[fadeIn_0.3s_ease]">
          <DownloadProgress
            status={currentTask}
            contentType="video"
            idleLabel="视频下载进度"
          />
        </section>
      )}

      <section className="animate-[fadeIn_0.3s_ease]">
        <SearchInput
          platforms={platforms}
          onSearch={() => {}}
          onResultSelect={handleSearchResultSelect}
        />
      </section>

      <section>
        <History
          contentType="video"
          emptyTitle="暂无视频下载记录"
          emptyHint="下载的视频会显示在这里"
        />
      </section>

    </>
  );
};

export default VideoPage;
