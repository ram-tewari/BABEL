import { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout';
import { LoadingSpinner } from './components/ui';
import './index.css';

// Lazy load pages for improved performance (Task 18.1)
const Home = lazy(() => import('./pages/Home').then(module => ({ default: module.Home })));
const ChapterView = lazy(() => import('./pages/ChapterView').then(module => ({ default: module.ChapterView })));
const CorrectionDashboard = lazy(() => import('./pages/CorrectionDashboard').then(module => ({ default: module.CorrectionDashboard })));
const Library = lazy(() => import('./pages/Library'));
const NovelDetail = lazy(() => import('./pages/NovelDetail'));
const CharacterGraph = lazy(() => import('./pages/CharacterGraph'));
const NotFound = lazy(() => import('./pages/NotFound').then(module => ({ default: module.NotFound })));

function App() {
  return (
    <MainLayout>
      <Suspense fallback={
        <div className="flex items-center justify-center min-h-[50vh]">
          <LoadingSpinner size="lg" />
        </div>
      }>
        <Routes>
          {/* Home Route - Redirects to Library or acts as Landing */}
          <Route path="/" element={<Home />} />

          {/* Library Routes */}
          <Route path="/library" element={<Library />} />
          <Route path="/library/:id" element={<NovelDetail />} />

          {/* Chapter View Routes - Support both legacy and novel-specific patterns */}
          <Route path="/chapter/:id" element={<ChapterView />} />
          <Route path="/library/:novelId/chapter/:id" element={<ChapterView />} />

          {/* Character relationship graph */}
          <Route path="/characters" element={<CharacterGraph />} />
          <Route path="/library/:novelId/characters" element={<CharacterGraph />} />

          {/* Corrections Dashboard Route */}
          <Route path="/corrections" element={<CorrectionDashboard />} />

          {/* 404 Not Found Route - Catch All */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </MainLayout>
  );
}

export default App;
