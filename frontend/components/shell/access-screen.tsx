"use client";

import { ArrowRightIcon, PlaneTakeoffIcon } from "lucide-react";
import { useState } from "react";
import { ApiError, startSession } from "@/lib/api";

/** Shown when there is no session: one access-code field (SPEC §8). */
export function AccessScreen({ onUnlocked }: { onUnlocked: () => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      await startSession(code.trim());
      onUnlocked();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 401
            ? "That access code isn't right. Check it and try again."
            : err.status === 429
              ? "Too many wrong codes from this network. Try again in an hour."
              : err.message,
        );
      } else {
        setError("Can't reach the server. Check the connection and try again.");
      }
      setBusy(false);
    }
  };

  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10" data-testid="access-screen">
      <div className="w-full max-w-[400px] space-y-7">
        <div className="space-y-4">
          <span className="grid size-9 place-items-center rounded-[10px] bg-[var(--ink)] text-[var(--ground)]">
            <PlaneTakeoffIcon className="size-[18px]" />
          </span>
          <div className="space-y-2">
            <p className="eyebrow">Airport Investment Intelligence</p>
            <h1 className="font-serif text-[40px] leading-[1.08]">Where should the next terminal go?</h1>
            <p className="text-[14px] leading-[1.55] text-[var(--ink-muted)]">
              A demo analyst that screens US airports for terminal investment from public FAA and BTS data. Enter the
              access code you were given to start.
            </p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-3" noValidate>
          <label htmlFor="access-code" className="block text-[13px] font-medium">
            Access code
          </label>
          <div className="flex gap-2">
            <input
              id="access-code"
              type="password"
              autoComplete="current-password"
              autoFocus
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                if (error) setError(null);
              }}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? "access-error" : undefined}
              className="num h-11 min-w-0 flex-1 rounded-[10px] border border-[var(--hairline-strong)] bg-[var(--card-surface)] px-3.5 text-[14px] outline-none placeholder:text-[var(--ink-muted)] focus-visible:border-[var(--ink-muted)] focus-visible:shadow-[0_0_0_3px_color-mix(in_oklab,var(--ink)_14%,transparent)] focus-visible:outline-none aria-[invalid]:border-[var(--bad)]"
            />
            <button
              type="submit"
              disabled={!code.trim() || busy}
              className="flex h-11 shrink-0 items-center gap-1.5 rounded-[10px] bg-[var(--ink)] px-4 text-[13px] font-semibold text-[var(--ground)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-35"
            >
              {busy ? "Checking…" : "Continue"}
              {!busy ? <ArrowRightIcon className="size-4" /> : null}
            </button>
          </div>
          {error ? (
            <p id="access-error" role="alert" className="text-[13px] text-[var(--bad)]">
              {error}
            </p>
          ) : null}
        </form>
      </div>
    </main>
  );
}
