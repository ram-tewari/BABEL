import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronLeft, ChevronRight, MessagesSquare, Pause, Play, Sparkles } from "lucide-react";
import { api, type StageBlock, type StageView } from "../lib/api";
import { cssColor } from "../lib/colors";
import { Rich } from "../components/Scenario";
import { Spinner, cx } from "../components/ui";

/** Lines the stage steps through: speech tags are already shown by the name plate. */
const isStep = (b: StageBlock) => b.type !== "tag" && b.type !== "break" && b.text.trim().length > 0;

/** Muted gradients when a place has no background yet. */
const PLACE_TINT: [RegExp, string][] = [
  [/street|square|alley/i, "linear-gradient(180deg,#3b4a5c 0%,#252d38 60%,#1b2028 100%)"],
  [/pub|tavern|restaurant/i, "linear-gradient(180deg,#5a3b24 0%,#2e1f15 100%)"],
  [/church|cathedral|chapel/i, "linear-gradient(180deg,#4a4458 0%,#25222e 100%)"],
  [/room|apartment|house/i, "linear-gradient(180deg,#4b4036 0%,#2a241e 100%)"],
  [/fog|mist|void|dream/i, "radial-gradient(circle at 50% 40%,#6b6b78 0%,#2c2c35 70%)"],
];
const tint = (place: string) => PLACE_TINT.find(([rx]) => rx.test(place))?.[1] ?? "linear-gradient(180deg,#3a3f4a 0%,#1f2228 100%)";

interface Actor {
  id: number;
  sprite: string | null;
  emotion: string;
}

/** Who is on stage at step ``i``: the last (up to) three people who spoke or acted in this scene. */
function presence(stage: StageView, steps: number[], i: number): Actor[] {
  const blocks = stage.blocks;
  const here = blocks[steps[i]];
  const seen = new Map<number, Actor>();
  for (let k = i; k >= 0 && seen.size < 3; k--) {
    const b = blocks[steps[k]];
    if (b.scene !== here.scene) break;
    if (b.character_id != null && (b.type === "dialogue" || b.type === "thought" || b.type === "action") && !seen.has(b.character_id))
      seen.set(b.character_id, { id: b.character_id, sprite: b.sprite ?? null, emotion: b.emotion ?? "neutral" });
  }
  return [...seen.values()];
}

