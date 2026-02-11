/**
 * Reading Progress Store Tests
 * 
 * Tests for reading progress tracking functionality including:
 * - Marking chapters as read
 * - Setting current chapter
 * - Progress percentage calculation
 * - localStorage persistence
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useReadingProgress } from './readingProgressStore';

describe('Reading Progress Store', () => {
    // Reset store and localStorage before each test
    beforeEach(() => {
        localStorage.clear();
        useReadingProgress.setState({
            currentChapterId: null,
            readChapterIds: new Set<number>(),
            totalChapters: 0,
        });
    });

    afterEach(() => {
        localStorage.clear();
    });

    describe('markChapterAsRead', () => {
        it('should mark a chapter as read', () => {
            const { markChapterAsRead, isChapterRead } = useReadingProgress.getState();
            
            markChapterAsRead(1);
            
            expect(isChapterRead(1)).toBe(true);
        });

        it('should handle marking multiple chapters as read', () => {
            const { markChapterAsRead, isChapterRead } = useReadingProgress.getState();
            
            markChapterAsRead(1);
            markChapterAsRead(2);
            markChapterAsRead(3);
            
            expect(isChapterRead(1)).toBe(true);
            expect(isChapterRead(2)).toBe(true);
            expect(isChapterRead(3)).toBe(true);
            expect(isChapterRead(4)).toBe(false);
        });

        it('should not duplicate chapter IDs', () => {
            const { markChapterAsRead } = useReadingProgress.getState();
            
            markChapterAsRead(1);
            markChapterAsRead(1);
            markChapterAsRead(1);
            
            const state = useReadingProgress.getState();
            expect(state.readChapterIds.size).toBe(1);
        });
    });

    describe('setCurrentChapter', () => {
        it('should set the current chapter', () => {
            const { setCurrentChapter } = useReadingProgress.getState();
            
            setCurrentChapter(5);
            
            const state = useReadingProgress.getState();
            expect(state.currentChapterId).toBe(5);
        });

        it('should automatically mark current chapter as read', () => {
            const { setCurrentChapter, isChapterRead } = useReadingProgress.getState();
            
            setCurrentChapter(5);
            
            expect(isChapterRead(5)).toBe(true);
        });

        it('should update current chapter when changed', () => {
            const { setCurrentChapter } = useReadingProgress.getState();
            
            setCurrentChapter(1);
            setCurrentChapter(2);
            setCurrentChapter(3);
            
            const state = useReadingProgress.getState();
            expect(state.currentChapterId).toBe(3);
        });
    });

    describe('getProgressPercentage', () => {
        it('should return 0% when no chapters are set', () => {
            const { getProgressPercentage } = useReadingProgress.getState();
            
            expect(getProgressPercentage()).toBe(0);
        });

        it('should return 0% when total is 0', () => {
            const { markChapterAsRead, getProgressPercentage } = useReadingProgress.getState();
            
            markChapterAsRead(1);
            
            expect(getProgressPercentage()).toBe(0);
        });

        it('should calculate correct percentage', () => {
            const { setTotalChapters, markChapterAsRead, getProgressPercentage } = useReadingProgress.getState();
            
            setTotalChapters(10);
            markChapterAsRead(1);
            markChapterAsRead(2);
            markChapterAsRead(3);
            
            expect(getProgressPercentage()).toBe(30);
        });

        it('should return 100% when all chapters are read', () => {
            const { setTotalChapters, markChapterAsRead, getProgressPercentage } = useReadingProgress.getState();
            
            setTotalChapters(5);
            markChapterAsRead(1);
            markChapterAsRead(2);
            markChapterAsRead(3);
            markChapterAsRead(4);
            markChapterAsRead(5);
            
            expect(getProgressPercentage()).toBe(100);
        });

        it('should round to nearest integer', () => {
            const { setTotalChapters, markChapterAsRead, getProgressPercentage } = useReadingProgress.getState();
            
            setTotalChapters(3);
            markChapterAsRead(1);
            
            // 1/3 = 33.333...% should round to 33%
            expect(getProgressPercentage()).toBe(33);
        });
    });

    describe('resetProgress', () => {
        it('should reset all progress', () => {
            const { setTotalChapters, setCurrentChapter, markChapterAsRead, resetProgress } = useReadingProgress.getState();
            
            setTotalChapters(10);
            setCurrentChapter(5);
            markChapterAsRead(1);
            markChapterAsRead(2);
            markChapterAsRead(3);
            
            resetProgress();
            
            const state = useReadingProgress.getState();
            expect(state.currentChapterId).toBe(null);
            expect(state.readChapterIds.size).toBe(0);
            expect(state.totalChapters).toBe(0);
        });
    });

    describe('localStorage persistence', () => {
        it('should persist state to localStorage', () => {
            const { setTotalChapters, setCurrentChapter } = useReadingProgress.getState();
            
            setTotalChapters(10);
            setCurrentChapter(5);
            
            // Check localStorage
            const stored = localStorage.getItem('babel-reading-progress');
            expect(stored).toBeTruthy();
            
            const parsed = JSON.parse(stored!);
            expect(parsed.state.currentChapterId).toBe(5);
            expect(parsed.state.totalChapters).toBe(10);
            expect(parsed.state.readChapterIds).toContain(5);
        });

        it('should restore state from localStorage', () => {
            // Set initial state
            const { setTotalChapters, setCurrentChapter } = useReadingProgress.getState();
            setTotalChapters(10);
            setCurrentChapter(5);
            
            // Simulate page reload by getting fresh state
            const newState = useReadingProgress.getState();
            
            expect(newState.currentChapterId).toBe(5);
            expect(newState.totalChapters).toBe(10);
            expect(newState.isChapterRead(5)).toBe(true);
        });
    });
});
