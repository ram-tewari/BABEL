import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Expand, Home, MessagesSquare, Minimize, Play, X } from "lucide-react";
import { api, type StageBlock, type StageView } from "../lib/api";
import { cssColor } from "../lib/colors";
import { Rich } from "../components/Scenario";
import { Proscenium } from "../components/Theatre";
import { Spinner, cx } from "../components/ui";
import { PaintedSet } from "./PaintedSet";
import { Motes, Weather } from "./Effects";
import { Colored, LineText, colorize, nameMatcher } from "./LineText";
import { preloadChapter, useChapterPreload } from "./preload";
import * as sound from "./sound";
import { reducedMotion, useVnSettings, type VnSettings } from "./settings";

/** What the stage steps through: speech tags are already shown by the name plate. */
const isStep = (b: StageBlock) => b.type !== "tag" && b.type !== "break" && b.text.trim().length > 0;
type Phase = "title" | "opening" | "play" | "closing" | "card" | "end";
type Scene = StageView["scenes"][number];

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
const chapterName = (title: string) => title.replace(/^\s*chapter\s+\d+\s*[:.\-–—]\s*/i, "").trim() || title;
/** "Chapter 4" as the book numbers it (its own title), falling back to the position in the book. */
const chapterNo = (c: StageView["chapter"]) => {
  const m = /^\s*chapter\s+(\d+)/i.exec(c.title);
  return `Chapter ${m ? m[1] : c.idx + 1}`;
};
const TONE_WORD: Record<string, string> = { whisper: "whispers", shout: "shouts", angry: "angrily", sad: "sadly", laugh: "laughing", nervous: "nervously", cold: "coldly" };

