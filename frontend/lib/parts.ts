// Helpers over useChat UI-message parts: tool steps, evidence, follow-ups and Data Confidence.
import type { UIMessage } from "ai";
import type { ConfidenceLevel, FollowupsData, ToolResult } from "@/lib/contracts";

export type Part = UIMessage["parts"][number];

/** The fields every tool part (static `tool-*` or `dynamic-tool`) carries. */
export interface ToolPartLike {
  type: string;
  toolCallId: string;
  toolName?: string;
  state: string;
  input?: unknown;
  output?: unknown;
  errorText?: string;
}

export function isToolPart(p: Part | { type: string }): p is Part & ToolPartLike {
  return p.type.startsWith("tool-") || p.type === "dynamic-tool";
}

export function toolNameOf(p: ToolPartLike): string {
  return p.type === "dynamic-tool" ? (p.toolName ?? "tool") : p.type.slice("tool-".length);
}

export const FOLLOWUPS_TOOL = "suggest_followups";

/** Tools whose output is a ToolResult envelope rendered as Evidence. */
export const EVIDENCE_TOOLS = new Set([
  "resolve_airports",
  "rank_airports",
  "airport_scorecard",
  "compare_airports",
  "route_mix",
  "unmet_demand",
  "live_traffic",
  "od_demand",
  "live_delays",
  "query_snapshot",
  "query_public_api",
]);

export const LIVE_TOOLS = new Set(["live_traffic", "od_demand", "live_delays", "query_public_api"]);

export type StepState = "running" | "done" | "error";

export interface Step {
  id: string;
  name: string;
  state: StepState;
  input: unknown;
  output: unknown;
  errorText?: string;
}

export function stepState(p: ToolPartLike): StepState {
  if (p.state === "output-error" || p.state === "output-denied") return "error";
  if (p.state === "output-available") return "done";
  return "running";
}

/** Tool outputs normally arrive as JSON objects; tolerate a JSON string too. */
export function parseOutput(output: unknown): unknown {
  if (typeof output === "string") {
    try {
      return JSON.parse(output);
    } catch {
      return output;
    }
  }
  return output;
}

export function isToolResult(x: unknown): x is ToolResult<unknown> {
  return (
    typeof x === "object" &&
    x !== null &&
    "data" in x &&
    "data_confidence" in x &&
    typeof (x as { data_confidence: unknown }).data_confidence === "object"
  );
}

/** All tool steps of one message, in order, excluding the follow-up chips tool. */
export function stepsOf(message: UIMessage): Step[] {
  const out: Step[] = [];
  for (const p of message.parts) {
    if (!isToolPart(p)) continue;
    const name = toolNameOf(p);
    if (name === FOLLOWUPS_TOOL) continue;
    out.push({
      id: p.toolCallId,
      name,
      state: stepState(p),
      input: p.input,
      output: p.state === "output-available" ? parseOutput(p.output) : undefined,
      errorText: p.errorText,
    });
  }
  return out;
}

export interface EvidenceEntry {
  id: string;
  name: string;
  result: ToolResult<unknown>;
}

export function evidenceOf(message: UIMessage): EvidenceEntry[] {
  return stepsOf(message)
    .filter((s) => s.state === "done" && EVIDENCE_TOOLS.has(s.name) && isToolResult(s.output))
    .map((s) => ({ id: s.id, name: s.name, result: s.output as ToolResult<unknown> }));
}

export function followupsOf(message: UIMessage): string[] {
  for (const p of message.parts) {
    if (!isToolPart(p) || toolNameOf(p) !== FOLLOWUPS_TOOL) continue;
    const out = parseOutput(p.output) as Partial<FollowupsData> | undefined;
    const inp = p.input as Partial<FollowupsData> | undefined;
    const qs = out?.questions ?? inp?.questions;
    if (Array.isArray(qs)) return qs.filter((q): q is string => typeof q === "string" && q.trim() !== "");
  }
  return [];
}

const RANK: Record<ConfidenceLevel, number> = { Low: 0, Medium: 1, High: 2 };

/** The answer's Data Confidence: the lowest level among its tool envelopes (SPEC §6). */
export function lowestConfidence(entries: EvidenceEntry[]): ConfidenceLevel | null {
  let lowest: ConfidenceLevel | null = null;
  for (const e of entries) {
    const lvl = e.result.data_confidence?.level;
    if (!lvl || !(lvl in RANK)) continue;
    if (lowest === null || RANK[lvl] < RANK[lowest]) lowest = lvl;
  }
  return lowest;
}

/**
 * The answer the chat shows: the text parts after the message's last tool call (its final message).
 * Text the model writes before a tool call is not the answer (SPEC §6); showing it too is how a whole
 * answer appeared twice, once before suggest_followups and again after it (backend app/agent/answer.py).
 */
export function answerTextsOf(message: UIMessage): Extract<Part, { type: "text" }>[] {
  let out: Extract<Part, { type: "text" }>[] = [];
  for (const p of message.parts) {
    if (isToolPart(p)) out = [];
    else if (p.type === "text") out.push(p);
  }
  return out;
}

export function textOf(message: UIMessage): string {
  return message.parts
    .filter((p): p is Extract<Part, { type: "text" }> => p.type === "text")
    .map((p) => p.text)
    .join("");
}

/** A short title for the rail, from the first user message. */
export function titleFrom(messages: UIMessage[]): string {
  const first = messages.find((m) => m.role === "user");
  const t = first ? textOf(first).trim().replace(/\s+/g, " ") : "";
  if (!t) return "New chat";
  return t.length > 64 ? `${t.slice(0, 61).trimEnd()}…` : t;
}

/** A compact one-line summary of tool arguments for step rows. */
export function argsSummary(input: unknown): string {
  if (input == null || typeof input !== "object") return input == null ? "" : String(input);
  return Object.entries(input as Record<string, unknown>)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" ");
}

/** The ad-hoc query a tool call ran, for the Trace: query_snapshot's SQL, or query_public_api's dataset and SoQL. */
export function adHocQuery(toolName: string, input: unknown): string {
  if (!input || typeof input !== "object") return "";
  const args = input as Record<string, unknown>;
  if (toolName === "query_snapshot") return String(args.sql ?? "");
  if (toolName !== "query_public_api") return "";
  const lines = [`dataset: ${String(args.dataset ?? "")}`];
  for (const k of ["select", "where", "group", "order", "limit"]) {
    if (args[k] != null && args[k] !== "") lines.push(`$${k}=${String(args[k])}`);
  }
  return lines.join("\n");
}
