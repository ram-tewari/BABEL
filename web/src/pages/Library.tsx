import { useEffect, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Play, Upload } from "lucide-react";
import { api, isActive, type Novel } from "../lib/api";
import { Cover, ErrorNote, Spinner, cx } from "../components/ui";
import { HudBar, Proscenium, useThemeArt } from "../components/Theatre";
import { PaintedSet } from "../vn/PaintedSet";
import { Petals } from "../vn/Effects";
import { reducedMotion } from "../vn/settings";

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
  const list = novels.data ?? [];
  const current = list.find((n) => n.last_chapter_id) ?? list[0];

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
      <HudBar>
        <input ref={fileRef} type="file" accept=".epub,.txt" hidden onChange={(e) => pick(e.target.files)} />
        <button className="btn-brass !min-h-[34px] !text-[13px]" onClick={() => fileRef.current?.click()} disabled={importer.isPending}>
          {importer.isPending ? <Spinner size={14} /> : <Upload size={14} />}
          <span className="hidden sm:inline">{importer.isPending ? "Importing…" : "Import a book"}</span>
        </button>
      </HudBar>

      <Hero current={current} onImport={() => fileRef.current?.click()} empty={!novels.isLoading && list.length === 0} />

      <main className="mx-auto max-w-7xl px-4 pb-24 sm:px-6">
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
        ) : list.length === 0 ? null : (
          <>
            <div className="mb-6 flex items-end justify-between gap-4">
              <div>
                <div className="eyebrow">Repertoire</div>
                <h2 className="display mt-1 text-4xl">Now showing</h2>
              </div>
              <span className="text-sm text-muted">{list.length} {list.length === 1 ? "production" : "productions"}</span>
            </div>
            <div className="brass-rule mb-8" />
            <ul className="grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-5">
              {list.map((n) => (
                <li key={n.id}>
                  <Playbill novel={n} />
                </li>
              ))}
            </ul>
          </>
        )}
      </main>

      <div
        aria-hidden={!dragging}
        className={cx(
          "pointer-events-none fixed inset-3 z-50 flex items-center justify-center border-2 border-dashed border-brass bg-bg/85 backdrop-blur transition-opacity",
          dragging ? "opacity-100" : "opacity-0",
        )}
      >
        <div className="text-center">
          <Upload className="mx-auto mb-3 text-brass" size={40} />
          <div className="display text-3xl">Drop to add to the repertoire</div>
          <div className="text-sm text-muted">EPUB or TXT</div>
        </div>
      </div>
    </div>
  );
}

/** The lobby: a proscenium whose curtains part on arrival, the tagline, and tonight's performance. */
function Hero({ current, onImport, empty }: { current?: Novel; onImport: () => void; empty: boolean }) {
  const art = useThemeArt();
  const stage = art.url("stage.webp");
  const [open, setOpen] = useState(0);
  const motion = !reducedMotion();
  useEffect(() => {
    const t = setTimeout(() => setOpen(0.86), motion ? 350 : 0);
    return () => clearTimeout(t);
  }, [motion]);
  return (
    <section className="relative">
      <Proscenium open={open} className="h-[min(78vh,760px)] w-full" duration={1600}>
        <div className="absolute inset-0">
          {stage ? <img src={stage} alt="" className="h-full w-full object-cover [image-rendering:pixelated]" /> : <PaintedSet category="street" night />}
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_35%,transparent_25%,#05070bdd_90%)]" />
          <Petals on={motion} count={10} />
        </div>
        <div className="absolute inset-0 z-[25] flex items-center justify-center px-6 text-center">
          <div style={{ animation: motion ? "fadein 1.2s .9s var(--ease-out) both" : undefined }}>
            <div className="eyebrow !text-[#dfb56f]">The Theatre of Stories</div>
            <h1 className="display mx-auto mt-4 max-w-4xl text-[clamp(48px,8vw,120px)] leading-[0.92] text-[#f3ece4] drop-shadow-[0_6px_30px_#000]">Every novel, staged.</h1>
            <p className="mx-auto mt-5 max-w-xl text-[17px] text-[#e6dccf]/90">
              Import a webnovel and BABEL casts it: who says what, how they feel, where they stand. Then the curtain rises.
            </p>
            <div className="mt-8 flex flex-wrap justify-center gap-3">
              {current && (
                <Link to={`/play/${current.id}`} className="btn-brass">
                  <Play size={15} /> {current.last_chapter_id ? "Continue" : "Play"} · <span className="max-w-[16rem] truncate">{current.title}</span>
                </Link>
              )}
              <button onClick={onImport} className={empty ? "btn-brass" : "btn-ghost"}>
                <Upload size={15} /> Import a book
              </button>
            </div>
            {empty && <p className="mt-4 text-sm text-white/60">or drop an EPUB / TXT anywhere on this page</p>}
          </div>
        </div>
      </Proscenium>
    </section>
  );
}

/** A production on the playbill wall: framed cover, staging progress, Play and Programme. */
function Playbill({ novel }: { novel: Novel }) {
  const play = useQuery({ queryKey: ["play", novel.id], queryFn: () => api.play(novel.id), staleTime: 30_000 });
  const pct = novel.chapter_count ? Math.round((novel.done_count / novel.chapter_count) * 100) : 0;
  return (
    <article className="group">
      <Link to={`/play/${novel.id}`} className="relative block" aria-label={`Play ${novel.title}`}>
        <div className="border-[3px] border-[#8a5a2b] bg-[#1a100a] p-1.5 shadow-[0_18px_40px_#000c] transition-transform duration-300 [transition-timing-function:var(--ease-out)] group-hover:-translate-y-1.5" style={{ boxShadow: "inset 0 0 0 1px #dfb56f66, 0 18px 40px #000c" }}>
          <Cover novel={novel} className="!rounded-none" />
        </div>
        <span className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <span className="btn-brass !min-h-[36px] !px-4 !text-[13px]">
            <Play size={13} /> Play
          </span>
        </span>
      </Link>
      <h3 className="display mt-3 line-clamp-2 text-xl leading-tight">{novel.title}</h3>
      {novel.author && <div className="truncate text-xs text-muted">{novel.author}</div>}
      <div className="mt-2 flex items-center gap-2 font-mono text-[11px] text-faint">
        {isActive(novel.job) ? <Spinner size={10} /> : <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: pct === 100 ? "var(--ok)" : "var(--brass)" }} />}
        {novel.done_count}/{novel.chapter_count} staged
        {play.data && play.data.ready > 0 && <span className="text-[#dfb56f]">· {play.data.ready} fully cast</span>}
      </div>
      <div className="mt-3 flex gap-2">
        <Link to={`/play/${novel.id}`} className="btn-ghost !min-h-[32px] !px-3 !text-[12px]">
          <Play size={12} /> Play
        </Link>
        <Link to={`/novel/${novel.id}`} className="btn-ghost !min-h-[32px] !px-3 !text-[12px]">
          <BookOpen size={12} /> Programme
        </Link>
      </div>
    </article>
  );
}
