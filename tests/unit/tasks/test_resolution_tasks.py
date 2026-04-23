from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import ResolutionError
from src.storage.db.orm_models import AssetType, TargetConfig, TargetStatus
from src.tasks.workers.resolution_tasks import _run_resolution_pipeline


@pytest.fixture
def mock_equity_target():
    """Returns a mock TargetConfig in the PENDING state."""
    target = MagicMock(spec=TargetConfig)
    target.id = 1
    target.identifier = "RELIANCE"
    target.asset_type = AssetType.EQUITY
    target.status = TargetStatus.PENDING_RESOLUTION
    return target


@pytest.mark.asyncio
@patch("src.tasks.workers.resolution_tasks.TargetRepository")
@patch("src.tasks.workers.resolution_tasks.AsyncSessionLocal")
@patch("src.tasks.workers.resolution_tasks.resolve_equity_symbols")
async def test_resolution_happy_path(
    mock_resolve_equity, mock_session_maker, mock_repo_class, mock_equity_target
):
    """Test that a successful resolution saves the mapping and sets status to ACTIVE."""
    # 1. Setup DB Session & Repo Mocks
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_id = AsyncMock(return_value=mock_equity_target)
    mock_repo.save_vendor_mapping = AsyncMock()
    mock_repo.update_status = AsyncMock()

    # 2. Setup Strategy Mock
    mock_resolve_equity.return_value = {"nse_symbol": "RELIANCE.NS"}

    # 3. Execute
    await _run_resolution_pipeline(1)

    # 4. Assert
    mock_repo.get_by_id.assert_called_once_with(1)
    mock_resolve_equity.assert_called_once_with("RELIANCE")
    mock_repo.save_vendor_mapping.assert_called_once_with(1, {"nse_symbol": "RELIANCE.NS"})
    mock_repo.update_status.assert_called_once_with(1, TargetStatus.ACTIVE)


@pytest.mark.asyncio
@patch("src.tasks.workers.resolution_tasks.TargetRepository")
@patch("src.tasks.workers.resolution_tasks.AsyncSessionLocal")
@patch("src.tasks.workers.resolution_tasks.resolve_equity_symbols")
async def test_resolution_domain_error_manual_intervention(
    mock_resolve_equity, mock_session_maker, mock_repo_class, mock_equity_target
):
    """Test that an unresolvable ticker sets the status to MANUAL_INTERVENTION."""
    # 1. Setup DB Session & Repo Mocks
    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_id = AsyncMock(return_value=mock_equity_target)
    mock_repo.save_vendor_mapping = AsyncMock()
    mock_repo.update_status = AsyncMock()

    # 2. Setup Strategy Mock to RAISE an error
    mock_resolve_equity.side_effect = ResolutionError(
        identifier="BAD_TICKER", reason="Not found on NSE"
    )

    # 3. Execute (It should raise the error up to Celery)
    with pytest.raises(ResolutionError):
        await _run_resolution_pipeline(1)

    # 4. Assert Failure Path
    mock_repo.save_vendor_mapping.assert_not_called()
    mock_repo.update_status.assert_called_once_with(1, TargetStatus.MANUAL_INTERVENTION)


@pytest.mark.asyncio
@patch("src.tasks.workers.resolution_tasks.TargetRepository")
@patch("src.tasks.workers.resolution_tasks.AsyncSessionLocal")
async def test_resolution_skips_active_target(
    mock_session_maker, mock_repo_class, mock_equity_target
):
    """Test that if a target is already ACTIVE, the orchestrator safely skips it."""
    # Set target to ACTIVE
    mock_equity_target.status = TargetStatus.ACTIVE

    mock_session = AsyncMock()
    mock_session_maker.return_value.__aenter__.return_value = mock_session

    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo
    mock_repo.get_by_id = AsyncMock(return_value=mock_equity_target)
    mock_repo.save_vendor_mapping = AsyncMock()
    mock_repo.update_status = AsyncMock()

    # Execute
    await _run_resolution_pipeline(1)

    # Assert it bailed out early
    mock_repo.save_vendor_mapping.assert_not_called()
    mock_repo.update_status.assert_not_called()
