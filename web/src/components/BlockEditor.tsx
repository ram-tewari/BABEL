import { useEffect, useState } from "react";
import { Undo2 } from "lucide-react";
import type { Block, BlockType, Character } from "../lib/api";
import { Button, Field, Modal, cx, inputCls } from "./ui";
import { Rich } from "./Scenario";

const TYPES: { value: BlockType; label: string }[] = [
  { value: "dialogue", label: "Dialogue" },
  { value: "thought", label: "Thought" },
  { value: "narration", label: "Narration" },
  { value: "tag", label: "Speech tag" },
  { value: "system", label: "System" },
  { value: "sfx", label: "Sound" },
  { value: "break", label: "Break" },
];

export function BlockEditor({
  block,
  cast,
  onClose,
  onSave,
  onRevert,
  pending,
}: {
  block: Block | null;
  cast: Character[];
  onClose: () => void;
  onSave: (type: BlockType, speaker: string | null) => void;
  onRevert: () => void;
  pending: boolean;
}) {
  const [type, setType] = useState<BlockType>("narration");
  const [speaker, setSpeaker] = useState("");
  useEffect(() => {
    if (!block) return;
    setType(block.type);
    const c = cast.find((x) => x.id === block.character_id);
    setSpeaker(c?.name ?? block.speaker ?? "");
  }, [block, cast]);
  const spoken = type === "dialogue" || type === "thought";

  return (
    <Modal open={!!block} onClose={onClose} title="Correct this line">
      {block && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            onSave(type, spoken ? speaker.trim() || null : null);
          }}
        >
          <blockquote className="max-h-40 overflow-auto rounded-lg border border-line bg-bg px-3 py-2 font-serif text-sm leading-relaxed">
            <Rich text={block.text} />
          </blockquote>
          <Field label="Type">
            <div className="flex flex-wrap gap-1.5" role="radiogroup">
              {TYPES.map((t) => (
                <button
                  type="button"
                  key={t.value}
                  role="radio"
                  aria-checked={type === t.value}
                  onClick={() => setType(t.value)}
                  className={cx(
                    "rounded-full border px-3 py-1 text-[13px]",
                    type === t.value ? "border-accent bg-accent/15 text-text" : "border-line text-muted hover:text-text",
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </Field>
          {spoken && (
            <Field label="Speaker" hint="Pick from the cast or type a new name — new names become characters.">
              <input className={inputCls} list="cast-names" value={speaker} onChange={(e) => setSpeaker(e.target.value)} placeholder="Who says this?" autoFocus />
              <datalist id="cast-names">
                {cast.map((c) => (
                  <option key={c.id} value={c.name} />
                ))}
              </datalist>
            </Field>
          )}
          <div className="flex items-center justify-between gap-2 pt-2">
            {block.edited ? (
              <Button type="button" variant="ghost" size="sm" onClick={onRevert} disabled={pending}>
                <Undo2 size={14} /> Revert to model
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" disabled={pending}>
                Save
              </Button>
            </div>
          </div>
        </form>
      )}
    </Modal>
  );
}
