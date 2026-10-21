"use client";

import { MessagesSquareIcon, MoonIcon, PlaneTakeoffIcon, PlusIcon, SunIcon } from "lucide-react";
import type { Theme } from "@/lib/theme";
import { cn } from "@/lib/utils";

function RailItem({
  icon,
  label,
  onClick,
  pressed,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  pressed?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-pressed={pressed}
      title={label}
      className={cn(
        "flex h-11 w-full shrink-0 items-center gap-3 overflow-hidden rounded-[22px] px-[14px] text-[13px] text-[var(--ink-muted)] hover:bg-[var(--tint-strong)] hover:text-[var(--ink)]",
        pressed && "bg-[var(--tint-strong)] text-[var(--ink)]",
      )}
    >
      <span className="grid size-5 shrink-0 place-items-center">{icon}</span>
      <span className="whitespace-nowrap opacity-0 transition-opacity duration-150 group-hover/rail:opacity-100 group-has-[:focus-visible]/rail:opacity-100">
        {label}
      </span>
    </button>
  );
}

/**
 * The 76px icon rail. On hover or keyboard focus it widens to 248px with labels, over the workspace
 * (absolutely positioned), so the layout beside it never moves.
 */
export function Rail({
  onNewChat,
  onToggleRecent,
  recentOpen,
  theme,
  onToggleTheme,
}: {
  onNewChat: () => void;
  onToggleRecent: () => void;
  recentOpen: boolean;
  theme: Theme;
  onToggleTheme: () => void;
}) {
  return (
    <nav aria-label="Main" className="relative z-30 w-[76px] shrink-0" data-testid="rail">
      <div className="group/rail absolute inset-y-0 left-0 flex w-[76px] flex-col gap-1 border-r border-[var(--hairline)] bg-[var(--rail)] px-[14px] py-3 transition-[width,box-shadow] duration-200 ease-out hover:w-[248px] hover:shadow-[var(--shadow-float)] has-[:focus-visible]:w-[248px] has-[:focus-visible]:shadow-[var(--shadow-float)]">
        <div className="mb-3 flex h-11 shrink-0 items-center gap-3 overflow-hidden px-[10px]">
          <span className="grid size-7 shrink-0 place-items-center rounded-[8px] bg-[var(--ink)] text-[var(--ground)]">
            <PlaneTakeoffIcon className="size-4" strokeWidth={2} />
          </span>
          <span className="whitespace-nowrap text-[13px] font-semibold leading-tight opacity-0 transition-opacity duration-150 group-hover/rail:opacity-100 group-has-[:focus-visible]/rail:opacity-100">
            Airport Investment
            <span className="block text-[11.5px] font-normal text-[var(--ink-muted)]">Intelligence agent</span>
          </span>
        </div>
        <RailItem icon={<PlusIcon className="size-[18px]" />} label="New chat" onClick={onNewChat} />
        <RailItem
          icon={<MessagesSquareIcon className="size-[18px]" />}
          label="Recent chats"
          onClick={onToggleRecent}
          pressed={recentOpen}
        />
        <div className="flex-1" />
        <RailItem
          icon={theme === "dark" ? <SunIcon className="size-[18px]" /> : <MoonIcon className="size-[18px]" />}
          label={theme === "dark" ? "Light theme" : "Dark theme"}
          onClick={onToggleTheme}
        />
      </div>
    </nav>
  );
}
