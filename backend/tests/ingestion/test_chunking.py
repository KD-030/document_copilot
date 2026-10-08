import pytest

from app.ingestion.chunking import chunk_filing_text


def test_chunk_filing_text_keeps_sections_and_overlaps() -> None:
    business = " ".join(f"business{i}" for i in range(9))
    risks = " ".join(f"risk{i}" for i in range(4))
    text = f"Item 1. Business\n{business}\nItem 1A. Risk Factors\n{risks}"

    chunks = chunk_filing_text(text, max_words=5, overlap_words=1)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert [chunk.section_title for chunk in chunks] == [
        "Business",
        "Business",
        "Business",
        "Risk Factors",
        "Risk Factors",
    ]
    assert chunks[0].content.split()[-1] == chunks[1].content.split()[0]
    assert all(len(chunk.content.split()) <= 5 for chunk in chunks)


def test_chunk_filing_text_rejects_invalid_sizes() -> None:
    with pytest.raises(ValueError, match="Chunk size"):
        chunk_filing_text("text", max_words=3, overlap_words=3)
