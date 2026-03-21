import React from 'react';
import type { MangaSearchResult } from '../api/client';

interface MangaSearchResultsProps {
  results: MangaSearchResult[];
  loading?: boolean;
  disabled?: boolean;
  errorMessage?: string | null;
  onSelect: (result: MangaSearchResult) => void;
  actionLabel?: string | ((result: MangaSearchResult) => string);
}

const MangaSearchResults: React.FC<MangaSearchResultsProps> = ({
  results,
  loading = false,
  disabled = false,
  errorMessage = null,
  onSelect,
  actionLabel,
}) => {
  const getActionLabel = (result: MangaSearchResult) => {
    if (typeof actionLabel === 'function') {
      return actionLabel(result);
    }

    return actionLabel || '选择';
  };

  if (loading) {
    return <div>正在搜索...</div>;
  }

  if (errorMessage) {
    return <div>{errorMessage}</div>;
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
              disabled={disabled}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
            >
              {getActionLabel(result)}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default MangaSearchResults;