export function VisualNovel() {
  const { chapterId } = useParams();
  const cid = Number(chapterId);
  const navigate = useNavigate();
  const stage = useQuery({
    queryKey: ["stage", cid],
    queryFn: () => api.stage(cid),
    // keep checking while this chapter's faces/backgrounds are still being drawn
    refetchInterval: (q) => {
      const d = q.state.data;
      if (!d) return false;
      const missingArt = Object.values(d.cast).some((c) => !c.has_art) || d.scenes.some((s) => !s.background);
      return missingArt ? 6000 : false;
    },
  });
  const prepare = useMutation({ mutationFn: () => api.prepareStage(cid) });
  const prepared = useRef<number | null>(null);
  useEffect(() => {
    if (prepared.current !== cid) {
      prepared.current = cid;
      prepare.mutate(undefined, { onSuccess: () => void stage.refetch() });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cid]);

  const s = stage.data;
  const steps = useMemo(() => (s ? s.blocks.map((b, i) => (isStep(b) ? i : -1)).filter((i) => i >= 0) : []), [s]);
  const [i, setI] = useState(0);
  const [auto, setAuto] = useState(false);
  useEffect(() => setI(0), [cid]);

  const atEnd = s ? i >= steps.length - 1 : false;
  const next = useCallback(() => {
    if (!s) return;
    if (i < steps.length - 1) setI(i + 1);
    else if (s.chapter.next_id) navigate(`/vn/${s.chapter.next_id}`);
  }, [s, i, steps.length, navigate]);
  const prev = useCallback(() => setI((x) => Math.max(0, x - 1)), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " " || e.key === "Enter") {
        e.preventDefault();
        next();
      } else if (e.key === "ArrowLeft" || e.key === "Backspace") prev();
      else if (e.key.toLowerCase() === "a") setAuto((x) => !x);
      else if (e.key === "Escape") navigate(`/read/${cid}`);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [next, prev, navigate, cid]);

  const block = s && steps.length ? s.blocks[steps[Math.min(i, steps.length - 1)]] : null;
  useEffect(() => {
    if (!auto || !block) return;
    const t = setTimeout(next, Math.min(9000, 1400 + block.text.length * 45));
    return () => clearTimeout(t);
  }, [auto, block, next]);

  if (stage.isLoading || !s) {
    return (
      <div className="flex h-dvh items-center justify-center bg-black text-white">
        <Spinner />
      </div>
    );
  }
  if (!block) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center gap-3 bg-black text-white">
        <p>This chapter has nothing to stage.</p>
        <Link className="underline" to={`/read/${cid}`}>
          Read it in chat mode
        </Link>
      </div>
    );
  }

  const scene = s.scenes[block.scene] ?? s.scenes[0];
  const actors = presence(s, steps, Math.min(i, steps.length - 1));
  const speaking = block.type === "dialogue" || block.type === "thought" || block.type === "action" ? block.character_id : null;
  const castOf = (id: number | null) => (id != null ? s.cast[String(id)] : undefined);
  const missingArt = Object.values(s.cast).filter((c) => !c.has_art).map((c) => c.name);

  return (
    <div className="relative h-dvh w-full select-none overflow-hidden bg-black text-white" onClick={next}>
      {/* background */}
      <div className="absolute inset-0 transition-[background] duration-700" style={{ background: tint(scene?.place ?? "") }} />
      {scene?.background && <img key={scene.background} src={scene.background} alt="" className="absolute inset-0 h-full w-full animate-[fadein_.7s_ease] object-cover" />}
      {scene?.night && <div className="pointer-events-none absolute inset-0 bg-[#0b1430]/55 mix-blend-multiply" />}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/70 to-transparent" />

      {/* sprites */}
      <Stage actors={actors} speaking={speaking} cast={s.cast} />

      {/* top bar */}
      <div className="absolute inset-x-0 top-0 z-20 flex items-center gap-2 bg-gradient-to-b from-black/60 to-transparent px-3 py-2 text-sm" onClick={(e) => e.stopPropagation()}>
        <Link to={`/read/${cid}`} className="inline-flex items-center gap-1 rounded-lg px-2 py-1 text-white/80 hover:bg-white/10 hover:text-white" title="Back to chat mode (Esc)">
          <ArrowLeft size={16} /> <MessagesSquare size={15} />
        </Link>
        <span className="min-w-0 flex-1 truncate text-center font-medium text-white/90">
          {s.chapter.title} <span className="font-normal text-white/50">· {scene?.place}</span>
        </span>
        <button className="rounded-lg p-1.5 text-white/80 hover:bg-white/10" onClick={() => setAuto(!auto)} aria-label={auto ? "Stop auto-play (A)" : "Auto-play (A)"} aria-pressed={auto}>
          {auto ? <Pause size={17} /> : <Play size={17} />}
        </button>
      </div>
      {(prepare.isPending || missingArt.length > 0 || !s.ready) && (
        <div className="absolute left-3 top-12 z-20 max-w-sm rounded-lg bg-black/60 px-3 py-2 text-xs text-white/80" onClick={(e) => e.stopPropagation()}>
          {prepare.isPending ? (
            <span className="flex items-center gap-2">
              <Spinner size={12} /> Preparing this chapter…
            </span>
          ) : s.missing.length > 0 ? (
            <span>
              Needs a design: {s.missing.join(", ")} —{" "}
              <Link className="underline" to={`/novel/${s.chapter.novel_id}/design`}>
                pick a look
              </Link>
            </span>
          ) : missingArt.length > 0 ? (
            <span className="flex items-center gap-2">
              <Sparkles size={12} /> Drawing {missingArt.length} more face{missingArt.length === 1 ? "" : "s"} for this chapter…
            </span>
          ) : null}
        </div>
      )}

      {/* the line */}
      <LineBox block={block} cast={castOf(block.character_id)} />

      {/* progress + paging */}
      <div className="absolute inset-x-0 bottom-0 z-20 flex items-center gap-2 px-3 pb-2" onClick={(e) => e.stopPropagation()}>
        <button className="rounded p-1 text-white/60 hover:text-white disabled:opacity-30" onClick={prev} disabled={i === 0} aria-label="Previous line">
          <ChevronLeft size={16} />
        </button>
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/15">
          <div className="h-full bg-white/60 transition-[width]" style={{ width: `${((i + 1) / steps.length) * 100}%` }} />
        </div>
        <button className="rounded p-1 text-white/60 hover:text-white" onClick={next} aria-label={atEnd ? "Next chapter" : "Next line"}>
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

function Stage({ actors, speaking, cast }: { actors: Actor[]; speaking: number | null; cast: StageView["cast"] }) {
  // POV / right-side characters stand on the right, others left; up to three on stage
  const left = actors.filter((a) => cast[String(a.id)]?.side !== "right");
  const right = actors.filter((a) => cast[String(a.id)]?.side === "right");
  const slots: { a: Actor; x: number }[] = [];
  const narrow = typeof window !== "undefined" && window.innerWidth < 640;
  left.slice(0, 2).forEach((a, k) => slots.push({ a, x: narrow ? (k === 0 ? 30 : 45) : k === 0 ? 24 : 40 }));
  right.slice(0, 2).forEach((a, k) => slots.push({ a, x: narrow ? (k === 0 ? 70 : 55) : k === 0 ? 76 : 60 }));
  if (slots.length === 1) slots[0].x = narrow ? 50 : slots[0].x; // alone on a phone: centre stage
  return (
    <div className="pointer-events-none absolute inset-0">
      {slots.map(({ a, x }) => {
        const c = cast[String(a.id)];
        const active = a.id === speaking;
        // nobody speaking (narration): everyone stays lit; someone speaking: the others step back
        const dim = speaking != null && !active;
        return (
          <div
            key={a.id}
            className="absolute bottom-0 flex h-[74%] items-end transition-all duration-300"
            style={{ left: `${x}%`, zIndex: active ? 5 : 1, filter: dim ? "brightness(.55) saturate(.7)" : "none", transform: `translateX(-50%) scale(${dim ? 0.96 : 1})` }}
          >
            {a.sprite ? (
              <img
                src={a.sprite}
                alt={c?.name ?? ""}
                className="h-full w-auto max-w-[min(62vw,620px)] object-contain object-bottom [filter:drop-shadow(0_0_1px_rgba(0,0,0,.7))_drop-shadow(0_10px_24px_rgba(0,0,0,.45))]"
              />
            ) : (
              <Silhouette color={c?.color} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function Silhouette({ color }: { color?: string | null }) {
  return (
    <svg viewBox="0 0 200 300" className="h-[70%] w-auto opacity-70" aria-hidden>
      <circle cx="100" cy="80" r="46" fill={cssColor(color ?? "slot:0")} opacity=".55" />
      <path d="M20 300 C20 190 60 150 100 150 C140 150 180 190 180 300 Z" fill={cssColor(color ?? "slot:0")} opacity=".45" />
    </svg>
  );
}

function LineBox({ block, cast }: { block: StageBlock; cast?: StageView["cast"][string] }) {
  if (block.type === "sfx") {
    return (
      <div className="pointer-events-none absolute inset-x-0 top-1/3 z-10 text-center font-sans text-5xl font-black uppercase tracking-wide text-amber-300 drop-shadow-[0_4px_12px_rgba(0,0,0,.8)] sm:text-6xl" style={{ transform: "rotate(-3deg)" }}>
        {block.text}
      </div>
    );
  }
  if (block.type === "system") {
    return (
      <div className="absolute left-1/2 top-1/4 z-10 w-[min(92%,34rem)] -translate-x-1/2 rounded-lg border border-sky-300/60 bg-sky-950/85 px-5 py-4 text-center font-mono text-sm text-sky-100 shadow-[0_0_30px_rgba(56,189,248,.35)]">
        <Rich text={block.text} />
      </div>
    );
  }
  const name = block.type === "narration" ? null : cast?.name ?? block.speaker;
  const color = cssColor(cast?.color ?? "slot:0");
  return (
    <div className="absolute inset-x-0 bottom-6 z-10 px-3 sm:px-8">
      <div
        key={`${block.para}-${block.text.slice(0, 20)}`}
        className={cx(
          "mx-auto max-w-4xl animate-[fadein_.25s_ease] rounded-xl border px-5 pb-4 pt-3 shadow-2xl backdrop-blur-md",
          block.type === "thought" ? "border-dashed border-white/40 bg-black/55" : "border-white/15 bg-black/70",
        )}
      >
        {name && (
          <div className="mb-1 text-sm font-semibold tracking-wide" style={{ color }}>
            {name}
            {block.type === "thought" && <span className="ml-1.5 font-normal text-white/50">thinks</span>}
            {block.emotion && block.emotion !== "neutral" && block.type !== "action" && <span className="ml-2 text-xs font-normal capitalize text-white/40">{block.emotion}</span>}
          </div>
        )}
        <p className={cx("font-serif text-[17px] leading-relaxed text-white/95 sm:text-lg", (block.type === "thought" || block.type === "action") && "italic text-white/80", block.type === "narration" && "text-white/85")}>
          <Rich text={block.text} />
        </p>
      </div>
    </div>
  );
}
