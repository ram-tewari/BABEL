/**
 * SettingsModal Component
 * 
 * Modal dialog for theme toggle and font size slider.
 * Connects to the Zustand settings store for persistence.
 * 
 * Task 9.1-9.4: Implement SettingsModal
 * Validates: Requirements 2.7, 1.7, 1.8
 */

import { Modal } from '@/components/ui/Modal';
import { useSettings } from '@/stores/settingsStore';
import { cn } from '@/lib/utils';

interface SettingsModalProps {
    /** Whether the modal is open */
    open: boolean;
    /** Callback when the modal should close */
    onClose: () => void;
}

/**
 * SettingsModal provides controls for theme and font size.
 * 
 * Features:
 * - Theme toggle (Light / Dark) with active state highlighting
 * - Font size slider (12px - 24px) with live preview
 * - Settings automatically persist to localStorage via Zustand
 * - All changes take effect immediately
 */
export function SettingsModal({ open, onClose }: SettingsModalProps) {
    const { theme, fontSize, setTheme, setFontSize } = useSettings();

    return (
        <Modal open={open} onClose={onClose}>
            <div className="modal-header" data-testid="settings-modal-header">
                ⚙️ Settings
            </div>

            {/* Theme Toggle */}
            <div className="modal-field" data-testid="settings-theme-field">
                <label>Theme</label>
                <div className="theme-toggle">
                    <button
                        className={cn('theme-button', theme === 'light' && 'active')}
                        onClick={() => setTheme('light')}
                        data-testid="theme-light-button"
                    >
                        ☀️ Light
                    </button>
                    <button
                        className={cn('theme-button', theme === 'dark' && 'active')}
                        onClick={() => setTheme('dark')}
                        data-testid="theme-dark-button"
                    >
                        🌙 Dark
                    </button>
                </div>
            </div>

            {/* Font Size Slider */}
            <div className="modal-field" data-testid="settings-font-field">
                <label>Font Size: {fontSize}px</label>
                <input
                    type="range"
                    min={12}
                    max={24}
                    step={1}
                    value={fontSize}
                    onChange={(e) => setFontSize(Number(e.target.value))}
                    data-testid="font-size-slider"
                />
            </div>

            {/* Close Button */}
            <button
                className="modal-close"
                onClick={onClose}
                data-testid="settings-close-button"
            >
                Close
            </button>
        </Modal>
    );
}
