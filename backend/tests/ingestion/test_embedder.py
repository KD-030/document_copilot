import asyncio

import pytest

from app.ingestion.embedder import embed_texts


class FakeResponse:
    def __init__(self, vectors):
        self.vectors = vectors

    def raise_for_status(self):
        return None

    def json(self):
        return self.vectors


class FakeClient:
    def __init__(self, response_factory):
        self.response_factory = response_factory
        self.requests = []

    async def post(self, path, *, json):
        self.requests.append((path, json))
        return FakeResponse(self.response_factory(json["inputs"]))


def test_embed_texts_batches_inputs_and_validates_embedding_dimensions():
    client = FakeClient(lambda batch: [[0.1, 0.2] for _ in batch])

    embeddings = asyncio.run(
        embed_texts(
            client,
            [f"filing chunk {index}" for index in range(17)],
            model="BAAI/bge-small-en-v1.5",
            dimensions=2,
        )
    )

    assert len(embeddings) == 17
    assert [len(request[1]["inputs"]) for request in client.requests] == [16, 1]
    assert all(
        request[0] == "/hf-inference/models/BAAI/bge-small-en-v1.5"
        for request in client.requests
    )
    assert embeddings[0] == [0.1, 0.2]


def test_embed_texts_rejects_an_unexpected_embedding_shape():
    client = FakeClient(lambda batch: [[0.1] for _ in batch])

    with pytest.raises(RuntimeError, match="unexpected shape"):
        asyncio.run(
            embed_texts(
                client,
                ["filing chunk"],
                model="BAAI/bge-small-en-v1.5",
                dimensions=2,
            )
        )
