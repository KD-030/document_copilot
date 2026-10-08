import asyncio

import httpx
from supabase import AsyncClient

from app.config import settings
from app.ingestion.embedder import embed_texts
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.models import SearchFilters, SourcePassage

SEARCH_RESULT_LIMIT = 20


async def _search(
    client: AsyncClient,
    function_name: str,
    parameters: dict[str, object],
) -> list[SourcePassage]:
    response = await client.rpc(function_name, parameters).execute()
    return [SourcePassage.model_validate(row) for row in response.data]


async def retrieve_passages(
    supabase: AsyncClient,
    inference: httpx.AsyncClient,
    query: str,
    *,
    filters: SearchFilters | None = None,
    limit: int = SEARCH_RESULT_LIMIT,
) -> list[SourcePassage]:
    if not query.strip():
        raise ValueError("Search query must not be empty")
    if not 1 <= limit <= 100:
        raise ValueError("Search result limit must be between 1 and 100")

    filters = filters or SearchFilters()
    embedding = (
        await embed_texts(
            inference,
            [query],
            model=settings.hf_embedding_model,
            dimensions=settings.hf_embedding_dimensions,
        )
    )[0]
    vector_text = "[" + ",".join(map(str, embedding)) + "]"
    filter_parameters: dict[str, object] = {
        "result_limit": limit,
        "filter_ticker": filters.ticker,
        "filter_fiscal_year": filters.fiscal_year,
    }
    vector_parameters = {
        **filter_parameters,
        "query_embedding": vector_text,
    }
    text_parameters = {
        **filter_parameters,
        "query_text": query,
    }

    vector_results, text_results = await asyncio.gather(
        _search(supabase, "search_chunks_by_embedding", vector_parameters),
        _search(supabase, "search_chunks_by_text", text_parameters),
    )
    return reciprocal_rank_fusion((vector_results, text_results))
