"use client";

import { ChevronRightIcon } from "lucide-react";
import { useState } from "react";
import { Tool, ToolContent, ToolError, ToolHeader, ToolInput } from "@/components/ai-elements/tool";
import { fmtDuration } from "@/lib/format";
import { argsSummary, type Step } from "@/lib/parts";
import { cn } from "@/lib/utils";

/** The collapsed "▸ N steps · Ts" row per answer, expanding to the tool list (live-blue pulse while running). */
export function StepsRow({
  steps,
  stepMs,
  elapsedMs,
}: {
  steps: Step[];
  stepMs: (id: string) => number | undefined;
  elapsedMs?: number;
}) {
  const [open, setOpen] = useState(false);
  if (steps.length === 0) return null;
  const running = steps.some((s) => s.state === "running");
  const failed = steps.filter((s) => s.state === "error").length;
  const total = elapsedMs ?? sum(steps.map((s) => stepMs(s.id)));
  return (
    <div className="-ml-2" data-testid="steps-row">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[12.5px] text-[var(--ink-muted)] hover:bg-[var(--tint)] hover:text-[var(--ink)]"
      >
        <ChevronRightIcon aria-hidden className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        {running ? <span aria-hidden className="live-dot mr-0.5 size-1.5 rounded-full" /> : null}
        <span className={cn("num", running && "text-[var(--live-ink)]")}>
          {steps.length} {steps.length === 1 ? "step" : "steps"}
          {running ? " · running" : total ? ` · ${fmtDuration(total)}` : ""}
          {failed ? ` · ${failed} failed` : ""}
        </span>
      </button>
      {open ? (
        <div className="land mt-0.5 space-y-0.5 border-l border-[var(--hairline)] pl-1 ml-[0.95rem]">
          {steps.map((s) => (
            <Tool key={s.id}>
              <ToolHeader name={s.name} state={s.state} summary={argsSummary(s.input)} duration={fmtDuration(stepMs(s.id))} />
              <ToolContent>
                <ToolInput input={s.input} />
                <ToolError errorText={s.errorText} />
              </ToolContent>
            </Tool>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** "Thought for Ns": the model's reasoning, collapsed, in secondary ink. */
export function ThoughtRow({ text, ms, streaming }: { text: string; ms?: number; streaming?: boolean }) {
  const [open, setOpen] = useState(false);
  if (!text.trim()) return null;
  return (
    <div className="-ml-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 rounded-[8px] px-2 py-1 text-[12.5px] text-[var(--ink-muted)] hover:bg-[var(--tint)] hover:text-[var(--ink)]"
      >
        <ChevronRightIcon aria-hidden className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        {streaming ? "Thinking…" : ms ? `Thought for ${Math.max(1, Math.round(ms / 1000))}s` : "Thought"}
      </button>
      {open ? (
        <p className="land ml-[0.95rem] whitespace-pre-wrap border-l border-[var(--hairline)] py-1 pl-3 text-[13px] text-[var(--ink-muted)]">
          {text}
        </p>
      ) : null}
    </div>
  );
}

function sum(xs: (number | undefined)[]): number | undefined {
  const ys = xs.filter((x): x is number => typeof x === "number");
  return ys.length ? ys.reduce((a, b) => a + b, 0) : undefined;
}
