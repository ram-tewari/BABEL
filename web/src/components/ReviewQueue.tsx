import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CheckCheck, Download, ExternalLink } from "lucide-react";
import { Link } from "react-router";
import { api, TIER_LABEL, type ReviewItem } from "../lib/api";
import { Button, Empty, ErrorNote, Spinner, buttonCls, cx } from "./ui";
import { Rich } from "./Scenario";

/** The lines BABEL is least sure about, for a human to settle in one click — plus the corrections log. */
export function ReviewQueue({ novelId }: { novelId: number }) {
  const qc = useQueryClient();
  const queue = useQuery({ queryKey: ["review", novelId], queryFn: () => api.review(novelId) });
  const corrections = useQuery({ queryKey: ["corrections", novelId], queryFn: () => api.corrections(novelId) });
  const refresh = () => ["review", "corrections", "chapter", "novel", "cast"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const fix = useMutation({
    mutationFn: (a: { item: ReviewItem; speaker: string }) => api.edit(a.item.chapter_id, a.item.block.seg, a.item.block.type, a.speaker, a.item.block.tone),
    onSuccess: refresh,
  });
  const accept = useMutation({ mutationFn: (item: ReviewItem) => api.accept(item.chapter_id, item.block.seg), onSuccess: refresh });

  const fixed = corrections.data?.filter((c) => !c.confirmed).length ?? 0;
  const confirmed = corrections.data?.filter((c) => c.confirmed).length ?? 0;

  return (
    <div className="space-y-10">
      <section>
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-base font-semibold">Needs a look</h2>
          <span className="text-xs text-muted">Lines below the confidence threshold after every model tier had its say.</span>
        </div>
        <ErrorNote error={fix.error ?? accept.error} />
        {queue.isLoading ? (
          <Spinner />
        ) : !queue.data?.length ? (
          <Empty icon={<CheckCheck size={40} />} title="Nothing to review">
            Every transformed line is above the confidence threshold.
          </Empty>
        ) : (
          <ul className="space-y-3">
            {queue.data.map((item) => (
              <li key={`${item.chapter_id}-${item.block.seg[0]}`} className="rounded-xl border border-line bg-surface p-4">
                <div className="mb-2 flex items-center justify-between gap-2 text-xs text-muted">
                  <span>
                    {item.chapter_title} · <span className="text-warn">{Math.round(item.block.conf * 100)}%</span> · {TIER_LABEL[item.block.tier]}
                  </span>
                  <Link to={`/read/${item.chapter_id}`} className="inline-flex items-center gap-1 hover:text-text">
                    open <ExternalLink size={12} />
                  </Link>
                </div>
                <div className="space-y-1 font-serif text-sm text-faint">
                  {item.before.map((t, i) => (
                    <p key={i} className="line-clamp-2">
                      <Rich text={t} />
                    </p>
                  ))}
                </div>
                <p className="my-2 border-l-2 border-warn pl-3 font-serif text-[15px]">
                  <span className="mr-2 font-sans text-xs font-semibold uppercase tracking-wide text-muted">{item.block.speaker ?? "?"} {item.block.type}:</span>
                  <Rich text={item.block.text} />
                </p>
                <div className="space-y-1 font-serif text-sm text-faint">
                  {item.after.map((t, i) => (
                    <p key={i} className="line-clamp-2">
                      <Rich text={t} />
                    </p>
                  ))}
                </div>
                {item.block.why && <p className="mt-2 text-xs text-faint">Why: {item.block.why}</p>}
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <span className="mr-1 text-xs text-muted">Who?</span>
                  {[...new Set([item.block.speaker, ...item.block.candidates].filter(Boolean) as string[])].map((c) => (
                    <button
                      key={c}
                      onClick={() => (c === item.block.speaker ? accept.mutate(item) : fix.mutate({ item, speaker: c }))}
                      disabled={fix.isPending || accept.isPending}
                      className={cx("rounded-full border px-3 py-1 text-[13px] hover:border-accent", c === item.block.speaker ? "border-line bg-raised" : "border-line")}
                    >
                      {c === item.block.speaker && <Check size={12} className="mr-1 inline" />}
                      {c}
                    </button>
                  ))}
                  <Link to={`/read/${item.chapter_id}`} className="ml-auto text-xs text-muted hover:text-text">
                    something else…
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold">Corrections</h2>
          <a className={buttonCls("outline", "sm")} href={api.exportUrl(novelId, "corrections")} download>
            <Download size={14} /> Export JSONL
          </a>
        </div>
        <p className="mb-3 text-sm text-muted">
          {fixed} fixed · {confirmed} confirmed. These are gold labels: export them to measure or fine-tune a model, and they survive every re-transform.
        </p>
        {(corrections.data?.length ?? 0) > 0 && (
          <div className="overflow-x-auto rounded-xl border border-line">
            <table className="w-full text-left text-sm">
              <thead className="bg-raised text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-3 py-2">Chapter</th>
                  <th className="px-3 py-2">Line</th>
                  <th className="px-3 py-2">Was</th>
                  <th className="px-3 py-2">Now</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {corrections.data!.slice(-200).reverse().map((c) => (
                  <tr key={`${c.chapter_id}-${c.seg}`}>
                    <td className="whitespace-nowrap px-3 py-2 text-muted">
                      <Link to={`/read/${c.chapter_id}`} className="hover:text-text">
                        {c.chapter_idx + 1}
                      </Link>
                    </td>
                    <td className="max-w-md truncate px-3 py-2 font-serif">{c.text}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-faint">{c.before ? `${c.before.speaker ?? "—"} (${c.before.type}, ${TIER_LABEL[c.before.tier]})` : "—"}</td>
                    <td className="whitespace-nowrap px-3 py-2">{c.confirmed ? <span className="text-ok">✓ confirmed</span> : `${c.after.speaker ?? "—"} (${c.after.type})`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <Button variant="ghost" size="sm" onClick={refresh}>
        Refresh
      </Button>
    </div>
  );
}
