import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Modern SQLAlchemy 2.0 Declarative Base."""

    pass


class AssetType(enum.StrEnum):
    EQUITY = "EQUITY"
    MUTUAL_FUND = "MUTUAL_FUND"


class TargetStatus(enum.StrEnum):
    PENDING_RESOLUTION = "PENDING_RESOLUTION"
    ACTIVE = "ACTIVE"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    FAILED = "FAILED"


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
    status: Mapped[TargetStatus] = mapped_column(
        SQLEnum(TargetStatus),
        default=TargetStatus.PENDING_RESOLUTION,
        server_default="PENDING_RESOLUTION",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    ai_insights: Mapped[list["AIBriefResult"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )
    vendor_mapping: Mapped["AssetVendorMapping"] = relationship(
        back_populates="target", uselist=False, cascade="all, delete-orphan"
    )


class AssetVendorMapping(Base):
    __tablename__ = "asset_vendor_mapping"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # unique=True enforces the strict 1-to-1 relationship at the DB level
    target_id: Mapped[int] = mapped_column(
        ForeignKey("target_configs.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    yfinance_symbol: Mapped[str | None] = mapped_column(String(50))
    screener_symbol: Mapped[str | None] = mapped_column(String(50))
    nse_symbol: Mapped[str | None] = mapped_column(String(50))
    amfi_code: Mapped[str | None] = mapped_column(String(50))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    target: Mapped["TargetConfig"] = relationship(back_populates="vendor_mapping")


class JobRunMetadata(Base):
    __tablename__ = "job_run_metadata"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), default=JobStatus.PENDING)

    celery_task_id: Mapped[str | None] = mapped_column(String(255), index=True)
    brief_markdown: Mapped[str | None] = mapped_column(Text)
    raw_response: Mapped[dict | list | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )

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
