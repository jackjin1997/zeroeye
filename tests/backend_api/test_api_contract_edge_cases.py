import pytest
import asyncio
from backend.api_contract import (
    load_openapi_spec,
    iter_operations,
    MockBackendApiClient,
    build_valid_payload,
)

@pytest.fixture
def spec():
    return load_openapi_spec()

@pytest.fixture
def operations(spec):
    return iter_operations(spec)

@pytest.fixture
def client(spec, operations):
    return MockBackendApiClient(spec, operations)

def test_missing_required_fields_contract_error(spec, operations, client):
    op = next(op for op in operations if op.request_body_required)
    
    response = client.request(op.method, op.path, payload={}, token="valid-token")
    
    assert response.status_code >= 400
    assert response.status_code in (422, 400, 409) or response.status_code in op.error_statuses
    
    assert "code" in response.body
    assert "message" in response.body
    assert response.body["message"] == "Invalid request parameters"

def test_malformed_payload_force_internal_error(spec, operations, client):
    op = next(op for op in operations if op.request_body_required)
    
    response = client.request(op.method, op.path, payload={"__force_internal_error__": True}, token="valid-token")
    
    assert response.status_code == 500
    assert "code" in response.body
    assert "message" in response.body
    assert response.body["message"] == "Internal server error"

def test_async_helper_execution(spec, operations, client):
    op = next(op for op in operations if not op.path.startswith("/auth/"))
    valid_payload = build_valid_payload(spec, op) if op.request_body_required else {}
    
    async def run_async():
        return await client.request_async(op.method, op.path, payload=valid_payload, token="valid-token")
        
    response = asyncio.run(run_async())
    
    assert 200 <= response.status_code < 300
    assert response.body.get("ok") is True

def test_unauthenticated_request_returns_error(spec, operations, client):
    op = next(op for op in operations if not op.path.startswith("/auth/"))
    
    response = client.request(op.method, op.path, payload={}, token=None)
    
    assert response.status_code in (401, 403, 400)
    assert response.body["code"] == 4002
    assert response.body["message"] == "Authentication required"

