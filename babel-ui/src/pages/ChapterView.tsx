/**
 * ChapterView Page Component
 * 
 * Main chapter reading page that fetches and displays chapter content
 * using TanStack Query and renders each block through ScriptBlock.
 * 
 * Supports bi-directional infinite scroll:
 * - Scroll DOWN to auto-load the next chapter
 * - Scroll UP to auto-load the previous chapter
 * 
 * Task 12.1-12.4: Implement ChapterView page
 * Validates: Requirements 4.1, 4.4, 4.5, 5.1, 5.2, 5.6, 5.7
 */

import { useParams, Link } from 'react-router-dom';
import { useEffect, useState, useRef, useCallback } from 'react';
import { useChapter } from '@/hooks/useChapter';
import { ScriptBlock } from '@/components/reader';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { api, getChapter, type ChapterResponse } from '@/lib/api';
import { formatChapterTitle } from '@/lib/utils';
import { useReadingProgress } from '@/stores/readingProgressStore';
import { useGlossary } from '@/stores/glossaryStore';

// Render window configuration
const RENDER_WINDOW_SIZE = 5;

// Export for testing
export function calculateRenderWindow(
  loadedChapters: ChapterResponse[],
  currentChapterId: number,
  windowSize: number = RENDER_WINDOW_SIZE
): number[] {
  if (loadedChapters.length === 0) return [];
  
  const currentIndex = loadedChapters.findIndex(ch => ch.id === currentChapterId);
  if (currentIndex === -1) {
    // Current chapter not loaded yet, return empty window
    return [];
  }
  
  const halfWindow = Math.floor(windowSize / 2);
  const startIndex = Math.max(0, currentIndex - halfWindow);
  const endIndex = Math.min(loadedChapters.length, startIndex + windowSize);
  
  // Adjust start if we're at the end
  const actualStart = Math.max(0, endIndex - windowSize);
  
  return loadedChapters
    .slice(actualStart, endIndex)
    .map(ch => ch.id);
}

