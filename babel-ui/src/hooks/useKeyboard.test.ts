/**
 * useKeyboard Hook Tests
 * 
 * Tests for keyboard shortcuts including:
 * - Arrow key navigation
 * - Ctrl+B sidebar toggle  
 * - Escape modal close
 * - Input field exclusion
 * 
 * Task 14.3: Write tests for keyboard shortcuts
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { useKeyboard } from './useKeyboard';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => {
    const actual = await importOriginal() as any;
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

// Mock settings store
const mockToggleSidebar = vi.fn();
vi.mock('@/stores/settingsStore', () => ({
    useSettings: () => ({
        toggleSidebar: mockToggleSidebar,
        theme: 'dark',
        fontSize: 16,
        sidebarOpen: true,
        characterPrefs: {},
        setTheme: vi.fn(),
        setFontSize: vi.fn(),
        setSidebarOpen: vi.fn(),
        getCharacterPrefs: vi.fn(() => ({})),
        setCharacterPrefs: vi.fn(),
        resetCharacterPrefs: vi.fn(),
    }),
}));

function createWrapper() {
    return ({ children }: { children: React.ReactNode }) =>
        React.createElement(MemoryRouter, null, children);
}

function fireKeyDown(key: string, options: Partial<KeyboardEventInit> = {}) {
    const event = new KeyboardEvent('keydown', {
        key,
        bubbles: true,
        cancelable: true,
        ...options,
    });
    document.dispatchEvent(event);
    return event;
}

describe('useKeyboard', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    describe('Arrow Key Navigation', () => {
        it('should navigate to previous chapter on ArrowLeft', () => {
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ navigation: { prev: 3, next: 5 } }),
                { wrapper }
            );

            fireKeyDown('ArrowLeft');
            expect(mockNavigate).toHaveBeenCalledWith('/chapter/3');
        });

        it('should navigate to next chapter on ArrowRight', () => {
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ navigation: { prev: 3, next: 5 } }),
                { wrapper }
            );

            fireKeyDown('ArrowRight');
            expect(mockNavigate).toHaveBeenCalledWith('/chapter/5');
        });

        it('should not navigate when no previous chapter', () => {
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ navigation: { next: 2 } }),
                { wrapper }
            );

            fireKeyDown('ArrowLeft');
            expect(mockNavigate).not.toHaveBeenCalled();
        });

        it('should not navigate when no next chapter', () => {
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ navigation: { prev: 1 } }),
                { wrapper }
            );

            fireKeyDown('ArrowRight');
            expect(mockNavigate).not.toHaveBeenCalled();
        });

        it('should not navigate when modal is open', () => {
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ navigation: { prev: 1, next: 3 }, modalOpen: true }),
                { wrapper }
            );

            fireKeyDown('ArrowLeft');
            fireKeyDown('ArrowRight');
            expect(mockNavigate).not.toHaveBeenCalled();
        });
    });

    describe('Sidebar Toggle', () => {
        it('should toggle sidebar on Ctrl+B', () => {
            const wrapper = createWrapper();
            renderHook(() => useKeyboard(), { wrapper });

            fireKeyDown('b', { ctrlKey: true });
            expect(mockToggleSidebar).toHaveBeenCalledTimes(1);
        });

        it('should toggle sidebar on Cmd+B (Mac)', () => {
            const wrapper = createWrapper();
            renderHook(() => useKeyboard(), { wrapper });

            fireKeyDown('b', { metaKey: true });
            expect(mockToggleSidebar).toHaveBeenCalledTimes(1);
        });

        it('should not toggle sidebar on B without modifier', () => {
            const wrapper = createWrapper();
            renderHook(() => useKeyboard(), { wrapper });

            fireKeyDown('b');
            expect(mockToggleSidebar).not.toHaveBeenCalled();
        });
    });

    describe('Escape Key', () => {
        it('should call onCloseModal on Escape when modal is open', () => {
            const onCloseModal = vi.fn();
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ modalOpen: true, onCloseModal }),
                { wrapper }
            );

            fireKeyDown('Escape');
            expect(onCloseModal).toHaveBeenCalledTimes(1);
        });

        it('should not call onCloseModal on Escape when no modal is open', () => {
            const onCloseModal = vi.fn();
            const wrapper = createWrapper();
            renderHook(
                () => useKeyboard({ modalOpen: false, onCloseModal }),
                { wrapper }
            );

            fireKeyDown('Escape');
            expect(onCloseModal).not.toHaveBeenCalled();
        });
    });
});
