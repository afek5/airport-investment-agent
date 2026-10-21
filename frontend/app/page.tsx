"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useMemo } from "react";

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation";
import { Message, MessageContent, MessageResponse } from "@/components/ai-elements/message";
import { Composer } from "@/components/composer";
import { Tool, ToolContent, ToolHeader, ToolInput, ToolOutput } from "@/components/ai-elements/tool";
import { EVIDENCE_TOOLS, EvidenceCard } from "@/components/evidence";
import type { FollowupsData, ToolResult } from "@/lib/contracts";

const STARTERS = [
  "Which airports in New England are strong candidates for terminal expansion?",
  "Compare LA and Santa Ana airport congestion levels.",
  "What is the percentage of long haul flights out of Anchorage airport?",
  "What is the unmet flight demand in SFO airport and why?",
];

type Part = UIMessage["parts"][number];
type ToolLikePart = Extract<Part, { type: `tool-${string}` }> | Extract<Part, { type: "dynamic-tool" }>;

function isToolPart(p: Part): p is ToolLikePart {
  return p.type.startsWith("tool-") || p.type === "dynamic-tool";
}

function toolName(p: ToolLikePart): string {
  return p.type === "dynamic-tool" ? (p as { toolName: string }).toolName : p.type.slice("tool-".length);
}

export default function Home() {
  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/chat" }), []);
  const { messages, sendMessage, status, stop, error } = useChat({ transport });

  const evidence = useMemo(() => {
    const out: { id: string; name: string; result: ToolResult<unknown> }[] = [];
    for (const m of messages) {
      for (const p of m.parts) {
        if (isToolPart(p) && p.state === "output-available" && EVIDENCE_TOOLS.has(toolName(p))) {
          out.push({ id: p.toolCallId, name: toolName(p), result: p.output as ToolResult<unknown> });
        }
      }
    }
    return out.reverse();
  }, [messages]);

  const lastFollowups = useMemo(() => {
    const last = messages.at(-1);
    if (!last || last.role !== "assistant" || status !== "ready") return [];
    for (const p of last.parts) {
      if (isToolPart(p) && toolName(p) === "suggest_followups" && p.state === "output-available") {
        return (p.output as FollowupsData).questions;
      }
    }
    return [];
  }, [messages, status]);

  const ask = (text: string) => {
    if (text.trim()) sendMessage({ text });
  };

  return (
    <div className="flex h-dvh w-full">
      <main className="flex min-w-0 flex-1 flex-col">
        <Conversation className="flex-1">
          <ConversationContent className="mx-auto w-full max-w-[720px] px-4 py-8 md:px-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center gap-6 pt-[14vh] text-center">
                <h1 className="font-serif text-[44px] leading-[1.08]">Where should the next terminal go?</h1>
                <div className="flex flex-wrap justify-center gap-2">
                  {STARTERS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => ask(q)}
                      className="rounded-[10px] border border-[var(--hairline)] px-3 py-2 text-left text-[13px] hover:bg-[var(--secondary)]"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m) => (
              <Message key={m.id} from={m.role}>
                <MessageContent>
                  {m.parts.map((p, i) => {
                    if (p.type === "text") {
                      return <MessageResponse key={i}>{p.text}</MessageResponse>;
                    }
                    if (isToolPart(p)) {
                      const name = toolName(p);
                      if (name === "suggest_followups") return null;
                      return (
                        <Tool key={p.toolCallId} data-testid={`tool-step-${name}`}>
                          <ToolHeader
                            type="dynamic-tool"
                            toolName={name}
                            state={p.state}
                            title={name}
                          />
                          <ToolContent>
                            <ToolInput input={p.input} />
                            <ToolOutput output={p.output} errorText={p.errorText} />
                          </ToolContent>
                        </Tool>
                      );
                    }
                    return null;
                  })}
                </MessageContent>
              </Message>
            ))}
            {lastFollowups.length > 0 && (
              <div className="flex flex-wrap gap-2" data-testid="followups">
                {lastFollowups.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => ask(q)}
                    className="rounded-[10px] border border-[var(--hairline)] px-3 py-1.5 text-[13px] hover:bg-[var(--secondary)]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
            {error && <p className="text-sm text-[var(--bad)]">Something went wrong: {error.message}</p>}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>
        <div className="mx-auto w-full max-w-[760px] px-4 pb-4 md:px-6">
          <Composer status={status} onSubmit={ask} onStop={stop} />
        </div>
      </main>
      <aside
        aria-label="Mission panel"
        className="hidden w-[380px] shrink-0 overflow-y-auto border-l border-[var(--hairline)] p-4 lg:block"
      >
        <h2 className="num mb-3 text-xs font-medium uppercase tracking-[0.06em] text-[var(--ink-muted)]">
          Evidence
        </h2>
        {evidence.length === 0 ? (
          <p className="text-sm text-[var(--ink-muted)]">Evidence from tool results appears here.</p>
        ) : (
          <div className="space-y-4">
            {evidence.map((e) => (
              <EvidenceCard key={e.id} toolName={e.name} result={e.result} />
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}
