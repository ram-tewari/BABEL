/**
 * Data Fetching Integration Tests
 * 
 * Tests for useChapter and useChapterList hooks with mocked API.
 * 
 * Task 11.4: Write integration tests for data fetching
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useChapter } from './useChapter';
import { useChapterList } from './useChapterList';

// Mock the API module
vi.mock('@/lib/api', () => ({
    api: {
        getChapter: vi.fn(),
        getChapterList: vi.fn(),
        getNovelChapters: vi.fn(),
        getCharacterList: vi.fn(),
        healthCheck: vi.fn(),
    },
}));

import { api } from '@/lib/api';

const mockedApi = vi.mocked(api);

function createWrapper() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
                gcTime: 0,
            },
        },
    });
    return ({ children }: { children: React.ReactNode }) =>
        React.createElement(QueryClientProvider, { client: queryClient }, children);
}

const mockChapterData = {
    id: 1,
    chapter_index: 1,
    filename: '001.json',
    title: 'Chapter 1',
    blocks: [
        { type: 'narrator' as const, content: 'Once upon a time...' },
        { type: 'dialogue' as const, speaker: 'Hero', content: 'Hello!', tone: 'happy' },
    ],
    metadata: {
        model_version: '1.0',
        processed_at: '2024-01-01',
        source_hash: 'abc123',
    },
    navigation: { prev: undefined, next: 2 },
};

const mockChapterList = {
    chapters: [
        {
            id: 1,
            chapter_index: 1,
            filename: '001.json',
            title: 'Chapter 1',
            status: 'completed',
            phase: 'render',
        },
        {
            id: 2,
            chapter_index: 2,
            filename: '002.json',
            title: 'Chapter 2',
            status: 'completed',
            phase: 'render',
        },
    ],
    total: 2,
    novel_id: 'default',
};

describe('useChapter', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should fetch chapter data successfully', async () => {
        mockedApi.getChapter.mockResolvedValue(mockChapterData);
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(1), { wrapper });

        await waitFor(() => {
            expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(mockChapterData);
        // Called at least once for the main fetch (may also prefetch next/prev)
        expect(mockedApi.getChapter).toHaveBeenCalledWith(1);
    });

    it('should return loading state initially', () => {
        mockedApi.getChapter.mockReturnValue(new Promise(() => { }));
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(1), { wrapper });

        expect(result.current.isLoading).toBe(true);
        expect(result.current.data).toBeUndefined();
    });

    it('should prefetch next chapter when available', async () => {
        mockedApi.getChapter.mockResolvedValue(mockChapterData);
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(1), { wrapper });

        await waitFor(() => {
            expect(result.current.isSuccess).toBe(true);
        });

        // Should prefetch next chapter (id=2 from navigation)
        await waitFor(() => {
            expect(mockedApi.getChapter).toHaveBeenCalledWith(2);
        });
    });

    it('should not fetch when id is null', () => {
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(null), { wrapper });

        expect(result.current.isLoading).toBe(false);
        expect(mockedApi.getChapter).not.toHaveBeenCalled();
    });

    it('should not fetch when id is 0', () => {
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(0), { wrapper });

        // enabled: chapterId !== null && chapterId > 0
        expect(result.current.fetchStatus).toBe('idle');
        expect(mockedApi.getChapter).not.toHaveBeenCalled();
    });
});

describe('useChapter navigation data', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should return navigation data from chapter', async () => {
        mockedApi.getChapter.mockResolvedValue(mockChapterData);
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(1), { wrapper });

        await waitFor(() => {
            expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data?.navigation?.next).toBe(2);
        expect(result.current.data?.navigation?.prev).toBeUndefined();
    });

    it('should return undefined navigation when loading', () => {
        mockedApi.getChapter.mockReturnValue(new Promise(() => { }));
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapter(1), { wrapper });

        expect(result.current.data?.navigation).toBeUndefined();
    });
});

describe('useChapterList', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should fetch chapter list successfully', async () => {
        mockedApi.getChapterList.mockResolvedValueOnce(mockChapterList);
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapterList(), { wrapper });

        await waitFor(() => {
            expect(result.current.isSuccess).toBe(true);
        });

        expect(result.current.data).toEqual(mockChapterList);
        expect(result.current.data?.chapters).toHaveLength(2);
    });

    it('should handle loading state', () => {
        mockedApi.getChapterList.mockReturnValue(new Promise(() => { }));
        const wrapper = createWrapper();

        const { result } = renderHook(() => useChapterList(), { wrapper });

        expect(result.current.isLoading).toBe(true);
    });

    it('should call getChapterList with default novel id', async () => {
        mockedApi.getChapterList.mockResolvedValueOnce(mockChapterList);
        const wrapper = createWrapper();

        renderHook(() => useChapterList(), { wrapper });

        await waitFor(() => {
            expect(mockedApi.getChapterList).toHaveBeenCalledWith('default');
        });
    });

    it('should call getNovelChapters with custom novel id', async () => {
        // Mock getNovelChapters instead of getChapterList
        mockedApi.getNovelChapters.mockResolvedValueOnce(mockChapterList);
        const wrapper = createWrapper();

        renderHook(() => useChapterList('custom-novel'), { wrapper });

        await waitFor(() => {
            expect(mockedApi.getNovelChapters).toHaveBeenCalledWith('custom-novel');
        });
    });
});

// ============================================================================
// Property-Based Tests (Tasks 30.1, 31.1)
// ============================================================================

import * as fc from 'fast-check';
import { chapterKeys } from './useChapter';

describe('PBT: Navigation Consistency (Task 30.1)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should generate deterministic query keys for any chapter ID', () => {
        fc.assert(
            fc.property(fc.integer({ min: 1, max: 10000 }), (id) => {
                const key1 = chapterKeys.detail(id);
                const key2 = chapterKeys.detail(id);
                expect(key1).toEqual(key2);
                expect(key1).toEqual(['chapters', 'detail', id]);
            }),
            { numRuns: 500 }
        );
    });

    it('should generate unique query keys for different chapter IDs', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 10000 }),
                fc.integer({ min: 1, max: 10000 }),
                (id1, id2) => {
                    if (id1 === id2) return true;
                    const key1 = chapterKeys.detail(id1);
                    const key2 = chapterKeys.detail(id2);
                    // Keys differ only in the chapter id component
                    expect(key1[2]).not.toBe(key2[2]);
                }
            ),
            { numRuns: 500 }
        );
    });

    it('should enable fetch only for positive chapter IDs', async () => {
        fc.assert(
            fc.property(fc.integer({ min: 1, max: 10000 }), (id) => {
                mockedApi.getChapter.mockResolvedValue(mockChapterData);
                const wrapper = createWrapper();

                const { result } = renderHook(() => useChapter(id), { wrapper });

                // Positive IDs should trigger loading (enabled = true)
                expect(result.current.isLoading).toBe(true);
            }),
            { numRuns: 20 } // Fewer runs due to hook rendering overhead
        );
    });

    it('should disable fetch for null chapter IDs', () => {
        const wrapper = createWrapper();
        const { result } = renderHook(() => useChapter(null), { wrapper });

        expect(result.current.isLoading).toBe(false);
        expect(result.current.fetchStatus).toBe('idle');
    });

    it('should disable fetch for zero and negative chapter IDs', () => {
        fc.assert(
            fc.property(fc.integer({ min: -100, max: 0 }), (id) => {
                const wrapper = createWrapper();
                const { result } = renderHook(() => useChapter(id), { wrapper });

                expect(result.current.fetchStatus).toBe('idle');
                expect(mockedApi.getChapter).not.toHaveBeenCalled();
            }),
            { numRuns: 20 }
        );
    });
});

describe('PBT: Cache Efficiency (Task 31.1)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('should reuse cached data when same chapter is requested again', async () => {
        mockedApi.getChapter.mockResolvedValue(mockChapterData);

        // Use a shared QueryClient so the cache persists across renders
        const queryClient = new QueryClient({
            defaultOptions: {
                queries: { retry: false, gcTime: Infinity, staleTime: Infinity },
            },
        });
        const wrapper = ({ children }: { children: React.ReactNode }) =>
            React.createElement(QueryClientProvider, { client: queryClient }, children);

        // First fetch
        const { result: result1 } = renderHook(() => useChapter(1), { wrapper });
        await waitFor(() => {
            expect(result1.current.isSuccess).toBe(true);
        });

        const callCountAfterFirst = mockedApi.getChapter.mock.calls.filter(
            (c: unknown[]) => c[0] === 1
        ).length;

        // Second fetch of same chapter — should use cache
        const { result: result2 } = renderHook(() => useChapter(1), { wrapper });
        await waitFor(() => {
            expect(result2.current.isSuccess).toBe(true);
        });

        const callCountAfterSecond = mockedApi.getChapter.mock.calls.filter(
            (c: unknown[]) => c[0] === 1
        ).length;

        // Should NOT have made an additional API call
        expect(callCountAfterSecond).toBe(callCountAfterFirst);
        expect(result2.current.data).toEqual(mockChapterData);
    });

    it('should maintain query key uniqueness for cache isolation', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 1000 }),
                fc.integer({ min: 1001, max: 2000 }),
                (id1, id2) => {
                    const key1 = JSON.stringify(chapterKeys.detail(id1));
                    const key2 = JSON.stringify(chapterKeys.detail(id2));
                    expect(key1).not.toBe(key2);
                }
            ),
            { numRuns: 200 }
        );
    });

    describe('PBT: Chapter List Isolation (Task 16.2 / Property 11)', () => {
        beforeEach(() => {
            vi.clearAllMocks();
        });

        it('should route default novelId to legacy API', async () => {
            mockedApi.getChapterList.mockResolvedValue(mockChapterList);
            // Use default novelId ('default')
            const { result, unmount } = renderHook(() => useChapterList('default'), { wrapper: createWrapper() });

            await waitFor(() => expect(result.current.isSuccess).toBe(true));

            expect(mockedApi.getChapterList).toHaveBeenCalledWith('default');
            expect(mockedApi.getNovelChapters).not.toHaveBeenCalled();
            unmount();
        });

        it('should route custom novelId to Library API (getNovelChapters)', async () => {
            await fc.assert(
                fc.asyncProperty(
                    fc.string({ minLength: 1 }).filter(sid => sid !== 'default' && sid !== 'undefined'),
                    async (novelId) => {
                        // Reset mocks manually since they persist in closure? 
                        // No, new mock call clears history? 
                        // beforeEach runs only before IT. Property runs repeatedly inside ONE IT.
                        // So we must manually clear or just check call count > 0?
                        // Better to clear manually.
                        mockedApi.getChapterList.mockClear();
                        mockedApi.getNovelChapters.mockClear();

                        // Setup return value
                        const iterationMockData = { ...mockChapterList, novelId };
                        mockedApi.getNovelChapters.mockResolvedValue(iterationMockData);

                        const { result, unmount } = renderHook(() => useChapterList(novelId), { wrapper: createWrapper() });

                        await waitFor(() => expect(result.current.isSuccess).toBe(true));

                        expect(mockedApi.getNovelChapters).toHaveBeenCalledWith(novelId);
                        expect(mockedApi.getChapterList).not.toHaveBeenCalled();

                        unmount();
                    }
                ),
                { numRuns: 20 }
            );
        });
    });
});
