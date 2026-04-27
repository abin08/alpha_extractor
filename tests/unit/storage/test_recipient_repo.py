from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.db.orm_models import NotificationRecipient
from src.storage.db.repositories.recipient_repo import RecipientRepository


@pytest.fixture
def mock_session():
    """Fixture for a mocked AsyncSession."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.mark.asyncio
async def test_get_all_recipients(mock_session):
    """Test retrieving all recipients."""
    repo = RecipientRepository(mock_session)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        NotificationRecipient(id=1, email="one@example.com"),
        NotificationRecipient(id=2, email="two@example.com"),
    ]
    mock_session.execute.return_value = mock_result

    recipients = await repo.get_all()

    assert len(recipients) == 2
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_active_recipients(mock_session):
    """Test retrieving only active recipients."""
    repo = RecipientRepository(mock_session)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        NotificationRecipient(id=1, email="active@example.com", is_active=True),
    ]
    mock_session.execute.return_value = mock_result

    recipients = await repo.get_all_active()

    assert len(recipients) == 1
    assert recipients[0].is_active is True
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_recipient_success(mock_session):
    """Test successful recipient creation."""
    repo = RecipientRepository(mock_session)

    result = await repo.create("new@example.com")

    assert result.email == "new@example.com"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once()


@pytest.mark.asyncio
async def test_create_recipient_duplicate_error(mock_session):
    """Test that IntegrityError (duplicate email) returns None and rolls back."""
    repo = RecipientRepository(mock_session)

    # Simulate a DB unique constraint violation on commit
    mock_session.commit.side_effect = IntegrityError(
        "Unique constraint failed", params={}, orig=None
    )

    result = await repo.create("duplicate@example.com")

    assert result is None
    mock_session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_delete_recipient_success(mock_session):
    """Test deleting an existing recipient."""
    repo = RecipientRepository(mock_session)
    mock_recipient = NotificationRecipient(id=5, email="delete@example.com")

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_recipient
    mock_session.execute.return_value = mock_execute_result

    deleted = await repo.delete(5)

    assert deleted is True
    mock_session.delete.assert_called_once_with(mock_recipient)
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_recipient_not_found(mock_session):
    """Test deleting a recipient that doesn't exist."""
    repo = RecipientRepository(mock_session)

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_execute_result

    deleted = await repo.delete(999)

    assert deleted is False
    mock_session.delete.assert_not_called()
    mock_session.commit.assert_not_called()
