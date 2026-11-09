import { useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Combine, ImagePlus, Lock, Search, Star, Users, X } from "lucide-react";
import { api, type Entity } from "../lib/api";
import { SLOT_COUNT, cssColor } from "../lib/colors";
import { Avatar, Button, Empty, ErrorNote, Field, Spinner, cx, inputCls } from "./ui";
import { DesignButton } from "./DesignEditor";

export function useCast(novelId: number) {
  return useQuery({ queryKey: ["cast", novelId], queryFn: () => api.entities(novelId, "character"), enabled: novelId > 0 });
}

export function useEntityMutations(novelId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    ["cast", "entities", "chapter", "novel", "graph"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  };
  return {
    patch: useMutation({ mutationFn: (a: { id: number; body: Parameters<typeof api.patchEntity>[1] }) => api.patchEntity(a.id, a.body), onSuccess: refresh }),
    merge: useMutation({ mutationFn: (a: { id: number; into: number }) => api.mergeEntity(a.id, a.into), onSuccess: refresh }),
    addAlias: useMutation({ mutationFn: (a: { id: number; alias: string }) => api.addAlias(a.id, a.alias), onSuccess: refresh }),
    removeAlias: useMutation({ mutationFn: (a: { id: number; alias: string }) => api.removeAlias(a.id, a.alias), onSuccess: refresh }),
    portrait: useMutation({ mutationFn: (a: { id: number; file: File }) => api.uploadPortrait(a.id, a.file), onSuccess: refresh }),
    remove: useMutation({ mutationFn: (id: number) => api.deleteEntity(id), onSuccess: refresh }),
    pov: useMutation({ mutationFn: (cid: number | null) => api.patchNovel(novelId, { pov_character_id: cid }), onSuccess: refresh }),
  };
}

export function CastEditor({ novelId, povId }: { novelId: number; povId: number | null }) {
  const cast = useCast(novelId);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [showMinor, setShowMinor] = useState(false);
  const rows = useMemo(() => {
    let r = cast.data ?? [];
    const needle = q.trim().toLowerCase();
    if (needle) r = r.filter((c) => c.name.toLowerCase().includes(needle) || c.aliases.some((a) => a.toLowerCase().includes(needle)));
    else if (!showMinor) r = r.filter((c) => c.lines >= 3 || c.id === povId || c.locked.length > 0);
    return r;
  }, [cast.data, q, showMinor, povId]);
  const hidden = (cast.data?.length ?? 0) - rows.length;

  if (cast.isLoading) return <Spinner />;
  if (!cast.data?.length)
    return (
      <Empty icon={<Users size={40} />} title="No characters yet">
        Characters are discovered as chapters are transformed — or import a glossary in the Glossary tab.
      </Empty>
    );
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-faint" />
          <input className={cx(inputCls, "pl-9")} placeholder="Find a character or alias…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search cast" />
        </div>
        <span className="text-sm text-muted">{cast.data.length} characters</span>
      </div>
      <ul className="divide-y divide-line rounded-xl border border-line">
        {rows.map((c) => (
          <li key={c.id}>
            <button className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-raised" onClick={() => setOpen(open === c.id ? null : c.id)} aria-expanded={open === c.id}>
              <Avatar character={c} size={34} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-sm font-medium">
                  <span style={{ color: cssColor(c.color) }}>{c.name}</span>
                  {c.is_pov && <Star size={13} className="fill-accent text-accent" aria-label="point of view" />}
                  {c.gender && c.gender !== "n" && <span className="text-xs font-normal text-faint">{c.gender === "m" ? "♂" : "♀"}</span>}
                </div>
                <div className="truncate text-xs text-muted">{c.note ?? (c.aliases.length ? `aka ${c.aliases.slice(0, 4).join(", ")}` : " ")}</div>
              </div>
              <span className="shrink-0 text-xs tabular-nums text-faint">{c.lines.toLocaleString()} lines</span>
            </button>
            {open === c.id && (
              <div className="border-t border-line bg-bg/50 px-4 py-4">
                <CharacterPanel character={c} novelId={novelId} cast={cast.data!} />
              </div>
            )}
          </li>
        ))}
      </ul>
      {!q && hidden > 0 && (
        <button className="mt-3 text-sm text-accent hover:underline" onClick={() => setShowMinor(!showMinor)}>
          {showMinor ? "Hide minor characters" : `Show ${hidden} minor characters`}
        </button>
      )}
    </div>
  );
}

