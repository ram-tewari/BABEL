/**
 * Modal Component
 * 
 * Base modal component with backdrop blur, close on backdrop click,
 * close on Escape key, and focus trap. Used as the foundation for
 * SettingsModal and CharacterModal.
 * 
 * Task 7.2: Implement Modal base component
 * Validates: System Design
 */

import { useEffect, useRef, useCallback } from 'react';

interface ModalProps {
    /** Whether the modal is open */
    open: boolean;
    /** Callback when the modal should close */
    onClose: () => void;
    /** Modal content */
    children: React.ReactNode;
}

/**
 * Modal renders a centered overlay dialog.
 * 
 * Features:
 * - Backdrop with blur (4px) and dark overlay (70% opacity)
 * - Close on backdrop click
 * - Close on Escape key
 * - Focus trap (Tab cycles within modal)
 * - Glassmorphism content panel
 * - Fade-in animation (0.2s)
 * - Prevents body scroll when open
 */
export function Modal({ open, onClose, children }: ModalProps) {
    const modalRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);

    // Close on Escape key
    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onClose();
            }

            // Focus trap: Tab cycles within modal
            if (e.key === 'Tab' && contentRef.current) {
                const focusableElements = contentRef.current.querySelectorAll(
                    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
                );
                const firstFocusable = focusableElements[0] as HTMLElement;
                const lastFocusable = focusableElements[focusableElements.length - 1] as HTMLElement;

                if (e.shiftKey) {
                    if (document.activeElement === firstFocusable) {
                        e.preventDefault();
                        lastFocusable?.focus();
                    }
                } else {
                    if (document.activeElement === lastFocusable) {
                        e.preventDefault();
                        firstFocusable?.focus();
                    }
                }
            }
        },
        [onClose]
    );

    // Close on backdrop click
    const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
        if (e.target === modalRef.current) {
            onClose();
        }
    };

    // Add/remove event listeners and manage body scroll
    useEffect(() => {
        if (open) {
            document.addEventListener('keydown', handleKeyDown);
            document.body.style.overflow = 'hidden';

            // Focus first focusable element in modal
            requestAnimationFrame(() => {
                if (contentRef.current) {
                    const firstFocusable = contentRef.current.querySelector(
                        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
                    ) as HTMLElement;
                    firstFocusable?.focus();
                }
            });
        }

        return () => {
            document.removeEventListener('keydown', handleKeyDown);
            document.body.style.overflow = '';
        };
    }, [open, handleKeyDown]);

    if (!open) return null;

    return (
        <div
            ref={modalRef}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={handleBackdropClick}
            data-testid="modal-backdrop"
            role="dialog"
            aria-modal="true"
        >
            <div
                ref={contentRef}
                className="modal-content max-h-[90vh] overflow-y-auto"
                onClick={(e) => e.stopPropagation()} // Prevent clicks from bubbling to parent block
                data-testid="modal-content"
            >
                {children}
            </div>
        </div>
    );
}


