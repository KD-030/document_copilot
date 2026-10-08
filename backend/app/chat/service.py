from collections.abc import AsyncIterator, Sequence
from typing import Any
from uuid import UUID

import httpx
from openai import APIError as OpenAIAPIError
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior

from app.assistant.agent import NOT_ENOUGH_EVIDENCE, agent, evidence_prompt
from app.assistant.outputs import GroundedAnswer
from app.auth.dependencies import AuthenticatedUser
from app.chat.repository import persist_chat_turn
from app.chat.schemas import ChatTurnResponse, CitationRead
from app.config import settings
from app.grounding.validator import GroundingError, validate_answer
from app.ingestion.embedder import InferenceRequestError
from app.retrieval.models import SourcePassage
from app.retrieval.retriever import retrieve_passages


class AIServiceError(RuntimeError):
    """An upstream model request or grounded output failed."""


def _citation_responses(
    passages: Sequence[SourcePassage],
) -> list[CitationRead]:
    return [
        CitationRead(
            chunk_id=passage.chunk_id,
            citation_order=order,
            excerpt=passage.content,
            ticker=passage.ticker,
            company_name=passage.company_name,
            form_type=passage.form_type,
            fiscal_year=passage.fiscal_year,
            filed_at=passage.filed_at,
            section_title=passage.section_title,
            page_start=passage.page_start,
            page_end=passage.page_end,
            source_url=passage.source_url,
        )
        for order, passage in enumerate(passages)
    ]


async def stream_chat_turn(
    user: AuthenticatedUser,
    chat_id: UUID,
    question: str,
) -> AsyncIterator[dict[str, Any]]:
    async with httpx.AsyncClient(
        base_url="https://generativelanguage.googleapis.com",
        headers={"x-goog-api-key": settings.gemini_api_key},
        timeout=60,
    ) as inference:
        try:
            passages = await retrieve_passages(user.supabase, inference, question)
            if not passages:
                answer = GroundedAnswer(
                    answer=NOT_ENOUGH_EVIDENCE,
                    citation_ids=[],
                )
            else:
                async with agent.run_stream(
                    evidence_prompt(question, passages)
                ) as streamed_result:
                    emitted_text = ""
                    async for partial_answer in streamed_result.stream_output(
                        debounce_by=0.03
                    ):
                        current_text = partial_answer.answer
                        if (
                            not isinstance(current_text, str)
                            or current_text == emitted_text
                        ):
                            continue
                        if current_text.startswith(emitted_text):
                            yield {
                                "type": "delta",
                                "text": current_text[len(emitted_text) :],
                            }
                        else:
                            yield {"type": "replace", "text": current_text}
                        emitted_text = current_text
                    answer = await streamed_result.get_output()

            try:
                citations = validate_answer(answer, passages)
            except GroundingError as exc:
                raise AIServiceError(
                    "The answer did not meet the citation requirements"
                ) from exc

            user_message_id, assistant_message_id = await persist_chat_turn(
                user.supabase,
                chat_id,
                question,
                answer.answer,
                [passage.chunk_id for passage in citations],
            )
            yield {
                "type": "complete",
                "turn": ChatTurnResponse(
                    chat_id=chat_id,
                    user_message_id=user_message_id,
                    assistant_message_id=assistant_message_id,
                    user_content=question,
                    assistant_content=answer.answer,
                    citations=_citation_responses(citations),
                ).model_dump(mode="json"),
            }
        except (
            httpx.HTTPError,
            InferenceRequestError,
            OpenAIAPIError,
            ModelAPIError,
            UnexpectedModelBehavior,
        ) as exc:
            status = getattr(exc, "status_code", None)
            if status == 429:
                message = "Gemini quota or rate limit reached; wait before retrying."
            elif status in {400, 401, 403}:
                message = "Gemini rejected the request or API key; check Gemini API access and model configuration."
            else:
                message = "The Gemini answer service is unavailable."
            raise AIServiceError(message) from exc


async def answer_chat_turn(
    user: AuthenticatedUser,
    chat_id: UUID,
    question: str,
) -> ChatTurnResponse:
    turn: ChatTurnResponse | None = None
    async for event in stream_chat_turn(user, chat_id, question):
        if event["type"] == "complete":
            turn = ChatTurnResponse.model_validate(event["turn"])
    if turn is None:
        raise AIServiceError("The answer stream ended without a completed turn")
    return turn
