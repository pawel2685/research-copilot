"""Tests of the retry options.

The retrying itself is done by the genai SDK. `retry_args` is the function it uses to
turn `HttpRetryOptions` into a tenacity retry policy, so these tests run the policy
that our options produce, with the sleep replaced by a no-op.
"""
import pytest
import tenacity
from google.adk.models.google_llm import Gemini
from google.genai import errors
from google.genai._api_client import retry_args

from agents.retry import RETRY_OPTIONS, RETRYABLE_STATUS_CODES, make_model
from tests.fake_llm import FakeLlm


def _error(code):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": f"error {code}"}})


class Flaky:
    """Fails with the given status codes in order, then succeeds."""

    def __init__(self, *codes):
        self.codes = list(codes)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.codes:
            raise _error(self.codes.pop(0))
        return "ok"


def _run(func):
    sleeps = []
    retrying = tenacity.Retrying(**retry_args(RETRY_OPTIONS), sleep=sleeps.append)
    return retrying(func), sleeps


@pytest.mark.parametrize("code", RETRYABLE_STATUS_CODES)
def test_a_temporary_error_is_retried_until_it_succeeds(code):
    flaky = Flaky(code, code)
    result, sleeps = _run(flaky)
    assert result == "ok"
    assert flaky.calls == 3
    assert len(sleeps) == 2


def test_mixed_temporary_errors_are_retried():
    flaky = Flaky(503, 429)
    assert _run(flaky)[0] == "ok"
    assert flaky.calls == 3


def test_the_pause_grows_between_attempts():
    _, sleeps = _run(Flaky(503, 503, 503))
    assert sleeps[0] < sleeps[1] < sleeps[2]
    assert max(sleeps) <= RETRY_OPTIONS.max_delay


@pytest.mark.parametrize("code", [404, 400, 403, 401])
def test_other_errors_are_raised_at_once_without_a_retry(code):
    flaky = Flaky(code)
    with pytest.raises(errors.APIError) as raised:
        _run(flaky)
    assert raised.value.code == code
    assert flaky.calls == 1


def test_after_the_maximum_attempts_the_last_error_is_raised():
    flaky = Flaky(*[503] * 10)
    with pytest.raises(errors.ServerError) as raised:
        _run(flaky)
    assert raised.value.code == 503
    assert flaky.calls == RETRY_OPTIONS.attempts


def test_a_final_non_temporary_error_ends_the_retries():
    flaky = Flaky(503, 404)
    with pytest.raises(errors.ClientError):
        _run(flaky)
    assert flaky.calls == 2


def test_only_429_and_503_are_listed_and_404_never():
    assert set(RETRY_OPTIONS.http_status_codes) == {429, 503}
    assert 404 not in RETRY_OPTIONS.http_status_codes
    assert RETRY_OPTIONS.attempts > 1


def test_make_model_gives_a_gemini_model_with_the_retry_options():
    model = make_model("gemini-test")
    assert isinstance(model, Gemini)
    assert model.model == "gemini-test"
    assert model.retry_options == RETRY_OPTIONS


def test_the_retry_options_reach_the_sdk_client(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-key-for-this-test")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
    client = make_model("gemini-test").api_client
    assert client._api_client._http_options.retry_options == RETRY_OPTIONS


def test_a_model_object_and_an_empty_name_are_left_alone():
    fake = FakeLlm()
    assert make_model(fake) is fake
    assert make_model("") == ""
