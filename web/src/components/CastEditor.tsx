import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Combine, Search, Star, Users, X } from "lucide-react";
import { api, type Character } from "../lib/api";
import { SLOT_COUNT, cssColor } from "../lib/colors";
import { Avatar, Button, Empty, ErrorNote, Field, Spinner, cx, inputCls } from "./ui";

function useCastMutations(novelId: number) {
  const qc = useQueryClient();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["cast", novelId] });
    qc.invalidateQueries({ queryKey: ["chapter"] });
    qc.invalidateQueries({ queryKey: ["novel", novelId] });
  };
  return {
    patch: useMutation({ mutationFn: (a: { id: number; body: Parameters<typeof api.patchCharacter>[1] }) => api.patchCharacter(a.id, a.body), onSuccess: refresh }),
    merge: useMutation({ mutationFn: (a: { id: number; into: number }) => api.mergeCharacter(a.id, a.into), onSuccess: refresh }),
    addAlias: useMutation({ mutationFn: (a: { id: number; alias: string }) => api.addAlias(a.id, a.alias), onSuccess: refresh }),
    removeAlias: useMutation({ mutationFn: (a: { id: number; alias: string }) => api.removeAlias(a.id, a.alias), onSuccess: refresh }),
    pov: useMutation({ mutationFn: (cid: number | null) => api.patchNovel(novelId, { pov_character_id: cid }), onSuccess: refresh }),
  };
}

export function useCast(novelId: number) {
  return useQuery({ queryKey: ["cast", novelId], queryFn: () => api.characters(novelId), enabled: novelId > 0 });
}

export function CastEditor({ novelId, povId }: { novelId: number; povId: number | null }) {
  const cast = useCast(novelId);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [showMinor, setShowMinor] = useState(false);
  const rows = useMemo(() => {
    let r = cast.data ?? [];
    const needle = q.trim().toLowerCase();
    if (needle) r = r.filter((c) => c.name.toLowerCase().includes(needle) || c.aliases?.some((a) => a.toLowerCase().includes(needle)));
    else if (!showMinor) r = r.filter((c) => c.lines >= 3 || c.id === povId);
    return r;
  }, [cast.data, q, showMinor, povId]);
  const hidden = (cast.data?.length ?? 0) - rows.length;

  if (cast.isLoading) return <Spinner />;
  if (!cast.data?.length) {
    return (
      <Empty icon={<Users size={40} />} title="No characters yet">
        Characters are discovered as chapters are transformed.
      </Empty>
    );
  }
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
            <button
              className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-raised"
              onClick={() => setOpen(open === c.id ? null : c.id)}
              aria-expanded={open === c.id}
            >
              <Avatar character={c} size={34} />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-sm font-medium">
                  <span style={{ color: cssColor(c.color) }}>{c.name}</span>
                  {c.is_pov && <Star size={13} className="fill-accent text-accent" aria-label="point of view" />}
                </div>
                <div className="truncate text-xs text-muted">
                  {c.aliases?.length ? `aka ${c.aliases.slice(0, 4).join(", ")}` : c.note ?? " "}
                </div>
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

export function CharacterPanel({ character: c, novelId, cast, onDone }: { character: Character; novelId: number; cast: Character[]; onDone?: () => void }) {
  const m = useCastMutations(novelId);
  const [name, setName] = useState(c.name);
  const [alias, setAlias] = useState("");
  const [mergeInto, setMergeInto] = useState<string>("");
  const full = cast.find((x) => x.id === c.id) ?? c;
  const err = m.patch.error ?? m.merge.error ?? m.addAlias.error ?? m.removeAlias.error ?? m.pov.error;
  const others = cast.filter((x) => x.id !== c.id);

  return (
    <div className="space-y-4">
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

      <Field label="Color">
        <div className="flex flex-wrap items-center gap-1.5">
          {Array.from({ length: SLOT_COUNT }, (_, i) => `slot:${i}`).map((slot) => (
            <button
              key={slot}
              aria-label={`Color ${slot}`}
              onClick={() => m.patch.mutate({ id: c.id, body: { color: slot } })}
              className={cx("h-6 w-6 rounded-full ring-offset-2 ring-offset-surface", c.color === slot && "ring-2 ring-text")}
              style={{ background: cssColor(slot) }}
            />
          ))}
          <label className="relative h-6 w-6 cursor-pointer overflow-hidden rounded-full border border-dashed border-line" title="Custom color">
            <input
              type="color"
              className="absolute inset-0 cursor-pointer opacity-0"
              value={c.color.startsWith("#") ? c.color : "#888888"}
              onChange={(e) => m.patch.mutate({ id: c.id, body: { color: e.target.value } })}
            />
            <span className="flex h-full items-center justify-center text-xs text-muted">+</span>
          </label>
          {full.custom_color && (
            <button className="ml-1 text-xs text-muted hover:text-text" onClick={() => m.patch.mutate({ id: c.id, body: { color: null } })}>
              reset
            </button>
          )}
        </div>
      </Field>

      <div className="flex flex-wrap gap-4">
        <Field label="Chat side">
          <div className="flex rounded-lg border border-line p-0.5 text-[13px]" role="group">
            {(["left", "right"] as const).map((s) => (
              <button
                key={s}
                aria-pressed={c.side === s}
                onClick={() => m.patch.mutate({ id: c.id, body: { side: s } })}
                className={cx("rounded-md px-3 py-1 capitalize", c.side === s ? "bg-raised text-text" : "text-muted hover:text-text")}
              >
                {s}
              </button>
            ))}
          </div>
        </Field>
        <Field label="Point of view">
          <Button size="sm" variant={c.is_pov ? "primary" : "outline"} onClick={() => m.pov.mutate(c.is_pov ? null : c.id)}>
            <Star size={13} /> {c.is_pov ? "Protagonist" : "Make protagonist"}
          </Button>
        </Field>
      </div>

      <Field label="Also known as" hint="Any line labeled with one of these names is shown as this character.">
        <div className="flex flex-wrap gap-1.5">
          {(full.aliases ?? []).map((a) => (
            <span key={a} className="inline-flex items-center gap-1 rounded-full bg-raised py-0.5 pl-2.5 pr-1 text-xs">
              {a}
              <button aria-label={`Remove alias ${a}`} className="rounded-full p-0.5 text-faint hover:text-text" onClick={() => m.removeAlias.mutate({ id: c.id, alias: a })}>
                <X size={12} />
              </button>
            </span>
          ))}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (alias.trim()) m.addAlias.mutate({ id: c.id, alias: alias.trim() }, { onSuccess: () => setAlias("") });
            }}
          >
            <input className="h-6 w-32 rounded-full border border-dashed border-line bg-transparent px-2.5 text-xs placeholder:text-faint focus:border-accent focus:outline-none" placeholder="+ add alias" value={alias} onChange={(e) => setAlias(e.target.value)} />
          </form>
        </div>
      </Field>

      {others.length > 0 && (
        <Field label="Same person as…" hint="Merging moves every line and alias onto the chosen character.">
          <div className="flex gap-2">
            <select className={inputCls} value={mergeInto} onChange={(e) => setMergeInto(e.target.value)}>
              <option value="">Choose a character</option>
              {others.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.name} ({o.lines})
                </option>
              ))}
            </select>
            <Button
              disabled={!mergeInto || m.merge.isPending}
              onClick={() => m.merge.mutate({ id: c.id, into: Number(mergeInto) }, { onSuccess: () => onDone?.() })}
            >
              <Combine size={15} /> Merge
            </Button>
          </div>
        </Field>
      )}
      <ErrorNote error={err} />
    </div>
  );
}
