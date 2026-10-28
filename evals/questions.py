"""Fixed research questions for reproducible system evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvaluationQuestion:
    """A research question and its reference evidence."""

    id: str
    question: str
    reference_title: str
    expected_source_ids: tuple[str, ...]
    evaluation_criteria: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("Question ID must not be empty.")
        if not self.question.strip():
            raise ValueError("Question text must not be empty.")
        if not self.expected_source_ids:
            raise ValueError("At least one expected source is required.")
        if len(set(self.expected_source_ids)) != len(
            self.expected_source_ids
        ):
            raise ValueError("Expected source IDs must be unique.")
        if not self.evaluation_criteria:
            raise ValueError("At least one evaluation criterion is required.")


EVALUATION_QUESTIONS = (
    EvaluationQuestion(
        id="q001-rag",
        question=(
            "What problem does retrieval-augmented generation address, "
            "and how does it combine parametric and non-parametric memory?"
        ),
        reference_title=(
            "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
        ),
        expected_source_ids=("2005.11401",),
        evaluation_criteria=(
            "Explain the limitations of relying only on parametric memory.",
            "Distinguish parametric memory from external non-parametric memory.",
            "Explain how retrieved passages condition text generation.",
            "Support factual claims with source citations.",
        ),
    ),
    EvaluationQuestion(
        id="q002-transformer",
        question=(
            "How does the Transformer architecture process sequences "
            "without recurrent or convolutional layers?"
        ),
        reference_title="Attention Is All You Need",
        expected_source_ids=("1706.03762",),
        evaluation_criteria=(
            "Explain the role of attention mechanisms.",
            "Describe how the architecture avoids recurrence and convolutions.",
            "Distinguish the architectural proposal from its reported results.",
            "Support factual claims with source citations.",
        ),
    ),
    EvaluationQuestion(
        id="q003-bert",
        question=(
            "How does BERT use bidirectional context during pre-training "
            "and why is this useful for downstream language tasks?"
        ),
        reference_title=(
            "BERT: Pre-training of Deep Bidirectional Transformers "
            "for Language Understanding"
        ),
        expected_source_ids=("1810.04805",),
        evaluation_criteria=(
            "Explain the use of left and right context.",
            "Describe how pre-training supports downstream fine-tuning.",
            "Avoid claims that are not supported by the reference paper.",
            "Support factual claims with source citations.",
        ),
    ),
    EvaluationQuestion(
        id="q004-lora",
        question=(
            "How does Low-Rank Adaptation (LoRA) reduce the number of "
            "trainable parameters when fine-tuning large language models?"
        ),
        reference_title="LoRA: Low-Rank Adaptation of Large Language Models",
        expected_source_ids=("2106.09685",),
        evaluation_criteria=(
            "Explain why the pre-trained weights are frozen.",
            "Describe the role of trainable low-rank matrices.",
            "Distinguish parameter efficiency from model quality.",
            "Support factual claims with source citations.",
        ),
    ),
    EvaluationQuestion(
        id="q005-chain-of-thought",
        question=(
            "What is chain-of-thought prompting, and what kinds of tasks "
            "does the paper report improvements on?"
        ),
        reference_title=(
            "Chain-of-Thought Prompting Elicits Reasoning "
            "in Large Language Models"
        ),
        expected_source_ids=("2201.11903",),
        evaluation_criteria=(
            "Explain the use of intermediate reasoning steps in examples.",
            "Identify the task types evaluated in the paper.",
            "Describe reported findings without generalizing beyond the evidence.",
            "Support factual claims with source citations.",
        ),
    ),
)


def validate_question_set(
    questions: tuple[EvaluationQuestion, ...] = EVALUATION_QUESTIONS,
) -> None:
    """Validate that a benchmark contains unique question IDs."""
    ids = [question.id for question in questions]

    if len(ids) != len(set(ids)):
        raise ValueError("Question IDs must be unique.")
    if not questions:
        raise ValueError("The evaluation question set must not be empty.")