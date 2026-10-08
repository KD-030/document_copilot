from collections.abc import Mapping
from uuid import UUID, uuid4

from supabase import AsyncClient

from app.auth.dependencies import AuthenticatedUser
from app.chat.schemas import ChatRead, CitationRead, MessageRead


async def list_chats(client: AsyncClient) -> list[ChatRead]:
    response = (
        await client.table("chats")
        .select("id,title,created_at,updated_at")
        .order("updated_at", desc=True)
        .execute()
    )
    return [ChatRead.model_validate(row) for row in response.data]


async def create_chat(user: AuthenticatedUser, title: str | None) -> ChatRead:
    response = (
        await user.supabase.table("chats")
        .insert({"id": str(uuid4()), "user_id": str(user.id), "title": title})
        .select("id,title,created_at,updated_at")
        .execute()
    )
    return ChatRead.model_validate(response.data[0])


async def get_chat(client: AsyncClient, chat_id: UUID) -> ChatRead | None:
    response = (
        await client.table("chats")
        .select("id,title,created_at,updated_at")
        .eq("id", str(chat_id))
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return ChatRead.model_validate(response.data[0])


async def list_messages(client: AsyncClient, chat_id: UUID) -> list[MessageRead]:
    response = (
        await client.table("messages")
        .select(
            "id,chat_id,role,content,created_at,"
            "message_citations(id,citation_order,cited_text,chunk_id,"
            "chunks(content,section_title,page_start,page_end,documents("
            "ticker,company_name,form_type,fiscal_year,filed_at,source_url)))"
        )
        .eq("chat_id", str(chat_id))
        .order("created_at")
        .execute()
    )

    messages = []
    for row in response.data:
        citations = []
        for citation in row.get("message_citations", []):
            chunk = citation.get("chunks") or {}
            document = chunk.get("documents") or {}
            citations.append(
                CitationRead(
                    chunk_id=citation["chunk_id"],
                    citation_order=citation["citation_order"],
                    excerpt=citation.get("cited_text") or chunk["content"],
                    ticker=document["ticker"],
                    company_name=document["company_name"],
                    form_type=document["form_type"],
                    fiscal_year=document["fiscal_year"],
                    filed_at=document["filed_at"],
                    section_title=chunk["section_title"],
                    page_start=chunk["page_start"],
                    page_end=chunk["page_end"],
                    source_url=document["source_url"],
                )
            )
        message = {
            key: value for key, value in row.items() if key != "message_citations"
        }
        messages.append(MessageRead.model_validate({**message, "citations": citations}))
    return messages


async def persist_chat_turn(
    client: AsyncClient,
    chat_id: UUID,
    user_content: str,
    assistant_content: str,
    citation_ids: list[UUID],
) -> tuple[UUID, UUID]:
    response = await client.rpc(
        "persist_chat_turn",
        {
            "p_chat_id": str(chat_id),
            "p_user_content": user_content,
            "p_assistant_content": assistant_content,
            "p_citation_ids": [str(citation_id) for citation_id in citation_ids],
        },
    ).execute()
    row: Mapping[str, object] = response.data[0]
    return UUID(str(row["user_message_id"])), UUID(str(row["assistant_message_id"]))
