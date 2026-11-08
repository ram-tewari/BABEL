import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Search } from "lucide-react";
import { cx } from "./ui";

export interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon?: ReactNode;
  run: () => void;
}

/** Ctrl+K palette: jump to chapters, characters and actions. */
export function CommandMenu({ open, onClose, commands }: { open: boolean; onClose: () => void; commands: Command[] }) {
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (open) {
      setQ("");
      setSel(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return commands.filter((c) => c.group !== "Chapters").slice(0, 40);
    const num = Number(needle);
    return commands
      .map((c) => {
        const l = c.label.toLowerCase();
        const score = l === needle ? 0 : l.startsWith(needle) ? 1 : l.includes(needle) ? 2 : (c.hint ?? "").toLowerCase().includes(needle) ? 3 : 9;
        const numScore = Number.isFinite(num) && c.group === "Chapters" && c.hint === `#${num}` ? -1 : score;
        return { c, s: numScore };
      })
      .filter((x) => x.s < 9)
      .sort((a, b) => a.s - b.s)
      .slice(0, 40)
      .map((x) => x.c);
  }, [commands, q]);

  useEffect(() => setSel(0), [q]);
  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" });
  }, [sel]);

  if (!open) return null;
  const choose = (c?: Command) => {
    if (!c) return;
    onClose();
    c.run();
  };
  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[12vh] backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-label="Command menu" className="w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Search size={16} className="text-faint" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Chapter, character or action…"
            className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-faint focus-visible:outline-none"
            role="combobox"
            aria-expanded
            aria-controls="cmd-list"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") (e.preventDefault(), setSel((s) => Math.min(s + 1, results.length - 1)));
              if (e.key === "ArrowUp") (e.preventDefault(), setSel((s) => Math.max(s - 1, 0)));
              if (e.key === "Enter") (e.preventDefault(), choose(results[sel]));
              if (e.key === "Escape") onClose();
            }}
          />
          <kbd className="rounded border border-line px-1.5 text-[10px] text-faint">esc</kbd>
        </div>
        <ul id="cmd-list" ref={listRef} role="listbox" className="max-h-[50vh] overflow-y-auto py-2">
          {results.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted">No matches</li>}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <li key={c.id}>
                {header && <div className="px-4 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-faint">{header}</div>}
                <button
                  role="option"
                  aria-selected={i === sel}
                  onMouseMove={() => setSel(i)}
                  onClick={() => choose(c)}
                  className={cx("flex w-full items-center gap-3 px-4 py-2 text-left text-sm", i === sel && "bg-raised")}
                >
                  <span className="text-muted">{c.icon}</span>
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  {c.hint && <span className="shrink-0 text-xs text-faint">{c.hint}</span>}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
