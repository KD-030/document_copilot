from collections.abc import Sequence

from app.retrieval.models import SourcePassage


def reciprocal_rank_fusion(
    result_lists: Sequence[Sequence[SourcePassage]], *, rank_constant: int = 60
) -> list[SourcePassage]:
    scores: dict[str, float] = {}
    passages: dict[str, SourcePassage] = {}

    for results in result_lists:
        for rank, passage in enumerate(results, start=1):
            key = str(passage.chunk_id)
            scores[key] = scores.get(key, 0) + 1 / (rank_constant + rank)
            passages[key] = passage

    return [
        passages[key].model_copy(update={"score": score})
        for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ]
