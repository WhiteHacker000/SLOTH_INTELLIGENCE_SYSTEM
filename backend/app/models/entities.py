from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.schemas.decisions import DecisionStatus
from app.schemas.github import DiscussionSourceType


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    html_url: Mapped[str] = mapped_column(String(2048))
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Discussion(Base):
    __tablename__ = "discussions"
    __table_args__ = (
        UniqueConstraint(
            "repository_id", "source_type", "github_id", name="uq_discussion_source"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[DiscussionSourceType] = mapped_column(
        SqlEnum(
            DiscussionSourceType,
            name="discussion_source_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    github_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    repository_id: Mapped[UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), index=True
    )
    summary: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text)
    alternatives: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list)
    trade_offs: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[DecisionStatus] = mapped_column(
        SqlEnum(
            DecisionStatus,
            name="decision_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EvidenceReference(Base):
    __tablename__ = "evidence_references"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    discussion_id: Mapped[UUID] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), index=True
    )
    excerpt: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String(2048))


class DiscussionChunk(Base):
    __tablename__ = "discussion_chunks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    discussion_id: Mapped[UUID] = mapped_column(
        ForeignKey("discussions.id", ondelete="CASCADE"), index=True
    )
    ordinal: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    source_metadata: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
