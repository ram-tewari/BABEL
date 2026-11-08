import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ExternalLink, Lock, Paintbrush, Palette, RefreshCw, RotateCcw, Wand2 } from "lucide-react";
import { api, type ArtImage, type ArtTier, type DesignStatus, type DesignView, type Profile } from "../lib/api";
import { Button, ErrorNote, Modal, Spinner, cx, inputCls } from "./ui";

export const STATUS_LABEL: Record<DesignStatus, string> = {
  new: "No design yet",
  profiled: "Profile ready",
  candidates: "Drawing options…",
  choose: "Pick a look",
  sheet: "Drawing expressions…",
  approved: "Done",
  failed: "Needs attention",
};

export const TIER_HELP: Record<ArtTier, string> = {
  main: "Main cast: gets its own design",
  supporting: "Supporting: gets its own design",
  minor: "Minor: uses the shared extras library",
  extra: "Extra: uses the shared extras library",
};

const busy = (d?: DesignView) =>
  !!d && (d.status === "candidates" || d.status === "sheet" || d.candidates.some((c) => c.status === "queued" || c.status === "running"));

export function useDesign(entityId: number) {
  return useQuery({
    queryKey: ["design", entityId],
    queryFn: () => api.design(entityId),
    refetchInterval: (q) => (busy(q.state.data) ? 2500 : false),
  });
}

