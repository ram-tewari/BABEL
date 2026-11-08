import { useEffect, useState } from "react";
import { Check, Undo2 } from "lucide-react";
import { TIER_LABEL, TONES, type Block, type BlockType, type Entity, type Tone } from "../lib/api";
import { Button, Field, Modal, cx, inputCls } from "./ui";
import { Rich } from "./Scenario";

const TYPES: { value: BlockType; label: string }[] = [
  { value: "dialogue", label: "Dialogue" },
  { value: "thought", label: "Thought" },
  { value: "action", label: "Action beat" },
  { value: "narration", label: "Narration" },
  { value: "tag", label: "Speech tag" },
  { value: "system", label: "System" },
  { value: "sfx", label: "Sound" },
  { value: "break", label: "Break" },
];

export interface EditResult {
  type: BlockType;
  speaker: string | null;
  tone: Tone | null;
}

export function BlockEditor({
  block,
  cast,
  onClose,
  onSave,
  onAccept,
  onRevert,
  pending,
}: {
  block: Block | null;
  cast: Entity[];
  onClose: () => void;
  onSave: (r: EditResult) => void;
  onAccept: () => void;
  onRevert: () => void;
  pending: boolean;
}) {
  const [type, setType] = useState<BlockType>("narration");
  const [speaker, setSpeaker] = useState("");
  const [tone, setTone] = useState<Tone | null>(null);
  useEffect(() => {
    if (!block) return;
    setType(block.type);
    setSpeaker(cast.find((x) => x.id === block.character_id)?.name ?? block.speaker ?? "");
    setTone(block.tone);
  }, [block, cast]);
  const withSpeaker = type === "dialogue" || type === "thought" || type === "action";
  const save = (sp = speaker) => onSave({ type, speaker: withSpeaker ? sp.trim() || null : null, tone: type === "dialogue" ? tone : null });

  return (
    <Modal open={!!block} onClose={onClose} title="Correct this line">
      {block && (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <blockquote className="max-h-40 overflow-auto rounded-lg border border-line bg-bg px-3 py-2 font-serif text-sm leading-relaxed">
            <Rich text={block.text} />
          </blockquote>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
            <span>
              Decided by <b className="text-text">{TIER_LABEL[block.tier]}</b> · {Math.round(block.conf * 100)}% sure
            </span>
            {block.why && <span className="text-faint">— {block.why}</span>}
          </div>

          <Field group label="Type">
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Block type">
              {TYPES.map((t) => (
                <button
                  type="button"
                  key={t.value}
                  role="radio"
                  aria-checked={type === t.value}
                  onClick={() => setType(t.value)}
                  className={cx("rounded-full border px-3 py-1 text-[13px]", type === t.value ? "border-accent bg-accent/15 text-text" : "border-line text-muted hover:text-text")}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </Field>

          {withSpeaker && (
            <Field group label={type === "action" ? "Who does this" : "Speaker"} hint="Pick a suggestion, choose from the cast, or type a new name.">
              {block.candidates.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {block.candidates.map((c) => (
                    <button
                      type="button"
                      key={c}
                      onClick={() => setSpeaker(c)}
                      onDoubleClick={() => save(c)}
                      className={cx("rounded-full border px-3 py-1 text-[13px]", speaker === c ? "border-accent bg-accent/15" : "border-line text-muted hover:text-text")}
                    >
                      {c}
                    </button>
                  ))}
                </div>
              )}
              <input className={inputCls} list="cast-names" value={speaker} onChange={(e) => setSpeaker(e.target.value)} placeholder="Who?" aria-label="Speaker" />
              <datalist id="cast-names">
                {cast.map((c) => (
                  <option key={c.id} value={c.name} />
                ))}
              </datalist>
            </Field>
          )}

          {type === "dialogue" && (
            <Field group label="Tone">
              <div className="flex flex-wrap gap-1.5">
                {[null, ...TONES].map((t) => (
                  <button
                    type="button"
                    key={t ?? "none"}
                    onClick={() => setTone(t)}
                    aria-pressed={tone === t}
                    className={cx("rounded-full border px-2.5 py-0.5 text-[12px]", tone === t ? "border-accent bg-accent/15" : "border-line text-muted hover:text-text")}
                  >
                    {t ?? "normal"}
                  </button>
                ))}
              </div>
            </Field>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <div className="flex gap-1">
              {block.edited ? (
                <Button type="button" variant="ghost" size="sm" onClick={onRevert} disabled={pending}>
                  <Undo2 size={14} /> Revert
                </Button>
              ) : (
                <Button type="button" variant="ghost" size="sm" onClick={onAccept} disabled={pending} title="The pipeline got this right">
                  <Check size={14} /> It's correct
                </Button>
              )}
            </div>
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
