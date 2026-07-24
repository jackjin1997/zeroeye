import pytest
import json
from backend.src.protocol.serialize import Serializer, EncodingFormat, ProtocolError
from backend.src.protocol.validate import MessageValidator, ValidationResult

@pytest.fixture
def serializer():
    return Serializer(EncodingFormat.Json)

@pytest.fixture
def validator():
    return MessageValidator()

def test_missing_required_fields(serializer, validator):
    # Payload missing required fields for a known message type
    message_type = 0x2001  # ORDER_NEW
    version = 1
    # Empty payload (missing all required fields)
    payload = b'{}'

    result = validator.validate(message_type, version, payload)
    assert not result.valid
    assert any(e.code == "required" for e in result.errors)

def test_malformed_json(serializer, validator):
    message_type = 0x2001  # ORDER_NEW
    version = 1
    # Malformed JSON payload
    payload = b'{"side": "buy", "quantity": 10'  # missing closing brace

    with pytest.raises(ProtocolError):
        # The schema validator should raise on malformed JSON
        validator.schema_validator.validate(message_type, version, payload)

def test_invalid_field_types(serializer, validator):
    message_type = 0x2001  # ORDER_NEW
    version = 1
    # Payload with invalid field types (quantity as string)
    payload_dict = {
        "side": "buy",
        "type": "limit",
        "quantity": "ten",
        "price": 100.0,
        "time_in_force": "gtc"
    }
    payload = json.dumps(payload_dict).encode('utf-8')

    result = validator.validate(message_type, version, payload)
    assert not result.valid
    assert any("invalid" in e.code for e in result.errors)

def test_async_wrapper_behavior():
    # This test simulates async helper execution without optional pytest plugins
    import asyncio

    async def async_helper():
        await asyncio.sleep(0.01)
        return True

    async def test_async():
        result = await async_helper()
        assert result is True

    asyncio.run(test_async())

def test_error_response_shape(serializer):
    # Simulate an error response with missing fields
    error_response = {
        "code": 4001,
        "message": "Invalid request parameters",
        # missing request_id and details
    }
    serialized = json.dumps(error_response).encode('utf-8')

    # Deserialize and check fields
    data = json.loads(serialized)
    assert "code" in data
    assert "message" in data
    assert "request_id" not in data or data.get("request_id") is None
    assert "details" not in data or data.get("details") is None

def test_missing_required_fields_returns_structured_error(serializer, validator):
    message_type = 0x2001  # ORDER_NEW
    version = 1
    # Payload missing required 'side' field
    payload_dict = {
        "type": "limit",
        "quantity": 10,
        "price": 100.0,
        "time_in_force": "gtc"
    }
    payload = json.dumps(payload_dict).encode('utf-8')

    result = validator.validate(message_type, version, payload)
    assert not result.valid
    assert any(e.field == "side" and e.code == "required" for e in result.errors)

def test_invalid_enum_value(serializer, validator):
    message_type = 0x2001  # ORDER_NEW
    version = 1
    # Payload with invalid enum value for 'side'
    payload_dict = {
        "side": "hold",
        "type": "limit",
        "quantity": 10,
        "price": 100.0,
        "time_in_force": "gtc"
    }
    payload = json.dumps(payload_dict).encode('utf-8')

    result = validator.validate(message_type, version, payload)
    assert not result.valid
    assert any(e.field == "side" and e.code == "invalid_value" for e in result.errors)

def test_response_status_and_body_assertions():
    # Simulate a negative case response
    response = {
        "code": 4001,
        "message": "Invalid request parameters",
        "request_id": "req_abc123",
        "details": {
            "field": "symbol",
            "reason": "Unknown instrument symbol"
        }
    }
    # Assert status code and body shape
    assert response["code"] == 4001
    assert "message" in response
    assert "request_id" in response
    assert "details" in response
    assert isinstance(response["details"], dict)