export function Player({ chapterId, novelId, title = false }: { chapterId?: number; novelId?: number; title?: boolean }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [settings, setSettings] = useVnSettings();
  const motion = settings.effects && !reducedMotion();
  const [cid, setCid] = useState<number | undefined>(chapterId);
  const [phase, setPhase] = useState<Phase>(title ? "title" : "opening");
  const [i, setI] = useState(0);
  const [doneKey, setDoneKey] = useState("");
  const [auto, setAuto] = useState(false);
  const [skip, setSkip] = useState(false);
  const [hideUI, setHideUI] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [idle, setIdle] = useState(false);
  const prepared = useRef(new Set<number>());
  const rootRef = useRef<HTMLDivElement>(null);

  const play = useQuery({ queryKey: ["play", novelId], queryFn: () => api.play(novelId!), enabled: !!novelId && title });
  const stage = useQuery({
    queryKey: ["stage", cid],
    queryFn: () => api.stage(cid!),
    enabled: !!cid,
    refetchInterval: (q) => (missingArt(q.state.data) ? 7000 : false),
  });
  const s = stage.data && stage.data.chapter.id === cid ? stage.data : undefined;
  const loaded = useChapterPreload(s);

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
  const scene = s && block ? (s.scenes[block.scene] ?? s.scenes[0]) : undefined;

  // well before the end, fetch the next chapter and decode all of its art, so the curtain never waits
  const nextId = s?.chapter.next_id;
  const nearEnd = !!nextId && steps.length > 0 && at > steps.length * 0.55;
  useEffect(() => {
    if (!nearEnd || !nextId) return;
    prepare(nextId);
    void qc.fetchQuery({ queryKey: ["stage", nextId], queryFn: () => api.stage(nextId), staleTime: 20_000 }).then((v) => preloadChapter(v), () => undefined);
  }, [nearEnd, nextId, qc, prepare]);

  // curtains rise once the chapter is here and every face and set in it is decoded
  useEffect(() => {
    if (phase === "opening" && s && loaded.ready) {
      const t = setTimeout(() => setPhase("play"), 350);
      return () => clearTimeout(t);
    }
  }, [phase, s, loaded.ready]);

  // a line is complete once it has typed out (or at once while skipping / at speed 0)
  const lineKey = `${cid}:${at}`;
  const lineRef = useRef(lineKey);
  lineRef.current = lineKey;
  const complete = skip || settings.textSpeed === 0 || doneKey === lineKey;
  const onTyped = useCallback(() => setDoneKey(lineRef.current), []);

  // save where you are (the regular reader picks up here too)
  useEffect(() => {
    if (!s || phase !== "play") return;
    const t = setTimeout(() => void api.progress(s.chapter.novel_id, s.chapter.id, steps.length ? at / steps.length : 0).catch(() => undefined), 800);
    return () => clearTimeout(t);
  }, [s, at, steps.length, phase]);

  // screen shake on sound effects and shouts (Web Animations: nothing remounts)
  const shakeRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!motion || phase !== "play" || !block || !(block.type === "sfx" || block.tone === "shout")) return;
    shakeRef.current?.animate(
      [{ transform: "translate3d(0,0,0)" }, { transform: "translate3d(-6px,3px,0)" }, { transform: "translate3d(5px,-4px,0)" }, { transform: "translate3d(-3px,2px,0)" }, { transform: "translate3d(0,0,0)" }],
      { duration: 380, easing: "cubic-bezier(.3,.7,.4,1)" },
    );
  }, [block, motion, phase]);

  // sound: unlock on the first interaction, follow the volume, weather ambience per scene
  useEffect(() => sound.setVolume(settings.sound), [settings.sound]);
  useEffect(() => {
    const on = () => sound.unlock();
    window.addEventListener("pointerdown", on);
    window.addEventListener("keydown", on);
    return () => {
      window.removeEventListener("pointerdown", on);
      window.removeEventListener("keydown", on);
      sound.silence();
    };
  }, []);
  useEffect(() => {
    const w = phase === "play" && scene ? scene.weather : null;
    sound.ambience(w === "rain" && !scene?.indoor ? "rain" : (w === "snow" || w === "fog") && !scene?.indoor ? "wind" : null);
  }, [phase, scene]);

  // mouse parallax: the set drifts a little, the cast a little more (CSS variables; no re-render)
  useEffect(() => {
    const el = rootRef.current;
    if (!el || !motion) return;
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = 0;
        el.style.setProperty("--px", ((e.clientX / window.innerWidth) * 2 - 1).toFixed(3));
        el.style.setProperty("--py", ((e.clientY / window.innerHeight) * 2 - 1).toFixed(3));
      });
    };
    window.addEventListener("pointermove", onMove);
    return () => {
      window.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, [motion]);

  // the controls fade away while you read, and come back when the mouse moves
  useEffect(() => {
    let t = setTimeout(() => setIdle(true), 3500);
    const wake = () => {
      setIdle(false);
      clearTimeout(t);
      t = setTimeout(() => setIdle(true), 3500);
    };
    window.addEventListener("pointermove", wake);
    return () => {
      clearTimeout(t);
      window.removeEventListener("pointermove", wake);
    };
  }, []);

  const toNextChapter = useCallback(() => {
    if (!s?.chapter.next_id) {
      setPhase("end");
      return;
    }
    const next = s.chapter.next_id;
    setAuto(false);
    setSkip(false);
    setPhase("closing");
    sound.pageTurn();
    setTimeout(() => {
      setPhase("card");
      sound.swell();
      setCid(next);
      setI(0);
      window.history.replaceState(null, "", `/vn/${next}`);
      setTimeout(() => setPhase("opening"), 2200);
    }, 1350);
  }, [s]);

  const advance = useCallback(() => {
    if (phase !== "play" || !s) return;
    if (!complete) return setDoneKey(lineKey);
    if (at < steps.length - 1) setI(at + 1);
    else toNextChapter();
  }, [phase, s, complete, lineKey, at, steps.length, toNextChapter]);
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

  // scroll up for the backlog, down to advance (the classic VN wheel)
  const lastWheel = useRef(0);
  const onWheel = (e: React.WheelEvent) => {
    if (phase !== "play" || logOpen || settingsOpen) return;
    const now = performance.now();
    if (now - lastWheel.current < 400) return;
    lastWheel.current = now;
    if (e.deltaY < -10) setLogOpen(true);
    else if (e.deltaY > 10) advance();
  };

  const begin = (id: number) => {
    sound.unlock();
    setCid(id);
    setI(0);
    window.history.replaceState(null, "", `/vn/${id}`);
    setPhase("opening");
  };

  const open = phase === "play";
  const actors = useMemo(() => (s && block ? presence(s, steps, at) : []), [s, block, steps, at]);
  const speaking = block && (block.type === "dialogue" || block.type === "thought" || block.type === "action") ? block.character_id : null;
  const names = useMemo(() => nameMatcher(s ? Object.values(s.cast) : []), [s]);
  const showUI = !hideUI && phase === "play";

  return (
    <div
      ref={rootRef}
      className="fixed inset-0 select-none overflow-hidden bg-black text-[#f0e9e3]"
      style={{ ["--px" as string]: 0, ["--py" as string]: 0 }}
      onWheel={onWheel}
      onContextMenu={(e) => {
        if (phase !== "play") return;
        e.preventDefault();
        setHideUI((x) => !x);
      }}
    >
      <div ref={shakeRef} className="vn-layer h-full w-full">
        <Proscenium open={open} rest="away" className="h-full w-full" duration={1300}>
          <div className="absolute inset-0" onClick={() => (hideUI ? setHideUI(false) : advance())}>
            {scene && <Backdrop scene={scene} motion={motion} />}
            {scene && <Weather weather={scene.weather} night={scene.night} indoor={scene.indoor} on={motion} />}
            <div aria-hidden className={cx("pointer-events-none absolute inset-0 z-[8] bg-[radial-gradient(ellipse_at_center,transparent_40%,#0a0f2ecc_100%)] transition-opacity duration-700", block?.type === "thought" ? "opacity-100" : "opacity-0")} />
            {s && <Cast actors={actors} speaking={speaking} cast={s.cast} motion={motion} reactKey={at} reaction={block?.emotion} />}
            {block?.type === "sfx" && open && (
              <div key={at} className="pointer-events-none absolute inset-x-0 top-[28%] z-20 text-center font-[family-name:var(--font-display)] text-[clamp(56px,9vw,128px)] italic leading-none tracking-wide" style={{ animation: motion ? "vn-sfx .5s cubic-bezier(.2,.9,.3,1.2) both" : undefined }}>
                <span className="gold-text drop-shadow-[0_6px_18px_#000]">{block.text}</span>
              </div>
            )}
            {block?.type === "system" && open && (
              <div key={at} className="absolute left-1/2 top-[20%] z-20 w-[min(88%,38rem)] -translate-x-1/2 rounded-xl border border-[#73dde8]/50 bg-[#05141c]/90 px-7 py-6 text-center font-mono text-[15px] leading-relaxed text-[#c9f3f8] shadow-[0_0_60px_#73dde833,inset_0_0_30px_#73dde814]" style={{ animation: "vn-rise .45s var(--ease-out) both" }}>
                <div className="mb-2 text-[10px] uppercase tracking-[.3em] text-[#73dde8]/80">— system —</div>
                <Rich text={block.text} />
              </div>
            )}
            {/* film grain and a soft vignette over everything on stage */}
            <div aria-hidden className="pointer-events-none absolute inset-0 z-[26] bg-[radial-gradient(ellipse_at_50%_42%,transparent_55%,#000000a0_100%)]" />
            {motion && (
              <div aria-hidden className="pointer-events-none absolute inset-[-10%] z-[26] opacity-[.07] mix-blend-overlay">
                <div className="vn-grain h-full w-full" />
              </div>
            )}
            {scene && open && <PlaceCard key={`${cid}-${block?.scene}`} scene={scene} motion={motion} />}
          </div>
        </Proscenium>
      </div>

      {/* the dialogue */}
      {block && showUI && block.type !== "sfx" && block.type !== "system" && (
        <LineBox
          key={cid}
          lineKey={lineKey}
          block={block}
          cast={block.character_id != null ? s?.cast[String(block.character_id)] : undefined}
          names={names}
          speed={settings.textSpeed}
          complete={complete}
          onTyped={onTyped}
          onAdvance={advance}
        >
          <QuickMenu auto={auto} skip={skip} setAuto={setAuto} setSkip={setSkip} onLog={() => setLogOpen(true)} onSettings={() => setSettingsOpen(true)} onHide={() => setHideUI(true)} />
        </LineBox>
      )}

      {/* top: chapter and window controls; fade while you read */}
      {showUI && (
        <div key={cid} className={cx("absolute inset-x-0 top-0 z-40 flex items-start justify-between gap-3 px-[clamp(16px,3vw,40px)] pt-[clamp(14px,2.5vh,28px)] transition-opacity duration-700", idle && "opacity-0")} style={{ animation: "vn-fade .7s 1.05s both" }} onClick={(e) => e.stopPropagation()}>
          <div className="min-w-0" style={{ animation: "vn-rise .8s .4s var(--ease-out) both" }}>
            <div className="plaque !text-[10px] !text-[#dfb56f]/90">{s?.chapter.novel_title}</div>
            <div className="mt-1 truncate font-[family-name:var(--font-display)] text-xl leading-tight text-[#f3ece4]/90 drop-shadow-[0_2px_8px_#000]">{s ? chapterName(s.chapter.title) : ""}</div>
          </div>
          <div className="flex shrink-0 gap-1">
            <IconBtn label={fullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)"} onClick={toggleFullscreen}>
              {fullscreen ? <Minimize size={15} /> : <Expand size={15} />}
            </IconBtn>
            <IconBtn label="Chat mode (Esc)" to={cid ? `/read/${cid}` : "/"}>
              <MessagesSquare size={15} />
            </IconBtn>
            <IconBtn label="Programme" to={s ? `/novel/${s.chapter.novel_id}` : "/"}>
              <Home size={15} />
            </IconBtn>
          </div>
        </div>
      )}

      {/* progress: a hairline of gold */}
      {showUI && s && (
        <div className="absolute inset-x-0 bottom-0 z-40 h-[2px] bg-white/5" aria-hidden>
          <div className="h-full bg-gradient-to-r from-[#dfb56f00] via-[#dfb56f] to-[#f3d595] transition-[width] duration-500 ease-out" style={{ width: `${((at + 1) / Math.max(1, steps.length)) * 100}%` }} />
        </div>
      )}
      {showUI && s && (missingArt(s) || !s.chapter.transformed || s.missing.length > 0) && (
        <div className={cx("absolute right-[clamp(16px,3vw,40px)] top-[calc(clamp(14px,2.5vh,28px)+44px)] z-40 max-w-xs rounded-lg border border-white/10 bg-black/60 px-3 py-2 text-[11px] text-white/75 transition-opacity duration-700", idle && "opacity-0")} onClick={(e) => e.stopPropagation()}>
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
      {/* chapter card while the curtains are closed (and the chapter's art is being decoded) */}
      {(phase === "card" || phase === "opening") && <ChapterCard stage={s} progress={loaded} />}
      {phase === "end" && <EndCard stage={s} />}

      {logOpen && s && <Backlog stage={s} steps={steps} at={at} names={names} onJump={(k) => (setI(k), setLogOpen(false))} onClose={() => setLogOpen(false)} />}
      {settingsOpen && <SettingsPanel settings={settings} set={setSettings} onClose={() => setSettingsOpen(false)} />}
      {stage.isError && <div className="absolute inset-x-0 top-1/2 z-50 text-center text-white/80">Couldn't load this chapter.</div>}
    </div>
  );
}

function IconBtn({ label, onClick, to, children }: { label: string; onClick?: () => void; to?: string; children: React.ReactNode }) {
  const cls = "inline-flex h-9 w-9 items-center justify-center rounded-full border border-white/10 bg-black/35 text-[#f0e9e3]/80 transition-colors hover:border-[#dfb56f]/60 hover:text-white";
  return to ? (
    <Link to={to} className={cls} aria-label={label} title={label}>
      {children}
    </Link>
  ) : (
    <button onClick={onClick} className={cls} aria-label={label} title={label}>
      {children}
    </button>
  );
}

function QuickMenu({ auto, skip, setAuto, setSkip, onLog, onSettings, onHide }: { auto: boolean; skip: boolean; setAuto: (v: boolean) => void; setSkip: (v: boolean) => void; onLog: () => void; onSettings: () => void; onHide: () => void }) {
  return (
    <div className="flex items-center gap-0.5" onClick={(e) => e.stopPropagation()}>
      <button className="vn-ctl" aria-pressed={auto} title="Auto-play (A)" onClick={() => setAuto(!auto)}>
        Auto
      </button>
      <button className="vn-ctl" aria-pressed={skip} title="Skip to the scene's end (S)" onClick={() => setSkip(!skip)}>
        Skip
      </button>
      <button className="vn-ctl" title="Backlog (L, or scroll up)" onClick={onLog}>
        Log
      </button>
      <button className="vn-ctl" title="Settings" onClick={onSettings}>
        Config
      </button>
      <button className="vn-ctl" title="Hide the text (H, or right-click)" onClick={onHide}>
        Hide
      </button>
    </div>
  );
}

/** The scene's set: generated background if drawn, otherwise the painted one. New sets push in and cross-fade. */
const Backdrop = memo(function Backdrop({ scene, motion }: { scene: Scene; motion: boolean }) {
  const key = scene.background ?? `set:${scene.category}:${scene.night}`;
  const [layers, setLayers] = useState<{ key: string; scene: Scene }[]>([{ key, scene }]);
  useEffect(() => {
    setLayers((ls) => (ls[ls.length - 1]?.key === key ? ls : [...ls.slice(-1), { key, scene }]));
    const t = setTimeout(() => setLayers((ls) => ls.slice(-1)), 1400);
    return () => clearTimeout(t);
  }, [key, scene]);
  return (
    <div aria-hidden className="absolute inset-0 overflow-hidden">
      {layers.map((l, n) => (
        <div key={l.key} className="vn-layer absolute inset-0" style={{ animation: n > 0 ? "vn-fade 1.2s ease both" : undefined }}>
          {/* parallax (pointer) → slow drift (Ken Burns) → the art */}
          <div className="vn-layer absolute inset-[-5%]" style={{ transform: "translate3d(calc(var(--px) * -14px), calc(var(--py) * -8px), 0)", transition: "transform 1.2s cubic-bezier(.2,.8,.25,1)" }}>
            <div className="vn-layer h-full w-full" style={{ animation: motion ? "vn-kenburns 40s ease-in-out infinite alternate" : undefined }}>
              <div className="vn-layer h-full w-full" style={{ animation: n > 0 && motion ? "vn-push 1.6s cubic-bezier(.2,.8,.25,1) both" : undefined }}>
                {l.scene.background ? <img src={l.scene.background} alt="" decoding="async" className="h-full w-full object-cover" /> : <PaintedSet category={l.scene.category} night={l.scene.night} />}
              </div>
            </div>
          </div>
          {/* colour grade: night is cool and deep, day is warm; lamps flicker indoors at night */}
          {l.scene.night ? <div className="absolute inset-0 bg-[#0b1838]/50 mix-blend-multiply" /> : <div className="absolute inset-0 bg-[#ffcf8a]/[.07] mix-blend-soft-light" />}
          {l.scene.night && l.scene.indoor && motion && <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_30%_35%,#ffb45a26,transparent_55%)]" style={{ animation: "vn-flicker 4s ease-in-out infinite" }} />}
        </div>
      ))}
      <div className="absolute inset-x-0 bottom-0 h-[55%] bg-gradient-to-t from-black/80 via-black/30 to-transparent" />
    </div>
  );
});

interface Slot {
  a: Actor;
  x: number;
  side: "left" | "right";
  leaving?: boolean;
}

/** The cast on stage: they glide to their marks, breathe, react to the line, and fade out when they leave. */
const Cast = memo(function Cast({ actors, speaking, cast, motion, reactKey, reaction }: { actors: Actor[]; speaking: number | null; cast: StageView["cast"]; motion: boolean; reactKey: number; reaction?: string }) {
  const narrow = typeof window !== "undefined" && window.innerWidth < 640;
  const slots = useMemo(() => {
    const left = actors.filter((a) => cast[String(a.id)]?.side !== "right");
    const right = actors.filter((a) => cast[String(a.id)]?.side === "right");
    const out: Slot[] = [];
    left.slice(0, 2).forEach((a, k) => out.push({ a, x: narrow ? (k ? 40 : 28) : k ? 38 : 24, side: "left" }));
    right.slice(0, 2).forEach((a, k) => out.push({ a, x: narrow ? (k ? 60 : 72) : k ? 62 : 76, side: "right" }));
    if (out.length === 1) out[0].x = narrow ? 50 : out[0].side === "left" ? 30 : 70;
    return out;
  }, [actors, cast, narrow]);

  // keep people who just left for a moment so they can fade out
  const [leaving, setLeaving] = useState<Slot[]>([]);
  const prev = useRef<Slot[]>(slots);
  useEffect(() => {
    const ids = new Set(slots.map((x) => x.a.id));
    const gone = prev.current.filter((x) => !ids.has(x.a.id)).map((x) => ({ ...x, leaving: true }));
    prev.current = slots;
    if (!gone.length) return;
    setLeaving((l) => [...l.filter((x) => !ids.has(x.a.id)), ...gone]);
    // not cleared on the next line: a fast reader must not leave anyone stuck mid-exit
    setTimeout(() => setLeaving((l) => l.filter((x) => !gone.some((g) => g.a.id === x.a.id && x.leaving))), 520);
  }, [slots]);
  const shown = [...slots, ...leaving.filter((x) => !slots.some((y) => y.a.id === x.a.id))];

  return (
    <div className="pointer-events-none absolute inset-0 z-10">
      {shown.map(({ a, x, side, leaving: out }) => {
        const c = cast[String(a.id)];
        const active = a.id === speaking && !out;
        const dim = speaking != null && !active;
        const color = cssColor(c?.color ?? "slot:0");
        return (
          // the mark on stage (transform, so moving between marks is GPU-smooth)
          <div key={a.id} className="vn-layer absolute inset-0" style={{ transform: `translate3d(${x - 50}%,0,0)`, transition: "transform .7s cubic-bezier(.2,.8,.25,1)", zIndex: active ? 5 : 1 }}>
            {/* parallax: the cast sits nearer than the set */}
            <div className="vn-layer absolute inset-0" style={{ transform: "translate3d(calc(var(--px) * -26px), calc(var(--py) * -6px), 0)", transition: "transform 1.2s cubic-bezier(.2,.8,.25,1)" }}>
              <div className="absolute bottom-0 left-1/2 h-[80%] -translate-x-1/2" style={{ animation: out ? "vn-leave .5s ease-in forwards" : motion ? `vn-enter-${side} .8s cubic-bezier(.2,.8,.25,1) both` : undefined }}>
                {/* the speaker's light: a soft glow in their colour */}
                <div aria-hidden className="absolute inset-x-[-20%] bottom-[10%] top-[5%] transition-opacity duration-500" style={{ background: `radial-gradient(ellipse at 50% 35%, color-mix(in oklab, ${color} 40%, transparent), transparent 62%)`, opacity: active ? 0.55 : 0, filter: "blur(10px)" }} />
                <div className={cx("vn-fig relative h-full", motion && "vn-breathe")} style={{ filter: dim ? "brightness(.55) saturate(.7)" : "brightness(1) saturate(1)", transformOrigin: "50% 100%" }}>
                  <div key={active ? reactKey : "idle"} className={cx("h-full", active && motion && reaction && `vn-react-${reaction}`)} style={{ transform: active ? "scale(1.015)" : "scale(1)", transformOrigin: "50% 100%", transition: "transform .5s cubic-bezier(.2,.8,.25,1)" }}>
                    {a.sprite ? <Sprite src={a.sprite} alt={c?.name ?? ""} /> : <Silhouette color={c?.color} name={c?.name} />}
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
});

/** One character image that cross-fades between expressions (all decoded ahead, so it's instant). */
function Sprite({ src, alt }: { src: string; alt: string }) {
  const [layers, setLayers] = useState<string[]>([src]);
  useEffect(() => {
    setLayers((ls) => (ls[ls.length - 1] === src ? ls : [...ls.slice(-1), src]));
    const t = setTimeout(() => setLayers((ls) => ls.slice(-1)), 300);
    return () => clearTimeout(t);
  }, [src]);
  return (
    <div className="relative h-full">
      {layers.map((u, n) => (
        <img
          key={u}
          src={u}
          alt={n === layers.length - 1 ? alt : ""}
          decoding="async"
          className={cx("h-full w-auto max-w-[min(60vw,640px)] object-contain object-bottom [filter:drop-shadow(0_0_1px_rgba(0,0,0,.7))_drop-shadow(0_18px_30px_rgba(0,0,0,.45))]", n > 0 ? "absolute inset-0 m-auto" : "")}
          style={n > 0 ? { animation: "vn-fade .26s ease-out both" } : undefined}
        />
      ))}
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

/** The dialogue: a gradient stage-floor, the speaker's name in their colour, coloured typed text, the quick menu. */
function LineBox({ lineKey, block, cast, names, speed, complete, onTyped, onAdvance, children }: { lineKey: string; block: StageBlock; cast?: StageView["cast"][string]; names: ReturnType<typeof nameMatcher>; speed: number; complete: boolean; onTyped: () => void; onAdvance: () => void; children: React.ReactNode }) {
  const narration = block.type === "narration";
  const thought = block.type === "thought";
  const name = narration ? null : (cast?.name ?? block.speaker);
  const color = cssColor(cast?.color ?? "slot:0");
  const segs = useMemo(() => colorize(block.text, names, { quotes: narration || block.type === "action", marks: block.type === "dialogue" }), [block, names, narration]);
  const tone = block.tone && TONE_WORD[block.tone];
  return (
    // fades in once per chapter, after the curtains have parted
    <div className="absolute inset-x-0 bottom-0 z-30" onClick={onAdvance} style={{ animation: "vn-fade .7s 1.05s both" }}>
      <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-[44vh] bg-gradient-to-t from-[#05070b] via-[#05070bd0] to-transparent" />
      <div className="relative mx-auto w-[min(1120px,92vw)] pb-[clamp(18px,4vh,44px)]">
        <div className="mb-2 flex min-h-[38px] items-end gap-3" key={`${name}-${block.type}`} style={{ animation: "vn-rise .35s var(--ease-out) both" }}>
          {name ? (
            <>
              <span className="font-[family-name:var(--font-display)] text-[clamp(26px,2.4vw,36px)] leading-none" style={{ color, textShadow: `0 0 22px color-mix(in oklab, ${color} 55%, transparent), 0 2px 6px #000` }}>
                {name}
              </span>
              {(thought || tone) && <span className="plaque mb-1 !text-[10px] !text-[#efe6da]/60">{thought ? "thinking" : tone}</span>}
              <span aria-hidden className="mb-2 h-px flex-1" style={{ background: `linear-gradient(90deg, color-mix(in oklab, ${color} 70%, transparent), transparent)` }} />
            </>
          ) : (
            <span aria-hidden className="mb-2 h-px flex-1 bg-gradient-to-r from-transparent via-[#dfb56f]/45 to-transparent" />
          )}
        </div>
        <p
          className={cx(
            "min-h-[3.3em] font-serif text-[clamp(17px,1.4vw,21px)] leading-[1.7] [text-shadow:0_1px_2px_#000c]",
            thought ? "italic text-[#c9d3f2]" : block.type === "action" ? "italic text-[#e6dccf]" : narration ? "text-[#e8e0d4]" : "text-[#fbf6ee]",
            block.tone === "shout" && "text-[1.08em] font-medium",
            block.tone === "whisper" && "text-[.94em] opacity-85",
          )}
        >
          <LineText key={lineKey} segs={segs} speed={speed} done={complete} onDone={onTyped} voice={narration ? null : (block.character_id ?? 0)} tone={block.tone} />
          {complete && <span aria-hidden className="ml-2 inline-block h-2 w-2 rotate-45 border border-[#dfb56f] bg-[#dfb56f]/40 align-middle" style={{ animation: "vn-bob 1.2s ease-in-out infinite" }} />}
        </p>
        <div className="mt-2 flex justify-end opacity-70 transition-opacity hover:opacity-100">{children}</div>
      </div>
    </div>
  );
}

/** The place, written in on the left as a scene opens, then gone. */
function PlaceCard({ scene, motion }: { scene: Scene; motion: boolean }) {
  const when = [scene.night ? "Night" : "Day", scene.weather && scene.weather !== "clear" ? scene.weather : null].filter(Boolean).join(" · ");
  return (
    <div className="pointer-events-none absolute left-[clamp(16px,3vw,40px)] top-[clamp(70px,13vh,120px)] z-[28]" style={{ animation: motion ? "vn-loc 4.6s cubic-bezier(.2,.8,.25,1) .5s both" : "vn-fade .3s both" }}>
      <div className="plaque !text-[10px] !text-[#dfb56f]">{when}</div>
      <div className="mt-1.5 font-[family-name:var(--font-display)] text-[clamp(28px,3vw,42px)] capitalize leading-none text-[#f6efe4] drop-shadow-[0_2px_12px_#000]">{scene.place}</div>
      <div className="mt-2.5 h-px w-40 bg-gradient-to-r from-[#dfb56f] to-transparent" />
    </div>
  );
}

function ChapterCard({ stage, progress }: { stage?: StageView; progress: { done: number; total: number; ready: boolean } }) {
  const pct = progress.total ? progress.done / progress.total : 0;
  return (
    <div className="pointer-events-none absolute inset-0 z-50 flex items-center justify-center px-6">
      <div aria-hidden className="absolute inset-0 bg-[radial-gradient(ellipse_50%_42%_at_50%_50%,#05070bdd,#05070b66_60%,transparent_85%)]" style={{ animation: "vn-fade .8s ease both" }} />
      <div className="relative text-center" style={{ animation: "vn-rise 1s var(--ease-out) both" }}>
        <div className="plaque !text-[#dfb56f]">{stage ? `${stage.chapter.novel_title} · ${chapterNo(stage.chapter)}` : "The next chapter"}</div>
        <div className="mx-auto mt-5 max-w-3xl font-[family-name:var(--font-display)] text-[clamp(40px,6vw,84px)] leading-[1] text-[#f6efe4] drop-shadow-[0_4px_30px_#000]">{stage ? chapterName(stage.chapter.title) : "…"}</div>
        <div className="ornament mx-auto mt-7 w-[min(420px,70vw)] text-[11px]">✦</div>
        <div className="mt-5 h-5 text-[11px] uppercase tracking-[.28em] text-[#efe6da]/55">
          {!stage ? (
            "Raising the curtain…"
          ) : progress.ready ? (
            "Curtain up"
          ) : (
            <span className="inline-flex items-center gap-3">
              Setting the stage
              <span className="relative inline-block h-px w-28 overflow-hidden bg-white/15 align-middle">
                <span className="absolute inset-y-0 left-0 bg-[#dfb56f] transition-[width] duration-300" style={{ width: `${pct * 100}%` }} />
              </span>
              {progress.done}/{progress.total}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function TitleCard({ play, loading, novelId, onBegin, motion }: { play?: Awaited<ReturnType<typeof api.play>>; loading: boolean; novelId?: number; onBegin: (id: number) => void; motion: boolean }) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center">
      {/* a spotlight falls on the closed curtain */}
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_55%_60%_at_50%_42%,#ffe2a833,transparent_70%)]" />
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_50%,transparent_35%,#000000b0_100%)]" />
      <Motes on={motion} count={26} />
      {loading || !play ? (
        <Spinner />
      ) : (
        <div className="relative z-30 px-6 text-center" style={{ animation: "vn-rise 1.1s var(--ease-out) both" }}>
          <div className="plaque !text-[#e9c98d]">The Theatre of Stories presents</div>
          <h1 className="mx-auto mt-5 max-w-5xl font-[family-name:var(--font-display)] text-[clamp(48px,7.5vw,116px)] leading-[0.95] text-[#f8f1e6] [text-shadow:0_4px_40px_#000,0_0_80px_#dfb56f30]">{play.title}</h1>
          {play.author && <div className="mt-4 font-[family-name:var(--font-display)] text-2xl italic text-[#e6dccf]/90">{play.author}</div>}
          <div className="ornament mx-auto mt-8 w-[min(460px,70vw)] text-[11px]">✦</div>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            {play.continue && (
              <button className="btn-brass" onClick={() => onBegin(play.continue!.id)}>
                <Play size={14} /> Continue · Chapter {play.continue.idx + 1}
              </button>
            )}
            {play.first ? (
              <button className={play.continue ? "btn-ghost" : "btn-brass"} onClick={() => onBegin(play.first!.id)}>
                <BookOpen size={14} /> Begin
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
          <div className="mt-7 text-[11px] uppercase tracking-[.22em] text-white/45">
            {play.transformed} of {play.total} chapters staged · {play.ready} fully cast
          </div>
          <div className="mt-2 text-[11px] text-white/35">Space or click to advance · scroll up for the log · right-click hides the text · A auto · F fullscreen</div>
        </div>
      )}
    </div>
  );
}

function EndCard({ stage }: { stage?: StageView }) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center text-center">
      <div style={{ animation: "vn-rise 1s var(--ease-out) both" }}>
        <div className="plaque !text-[#dfb56f]">End of what's staged</div>
        <div className="mt-4 font-[family-name:var(--font-display)] text-6xl italic text-[#f3ece4]">Intermission</div>
        <div className="ornament mx-auto mt-6 w-72 text-[11px]">✦</div>
        <p className="mt-5 text-sm text-white/65">Transform more chapters to keep going.</p>
        <div className="mt-7 flex justify-center gap-3">
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

function Backlog({ stage, steps, at, names, onJump, onClose }: { stage: StageView; steps: number[]; at: number; names: ReturnType<typeof nameMatcher>; onJump: (k: number) => void; onClose: () => void }) {
  const end = useRef<HTMLLIElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, []);
  return (
    <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/70 p-4" style={{ animation: "vn-fade .25s ease both" }} onClick={onClose}>
      <div role="dialog" aria-label="Backlog" className="panel-glass flex max-h-[82vh] w-[min(880px,100%)] flex-col" style={{ animation: "vn-rise .35s var(--ease-out) both" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between border-b border-[#dfb56f]/15 px-6 py-4">
          <span className="font-[family-name:var(--font-display)] text-2xl text-[#f3ece4]">Backlog</span>
          <button onClick={onClose} aria-label="Close backlog" className="rounded-full p-1.5 text-white/70 hover:bg-white/10 hover:text-white">
            <X size={16} />
          </button>
        </div>
        <ol className="overflow-y-auto px-4 py-3">
          {steps.slice(0, at + 1).map((k, n) => {
            const b = stage.blocks[k];
            const c = b.character_id != null ? stage.cast[String(b.character_id)] : undefined;
            const who = c?.name ?? (b.type === "narration" ? null : b.speaker);
            const segs = colorize(b.text, names, { quotes: b.type === "narration", marks: b.type === "dialogue" });
            return (
              <li key={k} ref={n === at ? end : undefined}>
                <button onClick={() => onJump(n)} className="block w-full rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-white/[.04]">
                  {who && (
                    <span className="mb-0.5 block font-[family-name:var(--font-display)] text-lg leading-tight" style={{ color: cssColor(c?.color ?? "slot:0") }}>
                      {who}
                    </span>
                  )}
                  <span className={cx("font-serif text-[15px] leading-relaxed text-[#ece4d8]", (b.type === "thought" || b.type === "action") && "italic", b.type === "thought" && "text-[#c9d3f2]")}>
                    <Colored segs={segs} />
                  </span>
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
    <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/70 p-4" style={{ animation: "vn-fade .25s ease both" }} onClick={onClose}>
      <div role="dialog" aria-label="Settings" className="panel-glass w-[min(460px,100%)] space-y-6 px-7 py-6" style={{ animation: "vn-rise .35s var(--ease-out) both" }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <span className="font-[family-name:var(--font-display)] text-2xl text-[#f3ece4]">Config</span>
          <button onClick={onClose} aria-label="Close settings" className="rounded-full p-1.5 text-white/70 hover:bg-white/10 hover:text-white">
            <X size={16} />
          </button>
        </div>
        <Slider label="Text speed" value={settings.textSpeed} min={0} max={120} step={5} show={settings.textSpeed === 0 ? "instant" : `${settings.textSpeed} chars/s`} onChange={(v) => set({ textSpeed: v })} />
        <Slider label="Auto-play pause" value={settings.autoDelay} min={0.4} max={2.5} step={0.1} show={`×${settings.autoDelay.toFixed(1)}`} onChange={(v) => set({ autoDelay: v })} />
        <Slider label="Sound" value={settings.sound} min={0} max={1} step={0.05} show={settings.sound === 0 ? "off" : `${Math.round(settings.sound * 100)}%`} onChange={(v) => set({ sound: v })} />
        <label className="flex items-center justify-between text-sm text-white/80">
          Weather, parallax, reactions and screen shake
          <input type="checkbox" checked={settings.effects} onChange={(e) => set({ effects: e.target.checked })} className="h-4 w-4 accent-[#dfb56f]" />
        </label>
        <p className="text-xs text-white/40">Your system's reduced-motion setting always turns movement off.</p>
      </div>
    </div>
  );
}

function Slider({ label, value, min, max, step, show, onChange }: { label: string; value: number; min: number; max: number; step: number; show: string; onChange: (v: number) => void }) {
  return (
    <label className="block space-y-2 text-sm">
      <span className="flex justify-between text-white/80">
        {label} <span className="font-mono text-xs text-[#e9c98d]/80">{show}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-[#dfb56f]" aria-label={label} />
    </label>
  );
}
