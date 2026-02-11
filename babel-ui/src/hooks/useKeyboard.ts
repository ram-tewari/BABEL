/**
 * useKeyboard Hook
 * 
 * Global keyboard shortcut handler for the BABEL UI.
 * Listens for keyboard events and dispatches actions.
 * 
 * Task 14.1: Implement useKeyboard hook
 * Validates: Requirements 5.3
 */

import { useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSettings } from '@/stores/settingsStore';

interface UseKeyboardOptions {
    /** Current chapter's navigation data */
    navigation?: {
        prev?: number;
        next?: number;
    };
    /** Whether a modal is currently open */
    modalOpen?: boolean;
    /** Callback to close any open modal */
    onCloseModal?: () => void;
}

/**
 * Hook that registers global keyboard shortcuts.
 * 
 * Shortcuts:
 * - ArrowLeft: Navigate to previous chapter
 * - ArrowRight: Navigate to next chapter
 * - Ctrl+B / Cmd+B: Toggle sidebar
 * - Escape: Close open modals (handled by Modal component, but also here as fallback)
 * 
 * All shortcuts are suppressed when focus is on an input, textarea, or select element.
 */
export function useKeyboard(options: UseKeyboardOptions = {}) {
    const { navigation, modalOpen, onCloseModal } = options;
    const navigate = useNavigate();
    const { toggleSidebar } = useSettings();

    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            // Don't handle shortcuts when user is typing in an input
            const target = e.target as HTMLElement | null;
            const tagName = target?.tagName?.toLowerCase() ?? '';
            if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
                // Only allow Escape in input fields
                if (e.key !== 'Escape') return;
            }

            switch (e.key) {
                case 'ArrowLeft':
                    // Navigate to previous chapter
                    if (!modalOpen && navigation?.prev) {
                        e.preventDefault();
                        navigate(`/chapter/${navigation.prev}`);
                    }
                    break;

                case 'ArrowRight':
                    // Navigate to next chapter
                    if (!modalOpen && navigation?.next) {
                        e.preventDefault();
                        navigate(`/chapter/${navigation.next}`);
                    }
                    break;

                case 'b':
                case 'B':
                    // Ctrl+B / Cmd+B: Toggle sidebar
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        toggleSidebar();
                    }
                    break;

                case 'Escape':
                    // Close open modals
                    if (modalOpen && onCloseModal) {
                        onCloseModal();
                    }
                    break;
            }
        },
        [navigation, modalOpen, onCloseModal, navigate, toggleSidebar]
    );

    useEffect(() => {
        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [handleKeyDown]);
}
