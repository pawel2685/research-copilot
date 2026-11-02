import pytest


@pytest.fixture(autouse=True)
def no_response_cache(monkeypatch):
    """No test reads or writes the response cache, so runs never depend on old files."""
    monkeypatch.setenv("LLM_CACHE", "off")
