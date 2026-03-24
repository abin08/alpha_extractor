import enum
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Modern SQLAlchemy 2.0 Declarative Base."""

    pass


class AssetType(enum.StrEnum):
    EQUITY = "EQUITY"
    MUTUAL_FUND = "MUTUAL_FUND"


class JobStatus(enum.StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TargetConfig(Base):
    __tablename__ = "target_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), nullable=False)
    identifier: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ai_insights: Mapped[list["AIBriefResult"]] = relationship(back_populates="target")


class JobRunMetadata(Base):
    __tablename__ = "job_run_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), default=JobStatus.PENDING)

    # Where the massive raw context is stored in MinIO/S3
    s3_raw_uri: Mapped[str | None] = mapped_column(String(255))

    # Overarching market sentiment from the AI
    macro_sentiment: Mapped[str | None] = mapped_column(String(50))
    sector_rotation: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    ai_insights: Mapped[list["AIBriefResult"]] = relationship(back_populates="job_run")


class AIBriefResult(Base):
    __tablename__ = "ai_brief_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_run_id: Mapped[int] = mapped_column(
        ForeignKey("job_run_metadata.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[int] = mapped_column(
        ForeignKey("target_configs.id", ondelete="CASCADE"), index=True
    )

    # The extracted edge
    sentiment: Mapped[str] = mapped_column(String(50), nullable=False)
    catalyst: Mapped[str] = mapped_column(Text, nullable=False)
    actionable_edge: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    job_run: Mapped["JobRunMetadata"] = relationship(back_populates="ai_insights")
    target: Mapped["TargetConfig"] = relationship(back_populates="ai_insights")
