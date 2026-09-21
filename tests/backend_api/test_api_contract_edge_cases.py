"""
Backend API contract edge‑case tests.

Run locally with:
    python3 -m pytest -q tests/backend_api

These tests focus on negative scenarios:
* malformed or missing required fields,
* async helper execution without extra pytest plugins,
* response error shape verification.
"""

import asyncio
import pytest

# Import the contract helpers. Adjust the import path if the module location changes.
from backend.api_contract import (
    ContractError,
    validate_payload,
    async_wrapper,
    format_error_response,
)


# ----------------------------------------------------------------------
# Helper schemas used across tests
# ----------------------------------------------------------------------
_SIMPLE_SCHEMA = {
    "name": str,
    "age": int,
}


def _valid_payload():
    """Return a payload that satisfies ``_SIMPLE_SCHEMA``."""
    return {"name": "Alice", "age": 30}


# ----------------------------------------------------------------------
# 1. Malformed / missing required fields
# ----------------------------------------------------------------------
def test_validate_payload_missing_field_raises_contract_error():
    """Payload missing a required key should raise ``ContractError`` with a
    deterministic structure."""
    payload = {"name": "Bob"}  # ``age`` is missing
    with pytest.raises(ContractError) as exc_info:
        validate_payload(payload, _SIMPLE_SCHEMA)

    err = exc_info.value
    # The contract error must expose ``code`` and ``message`` attributes.
    assert hasattr(err, "code")
    assert hasattr(err, "message")
    assert err.code == "invalid_payload"
    # The message should mention the missing field.
    assert "age" in err.message.lower()


def test_validate_payload_wrong_type_raises_contract_error():
    """Payload with a field of the wrong type should raise ``ContractError``."""
    payload = {"name": "Charlie", "age": "not-an-int"}  # ``age`` should be int
    with pytest.raises(ContractError) as exc_info:
        validate_payload(payload, _SIMPLE_SCHEMA)

    err = exc_info.value
    assert err.code == "invalid_payload"
    assert "age" in err.message.lower()
    assert "int" in err.message.lower()


# ----------------------------------------------------------------------
# 2. Async helper execution
# ----------------------------------------------------------------------
@pytest.mark.asyncio
async def test_async_wrapper_runs_sync_function():
    """``async_wrapper`` should correctly execute a regular (sync) function
    and return its result without requiring any pytest async plugins."""
    def sync_add(a: int, b: int) -> int:
        return a + b

    result = await async_wrapper(sync_add, 2, 3)
    assert result == 5


@pytest.mark.asyncio
async def test_async_wrapper_propagates_exception():
    """Exceptions raised inside the wrapped function must propagate."""
    def sync_fail():
        raise ValueError("boom")

    with pytest.raises(ValueError) as exc_info:
        await async_wrapper(sync_fail)

    assert "boom" in str(exc_info.value)


@pytest.mark.asyncio
async def test_async_wrapper_handles_coroutine():
    """If the wrapped callable is already a coroutine, ``async_wrapper`` should
    await it and return the coroutine's result."""
    async def async_mul(a: int, b: int) -> int:
        await asyncio.sleep(0)  # force a real await point
        return a * b

    result = await async_wrapper(async_mul, 4, 5)
    assert result == 20


# ----------------------------------------------------------------------
# 3. Error response shape verification
# ----------------------------------------------------------------------
def test_format_error_response_structure():
    """``format_error_response`` must return a deterministic JSON‑compatible dict."""
    err = ContractError(
        code="invalid_payload",
        message="Missing required field: age",
        details={"field": "age"},
    )
    resp = format_error_response(err)

    # Top‑level must contain an ``error`` key.
    assert isinstance(resp, dict)
    assert "error" in resp
    error_body = resp["error"]
    # The nested error object must contain the three expected fields.
    assert error_body["code"] == "invalid_payload"
    assert error_body["message"] == "Missing required field: age"
    assert error_body["details"] == {"field": "age"}
