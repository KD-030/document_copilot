from datetime import date
from uuid import UUID

from pydantic import BaseModel


class SearchFilters(BaseModel):
    ticker: str | None = None
    fiscal_year: int | None = None


class SourcePassage(BaseModel):
    chunk_id: UUID
    document_id: UUID
    content: str
    section_title: str | None
    page_start: int | None
    page_end: int | None
    ticker: str
    company_name: str
    form_type: str
    fiscal_year: int
    filed_at: date | None
    source_url: str
    score: float = 0
