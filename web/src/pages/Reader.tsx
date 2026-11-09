import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Clapperboard, FileText, Library, ListOrdered, MessagesSquare, Moon, Pencil, RefreshCw, Sparkles, Type, User } from "lucide-react";
import { api, isActive, type Block, type ChapterView, type Entity, type TierMode } from "../lib/api";
import { setPrefs, usePrefs, WIDTHS, type Prefs } from "../lib/prefs";
import { ErrorNote, Field, IconButton, Modal, Spinner, buttonCls, cx } from "../components/ui";
import { Scenario } from "../components/Scenario";
import { BlockEditor, type EditResult } from "../components/BlockEditor";
import { CharacterPanel, useCast } from "../components/CastEditor";
import { ChapterSidebar } from "../components/ChapterSidebar";
import { CommandMenu, type Command } from "../components/CommandMenu";
import { TierBar } from "../components/TierBar";

const MAX_WINDOW = 4; // chapters kept in the DOM at once
const HEADER = 72; // px of sticky header + breathing room

export function Reader() {
  const { chapterId } = useParams();
  const routeId = Number(chapterId);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const prefs = usePrefs();

  const [win, setWin] = useState<number[]>([routeId]);
  const [current, setCurrent] = useState(routeId);
  const ourUrl = useRef<number | null>(null); // the id we last wrote into the URL ourselves
  const jump = useRef<{ id: number; position: number | null } | null>({ id: routeId, position: null });
  const anchor = useRef<{ el: HTMLElement; top: number } | null>(null);
  const userScrolled = useRef(false);
  const sections = useRef(new Map<number, HTMLElement>());

  const [editing, setEditing] = useState(false);
  const [editTarget, setEditTarget] = useState<{ chapterId: number; block: Block } | null>(null);
  const [charOpen, setCharOpen] = useState<Entity | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);

  // An outside navigation (link, back button, sidebar jump outside the window) resets the window.
  useEffect(() => {
    if (routeId === ourUrl.current) return;
    setWin([routeId]);
    setCurrent(routeId);
    jump.current = { id: routeId, position: null };
    userScrolled.current = false;
  }, [routeId]);

  const results = useQueries({ queries: win.map((id) => ({ queryKey: ["chapter", id], queryFn: () => api.chapter(id) })) });
  const loaded = results.map((r) => r.data);
  const first = loaded[0];
  const last = loaded[loaded.length - 1];
  const novelId = first?.novel_id ?? last?.novel_id ?? 0;
  const novel = useQuery({
    queryKey: ["novel", novelId],
    queryFn: () => api.novel(novelId),
    enabled: novelId > 0,
    refetchInterval: (q) => (isActive(q.state.data?.job) ? 2500 : false),
  });
  const chapters = useQuery({ queryKey: ["chapters", novelId], queryFn: () => api.chapters(novelId), enabled: novelId > 0 });
  const cast = useCast(novelId);
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 60_000 });

  // ── initial jump (restores the saved position inside the chapter) ─────
  useLayoutEffect(() => {
    const j = jump.current;
    if (!j || !novel.data || !first || first.id !== j.id) return;
    const el = sections.current.get(j.id);
    if (!el) return;
    const saved = novel.data.progress;
    const pos = j.position ?? (saved && saved.chapter_id === j.id ? saved.position : 0);
    const top = el.getBoundingClientRect().top + window.scrollY - HEADER;
    const span = Math.max(0, el.offsetHeight - window.innerHeight + HEADER);
    window.scrollTo({ top: pos > 0.02 ? top + pos * span : Math.max(0, top - 8) });
    jump.current = null;
  });

  // ── keep content still when chapters are added or removed above ──────
  useLayoutEffect(() => {
    const a = anchor.current;
    if (!a) return;
    const now = a.el.getBoundingClientRect().top;
    if (now !== a.top) window.scrollBy(0, now - a.top);
    anchor.current = loaded[0] ? null : { el: a.el, top: a.el.getBoundingClientRect().top };
  });
  const holdAnchor = () => {
    const firstLoaded = win.find((id) => sections.current.get(id));
    const el = firstLoaded ? sections.current.get(firstLoaded) : null;
    if (el) anchor.current = { el, top: el.getBoundingClientRect().top };
  };

  // ── infinite scroll in both directions ───────────────────────────────
  const extend = useCallback(
    (dir: "next" | "prev") => {
      if (dir === "next") {
        if (!last?.next_id || win.includes(last.next_id)) return;
        if (win.length >= MAX_WINDOW) {
          const keep = win[1];
          const el = sections.current.get(keep);
          if (el) anchor.current = { el, top: el.getBoundingClientRect().top };
        }
        setWin((w) => [...w, last.next_id!].slice(-MAX_WINDOW));
      } else {
        if (!first?.prev_id || win.includes(first.prev_id) || !userScrolled.current) return;
        holdAnchor();
        setWin((w) => [first.prev_id!, ...w].slice(0, MAX_WINDOW));
      }
    },
    [first, last, win],
  );
  const topRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && extend(e.target === topRef.current ? "prev" : "next")),
      { rootMargin: "900px 0px" },
    );
    if (topRef.current) io.observe(topRef.current);
    if (bottomRef.current) io.observe(bottomRef.current);
    return () => io.disconnect();
  }, [extend]);

  // ── which chapter is in view; URL + progress follow it ───────────────
  const saveTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    let raf = 0;
    const onScroll = () => {
      userScrolled.current = true;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        let inView = win[0];
        for (const id of win) {
          const el = sections.current.get(id);
          if (el && el.getBoundingClientRect().top <= HEADER + 40) inView = id;
        }
        if (inView !== current) {
          setCurrent(inView);
          ourUrl.current = inView;
          navigate(`/read/${inView}`, { replace: true });
        }
        clearTimeout(saveTimer.current);
        saveTimer.current = setTimeout(() => {
          const el = sections.current.get(inView);
          if (!el || !novelId) return;
          const top = el.getBoundingClientRect().top + window.scrollY - HEADER;
          const span = Math.max(1, el.offsetHeight - window.innerHeight + HEADER);
          const pos = Math.min(1, Math.max(0, (window.scrollY - top) / span));
          api.progress(novelId, inView, pos).then(() => void (pos >= 0.9 && qc.invalidateQueries({ queryKey: ["chapters", novelId] }))).catch(() => {});
        }, 900);
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [win, current, novelId, navigate, qc]);

  const goTo = useCallback(
    (id: number) => {
      const el = sections.current.get(id);
      if (el) {
        window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - HEADER + 8, behavior: "smooth" });
      } else {
        navigate(`/read/${id}`);
      }
      if (window.innerWidth < 1024) setSidebar(false);
    },
    [navigate],
  );
  const currentView = loaded.find((c) => c?.id === current);

  // ── keyboard ─────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "k") return e.preventDefault(), setCmdOpen((v) => !v);
      if (mod && e.key.toLowerCase() === "b") return e.preventDefault(), setSidebar((v) => !v);
      const t = e.target as HTMLElement;
      if (t.closest("input, textarea, select, dialog[open], [role=dialog]") || mod || e.altKey) return;
      if (e.key === "ArrowRight" && currentView?.next_id) goTo(currentView.next_id);
      if (e.key === "ArrowLeft" && currentView?.prev_id) goTo(currentView.prev_id);
      if (e.key === "e") setEditing((v) => !v);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [currentView, goTo]);

  // ── corrections ──────────────────────────────────────────────────────
  const setView = (view: ChapterView) => {
    qc.setQueryData(["chapter", view.id], view);
    ["cast", "review", "corrections"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    setEditTarget(null);
  };
  const edit = useMutation({ mutationFn: (r: EditResult) => api.edit(editTarget!.chapterId, editTarget!.block.seg, r.type, r.speaker, r.tone), onSuccess: setView });
  const accept = useMutation({ mutationFn: () => api.accept(editTarget!.chapterId, editTarget!.block.seg), onSuccess: setView });
  const revert = useMutation({ mutationFn: () => api.clearEdits(editTarget!.chapterId, editTarget!.block.seg), onSuccess: setView });

  // ── command menu ─────────────────────────────────────────────────────
  const commands = useMemo<Command[]>(() => {
    const out: Command[] = [
      { id: "lib", group: "Go to", label: "Library", icon: <Library size={15} />, run: () => navigate("/") },
      { id: "novel", group: "Go to", label: novel.data?.title ?? "Novel page", icon: <BookOpen size={15} />, run: () => navigate(`/novel/${novelId}`) },
      { id: "review", group: "Go to", label: "Review queue", hint: `${novel.data?.review_total ?? 0} lines`, icon: <Pencil size={15} />, run: () => navigate(`/novel/${novelId}/review`) },
      { id: "sidebar", group: "Actions", label: "Toggle chapter list", hint: "Ctrl+B", icon: <ListOrdered size={15} />, run: () => setSidebar((v) => !v) },
      { id: "edit", group: "Actions", label: editing ? "Stop correcting" : "Correct lines", hint: "e", icon: <Pencil size={15} />, run: () => setEditing((v) => !v) },
      { id: "view", group: "Actions", label: prefs.view === "scenario" ? "Show original text" : "Show scenario", icon: <FileText size={15} />, run: () => setPrefs({ view: prefs.view === "scenario" ? "original" : "scenario" }) },
      ...(["dark", "light", "sepia", "system"] as const).map((t) => ({ id: `theme-${t}`, group: "Theme", label: `${t[0].toUpperCase()}${t.slice(1)} theme`, icon: <Moon size={15} />, run: () => setPrefs({ theme: t }) })),
    ];
    (cast.data ?? []).slice(0, 60).forEach((c) => out.push({ id: `c${c.id}`, group: "Characters", label: c.name, hint: c.aliases.slice(0, 2).join(", "), icon: <User size={15} />, run: () => setCharOpen(c) }));
    (chapters.data ?? []).forEach((c) => out.push({ id: `ch${c.id}`, group: "Chapters", label: c.title, hint: `#${c.idx + 1}`, icon: <BookOpen size={15} />, run: () => goTo(c.id) }));
    return out;
  }, [cast.data, chapters.data, novel.data, novelId, editing, prefs.view, navigate, goTo]);

  const width = WIDTHS[prefs.width];
  const llm = !!(status.data?.tiers.local || status.data?.tiers.cloud.length);
  const initial = results[0];

  return (
    <div className="min-h-dvh [overflow-anchor:none]" style={{ ["--reader-size" as string]: `${prefs.fontSize}px` }}>
      <header className="sticky top-0 z-20 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto flex h-14 items-center gap-1 px-2 sm:px-4" style={{ maxWidth: `calc(${width} + 8rem)` }}>
          <IconButton label="Chapters (Ctrl+B)" onClick={() => setSidebar(!sidebar)} aria-pressed={sidebar}>
            <ListOrdered size={18} />
          </IconButton>
          <Link to={novelId ? `/novel/${novelId}` : "/"} className="inline-flex h-9 items-center gap-1 rounded-lg px-2 text-sm text-muted hover:bg-raised hover:text-text">
            <ArrowLeft size={16} />
            <span className="hidden max-w-40 truncate sm:inline">{novel.data?.title ?? "Back"}</span>
          </Link>
          <button className="min-w-0 flex-1 truncate px-2 text-center text-sm font-medium" onClick={() => setCmdOpen(true)} title="Jump to… (Ctrl+K)">
            {currentView?.title}
          </button>
          <IconButton label="Read as a visual novel" onClick={() => navigate(`/vn/${current}`)}>
            <Clapperboard size={18} />
          </IconButton>
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

      <ChapterSidebar open={sidebar} chapters={chapters.data ?? []} current={current} title={novel.data?.title ?? ""} onPick={goTo} onClose={() => setSidebar(false)} />

      <main className="mx-auto px-4 pb-40 pt-6" style={{ maxWidth: width }}>
        {editing && (
          <div className="sticky top-16 z-10 mb-6 rounded-lg border border-accent/40 bg-surface/95 px-3 py-2 text-center text-sm shadow-sm backdrop-blur">
            Correction mode — click a line to fix it. <span className="text-warn">●</span> uncertain <span className="text-accent">●</span> corrected
          </div>
        )}
        <div ref={topRef} aria-hidden className="h-px" />
        {initial?.isLoading && (
          <div className="flex justify-center py-24">
            <Spinner size={28} />
          </div>
        )}
        {initial?.error && <ErrorNote error={initial.error} />}
        {win.map((id, i) => {
          const view = loaded[i];
          return (
            <section
              key={id}
              data-chapter-id={id}
              ref={(el) => {
                if (el) sections.current.set(id, el);
                else sections.current.delete(id);
              }}
              className={cx(i > 0 && "mt-20 border-t border-line pt-14")}
            >
              {view ? (
                <ChapterBody
                  view={view}
                  prefs={prefs}
                  total={novel.data?.chapter_count}
                  editing={editing}
                  llm={llm}
                  onEdit={(block) => setEditTarget({ chapterId: id, block })}
                  onCharacter={setCharOpen}
                />
              ) : (
                <div className="flex justify-center py-16">
                  <Spinner />
                </div>
              )}
            </section>
          );
        })}
        <div ref={bottomRef} aria-hidden className="h-px" />
        {last && !last.next_id && <p className="mt-16 text-center text-sm text-muted">— End of the book —</p>}
      </main>

      <BlockEditor
        block={editTarget?.block ?? null}
        cast={cast.data ?? []}
        onClose={() => setEditTarget(null)}
        onSave={(r) => edit.mutate(r)}
        onAccept={() => accept.mutate()}
        onRevert={() => revert.mutate()}
        pending={edit.isPending || accept.isPending || revert.isPending}
      />
      <Modal open={!!charOpen} onClose={() => setCharOpen(null)} title={charOpen?.name ?? ""}>
        {charOpen && novelId > 0 && (
          <CharacterPanel key={charOpen.id} character={cast.data?.find((c) => c.id === charOpen.id) ?? charOpen} novelId={novelId} cast={cast.data ?? []} onDone={() => setCharOpen(null)} />
        )}
      </Modal>
      <ReaderSettings open={settingsOpen} onClose={() => setSettingsOpen(false)} prefs={prefs} />
      <CommandMenu open={cmdOpen} onClose={() => setCmdOpen(false)} commands={commands} />
    </div>
  );
}

