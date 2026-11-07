import { expect, test } from "@playwright/test";
import path from "node:path";

// Runs against a live `babel serve` (see playwright.config.ts) with an empty data dir.
test("import a book, transform offline, read and correct a line", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Your library is empty")).toBeVisible();
  const fixture = path.resolve(import.meta.dirname, "../../tests/fixtures/sample_chapter.txt");
  await page.locator('input[type="file"]').setInputFiles(fixture);
  await expect(page.getByRole("heading", { name: "sample chapter" })).toBeVisible();

  await page.getByRole("button", { name: /Options/ }).click();
  await page.getByRole("combobox").selectOption("heuristic");
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByText("Finished")).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: /Start reading|Continue reading/ }).click();
  await expect(page.getByText("You're late,")).toBeVisible();
  await expect(page.getByText("[Quest Updated: Find the missing courier before midnight.]")).toBeVisible();

  await page.keyboard.press("e");
  await page.getByText("Then we wait.", { exact: true }).click();
  await page.getByLabel("Speaker").fill("Old Harrow");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: /Old Harrow/i }).first()).toBeVisible();
});
