"""The pipeline as an agent for `adk web`.

Run from the repository root:

    adk web demo

and pick `research_copilot` in the browser. The demo shows the ADK flow (Planner,
parallel search branches, Writer, Critic). It does not do the one revision after a
rejecting Critic: that step lives in `agents/runner.py`, outside the ADK flow.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# `adk web demo` puts `demo/` on the path, but the project modules are in the root.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from google.adk.agents import SequentialAgent  # noqa: E402

from agents.critic import create_critic_agent  # noqa: E402
from agents.orchestrator import build_pipeline, notes_keys  # noqa: E402
from agents.pipeline import default_search  # noqa: E402
from agents.tools import make_search_tool  # noqa: E402
from contracts import RunConfig  # noqa: E402


def make_start_callback(cfg: RunConfig):
    """Build the `before_agent_callback` that prepares the state for one question.

    `run_pipeline` sets this state itself. In `adk web` nothing does, and the skip
    callbacks need `deadline_at`. It runs at every message, so a second question in the
    same chat starts with a fresh deadline and without the notes of the first one.
    """

    def start_run(ctx) -> None:
        parts = ctx.user_content.parts if ctx.user_content else []
        question = "".join(part.text or "" for part in parts).strip()
        ctx.state["question"] = question
        ctx.state["sub_questions"] = [question]
        ctx.state["deadline_at"] = time.time() + cfg.time_budget_s
        for key in notes_keys():
            ctx.state[key] = ""
        return None

    return start_run


def build_demo_pipeline(cfg: RunConfig | None = None) -> SequentialAgent:
    """The pipeline for the demo, with the models taken from `.env`."""
    cfg = cfg or RunConfig()
    search_tool = make_search_tool(
        default_search, hybrid=cfg.hybrid, budget_words=cfg.compress_budget_words
    )
    # TODO(B): pass B's Planner agent as `planner` once it is merged.
    pipeline = build_pipeline(
        cfg,
        search_tool=search_tool,
        planner=None,
        critic=create_critic_agent() if cfg.use_critic else None,
    )
    pipeline.before_agent_callback = make_start_callback(cfg)
    return pipeline


root_agent = build_demo_pipeline()
