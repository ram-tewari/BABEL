import { test, expect } from '@playwright/test';

/**
 * Interactions E2E Test (Task 20.4)
 * 
 * Verifies keyboard shortcuts and accessibility:
 * 1. Ctrl+B (Toggle Sidebar)
 * 2. Escape (Close Modals)
 * 3. Arrow Keys (Navigation)
 * 
 * Validates: Requirements 5.3 (Keyboard Navigation)
 */
test('keyboard shortcuts', async ({ page }) => {
    await page.goto('/');

    // 1. Sidebar Toggle (Ctrl+B)
    // Assuming a keybinding hook is active
    await page.keyboard.press('Control+B');

    // Verify Sidebar open/close state
    const sidebar = page.locator('.sidebar-nav'); // Assuming class name
    await expect(sidebar).toBeVisible(); // Or check visibility toggle based on initial state

    // Close again
    await page.keyboard.press('Control+B');
    await expect(sidebar).not.toBeVisible();

    // 2. Open a Modal and Close with Escape
    // Open Settings Modal manually or via button
    const settingsButton = page.locator('button[aria-label="Settings"]'); // Update selector
    await settingsButton.click();

    const settingsModal = page.locator('div[role="dialog"]');
    await expect(settingsModal).toBeVisible();

    // Press Escape
    await page.keyboard.press('Escape');
    await expect(settingsModal).not.toBeVisible();

    // 3. Arrow Key Navigation (Requires a Chapter)
    await page.goto('/chapter/1');

    // Wait for content (Chapter View)
    await expect(page.getByTestId('chapter-view')).toBeVisible();

    // Press ArrowRight (Next Chapter)
    await page.keyboard.press('ArrowRight');

    // Wait for navigation URL change
    // This assumes Chapter 1 -> Chapter 2 transition
    // If only one chapter exists, this might not navigate or show an alert/toast

    // Check URL or specific reaction (e.g., scroll position reset)
    await page.waitForURL(/\/chapter\/2/); // May fail if chapter structure not set up
    await expect(page).toHaveURL(/\/chapter\/2/);
});
