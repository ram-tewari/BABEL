import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, FileText, MessagesSquare, Pencil, RefreshCw, Sparkles, Type } from "lucide-react";
import { api, isActive, type Block, type BlockType, type Character } from "../lib/api";
import { setPrefs, usePrefs, WIDTHS, type Prefs } from "../lib/prefs";
import { Button, ErrorNote, Field, IconButton, Modal, Spinner, buttonCls, cx } from "../components/ui";
import { Scenario } from "../components/Scenario";
import { BlockEditor } from "../components/BlockEditor";
import { CharacterPanel, useCast } from "../components/CastEditor";

export function Reader() {
  const { chapterId } = useParams();
  const id = Number(chapterId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const prefs = usePrefs();
  const [editing, setEditing] = useState(false);
  const [editBlock, setEditBlock] = useState<Block | null>(null);
  const [charOpen, setCharOpen] = useState<Character | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [watchJob, setWatchJob] = useState(false);

  const chapter = useQuery({ queryKey: ["chapter", id], queryFn: () => api.chapter(id) });
  const ch = chapter.data;
  const novel = useQuery({
    queryKey: ["novel", ch?.novel_id],
    queryFn: () => api.novel(ch!.novel_id),
    enabled: !!ch,
    refetchInterval: (q) => (watchJob && isActive(q.state.data?.job) ? 2000 : false),
  });
  const cast = useCast(ch?.novel_id ?? 0);
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 60_000 });
  const source = useQuery({ queryKey: ["source", id], queryFn: () => api.source(id), enabled: prefs.view === "original" });

  // when a re-transform of this chapter finishes, reload it
  useEffect(() => {
    if (watchJob && novel.data && !isActive(novel.data.job)) {
      setWatchJob(false);
      qc.invalidateQueries({ queryKey: ["chapter", id] });
      qc.invalidateQueries({ queryKey: ["cast", ch?.novel_id] });
    }
  }, [watchJob, novel.data, id, ch?.novel_id, qc]);

  // prefetch the next chapter
  useEffect(() => {
    if (ch?.next_id) qc.prefetchQuery({ queryKey: ["chapter", ch.next_id], queryFn: () => api.chapter(ch.next_id!) });
  }, [ch?.next_id, qc]);

  // keyboard: ← → for chapters, e for edit mode
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, dialog[open]") || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "ArrowRight" && ch?.next_id) navigate(`/read/${ch.next_id}`);
      if (e.key === "ArrowLeft" && ch?.prev_id) navigate(`/read/${ch.prev_id}`);
      if (e.key === "e") setEditing((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ch?.next_id, ch?.prev_id, navigate]);

  useReadingProgress(ch?.novel_id, id, novel.data?.progress, !!ch);

  const characters = useMemo(() => {
    const m = new Map<number, Character>();
    ch?.characters.forEach((c) => m.set(c.id, c));
    return m;
  }, [ch]);

  const edit = useMutation({
    mutationFn: (a: { type: BlockType; speaker: string | null }) => api.edit(id, editBlock!.seg, a.type, a.speaker),
    onSuccess: (view) => {
      qc.setQueryData(["chapter", id], view);
      qc.invalidateQueries({ queryKey: ["cast", view.novel_id] });
      setEditBlock(null);
    },
  });
  const revert = useMutation({
    mutationFn: () => api.clearEdits(id, editBlock!.seg),
    onSuccess: (view) => {
      qc.setQueryData(["chapter", id], view);
      setEditBlock(null);
    },
  });
  const retransform = useMutation({
    mutationFn: (mode: "auto" | "heuristic") => api.retransform(id, mode),
    onSuccess: () => {
      setWatchJob(true);
      qc.invalidateQueries({ queryKey: ["novel", ch?.novel_id] });
    },
  });

  const width = WIDTHS[prefs.width];
  const llm = !!status.data?.llm;
  const working = retransform.isPending || (watchJob && isActive(novel.data?.job));

  return (
    <div className="min-h-dvh" style={{ ["--reader-size" as string]: `${prefs.fontSize}px` }}>
      <header className="sticky top-0 z-20 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex h-14 items-center gap-1 px-2 sm:px-4" style={{ maxWidth: `calc(${width} + 8rem)` }}>
          <Link to={ch ? `/novel/${ch.novel_id}` : "/"} className="inline-flex h-9 items-center gap-1 rounded-lg px-2 text-sm text-muted hover:bg-raised hover:text-text">
            <ArrowLeft size={16} />
            <span className="hidden max-w-40 truncate sm:inline">{novel.data?.title ?? "Back"}</span>
          </Link>
          <div className="min-w-0 flex-1 truncate px-2 text-center text-sm font-medium">{ch?.title}</div>
          <IconButton label={prefs.view === "scenario" ? "Show original text" : "Show scenario"} onClick={() => setPrefs({ view: prefs.view === "scenario" ? "original" : "scenario" })}>
            {prefs.view === "scenario" ? <FileText size={18} /> : <MessagesSquare size={18} />}
          </IconButton>
          <IconButton label={editing ? "Stop correcting (e)" : "Correct lines (e)"} onClick={() => setEditing(!editing)} className={cx(editing && "bg-accent/15 text-accent")} aria-pressed={editing}>
            <Pencil size={17} />
          </IconButton>
          <IconButton label="Reading settings" onClick={() => setSettingsOpen(true)}>
            <Type size={18} />
          </IconButton>
        </div>
      </header>

      <main className="mx-auto px-4 pb-32 pt-8" style={{ maxWidth: width }}>
        {chapter.isLoading ? (
          <div className="flex justify-center py-24">
            <Spinner size={28} />
          </div>
        ) : chapter.error || !ch ? (
          <ErrorNote error={chapter.error ?? "Chapter not found"} />
        ) : (
          <>
            <div className="mb-8 text-center">
              <div className="text-xs font-medium uppercase tracking-[0.2em] text-faint">
                Chapter {ch.idx + 1}
                {novel.data && ` of ${novel.data.chapter_count.toLocaleString()}`}
              </div>
              <h1 className="mt-2 font-serif text-2xl font-semibold leading-snug sm:text-3xl">{ch.title}</h1>
            </div>

            <StatusBanner
              method={ch.method}
              status={ch.status}
              error={ch.error}
              model={ch.model}
              llm={llm}
              working={!!working}
              onTransform={(mode) => retransform.mutate(mode)}
            />
            {editing && (
              <div className="mb-6 rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 text-center text-sm">
                Correction mode — click any line to fix its type or speaker. Corrections survive re-transforms.
              </div>
            )}

            {prefs.view === "original" ? (
              source.isLoading ? (
                <Spinner />
              ) : (
                <div className="scenario">
                  {source.data?.text.split(/\n+/).map((p, i) => (
                    <p key={i} className="prose mt-5">
                      {p}
                    </p>
                  ))}
                </div>
              )
            ) : (
              <Scenario
                blocks={ch.blocks}
                characters={characters}
                showTags={prefs.showTags}
                showAvatars={prefs.showAvatars}
                editing={editing}
                onEdit={setEditBlock}
                onCharacter={setCharOpen}
              />
            )}

            <nav className="mt-16 flex items-center justify-between gap-3 border-t border-line pt-8" aria-label="Chapter navigation">
              {ch.prev_id ? (
                <Link to={`/read/${ch.prev_id}`} className={buttonCls("ghost")}>
                  <ChevronLeft size={16} /> Previous
                </Link>
              ) : (
                <span />
              )}
              {ch.next_id ? (
                <Link to={`/read/${ch.next_id}`} className={buttonCls("primary")}>
                  Next chapter <ChevronRight size={16} />
                </Link>
              ) : (
                <span className="text-sm text-muted">End of the book</span>
              )}
            </nav>
          </>
        )}
      </main>

      <BlockEditor
        block={editBlock}
        cast={cast.data ?? []}
        onClose={() => setEditBlock(null)}
        onSave={(type, speaker) => edit.mutate({ type, speaker })}
        onRevert={() => revert.mutate()}
        pending={edit.isPending || revert.isPending}
      />
      <Modal open={!!charOpen} onClose={() => setCharOpen(null)} title={charOpen?.name ?? ""}>
        {charOpen && ch && (
          <>
            {charOpen.note && <p className="mb-4 text-sm text-muted">{charOpen.note}</p>}
            <CharacterPanel
              key={charOpen.id}
              character={cast.data?.find((c) => c.id === charOpen.id) ?? charOpen}
              novelId={ch.novel_id}
              cast={cast.data ?? []}
              onDone={() => setCharOpen(null)}
            />
          </>
        )}
      </Modal>
      <ReaderSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} prefs={prefs} />
    </div>
  );
}

