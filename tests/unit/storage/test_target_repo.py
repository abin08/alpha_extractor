from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.schemas.api_payloads import AssetType, TargetCreate
from src.storage.db.orm_models import TargetConfig
from src.storage.db.repositories.target_repo import TargetRepository


@pytest.fixture
def mock_session():
    """
    Fixture for a mocked AsyncSession.

    Matches the TargetRepository implementation:
    - .execute, .commit, .rollback, .refresh, and .delete are used with 'await'.
    - .add is used synchronously.
    """
    session = MagicMock(spec=AsyncSession)

    # Methods that your code 'awaits' must be AsyncMock
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()  # This fixes the 'TypeError' in your delete method

    # Method used without 'await'
    session.add = MagicMock()

    return session


@pytest.mark.asyncio
async def test_get_all_targets(mock_session):
    """Test retrieving all targets with proper ordering."""
    repo = TargetRepository(mock_session)

    # Mock the return chain: session.execute() -> result.scalars().all()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        TargetConfig(id=1, identifier="AAPL"),
        TargetConfig(id=2, identifier="GOOGL"),
    ]
    mock_session.execute.return_value = mock_result

    targets = await repo.get_all()

    assert len(targets) == 2
    assert targets[0].identifier == "AAPL"
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_target_success(mock_session):
    """Test successful target creation."""
    repo = TargetRepository(mock_session)
    target_data = TargetCreate(
        asset_type=AssetType.EQUITY, identifier="TSLA", name="Tesla Inc", is_active=True
    )

    result = await repo.create(target_data)

    assert result.identifier == "TSLA"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_target_duplicate_error(mock_session):
    """Test that IntegrityError (duplicates) returns None and rolls back."""
    repo = TargetRepository(mock_session)
    target_data = TargetCreate(asset_type=AssetType.EQUITY, identifier="TSLA", name="Tesla Inc")

    # Simulate a DB unique constraint violation on commit
    mock_session.commit.side_effect = IntegrityError(
        "Unique constraint failed", params={}, orig=None
    )

    result = await repo.create(target_data)

    assert result is None
    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_delete_target_success(mock_session):
    """Test deleting an existing target."""
    repo = TargetRepository(mock_session)
    mock_target = TargetConfig(id=10, identifier="RELIANCE.NS")

    # Mock finding the object: session.execute() -> result.scalar_one_or_none()
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_target
    mock_session.execute.return_value = mock_execute_result

    # Act
    deleted = await repo.delete(10)

    # Assert
    assert deleted is True
    mock_session.delete.assert_called_once_with(mock_target)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_target_not_found(mock_session):
    """Test deleting a target that doesn't exist."""
    repo = TargetRepository(mock_session)

    # Mock finding nothing: session.execute() -> result.scalar_one_or_none() returns None
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_execute_result

    # Act
    deleted = await repo.delete(999)

    # Assert
    assert deleted is False
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()
