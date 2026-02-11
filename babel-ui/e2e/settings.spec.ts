import { test, expect } from '@playwright/test';

/**
 * Settings Persistence E2E Test (Task 20.2)
 * 
 * Verifies that user preferences persist across sessions:
 * 1. Change theme (Dark -> Light -> Dark)
 * 2. Change font size
 * 3. Reload page
 * 4. Verify settings are retained
 * 
 * Validates: Property 3 (Settings Persistence)
 */
test('settings persistence', async ({ page }) => {
    await page.goto('/');

    // Open settings modal (Ctrl+S or Gear Icon)
    // Assuming a settings button or helper function to open it
    const settingsButton = page.locator('button[aria-label="Settings"]'); // Update selector if changed
    await settingsButton.click();

    const settingsModal = page.locator('div[role="dialog"]');
    await expect(settingsModal).toBeVisible();

    // 1. Change Theme
    const themeToggle = page.locator('button:has-text("Toggle Theme")'); // Update text if different
    await themeToggle.click();

    // Verify theme change (Assuming a class change on body or html)
    // Wait for transition
    await page.waitForTimeout(500);

    // Check localStorage if possible, or visually check CSS variable
    const theme = await page.evaluate(() => localStorage.getItem('theme-storage'));
    expect(theme).toContain('light'); // Assuming default was dark

    // 2. Change Font Size
    const fontSizeSlider = page.locator('input[type="range"]');

    // Set a specific value (e.g., 20px)
    await fontSizeSlider.fill('20');

    // Close settings
    const closeButton = page.locator('button[aria-label="Close"]');
    await closeButton.click();

    // 3. Reload Page
    await page.reload();

    // 4. Verify Settings Persist
    // Check theme
    const persistedTheme = await page.evaluate(() => localStorage.getItem('theme-storage'));
    expect(persistedTheme).toContain('light');

    // Check font size
    const persistedFontSize = await page.evaluate(() => localStorage.getItem('ui-settings-storage'));
    expect(persistedFontSize).toContain('20');
});
