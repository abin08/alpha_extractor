from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from src.tasks.workers.delivery_tasks import (
    _process_daily_digest,
    deliver_daily_digest_task,
)


@pytest.fixture
def mock_db_session():
    """Fixture to mock the AsyncSessionLocal and SQLAlchemy execution."""
    with patch("src.tasks.workers.delivery_tasks.AsyncSessionLocal") as mock_session_class:
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session
        yield mock_session


@pytest.mark.asyncio
@patch("src.tasks.workers.delivery_tasks.AlphaExtractorEmail")
@patch("src.tasks.workers.delivery_tasks.UNGClient")
async def test_process_daily_digest_success(mock_ung_class, mock_renderer_class, mock_db_session):
    """Test that the digest engine queries raw JSON, maps it to the UI component, and dispatches."""

    # 1. Arrange Input
    chord_results = [
        {"status": "success", "ticker": "RELIANCE.NS", "job_id": 10},
        {"status": "error", "ticker": "HDFCBANK.NS", "job_id": None},
    ]

    # 2. Arrange DB Mocks
    # 2a. Mock Recipients (First call to session.scalars)
    mock_recipients = MagicMock()
    mock_recipients.all.return_value = ["admin@alpha.com"]

    # 2b. Mock Targets (Call to session.execute)
    class MockRow:
        def __init__(self, identifier, name):
            self.identifier = identifier
            self.name = name

    # Mocking the iterable result of session.execute()
    mock_db_session.execute.return_value = [MockRow("RELIANCE.NS", "Reliance Industries Ltd")]

    # 2c. Mock JobRunMetadata JSON (Second call to session.scalars)
    mock_job = MagicMock()
    mock_job.id = 10
    mock_job.macro_sentiment = "BULLISH"
    mock_job.sector_rotation = "Tech leading the market."
    mock_job.raw_response = {
        "insights": [
            {
                "sentiment": "BULLISH",
                "catalyst": "Stellar Q4 Earnings.",
                "actionable_edge": "Buy on dips.",
            }
        ]
    }

    # Sequence the scalars calls: 1st returns recipients, 2nd returns jobs
    mock_db_session.scalars.side_effect = [mock_recipients, [mock_job]]

    # 3. Arrange Component & Client Mocks
    mock_renderer_instance = mock_renderer_class.return_value
    mock_renderer_instance.render.return_value = "<html><body>Pure Python UI</body></html>"

    mock_ung_instance = mock_ung_class.return_value
    mock_ung_instance.dispatch_brief = AsyncMock()

    # 4. Act
    result = await _process_daily_digest(chord_results)

    # 5. Assertions
    assert "Delivered Daily Digest (1 insights)" in result

    # Verify the UI component received the correctly mapped dictionary
    mock_renderer_instance.render.assert_called_once()
    template_data = mock_renderer_instance.render.call_args[0][0]

    assert template_data["macroSentiment"] == "bullish"
    assert template_data["macroSummary"] == "Tech leading the market."
    assert len(template_data["assets"]) == 1

    asset = template_data["assets"][0]
    assert asset["ticker"] == "RELIANCE.NS"
    assert asset["name"] == "Reliance Industries Ltd"
    assert asset["sentiment"] == "bullish"
    assert asset["catalyst"] == "Stellar Q4 Earnings."
    assert asset["actionableEdge"] == "Buy on dips."

    # Verify UNG Client dispatched the HTML
    mock_ung_instance.dispatch_brief.assert_called_once_with(
        ticker="DAILY_DIGEST",
        html_payload="<html><body>Pure Python UI</body></html>",
        recipients=["admin@alpha.com"],
        trace_id=ANY,
    )


@patch("src.tasks.workers.delivery_tasks._process_daily_digest", new_callable=MagicMock)
@patch("src.tasks.workers.delivery_tasks.asyncio.run")
def test_deliver_daily_digest_task_wrapper(mock_asyncio_run, mock_process):
    """Verify the new fan-in Celery wrapper executes correctly."""
    mock_asyncio_run.return_value = "Delivered Digest"
    dummy_coro = MagicMock(name="dummy_coroutine")
    mock_process.return_value = dummy_coro

    chord_results = [{"status": "success", "ticker": "RELIANCE.NS", "job_id": 10}]

    result = deliver_daily_digest_task(chord_results)

    assert result == "Delivered Digest"
    mock_process.assert_called_once_with(chord_results)
    mock_asyncio_run.assert_called_once_with(dummy_coro)
