/**
 * Reading Progress Store
 * 
 * Tracks reading progress across novels and chapters.
 * Supports multiple novels with independent progress tracking.
 * 
 * State is persisted to localStorage.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

/** localStorage key for reading progress persistence */
const STORAGE_KEY = 'babel-reading-progress-v2';

export interface NovelProgress {
  currentChapterId: number | null;
  readChapterIds: Set<number>;
  totalChapters: number;
  lastReadAt: number; // Timestamp
}

export interface ReadingProgressState {
  /** Map of novel ID to progress data */
  novels: Record<string, NovelProgress>;

  /** Currently active novel ID */
  currentNovelId: string | null;

  /** Initialize or update a novel's total chapters */
  initNovel: (novelId: string, totalChapters: number) => void;

  /** Mark a chapter as read for a specific novel */
  markChapterAsRead: (novelId: string, chapterId: number) => void;

  /** Set the current chapter being read for a novel */
  setCurrentChapter: (novelId: string, chapterId: number) => void;

  /** Get current chapter for a novel */
  getCurrentChapter: (novelId: string) => number | null;

  /** Check if a chapter has been read */
  isChapterRead: (novelId: string, chapterId: number) => boolean;

  /** Get reading progress percentage (0-100) */
  getProgressPercentage: (novelId: string) => number;

  /** Set current active novel context */
  setCurrentNovel: (novelId: string) => void;
}

export const useReadingProgress = create<ReadingProgressState>()(
  persist(
    (set, get) => ({
      novels: {},
      currentNovelId: null,

      initNovel: (novelId: string, totalChapters: number) => {
        set((state) => {
          const existing = state.novels[novelId];
          if (existing) {
            // Only update if totalChapters changed, preserve other progress
            if (existing.totalChapters !== totalChapters) {
              return {
                novels: {
                  ...state.novels,
                  [novelId]: { ...existing, totalChapters }
                }
              };
            }
            return state;
          }

          // Create new entry
          return {
            novels: {
              ...state.novels,
              [novelId]: {
                currentChapterId: null,
                readChapterIds: new Set<number>(),
                totalChapters,
                lastReadAt: Date.now()
              }
            }
          };
        });
      },

      setCurrentNovel: (novelId: string) => {
        set({ currentNovelId: novelId });
      },

      markChapterAsRead: (novelId: string, chapterId: number) => {
        set((state) => {
          const novel = state.novels[novelId];
          if (!novel) return state; // Should be initialized first

          const newReadChapterIds = new Set(novel.readChapterIds);
          newReadChapterIds.add(chapterId);

          return {
            novels: {
              ...state.novels,
              [novelId]: {
                ...novel,
                readChapterIds: newReadChapterIds,
                lastReadAt: Date.now()
              }
            }
          };
        });
      },

      setCurrentChapter: (novelId: string, chapterId: number) => {
        set((state) => {
          // Ensure novel exists, if not, create it lazily (though init should be called)
          const novel = state.novels[novelId] || {
            currentChapterId: null,
            readChapterIds: new Set<number>(),
            totalChapters: 0,
            lastReadAt: Date.now()
          };

          const newReadChapterIds = new Set(novel.readChapterIds);
          newReadChapterIds.add(chapterId);

          return {
            currentNovelId: novelId,
            novels: {
              ...state.novels,
              [novelId]: {
                ...novel,
                currentChapterId: chapterId,
                readChapterIds: newReadChapterIds,
                lastReadAt: Date.now()
              }
            }
          };
        });
      },

      getCurrentChapter: (novelId: string) => {
        return get().novels[novelId]?.currentChapterId || null;
      },

      isChapterRead: (novelId: string, chapterId: number) => {
        return get().novels[novelId]?.readChapterIds.has(chapterId) || false;
      },

      getProgressPercentage: (novelId: string) => {
        const novel = get().novels[novelId];
        if (!novel || novel.totalChapters === 0) return 0;
        return Math.round((novel.readChapterIds.size / novel.totalChapters) * 100);
      }
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      // Custom serialization
      partialize: (state) => ({
        novels: Object.fromEntries(
          Object.entries(state.novels).map(([id, data]) => [
            id,
            {
              ...data,
              readChapterIds: Array.from(data.readChapterIds)
            }
          ])
        ),
        currentNovelId: state.currentNovelId
      }),
      // Custom deserialization
      onRehydrateStorage: () => (state) => {
        if (state && state.novels) {
          // Convert arrays back to Sets
          Object.keys(state.novels).forEach(key => {
            const novel = state.novels[key];
            if (Array.isArray(novel.readChapterIds)) {
              novel.readChapterIds = new Set(novel.readChapterIds);
            }
          });
        }
      }
    }
  )
);
