"""Retries for temporary Gemini errors.

`LlmAgent` has no `retry_config` in google-adk 2.13 (the `RetryConfig` there is for
workflow nodes). The `Gemini` model class takes `retry_options`, and the genai SDK
retries inside it. Only the listed HTTP status codes are retried:

- `429`: rate limit. The free tier has low limits, so waiting usually helps.
- `503`: temporary overload ("high demand").

Everything else is raised at once, above all `404` (the model is not available for
this account and will not come back), `400` and `403`. When all attempts fail, the
last error is raised.
"""
from __future__ import annotations

from google.adk.models.base_llm import BaseLlm
from google.adk.models.google_llm import Gemini
from google.genai import types

RETRYABLE_STATUS_CODES = (429, 503)

# 4 attempts wait about 2 + 4 + 8 seconds (plus jitter) before giving up, which fits
# the time budget of a run. Example values, tune them after the first real runs.
RETRY_OPTIONS = types.HttpRetryOptions(
    attempts=4,
    initial_delay=2.0,
    max_delay=30.0,
    exp_base=2.0,
    jitter=1.0,
    http_status_codes=list(RETRYABLE_STATUS_CODES),
)


def make_model(model: str | BaseLlm) -> BaseLlm | str:
    """Return a Gemini model with retries for a model name.

    A model object is returned as it is, and so is an empty name (the agent then
    takes the model of its parent).
    """
    if isinstance(model, str) and model:
        return Gemini(model=model, retry_options=RETRY_OPTIONS)
    return model
