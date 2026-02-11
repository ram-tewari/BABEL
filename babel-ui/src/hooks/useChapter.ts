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
export const chapterKeys = {
    all: ['chapters'] as const,
    detail: (id: number) => [...chapterKeys.all, 'detail', id] as const,
};

/**
 * Hook for fetching a single chapter's content
 * 
 * @param chapterId - Chapter ID to fetch
 * @returns TanStack Query result with chapter data
 * 
 * Features:
 * - Caches chapter data for 5 minutes
 * - Retries failed requests 3 times with exponential backoff
 * - Prefetches next/previous chapters automatically
 * - Returns loading and error states
 */
export function useChapter(chapterId: number | null) {
    const queryClient = useQueryClient();

    const query = useQuery<ChapterResponse>({
        queryKey: chapterKeys.detail(chapterId ?? 0),
        queryFn: () => api.getChapter(chapterId!),
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
                    queryKey: chapterKeys.detail(next),
                    queryFn: () => api.getChapter(next),
                    staleTime: 5 * 60 * 1000,
                });
            }

            if (prev) {
                queryClient.prefetchQuery({
                    queryKey: chapterKeys.detail(prev),
                    queryFn: () => api.getChapter(prev),
                    staleTime: 5 * 60 * 1000,
                });
            }
        }
    }, [query.data, queryClient]);

    return query;
}
