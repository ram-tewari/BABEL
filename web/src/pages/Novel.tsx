import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, CircleAlert, Download, Search, Sparkles, Trash2, Upload, Wand2 } from "lucide-react";
import { api, isActive, type ChapterRow, type Job, type NovelDetail } from "../lib/api";
import { Button, Cover, ErrorNote, Field, Modal, Spinner, buttonCls, cx, inputCls } from "../components/ui";
import { JobCard } from "../components/JobCard";
import { CastEditor } from "../components/CastEditor";
import { StatusChip } from "../components/StatusChip";

const TABS = [
  { key: "chapters", label: "Chapters" },
  { key: "cast", label: "Cast" },
  { key: "export", label: "Export" },
  { key: "settings", label: "Settings" },
] as const;

export function NovelPage() {
  const { id, tab = "chapters" } = useParams();
  const novelId = Number(id);
  const novel = useQuery({
    queryKey: ["novel", novelId],
    queryFn: () => api.novel(novelId),
    refetchInterval: (q) => (isActive(q.state.data?.job) ? 2000 : false),
  });
  const qc = useQueryClient();
  const wasActive = useRef(false);
  useEffect(() => {
    // refresh chapter statuses + cast when a job finishes
    const active = isActive(novel.data?.job);
    if (wasActive.current && !active) {
      qc.invalidateQueries({ queryKey: ["chapters", novelId] });
      qc.invalidateQueries({ queryKey: ["cast", novelId] });
    }
    wasActive.current = active;
    if (active) qc.invalidateQueries({ queryKey: ["chapters", novelId] });
  }, [novel.data?.job?.done, novel.data?.job?.status, novelId, qc]);

  if (novel.isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner size={28} />
      </div>
    );
  }
  if (novel.error || !novel.data) {
    return (
      <div className="mx-auto max-w-xl p-8">
        <ErrorNote error={novel.error ?? "Novel not found"} />
      </div>
    );
  }
  const n = novel.data;

  return (
    <div className="min-h-dvh">
      <header className="border-b border-line">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-2 px-4">
          <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-text">
            <ArrowLeft size={16} /> Library
          </Link>
          <div className="ml-auto">
            <StatusChip />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 pb-24 pt-8">
        <NovelHeader novel={n} />
        <TransformPanel novel={n} />

        <nav className="mt-10 flex gap-1 border-b border-line" aria-label="Sections">
          {TABS.map((t) => (
            <NavLink
              key={t.key}
              to={t.key === "chapters" ? `/novel/${n.id}` : `/novel/${n.id}/${t.key}`}
              end
              className={({ isActive: on }) =>
                cx(
                  "-mb-px border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
                  on || (t.key === "chapters" && tab === "chapters") ? "border-accent text-text" : "border-transparent text-muted hover:text-text",
                )
              }
            >
              {t.label}
            </NavLink>
          ))}
        </nav>
        <div className="pt-6">
          {tab === "chapters" && <ChapterList novel={n} />}
          {tab === "cast" && <CastEditor novelId={n.id} povId={n.pov_character_id} />}
          {tab === "export" && <ExportPanel novel={n} />}
          {tab === "settings" && <SettingsPanel novel={n} />}
        </div>
      </main>
    </div>
  );
}

