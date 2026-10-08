from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.chunk import Chunk
    from app.database.models.message import Message


class MessageCitation(Base):
    """Connects an assistant response to the source passages it cites."""

    __tablename__ = "message_citations"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "citation_order", name="uq_message_citations_order"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    message_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("chunks.id", ondelete="RESTRICT"), nullable=False
    )
    citation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    cited_text: Mapped[str | None] = mapped_column(Text)

    message: Mapped["Message"] = relationship(back_populates="citations")
    chunk: Mapped["Chunk"] = relationship(back_populates="citations")