function StatusBanner({
  method,
  status,
  error,
  model,
  llm,
  working,
  onTransform,
}: {
  method: string;
  status: string;
  error: string | null;
  model: string | null;
  llm: boolean;
  working: boolean;
  onTransform: (mode: "auto" | "heuristic") => void;
}) {
  if (working) {
    return (
      <div className="mb-6 flex items-center justify-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-muted">
        <Spinner size={14} /> Transforming this chapter…
      </div>
    );
  }
  if (status === "failed") {
    return (
      <div className="mb-6 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
        <div className="text-danger">The last transform failed: {error}</div>
        <Button size="sm" variant="ghost" className="mt-1" onClick={() => onTransform("auto")}>
          <RefreshCw size={14} /> Try again
        </Button>
      </div>
    );
  }
  if (method === "preview" || method === "heuristic" || method === "mixed") {
    const text =
      method === "preview"
        ? "Not transformed yet — this is an instant offline preview."
        : method === "mixed"
          ? "Parts of this chapter fell back to the offline labeler."
          : "Labeled by the offline heuristic.";
    return (
      <div className="mb-6 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-lg border border-line bg-surface px-3 py-2 text-center text-sm text-muted">
        <span>{text}</span>
        {llm ? (
          <button className="inline-flex items-center gap-1 font-medium text-accent hover:underline" onClick={() => onTransform("auto")}>
            <Sparkles size={14} /> Transform with LLM
          </button>
        ) : method === "preview" ? (
          <button className="inline-flex items-center gap-1 font-medium text-accent hover:underline" onClick={() => onTransform("heuristic")}>
            Save offline labels
          </button>
        ) : null}
      </div>
    );
  }
  return model ? <div className="mb-6 text-center text-[11px] text-faint">labeled by {model}</div> : null;
}

