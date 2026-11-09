import { useQuery } from "@tanstack/react-query";
import { Cloud, Cpu, WifiOff } from "lucide-react";
import { api } from "../lib/api";

/** Which model tiers the server will use. */
export function StatusChip() {
  const { data } = useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 60_000 });
  if (!data) return null;
  const { local, cloud } = data.tiers;
  const title = [
    "Every line goes rules → memory first.",
    local ? `Uncertain lines go to the local model ${local} (free).` : "No local model (start Ollama and `ollama pull qwen3:30b-a3b` (or qwen3:8b) for free verification).",
    cloud.length ? `Still-uncertain lines go to ${cloud.map((c) => `${c.name}:${c.model}`).join(" → ")}.` : "No cloud provider configured.",
  ].join("\n");
  return (
    <span title={title} className="inline-flex items-center gap-2 rounded-full border border-line px-2.5 py-1 text-xs text-muted">
      {!local && !cloud.length ? (
        <>
          <WifiOff size={13} className="text-warn" /> rules only
        </>
      ) : (
        <>
          {local && (
            <span className="inline-flex items-center gap-1">
              <Cpu size={13} className="text-ok" /> local
            </span>
          )}
          {cloud.length > 0 && (
            <span className="inline-flex items-center gap-1">
              <Cloud size={13} style={{ color: "var(--slot-9)" }} /> {cloud[0].name}
            </span>
          )}
        </>
      )}
    </span>
  );
}
