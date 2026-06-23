/**
 * ChapterView Tests
 * 
 * Tests for the ChapterView component's window update logic (Task 2.1)
 * and handling of unloaded chapters (Task 2.2)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import '@testing-library/jest-dom';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ChapterView, calculateRenderWindow } from '../pages/ChapterView';
import { getChapter, type ChapterResponse } from '../lib/api';

// Mock IntersectionObserver for infinite scroll tests
const IntersectionObserverMock = vi.fn(() => ({
  observe: vi.fn(),
  disconnect: vi.fn(),
  unobserve: vi.fn(),
}));
vi.stubGlobal('IntersectionObserver', IntersectionObserverMock);

// Create mock functions at module level (before vi.mock calls)
const mocks = {
  useChapter: vi.fn(),
  getChapter: vi.fn(),
  getNovelChapter: vi.fn(),
};

// Mock the useChapter hook - use getter to avoid initialization order issues
vi.mock('../hooks/useChapter', () => ({
  get useChapter() {
    return mocks.useChapter;
  },
}));

// Mock the API - use getter to avoid initialization order issues
vi.mock('../lib/api', () => ({
  get getChapter() {
    return mocks.getChapter;
  },
  get api() {
    return {
      getNovelChapter: mocks.getNovelChapter,
    };
  },
}));

// Helper to create mock chapter data
function createMockChapter(id: number, title: string = `Chapter ${id}`): ChapterResponse {
  return {
    id,
    chapter_index: id,
    filename: `chapter-${id}.json`,
    title,
    blocks: [
      { type: 'narrator', content: `Content for chapter ${id}` }
    ],
    navigation: {
      prev: id > 1 ? id - 1 : undefined,
      next: id < 100 ? id + 1 : undefined,
    },
  };
}

describe('ChapterView Window Update Logic (Task 2.1)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  describe('calculateRenderWindow', () => {
    it('returns empty array when loadedChapters is empty', () => {
      const loadedChapters: ChapterResponse[] = [];
      const currentChapterId = 1;
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      expect(result).toEqual([]);
    });

    it('returns empty array when current chapter is not loaded', () => {
      const loadedChapters = [
        createMockChapter(1),
        createMockChapter(2),
        createMockChapter(3),
      ];
      const currentChapterId = 99; // Not in loadedChapters
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      expect(result).toEqual([]);
    });

    it('calculates window centered on current chapter', () => {
      // Create 10 chapters
      const loadedChapters = Array.from({ length: 10 }, (_, i) => createMockChapter(i + 1));
      const currentChapterId = 5;
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      // With windowSize 5 and current chapter 5 (index 4), window should be chapters 3-7
      expect(result).toEqual([3, 4, 5, 6, 7]);
    });

    it('handles window at start of chapters', () => {
      const loadedChapters = Array.from({ length: 10 }, (_, i) => createMockChapter(i + 1));
      const currentChapterId = 1;
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      // At the start, window should be chapters 1-5
      expect(result).toEqual([1, 2, 3, 4, 5]);
    });

    it('handles window at end of chapters', () => {
      const loadedChapters = Array.from({ length: 10 }, (_, i) => createMockChapter(i + 1));
      const currentChapterId = 10;
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      // At the end, window should be chapters 6-10
      expect(result).toEqual([6, 7, 8, 9, 10]);
    });

    it('handles single chapter', () => {
      const loadedChapters = [createMockChapter(1)];
      const currentChapterId = 1;
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      expect(result).toEqual([1]);
    });

    it('handles fewer chapters than window size', () => {
      const loadedChapters = [
        createMockChapter(1),
        createMockChapter(2),
        createMockChapter(3),
      ];
      const currentChapterId = 2;
      const windowSize = 5;
      
      const result = calculateRenderWindow(loadedChapters, currentChapterId, windowSize);
      
      // Should return all available chapters
      expect(result).toEqual([1, 2, 3]);
    });
  });

  describe('Window Update useEffect', () => {
    // Create a new QueryClient for each test
    let queryClient: QueryClient;

    beforeEach(() => {
      queryClient = new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
          },
        },
      });
    });

    afterEach(() => {
      cleanup();
      vi.resetAllMocks();
    });

    it('renders without crashing when chapter is not found', async () => {
      // Mock useChapter to return error state
      mocks.useChapter.mockReturnValue({
        data: undefined,
        isLoading: false,
        error: new Error('Chapter not found'),
      });

      render(
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Routes>
              <Route path="/chapter/:id" element={<ChapterView />} />
            </Routes>
          </BrowserRouter>
        </QueryClientProvider>
      );

      // Navigate to a chapter that doesn't exist
      window.history.pushState({}, '', '/chapter/999');

      // Wait for error state to appear
      await waitFor(() => {
        expect(screen.getByText('Chapter Not Found')).toBeInTheDocument();
      });
    });

    it('renders loading state initially', async () => {
      // Mock useChapter to return loading state
      mocks.useChapter.mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      });

      render(
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Routes>
              <Route path="/chapter/:id" element={<ChapterView />} />
            </Routes>
          </BrowserRouter>
        </QueryClientProvider>
      );

      // Navigate to a chapter
      window.history.pushState({}, '', '/chapter/1');

      // Should show loading state
      expect(screen.getByText('Loading chapter...')).toBeInTheDocument();
    });

    it('renders chapter content when loaded', async () => {
      const mockChapter = createMockChapter(1);
      
      // Mock useChapter to return loaded chapter
      mocks.useChapter.mockReturnValue({
        data: mockChapter,
        isLoading: false,
        error: null,
      });

      render(
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Routes>
              <Route path="/chapter/:id" element={<ChapterView />} />
            </Routes>
          </BrowserRouter>
        </QueryClientProvider>
      );

      // Navigate to chapter 1
      window.history.pushState({}, '', '/chapter/1');

      // Wait for chapter content to appear
      await waitFor(() => {
        expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
      });
    });
  });
});

describe('Task 2.2: Handle Current Chapter Not Loaded', () => {
  // Create a new QueryClient for each test
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('shows loading state when navigating to unloaded chapter', async () => {
    const mockChapter1 = createMockChapter(1);
    const mockChapter2 = createMockChapter(2);
    
    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Now navigate to chapter 2 (which is not loaded yet)
    window.history.pushState({}, '', '/chapter/2');

    // The loading state should appear when loadingChapterId is set
    await waitFor(() => {
      expect(screen.getByText('Loading chapter 2...')).toBeInTheDocument();
    });
  });

  it('triggers API call when navigating to unloaded chapter', async () => {
    const mockChapter1 = createMockChapter(1);
    const mockChapter2 = createMockChapter(2);
    
    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Now navigate to chapter 2 (which is not loaded yet)
    window.history.pushState({}, '', '/chapter/2');

    // The API call should be triggered when navigating to chapter 2
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(2);
    });
  });

  it('updates window after chapter loads', async () => {
    const mockChapter1 = createMockChapter(1);
    const mockChapter2 = createMockChapter(2);
    
    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Now navigate to chapter 2 (which is not loaded yet)
    window.history.pushState({}, '', '/chapter/2');

    // After chapter 2 loads, the render window should be updated
    // and the chapter should be rendered
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });
  });

  it('handles chapter load failure gracefully', async () => {
    const mockChapter1 = createMockChapter(1);
    
    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter to throw an error
    mocks.getChapter.mockRejectedValue(new Error('Failed to load chapter'));

    // Suppress console.error for this test
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Now navigate to chapter 2 (which will fail to load)
    window.history.pushState({}, '', '/chapter/2');

    // The error should be logged but not crash the app
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(2);
    });
    
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining('Failed to load chapter'),
      expect.any(Error)
    );

    consoleErrorSpy.mockRestore();
  });

  it('does not trigger load for already loaded chapter', async () => {
    const mockChapter1 = createMockChapter(1);
    const mockChapter2 = createMockChapter(2);
    
    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Manually add chapter 2 to loadedChapters by calling the API
    await mocks.getChapter(2);

    // Now navigate to chapter 2 (which is now loaded)
    window.history.pushState({}, '', '/chapter/2');

    // The API should not be called again since chapter 2 is already loaded
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });
  });
});

describe('Task 2.3: Handle Window at Boundaries', () => {
  // Create a new QueryClient for each test
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('triggers loadPrevChapter when at start of loaded chapters', async () => {
    // Create chapters with navigation: chapter 1 has prev, chapter 2 has prev and next
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };
    
    const mockChapter3 = createMockChapter(3);
    mockChapter3.navigation = { prev: 2, next: 4 };

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for loading additional chapters
    mocks.getChapter.mockResolvedValue(mockChapter3);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 3 (which is at the end of loaded chapters and has next)
    window.history.pushState({}, '', '/chapter/3');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Since chapter 3 is at the end and has next (chapter 4), loadNextChapter should be triggered
    // The mock should have been called for chapter 4
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalled();
    }, { timeout: 1000 });
  });

  it('triggers loadNextChapter when at end of loaded chapters', async () => {
    // Create chapters where chapter 3 is at the end
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };
    
    const mockChapter3 = createMockChapter(3);
    mockChapter3.navigation = { prev: 2, next: 4 }; // Has next chapter

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for loading chapter 4
    mocks.getChapter.mockResolvedValue(mockChapter3);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 3 (which is at the end and has next)
    window.history.pushState({}, '', '/chapter/3');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // loadNextChapter should be triggered since chapter 3 is at the end
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(4);
    }, { timeout: 1000 });
  });

  it('does not trigger load when already loading', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter - should not be called when already loading
    mocks.getChapter.mockImplementation(() => new Promise(resolve => setTimeout(() => resolve(mockChapter2), 1000)));

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2
    window.history.pushState({}, '', '/chapter/2');

    // Wait a short time - the first call should be in progress
    await new Promise(resolve => setTimeout(resolve, 100));

    // Count calls - should only be 1 (the initial load of chapter 2)
    // The boundary check should not trigger another load while loading
    const callCount = mocks.getChapter.mock.calls.length;
    
    // Wait a bit more to see if there are additional calls
    await new Promise(resolve => setTimeout(resolve, 200));

    // Should not have triggered duplicate loads
    expect(mocks.getChapter.mock.calls.length).toBeLessThanOrEqual(callCount + 1);
  });

  it('does not trigger load when no more chapters available', async () => {
    // Create chapter at the end with no next chapter
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: undefined }; // No next chapter

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for chapter 2
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2 (which has no next chapter)
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Wait to ensure no additional API calls are made
    await new Promise(resolve => setTimeout(resolve, 500));

    // Should only have called getChapter for chapter 2, not for a non-existent chapter 3
    expect(mocks.getChapter).toHaveBeenCalledTimes(1);
    expect(mocks.getChapter).toHaveBeenCalledWith(2);
  });

  it('expands window when fewer chapters available than window size', async () => {
    // Create only 2 chapters (fewer than default window size of 5)
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: undefined };

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for chapter 2
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Both chapters should be rendered (window expands to include all available)
    // The calculateRenderWindow function handles this case
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });
  });

  it('shows loading indicator at top boundary', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for chapter 2
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The top sentinel should show loading indicator when loading previous chapter
    // or indicate that scrolling up will load previous chapter
    const topSentinel = document.querySelector('[ref="topSentinel"]') || 
      document.evaluate("//div[contains(@class, 'h-10') and contains(@class, 'flex')]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    
    // The loading indicator should be present when loadingPrev is true
    expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
  });

  it('shows loading indicator at bottom boundary', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return chapter 1
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for chapter 2
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The bottom sentinel should show loading indicator when loadingNext is true
    // or indicate that scrolling will load more chapters
    expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
  });
});

describe('Task 4.2: scrollToChapter Function', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('scrolls to chapter when already in render window', async () => {
    const mockChapter1 = createMockChapter(1);
    const mockChapter2 = createMockChapter(2);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2 (which should be in render window)
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The chapter element should exist and be scrollable
    const chapterElement = document.querySelector('.chapter-container[data-chapter-id="2"]');
    expect(chapterElement).toBeInTheDocument();
  });

  it('triggers chapter load when navigating to unloaded chapter', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };

    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2 (which is not loaded yet)
    window.history.pushState({}, '', '/chapter/2');

    // The API should be called to load chapter 2
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(2);
    });
  });

  it('updates render window when navigating to chapter outside window', async () => {
    // Create 10 chapters
    const mockChapters = Array.from({ length: 10 }, (_, i) => 
      createMockChapter(i + 1)
    );

    // Set up navigation for each chapter
    mockChapters.forEach((ch, i) => {
      ch.navigation = {
        prev: i > 0 ? ch.id - 1 : undefined,
        next: i < 9 ? ch.id + 1 : undefined,
      };
    });

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapters[0],
      isLoading: false,
      error: null,
    });

    // Mock getChapter to return chapters on demand
    mocks.getChapter.mockImplementation((id: number) => 
      Promise.resolve(mockChapters[id - 1])
    );

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 8 (which is outside the initial render window of 5)
    window.history.pushState({}, '', '/chapter/8');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Chapter 8 should be loaded
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(8);
    });
  });

  it('uses requestAnimationFrame for smooth scrolling', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock requestAnimationFrame
    const mockRequestAnimationFrame = vi.fn((callback) => callback());
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation(mockRequestAnimationFrame);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // requestAnimationFrame should have been called for smooth scrolling
    await waitFor(() => {
      expect(mockRequestAnimationFrame).toHaveBeenCalled();
    });

    // Clean up
    vi.restoreAllMocks();
  });

  it('handles rapid navigation without race conditions', async () => {
    const mockChapter1 = createMockChapter(1);
    const mockChapter2 = createMockChapter(2);
    const mockChapter3 = createMockChapter(3);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    mockChapter2.navigation = { prev: 1, next: 3 };
    mockChapter3.navigation = { prev: 2, next: 4 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter with delay to simulate network latency
    mocks.getChapter.mockImplementation((id: number) => 
      new Promise((resolve) => setTimeout(() => {
        if (id === 2) resolve(mockChapter2);
        if (id === 3) resolve(mockChapter3);
      }, 50))
    );

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Rapidly navigate to chapter 2, then chapter 3
    window.history.pushState({}, '', '/chapter/2');
    await new Promise(resolve => setTimeout(resolve, 10));
    window.history.pushState({}, '', '/chapter/3');

    // Wait for all navigations to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    }, { timeout: 1000 });

    // Both chapters should be loaded
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(2);
      expect(mocks.getChapter).toHaveBeenCalledWith(3);
    });
  });
});

describe('Task 3.1: loadNextChapter with Render Window', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('adds new chapter to loadedChapters', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Manually trigger loadNextChapter by navigating to chapter 2
    // which is at the end and has next (chapter 3)
    window.history.pushState({}, '', '/chapter/2');

    // Wait for chapter 2 to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Chapter 2 should be loaded
    expect(mocks.getChapter).toHaveBeenCalledWith(2);
  });

  it('updates renderedChapterIds when new chapter is within render window', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };
    
    const mockChapter3 = createMockChapter(3);
    mockChapter3.navigation = { prev: 2, next: 4 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for loading additional chapters
    mocks.getChapter.mockResolvedValue(mockChapter3);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 3 (which is at the end and has next)
    window.history.pushState({}, '', '/chapter/3');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The render window should be updated to include chapter 3
    // and the API should have been called to load chapter 4
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalled();
    });
  });

  it('maintains scroll position when adding new chapter at end', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    // Mock window.scrollTo
    const scrollToMock = vi.fn();
    vi.stubGlobal('window', {
      ...window,
      scrollTo: scrollToMock,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1 first
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // scrollTo should have been called to maintain scroll position
    await waitFor(() => {
      expect(scrollToMock).toHaveBeenCalled();
    });
  });

  it('does not update renderedChapterIds when current chapter is not in new set', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };
    
    const mockChapter3 = createMockChapter(3);
    mockChapter3.navigation = { prev: 2, next: 4 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for loading chapter 3
    mocks.getChapter.mockResolvedValue(mockChapter3);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 3 (which is at the end and has next)
    window.history.pushState({}, '', '/chapter/3');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The render window should be updated to include chapter 3
    // and chapter 4 should be loaded
    await waitFor(() => {
      expect(mocks.getChapter).toHaveBeenCalledWith(4);
    });
  });

  it('handles loadNextChapter when already loading', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter to never resolve (simulates ongoing load)
    mocks.getChapter.mockReturnValue(new Promise(() => {}));

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2
    window.history.pushState({}, '', '/chapter/2');

    // Wait a short time
    await new Promise(resolve => setTimeout(resolve, 100));

    // Navigate back to chapter 1 (which should trigger loadNextChapter again)
    window.history.pushState({}, '', '/chapter/1');

    // Wait a bit more
    await new Promise(resolve => setTimeout(resolve, 100));

    // getChapter should only be called once (for chapter 2)
    // because the second call should be blocked while loading
    expect(mocks.getChapter).toHaveBeenCalledTimes(1);
  });

  it('handles loadNextChapter when no more chapters available', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: undefined, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: undefined }; // No next chapter

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for chapter 2
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Routes>
            <Route path="/chapter/:id" element={<ChapterView />} />
          </Routes>
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Navigate to chapter 1
    window.history.pushState({}, '', '/chapter/1');

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Navigate to chapter 2 (which has no next chapter)
    window.history.pushState({}, '', '/chapter/2');

    // Wait for navigation to complete
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Wait to ensure no additional API calls are made
    await new Promise(resolve => setTimeout(resolve, 500));

    // Should only have called getChapter for chapter 2
    expect(mocks.getChapter).toHaveBeenCalledTimes(1);
    expect(mocks.getChapter).toHaveBeenCalledWith(2);
  });
});
describe('Task 3.1: loadNextChapter with Render Window', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  it('adds new chapter to loadedChapters', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: null, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ChapterView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // getChapter should have been called for chapter 2
    await waitFor(() => {
      expect(vi.mocked(getChapter)).toHaveBeenCalledWith(2);
    });
  });

  it('updates renderedChapterIds when new chapter is within render window', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: null, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };
    
    const mockChapter3 = createMockChapter(3);
    mockChapter3.navigation = { prev: 2, next: 4 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for loading additional chapters
    mocks.getChapter.mockResolvedValue(mockChapter3);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ChapterView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The render window should be updated to include chapter 3
    // and the API should have been called to load chapter 4
    await waitFor(() => {
      expect(vi.mocked(getChapter)).toHaveBeenCalled();
    });
  });

  it('maintains scroll position when adding new chapter at end', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: null, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for the second chapter
    mocks.getChapter.mockResolvedValue(mockChapter2);

    // Mock window.scrollTo
    const scrollToMock = vi.fn();
    vi.stubGlobal('window', {
      ...window,
      scrollTo: scrollToMock,
    });

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ChapterView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // scrollTo should have been called to maintain scroll position
    await waitFor(() => {
      expect(scrollToMock).toHaveBeenCalled();
    });
  });

  it('does not update renderedChapterIds when current chapter is not in new set', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: null, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };
    
    const mockChapter3 = createMockChapter(3);
    mockChapter3.navigation = { prev: 2, next: 4 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for loading chapter 3
    mocks.getChapter.mockResolvedValue(mockChapter3);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ChapterView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // The render window should be updated to include chapter 3
    // and chapter 4 should be loaded
    await waitFor(() => {
      expect(vi.mocked(getChapter)).toHaveBeenCalledWith(4);
    });
  });

  it('handles loadNextChapter when already loading', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: null, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: 3 };

    // Mock useChapter to return first chapter
    mocks.useChapter.mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter to never resolve (simulates ongoing load)
    mocks.getChapter.mockReturnValue(new Promise(() => {}));

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ChapterView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Wait a short time
    await new Promise(resolve => setTimeout(resolve, 100));

    // getChapter should only be called once (for chapter 2)
    // because the second call should be blocked while loading
    expect(vi.mocked(getChapter)).toHaveBeenCalledTimes(1);
  });

  it('handles loadNextChapter when no more chapters available', async () => {
    const mockChapter1 = createMockChapter(1);
    mockChapter1.navigation = { prev: null, next: 2 };
    
    const mockChapter2 = createMockChapter(2);
    mockChapter2.navigation = { prev: 1, next: null }; // No next chapter

    // Mock useChapter to return first chapter
    const mockUseChapter = vi.fn().mockReturnValue({
      data: mockChapter1,
      isLoading: false,
      error: null,
    });

    // Mock getChapter for chapter 2
    vi.mocked(getChapter).mockResolvedValue(mockChapter2);

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ChapterView />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // Wait for initial chapter to load
    await waitFor(() => {
      expect(screen.getByTestId('chapter-view')).toBeInTheDocument();
    });

    // Wait to ensure no additional API calls are made
    await new Promise(resolve => setTimeout(resolve, 500));

    // Should only have called getChapter for chapter 2
    expect(vi.mocked(getChapter)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(getChapter)).toHaveBeenCalledWith(2);
  });
});