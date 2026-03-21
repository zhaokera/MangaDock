import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  getMangaChapters,
  getPlatforms,
  searchManga,
  startBatchDownload,
  startDownload,
  subscribeProgress,
  type MangaChapterCatalog,
  type MangaSearchResult,
  type Platform,
  type TaskStatus,
} from '../api/client';
import DownloadProgress from '../components/DownloadProgress';
import MangaChapterPicker from '../components/MangaChapterPicker';
import MangaDownloadConfirm from '../components/MangaDownloadConfirm';
import MangaSearchInput from '../components/MangaSearchInput';
import MangaSearchResults from '../components/MangaSearchResults';
import History from '../components/History';
import UrlInput from '../components/UrlInput';

interface MangaPageProps {
  platforms: Platform[];
}

const PLATFORM_COLORS: Record<string, { primary: string; secondary: string }> = {
  manhuagui: { primary: '#10B981', secondary: '#34D399' },
  default: { primary: '#6366F1', secondary: '#EC4899' },
};

const getPlatformColor = (platform?: string) => {
  if (!platform) {
    return PLATFORM_COLORS.default;
  }

  return PLATFORM_COLORS[platform] || PLATFORM_COLORS.default;
};

const MangaPage: React.FC<MangaPageProps> = ({ platforms }) => {
  const [downloading, setDownloading] = useState(false);
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [allPlatforms, setAllPlatforms] = useState<Platform[]>(platforms);
  const [searchAttempted, setSearchAttempted] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<MangaSearchResult[]>([]);
  const [chapterLoading, setChapterLoading] = useState(false);
  const [chapterCatalog, setChapterCatalog] = useState<MangaChapterCatalog | null>(null);
  const [selectedChapterUrls, setSelectedChapterUrls] = useState<string[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmPending, setConfirmPending] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    getPlatforms()
      .then((data) => setAllPlatforms(data.platforms || []))
      .catch(console.error);

    return () => {
      unsubscribeRef.current?.();
    };
  }, []);

  const resetChapterFlow = useCallback(() => {
    setChapterLoading(false);
    setChapterCatalog(null);
    setSelectedChapterUrls([]);
    setConfirmOpen(false);
    setConfirmPending(false);
  }, []);

  const handleSearch = useCallback(async (keyword: string, platform: string) => {
    try {
      setSearchAttempted(true);
      setSearchLoading(true);
      setSearchResults([]);
      resetChapterFlow();

      const result = await searchManga(keyword, platform);
      setSearchResults(result.results || []);
    } catch (error) {
      console.error('漫画搜索失败', error);
      alert(error instanceof Error ? error.message : '漫画搜索失败');
    } finally {
      setSearchLoading(false);
    }
  }, [resetChapterFlow]);

  const handleSelectSearchResult = useCallback(async (result: MangaSearchResult) => {
    try {
      setChapterLoading(true);
      setChapterCatalog(null);
      setSelectedChapterUrls([]);
      setConfirmOpen(false);
      setConfirmPending(false);

      const catalog = await getMangaChapters(result.url, result.platform);
      setChapterCatalog(catalog);
    } catch (error) {
      console.error('获取漫画章节失败', error);
      alert(error instanceof Error ? error.message : '获取章节失败');
    } finally {
      setChapterLoading(false);
    }
  }, []);

  const handleToggleChapter = useCallback((url: string) => {
    setSelectedChapterUrls((current) => (
      current.includes(url)
        ? current.filter((item) => item !== url)
        : [...current, url]
    ));
  }, []);

  const handleSelectAllChapters = useCallback(() => {
    setSelectedChapterUrls(chapterCatalog?.chapters.map((chapter) => chapter.url) || []);
  }, [chapterCatalog]);

  const handleClearAllChapters = useCallback(() => {
    setSelectedChapterUrls([]);
  }, []);

  const handleOpenConfirm = useCallback(() => {
    if (selectedChapterUrls.length === 0) {
      return;
    }

    setConfirmOpen(true);
  }, [selectedChapterUrls.length]);

  const selectedChapters = chapterCatalog?.chapters.filter((chapter) => selectedChapterUrls.includes(chapter.url)) || [];

  const handleBatchDownload = useCallback(async (urls: string[]) => {
    try {
      setDownloading(true);
      setCurrentTask(null);
      unsubscribeRef.current?.();
      unsubscribeRef.current = null;

      const result = await startBatchDownload(urls);

      if (result.success > 0) {
        alert(`成功创建 ${result.success} 个下载任务！\n失败: ${result.failed} 个`);
      } else {
        alert('所有任务创建失败，请检查 URL 是否正确');
      }

      // Batch mode intentionally tracks only the first successful task in the single-progress UI.
      const firstSuccessfulTaskId = result.results.find((item) => item.task_id)?.task_id;
      if (!firstSuccessfulTaskId) {
        setDownloading(false);
        return;
      }

      unsubscribeRef.current = subscribeProgress(firstSuccessfulTaskId, (status) => {
        setCurrentTask(status);
        if (status.status === 'completed' || status.status === 'failed') {
          setDownloading(false);
        }
      });
    } catch (error) {
      console.error('批量下载失败', error);
      setDownloading(false);
      alert(error instanceof Error ? error.message : '批量下载失败');
    }
  }, []);

  const handleConfirmDownload = useCallback(async () => {
    if (selectedChapterUrls.length === 0) {
      return;
    }

    setConfirmPending(true);
    setConfirmOpen(false);

    try {
      await handleBatchDownload(selectedChapterUrls);
    } finally {
      setConfirmPending(false);
    }
  }, [handleBatchDownload, selectedChapterUrls]);

  const handleDownload = useCallback(async (url: string) => {
    try {
      setDownloading(true);
      setCurrentTask(null);
      unsubscribeRef.current?.();

      const result = await startDownload(url);

      unsubscribeRef.current = subscribeProgress(result.task_id, (status) => {
        setCurrentTask(status);
        if (status.status === 'completed' || status.status === 'failed') {
          setDownloading(false);
        }
      });
    } catch (error) {
      console.error('下载失败', error);
      setDownloading(false);
      alert(error instanceof Error ? error.message : '下载失败');
    }
  }, []);

  return (
    <>
      <section className="text-center mb-8">
        <h2 className="font-display text-3xl mb-2">
          <span className="gradient-text">一键下载</span>
          <span className="text-gray-700"> 喜爱的漫画</span>
        </h2>
        <p className="text-gray-400">先搜索漫画章节，或直接粘贴章节链接下载</p>
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
          <h2 className="font-bold text-gray-800">搜索漫画</h2>
        </div>
        <MangaSearchInput platforms={platforms} loading={searchLoading || downloading} onSearch={handleSearch} />

        {searchAttempted && (
          <div className="mt-5">
            <MangaSearchResults
              results={searchResults}
              loading={searchLoading}
              onSelect={handleSelectSearchResult}
              actionLabel={(result) => `查看章节 ${result.title}`}
            />
          </div>
        )}

        {chapterLoading && (
          <div className="mt-5 text-sm text-gray-500">
            正在获取章节...
          </div>
        )}

        {chapterCatalog && !chapterLoading && !confirmOpen && (
          <div className="mt-5 space-y-4">
            <div className="rounded-2xl border border-gray-100 p-4">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-gray-800">{chapterCatalog.title}</h3>
                <p className="text-sm text-gray-500">{chapterCatalog.platform_display}</p>
              </div>
              <MangaChapterPicker
                chapters={chapterCatalog.chapters}
                selectedUrls={selectedChapterUrls}
                onToggleChapter={handleToggleChapter}
                onSelectAll={handleSelectAllChapters}
                onClearAll={handleClearAllChapters}
                chapterLabelPrefix="选择章节"
              />
            </div>

            <button
              type="button"
              onClick={handleOpenConfirm}
              disabled={selectedChapterUrls.length === 0 || downloading}
              className="rounded-2xl bg-primary px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              下载所选章节
            </button>
          </div>
        )}

        {chapterCatalog && confirmOpen && !chapterLoading && (
          <div className="mt-5">
            <MangaDownloadConfirm
              title={chapterCatalog.title}
              platformDisplay={chapterCatalog.platform_display}
              chapters={selectedChapters}
              pending={confirmPending}
              onConfirm={handleConfirmDownload}
              onBack={() => setConfirmOpen(false)}
            />
          </div>
        )}
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
          <h2 className="font-bold text-gray-800">输入链接</h2>
        </div>
        <UrlInput
          contentType="manga"
          onDownload={handleDownload}
          onBatchDownload={handleBatchDownload}
          disabled={downloading}
          platforms={platforms}
          allPlatforms={allPlatforms}
        />
      </section>

      {currentTask && (
        <section className="animate-[fadeIn_0.3s_ease]">
          <DownloadProgress
            status={currentTask}
            contentType="manga"
            idleLabel="漫画下载进度"
          />
        </section>
      )}

      <section>
        <History
          contentType="manga"
          emptyTitle="暂无漫画下载记录"
          emptyHint="下载的漫画会显示在这里"
        />
      </section>

      <section className="glass-card rounded-3xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100/50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center">
              <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
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
              { step: 3, text: '粘贴漫画章节链接到上方输入框' },
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

          <div className="mt-4 p-4 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-100">
            <div className="flex items-start gap-3">
              <div className="w-5 h-5 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0 mt-0.5">
                <svg className="w-3 h-3 text-amber-600" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                    clipRule="evenodd"
                  />
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

    </>
  );
};

export default MangaPage;
