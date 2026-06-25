"""Shared fixtures for backend API contract edge-case tests."""

from __future__ import annotations

import pytest

from backend.api_contract import (
    MessageEnvelope,
    PROTOCOL_VERSION,
    MIN_COMPATIBLE_VERSION,
    MAX_MESSAGE_SIZE,
)


@pytest.fixture
def valid_order_payload():
    return {
        "side": "buy",
        "type": "limit",
        "quantity": 10.0,
        "price": 150.25,
        "time_in_force": "gtc",
    }


@pytest.fixture
def valid_market_order_payload():
    return {
        "side": "sell",
        "type": "market",
        "quantity": 5.0,
    }


@pytest.fixture
def valid_account_payload():
    return {
        "amount": 1000.00,
        "currency": "USD",
    }


@pytest.fixture
def valid_envelope():
    return MessageEnvelope(
        message_id=0x2001,
        message_type=0x01,
        schema_version=PROTOCOL_VERSION,
        timestamp=1700000000000,
        payload=b"{}",
    )


@pytest.fixture
def minimal_envelope():
    return MessageEnvelope(
        message_id=0x5001,
        message_type=0x01,
        schema_version=PROTOCOL_VERSION,
    )