export function ChapterView() {
  const { id, novelId: novelIdParam } = useParams<{ id: string; novelId?: string }>();
  const loadGlossary = useGlossary((s) => s.loadGlossary);
  // Load glossary once per novel so speaker tooltips have data.
  useEffect(() => {
    loadGlossary(novelIdParam ? Number(novelIdParam) : undefined);
  }, [novelIdParam, loadGlossary]);
  const [loadedChapters, setLoadedChapters] = useState<ChapterResponse[]>([]);
  const [renderedChapterIds, setRenderedChapterIds] = useState<number[]>([]);
  const [loadingNext, setLoadingNext] = useState(false);
  const [loadingPrev, setLoadingPrev] = useState(false);
  const [loadingChapterId, setLoadingChapterId] = useState<number | null>(null); // Task 2.2: Track which chapter is being loaded
  const bottomSentinel = useRef<HTMLDivElement>(null);
  const topSentinel = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const previousIdRef = useRef<number | null>(null);
  const isInitialLoadRef = useRef(true);
  const windowUpdateTimeoutRef = useRef<number | null>(null);
  // Task 4.1: Track scroll position for restoration
  const scrollPositionRef = useRef<number>(0);
  const lastRenderedIdsRef = useRef<number[]>([]);
  // Task 4.3: Track pending target for rapid navigation
  const pendingTargetIdRef = useRef<number | null>(null);
  // Task 4.3: Track in-flight chapter loads to cancel them
  const inFlightLoadRef = useRef<{ chapterId: number; aborted: boolean } | null>(null);
  // Track if navigation was triggered by user click (vs scroll)
  const isUserNavigationRef = useRef(false);

  const { setCurrentChapter, currentNovelId, setCurrentNovel } = useReadingProgress();
  
  // Determine novel ID: from URL params, store, or default
  const novelId = novelIdParam || currentNovelId || 'default';

  // Debounced window update function
  const debouncedWindowUpdate = useCallback((targetId: number, chapters: ChapterResponse[]) => {
    // Clear any pending updates
    if (windowUpdateTimeoutRef.current) {
      clearTimeout(windowUpdateTimeoutRef.current);
    }

    // Schedule new update
    windowUpdateTimeoutRef.current = setTimeout(() => {
      const newWindow = calculateRenderWindow(chapters, targetId, RENDER_WINDOW_SIZE);
      setRenderedChapterIds(newWindow);
      windowUpdateTimeoutRef.current = null;
    }, 150); // 150ms debounce
  }, []);

  // Set current novel context if coming from library
  useEffect(() => {
    if (novelIdParam) {
      setCurrentNovel(novelIdParam);
    }
  }, [novelIdParam, setCurrentNovel]);

  // Cleanup debounce timeout on unmount
  useEffect(() => {
    return () => {
      if (windowUpdateTimeoutRef.current) {
        clearTimeout(windowUpdateTimeoutRef.current);
      }
      // Task 4.3: Mark any in-flight load as aborted
      if (inFlightLoadRef.current) {
        inFlightLoadRef.current.aborted = true;
      }
    };
  }, []);

  // Task 4.1: Save scroll position before window updates
  useEffect(() => {
    // Check if render window is about to change
    const hasChanged = JSON.stringify(lastRenderedIdsRef.current) !== JSON.stringify(renderedChapterIds);
    
    if (hasChanged && renderedChapterIds.length > 0) {
      // Save current scroll position before the window updates
      const scrollContainer = document.querySelector('main.overflow-y-auto') || document.scrollingElement;
      const currentScroll = scrollContainer && 'scrollTop' in scrollContainer 
        ? scrollContainer.scrollTop 
        : window.scrollY;
      
      scrollPositionRef.current = currentScroll;
      lastRenderedIdsRef.current = renderedChapterIds;
    }
  }, [renderedChapterIds]);

  // Task 4.1: Restore scroll position after window updates
  useEffect(() => {
    const targetId = id ? Number(id) : null;
    if (!targetId || renderedChapterIds.length === 0) return;

    // Check if the target chapter is in the current render window
    if (renderedChapterIds.includes(targetId)) {
      // Find the target element
      const targetElement = document.querySelector(`.chapter-container[data-chapter-id="${targetId}"]`);
      
      if (targetElement) {
        // Use requestAnimationFrame to ensure DOM is ready after render
        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            // Restore scroll position by scrolling to the target chapter
            // Use 'auto' behavior for instant restoration (no animation)
            targetElement.scrollIntoView({ behavior: 'auto', block: 'start' });
          });
        });
      }
    }
  }, [renderedChapterIds, id]);

  const initialId = id ? Number(id) : null;
  const { data: initialChapter, isLoading, error } = useChapter(initialId, novelId);

  // Task 2.2: Load a single chapter by ID (used when navigating to unloaded chapter)
  const loadChapterById = useCallback(async (chapterId: number) => {
    // Task 4.3: Check if there's already an in-flight load for this chapter
    if (inFlightLoadRef.current && inFlightLoadRef.current.chapterId === chapterId) {
      if (inFlightLoadRef.current.aborted) {
        // Reset the aborted flag and proceed
        inFlightLoadRef.current.aborted = false;
      } else {
        // Wait for the existing load to complete
        return inFlightLoadRef.current;
      }
    }

    // Task 4.3: Cancel any in-flight load for a different chapter
    if (inFlightLoadRef.current && inFlightLoadRef.current.chapterId !== chapterId) {
      inFlightLoadRef.current.aborted = true;
    }

    setLoadingChapterId(chapterId);
    // Task 4.3: Track this in-flight load
    inFlightLoadRef.current = { chapterId, aborted: false };
    
    try {
      const chapter = novelId === 'default'
        ? await getChapter(chapterId)
        : await api.getNovelChapter(parseInt(novelId), chapterId);
      
      // Check if this load was aborted before proceeding
      if (inFlightLoadRef.current?.aborted) {
        return null;
      }
      
      // Add to loaded chapters
      setLoadedChapters(prev => {
        // Check if chapter already exists
        if (prev.some(ch => ch.id === chapterId)) {
          return prev;
        }
        return [...prev, chapter];
      });
      
      inFlightLoadRef.current = null;
      return chapter;
    } catch (err) {
      inFlightLoadRef.current = null;
      console.error(`Failed to load chapter ${chapterId}`, err);
      throw err;
    } finally {
      setLoadingChapterId(null);
    }
  }, [novelId]);

  // Task 4.2: Updated scrollToChapter function
  // Scrolls to chapter within render window, handling loading if needed
  // Task 4.3: Handle rapid navigation by tracking pending target
  const scrollToChapter = useCallback((chapterId: number) => {
    // Mark this as user-initiated navigation
    isUserNavigationRef.current = true;
    
    // Task 4.3: Update pending target - this will be the final target
    pendingTargetIdRef.current = chapterId;
    
    // Helper function to wait for element and scroll
    const waitForElementAndScroll = (maxAttempts = 20, attemptDelay = 100) => {
      let attempts = 0;
      
      const tryScroll = () => {
        // Check if this is still the pending target
        if (pendingTargetIdRef.current !== chapterId) {
          return; // A newer navigation has superseded this one
        }
        
        const targetElement = document.querySelector(`.chapter-container[data-chapter-id="${chapterId}"]`);
        
        if (targetElement) {
          // Element found, scroll to it
          targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } else if (attempts < maxAttempts) {
          // Element not found yet, try again
          attempts++;
          setTimeout(tryScroll, attemptDelay);
        } else {
          console.warn(`Failed to find chapter ${chapterId} after ${maxAttempts} attempts`);
        }
      };
      
      // Start trying immediately
      requestAnimationFrame(() => {
        requestAnimationFrame(tryScroll);
      });
    };
    
    // Check if chapter is in the render window
    const isInRenderWindow = renderedChapterIds.includes(chapterId);
    
    if (!isInRenderWindow) {
      // Chapter needs to load first - check if it's loaded but not in window
      const chapterLoaded = loadedChapters.some(ch => ch.id === chapterId);
      
      if (!chapterLoaded) {
        // Chapter not loaded at all - trigger load and scroll after
        loadChapterById(chapterId).then((chapter) => {
          // Task 4.3: Only proceed if this is still the pending target
          if (pendingTargetIdRef.current !== chapterId) {
            return; // A newer navigation has superseded this one
          }
          
          if (!chapter) return; // Load was aborted
          
          // After loading, update window and wait for render
          const newWindow = calculateRenderWindow(loadedChapters, chapterId, RENDER_WINDOW_SIZE);
          setRenderedChapterIds(newWindow);
          
          // Wait for element to render and then scroll
          waitForElementAndScroll();
        });
        return;
      }
      
      // Chapter is loaded but not in render window - update window and wait for render
      const newWindow = calculateRenderWindow(loadedChapters, chapterId, RENDER_WINDOW_SIZE);
      setRenderedChapterIds(newWindow);
      
      // Wait for element to render and then scroll
      waitForElementAndScroll();
      return;
    }
    
    // Chapter is in render window - wait for it to be in DOM and scroll
    waitForElementAndScroll();
  }, [renderedChapterIds, loadedChapters, loadChapterById]);

  // Task 4.2: Scroll to chapter header when URL id changes
  useEffect(() => {
    const targetId = id ? Number(id) : null;
    if (!targetId) return;

    // Skip if this is the initial load (previousId is null)
    if (previousIdRef.current === null) {
      previousIdRef.current = targetId;
      return;
    }

    // Skip if id hasn't changed
    if (previousIdRef.current === targetId) {
      return;
    }

    // Check if we're jumping more than 5 chapters away
    const previousIndex = loadedChapters.findIndex(ch => ch.id === previousIdRef.current);
    const targetIndex = loadedChapters.findIndex(ch => ch.id === targetId);
    const isLargeJump = previousIndex !== -1 && targetIndex === -1; // Target not in loaded chapters
    
    // If jumping to a chapter not in cache, check if it's far away
    if (isLargeJump && loadedChapters.length > 0) {
      // Calculate distance based on chapter IDs (assuming sequential IDs)
      const distance = Math.abs(targetId - (previousIdRef.current || 0));
      
      if (distance > 5) {
        // PERFORMANCE: Clear cache immediately and load target chapter directly
        setLoadedChapters([]);
        setRenderedChapterIds([]);
        
        // Load the target chapter directly without waiting for initialChapter query
        loadChapterById(targetId).then((chapter) => {
          if (!chapter || pendingTargetIdRef.current !== targetId) return;
          
          // Initialize with the new chapter
          setLoadedChapters([chapter]);
          const initialWindow = calculateRenderWindow([chapter], chapter.id, RENDER_WINDOW_SIZE);
          setRenderedChapterIds(initialWindow);
          setCurrentChapter(novelId, chapter.id);
          
          // Scroll to the chapter
          requestAnimationFrame(() => {
            requestAnimationFrame(() => {
              const targetElement = document.querySelector(`.chapter-container[data-chapter-id="${targetId}"]`);
              if (targetElement) {
                targetElement.scrollIntoView({ behavior: 'auto', block: 'start' });
              }
            });
          });
        });
        
        previousIdRef.current = targetId;
        pendingTargetIdRef.current = targetId;
        return; // Exit early, we've handled the large jump
      }
    }

    previousIdRef.current = targetId;

    // Task 4.3: Set this as the pending target - only this target will be rendered
    pendingTargetIdRef.current = targetId;

    // Use the scrollToChapter function which handles:
    // 1. Checking if chapter is in render window
    // 2. Loading chapter if needed
    // 3. Smooth scrolling with requestAnimationFrame
    scrollToChapter(targetId);
  }, [id, loadedChapters, renderedChapterIds, scrollToChapter, loadChapterById, novelId, setCurrentChapter]);

  // Initialize with the first chapter when loaded or ID changes
  useEffect(() => {
    if (initialChapter && isInitialLoadRef.current) {
      // Only run this on the very first load
      setLoadedChapters([initialChapter]);
      
      // Calculate initial render window
      const initialWindow = calculateRenderWindow([initialChapter], initialChapter.id, RENDER_WINDOW_SIZE);
      setRenderedChapterIds(initialWindow);
      
      // Mark chapter as current/read
      setCurrentChapter(novelId, initialChapter.id);
      isInitialLoadRef.current = false;
    }
  }, [initialChapter, setCurrentChapter, novelId]);

  // Load NEXT chapter (scroll down)
  const loadNextChapter = useCallback(async () => {
    if (loadingNext || loadingPrev || !loadedChapters.length) return;

    const lastChapter = loadedChapters[loadedChapters.length - 1];
    const nextId = lastChapter.navigation?.next;

    if (!nextId) return;

    // Task 3.1: Save scroll position before loading
    const scrollContainer = document.querySelector('main.overflow-y-auto') || document.scrollingElement;
    const scrollYBefore = scrollContainer ? ('scrollTop' in scrollContainer ? scrollContainer.scrollTop : window.scrollY) : window.scrollY;

    setLoadingNext(true);
    try {
      const nextChapter = novelId === 'default'
        ? await getChapter(nextId)
        : await api.getNovelChapter(parseInt(novelId), nextId);

      const newLoadedChapters = [...loadedChapters, nextChapter];
      setLoadedChapters(newLoadedChapters);

      // Task 3.1: Update render window if current chapter is in the new set
      const currentId = id ? Number(id) : null;
      if (currentId) {
        const newWindow = calculateRenderWindow(newLoadedChapters, currentId, RENDER_WINDOW_SIZE);
        setRenderedChapterIds(newWindow);
      }

      // Update URL to reflect current chapter
      const newUrl = novelIdParam 
        ? `/library/${novelIdParam}/chapter/${nextId}`
        : `/chapter/${nextId}`;
      window.history.replaceState(null, '', newUrl);

      // Task 3.1: Restore scroll position after adding chapter at the end
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (scrollContainer && 'scrollTop' in scrollContainer) {
            scrollContainer.scrollTop = scrollYBefore;
          } else {
            window.scrollTo(0, scrollYBefore);
          }
        });
      });

      // Mark next chapter as current/read
        setCurrentChapter(novelId, nextId);
      } catch (err) {
        console.error("Failed to load next chapter", err);
      } finally {
        setLoadingNext(false);
      }
    }, [loadedChapters, loadingNext, loadingPrev, setCurrentChapter, novelId, novelIdParam, id]);

  // Load PREVIOUS chapter (scroll up)
  // Task 3.2: Update loadPrevChapter to work with render window
  const loadPrevChapter = useCallback(async () => {
    if (loadingPrev || loadingNext || !loadedChapters.length) return;

    const firstChapter = loadedChapters[0];
    const prevId = firstChapter.navigation?.prev;

    if (!prevId) return;

    // Task 3.2: Save scroll position before loading
    const scrollContainer = document.querySelector('main.overflow-y-auto') || document.scrollingElement;
    const scrollHeightBefore = scrollContainer?.scrollHeight || 0;
    const scrollTopBefore = scrollContainer && 'scrollTop' in scrollContainer ? scrollContainer.scrollTop : window.scrollY;

    setLoadingPrev(true);
    try {
      const prevChapter = novelId === 'default'
        ? await getChapter(prevId)
        : await api.getNovelChapter(parseInt(novelId), prevId);

      // Task 3.2: Add new chapter to loadedChapters (prepend)
      const newLoadedChapters = [prevChapter, ...loadedChapters];
      setLoadedChapters(newLoadedChapters);
      
      // Task 3.2: Update renderedChapterIds if needed
      const currentId = id ? Number(id) : null;
      if (currentId) {
        const newWindow = calculateRenderWindow(newLoadedChapters, currentId, RENDER_WINDOW_SIZE);
        setRenderedChapterIds(newWindow);
      }

      // Task 3.2: Restore scroll position after prepending
      // After React renders the prepended chapter, restore scroll position
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const scrollHeightAfter = scrollContainer?.scrollHeight || 0;
          const heightDiff = scrollHeightAfter - scrollHeightBefore;
          if (scrollContainer && 'scrollTop' in scrollContainer) {
            scrollContainer.scrollTop = scrollTopBefore + heightDiff;
          } else {
            window.scrollTo(0, scrollTopBefore + heightDiff);
          }
        });
      });
    } catch (err) {
      console.error("Failed to load previous chapter", err);
    } finally {
      setLoadingPrev(false);
    }
  }, [loadedChapters, loadingPrev, loadingNext, novelId, id]);

  // Task 2.1: Window update logic - update render window when current chapter changes
  // Task 2.3: Also detect boundaries and trigger infinite scroll
  // Task 4.3: Handle rapid navigation - only render final target chapter's window
  useEffect(() => {
    const targetId = id ? Number(id) : null;
    if (!targetId) return;

    // Skip if this is the initial load (previousId is null)
    if (previousIdRef.current === null) {
      previousIdRef.current = targetId;
      return;
    }

    // Skip if id hasn't changed
    if (previousIdRef.current === targetId) {
      return;
    }

    previousIdRef.current = targetId;

    // Task 4.3: Set this as the pending target - only this target will be rendered
    pendingTargetIdRef.current = targetId;

    // Check if target chapter is in the current render window
    const needsWindowUpdate = !renderedChapterIds.includes(targetId);

    if (needsWindowUpdate && loadedChapters.length > 0) {
      // Check if target chapter is loaded but not in render window
      const chapterLoaded = loadedChapters.some(ch => ch.id === targetId);
      
      if (chapterLoaded) {
        // Chapter is loaded, just update the window
        const newWindow = calculateRenderWindow(loadedChapters, targetId, RENDER_WINDOW_SIZE);
        setRenderedChapterIds(newWindow);
      } else {
        // Task 2.2: Chapter is not loaded - trigger load and show loading state
        loadChapterById(targetId).then((chapter) => {
          // Task 4.3: Only proceed if this is still the pending target
          if (pendingTargetIdRef.current !== targetId) {
            return; // A newer navigation has superseded this one
          }
          
          if (!chapter) return; // Load was aborted
          
          // After loading, update the render window
          const newWindow = calculateRenderWindow(loadedChapters, targetId, RENDER_WINDOW_SIZE);
          setRenderedChapterIds(newWindow);
        });
      }
    }

    // Task 2.3: Detect boundaries and trigger infinite scroll
    if (loadedChapters.length > 0) {
      const currentIndex = loadedChapters.findIndex(ch => ch.id === targetId);
      
      // At start of loaded chapters and has previous chapters to load
      if (currentIndex === 0 && loadedChapters[0]?.navigation?.prev && !loadingPrev && !loadingNext) {
        loadPrevChapter();
      }
      
      // At end of loaded chapters and has next chapters to load
      if (currentIndex === loadedChapters.length - 1 && loadedChapters[loadedChapters.length - 1]?.navigation?.next && !loadingNext && !loadingPrev) {
        loadNextChapter();
      }
    }
  }, [id, loadedChapters, renderedChapterIds, loadChapterById, loadPrevChapter, loadNextChapter, loadingPrev, loadingNext]);

  // Bottom Intersection Observer (load next)
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting) {
          loadNextChapter();
        }
      },
      { threshold: 0.5 }
    );

    if (bottomSentinel.current) {
      observer.observe(bottomSentinel.current);
    }

    return () => observer.disconnect();
  }, [loadNextChapter]);

  // Top Intersection Observer (load prev)
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        if (entries[0].isIntersecting) {
          loadPrevChapter();
        }
      },
      { threshold: 0.1 }
    );

    if (topSentinel.current) {
      observer.observe(topSentinel.current);
    }

    return () => observer.disconnect();
  }, [loadPrevChapter]);

  // Render Window Boundary Observers
  // Observe the first and last rendered chapters to detect when to expand the window
  useEffect(() => {
    if (renderedChapterIds.length === 0 || loadedChapters.length === 0) return;

    const observers: IntersectionObserver[] = [];

    // Observer for the first rendered chapter
    const firstRenderedId = renderedChapterIds[0];
    const firstElement = document.querySelector(`.chapter-container[data-chapter-id="${firstRenderedId}"]`);
    
    if (firstElement) {
      const firstObserver = new IntersectionObserver(
        entries => {
          if (entries[0].isIntersecting) {
            // First chapter is visible, check if we should expand window upward
            const firstLoadedId = loadedChapters[0]?.id;
            if (firstLoadedId && firstLoadedId !== firstRenderedId) {
              // There are loaded chapters before the first rendered one
              const currentId = id ? Number(id) : null;
              if (currentId) {
                debouncedWindowUpdate(currentId, loadedChapters);
              }
            }
          }
        },
        { threshold: 0.1, rootMargin: '200px 0px' }
      );
      firstObserver.observe(firstElement);
      observers.push(firstObserver);
    }

    // Observer for the last rendered chapter
    const lastRenderedId = renderedChapterIds[renderedChapterIds.length - 1];
    const lastElement = document.querySelector(`.chapter-container[data-chapter-id="${lastRenderedId}"]`);
    
    if (lastElement) {
      const lastObserver = new IntersectionObserver(
        entries => {
          if (entries[0].isIntersecting) {
            // Last chapter is visible, check if we should expand window downward
            const lastLoadedId = loadedChapters[loadedChapters.length - 1]?.id;
            if (lastLoadedId && lastLoadedId !== lastRenderedId) {
              // There are loaded chapters after the last rendered one
              const currentId = id ? Number(id) : null;
              if (currentId) {
                debouncedWindowUpdate(currentId, loadedChapters);
              }
            }
          }
        },
        { threshold: 0.1, rootMargin: '200px 0px' }
      );
      lastObserver.observe(lastElement);
      observers.push(lastObserver);
    }

    // Cleanup
    return () => {
      observers.forEach(observer => observer.disconnect());
    };
  }, [renderedChapterIds, loadedChapters, id, debouncedWindowUpdate]);

  // IntersectionObserver to track which chapter is currently visible during scroll
  // Updates URL and sidebar to reflect the chapter user is reading
  useEffect(() => {
    if (renderedChapterIds.length === 0) return;

    const observerCallback = (entries: IntersectionObserverEntry[]) => {
      // Find the most visible chapter (highest intersection ratio)
      let mostVisible: { id: number; ratio: number } | null = null;

      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const chapterId = Number(entry.target.getAttribute('data-chapter-id'));
          if (chapterId && entry.intersectionRatio > (mostVisible?.ratio || 0)) {
            mostVisible = { id: chapterId, ratio: entry.intersectionRatio };
          }
        }
      });

      // Update URL and reading progress if we found a visible chapter
      // Only update if this wasn't triggered by user navigation (clicking sidebar)
      if (mostVisible && !isUserNavigationRef.current) {
        const currentId = id ? Number(id) : null;
        if (currentId !== mostVisible.id) {
          // Update URL without scrolling
          const newUrl = novelIdParam 
            ? `/library/${novelIdParam}/chapter/${mostVisible.id}`
            : `/chapter/${mostVisible.id}`;
          window.history.replaceState(null, '', newUrl);
          
          // Update reading progress
          setCurrentChapter(novelId, mostVisible.id);
        }
      }

      // Reset user navigation flag after a short delay
      if (isUserNavigationRef.current) {
        setTimeout(() => {
          isUserNavigationRef.current = false;
        }, 1000);
      }
    };

    const observer = new IntersectionObserver(observerCallback, {
      threshold: [0, 0.25, 0.5, 0.75, 1],
      rootMargin: '-20% 0px -20% 0px' // Focus on middle 60% of viewport
    });

    // Observe all rendered chapter containers
    renderedChapterIds.forEach(chapterId => {
      const element = document.querySelector(`.chapter-container[data-chapter-id="${chapterId}"]`);
      if (element) {
        observer.observe(element);
      }
    });

    return () => observer.disconnect();
  }, [renderedChapterIds, id, novelIdParam, novelId, setCurrentChapter]);


  // Loading State (Initial)
  if (isLoading && loadedChapters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 animate-fadeIn">
        <LoadingSpinner size="lg" />
        <p className="text-[var(--text-dim)]">Loading chapter...</p>
      </div>
    );
  }

  // Task 2.2: Loading state when navigating to unloaded chapter
  const targetId = id ? Number(id) : null;
  const isNavigatingToChapter = targetId && loadingChapterId === targetId && loadedChapters.length > 0;
  if (isNavigatingToChapter) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 animate-fadeIn">
        <LoadingSpinner size="lg" />
        <p className="text-[var(--text-dim)]">Loading chapter {targetId}...</p>
      </div>
    );
  }

  // Error State
  if (error && loadedChapters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 animate-fadeIn">
        <div className="text-6xl mb-4">📖</div>
        <h2 className="text-2xl font-semibold text-[var(--text-main)]">
          Chapter Not Found
        </h2>
        <p className="text-[var(--text-dim)] text-center max-w-md">
          Could not load chapter {id}. It may not exist or the server may be unavailable.
        </p>
        <div className="flex gap-4 mt-4">
          <Link
            to="/"
            className="px-6 py-2 rounded-xl bg-[var(--accent)] text-[var(--bg-primary)] hover:bg-[var(--accent-hover)] transition-all"
          >
            ← Back to Home
          </Link>
          <button
            onClick={() => window.location.reload()}
            className="px-6 py-2 rounded-xl bg-[var(--bg-tertiary)] text-[var(--text-main)] border border-[var(--border)] hover:border-[var(--accent)] transition-all"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // No data state
  if (!loadedChapters.length) {
    return null;
  }

  // Filter chapters to render based on the render window
  const chaptersToRender = loadedChapters
    .filter(ch => renderedChapterIds.includes(ch.id))
    .sort((a, b) => {
      const aIndex = loadedChapters.findIndex(ch => ch.id === a.id);
      const bIndex = loadedChapters.findIndex(ch => ch.id === b.id);
      return aIndex - bIndex;
    });

  // Check if previous chapters are available
  const hasPrev = !!loadedChapters[0]?.navigation?.prev;
  const hasNext = !!loadedChapters[loadedChapters.length - 1]?.navigation?.next;

  return (
    <div ref={contentRef} className="max-w-[800px] mx-auto w-full animate-fadeIn" data-testid="chapter-view">

      {/* Top Sentinel — triggers loading previous chapter */}
      <div ref={topSentinel} className="h-10 flex items-center justify-center opacity-50">
        {loadingPrev ? (
          <LoadingSpinner size="md" />
        ) : hasPrev ? (
          <span className="text-[var(--text-dim)] animate-pulse text-sm">↑ Scroll up for previous chapter</span>
        ) : null}
      </div>

      {chaptersToRender.map((chapterData) => {
        // Calculate the original index in loadedChapters for proper chapter-divider rendering
        const originalIndex = loadedChapters.findIndex(ch => ch.id === chapterData.id);
        
        return (
        <div
          key={chapterData.id}
          id={`chapter-${originalIndex}`}
          data-chapter-id={chapterData.id}
          className="chapter-container mb-20 fade-in-up scroll-mt-24"
        >
          {/* Chapter Header divider for all chapters after the first */}
          {originalIndex > 0 && (
            <div id={`chapter-divider-${originalIndex}`} className="my-12 flex flex-col items-center gap-4 scroll-mt-24">
              <div className="flex items-center gap-4 w-full max-w-md">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-purple-500/40 to-transparent" />
                <div className="w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_8px_#a855f7]" />
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-purple-500/40 to-transparent" />
              </div>
              <h2 className="text-2xl font-cinzel text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-indigo-400 tracking-wide">
                {formatChapterTitle(chapterData.title)}
              </h2>
              <div className="flex items-center gap-4 w-full max-w-md">
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-purple-500/40 to-transparent" />
                <div className="w-2 h-2 rounded-full bg-purple-500 shadow-[0_0_8px_#a855f7]" />
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-purple-500/40 to-transparent" />
              </div>
            </div>
          )}

          {/* Chapter Content - renders each block, grouping consecutive narrators */}
          <div className="content flex flex-col gap-5" data-testid="chapter-content">
            {(() => {
              const elements: React.ReactNode[] = [];
              let i = 0;
              while (i < chapterData.blocks.length) {
                const block = chapterData.blocks[i];
                if (block.type === 'narrator') {
                  // Collect all consecutive narrator blocks
                  const narratorGroup: typeof chapterData.blocks = [];
                  const startIndex = i;
                  while (i < chapterData.blocks.length && chapterData.blocks[i].type === 'narrator') {
                    narratorGroup.push(chapterData.blocks[i]);
                    i++;
                  }
                  // Render them inside a single wrapper (no gap between them)
                  elements.push(
                    <div key={`${chapterData.id}-narrator-group-${startIndex}`} className="narrator-group shadow-[0_4px_30px_rgba(109,40,217,0.15)] rounded-xl">
                      {narratorGroup.map((nb, ni) => (
                        <ScriptBlock
                          key={`${chapterData.id}-narrator-${startIndex}-${ni}`}
                          block={nb}
                          blockIndex={startIndex + ni}
                          chapterId={chapterData.filename.replace('.json', '')}
                          allBlocks={chapterData.blocks}
                          onUpdate={(updatedBlock) => {
                            // Handle deletion
                            if (updatedBlock === null) {
                              const newBlocks = [...chapterData.blocks];
                              newBlocks.splice(startIndex + ni, 1);
                              setLoadedChapters(prev => prev.map(ch =>
                                ch.id === chapterData.id
                                  ? { ...ch, blocks: newBlocks }
                                  : ch
                              ));
                              return;
                            }

                            // Update local state
                            const newBlocks = [...chapterData.blocks];
                            newBlocks[startIndex + ni] = updatedBlock;

                            setLoadedChapters(prev => prev.map(ch =>
                              ch.id === chapterData.id
                                ? { ...ch, blocks: newBlocks }
                                : ch
                            ));
                          }} mergeTop={ni > 0}
                          mergeBottom={ni < narratorGroup.length - 1}
                        />
                      ))}
                    </div>
                  );
                } else {
                  elements.push(
                    <ScriptBlock
                      key={`${chapterData.id}-${block.type}-${i}`}
                      block={block}
                      blockIndex={i}
                      chapterId={chapterData.filename.replace('.json', '')}
                      allBlocks={chapterData.blocks}
                      onUpdate={(updatedBlock) => {
                        // Handle deletion
                        if (updatedBlock === null) {
                          const newBlocks = [...chapterData.blocks];
                          newBlocks.splice(i, 1);
                          setLoadedChapters(prev => prev.map(ch =>
                            ch.id === chapterData.id
                              ? { ...ch, blocks: newBlocks }
                              : ch
                          ));
                          return;
                        }

                        // Update local state
                        const newBlocks = [...chapterData.blocks];
                        newBlocks[i] = updatedBlock;

                        setLoadedChapters(prev => prev.map(ch =>
                          ch.id === chapterData.id
                            ? { ...ch, blocks: newBlocks }
                            : ch
                        ));
                      }}
                    />
                  );
                  i++;
                }
              }
              return elements;
            })()}
          </div>
        </div>
      )})}

      {/* Bottom Sentinel — triggers loading next chapter */}
      <div ref={bottomSentinel} className="h-20 flex items-center justify-center py-10 opacity-50">
        {loadingNext ? (
          <LoadingSpinner size="md" />
        ) : hasNext ? (
          <span className="text-[var(--text-dim)] animate-pulse">Scroll for more...</span>
        ) : (
          <span className="text-[var(--text-dim)]">End of Series via DB</span>
        )}
      </div>

    </div>
  );
}
