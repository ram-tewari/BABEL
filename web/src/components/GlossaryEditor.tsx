import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Plus, Trash2, Upload } from "lucide-react";
import { api, type Entity, type EntityKind } from "../lib/api";
import { cssColor } from "../lib/colors";
import { AliasChips, useEntityMutations } from "./CastEditor";
import { Button, ErrorNote, Spinner, buttonCls, cx, inputCls } from "./ui";

const KINDS: { kind: Exclude<EntityKind, "character">; label: string; hint: string }[] = [
  { kind: "location", label: "Places", hint: "cities, realms, buildings" },
  { kind: "faction", label: "Factions", hint: "organizations, families, churches" },
  { kind: "term", label: "Terms", hint: "skills, items, titles, concepts" },
];

/** Locations, factions and terms in the Akashic Record, plus glossary YAML import/export. */
export function GlossaryEditor({ novelId }: { novelId: number }) {
  const qc = useQueryClient();
  const [kind, setKind] = useState<Exclude<EntityKind, "character">>("location");
  const list = useQuery({ queryKey: ["entities", novelId, kind], queryFn: () => api.entities(novelId, kind) });
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const create = useMutation({
    mutationFn: () => api.createEntity(novelId, { name: name.trim(), kind, note: note.trim() || null }),
    onSuccess: () => {
      setName("");
      setNote("");
      qc.invalidateQueries({ queryKey: ["entities"] });
    },
  });
  const fileRef = useRef<HTMLInputElement>(null);
  const importer = useMutation({
    mutationFn: async (f: File) => api.importGlossary(novelId, await f.text()),
    onSuccess: () => ["entities", "cast", "chapter"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })),
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface p-4 text-sm">
        <div className="min-w-0 flex-1 text-muted">
          The Akashic Record is BABEL's memory of this novel. Notes here are shown as tooltips in the reader and given to the models as context. Anything you write is never overwritten.
        </div>
        <a className={buttonCls("outline", "sm")} href={api.glossaryUrl(novelId)} download>
          <Download size={14} /> Export YAML
        </a>
        <input ref={fileRef} type="file" accept=".yaml,.yml,text/yaml" hidden onChange={(e) => e.target.files?.[0] && importer.mutate(e.target.files[0])} />
        <Button size="sm" onClick={() => fileRef.current?.click()} disabled={importer.isPending}>
          <Upload size={14} /> Import YAML
        </Button>
      </div>
      {importer.data && <p className="text-sm text-ok">Imported: {importer.data.created} new, {importer.data.updated} updated.</p>}
      <ErrorNote error={importer.error} />

      <div className="flex gap-1 border-b border-line" role="tablist">
        {KINDS.map((k) => (
          <button key={k.kind} role="tab" aria-selected={kind === k.kind} onClick={() => setKind(k.kind)} className={cx("-mb-px border-b-2 px-3 py-2 text-sm", kind === k.kind ? "border-accent text-text" : "border-transparent text-muted hover:text-text")}>
            {k.label}
          </button>
        ))}
      </div>

      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) create.mutate();
        }}
      >
        <input className={cx(inputCls, "w-48")} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} aria-label="Name" />
        <input className={cx(inputCls, "min-w-48 flex-1")} placeholder={`Note (${KINDS.find((k) => k.kind === kind)!.hint})`} value={note} onChange={(e) => setNote(e.target.value)} aria-label="Note" />
        <Button type="submit" disabled={!name.trim() || create.isPending}>
          <Plus size={15} /> Add
        </Button>
      </form>
      <ErrorNote error={create.error} />

      {list.isLoading ? (
        <Spinner />
      ) : list.data!.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted">Nothing here yet. Models add entries as they read; you can add your own.</p>
      ) : (
        <ul className="divide-y divide-line rounded-xl border border-line">
          {list.data!.map((e) => (
            <EntityRow key={e.id} entity={e} novelId={novelId} />
          ))}
        </ul>
      )}
    </div>
  );
}

function EntityRow({ entity: e, novelId }: { entity: Entity; novelId: number }) {
  const m = useEntityMutations(novelId);
  const [note, setNote] = useState(e.note ?? "");
  const [alias, setAlias] = useState("");
  return (
    <li className="space-y-2 px-4 py-3">
      <div className="flex items-center gap-3">
        {e.kind === "faction" && (
          <label className="relative h-5 w-5 shrink-0 cursor-pointer overflow-hidden rounded-full" style={{ background: cssColor(e.color) }} title="Faction color (used in the character graph)">
            <input type="color" className="absolute inset-0 opacity-0" value={e.color.startsWith("#") ? e.color : "#888888"} onChange={(ev) => m.patch.mutate({ id: e.id, body: { color: ev.target.value } })} />
          </label>
        )}
        <span className="text-sm font-medium">{e.name}</span>
        <button className="ml-auto text-faint hover:text-danger" aria-label={`Delete ${e.name}`} onClick={() => m.remove.mutate(e.id)}>
          <Trash2 size={15} />
        </button>
      </div>
      <input
        className={cx(inputCls, "h-8")}
        value={note}
        placeholder="Add a note…"
        onChange={(ev) => setNote(ev.target.value)}
        onBlur={() => note !== (e.note ?? "") && m.patch.mutate({ id: e.id, body: { note: note || null } })}
        aria-label={`Note for ${e.name}`}
      />
      <AliasChips entity={e} value={alias} setValue={setAlias} onAdd={(a) => m.addAlias.mutate({ id: e.id, alias: a }, { onSuccess: () => setAlias("") })} onRemove={(a) => m.removeAlias.mutate({ id: e.id, alias: a })} />
    </li>
  );
}
