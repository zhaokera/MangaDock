import React from 'react';
import type { MangaChapter } from '../api/client';

interface MangaChapterPickerProps {
  chapters: MangaChapter[];
  selectedUrls: string[];
  onToggleChapter: (url: string) => void;
  onSelectAll: () => void;
  onClearAll: () => void;
  chapterLabelPrefix?: string;
}

const MangaChapterPicker: React.FC<MangaChapterPickerProps> = ({
  chapters,
  selectedUrls,
  onToggleChapter,
  onSelectAll,
  onClearAll,
  chapterLabelPrefix = '选择章节',
}) => {
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button type="button" onClick={onSelectAll} className="rounded-lg border border-gray-200 px-3 py-2 text-sm">
          全选
        </button>
        <button type="button" onClick={onClearAll} className="rounded-lg border border-gray-200 px-3 py-2 text-sm">
          清空
        </button>
      </div>

      <div className="space-y-2">
        {chapters.map((chapter) => {
          const checked = selectedUrls.includes(chapter.url);

          return (
            <label key={chapter.url} className="flex items-center gap-3 rounded-xl border border-gray-100 px-4 py-3">
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggleChapter(chapter.url)}
                aria-label={`${chapterLabelPrefix} ${chapter.title}`}
              />
              <span className="text-sm text-gray-700">{chapter.title}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
};

export default MangaChapterPicker;