function NovelHeader({ novel: n }: { novel: NovelDetail }) {
  const startId = n.progress?.chapter_id;
  const first = useQuery({ queryKey: ["chapters", n.id], queryFn: () => api.chapters(n.id) });
  const firstId = first.data?.[0]?.id;
  return (
    <section className="flex flex-col gap-6 sm:flex-row">
      <div className="w-36 shrink-0 sm:w-44">
        <Cover novel={n} />
      </div>
      <div className="min-w-0 flex-1">
        <h1 className="font-serif text-3xl font-semibold leading-tight">{n.title}</h1>
        {n.author && <div className="mt-1 text-muted">{n.author}</div>}
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
          <span>{n.chapter_count.toLocaleString()} chapters</span>
          <span>{Math.round(n.word_count / 1000).toLocaleString()}k words</span>
          <span>
            {n.done_count.toLocaleString()} transformed
            {n.methods.llm ? ` · ${n.methods.llm} by LLM` : ""}
            {n.methods.heuristic ? ` · ${n.methods.heuristic} offline` : ""}
          </span>
          {n.failed_count > 0 && <span className="text-danger">{n.failed_count} failed</span>}
        </div>
        {n.description && <p className="mt-4 line-clamp-4 max-w-2xl text-sm leading-relaxed text-muted">{n.description}</p>}
        <div className="mt-5 flex flex-wrap gap-2">
          {(startId ?? firstId) && (
            <Link to={`/read/${startId ?? firstId}`} className={buttonCls("primary")}>
              <BookOpen size={16} /> {startId ? "Continue reading" : "Start reading"}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

function TransformPanel({ novel: n }: { novel: NovelDetail }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 60_000 });
  const start = useMutation({
    mutationFn: (body: Parameters<typeof api.startJob>[1]) => api.startJob(n.id, body),
    onSuccess: () => {
      setOpen(false);
      qc.invalidateQueries({ queryKey: ["novel", n.id] });
    },
  });
  const job = n.job;
  const remaining = n.chapter_count - n.done_count;
  const showJob = job && (isActive(job) || job.status === "paused" || (job.finished_at && Date.now() - Date.parse(job.finished_at) < 3600_000));

  return (
    <section className="mt-8 space-y-3">
      {showJob && <JobCard job={job!} novelId={n.id} />}
      {!isActive(job) && job?.status !== "paused" && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-line p-4">
          <Wand2 size={18} className="text-accent" />
          <div className="min-w-0 flex-1 text-sm">
            {remaining > 0 ? (
              <>
                <b>{remaining.toLocaleString()}</b> chapters not transformed yet.{" "}
                <span className="text-muted">
                  {status.data?.llm ? `They'll be labeled by ${status.data.providers[0]?.name}.` : "No LLM configured, so the offline labeler will be used."}
                </span>
              </>
            ) : (
              <span className="text-muted">Every chapter is transformed. You can re-run ranges with a better model at any time.</span>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setOpen(true)}>
              Options…
            </Button>
            {remaining > 0 && (
              <Button variant="primary" size="sm" onClick={() => start.mutate({})} disabled={start.isPending}>
                <Sparkles size={14} /> Transform all
              </Button>
            )}
          </div>
        </div>
      )}
      <ErrorNote error={start.error} />
      <TransformOptions open={open} onClose={() => setOpen(false)} novel={n} onStart={(b) => start.mutate(b)} pending={start.isPending} />
    </section>
  );
}

function TransformOptions({
  open,
  onClose,
  novel,
  onStart,
  pending,
}: {
  open: boolean;
  onClose: () => void;
  novel: NovelDetail;
  onStart: (b: { first: number | null; last: number | null; force: boolean; mode: Job["mode"] }) => void;
  pending: boolean;
}) {
  const [first, setFirst] = useState("1");
  const [last, setLast] = useState(String(novel.chapter_count));
  const [force, setForce] = useState(false);
  const [mode, setMode] = useState<Job["mode"]>("auto");
  const toIdx = (s: string) => (s.trim() === "" ? null : Math.max(0, Number(s) - 1));
  return (
    <Modal open={open} onClose={onClose} title="Transform chapters">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onStart({ first: toIdx(first), last: toIdx(last), force, mode });
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <Field label="From chapter">
            <input className={inputCls} type="number" min={1} max={novel.chapter_count} value={first} onChange={(e) => setFirst(e.target.value)} />
          </Field>
          <Field label="To chapter">
            <input className={inputCls} type="number" min={1} max={novel.chapter_count} value={last} onChange={(e) => setLast(e.target.value)} />
          </Field>
        </div>
        <Field label="Labeler" hint="Auto uses the LLM chain and falls back to the offline labeler for any chunk that fails.">
          <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value as Job["mode"])}>
            <option value="auto">Auto (LLM, with offline fallback)</option>
            <option value="llm">LLM only (mark failures)</option>
            <option value="heuristic">Offline only (instant, no API)</option>
          </select>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="accent-[var(--accent)]" />
          Re-transform chapters that are already done
        </label>
        <p className="text-xs text-faint">Your manual corrections are kept even when chapters are re-transformed.</p>
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={pending}>
            <Sparkles size={14} /> Start
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const STATUS_DOT: Record<string, string> = {
  done: "bg-ok",
  failed: "bg-danger",
  pending: "bg-faint/50",
};

function ChapterList({ novel }: { novel: NovelDetail }) {
  const chapters = useQuery({ queryKey: ["chapters", novel.id], queryFn: () => api.chapters(novel.id) });
  const [filter, setFilter] = useState<"all" | "done" | "pending" | "failed">("all");
  const [q, setQ] = useState("");
  const [deepQ, setDeepQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDeepQ(q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]);
  const search = useQuery({
    queryKey: ["search", novel.id, deepQ],
    queryFn: () => api.search(novel.id, deepQ),
    enabled: deepQ.length >= 3,
  });

  const rows = useMemo(() => {
    let r = chapters.data ?? [];
    if (filter !== "all") r = r.filter((c) => c.status === filter);
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      r = r.filter((c) => c.title.toLowerCase().includes(needle) || String(c.idx + 1) === needle);
    }
    return r;
  }, [chapters.data, filter, q]);

  const current = novel.progress?.chapter_id;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input
            className={cx(inputCls, "pl-9")}
            placeholder="Find a chapter, or search the text…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Search chapters"
          />
        </div>
        <div className="flex rounded-lg border border-line p-0.5 text-[13px]" role="group" aria-label="Filter by status">
          {(["all", "done", "pending", "failed"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              aria-pressed={filter === f}
              className={cx("rounded-md px-2.5 py-1 capitalize", filter === f ? "bg-raised text-text" : "text-muted hover:text-text")}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {deepQ.length >= 3 && (search.data?.length ?? 0) > 0 && (
        <div className="mb-6 rounded-xl border border-line bg-surface p-2">
          <div className="px-2 py-1 text-xs font-medium uppercase tracking-wide text-muted">Found in text</div>
          <ul>
            {search.data!.slice(0, 8).map((h) => (
              <li key={h.id}>
                <Link to={`/read/${h.id}`} className="block rounded-lg px-2 py-2 hover:bg-raised">
                  <div className="text-sm font-medium">{h.title}</div>
                  <div className="line-clamp-1 text-xs text-muted">…{h.snippet}…</div>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      {chapters.isLoading ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted">No chapters match.</p>
      ) : (
        <ol className="divide-y divide-line rounded-xl border border-line">
          {rows.map((c) => (
            <ChapterItem key={c.id} c={c} current={c.id === current} />
          ))}
        </ol>
      )}
    </div>
  );
}

function ChapterItem({ c, current }: { c: ChapterRow; current: boolean }) {
  return (
    <li style={{ contentVisibility: "auto", containIntrinsicSize: "0 48px" }}>
      <Link to={`/read/${c.id}`} className={cx("flex h-12 items-center gap-3 px-4 text-sm hover:bg-raised", current && "bg-accent/5")}>
        <span className="w-12 shrink-0 text-right tabular-nums text-faint">{c.idx + 1}</span>
        <span className={cx("h-2 w-2 shrink-0 rounded-full", STATUS_DOT[c.status])} title={c.status} />
        <span className="min-w-0 flex-1 truncate">{c.title}</span>
        {current && <span className="shrink-0 text-xs text-accent">reading</span>}
        {c.status === "failed" && (
          <span title={c.error ?? ""} className="shrink-0 text-danger">
            <CircleAlert size={15} />
          </span>
        )}
        {c.method === "heuristic" && <span className="hidden shrink-0 text-xs text-faint sm:inline">offline</span>}
        <span className="hidden w-16 shrink-0 text-right text-xs tabular-nums text-faint sm:inline">{c.word_count.toLocaleString()}w</span>
      </Link>
    </li>
  );
}

function ExportPanel({ novel }: { novel: NovelDetail }) {
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const toIdx = (s: string) => (s.trim() === "" ? null : Math.max(0, Number(s) - 1));
  const items = [
    { kind: "epub" as const, title: "EPUB", desc: "Chat-style scenario for e-readers and phone reading apps." },
    { kind: "html" as const, title: "Single HTML file", desc: "Self-contained page that follows light/dark mode. Good for sharing or archiving." },
    { kind: "corrections" as const, title: "Corrections (JSONL)", desc: "Every manual fix you made — useful for evaluating or fine-tuning a labeler." },
  ];
  return (
    <div className="max-w-2xl space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:max-w-sm">
        <Field label="From chapter">
          <input className={inputCls} type="number" min={1} placeholder="1" value={first} onChange={(e) => setFirst(e.target.value)} />
        </Field>
        <Field label="To chapter">
          <input className={inputCls} type="number" min={1} placeholder={String(novel.chapter_count)} value={last} onChange={(e) => setLast(e.target.value)} />
        </Field>
      </div>
      <ul className="space-y-3">
        {items.map((it) => (
          <li key={it.kind} className="flex items-center gap-4 rounded-xl border border-line bg-surface p-4">
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{it.title}</div>
              <div className="text-xs text-muted">{it.desc}</div>
            </div>
            <a
              href={api.exportUrl(novel.id, it.kind, it.kind === "corrections" ? null : toIdx(first), it.kind === "corrections" ? null : toIdx(last))}
              download
              className={buttonCls("outline", "sm")}
            >
              <Download size={14} /> Download
            </a>
          </li>
        ))}
      </ul>
      <p className="text-xs text-faint">Untransformed chapters are exported with an offline preview labeling.</p>
    </div>
  );
}

function SettingsPanel({ novel }: { novel: NovelDetail }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [title, setTitle] = useState(novel.title);
  const [author, setAuthor] = useState(novel.author ?? "");
  const [description, setDescription] = useState(novel.description ?? "");
  const [confirm, setConfirm] = useState(false);
  const coverRef = useRef<HTMLInputElement>(null);
  const appendRef = useRef<HTMLInputElement>(null);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["novel", novel.id] });
    qc.invalidateQueries({ queryKey: ["novels"] });
    qc.invalidateQueries({ queryKey: ["chapters", novel.id] });
  };
  const save = useMutation({ mutationFn: () => api.patchNovel(novel.id, { title, author: author || null, description: description || null }), onSuccess: refresh });
  const cover = useMutation({ mutationFn: (f: File) => api.uploadCover(novel.id, f), onSuccess: refresh });
  const append = useMutation({ mutationFn: (f: File) => api.appendChapters(novel.id, f), onSuccess: refresh });
  const del = useMutation({
    mutationFn: () => api.deleteNovel(novel.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["novels"] });
      navigate("/");
    },
  });
  return (
    <div className="max-w-xl space-y-10">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <Field label="Title">
          <input className={inputCls} value={title} onChange={(e) => setTitle(e.target.value)} required />
        </Field>
        <Field label="Author">
          <input className={inputCls} value={author} onChange={(e) => setAuthor(e.target.value)} />
        </Field>
        <Field label="Description">
          <textarea className={cx(inputCls, "h-28 py-2")} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="flex items-center gap-3">
          <Button type="submit" variant="primary" disabled={save.isPending}>
            Save
          </Button>
          {save.isSuccess && <span className="text-sm text-ok">Saved</span>}
        </div>
        <ErrorNote error={save.error} />
      </form>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold">Files</h3>
        <div className="flex flex-wrap gap-2">
          <input ref={coverRef} type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && cover.mutate(e.target.files[0])} />
          <Button onClick={() => coverRef.current?.click()} disabled={cover.isPending}>
            <Upload size={15} /> Replace cover
          </Button>
          <input ref={appendRef} type="file" accept=".epub,.txt" hidden onChange={(e) => e.target.files?.[0] && append.mutate(e.target.files[0])} />
          <Button onClick={() => appendRef.current?.click()} disabled={append.isPending}>
            {append.isPending ? <Spinner size={14} /> : <Upload size={15} />} Add new chapters
          </Button>
        </div>
        <p className="text-xs text-faint">
          “Add new chapters” takes a newer EPUB/TXT of the same novel and appends only the chapters you don’t have yet — handy for ongoing webnovels.
        </p>
        {append.data && <p className="text-sm text-ok">Added {append.data.added} new chapters.</p>}
        <ErrorNote error={cover.error ?? append.error} />
      </section>

      <section className="space-y-3 rounded-xl border border-danger/30 p-4">
        <h3 className="text-sm font-semibold text-danger">Delete novel</h3>
        <p className="text-sm text-muted">Removes the novel, its chapters, cast and corrections from your library. The original file is not affected.</p>
        {confirm ? (
          <div className="flex gap-2">
            <Button variant="danger" onClick={() => del.mutate()} disabled={del.isPending}>
              <Trash2 size={15} /> Yes, delete “{novel.title}”
            </Button>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Cancel
            </Button>
          </div>
        ) : (
          <Button variant="danger" onClick={() => setConfirm(true)}>
            <Trash2 size={15} /> Delete…
          </Button>
        )}
      </section>
    </div>
  );
}
