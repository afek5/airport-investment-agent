// Client for the session and history routes (SPEC §7). Cookies carry the session; nothing is stored client-side.
import type { UIMessage } from "ai";

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at?: string | null;
  created_at?: string | null;
}

export interface Conversation extends ConversationSummary {
  messages: UIMessage[];
}

/** An HTTP failure with a user-facing message taken from the response when it has one. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** FastAPI errors look like {"detail": "..."}; anything else is shown as plain text. */
export function messageFromBody(body: string, fallback: string): string {
  if (!body) return fallback;
  try {
    const j = JSON.parse(body) as unknown;
    if (j && typeof j === "object") {
      const o = j as Record<string, unknown>;
      const d = o.detail ?? o.message ?? o.error;
      if (typeof d === "string" && d) return d;
      if (d && typeof d === "object" && typeof (d as Record<string, unknown>).message === "string") {
        return (d as { message: string }).message;
      }
      return fallback;
    }
  } catch {
    /* not JSON */
  }
  return body.length > 300 ? fallback : body;
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    throw new ApiError(res.status, messageFromBody(await res.text(), `Request failed (${res.status}).`));
  }
  return res;
}

/** GET /api/session → {authenticated}. Throws ApiError on HTTP failure (404 when the route is absent). */
export async function sessionStatus(): Promise<boolean> {
  const body = (await (await request("/api/session")).json()) as { authenticated?: unknown };
  return body?.authenticated === true;
}

/** POST /api/session {code}. Resolves on success; throws ApiError(401 | 429 | …) otherwise. */
export async function startSession(code: string): Promise<void> {
  await request("/api/session", { method: "POST", body: JSON.stringify({ code }) });
}

function summaryFrom(x: unknown): ConversationSummary | null {
  if (!x || typeof x !== "object") return null;
  const o = x as Record<string, unknown>;
  if (typeof o.id !== "string") return null;
  return {
    id: o.id,
    title: typeof o.title === "string" && o.title ? o.title : "Untitled chat",
    updated_at: typeof o.updated_at === "string" ? o.updated_at : null,
    created_at: typeof o.created_at === "string" ? o.created_at : null,
  };
}

/** GET /api/conversations: accepts a bare array or {conversations: [...]}. */
export async function listConversations(): Promise<ConversationSummary[]> {
  const body = (await (await request("/api/conversations")).json()) as unknown;
  const arr = Array.isArray(body) ? body : ((body as { conversations?: unknown[] })?.conversations ?? []);
  return arr.map(summaryFrom).filter((c): c is ConversationSummary => c !== null);
}

/** GET /api/conversations/{id}: accepts {id, title, messages} or a bare UI-message array. */
export async function getConversation(id: string): Promise<Conversation> {
  const body = (await (await request(`/api/conversations/${encodeURIComponent(id)}`)).json()) as unknown;
  if (Array.isArray(body)) return { id, title: "", messages: body as UIMessage[] };
  const o = (body ?? {}) as Record<string, unknown>;
  return {
    ...(summaryFrom({ id, ...o }) ?? { id, title: "" }),
    messages: Array.isArray(o.messages) ? (o.messages as UIMessage[]) : [],
  };
}

/** PUT /api/conversations/{id} with {messages, title}: messages is the useChat UI-message array (SPEC §7). */
export async function saveConversation(id: string, messages: UIMessage[], title: string): Promise<ConversationSummary | null> {
  const res = await request(`/api/conversations/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({ title, messages }),
  });
  try {
    return summaryFrom(await res.json());
  } catch {
    return null;
  }
}

export async function deleteConversation(id: string): Promise<void> {
  await request(`/api/conversations/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** A friendly line for a failed chat request (guards in SPEC §9 answer 401/413/429 with a reason). */
export function chatErrorMessage(err: Error & { statusCode?: number; responseBody?: string }): string {
  const status = err.statusCode;
  const fromBody = messageFromBody(err.responseBody ?? err.message ?? "", "");
  if (status === 413) return fromBody || "That message is too long. Keep it under 2,000 characters.";
  if (status === 429) return fromBody || "The hourly message limit is reached. Try again later.";
  if (status === 402 || status === 503) return fromBody || "The demo budget for today is reached. Try again tomorrow.";
  if (status && status >= 500) return "The analyst service failed to answer. Try again in a moment.";
  if (/failed to fetch|network/i.test(err.message ?? "")) return "Can't reach the server. Check the connection and try again.";
  return fromBody || "Something went wrong while answering. Try again.";
}
