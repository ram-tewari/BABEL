import { cssColor, initials, titleHue } from "./colors";

test("palette slots map to theme variables", () => {
  expect(cssColor("slot:3")).toBe("var(--slot-3)");
  expect(cssColor("slot:15")).toBe("var(--slot-3)");
  expect(cssColor("#ff0000")).toBe("#ff0000");
  expect(cssColor("javascript:alert(1)")).toBe("var(--muted)");
  expect(cssColor(null)).toBe("var(--muted)");
});

test("initials", () => {
  expect(initials("Klein Moretti")).toBe("KM");
  expect(initials("Audrey")).toBe("AU");
  expect(initials("周明瑞")).toBe("周");
  expect(initials("")).toBe("?");
});

test("title hue is stable", () => {
  expect(titleHue("Lord of Mysteries")).toBe(titleHue("Lord of Mysteries"));
});
