// The voice call (SPEC §10, ADR 0004): gpt-live-1 over WebRTC in client-delegation mode.
//
// gpt-live-1 is only the voice. When it delegates (`session.delegation.created`, which carries no question text),
// the browser rebuilds the question from `session.input_transcript.delta`, asks our analyst (the same Claude agent
// as the chat, in spoken mode) and hands the answer back with `session.commentary.append` for that delegation.
// The analyst's tool parts go into the conversation, so the Evidence panel fills as for a typed question.
//
// Event names and order follow developers.openai.com/api/docs/guides/live-delegation and /realtime-webrtc
// (read 2026-10-22): wait for `session.started` before sending; never send `session.start`; close with
// `session.close` and keep reading until `session.closed`.
import { ApiError, messageFromBody } from "@/lib/api";

export const MAX_CALL_MS = 5 * 60 * 1000; // SPEC §9; the Live API documents no maximum, so the browser ends it
export const CLOSE_TIMEOUT_MS = 15_000;
export const ICE_TIMEOUT_MS = 10_000;
export const START_TIMEOUT_MS = 20_000;
/** A delegation's question is complete once no transcript delta has arrived for this long. */
export const TRANSCRIPT_SETTLE_MS = 600;
export const TRANSCRIPT_WAIT_MS = 4_000;
/** After the last spoken-transcript delta, the call goes back to "listening". */
export const SPEAKING_IDLE_MS = 1_500;
/** Commentary content is limited to 500 tokens; 120 spoken words fit well inside this. */
export const MAX_COMMENTARY_CHARS = 1_800;

export const PROGRESS_NOTE =
  "The analyst is pulling the numbers from the Snapshot now; it usually takes 10 to 30 seconds. Keep the caller company briefly and do not guess any figures.";

export type CallPhase = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "ending" | "ended";

export interface CallState {
  phase: CallPhase;
  /** Clock time of `session.started`; the mm:ss timer counts from it. */
  startedAt: number | null;
  userCaption: string;
  modelCaption: string;
  error: string | null;
}

export interface AnalystResult {
  text: string;
  message_id: string;
  parts: unknown[];
  tools: string[];
  elapsed_ms: number;
  guard?: string;
}

/** The subset of RTCDataChannel the call uses (a fake in tests). */
export interface ChannelLike {
  readyState: string;
  send(data: string): void;
  close(): void;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: (() => void) | null;
}

export interface CallDeps {
  getUserMedia: () => Promise<MediaStream>;
  createPeer: () => RTCPeerConnection;
  createSession: (sdp: string) => Promise<{ session_id: string; sdp: string; max_call_s?: number }>;
  analyst: (question: string, signal: AbortSignal) => Promise<AnalystResult>;
  onAudio?: (stream: MediaStream) => void;
  now?: () => number;
}

export interface CallCallbacks {
  onState: (s: CallState) => void;
  /** The delegated answer, to add to the conversation (user question + assistant message with tool parts). */
  onAnswer: (question: string, result: AnalystResult) => void;
  /** Every data-channel event in and out, for debugging and the e2e log. */
  onEvent?: (dir: "in" | "out", ev: Record<string, unknown>) => void;
}

type Ev = Record<string, unknown> & { type?: string };

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

