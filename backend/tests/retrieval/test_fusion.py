from datetime import date
from uuid import UUID

from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import SourcePassage


def passage(chunk_id: str, content: str) -> SourcePassage:
    return SourcePassage(
        chunk_id=UUID(chunk_id),
        document_id=UUID("00000000-0000-0000-0000-000000000001"),
        content=content,
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


def test_reciprocal_rank_fusion_combines_lists_and_deduplicates() -> None:
    first = passage("00000000-0000-0000-0000-000000000001", "first")
    second = passage("00000000-0000-0000-0000-000000000002", "second")
    third = passage("00000000-0000-0000-0000-000000000003", "third")

    results = reciprocal_rank_fusion(
        ([first, second], [second, third]),
        rank_constant=0,
    )

    assert [item.chunk_id for item in results] == [
        second.chunk_id,
        first.chunk_id,
        third.chunk_id,
    ]
    assert results[0].content == "second"
    assert results[0].score == 1 / 2 + 1
    assert results[1].score == 1
