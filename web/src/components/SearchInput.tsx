import React, { useState } from 'react';
import { searchVideos, type SearchResult } from '../api/client';

interface SearchInputProps {
  platforms: Array<{ name: string; display_name: string }>;
  onSearch: (keyword: string, platform?: string) => void;
  onResultSelect: (result: SearchResult) => void;
  lockedPlatform?: string;
  hidePlatformSelector?: boolean;
  title?: string;
  placeholder?: string;
}

// 平台颜色配置
const PLATFORM_COLORS: Record<string, { primary: string; secondary: string; bg: string }> = {
  tencent: {
    primary: '#00AEE1',
    secondary: '#0066AA',
    bg: 'from-[#00AEE1]/5 to-[#0066AA]/5',
  },
  iqiyi: {
    primary: '#FF5252',
    secondary: '#D32F2F',
    bg: 'from-[#FF5252]/5 to-[#D32F2F]/5',
  },
  youku: {
    primary: '#FFE600',
    secondary: '#FFC100',
    bg: 'from-[#FFE600]/5 to-[#FFC100]/5',
  },
  mango: {
    primary: '#F57C00',
    secondary: '#E65100',
    bg: 'from-[#F57C00]/5 to-[#E65100]/5',
  },
  default: {
    primary: '#6366F1',
    secondary: '#EC4899',
    bg: 'from-[#6366F1]/5 to-[#EC4899]/5',
  },
};

