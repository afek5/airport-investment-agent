"use client";

import { CheckIcon, Trash2Icon } from "lucide-react";
import { useEffect, useState } from "react";
import type { ConversationSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

export function relativeTime(iso?: string | null, now = Date.now()): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.round(h / 24);
  if (d < 7) return `${d}d`;
  return new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export type HistoryState = "loading" | "ready" | "unavailable" | "error";

export function RecentChats({
  conversations,
  state,
  activeId,
  onSelect,
  onDelete,
  onRetry,
}: {
  conversations: ConversationSummary[];
  state: HistoryState;
  activeId: string;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRetry: () => void;
}) {
  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="recent-chats">
      <h2 className="eyebrow flex h-[52px] shrink-0 items-center px-5">Recent chats</h2>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        {state === "loading" ? (
          <ul aria-label="Loading recent chats" className="space-y-2 px-2 pt-1">
            {[0, 1, 2].map((i) => (
              <li key={i} className="h-4 rounded-[6px] bg-[var(--tint-strong)]" style={{ width: `${82 - i * 14}%` }} />
            ))}
          </ul>
        ) : state === "unavailable" ? (
          <p className="px-2 text-[13px] text-[var(--ink-muted)]">Chat history isn&apos;t available on this server.</p>
        ) : state === "error" ? (
          <p className="px-2 text-[13px] text-[var(--ink-muted)]">
            Couldn&apos;t load recent chats.{" "}
            <button type="button" className="underline underline-offset-2 hover:text-[var(--ink)]" onClick={onRetry}>
              Try again
            </button>
          </p>
        ) : conversations.length === 0 ? (
          <p className="px-2 text-[13px] leading-[1.5] text-[var(--ink-muted)]">
            No saved chats yet. Each conversation is saved here after its first answer.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => (
              <ChatItem key={c.id} c={c} active={c.id === activeId} onSelect={onSelect} onDelete={onDelete} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ChatItem({
  c,
  active,
  onSelect,
  onDelete,
}: {
  c: ConversationSummary;
  active: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  useEffect(() => {
    if (!confirming) return;
    const t = setTimeout(() => setConfirming(false), 3000);
    return () => clearTimeout(t);
  }, [confirming]);
  return (
    <li className="group/item relative">
      <button
        type="button"
        onClick={() => onSelect(c.id)}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex w-full min-w-0 items-baseline gap-2 rounded-[10px] py-2 pl-3 pr-10 text-left text-[13px] hover:bg-[var(--tint)]",
          active && "bg-[var(--tint-strong)] font-medium",
        )}
      >
        <span className="min-w-0 flex-1 truncate">{c.title}</span>
        <span className="num shrink-0 text-[11px] text-[var(--ink-muted)] group-hover/item:invisible group-focus-within/item:invisible">
          {relativeTime(c.updated_at ?? c.created_at)}
        </span>
      </button>
      <button
        type="button"
        aria-label={confirming ? `Confirm delete “${c.title}”` : `Delete “${c.title}”`}
        onClick={() => (confirming ? onDelete(c.id) : setConfirming(true))}
        className={cn(
          "absolute right-1 top-1/2 grid size-7 -translate-y-1/2 place-items-center rounded-[8px] text-[var(--ink-muted)] opacity-0 hover:bg-[var(--tint-strong)] hover:text-[var(--ink)] focus-visible:opacity-100 group-hover/item:opacity-100",
          confirming && "text-[var(--bad)] opacity-100 hover:text-[var(--bad)]",
        )}
      >
        {confirming ? <CheckIcon className="size-3.5" /> : <Trash2Icon className="size-3.5" />}
      </button>
    </li>
  );
}
