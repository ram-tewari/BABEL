/**
 * useChapter Hook
 * 
 * TanStack Query hook for fetching a single chapter's content by ID.
 * Implements caching, retry logic, prefetching, and loading/error states.
 * 
 * Task 11.2: Implement useChapter hook
 * Validates: Requirements 4.1, 4.3, 4.6
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { api } from '@/lib/api';
import type { ChapterResponse } from '@/lib/api';

/**
 * Query key factory for chapter data
 */
/**
 * Query key factory for chapter data
 */
export const chapterKeys = {
    all: ['chapters'] as const,
    detail: (id: number, novelId: number | string = 'default') => [...chapterKeys.all, 'detail', String(novelId), id] as const,
};

/**
 * Hook for fetching a single chapter's content
 * 
 * @param chapterId - Chapter ID to fetch
 * @param novelId - Optional Novel ID (default: 'default')
 * @returns TanStack Query result with chapter data
 * 
 * Features:
 * - Caches chapter data for 5 minutes
 * - Retries failed requests 3 times with exponential backoff
 * - Prefetches next/previous chapters automatically
 * - Returns loading and error states
 */
export function useChapter(chapterId: number | null, novelId: number | string = 'default') {
    const queryClient = useQueryClient();

    const query = useQuery<ChapterResponse>({
        queryKey: chapterKeys.detail(chapterId ?? 0, novelId),
        queryFn: () => {
            if (novelId === 'default') {
                return api.getChapter(chapterId!);
            } else {
                // Ensure novelId is a number for the API call
                const nId = typeof novelId === 'string' ? parseInt(novelId, 10) : novelId;
                if (isNaN(nId)) {
                    // Fallback for invalid ID, though shouldn't happen if properly typed
                    return api.getChapter(chapterId!);
                }
                return api.getNovelChapter(nId, chapterId!);
            }
        },
        enabled: chapterId !== null && chapterId > 0,
        staleTime: 5 * 60 * 1000, // 5 minutes
        gcTime: 30 * 60 * 1000, // 30 minutes cache
        retry: 3,
        retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    });

    // Prefetch next and previous chapters
    useEffect(() => {
        if (query.data?.navigation) {
            const { prev, next } = query.data.navigation;

            if (next) {
                queryClient.prefetchQuery({
                    queryKey: chapterKeys.detail(next, novelId),
                    queryFn: () => {
                        if (novelId === 'default') return api.getChapter(next);
                        const nId = typeof novelId === 'string' ? parseInt(novelId, 10) : novelId;
                        return api.getNovelChapter(nId, next);
                    },
                    staleTime: 5 * 60 * 1000,
                });
            }

            if (prev) {
                queryClient.prefetchQuery({
                    queryKey: chapterKeys.detail(prev, novelId),
                    queryFn: () => {
                        if (novelId === 'default') return api.getChapter(prev);
                        const nId = typeof novelId === 'string' ? parseInt(novelId, 10) : novelId;
                        return api.getNovelChapter(nId, prev);
                    },
                    staleTime: 5 * 60 * 1000,
                });
            }
        }
    }, [query.data, queryClient, novelId]);

    return query;
}
