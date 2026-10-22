"use client";

import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport, type UIMessage } from "ai";
import { MenuIcon, PanelRightIcon, RotateCwIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Conversation, ConversationContent, ConversationScrollButton } from "@/components/ai-elements/conversation";
import { MessageResponse } from "@/components/ai-elements/message";
import { Composer, type ComposerHandle } from "@/components/composer";
import { ConfidenceBadge } from "@/components/evidence/evidence-meta";
import { chatErrorMessage, saveConversation, type ConversationSummary } from "@/lib/api";
import { answerTextsOf, evidenceOf, followupsOf, isToolPart, lowestConfidence, stepsOf, titleFrom, type Part } from "@/lib/parts";
import { useTimings } from "@/lib/timings";
import type { AnalystResult } from "@/lib/voice";
import { cn } from "@/lib/utils";
import { MissionPanel } from "./mission-panel";
import { StepsRow, ThoughtRow } from "./steps";
import { CallBar, useVoiceAvailable, useVoiceCall } from "./voice-call";

export const STARTERS = [
  "Which airports in New England are strong candidates for terminal expansion?",
  "Compare LA and Santa Ana airport congestion levels.",
  "What is the percentage of long haul flights out of Anchorage airport?",
  "What is the unmet flight demand in SFO airport and why?",
];

export interface PanelControl {
  open: boolean;
  overlay: boolean;
  /** byUser=false is the automatic open after the first tool call; the shell ignores it once the user closed the panel. */
  setOpen: (open: boolean, byUser: boolean) => void;
}

type ApiErr = Error & { statusCode?: number; responseBody?: string };

