"use client";
import { Component, type ReactNode } from "react";

/** Keeps one malformed tool payload from blanking the whole Mission panel. */
export class EvidenceBoundary extends Component<{ toolName: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <p className="text-[13px] text-[var(--ink-muted)]">
        <span className="num">{this.props.toolName}</span> returned data this view can&apos;t display. The raw output is
        in Trace.
      </p>
    );
  }
}
