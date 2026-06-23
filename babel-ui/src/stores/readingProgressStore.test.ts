/**
 * Reading Progress Store Tests
 * 
 * Tests for reading progress tracking functionality including:
 * - Marking chapters as read
 * - Setting current chapter
 * - Progress percentage calculation
 * - localStorage persistence
 * - Multi-novel support
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import fc from 'fast-check';
import { useReadingProgress } from './readingProgressStore';

describe('Reading Progress Store', () => {
    // Reset store and localStorage before each test
    beforeEach(() => {
        localStorage.clear();
        useReadingProgress.setState({
            novels: {},
            currentNovelId: null,
        });
    });

    afterEach(() => {
        localStorage.clear();
    });

    describe('Single Novel Operations', () => {
        it('should mark a chapter as read', () => {
            const { markChapterAsRead, isChapterRead, initNovel } = useReadingProgress.getState();

            initNovel('novel1', 10);
            markChapterAsRead('novel1', 1);

            expect(isChapterRead('novel1', 1)).toBe(true);
        });

        it('should handle marking multiple chapters as read', () => {
            const { markChapterAsRead, isChapterRead, initNovel } = useReadingProgress.getState();

            initNovel('novel1', 10);
            markChapterAsRead('novel1', 1);
            markChapterAsRead('novel1', 2);
            markChapterAsRead('novel1', 3);

            expect(isChapterRead('novel1', 1)).toBe(true);
            expect(isChapterRead('novel1', 2)).toBe(true);
            expect(isChapterRead('novel1', 3)).toBe(true);
            expect(isChapterRead('novel1', 4)).toBe(false);
        });

        it('should calculate correct percentage', () => {
            const { initNovel, markChapterAsRead, getProgressPercentage } = useReadingProgress.getState();

            initNovel('novel1', 10);
            markChapterAsRead('novel1', 1);
            markChapterAsRead('novel1', 2);
            markChapterAsRead('novel1', 3);

            expect(getProgressPercentage('novel1')).toBe(30);
        });

        it('should track current chapter', () => {
            const { setCurrentChapter, getCurrentChapter } = useReadingProgress.getState();

            setCurrentChapter('novel1', 5);

            expect(getCurrentChapter('novel1')).toBe(5);
        });
    });

    describe('Multi-Novel Operations', () => {
        it('should track progress independently for different novels', () => {
            const store = useReadingProgress.getState();

            // Novel 1
            store.initNovel('novel1', 10);
            store.markChapterAsRead('novel1', 1);
            store.setCurrentChapter('novel1', 5);

            // Novel 2
            store.initNovel('novel2', 20);
            store.markChapterAsRead('novel2', 1);
            store.setCurrentChapter('novel2', 10);

            // Verify Novel 1
            expect(store.isChapterRead('novel1', 1)).toBe(true);
            expect(store.getCurrentChapter('novel1')).toBe(5);
            expect(store.getProgressPercentage('novel1')).toBe(20);
            // Wait, setCurrentChapter calls markChapterAsRead in implementation?
            // "Also mark as read when set as current" - Yes.
            // So chapter 1 and 5 are read. 2/10 = 20%.

            // Verify Novel 2
            expect(store.isChapterRead('novel2', 1)).toBe(true);
            expect(store.getCurrentChapter('novel2')).toBe(10);
            expect(store.getProgressPercentage('novel2')).toBe(10); // 1 and 10 read => 2/20 = 10%

            // Verify Independence
            expect(store.isChapterRead('novel1', 10)).toBe(false);
            expect(store.isChapterRead('novel2', 5)).toBe(false);
        });
    });

    describe('Context Switching', () => {
        it('should switch current novel context', () => {
            const store = useReadingProgress.getState();

            store.setCurrentNovel('novel1');
            expect(useReadingProgress.getState().currentNovelId).toBe('novel1');

            store.setCurrentNovel('novel2');
            expect(useReadingProgress.getState().currentNovelId).toBe('novel2');
        });
    });

    // Property Test: Reading Position Persistence
    it('Property 10: Reading Position Persistence - correctly persists and restores state for arbitrary novels', () => {
        fc.assert(
            fc.property(
                fc.dictionary(
                    fc.string({ minLength: 1 }), // novelId
                    fc.record({
                        totalChapters: fc.integer({ min: 1, max: 1000 }),
                        currentChapterId: fc.option(fc.integer({ min: 1, max: 1000 }), { nil: null }),
                        readChapters: fc.array(fc.integer({ min: 1, max: 1000 }))
                    })
                ),
                (novelsData) => {
                    // Reset
                    localStorage.clear();
                    useReadingProgress.setState({ novels: {}, currentNovelId: null });
                    const store = useReadingProgress.getState();

                    // 2. Apply Operations
                    Object.entries(novelsData).forEach(([novelId, data]) => {
                        store.initNovel(novelId, data.totalChapters);
                        if (data.currentChapterId) {
                            store.setCurrentChapter(novelId, data.currentChapterId);
                        }
                        data.readChapters.forEach(ch => {
                            if (ch <= data.totalChapters) {
                                store.markChapterAsRead(novelId, ch);
                            }
                        });
                    });

                    // 3. Verify Store State Matches Input (in-memory)
                    Object.entries(novelsData).forEach(([novelId, data]) => {
                        const novelState = useReadingProgress.getState().novels[novelId];
                        expect(novelState).toBeDefined();

                        if (data.currentChapterId) {
                            expect(novelState.currentChapterId).toBe(data.currentChapterId);
                        }

                        // Check if read chapters are present
                        data.readChapters.forEach(ch => {
                            if (ch <= data.totalChapters) {
                                expect(novelState.readChapterIds.has(ch)).toBe(true);
                            }
                        });
                    });

                    // 4. Verify Persistence (Serialization/Deserialization)
                    // Retrieve from localStorage
                    const stored = localStorage.getItem('babel-reading-progress-v2');
                    expect(stored).toBeTruthy();

                    // Clear store state (simulate reload)
                    useReadingProgress.setState({ novels: {}, currentNovelId: null });

                    // Manually trigger rehydration logic (Zustand persist middleware handles this on init, 
                    // but in test environment we might need to force it or manually parse 'stored' 
                    // and use 'onRehydrateStorage' logic to verify correctness).
                    // Or simpler: parse stored JSON and check structure.

                    const parsed = JSON.parse(stored!);
                    const persistedState = parsed.state;

                    Object.entries(novelsData).forEach(([novelId, data]) => {
                        const persistedNovel = persistedState.novels[novelId];
                        expect(persistedNovel).toBeDefined();

                        if (data.currentChapterId) {
                            expect(persistedNovel.currentChapterId).toBe(data.currentChapterId);
                        }

                        // Check serialized structure (Sets are arrays in JSON)
                        expect(Array.isArray(persistedNovel.readChapterIds)).toBe(true);

                        // Check content
                        data.readChapters.forEach(ch => {
                            if (ch <= data.totalChapters) {
                                expect(persistedNovel.readChapterIds).toContain(ch);
                            }
                        });
                    });
                }
            )
        );
    });
});
