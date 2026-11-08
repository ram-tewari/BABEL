import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Check, CircleAlert, Download, Globe, Search, Sparkles, Trash2, Upload, Wand2 } from "lucide-react";
import { api, isActive, type ChapterRow, type NovelDetail, type TierMode } from "../lib/api";
import { Button, Cover, ErrorNote, Field, Modal, Spinner, buttonCls, cx, inputCls } from "../components/ui";
import { JobCard } from "../components/JobCard";
import { CastEditor } from "../components/CastEditor";
import { DesignTab } from "../components/DesignTab";
import { GlossaryEditor } from "../components/GlossaryEditor";
import { ReviewQueue } from "../components/ReviewQueue";
import { CharacterGraph } from "../components/CharacterGraph";
import { StatusChip } from "../components/StatusChip";
import { TierBar } from "../components/TierBar";

const TABS = [
  { key: "chapters", label: "Chapters" },
  { key: "cast", label: "Cast" },
  { key: "design", label: "Design" },
  { key: "glossary", label: "Glossary" },
  { key: "review", label: "Review" },
  { key: "graph", label: "Graph" },
  { key: "export", label: "Export" },
  { key: "settings", label: "Settings" },
] as const;

export function NovelPage() {
  const { id, tab = "chapters" } = useParams();
  const novelId = Number(id);
  const qc = useQueryClient();
  const novel = useQuery({
    queryKey: ["novel", novelId],
    queryFn: () => api.novel(novelId),
    refetchInterval: (q) => (isActive(q.state.data?.job) ? 2000 : false),
  });
  const wasActive = useRef(false);
  useEffect(() => {
    const active = isActive(novel.data?.job);
    if (active || wasActive.current) ["chapters", "cast", "review", "graph"].forEach((k) => qc.invalidateQueries({ queryKey: [k, novelId] }));
    wasActive.current = active;
  }, [novel.data?.job?.done, novel.data?.job?.status, novelId, qc]);

  if (novel.isLoading)
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner size={28} />
      </div>
    );
  if (novel.error || !novel.data)
    return (
      <div className="mx-auto max-w-xl p-8">
        <ErrorNote error={novel.error ?? "Novel not found"} />
      </div>
    );
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
        <nav className="mt-10 flex gap-1 overflow-x-auto border-b border-line" aria-label="Sections">
          {TABS.map((t) => (
            <NavLink
              key={t.key}
              to={t.key === "chapters" ? `/novel/${n.id}` : `/novel/${n.id}/${t.key}`}
              end
              className={({ isActive: on }) =>
                cx("-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium", on || (t.key === "chapters" && tab === "chapters") ? "border-accent text-text" : "border-transparent text-muted hover:text-text")
              }
            >
              {t.label}
              {t.key === "review" && n.review_total > 0 && <span className="ml-1.5 rounded-full bg-warn/20 px-1.5 text-[11px] text-warn">{n.review_total}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="pt-6">
          {tab === "chapters" && <ChapterList novel={n} />}
          {tab === "cast" && <CastEditor novelId={n.id} povId={n.pov_character_id} />}
          {tab === "design" && <DesignTab novelId={n.id} />}
          {tab === "glossary" && <GlossaryEditor novelId={n.id} />}
          {tab === "review" && <ReviewQueue novelId={n.id} />}
          {tab === "graph" && <CharacterGraph novelId={n.id} />}
          {tab === "export" && <ExportPanel novel={n} />}
          {tab === "settings" && <SettingsPanel novel={n} />}
        </div>
      </main>
    </div>
  );
}

function NovelHeader({ novel: n }: { novel: NovelDetail }) {
  const chapters = useQuery({ queryKey: ["chapters", n.id], queryFn: () => api.chapters(n.id) });
  const startId = n.progress?.chapter_id ?? chapters.data?.[0]?.id;
  const cloud = n.usage.filter((u) => u.tier === "cloud");
  const local = n.usage.filter((u) => u.tier === "local");
  const sum = (rows: typeof n.usage, f: (u: (typeof n.usage)[number]) => number) => rows.reduce((a, u) => a + f(u), 0);
  const hasTiers = Object.keys(n.tier_counts).length > 0;
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
          <span>{n.done_count.toLocaleString()} transformed</span>
          {n.read_count > 0 && <span>{n.read_count.toLocaleString()} read</span>}
          {n.status && <span className="capitalize">{n.status}</span>}
          {n.failed_count > 0 && <span className="text-danger">{n.failed_count} failed</span>}
        </div>
        {n.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {n.tags.slice(0, 10).map((t) => (
              <span key={t} className="rounded-full bg-raised px-2 py-0.5 text-[11px] text-muted">
                {t}
              </span>
            ))}
          </div>
        )}
        {n.description && <p className="mt-4 line-clamp-4 max-w-2xl text-sm leading-relaxed text-muted">{n.description}</p>}
        <div className="mt-5 flex flex-wrap gap-2">
          {startId && (
            <Link to={`/read/${startId}`} className={buttonCls("primary")}>
              <BookOpen size={16} /> {n.progress ? "Continue reading" : "Start reading"}
            </Link>
          )}
        </div>
        {hasTiers && (
          <div className="mt-6 max-w-xl rounded-xl border border-line p-4">
            <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">Who decided the lines</div>
            <TierBar counts={n.tier_counts} />
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
              {local.length > 0 && <span>local model: {sum(local, (u) => u.questions).toLocaleString()} questions · free</span>}
              <span>
                cloud: {sum(cloud, (u) => u.prompt_tokens + u.completion_tokens).toLocaleString()} tokens ({sum(cloud, (u) => u.questions).toLocaleString()} questions)
              </span>
              <span>corrections: {n.corrections}</span>
            </div>
          </div>
        )}
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
  const recent = job?.finished_at && Date.now() - Date.parse(job.finished_at) < 3600_000;
  const tiers = status.data?.tiers;
  const chain = tiers ? ["rules", "memory", tiers.local && "local model", tiers.cloud.length && tiers.cloud[0].name].filter(Boolean).join(" → ") : "";
  return (
    <section className="mt-8 space-y-3">
      {job && (isActive(job) || job.status === "paused" || recent) && <JobCard job={job} novelId={n.id} />}
      {!isActive(job) && job?.status !== "paused" && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-line p-4">
          <Wand2 size={18} className="text-accent" />
          <div className="min-w-0 flex-1 text-sm">
            {remaining > 0 ? (
              <>
                <b>{remaining.toLocaleString()}</b> chapters to transform. <span className="text-muted">Pipeline: {chain}.</span>
              </>
            ) : (
              <span className="text-muted">Every chapter is transformed. Re-run any range after adding a model or editing the glossary.</span>
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
      {open && <TransformOptions novel={n} onClose={() => setOpen(false)} onStart={(b) => start.mutate(b)} pending={start.isPending} />}
    </section>
  );
}

function TransformOptions({ novel, onClose, onStart, pending }: { novel: NovelDetail; onClose: () => void; onStart: (b: { first: number | null; last: number | null; force: boolean; tiers: TierMode }) => void; pending: boolean }) {
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 60_000 });
  const [first, setFirst] = useState("1");
  const [last, setLast] = useState(String(novel.chapter_count));
  const [force, setForce] = useState(false);
  const [tiers, setTiers] = useState<TierMode>("auto");
  const toIdx = (s: string) => (s.trim() === "" ? null : Math.max(0, Number(s) - 1));
  const est = useQuery({ queryKey: ["estimate", novel.id, first, last], queryFn: () => api.estimate(novel.id, toIdx(first), toIdx(last)) });
  const t = status.data?.tiers;
  const options: { v: TierMode; label: string; ok: boolean }[] = [
    { v: "auto", label: "Full cascade — rules → memory → local → cloud (best quality, lowest cost)", ok: true },
    { v: "rules", label: "Rules + memory only — instant, offline", ok: true },
    { v: "local", label: "Up to the local model — free, no cloud calls", ok: !!t?.local },
    { v: "cloud", label: "Skip the local model — the cloud answers every uncertain line", ok: !!t?.cloud.length },
  ];
  return (
    <Modal open onClose={onClose} title="Transform chapters" wide>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onStart({ first: toIdx(first), last: toIdx(last), force, tiers });
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
        <Field group label="Decision tiers">
          <div className="space-y-1.5" role="radiogroup">
            {options.map((o) => (
              <label key={o.v} className={cx("flex items-start gap-2 rounded-lg border px-3 py-2 text-sm", tiers === o.v ? "border-accent bg-accent/5" : "border-line", !o.ok && "opacity-50")}>
                <input type="radio" name="tiers" className="mt-1 accent-[var(--accent)]" checked={tiers === o.v} disabled={!o.ok} onChange={() => setTiers(o.v)} />
                <span>
                  {o.label}
                  {!o.ok && " (not configured)"}
                </span>
              </label>
            ))}
          </div>
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="accent-[var(--accent)]" />
          Re-transform chapters that are already done (your corrections are kept)
        </label>
        {est.data && (
          <div className="rounded-lg bg-raised px-3 py-2 text-xs text-muted">
            <b className="text-text">{est.data.chapters.toLocaleString()}</b> chapters ({Math.round(est.data.words / 1000).toLocaleString()}k words) to go — estimated from {est.data.basis}:
            {est.data.per_tier.local && (tiers === "auto" || tiers === "local") && (
              <div>· local model: ~{est.data.per_tier.local.questions.toLocaleString()} questions, ~{est.data.local_minutes} min, free</div>
            )}
            {est.data.per_tier.cloud && (tiers === "auto" || tiers === "cloud") && <div>· cloud: ~{(est.data.per_tier.cloud.prompt + est.data.per_tier.cloud.completion).toLocaleString()} tokens</div>}
            {tiers === "rules" && <div>· no model calls</div>}
          </div>
        )}
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

const STATUS_DOT: Record<string, string> = { done: "bg-ok", failed: "bg-danger", pending: "bg-faint/50" };

function ChapterList({ novel }: { novel: NovelDetail }) {
  const chapters = useQuery({ queryKey: ["chapters", novel.id], queryFn: () => api.chapters(novel.id) });
  const [filter, setFilter] = useState<"all" | "unread" | "done" | "pending" | "review" | "failed">("all");
  const [q, setQ] = useState("");
  const [deepQ, setDeepQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDeepQ(q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]);
  const search = useQuery({ queryKey: ["search", novel.id, deepQ], queryFn: () => api.search(novel.id, deepQ), enabled: deepQ.length >= 3 });
  const rows = useMemo(() => {
    let r = chapters.data ?? [];
    if (filter === "review") r = r.filter((c) => c.review_count > 0);
    else if (filter === "unread") r = r.filter((c) => !c.is_read);
    else if (filter !== "all") r = r.filter((c) => c.status === filter);
    const needle = q.trim().toLowerCase();
    if (needle) r = r.filter((c) => c.title.toLowerCase().includes(needle) || String(c.idx + 1) === needle);
    return r;
  }, [chapters.data, filter, q]);
  const current = novel.progress?.chapter_id;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input className={cx(inputCls, "pl-9")} placeholder="Find a chapter, or search the text…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search chapters" />
        </div>
        <div className="flex flex-wrap rounded-lg border border-line p-0.5 text-[13px]" role="group" aria-label="Filter">
          {(["all", "unread", "done", "pending", "review", "failed"] as const).map((f) => (
            <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f} className={cx("rounded-md px-2.5 py-1 capitalize", filter === f ? "bg-raised text-text" : "text-muted hover:text-text")}>
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
      <Link to={`/read/${c.id}`} className={cx("flex h-12 items-center gap-3 px-4 text-sm hover:bg-raised", current && "bg-accent/5", c.is_read && !current && "text-muted")}>
        <span className="w-12 shrink-0 text-right tabular-nums text-faint">{c.idx + 1}</span>
        <span className={cx("h-2 w-2 shrink-0 rounded-full", STATUS_DOT[c.status])} title={c.status} />
        <span className="min-w-0 flex-1 truncate">{c.title}</span>
        {current && <span className="shrink-0 text-xs text-accent">reading</span>}
        {c.is_read && !current && <Check size={14} className="shrink-0 text-ok" aria-label="read" />}
        {c.review_count > 0 && (
          <span className="shrink-0 rounded-full bg-warn/15 px-1.5 text-[11px] text-warn" title="lines to review">
            {c.review_count}
          </span>
        )}
        {c.status === "failed" && (
          <span title={c.error ?? ""} className="shrink-0 text-danger">
            <CircleAlert size={15} />
          </span>
        )}
        <span className="hidden w-24 shrink-0 sm:block">{Object.keys(c.tiers).length > 0 && <TierBar counts={c.tiers} compact />}</span>
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
    { kind: "epub" as const, title: "EPUB", desc: "The chat-style scenario for e-readers and phone reading apps." },
    { kind: "html" as const, title: "Single HTML file", desc: "Self-contained, follows light/dark mode. Good for sharing or archiving." },
    { kind: "json" as const, title: "Visual Scenario JSON", desc: "The standardized format: every block with speaker, tone, confidence and the tier that decided it." },
    { kind: "corrections" as const, title: "Corrections (JSONL)", desc: "Your fixes and confirmations — gold labels for evaluating or fine-tuning a model." },
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
      <p className="text-xs text-faint">Untransformed chapters are exported with the instant rules + memory labeling.</p>
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
  const refresh = () => ["novel", "novels", "chapters"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const save = useMutation({ mutationFn: () => api.patchNovel(novel.id, { title, author: author || null, description: description || null }), onSuccess: refresh });
  const cover = useMutation({ mutationFn: (f: File) => api.uploadCover(novel.id, f), onSuccess: refresh });
  const append = useMutation({ mutationFn: (f: File) => api.appendChapters(novel.id, f), onSuccess: refresh });
  const find = useMutation({ mutationFn: (apply: boolean) => api.fetchMetadata(novel.id, apply), onSuccess: (r) => void (r.applied && refresh()) });
  const del = useMutation({
    mutationFn: () => api.deleteNovel(novel.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["novels"] });
      navigate("/");
    },
  });
  const meta = find.data?.metadata;
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
        <h3 className="text-sm font-semibold">Find cover & details online</h3>
        <p className="text-xs text-muted">Searches Open Library and Google Books, then RoyalRoad and NovelUpdates (those two often block automated requests).</p>
        <Button onClick={() => find.mutate(false)} disabled={find.isPending}>
          {find.isPending ? <Spinner size={14} /> : <Globe size={15} />} Search by title
        </Button>
        {meta && (
          <div className="flex gap-3 rounded-xl border border-line p-3">
            {meta.cover_url && <img src={meta.cover_url} alt="" className="h-28 w-20 shrink-0 rounded object-cover" />}
            <div className="min-w-0 text-sm">
              <div className="font-medium">{meta.title}</div>
              <div className="text-xs text-muted">
                {meta.author} · from {meta.source}
              </div>
              {meta.description && <p className="mt-1 line-clamp-3 text-xs text-muted">{meta.description}</p>}
              {!find.data!.applied ? (
                <Button size="sm" variant="primary" className="mt-2" onClick={() => find.mutate(true)}>
                  Use this
                </Button>
              ) : (
                <p className="mt-2 text-xs text-ok">Applied.</p>
              )}
            </div>
          </div>
        )}
        {find.data?.notes.length ? <p className="text-xs text-faint">{find.data.notes.join(" · ")}</p> : null}
        <ErrorNote error={find.error} />
      </section>

      <section className="space-y-3">
        <h3 className="text-sm font-semibold">Files</h3>
        <div className="flex flex-wrap gap-2">
          <input ref={coverRef} type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && cover.mutate(e.target.files[0])} />
          <Button onClick={() => coverRef.current?.click()} disabled={cover.isPending}>
            <Upload size={15} /> Upload cover
          </Button>
          <input ref={appendRef} type="file" accept=".epub,.txt" hidden onChange={(e) => e.target.files?.[0] && append.mutate(e.target.files[0])} />
          <Button onClick={() => appendRef.current?.click()} disabled={append.isPending}>
            {append.isPending ? <Spinner size={14} /> : <Upload size={15} />} Add new chapters
          </Button>
        </div>
        <p className="text-xs text-faint">“Add new chapters” takes a newer file of the same novel and appends only chapters you don’t have yet — for ongoing webnovels.</p>
        {append.data && <p className="text-sm text-ok">Added {append.data.added} new chapters.</p>}
        <ErrorNote error={cover.error ?? append.error} />
      </section>

      <section className="space-y-3 rounded-xl border border-danger/30 p-4">
        <h3 className="text-sm font-semibold text-danger">Delete novel</h3>
        <p className="text-sm text-muted">Removes the novel, its chapters, memory and corrections from your library. Your original file is not touched.</p>
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