function ReaderSettings({ open, onClose, prefs }: { open: boolean; onClose: () => void; prefs: Prefs }) {
  const seg = <T extends string>(value: T, options: { v: T; label: string }[], set: (v: T) => void) => (
    <div className="flex rounded-lg border border-line p-0.5 text-[13px]" role="group">
      {options.map((o) => (
        <button key={o.v} aria-pressed={value === o.v} onClick={() => set(o.v)} className={cx("flex-1 rounded-md px-2.5 py-1.5", value === o.v ? "bg-raised text-text" : "text-muted hover:text-text")}>
          {o.label}
        </button>
      ))}
    </div>
  );
  return (
    <Modal open={open} onClose={onClose} title="Reading settings">
      <div className="space-y-5">
        <Field label="Theme">
          {seg(prefs.theme, [
            { v: "dark", label: "Dark" },
            { v: "light", label: "Light" },
            { v: "sepia", label: "Sepia" },
            { v: "system", label: "System" },
          ], (theme) => setPrefs({ theme }))}
        </Field>
        <Field label={`Text size · ${prefs.fontSize}px`}>
          <input type="range" min={14} max={26} value={prefs.fontSize} onChange={(e) => setPrefs({ fontSize: Number(e.target.value) })} className="w-full accent-[var(--accent)]" />
        </Field>
        <Field label="Line width">
          {seg(prefs.width, [
            { v: "narrow", label: "Narrow" },
            { v: "medium", label: "Medium" },
            { v: "wide", label: "Wide" },
          ], (width) => setPrefs({ width }))}
        </Field>
        <label className="flex items-center justify-between gap-4 text-sm">
          Show speech tags (“he said…”)
          <input type="checkbox" checked={prefs.showTags} onChange={(e) => setPrefs({ showTags: e.target.checked })} className="h-4 w-4 accent-[var(--accent)]" />
        </label>
        <label className="flex items-center justify-between gap-4 text-sm">
          Show avatars
          <input type="checkbox" checked={prefs.showAvatars} onChange={(e) => setPrefs({ showAvatars: e.target.checked })} className="h-4 w-4 accent-[var(--accent)]" />
        </label>
        <p className="text-xs text-faint">Keys: ← → change chapter · e toggles correction mode</p>
      </div>
    </Modal>
  );
}

/** Save which chapter (and how far into it) the reader is; restore the scroll position on return. */
function useReadingProgress(novelId: number | undefined, chapterId: number, saved: { chapter_id: number; position: number } | null | undefined, ready: boolean) {
  const restored = useRef<number | null>(null);
  useEffect(() => {
    if (!ready || restored.current === chapterId || saved === undefined) return;
    restored.current = chapterId;
    if (saved && saved.chapter_id === chapterId && saved.position > 0.02) {
      requestAnimationFrame(() => {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        window.scrollTo({ top: saved.position * max });
      });
    } else {
      window.scrollTo({ top: 0 });
    }
  }, [ready, chapterId, saved]);

  useEffect(() => {
    if (!novelId) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    const save = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      const pos = max > 0 ? Math.min(1, window.scrollY / max) : 0;
      api.progress(novelId, chapterId, pos).catch(() => {});
    };
    save();
    const onScroll = () => {
      clearTimeout(t);
      t = setTimeout(save, 1200);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      clearTimeout(t);
      window.removeEventListener("scroll", onScroll);
    };
  }, [novelId, chapterId]);
}
