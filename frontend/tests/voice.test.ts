// The voice call's data-channel handling (lib/voice.ts) against a fake "oai-events" channel and fake timers.
import { afterEach, beforeEach, describe, expect, it, type Mock, vi } from "vitest";
import { ApiError } from "@/lib/api";
import {
  type AnalystResult,
  type CallDeps,
  type CallState,
  type ChannelLike,
  CLOSE_TIMEOUT_MS,
  MAX_CALL_MS,
  PROGRESS_NOTE,
  VoiceCall,
  callErrorMessage,
} from "@/lib/voice";

class FakeChannel implements ChannelLike {
  readyState = "open";
  sent: Record<string, unknown>[] = [];
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;
  send(data: string) {
    this.sent.push(JSON.parse(data));
  }
  close() {
    this.closed = true;
    this.readyState = "closed";
  }
  emit(ev: Record<string, unknown>) {
    this.onmessage?.({ data: JSON.stringify(ev) });
  }
  ofType(type: string) {
    return this.sent.filter((e) => e.type === type);
  }
}

const RESULT: AnalystResult = {
  text: "2.7% of scheduled passenger departures from Anchorage are Long-haul Flights. Data Confidence is High.",
  message_id: "msg-1",
  parts: [{ type: "tool-route_mix", toolCallId: "c1", state: "output-available", input: { iata: "ANC" }, output: {} }],
  tools: ["route_mix", "suggest_followups"],
  elapsed_ms: 12_000,
};

type AnalystFn = (question: string, signal: AbortSignal) => Promise<AnalystResult>;

function setup(analyst: Mock<AnalystFn> = vi.fn<AnalystFn>(async () => RESULT)) {
  const states: CallState[] = [];
  const answers: [string, AnalystResult][] = [];
  const deps = { analyst, now: () => Date.now() } as unknown as CallDeps;
  const call = new VoiceCall(deps, {
    onState: (s) => states.push(s),
    onAnswer: (q, r) => answers.push([q, r]),
  });
  // A connected call: tests drive the channel directly (start() needs real WebRTC).
  (call as unknown as { state: CallState }).state = { ...call.state, phase: "connecting" };
  const ch = new FakeChannel();
  call.attach(ch);
  return { call, ch, states, answers, analyst };
}

const delta = (ch: FakeChannel, text: string) => ch.emit({ type: "session.input_transcript.delta", delta: text, start_ms: 0, end_ms: 10 });
const delegation = (ch: FakeChannel, id: string) =>
  ch.emit({ type: "session.delegation.created", delegation: { id, type: "delegation", target: "client" }, offset_ms: 4000 });

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-22T10:00:00Z"));
});
afterEach(() => vi.useRealTimers());

