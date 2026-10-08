import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from postgrest.exceptions import APIError

from app.auth.dependencies import CurrentUser
from app.chat.repository import (
    create_chat,
    get_chat,
    list_chats,
    list_messages,
)
from app.chat.schemas import (
    ChatCreateRequest,
    ChatRead,
    ChatTurnRequest,
    ChatTurnResponse,
    MessageRead,
)
from app.chat.service import AIServiceError, answer_chat_turn, stream_chat_turn
from app.grounding.validator import GroundingError

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("", response_model=list[ChatRead])
async def get_chats(current_user: CurrentUser) -> list[ChatRead]:
    try:
        return await list_chats(current_user.supabase)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to load chats from Supabase",
        ) from exc


@router.post("", response_model=ChatRead, status_code=status.HTTP_201_CREATED)
async def post_chat(
    request: ChatCreateRequest,
    current_user: CurrentUser,
) -> ChatRead:
    try:
        return await create_chat(current_user, request.title)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to create chat in Supabase",
        ) from exc


@router.get("/{chat_id}/messages", response_model=list[MessageRead])
async def get_chat_messages(
    chat_id: UUID,
    current_user: CurrentUser,
) -> list[MessageRead]:
    try:
        chat = await get_chat(current_user.supabase, chat_id)
        if chat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found",
            )
        return await list_messages(current_user.supabase, chat_id)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to load chat messages from Supabase",
        ) from exc


@router.post("/{chat_id}/messages", response_model=ChatTurnResponse)
async def post_chat_message(
    chat_id: UUID,
    request: ChatTurnRequest,
    current_user: CurrentUser,
) -> ChatTurnResponse:
    try:
        chat = await get_chat(current_user.supabase, chat_id)
        if chat is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found",
            )
        return await answer_chat_turn(current_user, chat_id, request.content)
    except HTTPException:
        raise
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except GroundingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The answer did not meet the citation requirements",
        ) from exc
    except APIError as exc:
        if exc.code == "P0002":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Chat not found",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase database request failed",
        ) from exc


@router.post("/{chat_id}/messages/stream")
async def post_chat_message_stream(
    chat_id: UUID,
    request: ChatTurnRequest,
    current_user: CurrentUser,
) -> StreamingResponse:
    try:
        chat = await get_chat(current_user.supabase, chat_id)
    except APIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to load chat from Supabase",
        ) from exc
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    async def events():
        try:
            async for event in stream_chat_turn(
                current_user,
                chat_id,
                request.content,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except AIServiceError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        except APIError:
            yield (
                "data: "
                f"{json.dumps({'type': 'error', 'message': 'Supabase database request failed'})}\n\n"
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
