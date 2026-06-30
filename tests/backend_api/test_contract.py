"""
Tests for the backend API contract validation layer.

Covers:
  - Happy-path validation (a valid payload passes cleanly)
  - Malformed / missing required fields → ContractError
  - Async wrapper (smoke test, no optional plugins)
  - Response shape assertions (success_response, error_response)
  - Edge cases: empty payload, wrong types, extra fields, nullable, choices

Run with:
    python3 -m pytest tests/backend_api -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

# Ensure the repo root is on sys.path so we can import backend
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from backend.api_contract import (
    ContractError,
    async_validate,
    error_response,
    make_response,
    merge_contracts,
    success_response,
    validate_payload,
)

# ---------------------------------------------------------------------------
# Shared schema used across several tests
# ---------------------------------------------------------------------------

_USER_SCHEMA = {
    "user_id":   {"required": True,  "type": str, "min_len": 1, "max_len": 64},
    "email":     {"required": True,  "type": str, "pattern": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")},
    "age":       {"required": False, "type": int, "min": 0, "max": 150},
    "role":      {"required": False, "type": str, "choices": ["admin", "user", "guest"]},
    "nickname":  {"required": False, "type": str, "nullable": True},
    "tags":      {"required": False, "type": list, "max_len": 10},
}

# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:
    """A clean, well-formed payload should pass without raising."""

    def test_minimal_valid_payload(self):
        payload = {"user_id": "neo", "email": "neo@example.com"}
        result = validate_payload(payload, _USER_SCHEMA)
        assert result == payload

    def test_full_valid_payload(self):
        payload = {
            "user_id": "neo007",
            "email":   "neo007@matrix.io",
            "age":     30,
            "role":    "admin",
            "tags":    ["rust", "python"],
        }
        result = validate_payload(payload, _USER_SCHEMA)
        assert result == payload

    def test_nullable_field_omitted(self):
        payload = {"user_id": "a", "email": "a@b.co"}
        result = validate_payload(payload, _USER_SCHEMA)
        assert "nickname" not in result  # was never sent

    def test_nullable_field_explicit_null(self):
        payload = {"user_id": "b", "email": "b@b.co", "nickname": None}
        result = validate_payload(payload, _USER_SCHEMA)
        assert result["nickname"] is None


# ---------------------------------------------------------------------------
# 2. Malformed / missing required fields
# ---------------------------------------------------------------------------

class TestMissingRequired:
    """Missing or None for a required field must raise ContractError."""

    def test_missing_required(self):
        with pytest.raises(ContractError) as exc:
            validate_payload({"email": "a@b.co"}, _USER_SCHEMA)
        assert "user_id" in exc.value.fields

    def test_none_required(self):
        with pytest.raises(ContractError):
            validate_payload({"user_id": None, "email": "a@b.co"}, _USER_SCHEMA)


class TestTypeViolations:
    """Wrong types for fields must raise."""

    def test_string_as_int(self):
        with pytest.raises(ContractError) as exc:
            validate_payload({"user_id": 42, "email": "x@y.z"}, _USER_SCHEMA)
        assert "user_id" in exc.value.fields
        assert "int" in exc.value.fields["user_id"]  # got int, expected str

    def test_list_as_string(self):
        with pytest.raises(ContractError):
            validate_payload({"user_id": "x", "email": ["not", "a", "string"]}, _USER_SCHEMA)


class TestStringConstraints:
    """Min/max length and pattern checks on strings."""

    def test_string_too_short(self):
        with pytest.raises(ContractError) as exc:
            validate_payload({"user_id": "", "email": "a@b.co"}, _USER_SCHEMA)
        assert "user_id" in exc.value.fields

    def test_string_too_long(self):
        with pytest.raises(ContractError) as exc:
            validate_payload({"user_id": "x" * 65, "email": "a@b.co"}, _USER_SCHEMA)
        assert "user_id" in exc.value.fields

    def test_email_pattern_fail(self):
        with pytest.raises(ContractError) as exc:
            validate_payload({"user_id": "x", "email": "not-an-email"}, _USER_SCHEMA)
        assert "email" in exc.value.fields

    def test_email_pattern_pass(self):
        payload = {"user_id": "x", "email": "yolo@test.cn"}
        assert validate_payload(payload, _USER_SCHEMA) == payload


class TestChoices:
    """Choices constraint rejects invalid values."""

    def test_valid_choice(self):
        payload = {"user_id": "x", "email": "x@y.z", "role": "guest"}
        assert validate_payload(payload, _USER_SCHEMA) == payload

    def test_invalid_choice(self):
        with pytest.raises(ContractError) as exc:
            validate_payload({"user_id": "x", "email": "x@y.z", "role": "superadmin"}, _USER_SCHEMA)
        assert "role" in exc.value.fields


class TestNumericConstraints:
    """Min/max numeric bounds."""

    def test_age_below_min(self):
        with pytest.raises(ContractError):
            validate_payload({"user_id": "x", "email": "x@y.z", "age": -1}, _USER_SCHEMA)

    def test_age_above_max(self):
        with pytest.raises(ContractError):
            validate_payload({"user_id": "x", "email": "x@y.z", "age": 999}, _USER_SCHEMA)

    def test_age_boundary_valid(self):
        payload = {"user_id": "x", "email": "x@y.z", "age": 0}
        assert validate_payload(payload, _USER_SCHEMA)["age"] == 0


class TestListConstraints:
    """Max-length on lists."""

    def test_list_exceeds_max(self):
        with pytest.raises(ContractError):
            validate_payload(
                {"user_id": "x", "email": "x@y.z", "tags": list(range(11))},
                _USER_SCHEMA,
            )

    def test_list_at_max(self):
        payload = {"user_id": "x", "email": "x@y.z", "tags": list(range(10))}
        assert validate_payload(payload, _USER_SCHEMA)["tags"] == list(range(10))


# ---------------------------------------------------------------------------
# 3. Extra fields
# ---------------------------------------------------------------------------

class TestExtraFields:
    """Unknown fields are rejected by default; allow_extra=True skips them."""

    def test_extra_fields_rejected(self):
        with pytest.raises(ContractError) as exc:
            validate_payload(
                {"user_id": "x", "email": "x@y.z", "wtf_key": "boom"},
                _USER_SCHEMA,
            )
        assert "wtf_key" in exc.value.fields

    def test_extra_fields_allowed(self):
        payload = {"user_id": "x", "email": "x@y.z", "wtf_key": "ok"}
        result = validate_payload(payload, _USER_SCHEMA, allow_extra=True)
        assert result["wtf_key"] == "ok"


# ---------------------------------------------------------------------------
# 4. ContractError structure
# ---------------------------------------------------------------------------

class TestContractErrorShape:
    """ContractError should expose structured error data."""

    def test_to_dict(self):
        err = ContractError("bad field", code="X", fields={"x": "nope"})
        d = err.to_dict()
        assert d["error"] == "X"
        assert d["message"] == "bad field"
        assert d["fields"] == {"x": "nope"}

    def test_to_response_400(self):
        err = ContractError("nope", fields={"x": "bad"})
        resp = err.to_response(422)
        assert resp["status"] == 422
        assert resp["body"]["error"] == "CONTRACT_VIOLATION"


# ---------------------------------------------------------------------------
# 5. Response helpers
# ---------------------------------------------------------------------------

class TestResponseHelpers:
    """make_response / success_response / error_response shape."""

    def test_make_response_minimal(self):
        r = make_response(200, "ok")
        assert r == {"status": 200, "message": "ok"}

    def test_make_response_with_data(self):
        r = make_response(200, "created", data={"id": "abc"})
        assert r["data"] == {"id": "abc"}

    def test_success_response(self):
        r = success_response(data=[1, 2, 3])
        assert r["status"] == 200
        assert r["data"] == [1, 2, 3]

    def test_error_response(self):
        r = error_response(500, "internal error", details="OOM")
        assert r["status"] == 500
        assert r["data"]["error"] == "OOM"


# ---------------------------------------------------------------------------
# 6. Async wrapper
# ---------------------------------------------------------------------------

class TestAsyncWrapper:
    """async_validate should behave identically to validate_payload."""

    @pytest.mark.asyncio
    async def test_async_valid_payload(self):
        result = await async_validate(
            {"user_id": "neo", "email": "n@n.co"},
            _USER_SCHEMA,
        )
        assert result["user_id"] == "neo"

    @pytest.mark.asyncio
    async def test_async_invalid_payload(self):
        with pytest.raises(ContractError):
            await async_validate(
                {"user_id": "", "email": "n@n.co"},
                _USER_SCHEMA,
            )


# ---------------------------------------------------------------------------
# 7. Empty / edge payloads
# ---------------------------------------------------------------------------

class TestEdgePayloads:
    """Behaviour with empty or weird inputs."""

    def test_empty_dict_no_schema(self):
        # No required fields → empty payload is fine
        result = validate_payload({}, {})
        assert result == {}

    def test_empty_dict_with_required(self):
        with pytest.raises(ContractError):
            validate_payload({}, {"name": {"required": True, "type": str}})

    def test_non_dict_payload(self):
        with pytest.raises(ContractError) as exc:
            validate_payload("hello", {})
        assert "JSON object" in str(exc.value)

    def test_none_payload(self):
        with pytest.raises(ContractError):
            validate_payload(None, {})


# ---------------------------------------------------------------------------
# 8. merge_contracts
# ---------------------------------------------------------------------------

class TestMergeContracts:
    """merge_contracts should combine schema dicts, later wins."""

    def test_merge_disjoint(self):
        a = {"x": {"required": True}}
        b = {"y": {"required": False}}
        assert merge_contracts(a, b) == {"x": {"required": True}, "y": {"required": False}}

    def test_merge_overwrite(self):
        a = {"x": {"required": True, "type": str}}
        b = {"x": {"required": False, "type": int}}
        merged = merge_contracts(a, b)
        assert merged["x"]["required"] is False
        assert merged["x"]["type"] is int
