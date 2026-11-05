"""Edge-case tests for backend.api_contract.

Covers: malformed payloads, missing fields, type mismatches,
range violations, async wrapper error shape, response body structure.

Run: python3 -m pytest -q tests/backend_api/
"""
import asyncio
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.api_contract import (
    ContractError, ContractErrorCode, ContractResult,
    validate_required, validate_types, validate_range,
    build_result, async_call, sync_call,
)


# ============================================================
# FIXTURES — isolated, no network
# ============================================================

@pytest.fixture
def valid_payload():
    return {"name": "test", "count": 5, "active": True}


@pytest.fixture
def bad_async_fn():
    async def _bad():
        raise RuntimeError("boom")
    return _bad


@pytest.fixture
def ok_async_fn():
    async def _ok():
        await asyncio.sleep(0)  # yield to loop
        return {"status": "ok"}
    return _ok


@pytest.fixture
def raises_contract_error():
    async def _fn():
        raise ContractError(
            code=ContractErrorCode.MISSING_FIELD,
            message="nope",
            field="x",
        )
    return _fn


# ============================================================
# 1. MALFORMED / MISSING PAYLOAD — negative cases
# ============================================================

class TestMalformedPayload:
    def test_none_payload(self):
        r = build_result(None)
        assert not r.ok
        assert r.error.code == ContractErrorCode.INVALID_PAYLOAD

    def test_string_instead_of_dict(self):
        r = build_result("not a dict")
        assert not r.ok
        assert r.error.code == ContractErrorCode.INVALID_PAYLOAD

    def test_list_instead_of_dict(self):
        r = build_result([1, 2, 3])
        err = validate_required([1, 2, 3], ["a"])
        assert err is not None
        assert err.code == ContractErrorCode.INVALID_PAYLOAD

    def test_empty_dict_passes_no_required(self):
        r = build_result({})
        assert r.ok
        assert r.value == {}


# ============================================================
# 2. MISSING REQUIRED FIELDS
# ============================================================

class TestMissingFields:
    def test_single_missing(self, valid_payload):
        del valid_payload["name"]
        err = validate_required(valid_payload, ["name"])
        assert err is not None
        assert err.code == ContractErrorCode.MISSING_FIELD
        assert err.field == "name"

    def test_value_is_none_treated_as_missing(self):
        err = validate_required({"x": None}, ["x"])
        assert err is not None
        assert err.code == ContractErrorCode.MISSING_FIELD

    def test_multiple_required_first_reported(self):
        err = validate_required({}, ["a", "b", "c"])
        assert err is not None
        assert err.field == "a"

    def test_all_required_present(self, valid_payload):
        err = validate_required(valid_payload, ["name", "count"])
        assert err is None


# ============================================================
# 3. TYPE MISMATCH
# ============================================================

class TestTypeMismatch:
    def test_wrong_type_int_vs_str(self):
        errs = validate_types({"x": "abc"}, {"x": int})
        assert len(errs) == 1
        assert errs[0].code == ContractErrorCode.TYPE_MISMATCH
        assert errs[0].field == "x"

    def test_bool_treated_differently_from_int(self):
        # Python quirk: isinstance(True, int) is True — we explicitly guard
        errs = validate_types({"x": True}, {"x": int})
        assert len(errs) == 1, "bool should NOT pass int check"
        assert errs[0].field == "x"

    def test_missing_fields_skipped(self):
        errs = validate_types({}, {"x": int})
        assert errs == []

    def test_all_types_match(self):
        errs = validate_types({"a": 1, "b": "s"}, {"a": int, "b": str})
        assert errs == []


# ============================================================
# 4. RANGE VIOLATIONS
# ============================================================

class TestRangeViolations:
    def test_value_below_min(self):
        errs = validate_range({"x": -5}, {"x": (0, 100)})
        assert len(errs) == 1
        assert errs[0].code == ContractErrorCode.VALUE_OUT_OF_RANGE
        assert errs[0].details["min"] == 0
        assert errs[0].details["actual"] == -5

    def test_value_above_max(self):
        errs = validate_range({"x": 150}, {"x": (0, 100)})
        assert len(errs) == 1
        assert errs[0].details["max"] == 100

    def test_value_at_boundary_passes(self):
        errs = validate_range({"x": 0}, {"x": (0, 100)})
        assert errs == []
        errs = validate_range({"x": 100}, {"x": (0, 100)})
        assert errs == []

    def test_bool_rejected_for_range(self):
        errs = validate_range({"x": True}, {"x": (0, 100)})
        assert len(errs) == 1
        assert errs[0].code == ContractErrorCode.TYPE_MISMATCH


# ============================================================
# 5. ASYNC WRAPPER — no pytest-asyncio plugin required
# ============================================================

class TestAsyncWrapper:
    def test_async_ok(self, ok_async_fn):
        result = asyncio.run(async_call(ok_async_fn))
        assert result.ok
        assert result.value == {"status": "ok"}

    def test_async_exception_caught(self, bad_async_fn):
        result = asyncio.run(async_call(bad_async_fn))
        assert not result.ok
        assert result.error.code == ContractErrorCode.ASYNC_ERROR
        assert result.error.details["exception_type"] == "RuntimeError"

    def test_async_contract_error_passthrough(self, raises_contract_error):
        result = asyncio.run(async_call(raises_contract_error))
        assert not result.ok
        assert result.error.code == ContractErrorCode.MISSING_FIELD
        assert result.error.field == "x"

    def test_async_with_args_kwargs(self):
        async def add(a, b):
            return a + b
        result = asyncio.run(async_call(add, 3, b=4))
        assert result.ok
        assert result.value == 7


# ============================================================
# 6. SYNC WRAPPER
# ============================================================

class TestSyncWrapper:
    def test_sync_ok(self):
        result = sync_call(lambda: 42)
        assert result.ok
        assert result.value == 42

    def test_sync_exception_caught(self):
        def boom():
            raise ValueError("nope")
        result = sync_call(boom)
        assert not result.ok
        assert result.error.code == ContractErrorCode.INTERNAL
        assert result.error.details["exception_type"] == "ValueError"


# ============================================================
# 7. RESPONSE SHAPE — to_dict() contract
# ============================================================

class TestResponseShape:
    def test_ok_shape(self, valid_payload):
        r = build_result(valid_payload, required=["name"])
        d = r.to_dict()
        assert d["error"] is False
        assert "value" in d
        assert "code" not in d

    def test_error_shape(self):
        r = build_result(None)
        d = r.to_dict()
        assert d["error"] is True
        assert "code" in d
        assert "message" in d
        assert "field" in d

    def test_contract_error_to_dict_roundtrip(self):
        ce = ContractError(
            code=ContractErrorCode.MISSING_FIELD,
            message="lost", field="email",
            details={"hint": "check input"},
        )
        d = ce.to_dict()
        assert d["code"] == "MISSING_FIELD"
        assert d["field"] == "email"
        assert d["details"]["hint"] == "check input"
