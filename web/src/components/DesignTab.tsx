import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router";
import { AlertTriangle, BookOpen, Clapperboard, Cpu, Images, Palette, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import { api, type ArtCharacter, type Entity, type NovelArt } from "../lib/api";
import { Avatar, Empty, ErrorNote, Modal, ProgressBar, Spinner, buttonCls, cx, inputCls } from "./ui";
import { useCast } from "./CastEditor";
import { DesignEditor, STATUS_LABEL } from "./DesignEditor";

const SCHEDULER_LABEL: Record<NovelArt["scheduler"]["status"], string> = {
  idle: "Idle",
  waiting: "Waiting",
  paused: "Paused",
  profiling: "Reading the book for",
  staging: "Preparing",
  drawing: "Drawing",
  checking: "Checking",
  unavailable: "Image models not installed",
};

const working = (a?: NovelArt) => !!a && (a.scheduler.queued > 0 || ["profiling", "staging", "drawing", "checking"].includes(a.scheduler.status));

export function DesignTab({ novelId }: { novelId: number }) {
  const qc = useQueryClient();
  const art = useQuery({ queryKey: ["novel-art", novelId], queryFn: () => api.novelArt(novelId), refetchInterval: (q) => (working(q.state.data) ? 3000 : 15_000) });
  const cast = useCast(novelId);
  const [open, setOpen] = useState<ArtCharacter | null>(null);
  const settings = useMutation({
    mutationFn: (body: Partial<NovelArt["settings"]>) => api.setNovelArt(novelId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["novel-art", novelId] }),
  });
  const [setting, setSetting] = useState("");
  const [era, setEra] = useState("");
  useEffect(() => setSetting(art.data?.settings.setting ?? ""), [art.data?.settings.setting]);
  useEffect(() => setEra(art.data?.settings.era ?? ""), [art.data?.settings.era]);

  if (art.isLoading) return <Spinner />;
  if (!art.data) return <ErrorNote error={art.error} />;
  const a = art.data;
  const byId = new Map((cast.data ?? []).map((c) => [c.id, c]));
  const choose = a.characters.filter((c) => c.status === "choose");
  const queue = a.queue.filter((c) => c.status !== "choose");
  const done = a.characters.filter((c) => c.status === "approved");
  const r = a.readiness;

  return (
    <div className="space-y-6">
      <section className="space-y-3 rounded-xl border border-line bg-surface p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className="flex items-center gap-2 font-medium">
            <BookOpen size={16} /> Visual novel
          </h3>
          <span className="text-sm text-muted">
            {r.ready} of {r.transformed} transformed chapters ready
            {r.ready_through !== null && ` · read straight through to chapter ${r.ready_through + 1}`}
          </span>
        </div>
        <ProgressBar value={r.ready} max={Math.max(1, r.transformed)} tone="ok" label="Chapters ready as a visual novel" />
        {r.ready_ids.length > 0 && (
          <Link to={`/vn/${r.ready_ids[0]}`} className={buttonCls("primary", "sm")}>
            <Clapperboard size={14} /> Read as a visual novel
          </Link>
        )}
        <p className="text-xs text-faint">
          A chapter is ready once every main and supporting character who speaks in it has a finished design. Minor characters and extras come from the shared library and never hold a chapter back. Until then, chapters read in chat mode.
        </p>
        {r.blocked.length > 0 && (
          <ul className="space-y-1 text-sm">
            {r.blocked.map((b) => (
              <li key={b.chapter_id} className="text-muted">
                Chapter {b.idx + 1} needs{" "}
                {b.missing.map((name, i) => {
                  const c = a.characters.find((x) => x.name === name);
                  return (
                    <span key={name}>
                      {i > 0 && ", "}
                      {c ? (
                        <button className="text-text underline decoration-line underline-offset-2 hover:decoration-accent" onClick={() => setOpen(c)}>
                          {name}
                        </button>
                      ) : (
                        name
                      )}
                    </span>
                  );
                })}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-wrap items-start gap-4 rounded-xl border border-line p-4">
        <div className="min-w-56 flex-1 space-y-1">
          <p className="flex items-center gap-2 text-sm font-medium">
            {working(a) && <Spinner size={14} />}
            {a.scheduler.images ? SCHEDULER_LABEL[a.scheduler.status] : SCHEDULER_LABEL.unavailable}{" "}
            {a.scheduler.detail && a.scheduler.images && <span className="font-normal text-muted">{a.scheduler.detail}</span>}
          </p>
          {!a.scheduler.images ? (
            <p className="text-xs text-muted">
              Run <code className="rounded bg-raised px-1">babel art setup</code> once (Apple Silicon), then restart <code className="rounded bg-raised px-1">babel serve</code>. You can already write profiles; drawing starts when the models are installed.
            </p>
          ) : (
            <p className="text-xs text-muted">
              {a.scheduler.queued} image{a.scheduler.queued === 1 ? "" : "s"} queued · {a.designed}/{a.needed} characters designed · drawing pauses while chapters are being transformed
            </p>
          )}
          {a.scheduler.checker ? (
            <p className="flex items-center gap-1 text-xs text-muted">
              <ShieldCheck size={12} /> Quality check by {a.scheduler.checker}: {a.scheduler.checked} images checked, {a.scheduler.caught} caught and redrawn
            </p>
          ) : (
            <p className="text-xs text-faint">
              No quality checker: <code className="rounded bg-raised px-1">ollama pull qwen3-vl:4b-instruct</code> to check every image automatically.
            </p>
          )}
          {a.scheduler.error && (
            <p className="flex items-center gap-1 text-xs text-danger">
              <AlertTriangle size={12} /> {a.scheduler.error}
            </p>
          )}
        </div>
        <div className="flex min-w-64 flex-1 flex-col gap-2">
          <label className="flex items-center justify-between gap-3 text-sm">
            <span>
              Design automatically in reading order
              <span className="block text-xs text-faint">Drafts profiles and draws options ahead of you; you pick each look.</span>
            </span>
            <button
              role="switch"
              aria-checked={a.settings.auto}
              aria-label="Design automatically"
              onClick={() => settings.mutate({ auto: !a.settings.auto })}
              className={cx("relative h-6 w-11 shrink-0 rounded-full transition-colors", a.settings.auto ? "bg-accent" : "bg-raised")}
            >
              <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all", a.settings.auto ? "left-[22px]" : "left-0.5")} />
            </button>
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-xs text-muted">Setting: helps the text model describe characters. Style: manhwa.</span>
            <input
              className={cx(inputCls, "h-8 text-sm")}
              value={setting}
              placeholder="Drafted from the book on first use, e.g. Victorian-era city, frock coats and long dresses"
              onChange={(e) => setSetting(e.target.value)}
              onBlur={() => setting !== a.settings.setting && settings.mutate({ setting })}
            />
          </label>
          <label className="space-y-1 text-sm">
            <span className="text-xs text-muted">Clothing era: the only part of the setting that's drawn</span>
            <input
              className={cx(inputCls, "h-8 text-sm")}
              value={era}
              placeholder="e.g. 1880s Victorian"
              onChange={(e) => setEra(e.target.value)}
              onBlur={() => era !== a.settings.era && settings.mutate({ era })}
            />
          </label>
        </div>
      </section>

      <ComputerPanel />

      <LibraryPanel novelId={novelId} />

      {a.needed === 0 && a.characters.length === 0 ? (
        <Empty icon={<Palette size={28} />} title="No characters to design yet">
          Transform some chapters first. Characters who talk become the cast, ordered by when they first appear.
        </Empty>
      ) : (
        <>
          {choose.length > 0 && (
            <CharacterList title="Waiting for your pick" highlight items={choose} byId={byId} onOpen={setOpen} />
          )}
          <CharacterList title="Up next, in reading order" items={queue} byId={byId} onOpen={setOpen} empty="Every main and supporting character has a design." />
          {done.length > 0 && <CharacterList title="Done" items={done} byId={byId} onOpen={setOpen} />}
        </>
      )}
      <ErrorNote error={settings.error} />

      <Modal open={!!open} onClose={() => setOpen(null)} title={open ? `Design: ${open.name}` : ""} wide="xl">
        {open && <DesignEditor entityId={open.id} novelId={novelId} />}
      </Modal>
    </div>
  );
}

function CharacterList({ title, items, byId, onOpen, highlight, empty }: { title: string; items: ArtCharacter[]; byId: Map<number, Entity>; onOpen: (c: ArtCharacter) => void; highlight?: boolean; empty?: string }) {
  return (
    <section className="space-y-2">
      <h3 className={cx("flex items-center gap-2 text-sm font-medium", highlight ? "text-accent" : "text-muted")}>
        {highlight && <Sparkles size={14} />} {title} <span className="font-normal text-faint">{items.length}</span>
      </h3>
      {items.length === 0 ? (
        empty && <p className="text-sm text-muted">{empty}</p>
      ) : (
        <ul className={cx("divide-y divide-line overflow-hidden rounded-xl border", highlight ? "border-accent/40" : "border-line")}>
          {items.map((c) => (
            <li key={c.id}>
              <button className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-raised" onClick={() => onOpen(c)}>
                <Avatar character={byId.get(c.id)} name={c.name} size={32} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{c.name}</span>
                  <span className="block text-xs text-faint">
                    {c.first_idx !== null ? `chapter ${c.first_idx + 1}` : "not placed yet"} · {c.tier} · {c.lines} lines
                  </span>
                </span>
                <span className={cx("shrink-0 rounded-full px-2 py-0.5 text-xs", c.status === "approved" ? "bg-ok/15 text-ok" : c.status === "choose" ? "bg-accent/15 text-accent" : c.status === "failed" ? "bg-danger/15 text-danger" : "bg-raised text-muted")}>
                  {STATUS_LABEL[c.status]}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Switch({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)} className={cx("relative h-6 w-11 shrink-0 rounded-full transition-colors", on ? "bg-accent" : "bg-raised")}>
      <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-surface shadow transition-all", on ? "left-[22px]" : "left-0.5")} />
    </button>
  );
}

const PRESSURE = { 1: "normal", 2: "under pressure", 4: "critical" } as Record<number, string>;

/** How BABEL shares your computer: free memory, and when automatic work may run. */
function ComputerPanel() {
  const qc = useQueryClient();
  const sys = useQuery({ queryKey: ["system"], queryFn: api.system, refetchInterval: 15_000 });
  const prefs = useMutation({ mutationFn: api.setSystemPrefs, onSuccess: () => qc.invalidateQueries({ queryKey: ["system"] }) });
  const s = sys.data;
  if (!s) return null;
  const loaded = Object.entries(s.ollama_loaded);
  const mins = Math.round(s.policy.idle_after_s / 60);
  return (
    <section className="space-y-3 rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <Cpu size={15} /> Your computer
        </h3>
        <span className="text-xs text-muted">
          {s.available_gb !== null && `${Math.round(s.available_gb)} GB free`}
          {s.total_gb !== null && ` of ${Math.round(s.total_gb)} GB`}
          {s.pressure !== null && ` · memory ${PRESSURE[s.pressure] ?? s.pressure}`}
          {s.on_battery !== null && ` · ${s.on_battery ? "on battery" : "plugged in"}`}
          {loaded.length > 0 && ` · loaded: ${loaded.map(([m, gb]) => `${m} (${gb.toFixed(1)} GB)`).join(", ")}`}
        </span>
      </div>
      <p className="text-xs text-faint">
        BABEL only loads a model when there's room for it, releases models soon after use, uses a smaller text model while your apps need the memory, and frees everything if memory gets critical. What you click runs right away; the switches below are for automatic work.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="flex items-center justify-between gap-3 text-sm">
          <span>
            Only while I'm away
            <span className="block text-xs text-faint">Automatic drawing waits until there's been no keyboard or mouse input for {mins} min.</span>
          </span>
          <Switch on={s.policy.background_when === "idle"} label="Only while I'm away" onChange={(v) => prefs.mutate({ background_when: v ? "idle" : "always" })} />
        </label>
        <label className="flex items-center justify-between gap-3 text-sm">
          <span>
            Pause on battery
            <span className="block text-xs text-faint">Automatic drawing waits until you're plugged in.</span>
          </span>
          <Switch on={s.policy.pause_on_battery} label="Pause on battery" onChange={(v) => prefs.mutate({ pause_on_battery: v })} />
        </label>
      </div>
      {!s.background_ok && s.background_reason && <p className="text-xs text-muted">Right now: {s.background_reason}.</p>}
      <ErrorNote error={prefs.error} />
    </section>
  );
}

/** The shared faces (for minor characters) and backgrounds this novel uses — drawn and picked automatically. */
function LibraryPanel({ novelId }: { novelId: number }) {
  const qc = useQueryClient();
  const lib = useQuery({ queryKey: ["library", novelId], queryFn: () => api.library(novelId), refetchInterval: 20_000 });
  const redraw = useMutation({ mutationFn: api.redrawLibrary, onSuccess: () => qc.invalidateQueries({ queryKey: ["library", novelId] }) });
  const defaults = useMutation({ mutationFn: () => api.paintDefaults(novelId), onSuccess: () => qc.invalidateQueries({ queryKey: ["library", novelId] }) });
  const restyle = useMutation({ mutationFn: () => api.restyle(novelId, true), onSuccess: () => qc.invalidateQueries() });
  const items = lib.data?.items ?? [];
  const groups = [
    { kind: "background", title: "Backgrounds" },
    { kind: "extra", title: "Faces for minor characters" },
  ] as const;
  return (
    <section className="space-y-3 rounded-xl border border-line p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-medium">
          <Images size={15} /> Shared library
        </h3>
        <button className="btn-ghost !min-h-[32px] !px-3 !text-[12px]" onClick={() => defaults.mutate()} disabled={defaults.isPending} title="Street, room, pub, office, church, parlour, forest and mist for this novel's era">
          {defaults.isPending ? <Spinner size={12} /> : <Images size={12} />} Paint the default sets
        </button>
        <button
          className="btn-ghost !min-h-[32px] !px-3 !text-[12px]"
          onClick={() => window.confirm("Redraw every character, shared face and set in the current anime style? Everyone keeps their current look on stage until the new one is chosen. It paints while you're idle.") && restyle.mutate()}
          disabled={restyle.isPending}
          title="Redraw everything in the current house style (anime / manhwa)"
        >
          {restyle.isPending ? <Spinner size={12} /> : <Images size={12} />} Redraw all in the current style
        </button>
      </div>
      {restyle.data && <p className="text-xs text-muted">Queued: {restyle.data.characters} characters, {restyle.data.extras} shared faces, {restyle.data.backgrounds} sets. Pick each main character's new look below when the options are ready.</p>}
      <p className="text-xs text-faint">
        Minor characters get a consistent face matched to their role, and places get a background (named places from how the book describes them). They're drawn just ahead of where you're reading, checked automatically, and shared with other novels in the same era. Until a set is painted, scenes use a built-in painted backdrop.
      </p>
      {defaults.data && <p className="text-xs text-muted">{defaults.data.queued ? `Painting ${defaults.data.queued} sets for ${defaults.data.era}…` : "The default sets are already painted or on their way."}</p>}
      {groups.map((g) => {
        const list = items.filter((i) => i.kind === g.kind);
        if (!list.length) return null;
        return (
          <div key={g.kind} className="space-y-1.5">
            <p className="text-xs text-muted">{g.title}</p>
            <div className="flex flex-wrap gap-2">
              {list.map((it) => (
                <figure key={it.entity_id} className="group relative w-28 overflow-hidden rounded-lg border border-line bg-bg" title={it.users.length ? `Used for: ${it.users.join(", ")}` : it.label}>
                  <div className={cx("flex items-center justify-center bg-raised", g.kind === "background" ? "aspect-[1344/768]" : "aspect-[832/1216]")}>
                    {it.thumb ? <img src={it.thumb} alt="" loading="lazy" className="h-full w-full object-cover" /> : it.status === "candidates" || it.status === "sheet" ? <Spinner size={14} /> : <span className="text-[10px] text-faint">queued</span>}
                  </div>
                  <figcaption className="truncate px-1.5 py-1 text-[11px] capitalize text-muted">{it.label}</figcaption>
                  {it.thumb && (
                    <button className="absolute right-1 top-1 rounded bg-black/60 p-1 text-white opacity-0 transition-opacity group-hover:opacity-100" onClick={() => redraw.mutate(it.entity_id)} aria-label={`Redraw ${it.label}`} title="Draw again">
                      <RefreshCw size={11} />
                    </button>
                  )}
                </figure>
              ))}
            </div>
          </div>
        );
      })}
    </section>
  );
}
