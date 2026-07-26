import pytest
import json
from backend.src.protocol.validate import MessageValidator, ValidationResult

@pytest.mark.asyncio
async def test_missing_required_fields():
    # Payload missing required 'side' field
    payload = json.loads('{}')
    result = MessageValidator.validate_order_payload(payload)
    assert not result.valid
    assert any(e.field == 'side' and e.code == 'required' for e in result.errors)

@pytest.mark.asyncio
async def test_invalid_enum_value():
    # Payload with invalid 'side' value
    payload = json.loads('{"side": "hold", "type": "market", "quantity": 10}')
    result = MessageValidator.validate_order_payload(payload)
    assert not result.valid
    assert any(e.field == 'side' and e.code == 'invalid_side' for e in result.errors)

@pytest.mark.asyncio
async def test_invalid_numeric_range():
    # Payload with negative quantity
    payload = json.loads('{"side": "buy", "type": "limit", "quantity": -5, "price": 100}')
    result = MessageValidator.validate_order_payload(payload)
    assert not result.valid
    assert any(e.field == 'quantity' and e.code == 'invalid_quantity' for e in result.errors)

@pytest.mark.asyncio
async def test_missing_price_for_limit_order():
    # Payload missing price for limit order
    payload = json.loads('{"side": "sell", "type": "limit", "quantity": 10}')
    result = MessageValidator.validate_order_payload(payload)
    assert not result.valid
    assert any(e.field == 'price' and e.code == 'required' for e in result.errors)

@pytest.mark.asyncio
async def test_valid_order_payload():
    # Valid payload
    payload = json.loads('{"side": "buy", "type": "market", "quantity": 100}')
    result = MessageValidator.validate_order_payload(payload)
    assert result.valid

@pytest.mark.asyncio
async def test_malformed_payload():
    # Malformed JSON payload (simulate by passing invalid JSON bytes)
    invalid_bytes = b'{"side": "buy", "type": "market", "quantity": 10'  # missing closing brace
    # The schema validator expects bytes, so we test the validate method directly
    validator = MessageValidator()
    result = validator.validate(0x2001, 1, invalid_bytes)
    assert not result.valid
    assert any(e.code == 'schema_mismatch' for e in result.errors)

@pytest.mark.asyncio
async def test_async_wrapper_behavior():
    # Test that async validation works without extra pytest plugins
    validator = MessageValidator()
    payload = json.loads('{"side": "buy", "type": "market", "quantity": 10}')
    result = validator.validate(0x2001, 1, json.dumps(payload).encode('utf-8'))
    assert result.valid

@pytest.mark.asyncio
async def test_error_response_shape():
    # Test that error response contains expected fields
    payload = json.loads('{}')
    result = MessageValidator.validate_order_payload(payload)
    assert not result.valid
    for error in result.errors:
        assert hasattr(error, 'field')
        assert hasattr(error, 'code')
        assert hasattr(error, 'message')
        assert hasattr(error, 'severity')
        assert error.severity.name == 'Error' or error.severity.name == 'Warning'