export function ChatSession({
  id,
  initialMessages,
  title,
  historyEnabled,
  panel,
  showMenuButton,
  onOpenNav,
  onSaved,
  onUnauthorized,
}: {
  id: string;
  initialMessages: UIMessage[];
  title?: string;
  historyEnabled: boolean;
  panel: PanelControl;
  showMenuButton: boolean;
  onOpenNav: () => void;
  onSaved: (summary: ConversationSummary) => void;
  onUnauthorized: () => void;
}) {
  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/chat", credentials: "same-origin" }), []);
  const { messages, setMessages, sendMessage, regenerate, status, stop, error, clearError } = useChat({ id, messages: initialMessages, transport });
  const { markSend, stepMs, elapsedMs, withTimings } = useTimings(messages, status);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const composer = useRef<ComposerHandle>(null);
  const busy = status === "submitted" || status === "streaming";

  // A 401 anywhere means the session ended: back to the access screen.
  const apiErr = error as ApiErr | undefined;
  useEffect(() => {
    if (apiErr?.statusCode === 401) onUnauthorized();
  }, [apiErr, onUnauthorized]);

  // Voice (SPEC §10): a delegated answer joins the conversation as a user question plus an assistant message
  // carrying the analyst's tool parts, so the steps, the Evidence panel and the history treat it like a typed one.
  const [voiceSaves, setVoiceSaves] = useState(0);
  const onVoiceAnswer = useCallback(
    (question: string, result: AnalystResult) => {
      const asked = { id: `voice-${result.message_id}`, role: "user", parts: [{ type: "text", text: question }], metadata: { voice: true } };
      const answered = {
        id: result.message_id,
        role: "assistant",
        parts: result.parts,
        metadata: { voice: true, timing: { elapsed_ms: result.elapsed_ms } },
      };
      setFocusedId(null);
      setMessages((prev) => [...prev, asked as UIMessage, answered as UIMessage]);
      setVoiceSaves((n) => n + 1);
    },
    [setMessages],
  );
  const voiceAvailable = useVoiceAvailable();
  const voice = useVoiceCall(id, onVoiceAnswer);

  // Save after every finished answer, typed or spoken (SPEC §7: the body is the useChat UI-message array).
  const prevBusy = useRef(busy);
  const savedVoice = useRef(0);
  useEffect(() => {
    const wasBusy = prevBusy.current;
    prevBusy.current = busy;
    const voiceDue = voiceSaves !== savedVoice.current;
    savedVoice.current = voiceSaves;
    if (!historyEnabled || busy || (!wasBusy && !voiceDue)) return;
    if (!messages.some((m) => m.role === "assistant")) return;
    const t = title || titleFrom(messages);
    saveConversation(id, withTimings(messages), t)
      .then((s) => {
        setSaveFailed(false);
        onSaved(s ?? { id, title: t, updated_at: new Date().toISOString() });
      })
      .catch((e: { status?: number }) => {
        if (e?.status === 401) onUnauthorized();
        else setSaveFailed(true);
      });
  }, [busy, historyEnabled, id, messages, onSaved, onUnauthorized, title, voiceSaves, withTimings]);

  // The panel opens by itself after the first tool call of a chat (the shell keeps it closed if the user closed it).
  const hasTools = messages.some((m) => m.parts.some(isToolPart));
  const autoOpened = useRef(false);
  const setPanelOpen = panel.setOpen;
  useEffect(() => {
    if (hasTools && !autoOpened.current) {
      autoOpened.current = true;
      setPanelOpen(true, false);
    }
  }, [hasTools, setPanelOpen]);

  const ask = (text: string) => {
    if (!text.trim() || busy) return;
    clearError();
    markSend();
    setFocusedId(null);
    void sendMessage({ text });
  };

  const showEvidence = (messageId: string) => {
    setFocusedId(messageId);
    panel.setOpen(true, true);
  };

  const last = messages.at(-1);
  const followups = last && last.role === "assistant" && status === "ready" ? followupsOf(last) : [];
  const awaiting = status === "submitted" && last?.role === "user";
  const chatTitle = title || (messages.length ? titleFrom(messages) : "New chat");

  const panelEl = (
    <MissionPanel
      messages={messages}
      status={status}
      focusedId={focusedId}
      onFocusLatest={() => setFocusedId(null)}
      stepMs={stepMs}
      onClose={() => panel.setOpen(false, true)}
      overlay={panel.overlay}
    />
  );

  return (
    <div className="flex min-w-0 flex-1">
      <main className="flex min-w-0 flex-1 flex-col" aria-label="Conversation">
        <header className="flex h-[52px] shrink-0 items-center gap-2 border-b border-[var(--hairline)] px-4 md:px-6">
          {showMenuButton ? (
            <button
              type="button"
              onClick={onOpenNav}
              aria-label="Open menu"
              className="-ml-1 grid size-9 place-items-center rounded-[10px] hover:bg-[var(--tint)]"
            >
              <MenuIcon className="size-[18px]" />
            </button>
          ) : null}
          <h1 className="min-w-0 truncate text-[13px] font-semibold" title={chatTitle}>
            {chatTitle}
          </h1>
          {messages.length > 0 && (!panel.open || panel.overlay) ? (
            <button
              type="button"
              onClick={() => panel.setOpen(!panel.open, true)}
              aria-pressed={panel.open}
              className="ml-auto flex h-8 items-center gap-1.5 rounded-[10px] border border-[var(--hairline-strong)] px-2.5 text-[12.5px] hover:bg-[var(--tint)]"
            >
              {busy ? <span aria-hidden className="live-dot size-1.5 rounded-full" /> : <PanelRightIcon className="size-3.5" />}
              Mission
            </button>
          ) : null}
        </header>

        <Conversation className="min-h-0 flex-1">
          <ConversationContent className="mx-auto w-full max-w-[768px] gap-7 px-4 pb-10 pt-8 md:px-6">
            {messages.length === 0 ? <Welcome onAsk={ask} disabled={busy} /> : null}
            {messages.map((m) =>
              m.role === "user" ? (
                <UserMessage key={m.id} message={m} />
              ) : (
                <AssistantMessage
                  key={m.id}
                  message={m}
                  streaming={busy && m.id === last?.id}
                  stepMs={stepMs}
                  elapsedMs={elapsedMs(m)}
                  onShowEvidence={() => showEvidence(m.id)}
                />
              ),
            )}
            {awaiting ? (
              <p className="land flex items-center gap-2 text-[13px] text-[var(--live-ink)]" role="status">
                <span aria-hidden className="live-dot size-2 rounded-full" /> Working on it…
              </p>
            ) : null}
            {followups.length > 0 ? (
              <div className="land flex flex-wrap gap-2" data-testid="followups" aria-label="Suggested follow-ups">
                {followups.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => ask(q)}
                    className="rounded-[10px] border border-[var(--hairline-strong)] px-3 py-1.5 text-left text-[13px] hover:border-[var(--ink-muted)] hover:bg-[var(--tint)]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            ) : null}
            {error && apiErr?.statusCode !== 401 ? (
              <div
                role="alert"
                className="flex flex-wrap items-center gap-3 rounded-[10px] border border-[color-mix(in_oklab,var(--bad)_40%,transparent)] px-4 py-3 text-[13px]"
              >
                <span className="min-w-0 flex-1">{chatErrorMessage(apiErr as ApiErr)}</span>
                {apiErr?.statusCode !== 413 ? (
                  <button
                    type="button"
                    onClick={() => {
                      clearError();
                      markSend();
                      void regenerate();
                    }}
                    className="flex items-center gap-1.5 rounded-[10px] border border-[var(--hairline-strong)] px-2.5 py-1 hover:bg-[var(--tint)]"
                  >
                    <RotateCwIcon className="size-3.5" /> Try again
                  </button>
                ) : null}
              </div>
            ) : null}
          </ConversationContent>
          <ConversationScrollButton className="bg-[var(--card-surface)]" />
        </Conversation>

        <div className="mx-auto w-full max-w-[808px] px-4 pb-4 md:px-6 md:pb-5">
          <CallBar state={voice.state} onEnd={voice.end} onDismiss={voice.dismiss} />
          <Composer
            ref={composer}
            status={status}
            onSubmit={ask}
            onStop={stop}
            onCall={voiceAvailable ? voice.start : undefined}
            callActive={voice.active}
          />
          <p className="mt-2 text-center text-[11.5px] text-[var(--ink-muted)]">
            Scores screen candidates from public FAA and BTS data; they don&apos;t prove a renovation would pay off.
            {saveFailed ? <span className="text-[var(--warn)]"> · This chat couldn&apos;t be saved to history.</span> : null}
          </p>
        </div>
      </main>

      {panel.open && !panel.overlay ? (
        <aside aria-label="Mission panel" className="panel-in w-[400px] shrink-0 border-l border-[var(--hairline)] bg-[var(--ground)]">
          {panelEl}
        </aside>
      ) : null}
      {panel.open && panel.overlay ? (
        <Overlay onClose={() => panel.setOpen(false, true)}>
          <aside
            aria-label="Mission panel"
            role="dialog"
            aria-modal="true"
            className="sheet-in fixed inset-0 z-50 bg-[var(--ground)] sm:inset-y-0 sm:left-auto sm:right-0 sm:w-[420px] sm:border-l sm:border-[var(--hairline)] sm:shadow-[var(--shadow-float)]"
          >
            {panelEl}
          </aside>
        </Overlay>
      ) : null}
    </div>
  );
}

/** Scrim + Escape-to-close for drawers and sheets. */
export function Overlay({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <>
      <div aria-hidden className="fixed inset-0 z-40 bg-[var(--scrim)]" onClick={onClose} />
      {children}
    </>
  );
}

function Welcome({ onAsk, disabled }: { onAsk: (q: string) => void; disabled: boolean }) {
  return (
    <div className="flex flex-col items-center gap-7 pt-[12vh] text-center max-sm:pt-[6vh]" data-testid="welcome">
      <div className="space-y-3">
        <h2 className="font-serif text-[44px] leading-[1.08] tracking-[-0.01em] max-sm:text-[36px]">
          Where should the next terminal go?
        </h2>
        <p className="mx-auto max-w-[34rem] text-[14px] text-[var(--ink-muted)]">
          Rank and compare US Primary Airports on a deterministic Investment Opportunity Score, with every number traced
          to public FAA and BTS data.
        </p>
      </div>
      <ul className="grid w-full max-w-[640px] gap-2 sm:grid-cols-2" aria-label="Starter questions">
        {STARTERS.map((q) => (
          <li key={q}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onAsk(q)}
              className="h-full w-full rounded-[16px] border border-[var(--hairline-strong)] bg-[var(--card-surface)] px-4 py-3 text-left text-[13.5px] leading-[1.45] shadow-[var(--shadow-card)] hover:border-[var(--ink-muted)] disabled:opacity-50"
            >
              {q}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UserMessage({ message }: { message: UIMessage }) {
  const text = message.parts
    .filter((p): p is Extract<Part, { type: "text" }> => p.type === "text")
    .map((p) => p.text)
    .join("");
  return (
    <div className="land flex justify-end" data-role="user">
      <p className="max-w-[85%] whitespace-pre-wrap rounded-[16px] bg-[var(--tint-strong)] px-4 py-2.5 text-[14px] leading-[1.5]">
        {text}
      </p>
    </div>
  );
}

function AssistantMessage({
  message,
  streaming,
  stepMs,
  elapsedMs,
  onShowEvidence,
}: {
  message: UIMessage;
  streaming: boolean;
  stepMs: (id: string) => number | undefined;
  elapsedMs?: number;
  onShowEvidence: () => void;
}) {
  const steps = stepsOf(message);
  const reasoning = message.parts
    .filter((p): p is Extract<Part, { type: "reasoning" }> => p.type === "reasoning")
    .map((p) => p.text)
    .join("\n\n");
  const texts = answerTextsOf(message);
  const evidence = evidenceOf(message);
  const level = lowestConfidence(evidence);
  const hasText = texts.some((t) => t.text.trim());
  return (
    <article className="land flex flex-col gap-2" data-role="assistant" data-testid="assistant-message">
      {reasoning ? <ThoughtRow text={reasoning} streaming={streaming && !hasText && steps.length === 0} /> : null}
      <StepsRow steps={steps} stepMs={stepMs} elapsedMs={streaming ? undefined : elapsedMs} />
      {texts.map((t, i) => (
        <MessageResponse key={i} isAnimating={streaming} className="text-[14px] leading-[1.6]">
          {t.text}
        </MessageResponse>
      ))}
      {!streaming && evidence.length > 0 ? (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {level ? <ConfidenceBadge level={level} /> : null}
          <button
            type="button"
            onClick={onShowEvidence}
            className={cn(
              "flex h-[26px] items-center gap-1.5 rounded-[6px] border border-[var(--hairline-strong)] px-2 text-[12px] hover:bg-[var(--tint)]",
            )}
          >
            <PanelRightIcon className="size-3.5" /> Evidence · {evidence.length}
          </button>
        </div>
      ) : null}
    </article>
  );
}
