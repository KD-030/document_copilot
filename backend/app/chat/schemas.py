from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatTurnRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message content must not be blank")
        return value


class ChatRead(BaseModel):
    id: UUID
    title: str | None
    created_at: datetime
    updated_at: datetime


class CitationRead(BaseModel):
    chunk_id: UUID
    citation_order: int
    excerpt: str
    ticker: str
    company_name: str
    form_type: str
    fiscal_year: int
    filed_at: date | None
    section_title: str | None
    page_start: int | None
    page_end: int | None
    source_url: str


class MessageRead(BaseModel):
    id: UUID
    chat_id: UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    citations: list[CitationRead] = Field(default_factory=list)


class ChatTurnResponse(BaseModel):
    chat_id: UUID
    user_message_id: UUID
    assistant_message_id: UUID
    user_content: str
    assistant_content: str
    citations: list[CitationRead]
