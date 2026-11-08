import { Fragment, useMemo, type ReactNode } from "react";
import type { Block, Entity, GlossaryHit, Tone } from "../lib/api";
import { cssColor } from "../lib/colors";
import { Avatar, cx } from "./ui";

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Matches glossary terms in text (longest first, whole words). */
export function useGlossary(hits: GlossaryHit[]) {
  return useMemo(() => {
    const byTerm = new Map<string, GlossaryHit>();
    hits.forEach((h) => h.terms.forEach((t) => byTerm.set(t.toLowerCase(), h)));
    const terms = [...byTerm.keys()].sort((a, b) => b.length - a.length);
    const re = terms.length ? new RegExp(`(?<![\\p{L}\\p{N}])(${terms.map(escapeRe).join("|")})(?![\\p{L}\\p{N}])`, "giu") : null;
    return { re, byTerm };
  }, [hits]);
}

type Gloss = ReturnType<typeof useGlossary>;

function GlossTerm({ text, hit }: { text: string; hit: GlossaryHit }) {
  return (
    <span className="group/gloss relative" tabIndex={0}>
      <span className="cursor-help underline decoration-dotted decoration-faint underline-offset-4">{text}</span>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-30 mb-2 w-64 -translate-x-1/2 rounded-lg border border-line bg-surface p-3 text-left font-sans text-[13px] not-italic leading-snug text-text opacity-0 shadow-xl transition-opacity group-hover/gloss:visible group-hover/gloss:opacity-100 group-focus/gloss:visible group-focus/gloss:opacity-100"
      >
        <span className="block font-semibold">{hit.name}</span>
        <span className="block text-[11px] uppercase tracking-wide text-faint">{hit.kind}</span>
        {hit.note && <span className="mt-1 block text-muted">{hit.note}</span>}
      </span>
    </span>
  );
}

function withGlossary(text: string, gloss?: Gloss, key = 0): ReactNode {
  if (!gloss?.re) return text;
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(gloss.re)) {
    const i = m.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    const hit = gloss.byTerm.get(m[0].toLowerCase());
    out.push(hit ? <GlossTerm key={`${key}-${i}`} text={m[0]} hit={hit} /> : m[0]);
    last = i + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}

/** *emphasis* → <em>, glossary terms → hover cards; never interprets HTML. */
export function Rich({ text, gloss }: { text: string; gloss?: Gloss }) {
  const parts = text.split(/(\*[^*\n]+\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.length > 2 && p.startsWith("*") && p.endsWith("*") ? (
          <em key={i}>{withGlossary(p.slice(1, -1), gloss, i)}</em>
        ) : (
          <Fragment key={i}>{withGlossary(p, gloss, i)}</Fragment>
        ),
      )}
    </>
  );
}

const TONE_CLASS: Partial<Record<Tone, string>> = {
  shout: "text-[1.12em] font-semibold tracking-wide",
  whisper: "text-[0.9em] italic opacity-80",
  angry: "font-medium",
};
const TONE_LABEL: Partial<Record<Tone, string>> = { whisper: "whispers", shout: "shouts", angry: "angrily", sad: "sadly", laugh: "laughing", nervous: "nervously", cold: "coldly" };

interface Props {
  blocks: Block[];
  characters: Map<number, Entity>;
  glossary?: GlossaryHit[];
  showTags: boolean;
  showAvatars: boolean;
  editing: boolean;
  onEdit: (block: Block) => void;
  onCharacter: (c: Entity) => void;
}

