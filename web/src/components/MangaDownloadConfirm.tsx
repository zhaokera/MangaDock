import React from 'react';
import type { MangaChapter } from '../api/client';

interface MangaDownloadConfirmProps {
  title: string;
  platformDisplay: string;
  chapters: MangaChapter[];
  pending: boolean;
  onConfirm: () => void;
  onBack: () => void;
}

const MangaDownloadConfirm: React.FC<MangaDownloadConfirmProps> = ({
  title,
  platformDisplay,
  chapters,
  pending,
  onConfirm,
  onBack,
}) => {
  return (
    <div className="space-y-4 rounded-2xl border border-gray-100 p-4">
      <div className="space-y-1">
        <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
        <p className="text-sm text-gray-500">{platformDisplay}</p>
        <p className="text-sm text-gray-600">已选择 {chapters.length} 个章节</p>
      </div>

      <div className="flex gap-3">
        <button type="button" onClick={onBack} className="rounded-xl border border-gray-200 px-4 py-2 text-sm">
          返回
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={pending}
          className="rounded-xl bg-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? '处理中...' : `确认下载 ${chapters.length} 个章节`}
        </button>
      </div>
    </div>
  );
};

export default MangaDownloadConfirm;
