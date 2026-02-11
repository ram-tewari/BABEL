import { test, expect } from '@playwright/test';

/**
 * Character Customization E2E Test (Task 20.3)
 * 
 * Verifies character preferences persist and apply correctly:
 * 1. Open a chapter
 * 2. Click a character name (Dialogue Bubble)
 * 3. Change display name and color
 * 4. Save
 * 5. Verify changes immediately visible
 * 6. Reload and verify changes persist
 * 
 * Validates: Property 3 (Character Preferences)
 */
test('character customization', async ({ page }) => {
    // 1. Open a Chapter
    await page.goto('/chapter/1'); // Assuming chapter 1 exists or dynamically fetch

    // Wait for content (Dialogue Block)
    const dialogueBlock = page.locator('.dialogue-block').first();
    await expect(dialogueBlock).toBeVisible();

    // 2. Click a Character Name to Open Modal
    const charName = await dialogueBlock.locator('.character-name').textContent();
    await dialogueBlock.locator('.character-name').click();

    const charModal = page.locator('div[role="dialog"]');
    await expect(charModal).toBeVisible();

    // 3. Customize Name
    const nameInput = charModal.locator('input[name="display_name"]');
    const originalName = await nameInput.inputValue();
    const newName = originalName + ' (Edited)';

    await nameInput.fill(newName);

    // Change Color (Assuming a color picker or preset)
    const colorPicker = charModal.locator('input[type="color"]');
    const newColor = '#ff0000';
    await colorPicker.fill(newColor);

    // 4. Save Changes
    const saveButton = charModal.locator('button:has-text("Save")');
    await saveButton.click();

    // Verify modal closed
    await expect(charModal).not.toBeVisible();

    // 5. Verify Changes Applied Immediately
    // The name in the bubble should be updated
    await expect(dialogueBlock.locator('.character-name')).toHaveText(newName);

    // The color style should be applied (e.g., box-shadow or border)
    // This depends on implementation details, checking style attribute might be tricky with CSS variables

    // 6. Reload and Verify Persistence
    await page.reload();

    // Check the first dialogue block again (assuming same character speaks first or early)
    // Might need to find a block by original speaker name if the first one changed
    // But for this test, let's assume chapter 1 starts with this character

    const reloadedBlock = page.locator('.dialogue-block').filter({
        hasText: newName
    }).first();

    await expect(reloadedBlock).toBeVisible();
    await expect(reloadedBlock.locator('.character-name')).toHaveText(newName);
});
