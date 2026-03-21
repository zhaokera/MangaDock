import React, { useEffect, useState } from 'react';

interface MangaSearchInputProps {
  platforms: Array<{ name: string; display_name: string }>;
  loading: boolean;
  onSearch: (keyword: string, platform: string) => void;
}

const MangaSearchInput: React.FC<MangaSearchInputProps> = ({ platforms, loading, onSearch }) => {
  const [keyword, setKeyword] = useState('');
  const [platform, setPlatform] = useState(platforms[0]?.name ?? '');

  useEffect(() => {
    if (platforms.length === 0) {
      if (platform !== '') {
        setPlatform('');
      }
      return;
    }

    if (!platforms.some((item) => item.name === platform)) {
      setPlatform(platforms[0].name);
    }
  }, [platform, platforms]);

  const hasValidPlatform = platforms.some((item) => item.name === platform);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!keyword.trim() || !hasValidPlatform) {
      return;
    }

    onSearch(keyword.trim(), platform);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="flex flex-col gap-3">
        <label className="text-sm font-medium text-gray-700">
          平台
          <select
            className="mt-2 w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm outline-none focus:border-primary"
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
            disabled={loading}
          >
            {platforms.map((item) => (
              <option key={item.name} value={item.name}>
                {item.display_name}
              </option>
            ))}
          </select>
        </label>

        <input
          type="text"
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="输入漫画名称..."
          disabled={loading}
          className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm outline-none focus:border-primary"
        />
      </div>

      <button
        type="submit"
        disabled={loading || !keyword.trim() || !hasValidPlatform}
        className="rounded-xl bg-primary px-5 py-3 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? '搜索中...' : '搜索'}
      </button>
    </form>
  );
};

export default MangaSearchInput;
