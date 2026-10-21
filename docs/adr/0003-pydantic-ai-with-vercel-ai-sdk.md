# Agent harness: Pydantic AI + Vercel AI SDK UI protocol (not a hand-written loop, not Claude Agent SDK)

We want a proven open-source harness from end to end, with no custom agent loop or streaming glue. Pydantic AI runs the Claude (claude-sonnet-5-5) tool loop over plain Python functions. Its built-in VercelAIAdapter streams text and tool steps using the Vercel AI SDK data-stream protocol, and the Next.js UI uses `useChat` with AI Elements components. The Claude Agent SDK was rejected for this web app: it runs a Claude Code subprocess per session, requires custom tools to be in-process MCP servers, and its main value is built-in tools we would disable.

## Consequences

- npm `ai` is on v7, so the adapter must be called with `sdk_version=7`.
- Conversation history lives in the browser (useChat) and is sent with each request. The server is stateless.
