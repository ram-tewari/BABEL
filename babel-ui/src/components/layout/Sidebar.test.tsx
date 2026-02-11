/**
 * Sidebar Component Tests
 * 
 * Tests for the Sidebar component including:
 * - Rendering chapter list
 * - Highlighting current chapter
 * - Loading states
 * - Error states
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Sidebar } from './Sidebar';
import * as useChapterListHook from '@/hooks/useChapterList';

// Create a test query client
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

// Wrapper component with all required providers
const TestWrapper = ({ children, route = '/' }: { children: React.ReactNode; route?: string }) => {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/chapter/:id" element={children} />
          <Route path="*" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('Sidebar', () => {
  it('renders the sidebar with title', () => {
    // Mock the hook to return loading state
    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <Sidebar />
      </TestWrapper>
    );

    expect(screen.getByText('Table of Contents')).toBeInTheDocument();
  });

  it('displays loading state', () => {
    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <Sidebar />
      </TestWrapper>
    );

    expect(screen.getByText('Loading chapters...')).toBeInTheDocument();
  });

  it('displays error state with retry button', () => {
    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error('Failed to fetch'),
    } as any);

    render(
      <TestWrapper>
        <Sidebar />
      </TestWrapper>
    );

    expect(screen.getByText('Failed to load chapters')).toBeInTheDocument();
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('renders chapter list when data is available', () => {
    const mockChapterList = {
      chapters: [
        {
          id: 1,
          chapter_index: 1,
          filename: '001_chapter_1.json',
          title: 'Chapter 1: The Beginning',
          status: 'completed',
          phase: 'render',
        },
        {
          id: 2,
          chapter_index: 2,
          filename: '002_chapter_2.json',
          title: 'Chapter 2: The Journey',
          status: 'completed',
          phase: 'render',
        },
      ],
      total: 2,
      novel_id: 'default',
    };

    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: mockChapterList,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <Sidebar />
      </TestWrapper>
    );

    expect(screen.getByText('Chapter 1: The Beginning')).toBeInTheDocument();
    expect(screen.getByText('Chapter 2: The Journey')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
    expect(screen.getByText('#2')).toBeInTheDocument();
  });

  it('highlights the current chapter', () => {
    const mockChapterList = {
      chapters: [
        {
          id: 1,
          chapter_index: 1,
          filename: '001_chapter_1.json',
          title: 'Chapter 1: The Beginning',
          status: 'completed',
          phase: 'render',
        },
        {
          id: 2,
          chapter_index: 2,
          filename: '002_chapter_2.json',
          title: 'Chapter 2: The Journey',
          status: 'completed',
          phase: 'render',
        },
      ],
      total: 2,
      novel_id: 'default',
    };

    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: mockChapterList,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper route="/chapter/1">
        <Sidebar />
      </TestWrapper>
    );

    // Find the link for chapter 1
    const chapter1Link = screen.getByText('Chapter 1: The Beginning').closest('a');
    expect(chapter1Link).toHaveClass('current');

    // Find the link for chapter 2
    const chapter2Link = screen.getByText('Chapter 2: The Journey').closest('a');
    expect(chapter2Link).not.toHaveClass('current');
  });

  it('displays empty state when no chapters are available', () => {
    const mockChapterList = {
      chapters: [],
      total: 0,
      novel_id: 'default',
    };

    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: mockChapterList,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <Sidebar />
      </TestWrapper>
    );

    expect(screen.getByText('No chapters available')).toBeInTheDocument();
  });

  it('renders correct links for chapters', () => {
    const mockChapterList = {
      chapters: [
        {
          id: 1,
          chapter_index: 1,
          filename: '001_chapter_1.json',
          title: 'Chapter 1: The Beginning',
          status: 'completed',
          phase: 'render',
        },
      ],
      total: 1,
      novel_id: 'default',
    };

    vi.spyOn(useChapterListHook, 'useChapterList').mockReturnValue({
      data: mockChapterList,
      isLoading: false,
      error: null,
    } as any);

    render(
      <TestWrapper>
        <Sidebar />
      </TestWrapper>
    );

    const link = screen.getByText('Chapter 1: The Beginning').closest('a');
    expect(link).toHaveAttribute('href', '/chapter/1');
  });
});