const SearchInput: React.FC<SearchInputProps> = ({
  platforms,
  onSearch,
  onResultSelect,
  lockedPlatform,
  hidePlatformSelector = false,
  title = '搜索动漫/视频',
  placeholder = '输入动漫或视频名称...',
}) => {
  const [keyword, setKeyword] = useState('');
  const [platform, setPlatform] = useState<string>(lockedPlatform ?? '');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');

  const getPlatformColor = (platformName?: string) => {
    if (!platformName) return PLATFORM_COLORS.default;
    return PLATFORM_COLORS[platformName] || PLATFORM_COLORS.default;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!keyword.trim()) {
      setError('请输入搜索关键词');
      return;
    }

    setLoading(true);
    setSearched(true);
    setResults([]);
    setError('');

    try {
      const selectedPlatform = lockedPlatform ?? platform ?? undefined;
      onSearch(keyword, selectedPlatform);
      const data = await searchVideos(keyword, selectedPlatform, 15);
      setResults(data.results || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : '搜索失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSelectResult = (result: SearchResult) => {
    onResultSelect(result);
    // 可选：滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="space-y-6">
      {/* Search Form */}
      <form onSubmit={handleSubmit} className="glass-card rounded-3xl p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/10 to-secondary/10 flex items-center justify-center">
            <svg className="w-4 h-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
          <h2 className="font-bold text-gray-800">{title}</h2>
        </div>

        <div className="space-y-4">
          {/* Platform Selector */}
          {!hidePlatformSelector && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">平台筛选</label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setPlatform('')}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    platform === ''
                      ? 'bg-primary text-white shadow-lg shadow-primary/20'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  全部平台
                </button>
                {platforms.map(p => {
                  const colors = getPlatformColor(p.name);
                  const selected = platform === p.name;
                  return (
                    <button
                      key={p.name}
                      type="button"
                      onClick={() => setPlatform(p.name)}
                      style={
                        selected
                          ? {
                              backgroundImage: `linear-gradient(135deg, ${colors.primary}, ${colors.secondary})`,
                              boxShadow: `0 10px 25px ${colors.primary}33`,
                            }
                          : undefined
                      }
                      className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                        selected ? 'text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {p.display_name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="relative">
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleSubmit(e as any);
                }
              }}
              placeholder={placeholder}
              disabled={loading}
              className="w-full px-5 py-4 text-base bg-white border border-gray-200 rounded-2xl outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all disabled:opacity-60 disabled:cursor-not-allowed"
            />
            <button
              type="submit"
              disabled={loading || !keyword.trim()}
              className="absolute right-3 top-1/2 -translate-y-1/2 px-6 py-2 bg-primary text-white rounded-xl font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? '搜索中...' : '搜索'}
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-center gap-2 text-red-500 text-sm">
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              {error}
            </div>
          )}
        </div>
      </form>

      {/* Results */}
      {searched && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-bold text-gray-800">
              搜索结果 {loading ? '(加载中...)' : results.length > 0 ? `(${results.length})` : ''}
            </h3>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-400">
              <svg className="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              正在搜索...
            </div>
          ) : error ? (
            <div className="text-center py-12 glass-card rounded-3xl">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-red-50 to-rose-50 flex items-center justify-center">
                <svg className="w-8 h-8 text-red-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M10.29 3.86l-7.4 12.81A2 2 0 004.62 19h14.76a2 2 0 001.73-3.03l-7.4-12.81a2 2 0 00-3.46 0z" />
                </svg>
              </div>
              <p className="text-red-500 text-sm">搜索失败</p>
              <p className="text-gray-400 text-xs mt-1">{error}</p>
            </div>
          ) : results.length === 0 ? (
            <div className="text-center py-12 glass-card rounded-3xl">
              <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-gray-100 to-gray-50 flex items-center justify-center">
                <svg className="w-8 h-8 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <p className="text-gray-400 text-sm">未找到相关结果</p>
              <p className="text-gray-300 text-xs mt-1">尝试更换关键词或平台</p>
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((result) => {
                const colors = getPlatformColor(result.platform);
                return (
                  <div
                    key={`${result.platform}-${result.url}`}
                    className="glass-card group rounded-2xl p-4 hover:shadow-lg transition-all duration-300 border border-transparent hover:border-primary/20"
                    style={{
                      background: `linear-gradient(to right, transparent 0%, ${colors.primary}05 100%)`,
                    }}
                  >
                    <div className="flex items-start gap-4">
                      {/* Platform badge */}
                      <div
                        className={`w-12 h-16 rounded-xl flex items-center justify-center flex-shrink-0 ${colors.bg}`}
                      >
                        <span className="text-xs font-bold text-gray-600">
                          {result.platform_display.substring(0, 2)}
                        </span>
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h4 className="font-medium text-gray-800 truncate group-hover:text-primary transition-colors">
                              {result.title}
                            </h4>
                            <div className="flex items-center gap-2 mt-2">
                              <span
                                className="text-xs font-medium px-2.5 py-1 rounded-full"
                                style={{
                                  background: `linear-gradient(135deg, ${colors.primary}10, ${colors.secondary}10)`,
                                  color: colors.primary,
                                }}
                              >
                                {result.platform_display}
                              </span>
                              <span className="text-xs text-gray-400">
                                匹配度: {result.score.toFixed(0)}%
                              </span>
                            </div>
                          </div>
                        </div>

                        <div className="mt-4 flex items-center gap-3">
                          <a
                            href={result.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-1 text-center py-2.5 text-sm font-medium text-gray-700 bg-gray-100 rounded-xl hover:bg-gray-200 transition-colors"
                          >
                            浏览详情
                          </a>
                          <button
                            onClick={() => handleSelectResult(result)}
                            className="flex-1 text-center py-2.5 text-sm font-medium text-white rounded-xl
                                       bg-gradient-to-r from-primary via-[#7C3AED] to-secondary hover:bg-right
                                       shadow-lg shadow-primary/20 hover:shadow-secondary/30
                                       transition-all duration-500"
                          >
                            下载
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Help */}
      <div className="glass-card rounded-3xl p-6">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center flex-shrink-0">
            <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p className="text-sm font-medium text-gray-800">使用说明</p>
            <p className="text-xs text-gray-500 mt-1">
              1. 输入动漫或视频名称进行搜索<br />
              2. 选择想要的平台筛选结果<br />
              3. 浏览详情确认后点击下载
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SearchInput;
