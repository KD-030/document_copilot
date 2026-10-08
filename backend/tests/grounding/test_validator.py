from datetime import date
from uuid import UUID

import pytest

from app.assistant.agent import NOT_ENOUGH_EVIDENCE
from app.assistant.outputs import GroundedAnswer
from app.grounding.validator import GroundingError, validate_answer
from app.retrieval.models import SourcePassage


def make_passage() -> SourcePassage:
    return SourcePassage(
        chunk_id=UUID("00000000-0000-0000-0000-000000000001"),
        document_id=UUID("00000000-0000-0000-0000-000000000010"),
        content="Services revenue increased.",
        section_title="Business",
        page_start=None,
        page_end=None,
        ticker="AAPL",
        company_name="Apple Inc.",
        form_type="10-K",
        fiscal_year=2025,
        filed_at=date(2025, 10, 31),
        source_url="https://www.sec.gov/filing",
    )


def test_validate_answer_returns_only_retrieved_citations() -> None:
    passage = make_passage()
    answer = GroundedAnswer(
        answer="Services revenue increased.",
        citation_ids=[passage.chunk_id, passage.chunk_id],
    )

    assert validate_answer(answer, [passage]) == [passage]


def test_validate_answer_rejects_uncited_claims() -> None:
    with pytest.raises(GroundingError, match="at least one citation"):
        validate_answer(
            GroundedAnswer(answer="Unsupported", citation_ids=[]), [make_passage()]
        )


def test_validate_answer_rejects_citations_outside_retrieved_evidence() -> None:
    answer = GroundedAnswer(
        answer="Unsupported",
        citation_ids=[UUID("00000000-0000-0000-0000-000000000002")],
    )

    with pytest.raises(GroundingError, match="not retrieved"):
        validate_answer(answer, [make_passage()])


def test_validate_answer_allows_not_enough_evidence_without_citations() -> None:
    answer = GroundedAnswer(answer=NOT_ENOUGH_EVIDENCE, citation_ids=[])

    assert validate_answer(answer, []) == []
