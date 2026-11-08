import { TIER_LABEL, type Tier } from "../lib/api";

const ORDER: Tier[] = ["rule", "memory", "local", "cloud", "user"];
export const TIER_COLOR: Record<Tier, string> = {
  rule: "var(--slot-7)",
  memory: "var(--slot-5)",
  local: "var(--slot-2)",
  cloud: "var(--slot-9)",
  user: "var(--accent)",
};

/** Who decided the dialogue & thought lines: rules, memory, local model, cloud model or you. */
export function TierBar({ counts, compact }: { counts: Partial<Record<Tier, number>>; compact?: boolean }) {
  const total = ORDER.reduce((n, t) => n + (counts[t] ?? 0), 0);
  if (!total) return null;
  return (
    <div>
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-raised" role="img" aria-label="Who decided each line">
        {ORDER.filter((t) => counts[t]).map((t) => (
          <div key={t} style={{ width: `${((counts[t] ?? 0) / total) * 100}%`, background: TIER_COLOR[t] }} title={`${TIER_LABEL[t]}: ${counts[t]}`} />
        ))}
      </div>
      {!compact && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {ORDER.filter((t) => counts[t]).map((t) => (
            <span key={t} className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: TIER_COLOR[t] }} />
              {TIER_LABEL[t]} {Math.round(((counts[t] ?? 0) / total) * 100)}%
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
