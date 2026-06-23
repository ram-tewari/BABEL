/**
 * useChapterList Hook
 * 
 * TanStack Query hook for fetching the chapter list (metadata only).
 * Implements caching, retry logic, and loading/error states.
 */

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { ChapterListResponse } from '@/lib/api';

/**
 * Hook for fetching chapter list metadata
 * 
 * @param novelId - Novel ID (default: 'default')
 * @returns TanStack Query result with chapter list data
 * 
 * @example
 * ```tsx
 * function ChapterList() {
 *   const { data, isLoading, error } = useChapterList();
 *   
 *   if (isLoading) return <div>Loading...</div>;
 *   if (error) return <div>Error loading chapters</div>;
 *   
 *   return (
 *     <ul>
 *       {data?.chapters.map(chapter => (
 *         <li key={chapter.id}>{chapter.title}</li>
 *       ))}
 *     </ul>
 *   );
 * }
 * ```
 */
export function useChapterList(novelId: string = 'default') {
  return useQuery<ChapterListResponse>({
    queryKey: ['chapterList', novelId],
    queryFn: async () => {
      // Use legacy endpoint for default/single-novel mode
      if (novelId === 'default') {
        return api.getChapterList('default');
      }
      // Use library endpoint for specific novels
      return api.getNovelChapters(novelId);
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - chapter list doesn't change often
    gcTime: 60 * 60 * 1000, // 1 hour cache time (formerly cacheTime)
    retry: 3, // Retry failed requests 3 times
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
  });
}
