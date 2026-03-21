import React from 'react';
import type { MangaSearchResult } from '../api/client';

interface MangaSearchResultsProps {
  results: MangaSearchResult[];
  loading?: boolean;
  onSelect: (result: MangaSearchResult) => void;
}

const MangaSearchResults: React.FC<MangaSearchResultsProps> = ({ results, loading = false, onSelect }) => {
  if (loading) {
    return <div>正在搜索...</div>;
  }

  if (results.length === 0) {
    return <div>未找到相关结果</div>;
  }

  return (
    <div className="space-y-3">
      {results.map((result) => (
        <div key={`${result.platform}-${result.url}`} className="rounded-xl border border-gray-100 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="font-medium text-gray-800">{result.title}</p>
              <p className="text-xs text-gray-500">{result.platform_display}</p>
            </div>
            <button
              type="button"
              onClick={() => onSelect(result)}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white"
            >
              选择
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default MangaSearchResults;
