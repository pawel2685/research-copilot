"""Tests for the Critic agent and its output models."""

import pytest
from pydantic import ValidationError

from agents.critic import (
    ClaimAssessment,
    CriticResult,
    create_critic_agent,
    critic_skipped_result,
)


def test_supported_claim_can_be_assessed():
    assessment = ClaimAssessment(
        claim="The method improved accuracy.",
        status="supported",
        source_ids=["paper-1"],
        rationale="The supplied excerpt reports an accuracy improvement.",
    )

    assert assessment.status == "supported"
    assert assessment.source_ids == ["paper-1"]


def test_unsupported_claim_can_be_assessed():
    assessment = ClaimAssessment(
        claim="The method works in every clinical setting.",
        status="unsupported",
        source_ids=["paper-1"],
        rationale="The supplied evidence does not establish this claim.",
    )

    assert assessment.status == "unsupported"


def test_contradicted_claim_can_be_assessed():
    assessment = ClaimAssessment(
        claim="The method reduced error rates.",
        status="contradicted",
        source_ids=["paper-2"],
        rationale="The supplied excerpt reports higher error rates.",
    )

    assert assessment.status == "contradicted"


def test_invalid_assessment_status_is_rejected():
    with pytest.raises(ValidationError):
        ClaimAssessment(
            claim="Example claim",
            status="unknown",
            source_ids=[],
            rationale="No valid status was provided.",
        )


def test_result_can_request_a_revision():
    result = CriticResult(
        approved=False,
        assessments=[
            ClaimAssessment(
                claim="The method works in every setting.",
                status="unsupported",
                source_ids=[],
                rationale="The supplied evidence is insufficient.",
            )
        ],
        revision_instructions=[
            "Remove the universal claim or support it with appropriate evidence."
        ],
    )

    assert result.approved is False
    assert len(result.revision_instructions) == 1


def test_skipped_critic_returns_unverified_result():
    result = critic_skipped_result()

    assert result.approved is None
    assert result.unverified is True
    assert result.assessments == []
    assert result.revision_instructions == []
    assert "time budget" in result.message


def test_skipped_critic_accepts_custom_reason():
    result = critic_skipped_result("Not enough time remained.")

    assert result.message == "Not enough time remained."
    assert result.unverified is True


def test_agent_uses_configured_model_and_output_schema(monkeypatch):
    monkeypatch.setenv("MODEL_LIGHT", "test-model")

    agent = create_critic_agent()

    assert agent.name == "critic"
    assert agent.model == "test-model"
    assert agent.output_schema is CriticResult
    assert agent.output_key == "critic_result"


def test_agent_can_be_created_with_explicit_model():
    agent = create_critic_agent(model="test-model")

    assert agent.model == "test-model"

def test_agent_requires_model_when_not_configured(monkeypatch):
    monkeypatch.setattr("agents.critic.load_dotenv", lambda: None)
    monkeypatch.delenv("MODEL_LIGHT", raising=False)

    with pytest.raises(RuntimeError, match="MODEL_LIGHT is missing"):
        create_critic_agent()
