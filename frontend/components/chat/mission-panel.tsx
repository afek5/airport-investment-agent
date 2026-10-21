"use client";

import type { ChatStatus, UIMessage } from "ai";
import { ChevronRightIcon, XIcon } from "lucide-react";
import { useState } from "react";
import { ToolStatus } from "@/components/ai-elements/tool";
import { EvidenceCard } from "@/components/evidence";
import { ConfidenceBadge } from "@/components/evidence/evidence-meta";
import { fmtDuration } from "@/lib/format";
import { argsSummary, evidenceOf, isToolPart, lowestConfidence, parseOutput, stepsOf, textOf, toolNameOf } from "@/lib/parts";
import { cn } from "@/lib/utils";

type SectionKey = "progress" | "evidence" | "trace";

function Section({
  id,
  title,
  meta,
  open,
  onToggle,
  children,
}: {
  id: SectionKey;
  title: string;
  meta?: React.ReactNode;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-[var(--hairline)] last:border-b-0" data-testid={`panel-${id}`}>
      <h3>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={`panel-${id}-body`}
          onClick={onToggle}
          className="flex w-full items-center gap-2 px-5 py-3 text-left hover:bg-[var(--tint)] max-sm:px-4"
        >
          <ChevronRightIcon aria-hidden className={cn("size-3.5 text-[var(--ink-muted)] transition-transform", open && "rotate-90")} />
          <span className="eyebrow text-[var(--ink)]">{title}</span>
          <span className="ml-auto flex items-center gap-2">{meta}</span>
        </button>
      </h3>
      {open ? (
        <div id={`panel-${id}-body`} className="px-5 pb-5 max-sm:px-4">
          {children}
        </div>
      ) : null}
    </section>
  );
}

/** The question a given assistant message answers (the user message just before it). */
function questionFor(messages: UIMessage[], assistantId: string): string {
  const i = messages.findIndex((m) => m.id === assistantId);
  for (let j = i - 1; j >= 0; j--) if (messages[j].role === "user") return textOf(messages[j]);
  return "";
}

