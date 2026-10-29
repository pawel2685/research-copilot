import pytest

from contracts import RunConfig
from evals.experiment_configs import EXPERIMENT_RUN_CONFIGS, get_run_config
from evals.metrics import EXPERIMENT_CONFIGS

SWITCHES = ("hybrid", "compress_budget_words", "use_planner", "use_critic")

TABLE = {
    "E0": (False, None, False, False),
    "E1": (True, None, False, False),
    "E2": (True, 3000, False, False),
    "E3": (True, 3000, True, False),
    "E4": (True, 3000, True, True),
}


def test_every_experiment_of_the_evaluation_has_a_configuration():
    assert tuple(EXPERIMENT_RUN_CONFIGS) == EXPERIMENT_CONFIGS


@pytest.mark.parametrize("name", TABLE)
def test_each_name_maps_to_its_row_of_the_table(name):
    cfg = get_run_config(name)
    assert isinstance(cfg, RunConfig)
    assert tuple(getattr(cfg, switch) for switch in SWITCHES) == TABLE[name]


def test_the_configurations_are_cumulative():
    """Each experiment changes exactly one switch compared with the one before."""
    names = list(TABLE)
    for before, after in zip(names, names[1:]):
        changed = [
            switch
            for switch in SWITCHES
            if getattr(get_run_config(before), switch) != getattr(get_run_config(after), switch)
        ]
        assert len(changed) == 1, (before, after, changed)


def test_get_run_config_returns_a_copy():
    cfg = get_run_config("E4")
    cfg.use_critic = False
    cfg.compress_budget_words = 1
    assert EXPERIMENT_RUN_CONFIGS["E4"].use_critic is True
    assert get_run_config("E4").compress_budget_words == 3000


def test_the_time_budget_is_the_same_everywhere():
    assert len({get_run_config(name).time_budget_s for name in TABLE}) == 1


@pytest.mark.parametrize("name", ["E5", "e1", "", "baseline"])
def test_unknown_name_raises_value_error(name):
    with pytest.raises(ValueError, match="Unknown experiment"):
        get_run_config(name)
