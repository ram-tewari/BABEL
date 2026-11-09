/** Character colors: "slot:N" maps to a theme-aware palette variable; "#hex" is used as-is. */
export const SLOT_COUNT = 12;

export function cssColor(color: string | null | undefined): string {
  if (!color) return "var(--muted)";
  if (color.startsWith("slot:")) {
    const n = Number(color.slice(5));
    return `var(--slot-${Number.isFinite(n) ? n % SLOT_COUNT : 0})`;
  }
  return /^#[0-9a-f]{3,8}$/i.test(color) ? color : "var(--muted)";
}

export function initials(name: string): string {
  const parts = name
    .replace(/[^\p{L}\p{N}\s'-]/gu, "")
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "?";
  // CJK names: first character only
  if (/^[぀-ヿ㐀-鿿가-힯]/.test(parts[0])) return parts[0][0];
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Stable hue for books without a cover. */
export function titleHue(title: string): string {
  let h = 0;
  for (const ch of title) h = (h * 31 + ch.codePointAt(0)!) >>> 0;
  return `var(--slot-${h % SLOT_COUNT})`;
}
