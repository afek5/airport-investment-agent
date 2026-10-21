"""The answer is the turn's final message, written after the last tool call (SPEC §6), enforced in code.

Why the order matters: on Claude Sonnet 5.5, text the model writes before a tool call in the same message
can come back as a progress-update `thinking` block, which is empty under the default thinking display. An
answer written before the suggest_followups call is therefore sometimes never delivered: the user sees
nothing, and the model, believing it already answered, writes a remark like "the answer is above". Text in
the final message, with no tool call after it, always arrives as text.

So suggest_followups is called first and the answer comes last (prompt rule 5), and `validate` catches a
turn that called suggest_followups but delivered no answer text: it sends the model back to write the
full answer as its final message, saying why the earlier text did not arrive.
"""

from __future__ import annotations

from typing import Any

from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, ToolCallPart, UserPromptPart

FOLLOWUPS_TOOL = "suggest_followups"
ANSWER_MARKER = "data confidence"  # every analytic answer carries this section (SPEC §6)
ANSWER_NOT_DELIVERED_RETRY = (
    "The user has not received an answer: text written before a tool call in the same message is not shown "
    "to the user. Write the full answer (Answer, Why, Assumptions & scope, Data Confidence) now as your final "
    "message, call no tool after it, and do not mention this notice or any earlier text.")


def answer_text(messages: list[ModelMessage]) -> str:
    """What the chat shows as the answer: every text part the model wrote in these messages, in order."""
    texts = [p.content.strip() for m in messages if isinstance(m, ModelResponse) for p in m.parts
             if isinstance(p, TextPart)]
    return "\n\n".join(t for t in texts if t)


def this_turn(messages: list[ModelMessage]) -> list[ModelMessage]:
    """The messages since the latest user prompt."""
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts):
            return messages[i:]
    return messages


def validate(ctx: RunContext[Any], output: str) -> str:
    """Output validator: a turn that called suggest_followups (an analytic answer) must deliver the answer,
    with its Data Confidence section, as text. Clarifying questions and the scoping statement call no
    suggest_followups and pass unchanged."""
    if ctx.partial_output:
        return output
    turn = this_turn(ctx.messages)
    analytic = any(isinstance(p, ToolCallPart) and p.tool_name == FOLLOWUPS_TOOL
                   for m in turn if isinstance(m, ModelResponse) for p in m.parts)
    if analytic and ANSWER_MARKER not in f"{answer_text(turn)}\n{output}".lower():
        raise ModelRetry(ANSWER_NOT_DELIVERED_RETRY)
    return output
