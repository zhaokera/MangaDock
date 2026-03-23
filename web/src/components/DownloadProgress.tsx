import React, { useEffect, useMemo, useState } from 'react';
import { TaskStatus, getDownloadUrl } from '../api/client';
import { getContentTypeForPlatform, type ContentType } from '../lib/contentType';

interface DownloadProgressProps {
  status: TaskStatus | null;
  contentType: ContentType;
  idleLabel?: string;
  onReset?: () => void;
  onRetry?: () => void;
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

const extractFileName = (path: string | null | undefined) => {
  if (!path) {
    return null;
  }

  const normalized = path.split(/[\\/]/);
  return normalized[normalized.length - 1] || null;
};

const DownloadProgress: React.FC<DownloadProgressProps> = ({ status, contentType, idleLabel, onReset, onRetry }) => {
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const [errorCopyState, setErrorCopyState] = useState<'idle' | 'copied' | 'failed'>('idle');

  useEffect(() => {
    setCopyState('idle');
    setErrorCopyState('idle');
  }, [status?.task_id, status?.status]);

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
  const downloadHref = getDownloadUrl(task_id);
  const downloadFileName = extractFileName(status.zip_path) || `${contentLabel}-${task_id}.zip`;
  const taskTitle = manga_info?.title || `${contentLabel}下载任务`;
  const taskSubtitle = manga_info?.chapter || (taskStatus === 'completed' ? '结果文件已准备好，可以直接下载' : `${contentLabel}下载任务`);
  const copyText = copyState === 'copied' ? '链接已复制' : copyState === 'failed' ? '复制失败' : '复制下载链接';
  const absoluteDownloadHref = useMemo(() => {
    if (typeof window === 'undefined') {
      return downloadHref;
    }

    return new URL(downloadHref, window.location.origin).toString();
  }, [downloadHref]);

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

  const handleCopyLink = async () => {
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('clipboard unavailable');
      }

      await navigator.clipboard.writeText(absoluteDownloadHref);
      setCopyState('copied');
    } catch {
      setCopyState('failed');
    }
  };

  const handleCopyError = async () => {
    if (!error) {
      return;
    }

    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error('clipboard unavailable');
      }

      await navigator.clipboard.writeText(error);
      setErrorCopyState('copied');
    } catch {
      setErrorCopyState('failed');
    }
  };

  return (
    <div className="glass-card rounded-3xl overflow-hidden">
      {/* Header with task info */}
      <div className="px-6 py-5 border-b border-gray-100/50">
        <div className="flex items-start gap-4">
          <div className={`w-16 h-20 rounded-xl ${platformConfig.bg} flex items-center justify-center flex-shrink-0`}>
            <svg className="w-8 h-8 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </div>

          <div className="flex-1 min-w-0">
            <h3 className="font-bold text-lg text-gray-800 truncate">
              {taskTitle}
            </h3>
            <p className="text-gray-500 mt-0.5">
              {taskSubtitle}
            </p>

            <div className="flex items-center gap-2 mt-2">
              {platform && (
                <span className={`inline-flex items-center gap-1 text-xs ${platformConfig.color}`}>
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                  </svg>
                  {platformConfig.name}
                </span>
              )}

              {manga_info?.page_count && manga_info.page_count > 0 && (
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

          <div className={`px-3 py-1.5 rounded-full text-xs font-medium ${config.bg} ${config.color} ${config.border} border`}>
            {config.title}
          </div>
        </div>
      </div>

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

        {taskStatus === 'failed' && (
          <div className="rounded-2xl border border-red-100 bg-gradient-to-br from-red-50 via-white to-orange-50 p-4 text-sm text-gray-700">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-red-500">需要处理</p>
                <p className="mt-1 text-base font-semibold text-gray-900">这次下载没有成功，可以直接重试或复制错误信息。</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-red-600 shadow-sm">
                {platformConfig.name}
              </span>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {onRetry && (
                <button
                  type="button"
                  onClick={onRetry}
                  className="flex items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-red-500 to-orange-500 px-4 py-4 text-sm font-medium text-white shadow-lg shadow-red-200 transition-all hover:shadow-red-300"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 005.582 9m0 0H10m10 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H14" />
                  </svg>
                  重试下载
                </button>
              )}

              <button
                type="button"
                onClick={handleCopyError}
                className="flex items-center justify-center gap-3 rounded-2xl border border-red-200 bg-white px-4 py-4 text-sm font-medium text-red-700 transition-colors hover:border-red-300 hover:bg-red-50"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16h8M8 12h8m-6-8h5a2 2 0 012 2v12a2 2 0 01-2 2h-5m-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h1" />
                </svg>
                {errorCopyState === 'copied' ? '错误已复制' : errorCopyState === 'failed' ? '复制失败' : '复制错误信息'}
              </button>
            </div>
          </div>
        )}

        {taskStatus === 'completed' && (
          <div className="rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-teal-50 p-4 text-sm text-gray-700">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-500">结果已准备好</p>
                <p className="mt-1 text-base font-semibold text-gray-900">现在可以直接下载，或继续处理下一条。</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-emerald-600 shadow-sm">
                {platformConfig.name}
              </span>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl bg-white/80 px-3 py-3 shadow-sm ring-1 ring-emerald-100/70">
                <p className="text-[11px] uppercase tracking-[0.18em] text-gray-400">文件名</p>
                <p className="mt-1 truncate font-medium text-gray-800">{downloadFileName}</p>
              </div>
              <div className="rounded-xl bg-white/80 px-3 py-3 shadow-sm ring-1 ring-emerald-100/70">
                <p className="text-[11px] uppercase tracking-[0.18em] text-gray-400">任务编号</p>
                <p className="mt-1 font-mono text-sm text-gray-700">{task_id}</p>
              </div>
              <div className="rounded-xl bg-white/80 px-3 py-3 shadow-sm ring-1 ring-emerald-100/70">
                <p className="text-[11px] uppercase tracking-[0.18em] text-gray-400">结果类型</p>
                <p className="mt-1 font-medium text-gray-800">{status.zip_path ? 'ZIP 打包文件' : '下载结果文件'}</p>
              </div>
            </div>
          </div>
        )}

        {/* Download button */}
        {taskStatus === 'completed' && (
          <div className="grid gap-3 sm:grid-cols-2">
            <a
              href={downloadHref}
              className="btn-primary flex items-center justify-center gap-3 w-full py-4 text-white font-medium rounded-2xl
                         bg-gradient-to-r from-secondary to-[#FF8FAB]
                         shadow-lg shadow-secondary/30 hover:shadow-secondary/50
                         transition-all duration-300"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              {status.zip_path ? '下载 ZIP 文件' : '下载结果文件'}
            </a>

            <button
              type="button"
              onClick={handleCopyLink}
              className="flex items-center justify-center gap-3 w-full rounded-2xl border border-gray-200 bg-white px-4 py-4 text-sm font-medium text-gray-700 transition-colors hover:border-primary/30 hover:text-primary"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16h8M8 12h8m-6-8h5a2 2 0 012 2v12a2 2 0 01-2 2h-5m-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h1" />
              </svg>
              {copyText}
            </button>

            {onReset && (
              <button
                type="button"
                onClick={onReset}
                className="sm:col-span-2 flex items-center justify-center gap-3 rounded-2xl border border-dashed border-gray-300 bg-gray-50 px-4 py-3 text-sm font-medium text-gray-600 transition-colors hover:border-gray-400 hover:bg-gray-100"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                继续下载下一条
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default DownloadProgress;
