import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Expand, FastForward, History, MessagesSquare, Minimize, Pause, Play, Settings2, X } from "lucide-react";
import { api, type StageBlock, type StageView } from "../lib/api";
import { cssColor } from "../lib/colors";
import { Rich } from "../components/Scenario";
import { Proscenium } from "../components/Theatre";
import { Spinner, cx } from "../components/ui";
import { PaintedSet } from "./PaintedSet";
import { Petals, Weather } from "./Effects";
import { reducedMotion, useVnSettings, type VnSettings } from "./settings";

/** What the stage steps through: speech tags are already shown by the name plate. */
const isStep = (b: StageBlock) => b.type !== "tag" && b.type !== "break" && b.text.trim().length > 0;
type Phase = "title" | "opening" | "play" | "closing" | "card" | "end";

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

const missingArt = (s?: StageView) => !!s && (Object.values(s.cast).some((c) => !c.has_art) || s.scenes.some((x) => !x.background));

export function Player({ chapterId, novelId, title = false }: { chapterId?: number; novelId?: number; title?: boolean }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [settings, setSettings] = useVnSettings();
  const motion = settings.effects && !reducedMotion();
  const [cid, setCid] = useState<number | undefined>(chapterId);
  const [phase, setPhase] = useState<Phase>(title ? "title" : "opening");
  const [i, setI] = useState(0);
  const [typed, setTyped] = useState(0);
  const [auto, setAuto] = useState(false);
  const [skip, setSkip] = useState(false);
  const [hideUI, setHideUI] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const prepared = useRef(new Set<number>());

  const play = useQuery({ queryKey: ["play", novelId], queryFn: () => api.play(novelId!), enabled: !!novelId && title });
  const stage = useQuery({
    queryKey: ["stage", cid],
    queryFn: () => api.stage(cid!),
    enabled: !!cid,
    refetchInterval: (q) => (missingArt(q.state.data) ? 7000 : false),
  });
  const s = stage.data;

  // prepare this chapter (and the next) now: you're reading it
  const prepare = useCallback(
    (id: number) => {
      if (prepared.current.has(id)) return;
      prepared.current.add(id);
      api.prepareStage(id).then((v) => qc.setQueryData(["stage", id], v), () => undefined);
    },
    [qc],
  );
  useEffect(() => {
    if (cid) prepare(cid);
  }, [cid, prepare]);

  const steps = useMemo(() => (s ? s.blocks.map((b, k) => (isStep(b) ? k : -1)).filter((k) => k >= 0) : []), [s]);
  const at = Math.min(i, Math.max(0, steps.length - 1));
  const block = s && steps.length ? s.blocks[steps[at]] : null;
  const scene = s && block ? s.scenes[block.scene] ?? s.scenes[0] : undefined;

  // preload the next chapter as this one nears its end
  useEffect(() => {
    if (s?.chapter.next_id && steps.length && at > steps.length - 25) {
      void qc.prefetchQuery({ queryKey: ["stage", s.chapter.next_id], queryFn: () => api.stage(s.chapter.next_id!) });
      prepare(s.chapter.next_id);
    }
  }, [s, at, steps.length, qc, prepare]);

  // curtains: open when a chapter is loaded and we're "opening"
  useEffect(() => {
    if (phase === "opening" && s && s.chapter.id === cid) {
      const t = setTimeout(() => setPhase("play"), 1200);
      return () => clearTimeout(t);
    }
  }, [phase, s, cid]);

  // typewriter
  const fullLen = block?.text.length ?? 0;
  useEffect(() => setTyped(settings.textSpeed === 0 || skip ? Number.MAX_SAFE_INTEGER : 0), [at, cid, settings.textSpeed, skip]);
  useEffect(() => {
    if (phase !== "play" || typed >= fullLen) return;
    const t = setInterval(() => setTyped((x) => x + 2), 2000 / Math.max(10, settings.textSpeed));
    return () => clearInterval(t);
  }, [phase, typed, fullLen, settings.textSpeed]);
  const complete = typed >= fullLen;

  // save where you are (the regular reader picks up here too)
  useEffect(() => {
    if (!s || phase !== "play") return;
    const t = setTimeout(() => void api.progress(s.chapter.novel_id, s.chapter.id, steps.length ? at / steps.length : 0).catch(() => undefined), 800);
    return () => clearTimeout(t);
  }, [s, at, steps.length, phase]);

  // screen shake on sound effects and shouts (Web Animations: nothing remounts)
  const stageRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!motion || !block || !(block.type === "sfx" || block.tone === "shout")) return;
    stageRef.current?.animate(
      [{ transform: "translate(0,0)" }, { transform: "translate(-8px,4px)" }, { transform: "translate(7px,-5px)" }, { transform: "translate(-5px,3px)" }, { transform: "translate(0,0)" }],
      { duration: 420, easing: "linear" },
    );
  }, [block, motion]);

  const toNextChapter = useCallback(() => {
    if (!s?.chapter.next_id) {
      setPhase("end");
      return;
    }
    const next = s.chapter.next_id;
    setAuto(false);
    setSkip(false);
    setPhase("closing");
    setTimeout(() => {
      setPhase("card");
      setCid(next);
      setI(0);
      window.history.replaceState(null, "", `/vn/${next}`);
      setTimeout(() => setPhase("opening"), 1900);
    }, 1150);
  }, [s]);

  const advance = useCallback(() => {
    if (phase !== "play" || !s) return;
    if (!complete) return setTyped(Number.MAX_SAFE_INTEGER);
    if (at < steps.length - 1) setI(at + 1);
    else toNextChapter();
  }, [phase, s, complete, at, steps.length, toNextChapter]);
  const back = useCallback(() => setI((x) => Math.max(0, Math.min(x, steps.length - 1) - 1)), [steps.length]);

  // auto and skip
  useEffect(() => {
    if (phase !== "play" || !block) return;
    if (skip) {
      const t = setTimeout(advance, 90);
      return () => clearTimeout(t);
    }
    if (auto && complete) {
      const t = setTimeout(advance, (900 + block.text.length * 28) * settings.autoDelay);
      return () => clearTimeout(t);
    }
  }, [phase, block, auto, skip, complete, advance, settings.autoDelay]);
  // skipping stops at the end of a scene
  useEffect(() => {
    if (skip && s && block && steps[at + 1] !== undefined && s.blocks[steps[at + 1]].scene !== block.scene) setSkip(false);
  }, [skip, s, block, steps, at]);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void document.documentElement.requestFullscreen?.();
  }, []);
  useEffect(() => {
    const on = () => setFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      const k = e.key.toLowerCase();
      if (logOpen || settingsOpen) {
        if (k === "escape") {
          setLogOpen(false);
          setSettingsOpen(false);
        }
        return;
      }
      if (k === "arrowright" || k === " " || k === "enter") {
        e.preventDefault();
        if (phase === "title") return;
        if (hideUI) return setHideUI(false);
        advance();
      } else if (k === "arrowleft" || k === "backspace") back();
      else if (k === "a") setAuto((x) => !x);
      else if (k === "s") setSkip((x) => !x);
      else if (k === "l") setLogOpen(true);
      else if (k === "h") setHideUI((x) => !x);
      else if (k === "f") toggleFullscreen();
      else if (k === "escape") navigate(cid ? `/read/${cid}` : novelId ? `/novel/${novelId}` : "/");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [advance, back, phase, hideUI, logOpen, settingsOpen, toggleFullscreen, navigate, cid, novelId]);

  const begin = (id: number) => {
    setCid(id);
    setI(0);
    window.history.replaceState(null, "", `/vn/${id}`);
    setPhase("opening");
  };

  const curtain = phase === "title" || phase === "closing" || phase === "card" || phase === "end" || (phase === "opening" && !(s && s.chapter.id === cid)) ? 0 : 1;
  const actors = s && block ? presence(s, steps, at) : [];
  const speaking = block && (block.type === "dialogue" || block.type === "thought" || block.type === "action") ? block.character_id : null;

  return (
    <div className="fixed inset-0 select-none bg-black text-[#f0e9e3]">
      <div ref={stageRef} className="h-full w-full">
      <Proscenium open={curtain} className="h-full w-full">
        <div className="absolute inset-0" onClick={() => (hideUI ? setHideUI(false) : advance())}>
          {scene && <Backdrop scene={scene} motion={motion} />}
          {scene && <Weather weather={scene.weather} night={scene.night} indoor={scene.indoor} on={motion} />}
          {block?.type === "thought" && <div aria-hidden className="pointer-events-none absolute inset-0 z-[8] bg-[radial-gradient(ellipse_at_center,transparent_45%,#05070bcc_100%)] transition-opacity duration-500" />}
          {s && <Cast actors={actors} speaking={speaking} cast={s.cast} motion={motion} reactKey={at} reaction={block?.emotion} />}
          {block?.type === "sfx" && (
            <div key={at} className="pointer-events-none absolute inset-x-0 top-[30%] z-20 text-center font-[family-name:var(--font-pixel)] text-6xl font-semibold uppercase tracking-wide text-[#f0c983] drop-shadow-[0_4px_0_#4a2a10]" style={{ animation: motion ? "vn-sfx .45s var(--ease-out) both" : undefined }}>
              {block.text}
            </div>
          )}
          {block?.type === "system" && (
            <div key={at} className="absolute left-1/2 top-[22%] z-20 w-[min(88%,36rem)] -translate-x-1/2 rounded-md border border-[#73dde8]/60 bg-[#06141c]/90 px-6 py-5 text-center font-mono text-[15px] text-[#c9f3f8] shadow-[0_0_40px_#73dde833]" style={{ animation: "vn-fade .35s ease both" }}>
              <Rich text={block.text} />
            </div>
          )}
          {scene && phase === "play" && <PlacePlaque key={`${cid}-${block?.scene}`} name={scene.place} motion={motion} />}
          {block && phase === "play" && !hideUI && block.type !== "sfx" && block.type !== "system" && (
            <LineBox block={block} cast={block.character_id != null ? s?.cast[String(block.character_id)] : undefined} typed={typed} complete={complete} />
          )}
        </div>
      </Proscenium>
      </div>

      {/* top bar */}
      {!hideUI && phase !== "title" && (
        <div className="absolute inset-x-0 top-[clamp(36px,9%,96px)] z-40 flex items-start justify-between gap-3 px-[12%] pt-2 text-sm" onClick={(e) => e.stopPropagation()}>
          <div className="hidden min-w-0 rounded bg-black/40 px-3 py-1.5 backdrop-blur-sm sm:block">
            <div className="eyebrow !text-[10px] !text-[#dfb56f]">{s?.chapter.novel_title}</div>
            <div className="truncate font-[family-name:var(--font-display)] text-lg leading-tight">{s?.chapter.title}</div>
          </div>
          <div className="flex shrink-0 gap-1 rounded bg-black/40 p-1 backdrop-blur-sm max-sm:mx-auto">
            <Ctl label={auto ? "Stop auto-play (A)" : "Auto-play (A)"} on={auto} onClick={() => setAuto(!auto)}>
              {auto ? <Pause size={15} /> : <Play size={15} />}
            </Ctl>
            <Ctl label={skip ? "Stop skipping (S)" : "Skip to the scene's end (S)"} on={skip} onClick={() => setSkip(!skip)}>
              <FastForward size={15} />
            </Ctl>
            <Ctl label="Backlog (L)" onClick={() => setLogOpen(true)}>
              <History size={15} />
            </Ctl>
            <Ctl label="Settings" onClick={() => setSettingsOpen(true)}>
              <Settings2 size={15} />
            </Ctl>
            <Ctl label={fullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)"} onClick={toggleFullscreen}>
              {fullscreen ? <Minimize size={15} /> : <Expand size={15} />}
            </Ctl>
            <Ctl label="Hide the text box (H)" onClick={() => setHideUI(true)}>
              <span className="font-[family-name:var(--font-tiny)] text-[10px]">H</span>
            </Ctl>
            <Link to={cid ? `/read/${cid}` : "/"} className="inline-flex h-8 w-8 items-center justify-center rounded text-[#f0e9e3]/80 hover:bg-white/10 hover:text-white" aria-label="Back to chat mode (Esc)" title="Back to chat mode (Esc)">
              <MessagesSquare size={15} />
            </Link>
          </div>
        </div>
      )}

      {/* progress + art status */}
      {!hideUI && phase === "play" && s && (
        <div className="absolute inset-x-[12%] bottom-[clamp(10px,2.4%,22px)] z-40 h-0.5 bg-white/10" aria-hidden>
          <div className="h-full bg-[#dfb56f]/70 transition-[width] duration-300" style={{ width: `${((at + 1) / Math.max(1, steps.length)) * 100}%` }} />
        </div>
      )}
      {!hideUI && phase === "play" && s && (missingArt(s) || !s.chapter.transformed || s.missing.length > 0) && (
        <div className="absolute left-[12%] top-[calc(clamp(36px,9%,96px)+64px)] z-40 max-w-xs rounded bg-black/55 px-2.5 py-1.5 text-[11px] text-white/75 backdrop-blur-sm" onClick={(e) => e.stopPropagation()}>
          {s.missing.length > 0 ? (
            <>
              Needs a look: {s.missing.join(", ")} —{" "}
              <Link className="underline" to={`/novel/${s.chapter.novel_id}/design`}>
                design
              </Link>
            </>
          ) : !s.chapter.transformed ? (
            "This chapter hasn't been through the full pipeline yet — speakers are a quick guess."
          ) : (
            <span className="flex items-center gap-1.5">
              <Spinner size={10} /> Painting this chapter's sets and faces…
            </span>
          )}
        </div>
      )}

      {/* title screen */}
      {phase === "title" && <TitleCard play={play.data} loading={play.isLoading} novelId={novelId} onBegin={begin} motion={motion} />}
      {/* chapter placard while the curtains are closed */}
      {(phase === "card" || (phase === "opening" && !(s && s.chapter.id === cid))) && <ChapterPlacard stage={s?.chapter.id === cid ? s : undefined} loading={!s || s.chapter.id !== cid} />}
      {phase === "end" && <EndCard stage={s} />}

      {logOpen && s && <Backlog stage={s} steps={steps} at={at} onJump={(k) => (setI(k), setLogOpen(false))} onClose={() => setLogOpen(false)} />}
      {settingsOpen && <SettingsPanel settings={settings} set={setSettings} onClose={() => setSettingsOpen(false)} />}
      {stage.isError && <div className="absolute inset-x-0 top-1/2 z-50 text-center text-white/80">Couldn't load this chapter.</div>}
    </div>
  );
}

function Ctl({ label, on, onClick, children }: { label: string; on?: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick} aria-label={label} title={label} aria-pressed={on} className={cx("inline-flex h-8 w-8 items-center justify-center rounded text-[#f0e9e3]/80 hover:bg-white/10 hover:text-white", on && "bg-[#dfb56f]/25 text-[#f3e6cf]")}>
      {children}
    </button>
  );
}

