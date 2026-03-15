import React, { useState, useEffect, useCallback } from 'react';
import UrlInput from './components/UrlInput';
import DownloadProgress from './components/DownloadProgress';
import History from './components/History';
import { startDownload, subscribeProgress, TaskStatus, getPlatforms, Platform } from './api/client';

// 平台颜色配置
const PLATFORM_COLORS: Record<string, { primary: string; secondary: string; bg: string }> = {
  bilibili: {
    primary: '#00A1D6',
    secondary: '#FB7299',
    bg: 'from-[#00A1D6]/5 to-[#FB7299]/5',
  },
  manhuagui: {
    primary: '#10B981',
    secondary: '#34D399',
    bg: 'from-[#10B981]/5 to-[#34D399]/5',
  },
  default: {
    primary: '#6366F1',
    secondary: '#EC4899',
    bg: 'from-[#6366F1]/5 to-[#EC4899]/5',
  },
};

// Floating decoration component
const FloatingDots: React.FC = () => (
  <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
    {/* Decorative circles */}
    <div className="absolute top-20 left-10 w-64 h-64 bg-primary/5 rounded-full blur-3xl" />
    <div className="absolute bottom-40 right-20 w-96 h-96 bg-secondary/5 rounded-full blur-3xl" />
    <div className="absolute top-1/2 left-1/3 w-48 h-48 bg-primary/3 rounded-full blur-2xl animate-float" />

    {/* Small floating dots */}
    <div className="absolute top-32 right-1/4 w-3 h-3 bg-secondary/30 rounded-full animate-float" style={{ animationDelay: '0.5s' }} />
    <div className="absolute top-1/3 left-1/4 w-2 h-2 bg-primary/30 rounded-full animate-float" style={{ animationDelay: '1s' }} />
    <div className="absolute bottom-1/4 right-1/3 w-4 h-4 bg-secondary/20 rounded-full animate-float" style={{ animationDelay: '1.5s' }} />
  </div>
);

const App: React.FC = () => {
  const [downloading, setDownloading] = useState(false);
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [platforms, setPlatforms] = useState<Platform[]>([]);

  const unsubscribeRef = React.useRef<(() => void) | null>(null);

  useEffect(() => {
    // 加载支持的平台列表
    getPlatforms().then(data => setPlatforms(data.platforms || [])).catch(console.error);

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, []);

  const handleDownload = useCallback(async (url: string) => {
    try {
      setDownloading(true);
      setCurrentTask(null);

      const result = await startDownload(url);

      const unsubscribe = subscribeProgress(
        result.task_id,
        (status) => {
          setCurrentTask(status);
          if (status.status === 'completed' || status.status === 'failed') {
            setDownloading(false);
          }
        },
        (error) => {
          console.error('SSE 错误', error);
          setDownloading(false);
        }
      );

      unsubscribeRef.current = unsubscribe;

    } catch (error) {
      console.error('下载失败', error);
      setDownloading(false);
      alert(error instanceof Error ? error.message : '下载失败');
    }
  }, []);

  // 获取当前平台的颜色
  const getPlatformColor = (platform?: string) => {
    if (!platform) return PLATFORM_COLORS.default;
    return PLATFORM_COLORS[platform] || PLATFORM_COLORS.default;
  };

  return (
    <div className="min-h-screen relative">
      {/* Background decorations */}
      <FloatingDots />

      {/* Header */}
      <header className="sticky top-0 z-20 backdrop-blur-xl bg-white/70 border-b border-gray-100/50">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            {/* Logo */}
            <div className="relative">
              <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg shadow-secondary/20">
                <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
              {/* Shine effect */}
              <div className="absolute inset-0 rounded-2xl bg-gradient-to-tr from-white/30 to-transparent pointer-events-none" />
            </div>

            {/* Title */}
            <div>
              <h1 className="font-display text-xl text-gray-800">
                漫画下载器
              </h1>
              <p className="text-sm text-gray-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                支持 {platforms.length > 0 ? platforms.map(p => p.display_name).join('、') : '多个'}平台
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-2xl mx-auto px-4 py-8 space-y-6">

        {/* Hero section */}
        <section className="text-center mb-8">
          <h2 className="font-display text-3xl mb-2">
            <span className="gradient-text">一键下载</span>
            <span className="text-gray-700"> 喜爱的漫画</span>
          </h2>
          <p className="text-gray-400">粘贴漫画链接，自动识别平台并下载</p>
        </section>

        {/* Supported platforms */}
        {platforms.length > 0 && (
          <section className="flex flex-wrap justify-center gap-2 mb-6">
            {platforms.map(p => {
              const colors = getPlatformColor(p.name);
              return (
                <div
                  key={p.name}
                  className="px-3 py-1.5 rounded-full text-xs font-medium bg-gradient-to-r text-gray-600 border border-gray-100"
                  style={{
                    background: `linear-gradient(135deg, ${colors.primary}10, ${colors.secondary}10)`,
                  }}
                >
                  {p.display_name}
                </div>
              );
            })}
          </section>
        )}

        {/* URL Input Card */}
        <section className="glass-card rounded-3xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/10 to-secondary/10 flex items-center justify-center">
              <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
              </svg>
            </div>
            <h2 className="font-bold text-gray-800">输入链接</h2>
          </div>
          <UrlInput onDownload={handleDownload} disabled={downloading} platforms={platforms} />
        </section>

        {/* Download Progress */}
        {currentTask && (
          <section className="animate-[fadeIn_0.3s_ease]">
            <DownloadProgress status={currentTask} />
          </section>
        )}

        {/* History */}
        <section>
          <History />
        </section>

        {/* Help section */}
        <section className="glass-card rounded-3xl overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100/50">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
                <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h2 className="font-bold text-gray-800">使用指南</h2>
            </div>
          </div>

          <div className="p-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {[
                { step: 1, text: '打开漫画网站，找到想下载的章节' },
                { step: 2, text: '复制章节链接' },
                { step: 3, text: '粘贴链接到上方输入框' },
                { step: 4, text: '点击下载，等待完成' },
              ].map((item) => (
                <div key={item.step} className="flex items-start gap-3 p-3 rounded-xl hover:bg-gray-50 transition-colors">
                  <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-white">{item.step}</span>
                  </div>
                  <p className="text-sm text-gray-600 leading-relaxed">{item.text}</p>
                </div>
              ))}
            </div>

            {/* Warning */}
            <div className="mt-4 p-4 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100">
              <div className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <svg className="w-3 h-3 text-amber-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-medium text-amber-800">温馨提示</p>
                  <p className="text-xs text-amber-600 mt-0.5">部分付费漫画需要登录对应平台账号才能下载</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="relative z-10 max-w-2xl mx-auto px-4 py-8 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/50 backdrop-blur-sm border border-gray-100">
          <span className="text-xs text-gray-400">仅供学习交流使用</span>
          <span className="w-1 h-1 rounded-full bg-gray-300" />
          <span className="text-xs text-gray-400">请勿用于商业用途</span>
        </div>
      </footer>

      {/* Global keyframe animation */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};

export default App;