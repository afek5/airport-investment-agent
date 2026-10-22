"use client";

import { PhoneOffIcon, XIcon } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import {
  type AnalystResult,
  browserDeps,
  type CallPhase,
  type CallState,
  MAX_CALL_MS,
  VoiceCall,
  voiceStatus,
} from "@/lib/voice";

const IDLE: CallState = { phase: "idle", startedAt: null, userCaption: "", modelCaption: "", error: null };

let statusOnce: Promise<boolean> | null = null;

/** Whether the server offers voice (OPENAI_API_KEY set). Asked once per page load. */
export function useVoiceAvailable(): boolean {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    let live = true;
    statusOnce ??= voiceStatus().then((s) => s.available);
    void statusOnce.then((a) => live && setAvailable(a));
    return () => {
      live = false;
    };
  }, []);
  return available;
}

/** One voice call at a time for this conversation; the delegated answers go to `onAnswer`. */
export function useVoiceCall(conversationId: string, onAnswer: (question: string, result: AnalystResult) => void) {
  const [state, setState] = useState<CallState>(IDLE);
  const call = useRef<VoiceCall | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  const answer = useRef(onAnswer);
  useEffect(() => {
    answer.current = onAnswer;
  }, [onAnswer]);

  const start = useCallback(() => {
    if (call.current?.active) return;
    audio.current ??= new Audio();
    audio.current.autoplay = true;
    const c = new VoiceCall(browserDeps(conversationId, audio.current), {
      onState: (s) => setState(s),
      onAnswer: (q, r) => answer.current(q, r),
    });
    call.current = c;
    void c.start();
  }, [conversationId]);

  const end = useCallback(() => void call.current?.end(), []);
  const dismiss = useCallback(() => setState(IDLE), []);

  // Leaving the conversation (or the page) hangs up.
  useEffect(() => () => void call.current?.end(), []);

  const active = state.phase !== "idle" && state.phase !== "ended";
  return { state, active, start, end, dismiss };
}

const LABEL: Record<CallPhase, string> = {
  idle: "",
  connecting: "Connecting…",
  listening: "Listening",
  thinking: "Pulling the numbers…",
  speaking: "Speaking",
  ending: "Ending the call…",
  ended: "Call ended",
};

export function mmss(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** The in-call bar above the composer: state, mm:ss timer, End, and the live caption. */
export function CallBar({ state, onEnd, onDismiss }: { state: CallState; onEnd: () => void; onDismiss: () => void }) {
  const [now, setNow] = useState(() => Date.now());
  const active = state.phase !== "idle" && state.phase !== "ended";
  const endButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!state.startedAt || !active) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [state.startedAt, active]);

  // Focus moves to End when the call starts, so the keyboard path can hang up at once.
  useEffect(() => {
    if (state.phase === "connecting") endButton.current?.focus();
  }, [state.phase]);

  if (state.phase === "idle") return null;
  if (state.phase === "ended") {
    if (!state.error) return null;
    return (
      <div
        role="alert"
        className="land mb-2 flex items-start gap-3 rounded-[16px] border border-[color-mix(in_oklab,var(--bad)_40%,transparent)] bg-[var(--card-surface)] px-4 py-3 text-[13px]"
        data-testid="call-error"
      >
        <span className="min-w-0 flex-1">{state.error}</span>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss"
          className="-mr-1 grid size-6 shrink-0 place-items-center rounded-[6px] text-[var(--ink-muted)] hover:bg-[var(--tint)]"
        >
          <XIcon className="size-3.5" />
        </button>
      </div>
    );
  }

  const elapsed = state.startedAt ? now - state.startedAt : 0;
  const working = state.phase === "thinking" || state.phase === "speaking" || state.phase === "listening";
  return (
    <section
      aria-label="Voice call"
      data-testid="call-bar"
      data-phase={state.phase}
      className="land mb-2 rounded-[16px] border border-[var(--hairline-strong)] bg-[var(--card-surface)] px-4 py-3 shadow-[var(--shadow-card)]"
    >
      <div className="flex items-center gap-3">
        <span
          aria-hidden
          className={cn(
            "size-2 shrink-0 rounded-full",
            working ? "live-dot" : "bg-[var(--ink-muted)] opacity-60",
          )}
        />
        <p className="min-w-0 flex-1 truncate text-[13px] font-medium" role="status" aria-live="polite">
          {LABEL[state.phase]}
        </p>
        <span className="num text-[12px] text-[var(--ink-muted)]" aria-label={`Call time ${mmss(elapsed)} of 5 minutes`}>
          {mmss(elapsed)} <span className="opacity-60 max-sm:hidden">/ {mmss(MAX_CALL_MS)}</span>
        </span>
        <button
          ref={endButton}
          type="button"
          onClick={onEnd}
          disabled={state.phase === "ending"}
          className="flex h-8 shrink-0 items-center gap-1.5 rounded-[10px] bg-[var(--ink)] px-3 text-[12.5px] font-medium text-[var(--ground)] hover:opacity-90 disabled:opacity-40"
        >
          <PhoneOffIcon className="size-3.5" /> End
        </button>
      </div>
      {state.userCaption || state.modelCaption ? (
        <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-[var(--hairline)] pt-2.5 text-[13px] leading-[1.45]" data-testid="call-caption">
          {state.userCaption ? (
            <>
              <dt className="eyebrow pt-[3px] text-[var(--ink-muted)]">You</dt>
              <dd className="min-w-0 break-words text-[var(--ink-muted)]">{state.userCaption}</dd>
            </>
          ) : null}
          {state.modelCaption ? (
            <>
              <dt className="eyebrow pt-[3px] text-[var(--ink-muted)]">Analyst</dt>
              <dd className="min-w-0 break-words">{state.modelCaption}</dd>
            </>
          ) : null}
        </dl>
      ) : (
        <p className="mt-1.5 pl-5 text-[12px] text-[var(--ink-muted)]">
          {state.phase === "connecting" ? "Allow the microphone if the browser asks." : "Ask about a US airport. The full evidence appears in the chat."}
        </p>
      )}
    </section>
  );
}
