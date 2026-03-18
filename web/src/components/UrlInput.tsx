import React, { useState, useRef } from 'react';
import { Platform } from '../api/client';

interface UrlInputProps {
  onDownload: (url: string) => void;
  onBatchDownload?: (urls: string[]) => void;
  disabled: boolean;
  platforms: Platform[];
}

const UrlInput: React.FC<UrlInputProps> = ({ onDownload, onBatchDownload, disabled, platforms }) => {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [focused, setFocused] = useState(false);
  const [isBatchMode, setIsBatchMode] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const validateUrl = (value: string): { valid: boolean; platform?: Platform } => {
    if (!value.trim()) {
      return { valid: false };
    }

    for (const platform of platforms) {
      for (const pattern of platform.patterns) {
        try {
          const regex = new RegExp(pattern);
          if (regex.test(value)) {
            return { valid: true, platform };
          }
        } catch {
          if (value.includes(pattern.replace(/\\/g, '').replace(/\./g, '.'))) {
            return { valid: true, platform };
          }
        }
      }
    }

    return { valid: false };
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!url.trim()) {
      setError('请输入漫画 URL');
      return;
    }

    // 检测是否是批量模式（多行输入）
    const lines = url.trim().split('\n').filter(line => line.trim() !== '');

    if (lines.length > 1 && onBatchDownload) {
      // 批量下载模式
      const validUrls: string[] = [];
      const invalidUrls: string[] = [];

      for (const line of lines) {
        const { valid, platform } = validateUrl(line);
        if (valid) {
          validUrls.push(line);
        } else {
          invalidUrls.push(line);
        }
      }

      if (validUrls.length === 0) {
        setError(`所有 URL 都无效，请输入支持的漫画网站链接`);
        return;
      }

      if (invalidUrls.length > 0) {
        setError(`部分 URL 无效（已跳过 ${invalidUrls.length} 个）`);
      }

      onBatchDownload(validUrls);
    } else {
      // 单个下载模式
      const { valid } = validateUrl(url);
      if (!valid) {
        const platformNames = platforms.map(p => p.display_name).join('、');
        setError(`请输入支持的漫画网站链接 (${platformNames})`);
        return;
      }

      onDownload(url);
    }
  };

  const toggleBatchMode = () => {
    setIsBatchMode(!isBatchMode);
    setUrl('');
    setError('');
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Mode Toggle */}
      {onBatchDownload && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={toggleBatchMode}
            disabled={disabled}
            className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
              isBatchMode
                ? 'bg-primary text-white shadow-lg shadow-primary/20'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {isBatchMode ? (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                批量下载模式
              </span>
            ) : (
              <span className="flex items-center gap-2">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                批量下载
              </span>
            )}
          </button>
        </div>
      )}

      {/* Input container with animated border */}
      <div
        className={`relative rounded-2xl transition-all duration-300 ${
          focused ? 'gradient-border' : ''
        }`}
      >
        <div className="relative flex flex-col bg-white rounded-2xl overflow-hidden">
          {/* Icon */}
          <div className="pl-5 pr-3 pt-5 text-2xl opacity-60">
            <svg
              className="w-6 h-6 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
              />
            </svg>
          </div>

          {/* Input/Textarea */}
          {isBatchMode ? (
            <textarea
              ref={textareaRef}
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError('');
              }}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="粘贴多个漫画链接，每行一个..."
              disabled={disabled}
              rows={6}
              className="flex-1 px-5 pb-5 text-base bg-transparent outline-none resize-none
                         placeholder:text-gray-400 disabled:opacity-60 disabled:cursor-not-allowed font-mono text-sm"
            />
          ) : (
            <input
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setError('');
              }}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="粘贴漫画章节链接..."
              disabled={disabled}
              className="flex-1 py-5 pr-5 text-base bg-transparent outline-none
                         placeholder:text-gray-400 disabled:opacity-60 disabled:cursor-not-allowed"
            />
          )}

          {/* Clear button */}
          {url && !disabled && (
            <button
              type="button"
              onClick={() => setUrl('')}
              className="pr-4 pt-4 text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="flex items-center gap-2 text-red-500 text-sm pl-1 animate-[fadeIn_0.3s_ease]">
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
          {error}
        </div>
      )}

      {/* Submit button */}
      <button
        type="submit"
        disabled={disabled}
        className="btn-primary w-full py-4 text-base font-medium text-white rounded-2xl
                   bg-gradient-to-r from-primary via-[#7C3AED] to-secondary
                   bg-[length:200%_100%] hover:bg-right
                   disabled:opacity-60 disabled:cursor-not-allowed
                   shadow-lg shadow-primary/20 hover:shadow-secondary/30
                   transition-all duration-500"
      >
        {disabled ? (
          <span className="flex items-center justify-center gap-3">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span>处理中</span>
            <span className="flex gap-1">
              <span className="loading-dot w-1.5 h-1.5 bg-white rounded-full"></span>
              <span className="loading-dot w-1.5 h-1.5 bg-white rounded-full"></span>
              <span className="loading-dot w-1.5 h-1.5 bg-white rounded-full"></span>
            </span>
          </span>
        ) : (
          <span className="flex items-center justify-center gap-2">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            {isBatchMode ? '批量开始下载' : '开始下载'}
          </span>
        )}
      </button>

      {/* Example URL hints */}
      <div className="space-y-1 text-center text-xs text-gray-400">
        <p>支持的平台：{platforms.map(p => p.display_name).join('、')}</p>
        {isBatchMode ? (
          <p>批量模式：每行粘贴一个链接，支持最多 20 个链接</p>
        ) : (
          <p>示例：https://www.manhuagui.com/comic/58667/868543.html</p>
        )}
      </div>
    </form>
  );
};

export default UrlInput;
