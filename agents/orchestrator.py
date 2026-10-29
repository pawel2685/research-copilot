"""The ADK flow: Planner, parallel search branches, Writer, Critic.

    Planner (optional) -> [ branch_1 | branch_2 | branch_3 | branch_4 ] -> Writer
        -> Critic (optional)

Each branch is a Searcher followed by a Reader. `ParallelAgent` needs a fixed list of
sub-agents and the Planner returns up to four sub-questions, so there are always four
branches and a branch skips itself when it has no sub-question. The single Critic
revision is not part of this flow: `agents/runner.py` does it in plain Python.
"""
from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

from agents.config import load_models
from agents.critic import critic_skipped_result
from agents.reader import create_reader_agent
from agents.searcher import create_searcher_agent
from agents.skipping import (
    CRITIC_MIN_LEFT_S,
    MAX_SUB_QUESTIONS,
    PLANNER_MIN_LEFT_S,
    make_branch_callback,
    make_deadline_callback,
)
from agents.writer import create_writer_agent
from contracts import RunConfig

_CRITIC_SKIP_TEXT = critic_skipped_result(
    "Critic skipped because the time budget was insufficient."
).model_dump_json()


def _planner_skip_text(ctx: Any) -> str:
    """A skipped Planner "plans" the original question as the only sub-question."""
    return json.dumps([ctx.state["question"]])


def notes_keys() -> list[str]:
    """State keys of the notes of the four branches, in branch order."""
    return [f"reading_notes_{n}" for n in range(1, MAX_SUB_QUESTIONS + 1)]


def _with_deadline_callback(
    agent: LlmAgent, min_left_s: float, skip_text: str | Callable[[Any], str]
) -> LlmAgent:
    """Copy of `agent` that skips itself when less than `min_left_s` is left.

    `skip_text` is what the skipped agent "says". It is saved as the output of the
    agent, so it must be valid for its `output_schema`.
    """
    existing = agent.before_agent_callback
    if existing is None:
        existing = []
    elif not isinstance(existing, list):
        existing = [existing]
    callbacks = [make_deadline_callback(min_left_s, skip_text), *existing]
    return agent.model_copy(update={"before_agent_callback": callbacks})


def _build_branch(
    index: int, search_tool: Callable[[str], list[dict]], light_model: str
) -> SequentialAgent:
    n = index + 1
    searcher = create_searcher_agent(
        search_tool,
        light_model,
        name=f"searcher_{n}",
        output_key=f"search_results_{n}",
        question_key=f"sub_question_{n}",
    )
    reader = create_reader_agent(
        light_model,
        name=f"reader_{n}",
        input_key=f"search_results_{n}",
        output_key=f"reading_notes_{n}",
    )
    return SequentialAgent(
        name=f"branch_{n}",
        sub_agents=[searcher, reader],
        before_agent_callback=make_branch_callback(index),
    )


def build_pipeline(
    cfg: RunConfig,
    *,
    search_tool: Callable[[str], list[dict]],
    planner: LlmAgent | None = None,
    critic: LlmAgent | None = None,
    models: tuple[str, str] | None = None,
) -> SequentialAgent:
    """Build the whole flow without making an API request.

    `models` is `(light, heavy)`, read from `.env` when it is `None`. The Planner and
    the Critic are only part of the flow when `cfg` switches them on and an agent is
    given. They get a callback that skips them when time runs short.
    """
    light, heavy = models or load_models()
    branches = ParallelAgent(
        name="search_branches",
        sub_agents=[
            _build_branch(index, search_tool, light)
            for index in range(MAX_SUB_QUESTIONS)
        ],
    )
    writer = create_writer_agent(heavy, notes_keys=notes_keys(), optional_notes=True)

    steps = []
    if cfg.use_planner and planner is not None:
        steps.append(_with_deadline_callback(planner, PLANNER_MIN_LEFT_S, _planner_skip_text))
    steps += [branches, writer]
    if cfg.use_critic and critic is not None:
        steps.append(_with_deadline_callback(critic, CRITIC_MIN_LEFT_S, _CRITIC_SKIP_TEXT))
    return SequentialAgent(name="research_pipeline", sub_agents=steps)
