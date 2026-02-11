import { test, expect } from '@playwright/test';

/**
 * Reading Journey E2E Test (Task 20.1)
 * 
 * Verifies the core user flow:
 * 1. Navigate to the Home page
 * 2. Select a chapter
 * 3. Read content (verify blocks are rendered)
 * 4. Navigate to the next chapter
 * 5. Verify the URL updates
 * 
 * Validates: Property 4 (Reading Experience)
 */
test('complete reading journey', async ({ page }) => {
    // 1. Navigate to the Home page
    await page.goto('/');
    await expect(page).toHaveTitle(/BABEL/i); // Assuming title contains BABEL

    // Verify home page elements
    await expect(page.getByTestId('home-page')).toBeVisible();
    await expect(page.getByTestId('chapter-grid')).toBeVisible();

    // 2. Select a chapter (Assuming at least one chapter exists)
    // We'll click the first chapter card
    const firstChapterLink = page.locator('a[href^="/chapter/"]').first();
    await expect(firstChapterLink).toBeVisible();

    // Get the chapter ID from the href to verify navigation later
    const href = await firstChapterLink.getAttribute('href');

    // Click the chapter
    await firstChapterLink.click();

    // 3. Read content
    // Verify we are on the chapter page
    await expect(page).toHaveURL(new RegExp(href!));
    await expect(page.getByTestId('chapter-view')).toBeVisible();

    // Verify content is loaded
    await expect(page.getByTestId('chapter-content')).toBeVisible();

    // Verify at least one script block is present
    const scriptBlock = page.locator('.script-block').first();
    await expect(scriptBlock).toBeVisible();

    // 4. Navigate to the next chapter
    // Check if a "Next" button exists and is clickable
    const nextButton = page.getByTestId('nav-next');

    if (await nextButton.isVisible() && await nextButton.isEnabled()) {
        await nextButton.click();

        // 5. Verify URL updates
        // The URL should change to a different chapter ID
        await expect(page).not.toHaveURL(new RegExp(href!));
        await expect(page.getByTestId('chapter-view')).toBeVisible();
    } else {
        console.log('No next chapter available, skipping navigation test step.');
    }
});
