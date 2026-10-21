"""The answer is the turn's final message, written after the last tool call (SPEC §6), enforced in code.

Why the order matters: on Claude Sonnet 5.5, text the model writes before a tool call in the same message
can come back as a progress-update `thinking` block, which is empty under the default thinking display; and
when it does come back as text, the model tends to write the answer a second time after the tool call. So
the chat shows only the final message: the text after the turn's last tool call (`answer_text` here, and
`answerTextsOf` in frontend/lib/parts.ts). Text before a tool call is never shown, so a turn cannot display
its answer twice.

`validate` (the output validator) holds every analytic turn to that contract:
- it called `suggest_followups` (SPEC §5: called last in every analytic answer), and
- its final message carries the full answer, with its Data Confidence section.
A turn that misses either is sent back with a notice saying what to do. A turn is analytic when it called a
data tool or `suggest_followups`; clarifying questions (no tool, or only `resolve_airports`) and the scoping
statement pass unchanged. When the retries run out, the output is kept rather than failing the answer.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart

FOLLOWUPS_TOOL = "suggest_followups"
NON_DATA_TOOLS = {FOLLOWUPS_TOOL, "resolve_airports"}
ANSWER_MARKER = "data confidence"  # every analytic answer carries this section (SPEC §6)
ANSWER_NOT_DELIVERED_RETRY = (
    "The user has not received an answer: only your final message, after your last tool call, is shown to "
    "the user. Write the full answer (Answer, Why, Assumptions & scope, Data Confidence) now as your final "
    "message, call no tool after it, and do not mention this notice or any earlier text.")
FOLLOWUPS_MISSING_RETRY = (
    "You did not call suggest_followups. Call it now with 2-3 short follow-up questions, then write the full "
    "answer (Answer, Why, Assumptions & scope, Data Confidence) as your final message, call no tool after it, "
    "and do not mention this notice. Only that final message is shown to the user.")


def answer_text(messages: list[ModelMessage]) -> str:
    """What the chat shows as the answer: the text the model wrote after its last tool call in these
    messages. Text written before a tool call is dropped, as the UI drops it."""
    texts: list[str] = []
    for m in messages:
        if not isinstance(m, ModelResponse):
            continue
        for p in m.parts:
            if isinstance(p, ToolCallPart):
                texts = []
            elif isinstance(p, TextPart) and p.content.strip():
                texts.append(p.content.strip())
    return "\n\n".join(texts)


def this_turn(messages: list[ModelMessage]) -> list[ModelMessage]:
    """The messages since the latest user prompt."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts):
            return messages[i:]
    return messages


def validate(ctx: RunContext[Any], output: str) -> str:
    """Output validator: an analytic turn calls suggest_followups and delivers the full answer, with its Data
    Confidence section, as its final message."""
    if ctx.partial_output:
        return output
    called = {p.tool_name for m in this_turn(ctx.messages) if isinstance(m, ModelResponse) for p in m.parts
              if isinstance(p, ToolCallPart)}
    if not (called - NON_DATA_TOOLS or FOLLOWUPS_TOOL in called):
        return output
    if ctx.retry >= ctx.max_retries:  # out of retries: keep the answer rather than fail the turn
        return output
    if FOLLOWUPS_TOOL not in called:
        raise ModelRetry(FOLLOWUPS_MISSING_RETRY)
    if ANSWER_MARKER not in output.lower():
        raise ModelRetry(ANSWER_NOT_DELIVERED_RETRY)
    return output
