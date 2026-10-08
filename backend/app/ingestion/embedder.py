from collections.abc import Sequence

import httpx

EMBEDDING_BATCH_SIZE = 16


async def embed_texts(
    client: httpx.AsyncClient,
    texts: Sequence[str],
    *,
    model: str,
    dimensions: int,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        response = await client.post(
            f"/hf-inference/models/{model}",
            json={"inputs": batch, "normalize": True},
        )
        response.raise_for_status()
        vectors = response.json()
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
            raise RuntimeError(
                "Hugging Face returned embeddings with an unexpected shape"
            )
        embeddings.extend([[float(value) for value in vector] for vector in vectors])

    if len(embeddings) != len(texts):
        raise RuntimeError(
            "Hugging Face returned an unexpected number of embeddings"
        )
    return embeddings
