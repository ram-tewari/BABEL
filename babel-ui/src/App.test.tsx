/**
 * App Component Tests
 * 
 * Tests for React Router configuration (Task 4.1)
 * Updated to work with QueryClientProvider and mocked API
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from './App';

// Mock the API module
vi.mock('@/lib/api', () => ({
  api: {
    getChapter: vi.fn().mockResolvedValue({
      id: 1,
      chapter_index: 1,
      title: 'Chapter 1: Test Chapter',
      blocks: [],
      metadata: {},
      navigation: {},
    }),
    getChapterList: vi.fn().mockResolvedValue({
      chapters: [],
      total: 0,
      novel_id: 'default',
    }),
    healthCheck: vi.fn().mockResolvedValue({ status: 'ok' }),
  },
}));

// Mock the useChapterList hook for Sidebar
vi.mock('@/hooks/useChapterList', () => ({
  useChapterList: () => ({
    data: { chapters: [], total: 0, novel_id: 'default' },
    isLoading: false,
    error: null,
  }),
}));

function createTestWrapper(route: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('App - React Router Configuration', () => {
  it('renders application shell on root route', () => {
    render(createTestWrapper('/'));

    // Header should be present (use getAllByText since it appears in multiple places)
    const matches = screen.getAllByText(/SYSTEM: BABEL/i);
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('renders ChapterView on /chapter/:id route', () => {
    render(createTestWrapper('/chapter/1'));

    // Should render within the MainLayout
    const mainContent = document.querySelector('main');
    expect(mainContent).toBeInTheDocument();
  });

  it('renders NotFound page on invalid route', () => {
    render(createTestWrapper('/invalid-route'));

    // Check for NotFound page content
    expect(screen.getByRole('heading', { name: /404/i })).toBeInTheDocument();
    expect(screen.getByText(/Page Not Found/i)).toBeInTheDocument();
  });

  it('renders sidebar with Table of Contents', () => {
    render(createTestWrapper('/'));

    expect(screen.getByText('Table of Contents')).toBeInTheDocument();
  });
});
