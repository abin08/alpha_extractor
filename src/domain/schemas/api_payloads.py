from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.storage.db.orm_models import AssetType, TargetStatus


class TargetBase(BaseModel):
    """Base properties shared across all TargetConfig schemas."""

    asset_type: AssetType = Field(description="Must be EQUITY or MUTUAL_FUND")
    identifier: str = Field(..., max_length=50, description="Ticker symbol or ISIN")
    name: str | None = Field(None, max_length=100, description="Human readable name")
    is_active: bool = True


class TargetCreate(TargetBase):
    """Payload expected when creating a new target."""

    pass


class TargetResponse(TargetBase):
    """Payload returned to the client, including database-generated fields."""

    id: int
    status: TargetStatus

    # This tells Pydantic to read the data from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)


class VendorMappingUpdate(BaseModel):
    """Payload for manually updating vendor routing symbols. All fields optional."""

    yfinance_symbol: str | None = Field(None, max_length=50, description="Yahoo Finance symbol")
    screener_symbol: str | None = Field(None, max_length=50, description="Screener.in URL slug")
    nse_symbol: str | None = Field(None, max_length=50, description="NSE official symbol")
    amfi_code: str | None = Field(None, max_length=50, description="AMFI Mutual Fund code")


class JobStatusResponse(BaseModel):
    """Response payload for Celery job status tracking."""

    task_id: str = Field(..., description="The Celery Task/Chain ID")
    status: str = Field(
        ..., description="Current state of the job (e.g., PENDING, SUCCESS, FAILURE)"
    )
    result: Any | None = Field(None, description="The final result if successful")
    error_message: str | None = Field(None, description="Sanitized error details if the job failed")
