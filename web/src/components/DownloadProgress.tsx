import React from 'react';
import { TaskStatus, getDownloadUrl } from '../api/client';
import { getContentTypeForPlatform, type ContentType } from '../lib/contentType';

interface DownloadProgressProps {
  status: TaskStatus | null;
  contentType: ContentType;
  idleLabel?: string;
}

// 平台显示配置
const PLATFORM_CONFIG: Record<string, { name: string; color: string; bg: string }> = {
  manhuagui: {
    name: '漫画柜',
    color: 'text-emerald-500',
    bg: 'bg-gradient-to-br from-emerald-200/50 to-green-200/50',
  },
  tencent: {
    name: '腾讯视频',
    color: 'text-sky-500',
    bg: 'bg-gradient-to-br from-sky-200/50 to-cyan-200/50',
  },
  iqiyi: {
    name: '爱奇艺',
    color: 'text-lime-500',
    bg: 'bg-gradient-to-br from-lime-200/50 to-green-200/50',
  },
  youku: {
    name: '优酷',
    color: 'text-amber-500',
    bg: 'bg-gradient-to-br from-amber-200/50 to-yellow-200/50',
  },
  mango: {
    name: '芒果TV',
    color: 'text-orange-500',
    bg: 'bg-gradient-to-br from-orange-200/50 to-red-200/50',
  },
  bilibili: {
    name: '哔哩哔哩',
    color: 'text-pink-500',
    bg: 'bg-gradient-to-br from-pink-200/50 to-rose-200/50',
  },
  default: {
    name: '漫画平台',
    color: 'text-primary',
    bg: 'bg-gradient-to-br from-primary/20 to-secondary/20',
  },
};

const DownloadProgress: React.FC<DownloadProgressProps> = ({ status, contentType, idleLabel }) => {
  if (!status) {
    if (!idleLabel) {
      return null;
    }

    return (
      <div className="glass-card rounded-3xl overflow-hidden">
        <div className="px-6 py-5">
          <p className="font-medium text-gray-800">{idleLabel}</p>
          <p className="text-sm text-gray-400 mt-1">
            {contentType === 'manga' ? '等待漫画下载任务开始' : '等待视频下载任务开始'}
          </p>
        </div>
      </div>
    );
  }

  const { task_id, status: taskStatus, progress, total, message, manga_info, platform, error } = status;
  if (platform && getContentTypeForPlatform(platform) !== contentType) {
    return null;
  }

  const percentage = total > 0 ? Math.round((progress / total) * 100) : 0;
  const contentLabel = contentType === 'manga' ? '漫画' : '视频';
  const unitLabel = contentType === 'manga' ? '页' : '集';

  // 获取平台配置
  const platformConfig = PLATFORM_CONFIG[platform || ''] || {
    ...PLATFORM_CONFIG.default,
    name: contentType === 'video' ? '视频平台' : PLATFORM_CONFIG.default.name,
  };

  // Status configuration
  const statusConfig = {
    pending: {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: 'text-amber-500',
      bg: 'bg-amber-50',
      border: 'border-amber-200',
      title: '准备中',
    },
    downloading: {
      icon: (
        <svg className="w-6 h-6 animate-bounce" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
        </svg>
      ),
      color: 'text-primary',
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      title: '下载中',
    },
    completed: {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: 'text-green-500',
      bg: 'bg-green-50',
      border: 'border-green-200',
      title: '下载完成',
    },
    failed: {
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: 'text-red-500',
      bg: 'bg-red-50',
      border: 'border-red-200',
      title: '下载失败',
    },
  };

  const config = statusConfig[taskStatus] || statusConfig.pending;

  return (
    <div className="glass-card rounded-3xl overflow-hidden">
      {/* Header with manga info */}
      {manga_info && (manga_info.title || manga_info.chapter) && (
        <div className="px-6 py-5 border-b border-gray-100/50">
          <div className="flex items-start gap-4">
            {/* Manga cover placeholder */}
            <div className={`w-16 h-20 rounded-xl ${platformConfig.bg} flex items-center justify-center flex-shrink-0`}>
              <svg className="w-8 h-8 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>

            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-lg text-gray-800 truncate">
                {manga_info.title || `${contentLabel} ${manga_info.comic_id || ''}`}
              </h3>
              <p className="text-gray-500 mt-0.5">
                {manga_info.chapter || (contentType === 'manga' ? `第${manga_info.episode_id || '?'}话` : `${contentLabel}下载任务`)}
              </p>

              {/* Platform badge and page count */}
              <div className="flex items-center gap-2 mt-2">
                {/* Platform badge */}
                {platform && (
                  <span className={`inline-flex items-center gap-1 text-xs ${platformConfig.color}`}>
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                    </svg>
                    {platformConfig.name}
                  </span>
                )}

                {manga_info.page_count && manga_info.page_count > 0 && (
                  <>
                    <span className="w-1 h-1 rounded-full bg-gray-300" />
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <span>{manga_info.page_count} 页</span>
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Status badge */}
            <div className={`px-3 py-1.5 rounded-full text-xs font-medium ${config.bg} ${config.color} ${config.border} border`}>
              {config.title}
            </div>
          </div>
        </div>
      )}

      {/* Progress section */}
      <div className="px-6 py-5 space-y-4">
        {/* Progress bar */}
        {(taskStatus === 'downloading' || taskStatus === 'completed') && total > 0 && (
          <div className="space-y-3">
            {/* Bar */}
            <div className="relative h-3 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out progress-shimmer"
                style={{ width: `${percentage}%` }}
              >
                <div className="h-full w-full bg-gradient-to-r from-primary via-[#7C3AED] to-secondary" />
              </div>

              {/* Glow effect */}
              <div
                className="absolute inset-y-0 rounded-full blur-sm opacity-50 transition-all duration-500"
                style={{ width: `${percentage}%`, background: 'linear-gradient(to right, #6366F1, #EC4899)' }}
              />
            </div>

            {/* Stats */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold gradient-text">{percentage}%</span>
                <span className="text-sm text-gray-400">
                  ({progress}/{total} {unitLabel})
                </span>
              </div>

              {/* Animated dots for downloading */}
              {taskStatus === 'downloading' && (
                <div className="flex gap-1">
                  <span className="loading-dot w-2 h-2 bg-primary rounded-full"></span>
                  <span className="loading-dot w-2 h-2 bg-secondary rounded-full"></span>
                  <span className="loading-dot w-2 h-2 bg-primary rounded-full"></span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Status message */}
        <div className={`flex items-center gap-3 ${config.color}`}>
          <div className={`p-2 rounded-xl ${config.bg}`}>
            {config.icon}
          </div>
          <div className="flex-1">
            <p className="font-medium">{message}</p>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-100 rounded-xl p-4 text-sm text-red-600">
            <div className="flex items-start gap-2">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Download button */}
        {taskStatus === 'completed' && (
          <a
            href={getDownloadUrl(task_id)}
            className="btn-primary flex items-center justify-center gap-3 w-full py-4 text-white font-medium rounded-2xl
                       bg-gradient-to-r from-secondary to-[#FF8FAB]
                       shadow-lg shadow-secondary/30 hover:shadow-secondary/50
                       transition-all duration-300"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            下载 ZIP 文件
          </a>
        )}
      </div>
    </div>
  );
};

export default DownloadProgress;
