import type { UIMessage } from "ai";

export function assistant(parts: unknown[], id = "a1"): UIMessage {
  return { id, role: "assistant", parts } as UIMessage;
}
export function user(text: string, id = "u1"): UIMessage {
  return { id, role: "user", parts: [{ type: "text", text }] } as UIMessage;
}
export const toolPart = (name: string, id: string, state: string, output?: unknown, input: unknown = {}) => ({
  type: `tool-${name}`,
  toolCallId: id,
  state,
  input,
  output,
});
