import React from 'react';
import { NavLink } from 'react-router-dom';

const linkBase =
  'px-3 py-1.5 text-xs font-medium rounded-lg transition-colors';

const AppNav: React.FC = () => {
  return (
    <nav aria-label="Primary" className="flex items-center gap-1 mt-1">
      <NavLink
        to="/manga"
        className={({ isActive }) =>
          `${linkBase} ${isActive ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:text-gray-600'}`
        }
      >
        漫画下载
      </NavLink>
      <NavLink
        to="/video"
        className={({ isActive }) =>
          `${linkBase} ${isActive ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:text-gray-600'}`
        }
      >
        视频下载
      </NavLink>
      <NavLink
        to="/dl-expo"
        className={({ isActive }) =>
          `${linkBase} ${isActive ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:text-gray-600'}`
        }
      >
        糯米影视
      </NavLink>
    </nav>
  );
};

export default AppNav;
