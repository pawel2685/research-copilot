"""A fake Gemini model, so the real ADK runner can be tested without the network."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types
from pydantic import Field


class FakeLlm(BaseLlm):
    """Answers by the role named in the system instruction of the agent.

    - Searcher: calls `search_papers` with the question, then repeats the tool result.
    - Reader: answers `NOTES <the passages it was given>`.
    - Writer: answers `REPORT <the notes it was given>`.
    - Critic: answers the JSON in `critic_json`.
    - Planner: answers the JSON in `planner_json`.

    Every system instruction is recorded in `instructions`, by role.
    """

    model: str = "fake"
    critic_json: str = '{"approved": true}'
    planner_json: str = '["only question"]'
    instructions: dict[str, list[str]] = Field(default_factory=dict)

    def _reply(self, text: str) -> LlmResponse:
        return LlmResponse(content=types.Content(role="model", parts=[types.Part(text=text)]))

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        system = str(llm_request.config.system_instruction).split("You are an agent.")[0]
        role = next(
            (r for r in ("Searcher", "Reader", "Writer", "Critic", "Planner") if f"You are the {r}" in system),
            "Unknown",
        )
        self.instructions.setdefault(role, []).append(system)
        last = llm_request.contents[-1]
        if role == "Searcher":
            responses = [part.function_response for part in last.parts if part.function_response]
            if responses:
                yield self._reply(json.dumps(responses[0].response))
            else:
                question = system.split("Question to search for:")[-1].strip() or "attention"
                call = types.FunctionCall(name="search_papers", args={"query": question})
                yield LlmResponse(
                    content=types.Content(role="model", parts=[types.Part(function_call=call)])
                )
        elif role == "Reader":
            yield self._reply("NOTES " + system.split("Passages:")[-1].strip())
        elif role == "Writer":
            yield self._reply("REPORT " + system.split("Notes:")[-1].strip())
        elif role == "Critic":
            yield self._reply(self.critic_json)
        elif role == "Planner":
            yield self._reply(self.planner_json)
        else:
            yield self._reply("?")