describe("voice call events", () => {
  it("sends nothing before session.started and starts the timer on it", () => {
    const { call, ch } = setup();
    expect(ch.sent).toEqual([]);
    ch.emit({ type: "session.started", session: { id: "live_1" } });
    expect(call.state.phase).toBe("listening");
    expect(call.state.startedAt).toBe(Date.now());
    expect(ch.sent.some((e) => e.type === "session.start")).toBe(false);
  });

  it("assembles the question from transcript deltas exactly as received", async () => {
    const { ch, analyst } = setup();
    ch.emit({ type: "session.started" });
    for (const d of ["What is the ", "percentage of long", " haul flights out of ", "Anchorage airport?"]) delta(ch, d);
    delegation(ch, "del_1");
    await vi.advanceTimersByTimeAsync(1_000);
    expect(analyst).toHaveBeenCalledOnce();
    expect(analyst.mock.calls[0][0]).toBe("What is the percentage of long haul flights out of Anchorage airport?");
  });

  it("waits for late transcript deltas before asking, and each delegation gets only its own words", async () => {
    const { ch, analyst } = setup();
    ch.emit({ type: "session.started" });
    delta(ch, "How about");
    delegation(ch, "del_1");
    await vi.advanceTimersByTimeAsync(300);
    delta(ch, " SFO unmet demand?"); // arrives after the delegation event
    await vi.advanceTimersByTimeAsync(1_000);
    expect(analyst.mock.calls[0][0]).toBe("How about SFO unmet demand?");
    delta(ch, "And Boston?");
    delegation(ch, "del_2");
    await vi.advanceTimersByTimeAsync(1_000);
    expect(analyst.mock.calls[1][0]).toBe("And Boston?");
  });

  it("delegation → analyst → commentary.append with the matching delegation_id, then the answer joins the chat", async () => {
    let resolve!: (r: AnalystResult) => void;
    const analyst = vi.fn<AnalystFn>(() => new Promise<AnalystResult>((r) => (resolve = r)));
    const { call, ch, answers } = setup(analyst);
    ch.emit({ type: "session.started" });
    delta(ch, "What is the percentage of long haul flights out of Anchorage airport?");
    delegation(ch, "del_42");
    expect(call.state.phase).toBe("thinking"); // "Pulling the numbers…"
    await vi.advanceTimersByTimeAsync(1_000);

    const [think] = ch.ofType("session.thinking.append");
    expect(think).toMatchObject({ delegation_id: "del_42", content: PROGRESS_NOTE });
    expect(ch.ofType("session.commentary.append")).toEqual([]);

    // gpt-live-1 keeps the caller company while the analyst works; the phase stays "thinking"
    ch.emit({ type: "session.output_transcript.delta", delta: "Pulling the numbers now.", start_ms: 1, end_ms: 2 });
    expect(call.state.phase).toBe("thinking");
    expect(call.state.modelCaption).toBe("Pulling the numbers now.");

    resolve(RESULT);
    await vi.advanceTimersByTimeAsync(0);
    const [comm] = ch.ofType("session.commentary.append");
    expect(comm).toMatchObject({ type: "session.commentary.append", delegation_id: "del_42", content: RESULT.text });
    expect(typeof comm.event_id).toBe("string");
    expect(answers).toEqual([["What is the percentage of long haul flights out of Anchorage airport?", RESULT]]);
    expect(call.state.phase).toBe("listening");

    ch.emit({ type: "session.commentary.appended", client_event_id: comm.event_id });
    expect(call.acknowledged.has(comm.event_id as string)).toBe(true);

    ch.emit({ type: "session.output_transcript.delta", delta: "About 2.7% of", start_ms: 3, end_ms: 4 });
    expect(call.state.phase).toBe("speaking");
    expect(call.state.modelCaption).toBe("About 2.7% of"); // the spoken answer starts a fresh caption
    await vi.advanceTimersByTimeAsync(2_000);
    expect(call.state.phase).toBe("listening");
  });

  it("captions show the latest user utterance and the model's spoken words", () => {
    const { call, ch } = setup();
    ch.emit({ type: "session.started" });
    delta(ch, "Hello");
    delta(ch, " there");
    expect(call.state.userCaption).toBe("Hello there");
    ch.emit({ type: "session.output_transcript.delta", delta: "Hi, ask me" });
    ch.emit({ type: "session.output_transcript.delta", delta: " about airports." });
    expect(call.state.modelCaption).toBe("Hi, ask me about airports.");
    delta(ch, "Rank New England");
    expect(call.state.userCaption).toBe("Rank New England");
  });

  it("an analyst error is spoken as a friendly line for that delegation, without figures", async () => {
    const analyst = vi.fn<AnalystFn>(async () => {
      throw new ApiError(429, "You have reached the demo limit of 30 messages an hour for this session.");
    });
    const { ch, answers } = setup(analyst);
    ch.emit({ type: "session.started" });
    delta(ch, "Rank Texas airports");
    delegation(ch, "del_9");
    await vi.advanceTimersByTimeAsync(1_000);
    const [comm] = ch.ofType("session.commentary.append");
    expect(comm.delegation_id).toBe("del_9");
    expect(String(comm.content)).toContain("demo limit of 30 messages");
    expect(answers).toEqual([]);
  });

  it("ends itself at 5:00 with session.close, then waits for session.closed before releasing", async () => {
    const { call, ch } = setup();
    ch.emit({ type: "session.started" });
    await vi.advanceTimersByTimeAsync(MAX_CALL_MS - 1_000);
    expect(ch.ofType("session.close")).toEqual([]);
    await vi.advanceTimersByTimeAsync(1_000);
    expect(ch.ofType("session.close")).toHaveLength(1);
    expect(call.state.phase).toBe("ending");
    expect(ch.closed).toBe(false); // still reading until session.closed
    ch.emit({ type: "session.closed", reason: "close_requested", usage: { seconds: 300 } });
    await vi.advanceTimersByTimeAsync(0);
    expect(call.state.phase).toBe("ended");
    expect(ch.closed).toBe(true);
    expect(call.state.error).toBeNull();
  });

  it("closes after the timeout when session.closed never comes", async () => {
    const { call, ch } = setup();
    ch.emit({ type: "session.started" });
    const ended = call.end();
    expect(ch.ofType("session.close")).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(CLOSE_TIMEOUT_MS - 1);
    expect(call.state.phase).toBe("ending");
    await vi.advanceTimersByTimeAsync(1);
    await ended;
    expect(call.state.phase).toBe("ended");
    expect(ch.closed).toBe(true);
  });

  it("hanging up mid-answer aborts the analyst request and sends no commentary", async () => {
    let signal!: AbortSignal;
    const analyst = vi.fn<AnalystFn>((_q, s) => {
      signal = s;
      return new Promise<AnalystResult>(() => undefined);
    });
    const { call, ch } = setup(analyst);
    ch.emit({ type: "session.started" });
    delta(ch, "Compare LAX and SNA");
    delegation(ch, "del_5");
    await vi.advanceTimersByTimeAsync(1_000);
    void call.end();
    expect(signal.aborted).toBe(true);
    ch.emit({ type: "session.closed" });
    await vi.advanceTimersByTimeAsync(0);
    expect(ch.ofType("session.commentary.append")).toEqual([]);
    expect(call.state.phase).toBe("ended");
  });

  it("a server-side close (e.g. expired) ends the call without an error", async () => {
    const { call, ch } = setup();
    ch.emit({ type: "session.started" });
    ch.emit({ type: "session.closed", reason: "expired" });
    await vi.advanceTimersByTimeAsync(0);
    expect(call.state.phase).toBe("ended");
    expect(call.state.error).toBeNull();
  });
});

