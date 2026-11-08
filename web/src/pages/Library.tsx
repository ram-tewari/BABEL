import { useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Library as LibraryIcon, Upload } from "lucide-react";
import { api, isActive, type Novel } from "../lib/api";
import { Button, Cover, Empty, ErrorNote, ProgressBar, Spinner, cx } from "../components/ui";
import { StatusChip } from "../components/StatusChip";
import { Logo } from "../components/Logo";

export function Library() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const novels = useQuery({
    queryKey: ["novels"],
    queryFn: api.novels,
    refetchInterval: (q) => (q.state.data?.some((n) => isActive(n.job)) ? 3000 : false),
  });
  const importer = useMutation({
    mutationFn: (f: File) => api.importNovel(f),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["novels"] });
      navigate(`/novel/${r.id}`);
    },
  });

  const pick = (files: FileList | null) => {
    const f = files?.[0];
    if (f) importer.mutate(f);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    pick(e.dataTransfer.files);
  };

  return (
    <div
      className="min-h-dvh"
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => e.currentTarget === e.target && setDragging(false)}
      onDrop={onDrop}
    >
      <header className="sticky top-0 z-10 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4">
          <Logo />
          <div className="ml-auto flex items-center gap-2">
            <StatusChip />
            <input ref={fileRef} type="file" accept=".epub,.txt" hidden onChange={(e) => pick(e.target.files)} />
            <Button variant="primary" onClick={() => fileRef.current?.click()} disabled={importer.isPending}>
              {importer.isPending ? <Spinner size={16} /> : <Upload size={16} />}
              <span className="hidden sm:inline">{importer.isPending ? "Importing…" : "Import book"}</span>
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8">
        {importer.error && (
          <div className="mb-6">
            <ErrorNote error={importer.error} />
          </div>
        )}
        {novels.isLoading ? (
          <div className="flex justify-center py-24">
            <Spinner size={28} />
          </div>
        ) : novels.error ? (
          <ErrorNote error={novels.error} />
        ) : novels.data!.length === 0 ? (
          <Empty icon={<LibraryIcon size={44} />} title="Your library is empty">
            <p>Drop an EPUB or TXT file anywhere on this page, or use <b>Import book</b>.</p>
            <p className="mt-2">
              BABEL splits it into chapters, then labels every line — dialogue, thoughts, system windows — so you can read it as a
              chat-style scenario.
            </p>
            <Button variant="primary" className="mt-6" onClick={() => fileRef.current?.click()}>
              <Upload size={16} /> Import your first book
            </Button>
          </Empty>
        ) : (
          <>
            <ContinueStrip novels={novels.data!} />
            <h2 className="mb-4 text-sm font-medium uppercase tracking-wide text-muted">Library</h2>
            <ul className="grid grid-cols-2 gap-x-5 gap-y-8 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {novels.data!.map((n) => (
                <li key={n.id}>
                  <NovelTile novel={n} />
                </li>
              ))}
            </ul>
          </>
        )}
      </main>

      <div
        aria-hidden={!dragging}
        className={cx(
          "pointer-events-none fixed inset-3 z-50 flex items-center justify-center rounded-3xl border-2 border-dashed border-accent bg-bg/80 backdrop-blur transition-opacity",
          dragging ? "opacity-100" : "opacity-0",
        )}
      >
        <div className="text-center">
          <Upload className="mx-auto mb-3 text-accent" size={40} />
          <div className="text-lg font-semibold">Drop to import</div>
          <div className="text-sm text-muted">EPUB or TXT</div>
        </div>
      </div>
    </div>
  );
}

function NovelTile({ novel }: { novel: Novel }) {
  const pct = novel.chapter_count ? Math.round((novel.done_count / novel.chapter_count) * 100) : 0;
  return (
    <Link to={`/novel/${novel.id}`} className="group block">
      <div className="transition-transform group-hover:-translate-y-1">
        <Cover novel={novel} />
      </div>
      <div className="mt-3 line-clamp-2 text-sm font-medium leading-snug">{novel.title}</div>
      {novel.author && <div className="truncate text-xs text-muted">{novel.author}</div>}
      <div className="mt-2 flex items-center gap-2">
        <ProgressBar value={novel.done_count} max={novel.chapter_count} tone={pct === 100 ? "ok" : "accent"} label="Transformed" />
        <span className="shrink-0 text-[11px] tabular-nums text-faint">
          {isActive(novel.job) ? <Spinner size={10} /> : `${pct}%`}
        </span>
      </div>
    </Link>
  );
}

function ContinueStrip({ novels }: { novels: Novel[] }) {
  const reading = novels.filter((n) => n.last_chapter_id).slice(0, 3);
  if (reading.length === 0) return null;
  return (
    <section className="mb-10">
      <h2 className="mb-4 text-sm font-medium uppercase tracking-wide text-muted">Continue reading</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {reading.map((n) => (
          <Link
            key={n.id}
            to={`/read/${n.last_chapter_id}`}
            className="flex items-center gap-4 rounded-xl border border-line bg-surface p-3 transition-colors hover:bg-raised"
          >
            <div className="w-12 shrink-0">
              <Cover novel={n} className="rounded-md shadow-none" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{n.title}</div>
              <div className="mt-0.5 flex items-center gap-1 text-xs text-accent">
                <BookOpen size={13} /> Resume
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
