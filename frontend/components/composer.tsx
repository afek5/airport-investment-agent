"use client";

import type { ChatStatus } from "ai";
import { ArrowUpIcon, PhoneIcon, SquareIcon } from "lucide-react";
import { forwardRef, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export const MAX_MESSAGE_CHARS = 2000;

export interface ComposerHandle {
  focus: () => void;
}

/** The message composer: Enter sends, Shift+Enter adds a line, the button stops a running answer.
 * `onCall` (only when the server offers voice) adds the Call button; it hides while a call is on. */
export const Composer = forwardRef<ComposerHandle, {
  status: ChatStatus;
  onSubmit: (text: string) => void;
  onStop: () => void;
  disabled?: boolean;
  onCall?: () => void;
  callActive?: boolean;
}>(function Composer({ status, onSubmit, onStop, disabled, onCall, callActive }, ref) {
  const [text, setText] = useState("");
  const area = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => ({ focus: () => area.current?.focus() }), []);
  const busy = status === "submitted" || status === "streaming";
  const over = text.length > MAX_MESSAGE_CHARS;
  const canSend = !!text.trim() && !busy && !over && !disabled;

  // Grow with content up to the max height.
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [text]);

  const send = () => {
    if (!canSend) return;
    onSubmit(text.trim());
    setText("");
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className="rounded-[28px] border border-[var(--hairline-strong)] bg-[var(--card-surface)] p-2 pl-5 shadow-[var(--shadow-card)] transition-shadow focus-within:shadow-[var(--shadow-float)] max-sm:pl-4"
    >
      <div className="flex items-end gap-2">
        <label htmlFor="composer" className="sr-only">
          Ask about US airports
        </label>
        <textarea
          id="composer"
          ref={area}
          placeholder="Ask about US airports…"
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          aria-invalid={over || undefined}
          aria-describedby={over ? "composer-limit" : undefined}
          className="max-h-[200px] min-h-10 flex-1 resize-none bg-transparent py-2.5 text-[14px] leading-[1.45] outline-none placeholder:text-[var(--ink-muted)] focus-visible:outline-none"
        />
        {onCall && !callActive ? (
          <button
            type="button"
            onClick={onCall}
            aria-label="Start a voice call"
            title="Voice call (up to 5 minutes)"
            data-testid="call-button"
            className="grid size-10 shrink-0 place-items-center rounded-full border border-[var(--hairline-strong)] text-[var(--ink)] hover:bg-[var(--tint)]"
          >
            <PhoneIcon className="size-4" />
          </button>
        ) : null}
        {busy ? (
          <button
            type="button"
            aria-label="Stop the answer"
            onClick={onStop}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-[var(--ink)] text-[var(--ground)] hover:opacity-90"
          >
            <SquareIcon className="size-3.5" fill="currentColor" />
          </button>
        ) : (
          <button
            type="submit"
            aria-label="Send"
            disabled={!canSend}
            className="grid size-10 shrink-0 place-items-center rounded-full bg-[var(--ink)] text-[var(--ground)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <ArrowUpIcon className="size-4" strokeWidth={2.25} />
          </button>
        )}
      </div>
      {text.length > MAX_MESSAGE_CHARS * 0.9 ? (
        <p
          id="composer-limit"
          className={cn("num px-1 pb-1 text-right text-[11.5px]", over ? "text-[var(--bad)]" : "text-[var(--ink-muted)]")}
        >
          {text.length.toLocaleString("en-US")} / {MAX_MESSAGE_CHARS.toLocaleString("en-US")}
          {over ? " · shorten the message to send it" : ""}
        </p>
      ) : null}
    </form>
  );
});
