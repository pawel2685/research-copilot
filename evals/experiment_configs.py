
"""Pipeline configurations for experiments E0 to E4.

E1-E4 are executed through agents.pipeline.answer_with_stats.
They add the following capabilities cumulatively:
- E1: hybrid retrieval
- E2: hybrid retrieval and context compression
- E3: E2 plus the Planner
- E4: E3 plus the Critic

E0 is a special single-call baseline. Its actual execution is implemented
in evals.single_call_baseline.answer_baseline_with_stats and dispatched
separately by evals.run_benchmark._run_one.

The E0 RunConfig entry is retained for compatibility with the experiment
registry, but it does not define the actual E0 execution path.
"""

from contracts import RunConfig


EXPERIMENT_RUN_CONFIGS: dict[str, RunConfig] = {
    # Registry placeholder only. The benchmark runs E0 through the
    # separate single-call baseline in evals/single_call_baseline.py.
    "E0": RunConfig(
        hybrid=False,
        compress_budget_words=None,
        use_planner=False,
        use_critic=False,
    ),
    "E1": RunConfig(
        hybrid=True,
        compress_budget_words=None,
        use_planner=False,
        use_critic=False,
    ),
    "E2": RunConfig(
        hybrid=True,
        compress_budget_words=3000,
        use_planner=False,
        use_critic=False,
    ),
    "E3": RunConfig(
        hybrid=True,
        compress_budget_words=3000,
        use_planner=True,
        use_critic=False,
    ),
    "E4": RunConfig(
        hybrid=True,
        compress_budget_words=3000,
        use_planner=True,
        use_critic=True,
    ),
}


def get_run_config(name: str) -> RunConfig:
    """Return a copy of the configuration of experiment `name`."""

    try:
        return EXPERIMENT_RUN_CONFIGS[name].model_copy()
    except KeyError:
        known = ", ".join(EXPERIMENT_RUN_CONFIGS)
        raise ValueError(
            f"Unknown experiment {name!r}. Known: {known}."
        ) from None
