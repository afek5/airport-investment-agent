"use client";

import type { ChatStatus } from "ai";
import { ArrowUpIcon, SquareIcon } from "lucide-react";
import { useState } from "react";

/** The message composer: Enter sends, Shift+Enter adds a line, the button stops a running answer. */
export function Composer({
  status,
  onSubmit,
  onStop,
}: {
  status: ChatStatus;
  onSubmit: (text: string) => void;
  onStop: () => void;
}) {
  const [text, setText] = useState("");
  const busy = status === "submitted" || status === "streaming";
  const send = () => {
    if (!text.trim() || busy) return;
    onSubmit(text);
    setText("");
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className="flex items-end gap-2 rounded-[28px] border border-[var(--hairline)] bg-[var(--card-surface)] p-2 pl-5 focus-within:shadow-lg"
    >
      <textarea
        aria-label="Message"
        placeholder="Ask about US airports…"
        rows={1}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        className="max-h-40 min-h-10 flex-1 resize-none bg-transparent py-2 text-sm outline-none placeholder:text-[var(--ink-muted)]"
      />
      {busy ? (
        <button
          type="button"
          aria-label="Stop"
          onClick={onStop}
          className="grid size-10 place-items-center rounded-[10px] bg-[var(--ink)] text-[var(--ground)]"
        >
          <SquareIcon className="size-4" />
        </button>
      ) : (
        <button
          type="submit"
          aria-label="Send"
          disabled={!text.trim()}
          className="grid size-10 place-items-center rounded-[10px] bg-[var(--ink)] text-[var(--ground)] disabled:opacity-40"
        >
          <ArrowUpIcon className="size-4" />
        </button>
      )}
    </form>
  );
}
