import pytest

from agents import config


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda: False)


def test_load_models_returns_both_values(monkeypatch):
    monkeypatch.setenv("MODEL_LIGHT", "light-model")
    monkeypatch.setenv("MODEL_HEAVY", "heavy-model")
    assert config.load_models() == ("light-model", "heavy-model")


@pytest.mark.parametrize("missing", ["MODEL_LIGHT", "MODEL_HEAVY"])
def test_load_models_names_the_missing_variable(monkeypatch, missing):
    monkeypatch.setenv("MODEL_LIGHT", "light-model")
    monkeypatch.setenv("MODEL_HEAVY", "heavy-model")
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        config.load_models()


def test_load_models_treats_an_empty_value_as_missing(monkeypatch):
    monkeypatch.setenv("MODEL_LIGHT", "")
    monkeypatch.setenv("MODEL_HEAVY", "heavy-model")
    with pytest.raises(RuntimeError, match="MODEL_LIGHT"):
        config.load_models()
