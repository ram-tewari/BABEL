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
import { getChapter, type ChapterResponse } from '@/lib/api';
import { formatChapterTitle } from '@/lib/utils';
import { useReadingProgress } from '@/stores/readingProgressStore';

export function ChapterView() {
  const { id } = useParams<{ id: string }>();
  const [chapters, setChapters] = useState<ChapterResponse[]>([]);
  const [loadingNext, setLoadingNext] = useState(false);
  const [loadingPrev, setLoadingPrev] = useState(false);
  const bottomSentinel = useRef<HTMLDivElement>(null);
  const topSentinel = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  const initialId = id ? Number(id) : null;
  const { data: initialChapter, isLoading, error } = useChapter(initialId);
  const { setCurrentChapter } = useReadingProgress();

  // Initialize with the first chapter when loaded or ID changes
  useEffect(() => {
    if (initialChapter) {
      setChapters([initialChapter]);
      window.scrollTo({ top: 0, behavior: 'instant' });
      // Mark chapter as current/read
      setCurrentChapter(initialChapter.id);
    }
  }, [initialChapter, initialId, setCurrentChapter]);

  // Load NEXT chapter (scroll down)
  const loadNextChapter = useCallback(async () => {
    if (loadingNext || loadingPrev || !chapters.length) return;

    const lastChapter = chapters[chapters.length - 1];
    const nextId = lastChapter.navigation?.next;

    if (!nextId) return;

    setLoadingNext(true);
    try {
      const nextChapter = await getChapter(nextId);
      setChapters(prev => [...prev, nextChapter]);
      window.history.replaceState(null, '', `/chapter/${nextId}`);
      // Mark next chapter as current/read
      setCurrentChapter(nextId);
    } catch (err) {
      console.error("Failed to load next chapter", err);
    } finally {
      setLoadingNext(false);
    }
  }, [chapters, loadingNext, loadingPrev, setCurrentChapter]);

  // Load PREVIOUS chapter (scroll up)
  const loadPrevChapter = useCallback(async () => {
    if (loadingPrev || loadingNext || !chapters.length) return;

    const firstChapter = chapters[0];
    const prevId = firstChapter.navigation?.prev;

    if (!prevId) return;

    setLoadingPrev(true);
    try {
      const prevChapter = await getChapter(prevId);

      // Measure scroll height before prepending
      const scrollContainer = document.querySelector('main.overflow-y-auto') || document.scrollingElement;
      const scrollHeightBefore = scrollContainer?.scrollHeight || 0;
      const scrollTopBefore = scrollContainer?.scrollTop || window.scrollY;

      setChapters(prev => [prevChapter, ...prev]);

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
  }, [chapters, loadingPrev, loadingNext]);

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


  // Loading State (Initial)
  if (isLoading && chapters.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 animate-fadeIn">
        <LoadingSpinner size="lg" />
        <p className="text-[var(--text-dim)]">Loading chapter...</p>
      </div>
    );
  }

  // Error State
  if (error && chapters.length === 0) {
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
  if (!chapters.length) {
    return null;
  }

  // Check if previous chapters are available
  const hasPrev = !!chapters[0]?.navigation?.prev;
  const hasNext = !!chapters[chapters.length - 1]?.navigation?.next;

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

      {chapters.map((chapterData, cIndex) => (
        <div
          key={chapterData.id}
          id={`chapter-${cIndex}`}
          data-chapter-id={chapterData.id}
          className="chapter-container mb-20 fade-in-up scroll-mt-24"
        >
          {/* Chapter Header divider for all chapters after the first */}
          {cIndex > 0 && (
            <div id={`chapter-divider-${cIndex}`} className="my-12 flex flex-col items-center gap-4 scroll-mt-24">
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
                              setChapters(prev => prev.map(ch => 
                                ch.id === chapterData.id 
                                  ? { ...ch, blocks: newBlocks }
                                  : ch
                              ));
                              return;
                            }
                            
                            // Update local state
                            const newBlocks = [...chapterData.blocks];
                            newBlocks[startIndex + ni] = updatedBlock;
                            
                            setChapters(prev => prev.map(ch => 
                              ch.id === chapterData.id 
                                ? { ...ch, blocks: newBlocks }
                                : ch
                            ));
                          }}mergeTop={ni > 0}
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
                          setChapters(prev => prev.map(ch => 
                            ch.id === chapterData.id 
                              ? { ...ch, blocks: newBlocks }
                              : ch
                          ));
                          return;
                        }
                        
                        // Update local state
                        const newBlocks = [...chapterData.blocks];
                        newBlocks[i] = updatedBlock;
                        
                        setChapters(prev => prev.map(ch => 
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
      ))}

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