function ChapterBody({
  view,
  prefs,
  total,
  editing,
  llm,
  onEdit,
  onCharacter,
}: {
  view: ChapterView;
  prefs: Prefs;
  total?: number;
  editing: boolean;
  llm: boolean;
  onEdit: (b: Block) => void;
  onCharacter: (c: Entity) => void;
}) {
  const qc = useQueryClient();
  const [watch, setWatch] = useState(false);
  const characters = useMemo(() => new Map(view.characters.map((c) => [c.id, c])), [view.characters]);
  const source = useQuery({ queryKey: ["source", view.id], queryFn: () => api.source(view.id), enabled: prefs.view === "original" });
  const job = useQuery({
    queryKey: ["novel", view.novel_id],
    queryFn: () => api.novel(view.novel_id),
    enabled: watch,
    refetchInterval: watch ? 2000 : false,
    select: (n) => n.job,
  });
  useEffect(() => {
    if (watch && job.data && !isActive(job.data)) {
      setWatch(false);
      ["chapter", "cast", "chapters"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    }
  }, [watch, job.data, qc]);
  const retransform = useMutation({ mutationFn: (tiers: TierMode) => api.retransform(view.id, tiers), onSuccess: () => setWatch(true) });

  return (
    <>
      <div className="mb-8 text-center">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-faint">
          Chapter {view.idx + 1}
          {total ? ` of ${total.toLocaleString()}` : ""}
        </div>
        <h1 className="mt-2 font-serif text-2xl font-semibold leading-snug sm:text-3xl">{view.title}</h1>
      </div>
      {watch || retransform.isPending ? (
        <div className="mb-6 flex items-center justify-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-muted">
          <Spinner size={14} /> Transforming this chapter…
        </div>
      ) : view.status === "failed" ? (
        <div className="mb-6 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
          <div className="text-danger">The last transform failed: {view.error}</div>
          <button className="mt-1 inline-flex items-center gap-1 text-accent hover:underline" onClick={() => retransform.mutate("auto")}>
            <RefreshCw size={14} /> Try again
          </button>
        </div>
      ) : view.method === "preview" ? (
        <div className="mb-6 flex flex-wrap items-center justify-center gap-x-3 gap-y-1 rounded-lg border border-line bg-surface px-3 py-2 text-center text-sm text-muted">
          <span>Instant preview (rules + memory). </span>
          <button className="inline-flex items-center gap-1 font-medium text-accent hover:underline" onClick={() => retransform.mutate(llm ? "auto" : "rules")}>
            <Sparkles size={14} /> {llm ? "Transform with the model cascade" : "Save these labels"}
          </button>
        </div>
      ) : (
        editing && (
          <div className="mb-6">
            <TierBar counts={view.tiers} />
            {view.summary && <p className="mt-3 text-sm italic text-muted">Previously: {view.summary}</p>}
          </div>
        )
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
        <Scenario blocks={view.blocks} characters={characters} glossary={view.glossary} showTags={prefs.showTags} showAvatars={prefs.showAvatars} editing={editing} onEdit={onEdit} onCharacter={onCharacter} />
      )}
      {view.next_id && (
        <div className="mt-12 text-center">
          <Link to={`/read/${view.next_id}`} className={cx(buttonCls("ghost", "sm"), "text-faint")}>
            Next chapter →
          </Link>
        </div>
      )}
    </>
  );
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
        <Field group label="Theme">
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
        <Field group label="Line width">
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
          Show avatars & portraits
          <input type="checkbox" checked={prefs.showAvatars} onChange={(e) => setPrefs({ showAvatars: e.target.checked })} className="h-4 w-4 accent-[var(--accent)]" />
        </label>
        <p className="text-xs text-faint">Keys: ← → chapters · e correct · Ctrl+B chapter list · Ctrl+K jump to anything</p>
      </div>
    </Modal>
  );
}
