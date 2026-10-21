import type { RouteMixData, ToolResult } from "@/lib/contracts";
import { EvidenceMeta } from "./evidence-meta";
import { RouteMixEvidence } from "./route-mix";

/** Tools whose output is a ToolResult envelope worth showing as Evidence. */
export const EVIDENCE_TOOLS = new Set([
  "route_mix",
  "rank_airports",
  "airport_scorecard",
  "compare_airports",
  "unmet_demand",
  "live_traffic",
  "od_demand",
  "live_delays",
  "query_snapshot",
]);

/** Evidence card keyed on the tool name. Unknown tools fall back to the envelope metadata only. */
export function EvidenceCard({ toolName, result }: { toolName: string; result: ToolResult<unknown> }) {
  let body: React.ReactNode = null;
  if (toolName === "route_mix") body = <RouteMixEvidence data={result.data as RouteMixData} />;
  return (
    <section
      data-testid={`evidence-${toolName}`}
      className="space-y-4 rounded-[16px] border border-[var(--hairline)] bg-[var(--card-surface)] p-5"
    >
      {body ?? <h3 className="num text-sm">{toolName}</h3>}
      <EvidenceMeta result={result} />
    </section>
  );
}
