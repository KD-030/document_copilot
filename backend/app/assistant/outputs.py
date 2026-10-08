from uuid import UUID

from pydantic import BaseModel, Field


class GroundedAnswer(BaseModel):
    answer: str = Field(min_length=1)
    citation_ids: list[UUID]