export function CharacterPanel({ character: c, novelId, cast, onDone }: { character: Entity; novelId: number; cast: Entity[]; onDone?: () => void }) {
  const m = useEntityMutations(novelId);
  const factions = useQuery({ queryKey: ["entities", novelId, "faction"], queryFn: () => api.entities(novelId, "faction") });
  const [name, setName] = useState(c.name);
  const [note, setNote] = useState(c.note ?? "");
  const [alias, setAlias] = useState("");
  const [mergeInto, setMergeInto] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const full = cast.find((x) => x.id === c.id) ?? c;
  const err = m.patch.error ?? m.merge.error ?? m.addAlias.error ?? m.removeAlias.error ?? m.pov.error ?? m.portrait.error;
  const others = cast.filter((x) => x.id !== c.id);

  return (
    <div className="space-y-4">
      <div className="flex gap-4">
        <div className="shrink-0 text-center">
          <Avatar character={full} size={64} />
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={(e) => e.target.files?.[0] && m.portrait.mutate({ id: c.id, file: e.target.files[0] })} />
          <button className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-muted hover:text-text" onClick={() => fileRef.current?.click()}>
            <ImagePlus size={12} /> portrait
          </button>
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim() && name.trim() !== c.name) m.patch.mutate({ id: c.id, body: { name: name.trim() } });
            }}
          >
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} aria-label="Display name" />
            <Button type="submit" disabled={!name.trim() || name.trim() === c.name || m.patch.isPending}>
              Rename
            </Button>
          </form>
          <textarea
            className={cx(inputCls, "h-16 py-2")}
            value={note}
            placeholder="Who is this? (shown in tooltips and given to the models as context)"
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => note !== (c.note ?? "") && m.patch.mutate({ id: c.id, body: { note: note || null } })}
            aria-label="Note"
          />
          {full.locked.length > 0 && (
            <p className="flex items-center gap-1 text-[11px] text-faint">
              <Lock size={11} /> You set {full.locked.join(", ")} — models won't change {full.locked.length > 1 ? "them" : "it"}.
            </p>
          )}
        </div>
      </div>

      <Field group label="Color">
        <div className="flex flex-wrap items-center gap-1.5">
          {Array.from({ length: SLOT_COUNT }, (_, i) => `slot:${i}`).map((slot) => (
            <button
              key={slot}
              aria-label={`Color ${slot}`}
              onClick={() => m.patch.mutate({ id: c.id, body: { color: slot } })}
              className={cx("h-6 w-6 rounded-full ring-offset-2 ring-offset-surface", full.color === slot && "ring-2 ring-text")}
              style={{ background: cssColor(slot) }}
            />
          ))}
          <label className="relative h-6 w-6 cursor-pointer overflow-hidden rounded-full border border-dashed border-line" title="Custom color">
            <input type="color" className="absolute inset-0 cursor-pointer opacity-0" value={full.color.startsWith("#") ? full.color : "#888888"} onChange={(e) => m.patch.mutate({ id: c.id, body: { color: e.target.value } })} />
            <span className="flex h-full items-center justify-center text-xs text-muted">+</span>
          </label>
        </div>
      </Field>

      <div className="flex flex-wrap gap-4">
        <Field group label="Chat side">
          <Segmented value={full.side} options={["left", "right"]} onChange={(side) => m.patch.mutate({ id: c.id, body: { side } })} />
        </Field>
        <Field group label="Gender">
          <Segmented value={full.gender ?? "n"} options={["m", "f", "n"]} labels={{ m: "he", f: "she", n: "?" }} onChange={(g) => m.patch.mutate({ id: c.id, body: { gender: g } })} />
        </Field>
        <Field group label="Point of view">
          <Button size="sm" variant={full.is_pov ? "primary" : "outline"} onClick={() => m.pov.mutate(full.is_pov ? null : c.id)}>
            <Star size={13} /> {full.is_pov ? "Protagonist" : "Make protagonist"}
          </Button>
        </Field>
        <Field group label="Look">
          <DesignButton entityId={c.id} novelId={novelId} />
        </Field>
        {(factions.data?.length ?? 0) > 0 && (
          <Field label="Faction">
            <select className={cx(inputCls, "h-8 w-44")} value={full.faction_id ?? ""} onChange={(e) => m.patch.mutate({ id: c.id, body: { faction_id: e.target.value ? Number(e.target.value) : null } })}>
              <option value="">—</option>
              {factions.data!.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>

      <Field group label="Also known as" hint="Any line labeled with one of these names is shown as this character.">
        <AliasChips entity={full} value={alias} setValue={setAlias} onAdd={(a) => m.addAlias.mutate({ id: c.id, alias: a }, { onSuccess: () => setAlias("") })} onRemove={(a) => m.removeAlias.mutate({ id: c.id, alias: a })} />
      </Field>

      {others.length > 0 && (
        <Field group label="Same person as…" hint="Merging moves every line and alias onto the chosen character (e.g. a transmigrator's old and new names).">
          <div className="flex gap-2">
            <select className={inputCls} value={mergeInto} onChange={(e) => setMergeInto(e.target.value)} aria-label="Merge into">
              <option value="">Choose a character</option>
              {others.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} ({o.lines})
                </option>
              ))}
            </select>
            <Button disabled={!mergeInto || m.merge.isPending} onClick={() => m.merge.mutate({ id: c.id, into: Number(mergeInto) }, { onSuccess: () => onDone?.() })}>
              <Combine size={15} /> Merge
            </Button>
          </div>
        </Field>
      )}
      <ErrorNote error={err} />
    </div>
  );
}

