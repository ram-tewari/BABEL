import { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout';
import { LoadingSpinner } from './components/ui';
import './index.css';

// Lazy load pages for improved performance (Task 18.1)
const Home = lazy(() => import('./pages/Home').then(module => ({ default: module.Home })));
const ChapterView = lazy(() => import('./pages/ChapterView').then(module => ({ default: module.ChapterView })));
const CorrectionDashboard = lazy(() => import('./pages/CorrectionDashboard').then(module => ({ default: module.CorrectionDashboard })));
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
          {/* Home Route - Chapter List */}
          <Route path="/" element={<Home />} />

          {/* Chapter View Route - Individual Chapter */}
          <Route path="/chapter/:id" element={<ChapterView />} />

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
