import React from 'react';
import { Outlet } from 'react-router-dom';
import AppNav from './AppNav';

const FloatingDots: React.FC = () => (
  <div className="fixed inset-0 pointer-events-none overflow-hidden z-0">
    <div className="absolute top-20 left-10 w-64 h-64 bg-primary/5 rounded-full blur-3xl" />
    <div className="absolute bottom-40 right-20 w-96 h-96 bg-secondary/5 rounded-full blur-3xl" />
    <div className="absolute top-1/2 left-1/3 w-48 h-48 bg-primary/3 rounded-full blur-2xl animate-float" />
    <div
      className="absolute top-32 right-1/4 w-3 h-3 bg-secondary/30 rounded-full animate-float"
      style={{ animationDelay: '0.5s' }}
    />
    <div
      className="absolute top-1/3 left-1/4 w-2 h-2 bg-primary/30 rounded-full animate-float"
      style={{ animationDelay: '1s' }}
    />
    <div
      className="absolute bottom-1/4 right-1/3 w-4 h-4 bg-secondary/20 rounded-full animate-float"
      style={{ animationDelay: '1.5s' }}
    />
  </div>
);

interface AppShellProps {
  platformCount: number;
}

const AppShell: React.FC<AppShellProps> = ({ platformCount }) => {
  return (
    <div className="min-h-screen relative">
      <FloatingDots />

      <header className="sticky top-0 z-20 backdrop-blur-xl bg-white/70 border-b border-gray-100/50 shadow-sm">
        <div className="max-w-2xl mx-auto px-4 py-3">
          <div className="flex items-center gap-4">
            <div className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg shadow-secondary/20">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                  />
                </svg>
              </div>
              <div className="absolute inset-0 rounded-xl bg-gradient-to-tr from-white/30 to-transparent pointer-events-none" />
            </div>

            <div className="flex-1">
              <h1 className="font-display text-lg text-gray-800">漫画下载器</h1>
              <AppNav />
            </div>

            <div className="hidden sm:flex items-center gap-2 text-xs text-gray-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
              <span>{platformCount} 平台</span>
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-10 max-w-2xl mx-auto px-4 py-6 space-y-6">
        <Outlet />
      </main>

      <footer className="relative z-10 max-w-2xl mx-auto px-4 py-8 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/50 backdrop-blur-sm border border-gray-100">
          <span className="text-xs text-gray-400">仅供学习交流使用</span>
          <span className="w-1 h-1 rounded-full bg-gray-300" />
          <span className="text-xs text-gray-400">请勿用于商业用途</span>
        </div>
      </footer>
    </div>
  );
};

export default AppShell;