describe("start() and friendly errors", () => {
  it("mic denial is a friendly message, and no session is requested", async () => {
    const createSession = vi.fn();
    const call = new VoiceCall(
      {
        getUserMedia: () => Promise.reject(Object.assign(new Error("denied"), { name: "NotAllowedError" })),
        createPeer: vi.fn(),
        createSession,
        analyst: vi.fn(),
      } as unknown as CallDeps,
      { onState: () => undefined, onAnswer: () => undefined },
    );
    await call.start();
    expect(call.state.phase).toBe("ended");
    expect(call.state.error).toMatch(/Microphone access was blocked/);
    expect(createSession).not.toHaveBeenCalled();
  });

  it("creates the data channel before the offer and passes the offer and answer SDP through", async () => {
    const order: string[] = [];
    const track = { stop: vi.fn() };
    const mic = { getTracks: () => [track] } as unknown as MediaStream;
    const ch = new FakeChannel();
    const pc = {
      iceGatheringState: "complete",
      localDescription: { sdp: "v=0 offer" },
      addTrack: vi.fn(() => order.push("addTrack")),
      createDataChannel: vi.fn((label: string) => {
        order.push(`channel:${label}`);
        return ch;
      }),
      createOffer: vi.fn(async () => {
        order.push("createOffer");
        return { type: "offer", sdp: "v=0 offer" };
      }),
      setLocalDescription: vi.fn(async () => void order.push("setLocal")),
      setRemoteDescription: vi.fn(async (d: RTCSessionDescriptionInit) => void order.push(`setRemote:${d.sdp}`)),
      close: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    };
    const createSession = vi.fn(async (sdp: string) => {
      order.push(`post:${sdp}`);
      return { session_id: "live_1", sdp: "v=0 answer", max_call_s: 300 };
    });
    const call = new VoiceCall(
      { getUserMedia: async () => mic, createPeer: () => pc as unknown as RTCPeerConnection, createSession, analyst: vi.fn() },
      { onState: () => undefined, onAnswer: () => undefined },
    );
    await call.start();
    expect(order).toEqual(["addTrack", "channel:oai-events", "createOffer", "setLocal", "post:v=0 offer", "setRemote:v=0 answer"]);
    expect(call.state.phase).toBe("connecting");
    ch.emit({ type: "session.started" });
    expect(call.state.phase).toBe("listening");
    const ended = call.end();
    ch.emit({ type: "session.closed" });
    await ended;
    expect(pc.close).toHaveBeenCalled();
    expect(track.stop).toHaveBeenCalled(); // the mic is released
  });

  it("429 and 503 from our backend show their friendly text", () => {
    expect(callErrorMessage(new ApiError(429, "The demo's 10 voice calls for today have been used."))).toMatch(/10 voice calls/);
    expect(callErrorMessage(new ApiError(503, "Voice calls are not available on this server."))).toMatch(/not available/);
    expect(callErrorMessage(new TypeError("Failed to fetch"))).toMatch(/could not be connected/);
    expect(callErrorMessage(Object.assign(new Error("x"), { name: "NotSupportedError" }))).toMatch(/microphone permission/);
  });
});
