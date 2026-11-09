import { useEffect, useMemo, useRef, useState } from "react";
import { Check, X } from "lucide-react";
import type { ChapterRow } from "../lib/api";
import { IconButton, cx, inputCls } from "./ui";

/** Chapter list for the reader (Ctrl+B). Shows read marks, transform status and the chapter in view. */
export function ChapterSidebar({
  open,
  chapters,
  current,
  title,
  onPick,
  onClose,
}: {
  open: boolean;
  chapters: ChapterRow[];
  current: number | null;
  title: string;
  onPick: (id: number) => void;
  onClose: () => void;
}) {
  const [q, setQ] = useState("");
  const listRef = useRef<HTMLOListElement>(null);
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return needle ? chapters.filter((c) => c.title.toLowerCase().includes(needle) || String(c.idx + 1) === needle) : chapters;
  }, [chapters, q]);

  useEffect(() => {
    if (!open || current == null) return;
    listRef.current?.querySelector(`[data-chapter-id="${current}"]`)?.scrollIntoView({ block: "center" });
  }, [open, current]);

  return (
    <>
      <div className={cx("fixed inset-0 z-30 bg-black/40 transition-opacity lg:hidden", open ? "opacity-100" : "pointer-events-none opacity-0")} onClick={onClose} aria-hidden />
      <aside
        aria-label="Chapters"
        aria-hidden={!open}
        className={cx(
          "fixed bottom-0 left-0 top-14 z-40 flex w-80 max-w-[85vw] flex-col border-r border-line bg-surface transition-transform",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center gap-2 border-b border-line p-3">
          <div className="min-w-0 flex-1 truncate text-sm font-medium">{title}</div>
          <IconButton label="Close chapters (Ctrl+B)" onClick={onClose}>
            <X size={16} />
          </IconButton>
        </div>
        <div className="p-3">
          <input className={cx(inputCls, "h-9")} placeholder="Filter chapters…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Filter chapters" tabIndex={open ? 0 : -1} />
        </div>
        <ol ref={listRef} className="flex-1 overflow-y-auto pb-6">
          {rows.map((c) => (
            <li key={c.id} style={{ contentVisibility: "auto", containIntrinsicSize: "0 40px" }}>
              <button
                data-chapter-id={c.id}
                tabIndex={open ? 0 : -1}
                onClick={() => onPick(c.id)}
                aria-current={c.id === current ? "true" : undefined}
                className={cx(
                  "flex h-10 w-full items-center gap-2 px-3 text-left text-[13px] hover:bg-raised",
                  c.id === current && "bg-accent/10 font-medium text-text",
                  c.id !== current && (c.is_read ? "text-faint" : "text-muted"),
                )}
              >
                <span className="w-10 shrink-0 text-right tabular-nums text-faint">{c.idx + 1}</span>
                <span className="min-w-0 flex-1 truncate">{c.title}</span>
                {c.is_read && <Check size={13} className="shrink-0 text-ok" aria-label="read" />}
                {c.status !== "done" && <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", c.status === "failed" ? "bg-danger" : "bg-faint/60")} title={c.status} />}
              </button>
            </li>
          ))}
        </ol>
      </aside>
    </>
  );
}
