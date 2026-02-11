/**
 * CharacterModal Component
 * 
 * Modal dialog for customizing character display name, color, and lane.
 * Connects to the Zustand settings store for persistence.
 * 
 * Task 10.1-10.3: Implement CharacterModal
 * Validates: Requirements 2.8, 3.4
 */

import { useState, useEffect } from 'react';
import { Modal } from '@/components/ui/Modal';
import { useSettings } from '@/stores/settingsStore';

interface CharacterModalProps {
    /** Whether the modal is open */
    open: boolean;
    /** Callback when the modal should close */
    onClose: () => void;
    /** Original character name (key for preferences) */
    character: string;
    /** Initial/default color (from hash generation) */
    initialColor: string;
    /** Initial/default lane position (from hash generation) */
    initialLane: 'left' | 'right' | 'center';
}

/**
 * CharacterModal provides controls to customize character appearance.
 * 
 * Features:
 * - Display name override (text input)
 * - Custom color picker
 * - Lane position selector (left/right/center)
 * - Save persists to localStorage via Zustand
 * - Reset removes all customizations for the character
 * - Cancel discards unsaved changes
 */
export function CharacterModal({
    open,
    onClose,
    character,
    initialColor,
    initialLane,
}: CharacterModalProps) {
    const { getCharacterPrefs, setCharacterPrefs, resetCharacterPrefs } = useSettings();

    // Local form state
    const [displayName, setDisplayName] = useState(character);
    const [color, setColor] = useState(initialColor);
    const [lane, setLane] = useState<'left' | 'right' | 'center'>(initialLane);

    // Reset local state when modal opens or character changes
    useEffect(() => {
        if (open) {
            const prefs = getCharacterPrefs(character);
            setDisplayName(prefs.displayName || character);
            setColor(prefs.color || initialColor);
            setLane(prefs.lane || initialLane);
        }
    }, [open, character, initialColor, initialLane, getCharacterPrefs]);

    const handleSave = () => {
        setCharacterPrefs(character, { displayName, color, lane });
        onClose();
    };

    const handleReset = () => {
        resetCharacterPrefs(character);
        onClose();
    };

    return (
        <Modal open={open} onClose={onClose}>
            <div className="modal-header" data-testid="character-modal-header">
                🎨 Character Settings
            </div>

            {/* Display Name */}
            <div className="modal-field" data-testid="character-name-field">
                <label>Display Name</label>
                <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Enter display name"
                    data-testid="character-name-input"
                />
            </div>

            {/* Color Picker */}
            <div className="modal-field" data-testid="character-color-field">
                <label>Color</label>
                <input
                    type="color"
                    value={color}
                    onChange={(e) => setColor(e.target.value)}
                    data-testid="character-color-input"
                />
            </div>

            {/* Lane Selector */}
            <div className="modal-field" data-testid="character-lane-field">
                <label>Position</label>
                <select
                    value={lane}
                    onChange={(e) => setLane(e.target.value as 'left' | 'right' | 'center')}
                    data-testid="character-lane-select"
                >
                    <option value="left">Left</option>
                    <option value="right">Right</option>
                    <option value="center">Center</option>
                </select>
            </div>

            {/* Action Buttons */}
            <div className="modal-actions" data-testid="character-modal-actions">
                <button
                    className="modal-button primary"
                    onClick={handleSave}
                    data-testid="character-save-button"
                >
                    Save
                </button>
                <button
                    className="modal-button secondary"
                    onClick={onClose}
                    data-testid="character-cancel-button"
                >
                    Cancel
                </button>
                <button
                    className="modal-button reset"
                    onClick={handleReset}
                    data-testid="character-reset-button"
                >
                    Reset
                </button>
            </div>
        </Modal>
    );
}
