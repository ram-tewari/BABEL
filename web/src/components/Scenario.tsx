import { Fragment, type ReactNode } from "react";
import type { Block, Character } from "../lib/api";
import { cssColor } from "../lib/colors";
import { Avatar, cx } from "./ui";

/** *emphasis* → <em>, everything else as text (no HTML injection). */
export function Rich({ text }: { text: string }) {
  const parts = text.split(/(\*[^*\n]+\*)/g);
  return (
    <>
      {parts.map((p, i) =>
        p.length > 2 && p.startsWith("*") && p.endsWith("*") ? <em key={i}>{p.slice(1, -1)}</em> : <Fragment key={i}>{p}</Fragment>,
      )}
    </>
  );
}

interface Props {
  blocks: Block[];
  characters: Map<number, Character>;
  showTags: boolean;
  showAvatars: boolean;
  editing: boolean;
  onEdit: (block: Block) => void;
  onCharacter: (c: Character) => void;
}

export function Scenario({ blocks, characters, showTags, showAvatars, editing, onEdit, onCharacter }: Props) {
  const out: ReactNode[] = [];
  let prevSpeaker: string | null = null; // key of previous bubble's speaker, for grouping
  let lastSide: "left" | "right" = "left";

  blocks.forEach((b, i) => {
    const key = `${b.seg[0]}-${i}`;
    const wrap = (node: ReactNode, extra?: string) => (
      <div
        key={key}
        className={cx(editing && "editable", extra)}
        onClick={editing ? () => onEdit(b) : undefined}
        role={editing ? "button" : undefined}
        tabIndex={editing ? 0 : undefined}
        onKeyDown={editing ? (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onEdit(b)) : undefined}
        aria-label={editing ? `Edit ${b.type} block` : undefined}
      >
        {node}
        {b.edited && editing && <span className="sr-only">(edited)</span>}
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
      out.push(
        wrap(
          <div className={cx("flex gap-3", right && "flex-row-reverse", grouped ? "mt-1.5" : "mt-6")} style={{ ["--who" as string]: who }}>
            {showAvatars && <div className="w-9 shrink-0">{!grouped && (c ? <button onClick={(e) => (e.stopPropagation(), onCharacter(c))} aria-label={`About ${name}`}><Avatar character={c} /></button> : <Avatar name={name} />)}</div>}
            <div className={cx("flex min-w-0 max-w-[85%] flex-col", right ? "items-end" : "items-start")}>
              {!grouped && (
                <button
                  className={cx("mb-1 font-sans text-[0.72em] font-semibold uppercase tracking-wider", c ? "hover:underline" : "cursor-default")}
                  style={{ color: who }}
                  onClick={c && !editing ? (e) => (e.stopPropagation(), onCharacter(c)) : undefined}
                  tabIndex={c && !editing ? 0 : -1}
                >
                  {name}
                  {b.type === "thought" && <span className="ml-1.5 font-normal normal-case tracking-normal opacity-70">thinks</span>}
                </button>
              )}
              <div
                className={cx(
                  "bubble rounded-2xl px-4 py-2",
                  b.type === "thought" && "thought italic text-muted",
                  right ? "rounded-tr-md" : "rounded-tl-md",
                  b.edited && editing && "ring-1 ring-accent/60",
                )}
              >
                <Rich text={b.text} />
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
      out.push(
        wrap(<div className="sfx my-7 text-center font-sans text-[1.35em] font-black uppercase text-accent">{b.text.replace(/^\*|\*$/g, "")}</div>),
      );
    } else if (b.type === "break") {
      out.push(wrap(<div className="my-10 text-center tracking-[0.8em] text-faint" aria-label="scene break">◆◆◆</div>));
    } else {
      out.push(
        wrap(
          <p className={cx("prose mt-6 text-text/90", b.edited && editing && "ring-1 ring-accent/60")}>
            <Rich text={b.text} />
          </p>,
        ),
      );
    }
  });
  return <div className="scenario">{out}</div>;
}