/** The scene's set: generated background if drawn, otherwise the painted one — cross-fading on every change. */
function Backdrop({ scene, motion }: { scene: StageView["scenes"][number]; motion: boolean }) {
  const key = scene.background ?? `set:${scene.category}:${scene.night}`;
  const [layers, setLayers] = useState<{ key: string; scene: typeof scene }[]>([{ key, scene }]);
  useEffect(() => {
    setLayers((ls) => (ls[ls.length - 1]?.key === key ? ls : [...ls.slice(-1), { key, scene }]));
    const t = setTimeout(() => setLayers((ls) => ls.slice(-1)), 1000);
    return () => clearTimeout(t);
  }, [key, scene]);
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      {layers.map((l, n) => (
        <div key={l.key} className="absolute inset-0" style={{ animation: n > 0 || layers.length === 1 ? "vn-fade .9s ease both" : undefined }}>
          <div className="absolute inset-[-4%]" style={{ animation: motion ? "vn-kenburns 38s ease-in-out infinite alternate" : undefined }}>
            {l.scene.background ? <img src={l.scene.background} alt="" className="h-full w-full object-cover" /> : <PaintedSet category={l.scene.category} night={l.scene.night} />}
          </div>
          {l.scene.background && l.scene.night && <div className="absolute inset-0 bg-[#0b1430]/55 mix-blend-multiply" />}
        </div>
      ))}
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/75 to-transparent" />
    </div>
  );
}