export function DesignEditor({ entityId, novelId }: { entityId: number; novelId: number }) {
  const qc = useQueryClient();
  const meta = useQuery({ queryKey: ["art-meta"], queryFn: api.artMeta, staleTime: 60_000 });
  const q = useDesign(entityId);
  const d = q.data;
  const set = (v: DesignView) => {
    qc.setQueryData(["design", entityId], v);
    qc.invalidateQueries({ queryKey: ["novel-art", novelId] });
    qc.invalidateQueries({ queryKey: ["entities", novelId] });
  };
  const draft = useMutation({ mutationFn: () => api.draftProfile(entityId), onSuccess: set });
  const save = useMutation({ mutationFn: (p: Profile) => api.saveProfile(entityId, p), onSuccess: set });
  const draw = useMutation({ mutationFn: () => api.drawCandidates(entityId), onSuccess: set });
  const approve = useMutation({ mutationFn: (id: number) => api.approveImage(id), onSuccess: set });
  const reroll = useMutation({ mutationFn: (id: number) => api.rerollImage(id), onSuccess: set });
  const reset = useMutation({ mutationFn: () => api.resetDesign(entityId), onSuccess: set });
  const tier = useMutation({ mutationFn: (t: ArtTier | null) => api.setArtTier(entityId, t), onSuccess: set });
  const [picked, setPicked] = useState<number | null>(null);

  if (q.isLoading || !d) return <Spinner />;
  const err = draft.error ?? save.error ?? draw.error ?? approve.error ?? reroll.error ?? reset.error ?? tier.error ?? q.error;
  const candidates = d.candidates;
  const drawing = candidates.some((c) => c.status === "queued" || c.status === "running");
  const art = meta.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className={cx("rounded-full px-2.5 py-0.5 text-xs font-medium", d.status === "approved" ? "bg-ok/15 text-ok" : d.status === "choose" ? "bg-accent/15 text-accent" : "bg-raised text-muted")}>
          {STATUS_LABEL[d.status]}
        </span>
        <span className="text-muted">
          {d.first_idx !== null ? `first appears in chapter ${d.first_idx + 1} · ` : ""}
          {d.lines} lines
        </span>
        <label className="ml-auto flex items-center gap-1.5 text-xs text-muted">
          Importance
          <select
            className={cx(inputCls, "h-7 w-36 py-0 text-xs")}
            value={d.tier_locked ? d.tier : ""}
            onChange={(e) => tier.mutate((e.target.value || null) as ArtTier | null)}
            aria-label="Importance"
          >
            <option value="">Automatic ({d.tier})</option>
            {(["main", "supporting", "minor", "extra"] as ArtTier[]).map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="-mt-4 text-xs text-faint">{TIER_HELP[d.tier]}</p>
      {d.message && <p className="rounded-lg bg-raised px-3 py-2 text-sm text-muted">{d.message}</p>}

      <ProfileForm design={d} fields={art?.fields ?? []} onSave={(p) => save.mutate(p)} saving={save.isPending}>
        <Button size="sm" variant="ghost" onClick={() => draft.mutate()} disabled={draft.isPending} title="Read the book's descriptions of this character and fill the profile (keeps fields you edited)">
          {draft.isPending ? <Spinner size={14} /> : <Wand2 size={14} />} Read the book
        </Button>
      </ProfileForm>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">1 · Pick a look</h3>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => draw.mutate()} disabled={!d.profile || draw.isPending || drawing} title={!d.profile ? "Fill in the profile first" : undefined}>
              <Paintbrush size={14} /> {candidates.length ? "Draw 6 more" : "Draw 6 options"}
            </Button>
            {picked !== null && (
              <Button size="sm" variant="primary" onClick={() => approve.mutate(picked, { onSuccess: () => setPicked(null) })} disabled={approve.isPending}>
                <Check size={14} /> Use this look
              </Button>
            )}
          </div>
        </div>
        {candidates.length === 0 ? (
          <p className="text-sm text-muted">Options are drawn from the profile. Pick the one that matches how you imagine them; every expression is made from it.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {candidates
              .slice()
              .reverse()
              .map((c) => (
                <Tile
                  key={c.id}
                  img={c}
                  selected={picked === c.id || (picked === null && d.base_image_id === c.id)}
                  badge={d.base_image_id === c.id ? "chosen" : undefined}
                  onClick={() => c.status === "done" && setPicked(c.id)}
                />
              ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-medium">2 · Expressions</h3>
          {d.base_image_id && (
            <Button size="sm" variant="ghost" onClick={() => reset.mutate()} disabled={reset.isPending} title="Start over with new options (the profile is kept)">
              <RotateCcw size={14} /> Start over
            </Button>
          )}
        </div>
        {!d.base_image_id ? (
          <p className="text-sm text-muted">Once you pick a look, the expression sheet is drawn from it automatically. The reader picks one per line from its tone.</p>
        ) : (
          <div className="grid grid-cols-4 gap-2 lg:grid-cols-8">
            {(art?.emotions ?? Object.keys(d.sheet)).map((e) => {
              const img = d.sheet[e];
              return (
                <div key={e} className="space-y-1">
                  <Tile img={img} label={e} onReroll={img && e !== "neutral" && img.status !== "queued" && img.status !== "running" ? () => reroll.mutate(img.id) : undefined} />
                </div>
              );
            })}
          </div>
        )}
      </section>
      <ErrorNote error={err} />
    </div>
  );
}

function Tile({ img, label, selected, badge, onClick, onReroll }: { img: ArtImage | null; label?: string; selected?: boolean; badge?: string; onClick?: () => void; onReroll?: () => void }) {
  const done = img?.status === "done" && img.thumb;
  return (
    <div className={cx("group relative overflow-hidden rounded-lg border bg-bg", selected ? "border-accent ring-2 ring-accent/40" : "border-line")}>
      <button type="button" onClick={onClick} disabled={!onClick || !done} className="block aspect-[832/1216] w-full" aria-label={label ? `${label} expression` : `Option ${img?.id ?? ""}`}>
        {done ? (
          <img src={img!.thumb!} alt="" loading="lazy" className="h-full w-full object-cover" />
        ) : img?.status === "failed" ? (
          <span className="flex h-full items-center justify-center p-2 text-center text-[11px] text-danger" title={img.error ?? ""}>
            failed
          </span>
        ) : (
          <span className="flex h-full items-center justify-center">{img ? <Spinner size={16} /> : <span className="text-xs text-faint">—</span>}</span>
        )}
      </button>
      {label && <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pb-1 pt-4 text-center text-[11px] capitalize text-white">{label}</span>}
      {badge && <span className="absolute left-1 top-1 rounded bg-accent px-1.5 text-[10px] font-medium text-accent-ink">{badge}</span>}
      <div className="absolute right-1 top-1 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
        {done && (
          <a href={img!.url!} target="_blank" rel="noreferrer" className="rounded bg-black/60 p-1 text-white" aria-label="Open full size">
            <ExternalLink size={12} />
          </a>
        )}
        {onReroll && (
          <button type="button" onClick={onReroll} className="rounded bg-black/60 p-1 text-white" aria-label={`Redraw ${label}`} title="Redraw this expression">
            <RefreshCw size={12} />
          </button>
        )}
      </div>
    </div>
  );
}

function ProfileForm({ design: d, fields, onSave, saving, children }: { design: DesignView; fields: { key: string; label: string }[]; onSave: (p: Profile) => void; saving: boolean; children: React.ReactNode }) {
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [tags, setTags] = useState("");
  useEffect(() => {
    const p = d.profile;
    setDraft(Object.fromEntries(fields.map((f) => [f.key, p?.[f.key]?.value ?? ""])));
    setTags((p?.tags ?? []).join(", "));
  }, [d.profile, fields]);
  const dirty = !!fields.length && (fields.some((f) => (d.profile?.[f.key]?.value ?? "") !== (draft[f.key] ?? "")) || (d.profile?.tags ?? []).join(", ") !== tags);

  const submit = () => {
    const p: Profile = {} as Profile;
    for (const f of fields) {
      const old = d.profile?.[f.key];
      if ((old?.value ?? "") !== draft[f.key]) p[f.key] = { value: draft[f.key], guessed: false, chapter: null, quote: "" };
    }
    if ((d.profile?.tags ?? []).join(", ") !== tags) p.tags = tags.split(",").map((t) => t.trim()).filter(Boolean);
    onSave(p);
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-medium">Appearance</h3>
        <div className="flex gap-2">
          {children}
          {dirty && (
            <Button size="sm" variant="primary" onClick={submit} disabled={saving}>
              Save
            </Button>
          )}
        </div>
      </div>
      {!d.profile && <p className="text-sm text-muted">“Read the book” drafts this from the novel's own descriptions, citing the chapter for each detail. Anything the book doesn't say is marked as a guess. Your edits are never overwritten.</p>}
      <div className="grid gap-x-4 gap-y-2.5 sm:grid-cols-2">
        {fields.map((f) => {
          const pf = d.profile?.[f.key];
          const locked = d.profile_locked.includes(f.key);
          return (
            <label key={f.key} className="block space-y-1">
              <span className="flex items-center gap-1.5 text-xs text-muted">
                {f.label}
                {locked ? (
                  <span className="inline-flex items-center gap-0.5 text-faint" title="You set this; the model won't change it">
                    <Lock size={10} /> yours
                  </span>
                ) : pf?.guessed && pf.value ? (
                  <span className="rounded bg-raised px-1 text-[10px] text-faint" title="The book doesn't say; this is a guess">
                    guess
                  </span>
                ) : pf?.chapter ? (
                  <span className="truncate text-[10px] text-faint" title={pf.quote}>
                    ch {pf.chapter}: “{pf.quote}”
                  </span>
                ) : null}
              </span>
              <input className={cx(inputCls, "h-8 text-sm")} value={draft[f.key] ?? ""} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })} />
            </label>
          );
        })}
      </div>
      {fields.length > 0 && (
        <label className="block space-y-1">
          <span className="text-xs text-muted">Illustration tags</span>
          <input className={cx(inputCls, "h-8 text-sm")} value={tags} onChange={(e) => setTags(e.target.value)} placeholder="black hair, brown eyes, frock coat" />
        </label>
      )}
    </section>
  );
}

export function DesignButton({ entityId, novelId }: { entityId: number; novelId: number }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size="sm" onClick={() => setOpen(true)}>
        <Palette size={14} /> Design
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Character design" wide="xl">
        {open && <DesignEditor entityId={entityId} novelId={novelId} />}
      </Modal>
    </>
  );
}
