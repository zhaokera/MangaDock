import React, { useEffect, useState } from 'react';
import { HistoryItem, getHistory, getDownloadUrl } from '../api/client';

// 平台显示配置
const PLATFORM_CONFIG: Record<string, { name: string; color: string; bg: string }> = {
  manhuagui: {
    name: '漫画柜',
    color: 'text-emerald-500',
    bg: 'bg-gradient-to-br from-emerald-100/50 to-green-100/50',
  },
  default: {
    name: '漫画',
    color: 'text-primary',
    bg: 'bg-gradient-to-br from-primary/10 to-secondary/10',
  },
};

const History: React.FC = () => {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHistory();
    const interval = setInterval(loadHistory, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadHistory = async () => {
    try {
      const data = await getHistory();
      setHistory(data.history || []);
    } catch (e) {
      console.error('加载历史失败', e);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diff = now.getTime() - date.getTime();
      const minutes = Math.floor(diff / 60000);
      const hours = Math.floor(diff / 3600000);

      if (minutes < 1) return '刚刚';
      if (minutes < 60) return `${minutes} 分钟前`;
      if (hours < 24) return `${hours} 小时前`;

      return date.toLocaleDateString('zh-CN', {
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return '';
    }
  };

  const formatFileSize = (pages: number) => {
    const kb = pages * 300;
    if (kb < 1024) return `${kb}KB`;
    return `${(kb / 1024).toFixed(1)}MB`;
  };

  const getPlatformConfig = (platform?: string) => {
    if (!platform) return PLATFORM_CONFIG.default;
    return PLATFORM_CONFIG[platform] || PLATFORM_CONFIG.default;
  };

  return (
    <div className="glass-card rounded-3xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-100/50 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary/10 to-secondary/10 flex items-center justify-center">
            <svg className="w-5 h-5 text-secondary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <h3 className="font-bold text-gray-800">下载历史</h3>
            {!loading && history.length > 0 && (
              <p className="text-xs text-gray-400">共 {history.length} 条记录</p>
            )}
          </div>
        </div>

        {!loading && history.length > 0 && (
          <div className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
            自动更新
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        {loading ? (
          <div className="flex items-center justify-center py-12 text-gray-400">
            <svg className="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            加载中...
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-50 flex items-center justify-center">
              <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
            </div>
            <p className="text-gray-400 text-sm">暂无下载记录</p>
            <p className="text-gray-300 text-xs mt-1">下载的漫画会显示在这里</p>
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((item, index) => {
              const platformConfig = getPlatformConfig(item.platform);

              return (
                <div
                  key={item.task_id || index}
                  className="history-item group flex items-center gap-4 p-3 rounded-2xl
                             hover:bg-gradient-to-r hover:from-gray-50 hover:to-white
                             border border-transparent hover:border-gray-100"
                >
                  {/* Mini cover */}
                  <div className={`w-12 h-16 rounded-xl ${platformConfig.bg} flex items-center justify-center flex-shrink-0`}>
                    <svg className="w-6 h-6 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                    </svg>
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-800 truncate group-hover:text-primary transition-colors">
                      {item.title}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                      {/* Platform badge */}
                      {item.platform && (
                        <span className={`flex items-center gap-0.5 ${platformConfig.color}`}>
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                          </svg>
                          {platformConfig.name}
                        </span>
                      )}
                      <span className="w-1 h-1 rounded-full bg-gray-300" />
                      <span>{item.chapter}</span>
                      <span className="w-1 h-1 rounded-full bg-gray-300" />
                      <span>{item.page_count} 页</span>
                      <span className="w-1 h-1 rounded-full bg-gray-300" />
                      <span>{formatFileSize(item.page_count)}</span>
                    </div>
                  </div>

                  {/* Time & Action */}
                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-xs text-gray-400 hidden sm:block">
                      {formatTime(item.created_at)}
                    </span>

                    <a
                      href={getDownloadUrl(item.task_id)}
                      className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-secondary
                                 bg-secondary/10 rounded-xl
                                 opacity-0 group-hover:opacity-100
                                 hover:bg-secondary/20 transition-all duration-200"
                    >
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      下载
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default History;