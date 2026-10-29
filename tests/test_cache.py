import asyncio
from types import SimpleNamespace

import pytest
from google.adk.agents import LlmAgent
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from agents import cache
from agents.runner import run_pipeline
from contracts import RunConfig
from tests.fake_llm import FakeLlm


@pytest.fixture(autouse=True)
def cache_on(monkeypatch, tmp_path):
    """These tests use the cache, in a temporary directory."""
    monkeypatch.setenv("LLM_CACHE", "on")
    monkeypatch.setenv("LLM_CACHE_DIR", str(tmp_path / "llm"))
    cache._pending.clear()


def _request(text="hello", model="m", system="be brief"):
    return LlmRequest(
        model=model,
        contents=[types.Content(role="user", parts=[types.Part(text=text)])],
        config=types.GenerateContentConfig(system_instruction=system),
    )


def _response(text="hi"):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))


def _ctx(invocation="i1", agent="a"):
    return SimpleNamespace(invocation_id=invocation, agent_name=agent)


def _miss_then_store(request, response, ctx=None):
    ctx = ctx or _ctx()
    assert cache.before_model(ctx, request) is None
    assert cache.after_model(ctx, response) is None


def test_miss_then_hit_returns_the_stored_response():
    request = _request()
    _miss_then_store(request, _response("stored answer"))
    hit = cache.before_model(_ctx(), request)
    assert hit is not None
    assert hit.content.parts[0].text == "stored answer"


def test_one_json_file_per_key():
    _miss_then_store(_request("a"), _response())
    _miss_then_store(_request("b"), _response())
    assert len(list(cache.cache_dir().glob("*.json"))) == 2


def test_different_prompts_models_and_instructions_give_different_keys():
    base = cache.cache_key(_request())
    assert cache.cache_key(_request()) == base
    assert cache.cache_key(_request(text="other")) != base
    assert cache.cache_key(_request(model="other")) != base
    assert cache.cache_key(_request(system="other")) != base


def test_tools_and_output_schema_are_part_of_the_key():
    plain = _request()
    with_tool = _request()
    with_tool.config.tools = [
        types.Tool(function_declarations=[types.FunctionDeclaration(name="search_papers")])
    ]
    with_schema = _request()
    with_schema.config.response_mime_type = "application/json"
    assert len({cache.cache_key(r) for r in (plain, with_tool, with_schema)}) == 3


def test_a_different_prompt_is_a_miss():
    _miss_then_store(_request("a"), _response())
    assert cache.before_model(_ctx(), _request("b")) is None


def test_switch_off_disables_reading(monkeypatch):
    request = _request()
    _miss_then_store(request, _response())
    monkeypatch.setenv("LLM_CACHE", "off")
    assert cache.before_model(_ctx(), request) is None


def test_switch_off_disables_storing(monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "OFF")
    _miss_then_store(_request(), _response())
    assert not cache.cache_dir().exists()
    monkeypatch.setenv("LLM_CACHE", "on")
    assert cache.before_model(_ctx(), _request()) is None


def test_the_cache_is_on_by_default(monkeypatch):
    monkeypatch.delenv("LLM_CACHE")
    assert cache.cache_enabled() is True


def test_default_directory(monkeypatch):
    monkeypatch.delenv("LLM_CACHE_DIR")
    assert str(cache.cache_dir()).replace("\\", "/") == ".cache/llm"


def test_corrupted_file_is_a_miss():
    request = _request()
    _miss_then_store(request, _response())
    (path,) = cache.cache_dir().glob("*.json")
    path.write_text("{not json", encoding="utf-8")
    assert cache.before_model(_ctx(), request) is None


def test_file_with_the_wrong_shape_is_a_miss():
    request = _request()
    _miss_then_store(request, _response())
    (path,) = cache.cache_dir().glob("*.json")
    path.write_text('{"content": 5}', encoding="utf-8")
    assert cache.before_model(_ctx(), request) is None


def test_unstorable_responses_are_not_stored():
    for response in (
        LlmResponse(),  # no content
        LlmResponse(content=_response().content, partial=True),
        LlmResponse(content=_response().content, error_code="SAFETY"),
    ):
        _miss_then_store(_request(), response)
    assert not cache.cache_dir().exists()


def test_binary_parts_survive_the_round_trip():
    call = types.Part(
        function_call=types.FunctionCall(name="search_papers", args={"query": "q"}),
        thought_signature=b"\xff\x00\xfe",
    )
    request = _request()
    _miss_then_store(request, LlmResponse(content=types.Content(role="model", parts=[call])))
    hit = cache.before_model(_ctx(), request)
    assert hit.content.parts[0].thought_signature == b"\xff\x00\xfe"
    assert hit.content.parts[0].function_call.args == {"query": "q"}


def test_a_hit_registers_nothing_and_is_not_stored_again():
    request = _request()
    _miss_then_store(request, _response())
    assert cache.before_model(_ctx(), request) is not None
    assert cache._pending == {}
    assert cache.after_model(_ctx(), _response("changed")) is None
    assert cache.before_model(_ctx(), request).content.parts[0].text == "hi"


def test_parallel_agents_do_not_mix_up_their_requests():
    first, second = _ctx(agent="a"), _ctx(agent="b")
    assert cache.before_model(first, _request("one")) is None
    assert cache.before_model(second, _request("two")) is None
    cache.after_model(second, _response("answer two"))
    cache.after_model(first, _response("answer one"))
    assert cache.before_model(_ctx(), _request("one")).content.parts[0].text == "answer one"
    assert cache.before_model(_ctx(), _request("two")).content.parts[0].text == "answer two"


def test_an_unwritable_cache_directory_does_not_break_a_run(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("LLM_CACHE_DIR", str(blocker / "sub"))
    _miss_then_store(_request(), _response())  # must not raise
    assert cache.before_model(_ctx(), _request()) is None


def test_with_cache_puts_the_callbacks_first_and_keeps_the_others():
    def mine(ctx, request):
        return None

    agent = LlmAgent(name="a", model="m", instruction="x", before_model_callback=mine)
    cached = cache.with_cache(agent)
    assert cached.before_model_callback == [cache.before_model, mine]
    assert cached.after_model_callback == [cache.after_model]
    assert agent.before_model_callback is mine  # the original is untouched


def test_a_repeated_run_does_not_call_the_model_again():
    question = "low-rank matrices"
    cfg = RunConfig(use_planner=False, use_critic=False)

    first = FakeLlm()
    result_one = asyncio.run(run_pipeline(question, cfg, models=(first, first)))
    calls_first = sum(len(v) for v in first.instructions.values())

    second = FakeLlm()
    result_two = asyncio.run(run_pipeline(question, cfg, models=(second, second)))

    assert calls_first == 4  # searcher x2, reader, writer
    assert second.instructions == {}
    assert result_two.report_markdown == result_one.report_markdown
    assert result_two.state["reading_notes_1"] == result_one.state["reading_notes_1"]


def test_switch_off_makes_every_run_call_the_model(monkeypatch):
    monkeypatch.setenv("LLM_CACHE", "off")
    cfg = RunConfig(use_planner=False, use_critic=False)
    for _ in range(2):
        fake = FakeLlm()
        asyncio.run(run_pipeline("low-rank matrices", cfg, models=(fake, fake)))
        assert sum(len(v) for v in fake.instructions.values()) == 4
