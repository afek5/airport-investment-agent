"use client";

// AI Elements `Tool`, restyled for mission control: a compact step row (status, tool name, arguments,
// duration) that expands to its parameters. Base UI's Collapsible marks the open trigger with
// `data-panel-open`.
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import { CheckIcon, ChevronRightIcon, XIcon } from "lucide-react";
import type { ComponentProps } from "react";

export type ToolState = "running" | "done" | "error";

export type ToolProps = ComponentProps<typeof Collapsible>;

export const Tool = ({ className, ...props }: ToolProps) => (
  <Collapsible className={cn("not-prose w-full", className)} {...props} />
);

const STATE_LABEL: Record<ToolState, string> = { running: "Running", done: "Done", error: "Failed" };

/** Status mark: a live-blue pulse while running, ok check when done, bad cross on error; always with a text label for AT. */
export function ToolStatus({ state }: { state: ToolState }) {
  return (
    <span className="grid size-4 shrink-0 place-items-center" role="img" aria-label={STATE_LABEL[state]}>
      {state === "running" ? (
        <span className="live-dot size-2 rounded-full" />
      ) : state === "done" ? (
        <CheckIcon className="size-3.5 text-[var(--ok)]" strokeWidth={2.5} />
      ) : (
        <XIcon className="size-3.5 text-[var(--bad)]" strokeWidth={2.5} />
      )}
    </span>
  );
}

export type ToolHeaderProps = {
  name: string;
  state: ToolState;
  summary?: string;
  duration?: string;
  className?: string;
};

export const ToolHeader = ({ name, state, summary, duration, className }: ToolHeaderProps) => (
  <CollapsibleTrigger
    className={cn(
      "group/step flex w-full min-w-0 items-center gap-2 rounded-[8px] px-2 py-1.5 text-left text-[12.5px] hover:bg-[var(--tint)]",
      className,
    )}
  >
    <ChevronRightIcon
      aria-hidden
      className="size-3.5 shrink-0 text-[var(--ink-muted)] transition-transform group-data-[panel-open]/step:rotate-90"
    />
    <ToolStatus state={state} />
    <span className={cn("num shrink-0", state === "running" && "text-[var(--live-ink)]")}>{name}</span>
    {summary ? <span className="num min-w-0 truncate text-[var(--ink-muted)]">{summary}</span> : null}
    <span className="num ml-auto shrink-0 pl-2 text-[var(--ink-muted)]">{state === "error" ? "failed" : duration}</span>
  </CollapsibleTrigger>
);

export type ToolContentProps = ComponentProps<typeof CollapsibleContent>;

export const ToolContent = ({ className, ...props }: ToolContentProps) => (
  <CollapsibleContent className={cn("space-y-2 pb-2 pl-[2.1rem] pr-2 pt-1", className)} {...props} />
);

export const ToolInput = ({ input }: { input: unknown }) => (
  <pre className="num max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-[8px] bg-[var(--tint)] p-2.5 text-[11.5px] leading-[1.5]">
    {JSON.stringify(input ?? {}, null, 2)}
  </pre>
);

export const ToolError = ({ errorText }: { errorText?: string }) =>
  errorText ? (
    <p className="rounded-[8px] border border-[color-mix(in_oklab,var(--bad)_40%,transparent)] p-2.5 text-[12.5px] text-[var(--bad)]">
      {errorText}
    </p>
  ) : null;
