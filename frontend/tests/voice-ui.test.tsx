// The Call button and the in-call bar (components/composer.tsx, components/chat/voice-call.tsx).
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CallBar, mmss } from "@/components/chat/voice-call";
import { Composer } from "@/components/composer";
import type { CallState } from "@/lib/voice";

const base: CallState = { phase: "listening", startedAt: Date.now() - 83_000, userCaption: "", modelCaption: "", error: null };

describe("Call button", () => {
  it("shows only when voice is available, and hides during a call", () => {
    const { rerender } = render(<Composer status="ready" onSubmit={vi.fn()} onStop={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Start a voice call" })).toBeNull();
    const onCall = vi.fn();
    rerender(<Composer status="ready" onSubmit={vi.fn()} onStop={vi.fn()} onCall={onCall} />);
    fireEvent.click(screen.getByRole("button", { name: "Start a voice call" }));
    expect(onCall).toHaveBeenCalledOnce();
    rerender(<Composer status="ready" onSubmit={vi.fn()} onStop={vi.fn()} onCall={onCall} callActive />);
    expect(screen.queryByRole("button", { name: "Start a voice call" })).toBeNull();
  });
});

describe("CallBar", () => {
  it("shows the state, the mm:ss timer, captions and an End button", () => {
    const onEnd = vi.fn();
    render(
      <CallBar
        state={{ ...base, phase: "thinking", userCaption: "Long haul out of Anchorage?", modelCaption: "Pulling the numbers now." }}
        onEnd={onEnd}
        onDismiss={vi.fn()}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Pulling the numbers…");
    expect(screen.getByText(/01:23/)).toBeInTheDocument();
    expect(screen.getByTestId("call-caption")).toHaveTextContent("Long haul out of Anchorage?");
    expect(screen.getByTestId("call-caption")).toHaveTextContent("Pulling the numbers now.");
    fireEvent.click(screen.getByRole("button", { name: /End/ }));
    expect(onEnd).toHaveBeenCalledOnce();
  });

  it.each([
    ["connecting", "Connecting…"],
    ["listening", "Listening"],
    ["speaking", "Speaking"],
  ] as const)("labels the %s phase", (phase, label) => {
    render(<CallBar state={{ ...base, phase }} onEnd={vi.fn()} onDismiss={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent(label);
  });

  it("an ended call with an error shows the friendly message as an alert; without one, nothing", () => {
    const { rerender, container } = render(
      <CallBar state={{ ...base, phase: "ended", error: "Microphone access was blocked." }} onEnd={vi.fn()} onDismiss={vi.fn()} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Microphone access was blocked.");
    rerender(<CallBar state={{ ...base, phase: "ended" }} onEnd={vi.fn()} onDismiss={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("formats mm:ss", () => {
    expect(mmss(0)).toBe("00:00");
    expect(mmss(59_999)).toBe("00:59");
    expect(mmss(300_000)).toBe("05:00");
  });
});
