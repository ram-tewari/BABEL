import { expect, test } from "@playwright/test";
import path from "node:path";

// Runs against a live `babel serve` with an empty, model-free library (see playwright.config.ts).
test("import → transform → read → correct → review", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Every novel, staged." })).toBeVisible();
  const fixture = path.resolve(import.meta.dirname, "../../tests/fixtures/sample_chapter.txt");
  await page.locator('input[type="file"]').setInputFiles(fixture);
  await expect(page.getByRole("heading", { name: "sample chapter" })).toBeVisible();

  await page.getByRole("button", { name: /Options/ }).click();
  await page.getByText("Rules + memory only").click();
  await page.getByRole("button", { name: "Start", exact: true }).click();
  await expect(page.getByText("Finished")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Who decided the lines")).toBeVisible();

  await page.getByRole("link", { name: /^Read$|Continue reading/ }).click();
  await expect(page.getByText("You're late,")).toBeVisible();
  await expect(page.getByText("[Quest Updated: Find the missing courier before midnight.]")).toBeVisible();
  await expect(page.getByText("CRASH!")).toBeVisible();

  // correct a line: suggestions, then a new name
  await page.keyboard.press("e");
  await page.getByText("Then we wait.", { exact: true }).click();
  await expect(page.getByText(/Decided by/)).toBeVisible();
  await page.getByRole("combobox", { name: "Speaker" }).fill("Old Harrow");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("button", { name: /Old Harrow/i }).first()).toBeVisible();
  await page.keyboard.press("e");

  // sidebar + command menu
  await page.keyboard.press("Control+b");
  await expect(page.getByRole("complementary", { name: "Chapters" })).toBeVisible();
  await page.keyboard.press("Control+b");
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("tobin");
  await expect(page.getByRole("option", { name: /Tobin/ })).toBeVisible();
  await page.keyboard.press("Escape");

  // visual novel: works without image models (painted sets, silhouettes); curtains open, lines advance
  await page.getByRole("button", { name: "Read as a visual novel" }).click();
  await expect(page).toHaveURL(/\/vn\/\d+/);
  await expect(page.getByRole("button", { name: /Auto-play/ })).toBeVisible();
  for (let k = 0; k < 4; k++) await page.keyboard.press("ArrowRight");
  await page.keyboard.press("l");
  await expect(page.getByRole("dialog", { name: "Backlog" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await expect(page).toHaveURL(/\/read\/\d+/);

  // the title screen: Begin opens the curtains onto the first chapter
  await page.goto(page.url().replace(/\/read\/\d+/, "/"));
  await page.getByRole("link", { name: /^Play sample chapter/ }).first().click();
  await expect(page.getByRole("heading", { name: "sample chapter" })).toBeVisible();
  await page.getByRole("button", { name: /Begin/ }).click();
  await expect(page).toHaveURL(/\/vn\/\d+/);
  await page.goto(page.url().replace(/\/vn\/\d+/, "/"));

  // the correction shows up in the review tab's log
  await page.getByRole("link", { name: /Programme/ }).first().click();
  await page.getByRole("link", { name: /^Review/ }).click();
  await expect(page.getByRole("cell", { name: /Old Harrow/ })).toBeVisible();

  // the design tab: readiness + a clear note that the image models aren't installed here
  await page.getByRole("link", { name: /^Design/ }).click();
  await expect(page.getByRole("heading", { name: "Visual novel" })).toBeVisible();
  await expect(page.getByText("Image models not installed")).toBeVisible();
  await expect(page.getByRole("switch", { name: "Design automatically" })).toBeVisible();
});
