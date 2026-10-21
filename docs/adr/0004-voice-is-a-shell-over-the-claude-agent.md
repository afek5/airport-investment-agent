# Voice calls use gpt-live-1 as a voice shell that delegates analysis to the same Claude agent

The optional "call" button uses OpenAI `gpt-live-1` in client-delegation mode. Every analytic question goes to the same Claude agent and the same deterministic tools as the text chat, so voice and text can never disagree on a number. gpt-live-1 keeps the conversation going ("pulling the numbers…") during a 10–30 s analysis and speaks a short summary. The full evidence appears in the UI. The OpenAI key stays on the server: the browser's WebRTC offer goes through our backend.

## Considered Options

- gpt-realtime-2.1 calling our tools directly: lower latency for simple lookups, but two "brains" that can disagree, duplicated tool schemas, and blocking tool calls.
