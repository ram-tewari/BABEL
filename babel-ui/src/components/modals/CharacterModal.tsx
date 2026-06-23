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
 * Convert HSL color to hex format for color picker
 */
function hslToHex(hsl: string): string {
    // Parse HSL string like "hsl(18, 69%, 70%)" or "hsl(18,69%,70%)"
    const match = hsl.match(/hsl\((\d+),?\s*(\d+)%,?\s*(\d+)%\)/);
    if (!match) {
        console.warn('Failed to parse HSL color:', hsl);
        return '#000000';
    }
    
    const h = parseInt(match[1]) / 360;
    const s = parseInt(match[2]) / 100;
    const l = parseInt(match[3]) / 100;
    
    let r, g, b;
    
    if (s === 0) {
        r = g = b = l;
    } else {
        const hue2rgb = (p: number, q: number, t: number) => {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1/6) return p + (q - p) * 6 * t;
            if (t < 1/2) return q;
            if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
            return p;
        };
        
        const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
        const p = 2 * l - q;
        r = hue2rgb(p, q, h + 1/3);
        g = hue2rgb(p, q, h);
        b = hue2rgb(p, q, h - 1/3);
    }
    
    const toHex = (x: number) => {
        const hex = Math.round(x * 255).toString(16);
        return hex.length === 1 ? '0' + hex : hex;
    };
    
    return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
}

/**
 * Convert hex color to HSL format for storage
 */
function hexToHsl(hex: string): string {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0, s = 0;
    const l = (max + min) / 2;
    
    if (max !== min) {
        const d = max - min;
        s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        
        switch (max) {
            case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
            case g: h = ((b - r) / d + 2) / 6; break;
            case b: h = ((r - g) / d + 4) / 6; break;
        }
    }
    
    return `hsl(${Math.round(h * 360)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`;
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

    // Get initial preferences
    const prefs = getCharacterPrefs(character);
    const initialHslColor = prefs.color || initialColor;

    // Local form state
    const [displayName, setDisplayName] = useState(prefs.displayName || character);
    const [colorHex, setColorHex] = useState(hslToHex(initialHslColor));
    const [lane, setLane] = useState<'left' | 'right' | 'center'>(prefs.lane || initialLane);

    // Reset local state when modal opens or character changes
    useEffect(() => {
        if (open) {
            const prefs = getCharacterPrefs(character);
            setDisplayName(prefs.displayName || character);
            const hslColor = prefs.color || initialColor;
            setColorHex(hslToHex(hslColor));
            setLane(prefs.lane || initialLane);
        }
    }, [open, character, initialColor, initialLane, getCharacterPrefs]);

    const handleSave = () => {
        // Convert hex back to HSL for storage
        const hslColor = hexToHsl(colorHex);
        setCharacterPrefs(character, { displayName, color: hslColor, lane });
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
                    value={colorHex}
                    onChange={(e) => setColorHex(e.target.value)}
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
