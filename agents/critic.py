"""Critic agent for checking research report claims against evidence."""

import os
from typing import Literal

from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from pydantic import BaseModel, Field


class ClaimAssessment(BaseModel):
    """Assessment of one factual claim in a research report."""

    claim: str = Field(
        description="The factual claim being evaluated."
    )
    status: Literal[
        "supported",
        "unsupported",
        "contradicted",
    ] = Field(
        description=(
            "Whether the supplied evidence supports, fails to support, "
            "or contradicts the claim."
        )
    )
    source_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Identifiers of supplied sources relevant to the assessment. "
            "Never invent source identifiers."
        ),
    )
    rationale: str = Field(
        description="Brief explanation based on the supplied evidence."
    )


class CriticResult(BaseModel):
    """Structured result returned by the Critic agent."""

    approved: bool | None = Field(
        description=(
            "True if the report passes verification, false if revision "
            "is required, or null if the Critic was skipped."
        )
    )
    assessments: list[ClaimAssessment] = Field(
        default_factory=list,
        description="Assessments of the report's factual claims.",
    )
    revision_instructions: list[str] = Field(
        default_factory=list,
        description=(
            "Specific corrections for the Writer. Empty when no "
            "revision is needed."
        ),
    )
    unverified: bool = Field(
        default=False,
        description="True when the report was not checked by the Critic.",
    )
    message: str = Field(
        default="",
        description="An optional summary or explanation of the result.",
    )


CRITIC_INSTRUCTION = """
You are the Critic agent in a research assistant system.

You receive a draft research report and evidence from retrieved sources.

Your responsibilities:
1. Identify substantive factual claims in the report.
2. Assess each claim using only the supplied source excerpts.
3. Mark each claim as supported, unsupported, or contradicted.
4. Include source identifiers exactly as supplied. Never invent sources.
5. Treat a claim as supported only when the supplied evidence directly
   supports it. A source mentioning the same topic is not sufficient.
6. Do not present unsupported claims as established facts.
7. Set approved to true only if all material factual claims are supported.
   Set it to false if any material claim is unsupported or contradicted.
8. When approval is false, provide concise, actionable revision
   instructions for the Writer.
9. Do not rewrite the report yourself. The orchestration layer may request
   one revision from the Writer; never request repeated revision cycles.
10. Normally set unverified to false. If the input explicitly states that
    the Critic was skipped, return approved=null, unverified=true, and
    explain this in message. Do not claim to have checked the report
    when the Critic was skipped.

Be conservative. If the available evidence is insufficient, mark the
claim unsupported rather than guessing.
"""


def create_critic_agent(model: str | None = None) -> LlmAgent:
    """Create the Critic agent without making an API request."""
    if model is None:
        load_dotenv()
        model = os.getenv("MODEL_LIGHT")

    if not model:
        raise RuntimeError(
            "MODEL_LIGHT is missing. Configure it in the local .env file."
        )

    return LlmAgent(
        name="critic",
        model=model,
        description=(
            "Checks research report claims against retrieved evidence "
            "and recommends corrections when necessary."
        ),
        instruction=CRITIC_INSTRUCTION,
        output_schema=CriticResult,
        output_key="critic_result",
    )


def critic_skipped_result(
    reason: str = "Critic skipped because the time budget was insufficient."
) -> CriticResult:
    """Represent a report that was passed through without Critic verification."""
    return CriticResult(
        approved=None,
        assessments=[],
        revision_instructions=[],
        unverified=True,
        message=reason,
    )