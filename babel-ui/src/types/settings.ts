/**
 * Settings Types
 * 
 * Type definitions for the settings store and character preferences.
 */

/** Character customization preferences */
export interface CharacterPrefs {
    /** Custom display name override */
    displayName?: string;
    /** Custom HSL or hex color override */
    color?: string;
    /** Custom lane position override */
    lane?: 'left' | 'right' | 'center';
}

/** Theme options */
export type Theme = 'dark' | 'light';

/** Settings state managed by Zustand */
export interface SettingsState {
    /** Current theme */
    theme: Theme;
    /** Font size in pixels (12-24) */
    fontSize: number;
    /** Whether sidebar is open */
    sidebarOpen: boolean;
    /** Per-character customization preferences */
    characterPrefs: Record<string, CharacterPrefs>;
}

/** Settings actions */
export interface SettingsActions {
    /** Set theme and persist */
    setTheme: (theme: Theme) => void;
    /** Set font size and persist */
    setFontSize: (fontSize: number) => void;
    /** Toggle sidebar state */
    toggleSidebar: () => void;
    /** Set sidebar open state directly */
    setSidebarOpen: (open: boolean) => void;
    /** Get character preferences (returns empty object if none) */
    getCharacterPrefs: (characterName: string) => CharacterPrefs;
    /** Set character preferences and persist */
    setCharacterPrefs: (characterName: string, prefs: CharacterPrefs) => void;
    /** Reset character preferences to defaults */
    resetCharacterPrefs: (characterName: string) => void;
}

/** Combined settings store type */
export type SettingsStore = SettingsState & SettingsActions;
