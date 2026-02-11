/**
 * Reading Progress Store
 * 
 * Tracks reading progress across chapters including:
 * - Current chapter being read
 * - Chapters that have been visited/read
 * - Reading completion percentage
 * 
 * State is persisted to localStorage and syncs across tabs.
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

/** localStorage key for reading progress persistence */
const STORAGE_KEY = 'babel-reading-progress';

export interface ReadingProgressState {
  /** Current chapter ID being read */
  currentChapterId: number | null;
  
  /** Set of chapter IDs that have been visited/read */
  readChapterIds: Set<number>;
  
  /** Total number of chapters available (for progress calculation) */
  totalChapters: number;
  
  /** Mark a chapter as read */
  markChapterAsRead: (chapterId: number) => void;
  
  /** Set the current chapter being read */
  setCurrentChapter: (chapterId: number) => void;
  
  /** Update total chapters count */
  setTotalChapters: (total: number) => void;
  
  /** Check if a chapter has been read */
  isChapterRead: (chapterId: number) => boolean;
  
  /** Get reading progress percentage (0-100) */
  getProgressPercentage: () => number;
  
  /** Reset all reading progress */
  resetProgress: () => void;
}

/**
 * Reading progress store with localStorage persistence.
 * 
 * Automatically saves state on every change and restores on page load.
 */
export const useReadingProgress = create<ReadingProgressState>()(
  persist(
    (set, get) => ({
      currentChapterId: null,
      readChapterIds: new Set<number>(),
      totalChapters: 0,

      markChapterAsRead: (chapterId: number) => {
        set((state) => {
          const newReadChapterIds = new Set(state.readChapterIds);
          newReadChapterIds.add(chapterId);
          return { readChapterIds: newReadChapterIds };
        });
      },

      setCurrentChapter: (chapterId: number) => {
        set({ currentChapterId: chapterId });
        // Also mark as read when set as current
        get().markChapterAsRead(chapterId);
      },

      setTotalChapters: (total: number) => {
        set({ totalChapters: total });
      },

      isChapterRead: (chapterId: number) => {
        return get().readChapterIds.has(chapterId);
      },

      getProgressPercentage: () => {
        const { readChapterIds, totalChapters } = get();
        if (totalChapters === 0) return 0;
        return Math.round((readChapterIds.size / totalChapters) * 100);
      },

      resetProgress: () => {
        set({
          currentChapterId: null,
          readChapterIds: new Set<number>(),
          totalChapters: 0,
        });
      },
    }),
    {
      name: STORAGE_KEY,
      storage: createJSONStorage(() => localStorage),
      // Custom serialization for Set
      partialize: (state) => ({
        currentChapterId: state.currentChapterId,
        readChapterIds: Array.from(state.readChapterIds),
        totalChapters: state.totalChapters,
      }),
      // Custom deserialization for Set
      merge: (persistedState: any, currentState) => ({
        ...currentState,
        ...persistedState,
        readChapterIds: new Set(persistedState?.readChapterIds || []),
      }),
    }
  )
);
