from collections.abc import Sequence
from math import sqrt

import httpx

EMBEDDING_BATCH_SIZE = 16


class InferenceRequestError(RuntimeError):
    """A Gemini inference request failed with an actionable status."""


def _raise_inference_error(response: httpx.Response) -> None:
    if response.is_success:
        return
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        detail = "Gemini quota or rate limit reached. Wait before retrying ingestion."
        if retry_after:
            detail += f" Retry after {retry_after} seconds."
    elif response.status_code in {400, 401, 403}:
        detail = (
            "Gemini rejected the request or API key; check Gemini API access "
            "and model configuration."
        )
    elif response.status_code == 503:
        detail = "Gemini inference is temporarily unavailable."
    else:
        detail = f"Gemini embedding request failed (HTTP {response.status_code})."
    raise InferenceRequestError(detail)


async def embed_texts(
    client: httpx.AsyncClient,
    texts: Sequence[str],
    *,
    model: str,
    dimensions: int,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        try:
            response = await client.post(
                f"/v1beta/models/{model}:batchEmbedContents",
                json={
                    "requests": [
                        {
                            "model": f"models/{model}",
                            "taskType": task_type,
                            "output_dimensionality": dimensions,
                            "content": {"parts": [{"text": text}]},
                        }
                        for text in batch
                    ]
                },
            )
        except httpx.HTTPError as exc:
            raise InferenceRequestError(
                "Could not reach the Gemini embedding API."
            ) from exc
        _raise_inference_error(response)
        result = response.json()
        items = result.get("embeddings") if isinstance(result, dict) else None
        vectors = (
            [item.get("values") for item in items]
            if isinstance(items, list)
            and all(isinstance(item, dict) for item in items)
            else None
        )
        if (
            not isinstance(vectors, list)
            or len(vectors) != len(batch)
            or any(
                not isinstance(vector, list)
                or len(vector) != dimensions
                or any(not isinstance(value, (int, float)) for value in vector)
                for vector in vectors
            )
        ):
            raise InferenceRequestError(
                "Gemini returned embeddings with an unexpected shape"
            )
        for vector in vectors:
            values = [float(value) for value in vector]
            magnitude = sqrt(sum(value * value for value in values))
            if magnitude == 0:
                raise InferenceRequestError(
                    "Gemini returned a zero-length embedding"
                )
            embeddings.append([value / magnitude for value in values])

    if len(embeddings) != len(texts):
        raise InferenceRequestError(
            "Gemini returned an unexpected number of embeddings"
        )
    return embeddings