let seq = 0;
const eventId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${(seq++).toString(36)}`;

/** A friendly line for a failure to start or keep the call. */
export function callErrorMessage(e: unknown): string {
  const name = (e as { name?: string })?.name;
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone access was blocked. Allow the microphone for this site in the browser, then call again.";
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return "No microphone was found. Connect one, then call again.";
  }
  if (e instanceof ApiError) {
    if (e.status === 401) return "Your session ended. Enter the access code again.";
    if (e.status === 429 || e.status === 503) return e.message;
    return e.message || "The call could not be connected. Please try again.";
  }
  return "The call could not be connected. Check the connection and try again.";
}

export class VoiceCall {
  state: CallState = { phase: "idle", startedAt: null, userCaption: "", modelCaption: "", error: null };
  private channel: ChannelLike | null = null;
  private pc: RTCPeerConnection | null = null;
  private mic: MediaStream | null = null;
  private input = ""; // the whole input transcript, deltas appended exactly as received
  private consumed = 0; // how much of `input` earlier delegations used
  private lastInputAt = 0;
  private lastSpeaker: "user" | "model" | null = null;
  private pending = 0; // delegations being answered
  private aborts = new Set<AbortController>();
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private speakingTimer: ReturnType<typeof setTimeout> | null = null;
  private closed: (() => void) | null = null;
  private started = false;
  readonly acknowledged = new Set<string>();
  readonly sent: Ev[] = [];

  constructor(
    private deps: CallDeps,
    private cb: CallCallbacks,
    private maxMs = MAX_CALL_MS,
  ) {}

  private now() {
    return this.deps.now ? this.deps.now() : Date.now();
  }

  private set(patch: Partial<CallState>) {
    this.state = { ...this.state, ...patch };
    this.cb.onState(this.state);
  }

  private later(ms: number, fn: () => void) {
    const t = setTimeout(() => {
      this.timers.delete(t);
      fn();
    }, ms);
    this.timers.add(t);
    return t;
  }

  get active() {
    return this.state.phase !== "idle" && this.state.phase !== "ended";
  }

  /** Mic → peer connection with the "oai-events" channel → offer via our backend → answer. From a user gesture. */
  async start(): Promise<void> {
    if (this.active) return;
    this.set({ phase: "connecting", error: null, userCaption: "", modelCaption: "", startedAt: null });
    try {
      this.mic = await this.deps.getUserMedia();
      if (this.state.phase !== "connecting") return this.teardown(); // hung up while the prompt was open
      const pc = this.deps.createPeer();
      this.pc = pc;
      for (const track of this.mic.getTracks()) pc.addTrack(track, this.mic);
      pc.ontrack = (e) => this.deps.onAudio?.(e.streams[0] ?? new MediaStream([e.track]));
      pc.onconnectionstatechange = () => {
        if (pc.connectionState === "failed" && this.active && this.state.phase !== "ending") {
          this.fail("The call connection dropped. Please call again.");
        }
      };
      this.attach(pc.createDataChannel("oai-events") as unknown as ChannelLike); // before the offer
      await pc.setLocalDescription(await pc.createOffer());
      await iceGathered(pc, ICE_TIMEOUT_MS);
      const offer = pc.localDescription?.sdp;
      if (!offer) throw new Error("no local description");
      const answer = await this.deps.createSession(offer);
      if (this.state.phase !== "connecting") return this.teardown();
      await pc.setRemoteDescription({ type: "answer", sdp: answer.sdp });
      if (answer.max_call_s) this.maxMs = Math.min(this.maxMs, answer.max_call_s * 1000);
      this.later(START_TIMEOUT_MS, () => {
        if (!this.started && this.state.phase === "connecting") this.fail("The call did not start. Please try again.");
      });
    } catch (e) {
      this.fail(callErrorMessage(e));
    }
  }

  /** Listen on the data channel (the real "oai-events" channel, or a fake in tests). */
  attach(channel: ChannelLike) {
    this.channel = channel;
    channel.onmessage = (e) => {
      let ev: Ev;
      try {
        ev = JSON.parse(String(e.data)) as Ev;
      } catch {
        return;
      }
      this.handle(ev);
    };
    channel.onclose = () => {
      this.closed?.();
      if (this.active && this.state.phase !== "ending") this.fail("The call was disconnected.");
    };
  }

  private send(ev: Ev): boolean {
    if (!this.channel || this.channel.readyState !== "open") return false;
    this.channel.send(JSON.stringify(ev));
    this.sent.push(ev);
    this.cb.onEvent?.("out", ev);
    return true;
  }

  handle(ev: Ev) {
    this.cb.onEvent?.("in", ev);
    switch (ev.type) {
      case "session.started":
        if (this.started) return;
        this.started = true;
        this.set({ phase: "listening", startedAt: this.now() });
        this.later(this.maxMs, () => void this.end());
        return;
      case "session.input_transcript.delta": {
        const delta = typeof ev.delta === "string" ? ev.delta : "";
        this.input += delta;
        this.lastInputAt = this.now();
        const fresh = this.lastSpeaker !== "user";
        this.lastSpeaker = "user";
        this.set({
          userCaption: tail((fresh ? "" : this.state.userCaption) + delta),
          ...(this.state.phase === "speaking" ? { phase: "listening" as const } : {}),
        });
        return;
      }
      case "session.output_transcript.delta": {
        const delta = typeof ev.delta === "string" ? ev.delta : "";
        const fresh = this.lastSpeaker !== "model";
        this.lastSpeaker = "model";
        this.set({
          modelCaption: tail((fresh ? "" : this.state.modelCaption) + delta),
          ...(this.pending === 0 && this.state.phase === "listening" ? { phase: "speaking" as const } : {}),
        });
        if (this.speakingTimer) clearTimeout(this.speakingTimer);
        this.speakingTimer = setTimeout(() => {
          if (this.state.phase === "speaking") this.set({ phase: "listening" });
        }, SPEAKING_IDLE_MS);
        return;
      }
      case "session.delegation.created": {
        const d = ev.delegation as { id?: unknown; target?: unknown } | undefined;
        if (typeof d?.id === "string" && (d.target === undefined || d.target === "client")) void this.delegate(d.id);
        return;
      }
      case "session.commentary.appended":
      case "session.thinking.appended":
        if (typeof ev.client_event_id === "string") this.acknowledged.add(ev.client_event_id);
        return;
      case "session.closed":
        this.closed?.();
        if (this.state.phase !== "ending") void this.finish();
        return;
      default:
        return;
    }
  }

  /** The user's words since the previous delegation, once the transcript has settled. */
  async questionSince(): Promise<string> {
    const deadline = this.now() + TRANSCRIPT_WAIT_MS;
    for (;;) {
      const text = this.input.slice(this.consumed).trim();
      const settled = this.now() - this.lastInputAt >= TRANSCRIPT_SETTLE_MS;
      if ((text && settled) || this.now() >= deadline) break;
      await wait(100);
    }
    const q = this.input.slice(this.consumed).replace(/\s+/g, " ").trim();
    this.consumed = this.input.length;
    return q.slice(-2000);
  }

  private async delegate(delegationId: string) {
    this.pending++;
    this.set({ phase: "thinking" });
    const abort = new AbortController();
    this.aborts.add(abort);
    let content: string;
    try {
      const question = await this.questionSince();
      if (!question) {
        content = "I did not catch the question. Please ask the caller to say it again.";
      } else {
        this.send({ type: "session.thinking.append", event_id: eventId("think"), delegation_id: delegationId, content: PROGRESS_NOTE });
        const result = await this.deps.analyst(question, abort.signal);
        if (abort.signal.aborted) return;
        this.cb.onAnswer(question, result);
        content = result.text || "The analyst returned no answer. Please ask again.";
      }
    } catch (e) {
      if (abort.signal.aborted) return;
      content =
        e instanceof ApiError && e.message
          ? `Tell the caller, without adding any figures: ${e.message}`
          : "Tell the caller the analyst could not answer just now, and suggest asking again or typing the question.";
    } finally {
      this.aborts.delete(abort);
      this.pending = Math.max(0, this.pending - 1);
    }
    this.send({
      type: "session.commentary.append",
      event_id: eventId("comm"),
      delegation_id: delegationId,
      content: content.slice(0, MAX_COMMENTARY_CHARS),
    });
    this.lastSpeaker = null; // the spoken answer starts a fresh caption
    if (this.pending === 0 && this.state.phase === "thinking") this.set({ phase: "listening" });
  }

  /** Hang up: session.close, then wait for session.closed (final usage) or the timeout, then release everything. */
  async end(): Promise<void> {
    if (!this.active || this.state.phase === "ending") return;
    for (const a of this.aborts) a.abort(); // cancel analyst work in our own backend (no cancel event exists)
    const canClose = this.started && this.channel?.readyState === "open";
    this.set({ phase: "ending" });
    if (canClose) {
      const closed = new Promise<void>((resolve) => {
        this.closed = resolve;
      });
      this.send({ type: "session.close" });
      let timer: ReturnType<typeof setTimeout> | undefined;
      await Promise.race([closed, new Promise<void>((r) => (timer = setTimeout(r, CLOSE_TIMEOUT_MS)))]);
      clearTimeout(timer);
    }
    await this.finish();
  }

  private fail(message: string) {
    this.set({ error: message });
    void this.finish();
  }

  private async finish() {
    this.teardown();
    this.set({ phase: "ended" });
  }

  private teardown() {
    for (const t of this.timers) clearTimeout(t);
    this.timers.clear();
    if (this.speakingTimer) clearTimeout(this.speakingTimer);
    for (const a of this.aborts) a.abort();
    try {
      if (this.channel) {
        this.channel.onclose = null;
        this.channel.onmessage = null;
      }
      this.channel?.close();
    } catch {
      /* already closed */
    }
    this.channel = null;
    this.pc?.close();
    this.pc = null;
    for (const t of this.mic?.getTracks() ?? []) t.stop();
    this.mic = null;
  }
}

function tail(s: string, max = 280): string {
  return s.length > max ? `…${s.slice(-max).trimStart()}` : s;
}

function iceGathered(pc: RTCPeerConnection, timeoutMs: number): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      clearTimeout(t);
      pc.removeEventListener("icegatheringstatechange", check);
      resolve();
    };
    const check = () => pc.iceGatheringState === "complete" && done();
    const t = setTimeout(done, timeoutMs); // send what was gathered so far
    pc.addEventListener("icegatheringstatechange", check);
  });
}

async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new ApiError(res.status, messageFromBody(await res.text(), `Request failed (${res.status}).`));
  return (await res.json()) as T;
}

export interface VoiceStatus {
  available: boolean;
  calls_left_today?: number;
  max_call_s?: number;
}

/** GET /api/voice/status; any failure means voice is unavailable (the Call button stays hidden). */
export async function voiceStatus(): Promise<VoiceStatus> {
  try {
    const res = await fetch("/api/voice/status", { credentials: "same-origin" });
    if (!res.ok) return { available: false };
    const j = (await res.json()) as VoiceStatus;
    return { ...j, available: j?.available === true };
  } catch {
    return { available: false };
  }
}

/** The browser's real dependencies: mic, peer connection, our two voice routes, and an audio element. */
export function browserDeps(conversationId: string, audio: HTMLAudioElement): CallDeps {
  return {
    getUserMedia: () => navigator.mediaDevices.getUserMedia({ audio: true }),
    createPeer: () => new RTCPeerConnection(),
    createSession: (sdp) => postJson("/api/voice/session", { sdp, conversation_id: conversationId }),
    analyst: (question, signal) =>
      postJson<AnalystResult>("/api/voice/analyst", { conversation_id: conversationId, question }, signal),
    onAudio: (stream) => {
      audio.srcObject = stream;
      void audio.play().catch(() => undefined);
    },
  };
}
