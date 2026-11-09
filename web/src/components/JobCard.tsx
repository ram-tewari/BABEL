import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, Square } from "lucide-react";
import { api, type Job } from "../lib/api";
import { Button, ProgressBar } from "./ui";

const STATUS_TEXT: Record<Job["status"], string> = {
  queued: "Queued",
  running: "Transforming",
  paused: "Paused",
  done: "Finished",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function JobCard({ job, novelId }: { job: Job; novelId: number }) {
  const qc = useQueryClient();
  const act = useMutation({
    mutationFn: (a: "pause" | "resume" | "cancel") => api.jobAction(job.id, a),
    onSettled: () => qc.invalidateQueries({ queryKey: ["novel", novelId] }),
  });
  const live = job.status === "running" || job.status === "queued";
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="text-sm font-medium">
          {STATUS_TEXT[job.status]}
          {job.total > 0 && (
            <span className="ml-2 tabular-nums text-muted">
              {job.done}/{job.total}
              {job.failed > 0 && <span className="text-danger"> · {job.failed} failed</span>}
            </span>
          )}
        </div>
        <div className="flex gap-1.5">
          {live && (
            <Button size="sm" variant="ghost" onClick={() => act.mutate("pause")} disabled={act.isPending}>
              <Pause size={14} /> Pause
            </Button>
          )}
          {(job.status === "paused" || job.status === "failed") && (
            <Button size="sm" variant="ghost" onClick={() => act.mutate("resume")} disabled={act.isPending}>
              <Play size={14} /> Resume
            </Button>
          )}
          {(live || job.status === "paused") && (
            <Button size="sm" variant="ghost" onClick={() => act.mutate("cancel")} disabled={act.isPending}>
              <Square size={13} /> Stop
            </Button>
          )}
        </div>
      </div>
      <ProgressBar value={job.done} max={job.total} label="Transform progress" tone={job.status === "done" ? "ok" : "accent"} />
      {job.message && <div className="mt-2 truncate text-xs text-muted" title={job.message}>{job.message}</div>}
    </div>
  );
}
