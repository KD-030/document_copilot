import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID

from app.retrieval import retriever
from app.retrieval.models import SearchFilters


def search_row(chunk_id: str, content: str) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "document_id": "00000000-0000-0000-0000-000000000010",
        "content": content,
        "section_title": "Business",
        "page_start": None,
        "page_end": None,
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "form_type": "10-K",
        "fiscal_year": 2025,
        "filed_at": date(2025, 10, 31).isoformat(),
        "source_url": "https://www.sec.gov/filing",
        "score": 0.5,
    }


class FakeRpc:
    def __init__(self, response):
        self.response = response

    async def execute(self):
        return self.response


class FakeSupabase:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def rpc(self, name, parameters):
        self.calls.append((name, parameters))
        return FakeRpc(SimpleNamespace(data=self.results[name]))


def test_retrieve_passages_embeds_and_runs_both_searches(monkeypatch) -> None:
    first_id = "00000000-0000-0000-0000-000000000001"
    second_id = "00000000-0000-0000-0000-000000000002"
    client = FakeSupabase(
        {
            "search_chunks_by_embedding": [search_row(first_id, "vector result")],
            "search_chunks_by_text": [
                search_row(first_id, "vector result"),
                search_row(second_id, "text result"),
            ],
        }
    )
    embedded_inputs = []

    async def fake_embed_texts(inference, texts, *, model, dimensions):
        embedded_inputs.extend(texts)
        return [[0.1, 0.2]]

    monkeypatch.setattr(retriever, "embed_texts", fake_embed_texts)
    results = asyncio.run(
        retriever.retrieve_passages(
            client,
            object(),
            "cloud revenue",
            filters=SearchFilters(ticker="AAPL", fiscal_year=2025),
            limit=7,
        )
    )

    assert embedded_inputs == ["cloud revenue"]
    assert [item.chunk_id for item in results] == [
        UUID(first_id),
        UUID(second_id),
    ]
    assert {call[0] for call in client.calls} == {
        "search_chunks_by_embedding",
        "search_chunks_by_text",
    }
    vector_call = next(
        parameters
        for name, parameters in client.calls
        if name == "search_chunks_by_embedding"
    )
    assert vector_call == {
        "query_embedding": "[0.1,0.2]",
        "result_limit": 7,
        "filter_ticker": "AAPL",
        "filter_fiscal_year": 2025,
    }