export function MissionPanel({
  messages,
  status,
  focusedId,
  onFocusLatest,
  stepMs,
  onClose,
  overlay,
}: {
  messages: UIMessage[];
  status: ChatStatus;
  focusedId: string | null;
  onFocusLatest: () => void;
  stepMs: (id: string) => number | undefined;
  onClose: () => void;
  overlay: boolean;
}) {
  const [open, setOpen] = useState<Record<SectionKey, boolean>>({ progress: true, evidence: true, trace: false });
  const toggle = (k: SectionKey) => setOpen((o) => ({ ...o, [k]: !o[k] }));

  const assistants = messages.filter((m) => m.role === "assistant");
  const latest = assistants.at(-1);
  const busy = status === "submitted" || status === "streaming";
  const latestWithEvidence = [...assistants].reverse().find((m) => evidenceOf(m).length > 0);
  const focused = (focusedId && assistants.find((m) => m.id === focusedId)) || latestWithEvidence || latest;
  const isLatestFocus = !focused || focused.id === (latestWithEvidence ?? latest)?.id;

  // Progress follows the current answer. While a new question is submitted, there's no assistant message yet.
  const awaiting = status === "submitted" && messages.at(-1)?.role === "user";
  const progressSteps = awaiting || !latest ? [] : stepsOf(latest);
  const writing = busy && !awaiting && !!latest && textOf(latest).length > 0;

  const evidence = focused ? evidenceOf(focused) : [];
  const level = lowestConfidence(evidence);
  const traceParts = focused ? focused.parts.filter(isToolPart) : [];

  return (
    <div className="flex h-full flex-col" data-testid="mission-panel">
      <header className="flex h-[52px] shrink-0 items-center gap-2 border-b border-[var(--hairline)] px-5 max-sm:px-4">
        <h2 className="text-[13px] font-semibold">Mission</h2>
        {busy ? (
          <span className="num flex items-center gap-1.5 text-[11.5px] text-[var(--live-ink)]">
            <span aria-hidden className="live-dot size-1.5 rounded-full" /> working
          </span>
        ) : null}
        <button
          type="button"
          onClick={onClose}
          aria-label="Close Mission panel"
          className="ml-auto grid size-8 place-items-center rounded-[10px] text-[var(--ink-muted)] hover:bg-[var(--tint)] hover:text-[var(--ink)]"
        >
          <XIcon className="size-4" />
        </button>
      </header>
      <div className={cn("min-h-0 flex-1 overflow-y-auto", overlay && "pb-[env(safe-area-inset-bottom)]")}>
        <Section
          id="progress"
          title="Progress"
          open={open.progress}
          onToggle={() => toggle("progress")}
          meta={
            progressSteps.length ? <span className="num text-[11.5px] text-[var(--ink-muted)]">{progressSteps.length}</span> : null
          }
        >
          {awaiting ? (
            <p className="flex items-center gap-2 text-[13px] text-[var(--live-ink)]">
              <span aria-hidden className="live-dot size-2 rounded-full" /> Reading the question…
            </p>
          ) : progressSteps.length === 0 ? (
            <p className="text-[13px] text-[var(--ink-muted)]">
              {latest ? "The last answer used no tools." : "Tool steps for the current answer appear here as the analyst works."}
            </p>
          ) : (
            <ol className="space-y-0.5" aria-live="polite">
              {progressSteps.map((s) => (
                <li key={s.id} className="flex min-w-0 items-center gap-2 py-1 text-[12.5px]">
                  <ToolStatus state={s.state} />
                  <span className={cn("num shrink-0", s.state === "running" && "text-[var(--live-ink)]")}>{s.name}</span>
                  <span className="num min-w-0 truncate text-[var(--ink-muted)]">{argsSummary(s.input)}</span>
                  <span className="num ml-auto shrink-0 pl-2 text-[var(--ink-muted)]">
                    {s.state === "error" ? "failed" : fmtDuration(stepMs(s.id))}
                  </span>
                </li>
              ))}
              {writing ? (
                <li className="flex items-center gap-2 py-1 text-[12.5px] text-[var(--live-ink)]">
                  <span className="grid size-4 place-items-center">
                    <span aria-hidden className="live-dot size-2 rounded-full" />
                  </span>
                  Writing the answer
                </li>
              ) : null}
            </ol>
          )}
        </Section>

        <Section
          id="evidence"
          title="Evidence"
          open={open.evidence}
          onToggle={() => toggle("evidence")}
          meta={level ? <ConfidenceBadge level={level} compact /> : null}
        >
          {evidence.length === 0 ? (
            <p className="text-[13px] text-[var(--ink-muted)]">
              Evidence from tool results appears here: plain tables, Data Confidence, Assumptions and As-of Dates.
            </p>
          ) : (
            <div className="space-y-4">
              {focused ? (
                <div className="flex items-start gap-2 text-[12.5px] text-[var(--ink-muted)]">
                  <p className="min-w-0 flex-1">
                    For: <span className="text-[var(--ink)]">{questionFor(messages, focused.id) || "this answer"}</span>
                  </p>
                  {!isLatestFocus ? (
                    <button type="button" onClick={onFocusLatest} className="shrink-0 underline underline-offset-2 hover:text-[var(--ink)]">
                      Latest
                    </button>
                  ) : null}
                </div>
              ) : null}
              {evidence.map((e) => (
                <EvidenceCard key={e.id} toolName={e.name} result={e.result} />
              ))}
            </div>
          )}
        </Section>

        <Section
          id="trace"
          title="Trace"
          open={open.trace}
          onToggle={() => toggle("trace")}
          meta={traceParts.length ? <span className="num text-[11.5px] text-[var(--ink-muted)]">{traceParts.length} {traceParts.length === 1 ? "call" : "calls"}</span> : null}
        >
          {traceParts.length === 0 ? (
            <p className="text-[13px] text-[var(--ink-muted)]">Raw tool calls (name, arguments, duration, ad-hoc SQL) appear here.</p>
          ) : (
            <ol className="space-y-3" data-testid="trace-list">
              {traceParts.map((p) => {
                const name = toolNameOf(p);
                const sql =
                  name === "query_snapshot" && p.input && typeof p.input === "object"
                    ? String((p.input as { sql?: unknown }).sql ?? "")
                    : "";
                return (
                  <li key={p.toolCallId} className="space-y-1.5 rounded-[10px] border border-[var(--hairline)] p-3">
                    <div className="flex items-center gap-2 text-[12.5px]">
                      <span className="num font-medium">{name}</span>
                      <span className="num text-[var(--ink-muted)]">{p.state}</span>
                      <span className="num ml-auto text-[var(--ink-muted)]">{fmtDuration(stepMs(p.toolCallId))}</span>
                    </div>
                    {sql ? (
                      <pre className="num overflow-x-auto whitespace-pre-wrap break-words rounded-[8px] bg-[var(--tint)] p-2.5 text-[11.5px]">
                        {sql}
                      </pre>
                    ) : null}
                    <details className="text-[12px]">
                      <summary className="cursor-pointer text-[var(--ink-muted)] hover:text-[var(--ink)]">Arguments</summary>
                      <pre className="num mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-[8px] bg-[var(--tint)] p-2.5 text-[11.5px]">
                        {JSON.stringify(p.input ?? {}, null, 2)}
                      </pre>
                    </details>
                    {p.state === "output-available" ? (
                      <details className="text-[12px]">
                        <summary className="cursor-pointer text-[var(--ink-muted)] hover:text-[var(--ink)]">Raw output</summary>
                        <pre className="num mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-[8px] bg-[var(--tint)] p-2.5 text-[11px]">
                          {JSON.stringify(parseOutput(p.output), null, 2)}
                        </pre>
                      </details>
                    ) : null}
                    {p.errorText ? <p className="text-[12px] text-[var(--bad)]">{p.errorText}</p> : null}
                  </li>
                );
              })}
            </ol>
          )}
        </Section>
      </div>
    </div>
  );
}
