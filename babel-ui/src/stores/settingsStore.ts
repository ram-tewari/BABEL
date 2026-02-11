/**
 * Settings Store (Zustand)
 * 
 * Global state management for theme, font size, sidebar, and character
 * customizations. All state is persisted to localStorage and can sync
 * across browser tabs.
 * 
 * Tasks 8.1-8.7: Zustand Store Implementation
 * Validates: Requirements 3.1-3.7, Property 3
 */

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { SettingsStore, Theme, CharacterPrefs } from '@/types/settings';

/** localStorage key for settings persistence */
const STORAGE_KEY = 'babel-settings';

/**
 * Apply theme to the document root element.
 * Sets the data-theme attribute which activates CSS variable overrides.
 */
function applyTheme(theme: Theme): void {
    document.documentElement.setAttribute('data-theme', theme);
}

/**
 * Apply font size to the document root element.
 * Updates the --base-font-size CSS variable.
 */
function applyFontSize(fontSize: number): void {
    document.documentElement.style.setProperty('--base-font-size', `${fontSize}px`);
}

/**
 * Settings store with persistence middleware.
 * 
 * State is automatically saved to localStorage on every change
 * and restored on page load. Cross-tab sync is handled via
 * the storage event listener.
 */
export const useSettingsStore = create<SettingsStore>()(
    persist(
        (set, get) => ({
            // --- State ---
            theme: 'dark' as Theme,
            fontSize: 16,
            sidebarOpen: true,
            characterPrefs: {} as Record<string, CharacterPrefs>,

            // --- Actions ---

            /** Set theme and apply to document */
            setTheme: (theme: Theme) => {
                applyTheme(theme);
                set({ theme });
            },

            /** Set font size (clamped 12-24) and apply to document */
            setFontSize: (fontSize: number) => {
                const clamped = Math.max(12, Math.min(24, fontSize));
                applyFontSize(clamped);
                set({ fontSize: clamped });
            },

            /** Toggle sidebar open/closed */
            toggleSidebar: () => {
                set((state) => ({ sidebarOpen: !state.sidebarOpen }));
            },

            /** Set sidebar state directly */
            setSidebarOpen: (open: boolean) => {
                set({ sidebarOpen: open });
            },

            /** Get preferences for a specific character */
            getCharacterPrefs: (characterName: string): CharacterPrefs => {
                return get().characterPrefs[characterName] || {};
            },

            /** Set preferences for a specific character */
            setCharacterPrefs: (characterName: string, prefs: CharacterPrefs) => {
                set((state) => ({
                    characterPrefs: {
                        ...state.characterPrefs,
                        [characterName]: prefs,
                    },
                }));
            },

            /** Reset preferences for a specific character (removes overrides) */
            resetCharacterPrefs: (characterName: string) => {
                set((state) => {
                    const { [characterName]: _, ...rest } = state.characterPrefs;
                    return { characterPrefs: rest };
                });
            },
        }),
        {
            name: STORAGE_KEY,
            storage: createJSONStorage(() => localStorage),
            // Only persist these fields (not functions)
            partialize: (state) => ({
                theme: state.theme,
                fontSize: state.fontSize,
                sidebarOpen: state.sidebarOpen,
                characterPrefs: state.characterPrefs,
            }),
            // On rehydration, apply theme and font size to DOM
            onRehydrateStorage: () => {
                return (state) => {
                    if (state) {
                        applyTheme(state.theme);
                        applyFontSize(state.fontSize);
                    }
                };
            },
        }
    )
);

/**
 * Cross-tab synchronization.
 * 
 * Listens for storage events from other tabs and updates the store
 * when the settings key changes. This ensures settings changes in
 * one tab are reflected in all other open tabs.
 * 
 * Task 8.6: Implement cross-tab synchronization
 */
if (typeof window !== 'undefined') {
    window.addEventListener('storage', (event) => {
        if (event.key === STORAGE_KEY && event.newValue) {
            try {
                const parsed = JSON.parse(event.newValue);
                const state = parsed.state;
                if (state) {
                    const store = useSettingsStore.getState();
                    if (state.theme && state.theme !== store.theme) {
                        store.setTheme(state.theme);
                    }
                    if (state.fontSize && state.fontSize !== store.fontSize) {
                        store.setFontSize(state.fontSize);
                    }
                    if (typeof state.sidebarOpen === 'boolean' && state.sidebarOpen !== store.sidebarOpen) {
                        store.setSidebarOpen(state.sidebarOpen);
                    }
                    if (state.characterPrefs) {
                        useSettingsStore.setState({ characterPrefs: state.characterPrefs });
                    }
                }
            } catch (err) {
                console.error('[Settings] Failed to sync cross-tab settings:', err);
            }
        }
    });
}

/**
 * Convenience hook alias for using the settings store.
 * Re-exports useSettingsStore for consistent naming convention.
 */
export const useSettings = useSettingsStore;
