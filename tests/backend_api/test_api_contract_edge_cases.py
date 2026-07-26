import pytest
import json
from backend.src.protocol.messages import MessageRegistry
from backend.src.protocol.serialize import Serializer, EncodingFormat
from backend.src.protocol.validate import MessageValidator, ValidationResult

@pytest.fixture
def registry():
    reg = MessageRegistry()
    # Register a dummy handler for a known message type for testing
    reg.register(0x1001, lambda payload: (payload, None))
    return reg

@pytest.fixture
def validator():
    val = MessageValidator()
    # Register a simple field validator for message type 0x1001
    def dummy_validator(payload):
        # Expect payload to be a JSON object with a required field "instrument_ids"
        if not isinstance(payload, dict):
            return ValidationResult.error("payload", "type_error", "Payload must be an object")
        if "instrument_ids" not in payload:
            return ValidationResult.error("instrument_ids", "required", "Missing instrument_ids")
        if not isinstance(payload["instrument_ids"], list):
            return ValidationResult.error("instrument_ids", "type_error", "instrument_ids must be a list")
        return ValidationResult.valid()
    val.register_field_validator(0x1001, dummy_validator)
    return val

def test_malformed_payload_missing_required_field(registry, validator):
    # Payload missing required field "instrument_ids"
    payload = json.dumps({"types": ["tick"]}).encode("utf-8")
    # Validate schema (simulate schema validation success)
    result = validator.validate(0x1001, 1, payload)
    assert result.has_errors()
    assert any(e.field == "instrument_ids" for e in result.errors)

def test_malformed_payload_wrong_type(registry, validator):
    # Payload with wrong type for instrument_ids
    payload = json.dumps({"instrument_ids": "not-a-list", "types": ["tick"]}).encode("utf-8")
    result = validator.validate(0x1001, 1, payload)
    assert result.has_errors()
    assert any("instrument_ids" in e.field for e in result.errors)

def test_async_wrapper_compatibility(registry):
    # Test that async handler can be called without special pytest plugins
    import asyncio

    async def async_handler(payload):
        await asyncio.sleep(0.01)
        return b"ok"

    registry.register(0x2001, lambda payload: asyncio.run(async_handler(payload)))

    # Call the async handler via the registry handle method
    result = registry.handle(0x2001, b"test")
    assert result == b"ok"

def test_response_status_and_body_assertions(registry):
    # Register a handler that returns error response for a specific input
    def error_handler(payload):
        if payload == b"bad":
            raise ValueError("Bad payload")
        return b"good"

    registry.register(0x3001, error_handler)

    # Test good payload
    result = registry.handle(0x3001, b"good")
    assert result == b"good"

    # Test bad payload triggers error
    with pytest.raises(ValueError):
        registry.handle(0x3001, b"bad")

def test_missing_handler_returns_error(registry):
    # Try to handle a message type with no registered handler
    with pytest.raises(Exception) as excinfo:
        registry.handle(0x9999, b"payload")
    assert "No handler registered" in str(excinfo.value)
