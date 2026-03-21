import React, { useEffect, useMemo, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { getPlatforms, type Platform } from './api/client';
import { getPlatformsForContentType } from './lib/contentType';
import AppShell from './components/AppShell';
import DlExpoPage from './pages/DlExpoPage';
import MangaPage from './pages/MangaPage';
import VideoPage from './pages/VideoPage';

const App: React.FC = () => {
  const [allPlatforms, setAllPlatforms] = useState<Platform[]>([]);

  useEffect(() => {
    getPlatforms()
      .then((data) => setAllPlatforms(data.platforms || []))
      .catch(console.error);
  }, []);

  const mangaPlatforms = useMemo(
    () => getPlatformsForContentType(allPlatforms, 'manga'),
    [allPlatforms],
  );
  const videoPlatforms = useMemo(
    () => getPlatformsForContentType(allPlatforms, 'video').filter((platform) => platform.name !== 'dl_expo'),
    [allPlatforms],
  );
  const dlExpoPlatforms = useMemo(
    () => allPlatforms.filter((platform) => platform.name === 'dl_expo'),
    [allPlatforms],
  );

  return (
    <Routes>
      <Route element={<AppShell platformCount={allPlatforms.length} />}>
        <Route index element={<Navigate to="/manga" replace />} />
        <Route
          path="manga"
          element={<MangaPage platforms={mangaPlatforms} />}
        />
        <Route
          path="video"
          element={<VideoPage platforms={videoPlatforms} />}
        />
        <Route
          path="dl-expo"
          element={<DlExpoPage platforms={dlExpoPlatforms} allPlatforms={allPlatforms} />}
        />
        <Route path="*" element={<Navigate to="/manga" replace />} />
      </Route>
    </Routes>
  );
};

export default App;
