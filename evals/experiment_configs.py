"""The run configuration of each experiment E0 to E4.

The settings are cumulative: each experiment adds one thing to the previous one.

E0 is the baseline and runs through the same pipeline with every switch off: vector
search only, no compression, no Planner, no Critic. It is not a separate single-call
baseline. This was not agreed with the evaluation owner yet.
"""
from contracts import RunConfig

EXPERIMENT_RUN_CONFIGS: dict[str, RunConfig] = {
    "E0": RunConfig(
        hybrid=False, compress_budget_words=None, use_planner=False, use_critic=False
    ),
    "E1": RunConfig(
        hybrid=True, compress_budget_words=None, use_planner=False, use_critic=False
    ),
    "E2": RunConfig(
        hybrid=True, compress_budget_words=3000, use_planner=False, use_critic=False
    ),
    "E3": RunConfig(
        hybrid=True, compress_budget_words=3000, use_planner=True, use_critic=False
    ),
    "E4": RunConfig(
        hybrid=True, compress_budget_words=3000, use_planner=True, use_critic=True
    ),
}


def get_run_config(name: str) -> RunConfig:
    """Return a copy of the configuration of experiment `name`."""
    try:
        return EXPERIMENT_RUN_CONFIGS[name].model_copy()
    except KeyError:
        known = ", ".join(EXPERIMENT_RUN_CONFIGS)
        raise ValueError(f"Unknown experiment {name!r}. Known: {known}.") from None
