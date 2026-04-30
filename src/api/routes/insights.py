from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db
from src.core.logger import get_logger
from src.domain.schemas.api_payloads import PaginatedSearchResponse
from src.storage.db.repositories.briefs import BriefRepository

logger = get_logger(__name__)
router = APIRouter(prefix="/insights", tags=["Insights & Search"])


@router.get(
    "/search",
    response_model=PaginatedSearchResponse,
    status_code=status.HTTP_200_OK,
)
async def search_historical_insights(
    ticker: str | None = Query(
        None, description="Filter by exact Target Ticker (e.g. RELIANCE.NS)"
    ),
    asset_type: str | None = Query(None, description="Filter by EQUITY or MUTUAL_FUND"),
    sentiment: str | None = Query(
        None, description="Filter by insight sentiment (BULLISH, BEARISH, NEUTRAL)"
    ),
    macro_sentiment: str | None = Query(None, description="Filter by overarching macro sentiment"),
    date_from: datetime | None = Query(None, description="Start date (ISO 8601 format)"),
    date_to: datetime | None = Query(None, description="End date (ISO 8601 format)"),
    keyword: str | None = Query(
        None, description="Full-text search in catalyst or actionable edge"
    ),
    limit: int = Query(50, ge=1, le=100, description="Max results to return per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search and paginate historical AI-generated insights.
    Allows dynamic filtering across assets, sentiments, and chronological windows.
    """
    logger.info(f"API Request: Search insights (ticker={ticker}, keyword={keyword}, limit={limit})")

    repo = BriefRepository(db)

    try:
        # 1. Execute the 3-way JOIN search query
        result_dict = await repo.search_insights(
            ticker=ticker,
            asset_type=asset_type,
            sentiment=sentiment,
            macro_sentiment=macro_sentiment,
            date_from=date_from,
            date_to=date_to,
            keyword=keyword,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Failed to fetch historical insights: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while searching insights.",
        )

    # 2. Map the raw repository dictionary directly to the final Pydantic Response Schema
    return PaginatedSearchResponse(
        data=result_dict["data"],
        pagination={
            "total_results": result_dict["total_results"],
            "limit": limit,
            "offset": offset,
        },
    )