/** The cast on stage: enter from their side, breathe, react to the line's emotion; others step back. */
function Cast({ actors, speaking, cast, motion, reactKey, reaction }: { actors: Actor[]; speaking: number | null; cast: StageView["cast"]; motion: boolean; reactKey: number; reaction?: string }) {
  const narrow = typeof window !== "undefined" && window.innerWidth < 640;
  const left = actors.filter((a) => cast[String(a.id)]?.side !== "right");
  const right = actors.filter((a) => cast[String(a.id)]?.side === "right");
  const slots: { a: Actor; x: number; side: "left" | "right" }[] = [];
  left.slice(0, 2).forEach((a, k) => slots.push({ a, x: narrow ? (k ? 42 : 30) : k ? 40 : 27, side: "left" }));
  right.slice(0, 2).forEach((a, k) => slots.push({ a, x: narrow ? (k ? 58 : 70) : k ? 60 : 73, side: "right" }));
  if (narrow && slots.length === 1) slots[0].x = 50;
  return (
    <div className="pointer-events-none absolute inset-0 z-10">
      {slots.map(({ a, x, side }) => {
        const c = cast[String(a.id)];
        const active = a.id === speaking;
        const dim = speaking != null && !active;
        return (
          <div key={a.id} className="absolute bottom-[2%] h-[76%] transition-[left] duration-500" style={{ left: `${x}%`, zIndex: active ? 5 : 1 }}>
            <div className="h-full -translate-x-1/2" style={{ animation: motion ? `vn-enter-${side} .55s var(--ease-out) both` : undefined }}>
              <div className={cx("h-full transition-[filter,transform] duration-300", motion && "vn-breathe")} style={{ filter: dim ? "brightness(.5) saturate(.65)" : "none", transform: dim ? "scale(.965)" : "none", transformOrigin: "50% 100%" }}>
                <div key={active ? reactKey : "idle"} className={cx("h-full", active && motion && reaction && `vn-react-${reaction}`)}>
                  {a.sprite ? (
                    <img src={a.sprite} alt={c?.name ?? ""} className="h-full w-auto max-w-[min(60vw,620px)] object-contain object-bottom [filter:drop-shadow(0_0_1px_rgba(0,0,0,.75))_drop-shadow(0_14px_26px_rgba(0,0,0,.5))]" />
                  ) : (
                    <Silhouette color={c?.color} name={c?.name} />
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Silhouette({ color, name }: { color?: string | null; name?: string }) {
  const fill = cssColor(color ?? "slot:0");
  return (
    <div className="relative flex h-full items-end">
      <svg viewBox="0 0 200 320" className="h-[78%] w-auto opacity-80" aria-hidden>
        <circle cx="100" cy="86" r="48" fill={fill} opacity=".5" />
        <path d="M18 320 C18 196 60 152 100 152 C140 152 182 196 182 320 Z" fill={fill} opacity=".42" />
      </svg>
      {name && <span className="absolute bottom-[18%] left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px] text-white/60">{name}</span>}
    </div>
  );
}

/** The dialogue box: glass and brass, a name plaque, typewriter text and a bobbing continue mark. */
function LineBox({ block, cast, typed, complete }: { block: StageBlock; cast?: StageView["cast"][string]; typed: number; complete: boolean }) {
  const narration = block.type === "narration";
  const name = narration ? null : cast?.name ?? block.speaker;
  const color = cssColor(cast?.color ?? "slot:0");
  return (
    <div className="absolute inset-x-0 bottom-[calc(clamp(10px,2.4%,22px)+14px)] z-30 flex justify-center px-[3%]">
      <div className={cx("panel-glass relative w-[min(1080px,78%)] px-7 pb-6 pt-5 shadow-[0_20px_60px_#000a] max-sm:w-full", block.type === "thought" && "border-dashed")}>
        {name && (
          <div className="absolute -top-5 left-6 flex items-center gap-2">
            <span className="btn-brass !min-h-[34px] !cursor-default !px-4 !text-[14px]" style={{ boxShadow: `inset 0 -3px 0 ${color}` }}>
              {name}
            </span>
            {block.type === "thought" && <span className="plaque !text-[11px] text-[#f3e6cf]/70">thinking</span>}
          </div>
        )}
        <p className={cx("min-h-[3.4em] font-serif text-[clamp(16px,1.35vw,20px)] leading-[1.65] text-[#f3ece4]", (block.type === "thought" || block.type === "action") && "italic text-[#e6dccf]", narration && "text-[#e8dfd3]")}>
          <Rich text={block.text.slice(0, typed)} />
          {!complete && <span className="opacity-0">{block.text.slice(typed)}</span>}
        </p>
        {complete && <span aria-hidden className="absolute bottom-2.5 right-5 text-[13px] text-[#dfb56f]" style={{ animation: "vn-bob 1.1s ease-in-out infinite" }}>▼</span>}
      </div>
    </div>
  );
}

/** A brass plaque that drops from the valance to name the place when a scene starts. */
function PlacePlaque({ name, motion }: { name: string; motion: boolean }) {
  return (
    <div className="pointer-events-none absolute left-1/2 top-[clamp(40px,10.5%,104px)] z-[28] -translate-x-1/2" style={{ animation: motion ? "vn-plaque 3.6s var(--ease-out) both" : "vn-fade .3s both" }}>
      <div className="btn-brass !min-h-[36px] !cursor-default !px-6 capitalize">{name}</div>
    </div>
  );
}

function ChapterPlacard({ stage, loading }: { stage?: StageView; loading: boolean }) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center">
      <div className="text-center" style={{ animation: "vn-placard .7s var(--ease-out) both" }}>
        <div className="mx-auto mb-3 h-10 w-px bg-gradient-to-b from-transparent to-[#dfb56f]" />
        <div className="panel-glass inline-block min-w-[min(520px,86vw)] px-10 py-7">
          <div className="eyebrow !text-[#dfb56f]">{stage ? `Chapter ${stage.chapter.idx + 1} of ${stage.chapter.chapter_count}` : "Next chapter"}</div>
          <div className="mt-2 font-[family-name:var(--font-display)] text-[clamp(28px,4vw,48px)] leading-tight text-[#f3ece4]">{stage ? stage.chapter.title : loading ? "…" : ""}</div>
          {loading && (
            <div className="mt-3 flex justify-center">
              <Spinner size={16} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TitleCard({ play, loading, novelId, onBegin, motion }: { play?: Awaited<ReturnType<typeof api.play>>; loading: boolean; novelId?: number; onBegin: (id: number) => void; motion: boolean }) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center">
      <Petals on={motion} />
      {loading || !play ? (
        <Spinner />
      ) : (
        <div className="relative z-30 px-6 text-center" style={{ animation: "vn-fade .8s ease both" }}>
          <div className="eyebrow !text-[#dfb56f]">The Theatre of Stories presents</div>
          <h1 className="mx-auto mt-4 max-w-4xl font-[family-name:var(--font-display)] text-[clamp(44px,7vw,104px)] leading-[0.95] text-[#f3ece4] drop-shadow-[0_4px_24px_#000]">{play.title}</h1>
          {play.author && <div className="mt-3 font-[family-name:var(--font-display)] text-xl italic text-[#e6dccf]">{play.author}</div>}
          <div className="brass-rule mx-auto mt-7 w-64" />
          <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
            {play.continue && (
              <button className="btn-brass" onClick={() => onBegin(play.continue!.id)}>
                <Play size={15} /> Continue · Chapter {play.continue.idx + 1}
              </button>
            )}
            {play.first ? (
              <button className={play.continue ? "btn-ghost" : "btn-brass"} onClick={() => onBegin(play.first!.id)}>
                <BookOpen size={15} /> Begin
              </button>
            ) : (
              <Link to={novelId ? `/novel/${novelId}` : "/"} className="btn-brass">
                Transform some chapters first
              </Link>
            )}
            <Link to={novelId ? `/novel/${novelId}` : "/"} className="btn-ghost">
              Programme
            </Link>
          </div>
          <div className="mt-5 text-xs text-white/55">
            {play.transformed} of {play.total} chapters staged · {play.ready} with every face designed · Space to advance · A auto · L backlog · F fullscreen
          </div>
        </div>
      )}
    </div>
  );
}

function EndCard({ stage }: { stage?: StageView }) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center text-center">
      <div style={{ animation: "vn-placard .7s var(--ease-out) both" }}>
        <div className="font-[family-name:var(--font-display)] text-5xl italic text-[#f3ece4]">Intermission</div>
        <p className="mt-3 text-sm text-white/70">That's everything staged so far. Transform more chapters to keep going.</p>
        <div className="mt-6 flex justify-center gap-3">
          {stage && (
            <Link className="btn-brass" to={`/novel/${stage.chapter.novel_id}`}>
              Programme
            </Link>
          )}
          {stage && (
            <Link className="btn-ghost" to={`/read/${stage.chapter.id}`}>
              Read in chat mode
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}

function Backlog({ stage, steps, at, onJump, onClose }: { stage: StageView; steps: number[]; at: number; onJump: (k: number) => void; onClose: () => void }) {
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, []);
  return (
    <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-label="Backlog" className="panel-glass flex max-h-[80vh] w-[min(860px,100%)] flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-white/10 px-5 py-3">
          <span className="plaque">Backlog</span>
          <button onClick={onClose} aria-label="Close backlog" className="rounded p-1 text-white/70 hover:text-white">
            <X size={16} />
          </button>
        </div>
        <ol className="overflow-y-auto px-5 py-3">
          {steps.slice(0, at + 1).map((k, n) => {
            const b = stage.blocks[k];
            const who = b.character_id != null ? stage.cast[String(b.character_id)]?.name ?? b.speaker : b.type === "narration" ? null : b.speaker;
            return (
              <li key={k} ref={n === at ? end : undefined}>
                <button onClick={() => onJump(n)} className="block w-full rounded px-2 py-2 text-left hover:bg-white/5">
                  {who && <span className="plaque mr-2 !text-[12px] text-[#dfb56f]">{who}</span>}
                  <span className={cx("font-serif text-[15px] text-[#ece4d8]", (b.type === "thought" || b.type === "action") && "italic")}>{b.text}</span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

function SettingsPanel({ settings, set, onClose }: { settings: VnSettings; set: (p: Partial<VnSettings>) => void; onClose: () => void }) {
  return (
    <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div role="dialog" aria-label="Settings" className="panel-glass w-[min(440px,100%)] space-y-5 px-6 py-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <span className="plaque">Settings</span>
          <button onClick={onClose} aria-label="Close settings" className="rounded p-1 text-white/70 hover:text-white">
            <X size={16} />
          </button>
        </div>
        <label className="block space-y-1.5 text-sm">
          <span className="flex justify-between text-white/80">
            Text speed <span className="text-white/50">{settings.textSpeed === 0 ? "instant" : `${settings.textSpeed} chars/s`}</span>
          </span>
          <input type="range" min={0} max={120} step={5} value={settings.textSpeed} onChange={(e) => set({ textSpeed: Number(e.target.value) })} className="w-full accent-[#dfb56f]" aria-label="Text speed" />
        </label>
        <label className="block space-y-1.5 text-sm">
          <span className="flex justify-between text-white/80">
            Auto-play pause <span className="text-white/50">×{settings.autoDelay.toFixed(1)}</span>
          </span>
          <input type="range" min={0.4} max={2.5} step={0.1} value={settings.autoDelay} onChange={(e) => set({ autoDelay: Number(e.target.value) })} className="w-full accent-[#dfb56f]" aria-label="Auto-play pause" />
        </label>
        <label className="flex items-center justify-between text-sm text-white/80">
          Weather, reactions and screen shake
          <input type="checkbox" checked={settings.effects} onChange={(e) => set({ effects: e.target.checked })} className="h-4 w-4 accent-[#dfb56f]" />
        </label>
        <p className="text-xs text-white/45">Your system's reduced-motion setting always turns movement off.</p>
      </div>
    </div>
  );
}
