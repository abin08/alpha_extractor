from pydantic import BaseModel, ConfigDict, Field

from src.storage.db.orm_models import AssetType


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

    # This tells Pydantic to read the data from SQLAlchemy ORM models
    model_config = ConfigDict(from_attributes=True)
