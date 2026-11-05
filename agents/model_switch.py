"""Choose the model of the Writer from the chat of the web demo.

`adk web` has no place for our own buttons, so the switch is a command at the start of a
message: `/lite <question>` writes the report with `MODEL_LIGHT`, `/heavy <question>` with
`MODEL_HEAVY` (the default). The choice stays for the rest of the chat until it is
changed. It exists because `MODEL_HEAVY` can have a much lower free-tier quota than
`MODEL_LIGHT` (see the README, section "Models").
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from google.adk.agents import SequentialAgent
from google.adk.models.llm_request import LlmRequest

# Session state: what the user chose ("light" or "heavy"), and the model name that the
# Writer used last (it can be read in the State tab of `adk web`).
CHOICE_KEY = "writer_model_choice"
USED_KEY = "writer_model_used"

_COMMANDS = {"/lite": "light", "/light": "light", "/heavy": "heavy"}


def split_command(text: str) -> tuple[str | None, str]:
    """Split a chat message into the model choice and the question.

    Returns `("light" | "heavy", question)` when the message starts with a command, and
    `(None, question)` when it does not. The command is not case sensitive.
    """
    text = text.strip()
    first, _, rest = text.partition(" ")
    choice = _COMMANDS.get(first.lower())
    if choice is None:
        return None, text
    return choice, rest.strip()


def make_model_override(
    light: str, heavy: str
) -> Callable[[Any, LlmRequest], None]:
    """A `before_model_callback` that sets the model of the request from the chat choice.

    It must run before the response cache, because the model name is part of the cache key.
    It never returns a response, so the model call goes on.
    """

    def override(ctx: Any, llm_request: LlmRequest) -> None:
        model = light if ctx.state.get(CHOICE_KEY) == "light" else heavy
        llm_request.model = model
        ctx.state[USED_KEY] = model
        return None

    return override


def add_writer_switch(pipeline: SequentialAgent, light: str, heavy: str) -> SequentialAgent:
    """Put the model override in front of the model callbacks of the Writer. Returns `pipeline`."""
    for agent in pipeline.sub_agents:
        if agent.name == "writer":
            existing = agent.before_model_callback
            if existing is None:
                existing = []
            elif not isinstance(existing, list):
                existing = [existing]
            agent.before_model_callback = [make_model_override(light, heavy), *existing]
    return pipeline
