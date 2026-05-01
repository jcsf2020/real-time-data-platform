from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from rtdp_contracts import MarketEvent


def test_market_event_contract_accepts_valid_trade_event() -> None:
    event = MarketEvent(
        event_id="event-1",
        symbol="BTCUSDT",
        price="100.50",
        quantity="0.25",
        event_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert event.schema_version == "1.0"
    assert event.event_type == "trade"
    assert event.event_id == "event-1"
    assert event.symbol == "BTCUSDT"


def test_market_event_contract_rejects_invalid_price() -> None:
    with pytest.raises(ValidationError):
        MarketEvent(
            event_id="event-1",
            symbol="BTCUSDT",
            price="0",
            quantity="0.25",
            event_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_market_event_contract_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValidationError):
        MarketEvent(
            schema_version="2.0",
            event_id="event-1",
            symbol="BTCUSDT",
            price="100.50",
            quantity="0.25",
            event_timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        )