export function AliasChips({ entity, onAdd, onRemove, value, setValue }: { entity: Entity; onAdd: (a: string) => void; onRemove: (a: string) => void; value: string; setValue: (v: string) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {entity.aliases.map((a) => (
        <span key={a} className="inline-flex items-center gap-1 rounded-full bg-raised py-0.5 pl-2.5 pr-1 text-xs">
          {a}
          <button aria-label={`Remove alias ${a}`} className="rounded-full p-0.5 text-faint hover:text-text" onClick={() => onRemove(a)}>
            <X size={12} />
          </button>
        </span>
      ))}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (value.trim()) onAdd(value.trim());
        }}
      >
        <input className="h-6 w-32 rounded-full border border-dashed border-line bg-transparent px-2.5 text-xs placeholder:text-faint focus:border-accent focus:outline-none" placeholder="+ add alias" value={value} onChange={(e) => setValue(e.target.value)} aria-label="Add alias" />
      </form>
    </div>
  );
}

export function Segmented<T extends string>({ value, options, labels, onChange }: { value: T; options: T[]; labels?: Partial<Record<T, string>>; onChange: (v: T) => void }) {
  return (
    <div className="flex rounded-lg border border-line p-0.5 text-[13px]" role="group">
      {options.map((o) => (
        <button key={o} aria-pressed={value === o} onClick={() => onChange(o)} className={cx("rounded-md px-3 py-1 capitalize", value === o ? "bg-raised text-text" : "text-muted hover:text-text")}>
          {labels?.[o] ?? o}
        </button>
      ))}
    </div>
  );
}
