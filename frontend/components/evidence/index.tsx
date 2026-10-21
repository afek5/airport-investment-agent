import type { ToolDataByName, ToolResult } from "@/lib/contracts";
import { LIVE_TOOLS } from "@/lib/parts";
import { AdHocEvidence, ResolveEvidence } from "./ad-hoc";
import { EvidenceBoundary } from "./boundary";
import { ComparisonEvidence } from "./comparison";
import { EvidenceMeta } from "./evidence-meta";
import { LiveDelaysEvidence, LiveTrafficEvidence, OdDemandEvidence } from "./live";
import { RankingEvidence } from "./ranking";
import { RouteMixEvidence } from "./route-mix";
import { ScorecardEvidence } from "./scorecard";
import { UnmetDemandEvidence } from "./unmet-demand";

export { EVIDENCE_TOOLS } from "@/lib/parts";

type Renderers = { [K in keyof ToolDataByName]: (props: { data: ToolDataByName[K] }) => React.ReactNode };

/** One plain-table renderer per tool `data` type, keyed on the tool name (HANDOFF §2). */
export const RENDERERS: Renderers = {
  resolve_airports: ResolveEvidence,
  rank_airports: RankingEvidence,
  airport_scorecard: ScorecardEvidence,
  compare_airports: ComparisonEvidence,
  route_mix: RouteMixEvidence,
  unmet_demand: UnmetDemandEvidence,
  live_traffic: LiveTrafficEvidence,
  od_demand: OdDemandEvidence,
  live_delays: LiveDelaysEvidence,
  query_snapshot: AdHocEvidence,
};

function renderBody(toolName: string, data: unknown): React.ReactNode {
  const R = (RENDERERS as Record<string, ((p: { data: unknown }) => React.ReactNode) | undefined>)[toolName];
  if (!R) return <h3 className="num text-sm">{toolName}</h3>;
  return (
    <EvidenceBoundary toolName={toolName}>
      <R data={data} />
    </EvidenceBoundary>
  );
}

/** An Evidence card: the tool's renderer plus the shared envelope metadata. Unknown tools fall back to metadata only. */
export function EvidenceCard({ toolName, result }: { toolName: string; result: ToolResult<unknown> }) {
  return (
    <article
      data-testid={`evidence-${toolName}`}
      className="evidence-card space-y-4 rounded-[16px] border border-[var(--hairline)] bg-[var(--card-surface)] p-4 shadow-[var(--shadow-card)]"
    >
      {renderBody(toolName, result.data)}
      <EvidenceMeta result={result} live={LIVE_TOOLS.has(toolName)} />
    </article>
  );
}
