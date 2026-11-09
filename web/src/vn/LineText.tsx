import { memo, useEffect, useMemo, useRef } from "react";
import { cssColor } from "../lib/colors";
import { blip } from "./sound";

/**
 * A line of the visual novel, coloured and typed.
 *
 * Colour: every cast member's name takes their colour, *emphasis* is gilded, and quoted speech inside
 * narration is lifted. Typing is pure CSS — each character fades in on its own delay — so the stage
 * never re-renders while a line types (that was what made everything stutter).
 */

export interface Seg {
  text: string;
  kind: "plain" | "name" | "em" | "quote" | "mark";
  color?: string;
}

export interface Named {
  name: string;
  color: string | null;
  aliases?: string[];
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const STOP = new Set(["the", "mr", "mrs", "miss", "sir", "lady", "lord", "old", "young", "man", "woman", "girl", "boy"]);

/** Names to colour: full names and (unambiguous) first names of everyone in the chapter's cast. */
export function nameMatcher(cast: Named[]): { rx: RegExp | null; color: Map<string, string> } {
  const color = new Map<string, string>();
  const firsts = new Map<string, number>();
  for (const c of cast) {
    const first = c.name.split(/\s+/)[0];
    firsts.set(first.toLowerCase(), (firsts.get(first.toLowerCase()) ?? 0) + 1);
  }
  for (const c of cast) {
    if (!c.name || /^[a-z]/.test(c.name)) continue; // "mobile hawkers", "woman": descriptions, not names
    const col = cssColor(c.color ?? "slot:0");
    color.set(c.name.toLowerCase(), col);
    const parts = c.name.split(/\s+/);
    if (parts.length > 1) {
      const first = parts[0];
      if (first.length >= 3 && !STOP.has(first.toLowerCase()) && firsts.get(first.toLowerCase()) === 1) color.set(first.toLowerCase(), col);
      const last = parts[parts.length - 1];
      if (last.length >= 4 && !STOP.has(last.toLowerCase()) && !color.has(last.toLowerCase())) color.set(last.toLowerCase(), col);
    }
    for (const al of c.aliases ?? []) if (!STOP.has(al.toLowerCase()) && !color.has(al.toLowerCase())) color.set(al.toLowerCase(), col);
  }
  const keys = [...color.keys()].sort((a, b) => b.length - a.length);
  return { rx: keys.length ? new RegExp(`(?<![\\p{L}\\p{N}])(${keys.map(esc).join("|")})(?![\\p{L}\\p{N}])`, "giu") : null, color };
}

export function colorize(text: string, names: ReturnType<typeof nameMatcher>, opts: { quotes: boolean; marks: boolean }): Seg[] {
  const out: Seg[] = [];
  const pushNames = (t: string, kind: Seg["kind"]) => {
    if (!names.rx || !t) {
      if (t) out.push({ text: t, kind });
      return;
    }
    let last = 0;
    for (const m of t.matchAll(names.rx)) {
      if (m.index! > last) out.push({ text: t.slice(last, m.index), kind });
      out.push({ text: m[0], kind: "name", color: names.color.get(m[0].toLowerCase()) });
      last = m.index! + m[0].length;
    }
    if (last < t.length) out.push({ text: t.slice(last), kind });
  };
  const plain = (t: string) => {
    if (!opts.quotes) return pushNames(t, "plain");
    // lift "speech" inside narration
    const parts = t.split(/([“"][^”"]{1,400}[”"])/g);
    parts.forEach((p, i) => pushNames(p, i % 2 ? "quote" : "plain"));
  };
  const open = opts.marks && !/^[“"'‘]/.test(text);
  if (open) out.push({ text: "“", kind: "mark" });
  text.split(/(\*[^*\n]+\*)/g).forEach((p) => {
    if (p.length > 2 && p.startsWith("*") && p.endsWith("*")) out.push({ text: p.slice(1, -1), kind: "em" });
    else plain(p);
  });
  if (open) out.push({ text: "”", kind: "mark" });
  return out;
}

const SEG_CLASS: Record<Seg["kind"], string> = {
  plain: "",
  name: "font-semibold [text-shadow:0_0_14px_currentColor]",
  em: "italic text-[#f3d595]",
  quote: "text-[#fbf6ee]",
  mark: "text-[#dfb56f]",
};

/** Milliseconds per character for a text speed (chars/second); 0 = instant. */
export const msPerChar = (speed: number) => (speed <= 0 ? 0 : 1000 / speed);

interface Props {
  segs: Seg[];
  speed: number; // chars per second, 0 = instant
  done: boolean; // show everything now
  onDone: () => void;
  voice?: number | null; // blip seed (character id); null = no blips
  tone?: string | null;
  className?: string;
}

export const LineText = memo(function LineText({ segs, speed, done, onDone, voice, tone, className }: Props) {
  const per = msPerChar(speed);
  const total = useMemo(() => segs.reduce((n, s) => n + s.text.length, 0), [segs]);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;

  // tell the player when the last character has landed
  useEffect(() => {
    if (done || per === 0) {
      if (!done) doneRef.current();
      return;
    }
    const t = setTimeout(() => doneRef.current(), total * per + 120);
    return () => clearTimeout(t);
  }, [segs, per, total, done]);

  // voice blips while typing (every few characters, skipping spaces)
  useEffect(() => {
    if (done || per === 0 || voice == null) return;
    const flat = segs.map((s) => s.text).join("");
    const start = performance.now();
    let k = 0;
    const t = setInterval(() => {
      const at = Math.floor((performance.now() - start) / per);
      if (at >= flat.length) return clearInterval(t);
      if (at >= k) {
        if (/[\p{L}\p{N}]/u.test(flat[at] ?? "")) blip(voice, tone);
        k = at + 3;
      }
    }, Math.max(30, per));
    return () => clearInterval(t);
  }, [segs, per, done, voice, tone]);

  let i = 0;
  return (
    <span className={(done || per === 0 ? "vn-instant " : "") + (className ?? "")}>
      {segs.map((s, n) => (
        <span key={n} className={SEG_CLASS[s.kind]} style={s.color ? { color: s.color } : undefined}>
          {[...s.text].map((ch) => {
            const d = i++ * per;
            return (
              <span key={i} className="vn-ch" style={{ animationDelay: `${d}ms` }}>
                {ch}
              </span>
            );
          })}
        </span>
      ))}
    </span>
  );
});

/** Coloured text without typing (the backlog). */
export function Colored({ segs }: { segs: Seg[] }) {
  return (
    <>
      {segs.map((s, n) => (
        <span key={n} className={SEG_CLASS[s.kind]} style={s.color ? { color: s.color } : undefined}>
          {s.text}
        </span>
      ))}
    </>
  );
}
