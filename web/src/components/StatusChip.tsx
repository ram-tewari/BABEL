import { useQuery } from "@tanstack/react-query";
import { Cpu, WifiOff } from "lucide-react";
import { api } from "../lib/api";

/** Which LLM chain the server will use (or that it is in offline heuristic mode). */
export function StatusChip() {
  const { data } = useQuery({ queryKey: ["status"], queryFn: api.status, staleTime: 60_000 });
  if (!data) return null;
  const online = !!data.llm;
  const label = online ? data.providers.map((p) => p.name).join(" → ") : "offline mode";
  const title = online
    ? `LLM chain: ${data.llm}`
    : "No LLM provider configured — chapters are labeled by the offline heuristic. Add an API key to .env (see README) for much better speaker attribution.";
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs text-muted"
    >
      {online ? <Cpu size={13} className="text-ok" /> : <WifiOff size={13} className="text-warn" />}
      {label}
    </span>
  );
}