export function Scenario({ blocks, characters, glossary = [], showTags, showAvatars, editing, onEdit, onCharacter }: Props) {
  const gloss = useGlossary(glossary);
  const out: ReactNode[] = [];
  let prevSpeaker: string | null = null;
  let lastSide: "left" | "right" = "left";

  blocks.forEach((b, i) => {
    const key = `${b.seg[0]}-${i}`;
    const flag = editing && (b.review || b.edited);
    const wrap = (node: ReactNode, extra?: string) => (
      <div
        key={key}
        className={cx("relative", editing && "editable", extra)}
        onClick={editing ? () => onEdit(b) : undefined}
        role={editing ? "button" : undefined}
        tabIndex={editing ? 0 : undefined}
        onKeyDown={editing ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onEdit(b)) : undefined}
        aria-label={editing ? `Correct ${b.type}${b.review ? " (uncertain)" : ""}` : undefined}
        title={editing && b.why ? `${b.why} · ${Math.round(b.conf * 100)}%` : undefined}
      >
        {flag && (
          <span
            aria-hidden
            className={cx("absolute -left-4 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full", b.edited ? "bg-accent" : "bg-warn")}
          />
        )}
        {node}
      </div>
    );

    if (b.type === "dialogue" || b.type === "thought") {
      const c = b.character_id != null ? characters.get(b.character_id) : undefined;
      const name = c?.name ?? b.speaker ?? (b.type === "thought" ? "Inner voice" : "Unknown");
      const side = c?.side ?? "left";
      const who = c ? cssColor(c.color) : "var(--faint)";
      const speakerKey = `${c?.id ?? name}:${b.type}`;
      const grouped = speakerKey === prevSpeaker;
      prevSpeaker = speakerKey;
      lastSide = side;
      const right = side === "right";
      const toneLabel = b.tone ? TONE_LABEL[b.tone] : undefined;
      out.push(
        wrap(
          <div className={cx("flex gap-3", right && "flex-row-reverse", grouped ? "mt-1.5" : "mt-6")} style={{ ["--who" as string]: who }}>
            {showAvatars && (
              <div className="w-9 shrink-0">
                {!grouped &&
                  (c ? (
                    <button onClick={(e) => (e.stopPropagation(), onCharacter(c))} aria-label={`About ${name}`} tabIndex={editing ? -1 : 0}>
                      <Avatar character={c} />
                    </button>
                  ) : (
                    <Avatar name={name} />
                  ))}
              </div>
            )}
            <div className={cx("flex min-w-0 max-w-[85%] flex-col", right ? "items-end" : "items-start")}>
              {!grouped && (
                <button
                  className={cx("mb-1 font-sans text-[0.72em] font-semibold uppercase tracking-wider", c ? "hover:underline" : "cursor-default")}
                  style={{ color: who }}
                  onClick={c && !editing ? (e) => (e.stopPropagation(), onCharacter(c)) : undefined}
                  tabIndex={c && !editing ? 0 : -1}
                >
                  {name}
                  {(b.type === "thought" || toneLabel) && (
                    <span className="ml-1.5 font-normal normal-case tracking-normal opacity-70">{b.type === "thought" ? "thinks" : toneLabel}</span>
                  )}
                </button>
              )}
              <div
                className={cx(
                  "bubble rounded-2xl px-4 py-2",
                  b.type === "thought" && "thought italic text-muted",
                  right ? "rounded-tr-md" : "rounded-tl-md",
                  b.tone && TONE_CLASS[b.tone],
                  b.tone === "shout" && "bubble-shout",
                )}
              >
                <Rich text={b.text} gloss={gloss} />
              </div>
            </div>
          </div>,
        ),
      );
      return;
    }

    if (b.type === "tag") {
      if (!showTags && !editing) return;
      out.push(
        wrap(
          <div className={cx("mt-1 font-sans text-[0.78em] italic text-faint", showAvatars && (lastSide === "right" ? "pr-12 text-right" : "pl-12"), !showAvatars && lastSide === "right" && "text-right")}>
            <Rich text={b.text} />
          </div>,
        ),
      );
      return;
    }

    if (b.type === "action") {
      const c = b.character_id != null ? characters.get(b.character_id) : undefined;
      const side = c?.side ?? lastSide;
      out.push(
        wrap(
          <p
            className={cx(
              "prose mt-4 border-l-2 pl-3 italic text-muted",
              showAvatars && side === "left" && "ml-12",
              side === "right" && "ml-auto max-w-[85%] border-l-0 border-r-2 pl-0 pr-3 text-right",
              showAvatars && side === "right" && "mr-12",
            )}
            style={{ borderColor: c ? cssColor(c.color) : "var(--line)" }}
          >
            <Rich text={b.text} gloss={gloss} />
          </p>,
        ),
      );
      prevSpeaker = null;
      return;
    }

    prevSpeaker = null;
    if (b.type === "system") {
      out.push(
        wrap(
          <div className="system-window mx-auto my-7 max-w-[92%] rounded-lg px-4 py-3 font-mono text-[0.85em] leading-relaxed">
            <Rich text={b.text} />
          </div>,
        ),
      );
    } else if (b.type === "sfx") {
      out.push(wrap(<div className="sfx my-7 text-center font-sans text-[1.35em] font-black uppercase text-accent">{b.text}</div>));
    } else if (b.type === "break") {
      out.push(wrap(<div className="my-10 text-center tracking-[0.8em] text-faint" aria-label="scene break">◆◆◆</div>));
    } else {
      out.push(
        wrap(
          <p className="prose mt-6 text-text/90">
            <Rich text={b.text} gloss={gloss} />
          </p>,
        ),
      );
    }
  });
  return <div className="scenario">{out}</div>;
}
