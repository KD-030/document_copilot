from collections.abc import Sequence

from app.assistant.agent import NOT_ENOUGH_EVIDENCE
from app.assistant.outputs import GroundedAnswer
from app.retrieval.models import SourcePassage


class GroundingError(ValueError):
    """The generated answer does not cite its retrieved evidence safely."""


def validate_answer(
    answer: GroundedAnswer,
    passages: Sequence[SourcePassage],
) -> list[SourcePassage]:
    if answer.answer.strip() == NOT_ENOUGH_EVIDENCE and not answer.citation_ids:
        return []

    passage_by_id = {passage.chunk_id: passage for passage in passages}
    if not answer.citation_ids:
        raise GroundingError("A supported answer must include at least one citation")

    cited_passages: list[SourcePassage] = []
    seen_ids = set()
    for citation_id in answer.citation_ids:
        if citation_id not in passage_by_id:
            raise GroundingError("Answer cites a passage that was not retrieved")
        if citation_id not in seen_ids:
            cited_passages.append(passage_by_id[citation_id])
            seen_ids.add(citation_id)
    return cited_passages
