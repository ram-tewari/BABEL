/**
 * Settings Store Tests
 * 
 * Tests for the Zustand settings store including:
 * - Theme persistence
 * - Font size management
 * - Sidebar state
 * - Character preferences
 * 
 * Task 8.7: Write state management tests
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useSettingsStore } from './settingsStore';

describe('Settings Store', () => {
    // Reset store and localStorage before each test
    beforeEach(() => {
        localStorage.clear();
        useSettingsStore.setState({
            theme: 'dark',
            fontSize: 16,
            sidebarOpen: true,
            characterPrefs: {},
        });
    });

    afterEach(() => {
        localStorage.clear();
    });

    describe('Theme Management', () => {
        it('should have dark theme by default', () => {
            expect(useSettingsStore.getState().theme).toBe('dark');
        });

        it('should set theme to light', () => {
            useSettingsStore.getState().setTheme('light');
            expect(useSettingsStore.getState().theme).toBe('light');
        });

        it('should set theme to dark', () => {
            useSettingsStore.getState().setTheme('light');
            useSettingsStore.getState().setTheme('dark');
            expect(useSettingsStore.getState().theme).toBe('dark');
        });

        it('should apply theme to document', () => {
            useSettingsStore.getState().setTheme('light');
            expect(document.documentElement.getAttribute('data-theme')).toBe('light');
        });
    });

    describe('Font Size Management', () => {
        it('should have 16px font size by default', () => {
            expect(useSettingsStore.getState().fontSize).toBe(16);
        });

        it('should set font size', () => {
            useSettingsStore.getState().setFontSize(20);
            expect(useSettingsStore.getState().fontSize).toBe(20);
        });

        it('should clamp font size to minimum of 12', () => {
            useSettingsStore.getState().setFontSize(8);
            expect(useSettingsStore.getState().fontSize).toBe(12);
        });

        it('should clamp font size to maximum of 24', () => {
            useSettingsStore.getState().setFontSize(30);
            expect(useSettingsStore.getState().fontSize).toBe(24);
        });

        it('should apply font size to document', () => {
            useSettingsStore.getState().setFontSize(20);
            expect(
                document.documentElement.style.getPropertyValue('--base-font-size')
            ).toBe('20px');
        });
    });

    describe('Sidebar State', () => {
        it('should have sidebar open by default', () => {
            expect(useSettingsStore.getState().sidebarOpen).toBe(true);
        });

        it('should toggle sidebar', () => {
            useSettingsStore.getState().toggleSidebar();
            expect(useSettingsStore.getState().sidebarOpen).toBe(false);
            useSettingsStore.getState().toggleSidebar();
            expect(useSettingsStore.getState().sidebarOpen).toBe(true);
        });

        it('should set sidebar open state directly', () => {
            useSettingsStore.getState().setSidebarOpen(false);
            expect(useSettingsStore.getState().sidebarOpen).toBe(false);
        });
    });

    describe('Character Preferences', () => {
        it('should return empty object for unknown character', () => {
            const prefs = useSettingsStore.getState().getCharacterPrefs('Unknown');
            expect(prefs).toEqual({});
        });

        it('should save character preferences', () => {
            useSettingsStore.getState().setCharacterPrefs('Chung Myung', {
                displayName: 'CM',
                color: '#ff0000',
                lane: 'left',
            });
            const prefs = useSettingsStore.getState().getCharacterPrefs('Chung Myung');
            expect(prefs.displayName).toBe('CM');
            expect(prefs.color).toBe('#ff0000');
            expect(prefs.lane).toBe('left');
        });

        it('should reset character preferences', () => {
            useSettingsStore.getState().setCharacterPrefs('Chung Myung', {
                displayName: 'CM',
                color: '#ff0000',
                lane: 'left',
            });
            useSettingsStore.getState().resetCharacterPrefs('Chung Myung');
            const prefs = useSettingsStore.getState().getCharacterPrefs('Chung Myung');
            expect(prefs).toEqual({});
        });

        it('should not affect other characters when resetting one', () => {
            useSettingsStore.getState().setCharacterPrefs('Chung Myung', {
                displayName: 'CM',
            });
            useSettingsStore.getState().setCharacterPrefs('Baek Cheon', {
                displayName: 'BC',
            });
            useSettingsStore.getState().resetCharacterPrefs('Chung Myung');

            expect(useSettingsStore.getState().getCharacterPrefs('Chung Myung')).toEqual({});
            expect(useSettingsStore.getState().getCharacterPrefs('Baek Cheon').displayName).toBe('BC');
        });

        it('should handle multiple characters', () => {
            useSettingsStore.getState().setCharacterPrefs('A', { displayName: 'Alpha' });
            useSettingsStore.getState().setCharacterPrefs('B', { displayName: 'Beta' });
            useSettingsStore.getState().setCharacterPrefs('C', { displayName: 'Charlie' });

            expect(useSettingsStore.getState().getCharacterPrefs('A').displayName).toBe('Alpha');
            expect(useSettingsStore.getState().getCharacterPrefs('B').displayName).toBe('Beta');
            expect(useSettingsStore.getState().getCharacterPrefs('C').displayName).toBe('Charlie');
        });
    });
});

// ============================================================================
// Property-Based Tests for Settings Persistence (Task 29.1)
// ============================================================================

import * as fc from 'fast-check';

describe('Settings Store - Property-Based Tests', () => {
    beforeEach(() => {
        localStorage.clear();
        useSettingsStore.setState({
            theme: 'dark',
            fontSize: 16,
            sidebarOpen: true,
            characterPrefs: {},
        });
    });

    afterEach(() => {
        localStorage.clear();
    });

    describe('Property 3: Settings Persistence', () => {
        it('should persist theme changes - any valid theme roundtrips through store', () => {
            const themes: Array<'dark' | 'light'> = ['dark', 'light'];
            themes.forEach(theme => {
                useSettingsStore.getState().setTheme(theme);
                expect(useSettingsStore.getState().theme).toBe(theme);
                // Theme should be applied to document
                expect(document.documentElement.getAttribute('data-theme')).toBe(theme);
            });
        });

        it('should clamp any numeric font size to [12, 24]', () => {
            fc.assert(
                fc.property(fc.integer({ min: -100, max: 200 }), (fontSize) => {
                    useSettingsStore.getState().setFontSize(fontSize);
                    const stored = useSettingsStore.getState().fontSize;
                    expect(stored).toBeGreaterThanOrEqual(12);
                    expect(stored).toBeLessThanOrEqual(24);

                    // For values in valid range, should be exact
                    if (fontSize >= 12 && fontSize <= 24) {
                        expect(stored).toBe(fontSize);
                    }
                }),
                { numRuns: 500 }
            );
        });

        it('should persist sidebar toggle - always boolean', () => {
            fc.assert(
                fc.property(fc.boolean(), (initialOpen) => {
                    useSettingsStore.getState().setSidebarOpen(initialOpen);
                    expect(useSettingsStore.getState().sidebarOpen).toBe(initialOpen);

                    // Toggle should flip
                    useSettingsStore.getState().toggleSidebar();
                    expect(useSettingsStore.getState().sidebarOpen).toBe(!initialOpen);
                }),
                { numRuns: 100 }
            );
        });

        it('should persist character prefs for any valid character name', () => {
            // Use alphanumeric names to avoid object key issues (__proto__, constructor)
            const charNameArb = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,29}$/);
            fc.assert(
                fc.property(
                    charNameArb,
                    fc.string({ minLength: 1, maxLength: 30 }),
                    fc.constantFrom('left' as const, 'right' as const, 'center' as const),
                    (name, displayName, lane) => {
                        const prefs = { displayName, lane };
                        useSettingsStore.getState().setCharacterPrefs(name, prefs);
                        const stored = useSettingsStore.getState().getCharacterPrefs(name);

                        expect(stored.displayName).toBe(displayName);
                        expect(stored.lane).toBe(lane);

                        // Reset should clear
                        useSettingsStore.getState().resetCharacterPrefs(name);
                        expect(useSettingsStore.getState().getCharacterPrefs(name)).toEqual({});
                    }
                ),
                { numRuns: 200 }
            );
        });

        it('should maintain theme after multiple rapid changes', () => {
            const themes: Array<'dark' | 'light'> = ['dark', 'light'];
            fc.assert(
                fc.property(
                    fc.array(fc.constantFrom(...themes), { minLength: 1, maxLength: 50 }),
                    (themeSequence) => {
                        themeSequence.forEach(t => useSettingsStore.getState().setTheme(t));
                        const lastTheme = themeSequence[themeSequence.length - 1];
                        expect(useSettingsStore.getState().theme).toBe(lastTheme);
                    }
                ),
                { numRuns: 100 }
            );
        });
    });
});
