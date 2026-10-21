"use client";
// Client-measured durations for tool steps and whole answers. The wire protocol carries no timings, so the
// browser times what it sees and stores the result in message metadata, which keeps it with saved history.
import type { ChatStatus, UIMessage } from "ai";
import { useCallback, useEffect, useRef, useState } from "react";
import { isToolPart } from "@/lib/parts";

interface Span {
  start: number;
  end?: number;
}

export interface TimingMeta {
  elapsed_ms?: number;
  steps?: Record<string, number>;
}

export function timingMetaOf(m: UIMessage): TimingMeta | undefined {
  const meta = m.metadata as { timing?: TimingMeta } | undefined;
  return meta && typeof meta === "object" ? meta.timing : undefined;
}

export function useTimings(messages: UIMessage[], status: ChatStatus) {
  const steps = useRef(new Map<string, Span>());
  const turns = useRef(new Map<string, Span>());
  const pendingStart = useRef<number | null>(null);
  const [version, setVersion] = useState(0);

  const markSend = useCallback(() => {
    pendingStart.current = performance.now();
  }, []);

  useEffect(() => {
    const now = performance.now();
    let changed = false;
    const live = status === "submitted" || status === "streaming";
    const last = messages.at(-1);
    for (const m of messages) {
      for (const p of m.parts) {
        if (!isToolPart(p)) continue;
        let s = steps.current.get(p.toolCallId);
        if (!s) {
          // Parts loaded from history (not streamed in this tab) get no client timing.
          if (!live || m !== last) continue;
          s = { start: now };
          steps.current.set(p.toolCallId, s);
          changed = true;
        }
        if (s.end == null && (p.state === "output-available" || p.state === "output-error" || p.state === "output-denied")) {
          s.end = now;
          changed = true;
        }
      }
    }
    if (last?.role === "assistant") {
      const t = turns.current.get(last.id);
      if (!t && live) {
        turns.current.set(last.id, { start: pendingStart.current ?? now });
        pendingStart.current = null;
        changed = true;
      } else if (t && t.end == null && !live) {
        t.end = now;
        changed = true;
      }
    }
    // Only ever re-render when a span opened or closed; the refs hold the times themselves.
    if (changed) setVersion((v) => v + 1);
  }, [messages, status]);

  const stepMs = useCallback(
    (id: string): number | undefined => {
      const s = steps.current.get(id);
      if (s?.end != null) return s.end - s.start;
      for (const m of messages) {
        const ms = timingMetaOf(m)?.steps?.[id];
        if (typeof ms === "number") return ms;
      }
      return undefined;
    },
    // `version` re-creates the reader after spans change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [messages, version],
  );

  const elapsedMs = useCallback(
    (m: UIMessage): number | undefined => {
      const t = turns.current.get(m.id);
      if (t?.end != null) return t.end - t.start;
      return timingMetaOf(m)?.elapsed_ms;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [version],
  );

  /** Messages with measured timings folded into assistant metadata, for saving. */
  const withTimings = useCallback(
    (msgs: UIMessage[]): UIMessage[] =>
      msgs.map((m) => {
        if (m.role !== "assistant") return m;
        const prev = timingMetaOf(m) ?? {};
        const stepsMs: Record<string, number> = { ...(prev.steps ?? {}) };
        for (const p of m.parts) {
          if (!isToolPart(p)) continue;
          const s = steps.current.get(p.toolCallId);
          if (s?.end != null) stepsMs[p.toolCallId] = Math.round(s.end - s.start);
        }
        const t = turns.current.get(m.id);
        const elapsed = t?.end != null ? Math.round(t.end - t.start) : prev.elapsed_ms;
        const base = (m.metadata && typeof m.metadata === "object" ? m.metadata : {}) as Record<string, unknown>;
        return { ...m, metadata: { ...base, timing: { elapsed_ms: elapsed, steps: stepsMs } } };
      }),
    [],
  );

  return { markSend, stepMs, elapsedMs, withTimings, version };
}
