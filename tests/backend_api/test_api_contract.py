"""Edge-case tests for backend API contract validation.

Covers:
  - Malformed / missing required fields returning structured contract errors
  - Boundary conditions on numeric and string fields
  - Response status/body assertions for negative cases
  - Async helper execution (no optional pytest plugins required)
  - Envelope and frame validation edge cases
  - RPC error code contracts

Run:
    python3 -m pytest -q tests/backend_api
"""

from __future__ import annotations

import asyncio
import math
import sys
from typing import Any, Dict

import pytest

# Ensure backend package is importable when run from repo root.
sys.path.insert(0, ".")

from backend.api_contract import (
    MessageEnvelope,
    ValidationResult,
    PROTOCOL_VERSION,
    MIN_COMPATIBLE_VERSION,
    MAX_MESSAGE_SIZE,
    FRAME_MAX_PAYLOAD_SIZE,
    VALID_SIDES,
    VALID_ORDER_TYPES,
    VALID_TIME_IN_FORCE,
    VALID_CURRENCIES,
    RPC_ERROR_CODES,
    validate_account_payload,
    validate_email,
    validate_enum,
    validate_hex_string,
    validate_instrument_id,
    validate_numeric_range,
    validate_order_payload,
    validate_pattern,
    validate_phone,
    validate_price,
    validate_quantity,
    validate_required,
    validate_string_length,
    validate_symbol,
    validate_timestamp,
    validate_uuid,
)


# ===================================================================
# 1.  Required-field edge cases
# ===================================================================

class TestRequiredFields:
    """Every required field that is missing must produce a structured error."""

    @pytest.mark.parametrize("field_name", ["side", "type", "quantity"])
    def test_order_missing_single_required_field(self, valid_order_payload, field_name):
        payload = {k: v for k, v in valid_order_payload.items() if k != field_name}
        result = validate_order_payload(payload)
        assert not result.valid
        codes = result.error_codes()
        assert "required" in codes
        assert any(e.field == field_name for e in result.errors)

    def test_order_completely_empty_payload(self):
        result = validate_order_payload({})
        assert not result.valid
        assert len(result.errors) >= 3  # side, type, quantity

    def test_order_none_values_treated_as_missing(self):
        payload = {"side": None, "type": None, "quantity": None}
        result = validate_order_payload(payload)
        assert not result.valid


# ===================================================================
# 2.  Invalid enum / side / type edge cases
# ===================================================================

class TestInvalidEnums:
    """Invalid enum values must produce a structured error with code invalid_*."""

    def test_invalid_side(self):
        result = validate_order_payload({
            "side": "long",
            "type": "limit",
            "quantity": 1,
            "price": 100,
        })
        assert not result.valid
        assert "invalid_side" in result.error_codes()

    @pytest.mark.parametrize("bad_type", ["stoploss", "trailing", "", "MARKET"])
    def test_invalid_order_type(self, bad_type):
        result = validate_order_payload({
            "side": "buy",
            "type": bad_type,
            "quantity": 1,
            "price": 100,
        })
        assert not result.valid
        assert "invalid_type" in result.error_codes()

    def test_invalid_time_in_force(self):
        result = validate_order_payload({
            "side": "buy",
            "type": "limit",
            "quantity": 1,
            "price": 100,
            "time_in_force": "expires_now",
        })
        assert not result.valid
        assert "invalid_tif" in result.error_codes()

    def test_invalid_currency(self):
        result = validate_account_payload({
            "amount": 100,
            "currency": "DOGE",
        })
        assert not result.valid
        assert "invalid_currency" in result.error_codes()


# ===================================================================
# 3.  Numeric boundary conditions
# ===================================================================

class TestNumericBoundaries:
    """Quantity and price boundary conditions."""

    @pytest.mark.parametrize("qty,expected_valid", [
        (0, False),
        (-1, False),
        (0.0001, True),
        (1, True),
        (999_999, True),
        (1_000_000, True),     # boundary: exactly at max (Rust uses >)
        (1_000_001, False),
        (float("inf"), False),
        (float("nan"), False),
    ])
    def test_quantity_boundaries(self, qty, expected_valid):
        payload = {"side": "buy", "type": "limit", "quantity": qty, "price": 10}
        result = validate_order_payload(payload)
        assert result.valid is expected_valid

    @pytest.mark.parametrize("price,expected_valid", [
        (-1, False),
        (0, False),
        (0.01, True),
        (999_999.99, True),
    ])
    def test_price_boundaries(self, price, expected_valid):
        payload = {"side": "buy", "type": "limit", "quantity": 1, "price": price}
        result = validate_order_payload(payload)
        assert result.valid is expected_valid

    def test_price_not_required_for_market_orders(self):
        payload = {"side": "buy", "type": "market", "quantity": 1}
        result = validate_order_payload(payload)
        assert result.valid

    def test_price_required_for_limit_orders(self):
        payload = {"side": "buy", "type": "limit", "quantity": 1}
        result = validate_order_payload(payload)
        assert not result.valid
        assert "price" in [e.field for e in result.errors]

    def test_price_required_for_stop_orders(self):
        for ot in ("stop", "stop_limit"):
            payload = {"side": "buy", "type": ot, "quantity": 1}
            result = validate_order_payload(payload)
            assert not result.valid

    def test_account_amount_boundary_zero(self):
        result = validate_account_payload({"amount": 0, "currency": "USD"})
        assert not result.valid
        assert "invalid_amount" in result.error_codes()

    def test_account_amount_boundary_over_max(self):
        result = validate_account_payload({"amount": 1_000_000_001, "currency": "USD"})
        assert not result.valid
        assert "max_exceeded" in result.error_codes()


# ===================================================================
# 4.  String / pattern validation edge cases
# ===================================================================

class TestStringValidation:
    """Edge cases for string validators."""

    @pytest.mark.parametrize("val,ok", [
        ("ab", True),
        ("a", False),
        ("", False),
        ("x" * 10, True),
        ("x" * 11, False),
    ])
    def test_string_length(self, val, ok):
        result = validate_string_length(val, "name", min_len=2, max_len=10)
        assert result.valid is ok

    def test_validate_required_none(self):
        result = validate_required(None, "field")
        assert not result.valid
        assert result.errors[0].code == "required"

    def test_validate_required_non_none(self):
        result = validate_required("value", "field")
        assert result.valid

    def test_validate_required_false_is_valid(self):
        result = validate_required(False, "flag")
        assert result.valid

    def test_validate_required_zero_is_valid(self):
        result = validate_required(0, "count")
        assert result.valid

    def test_validate_required_empty_string_is_valid(self):
        result = validate_required("", "name")
        assert result.valid

    def test_email_valid(self):
        assert validate_email("user@example.com").valid

    @pytest.mark.parametrize("bad_email", [
        "plain",
        "@example.com",
        "user@",
        "user@.com",
        "",
        "user @example.com",
    ])
    def test_email_invalid(self, bad_email):
        assert not validate_email(bad_email).valid

    def test_uuid_valid(self):
        assert validate_uuid("550e8400-e29b-41d4-a716-446655440000").valid

    @pytest.mark.parametrize("bad_uuid", [
        "550e8400-e29b-41d4-a716",
        "not-a-uuid",
        "550E8400-E29B-41D4-A716-446655440000",  # uppercase
        "",
    ])
    def test_uuid_invalid(self, bad_uuid):
        assert not validate_uuid(bad_uuid).valid

    def test_phone_valid(self):
        assert validate_phone("+1-555-123-4567").valid

    def test_phone_too_short(self):
        assert not validate_phone("123").valid

    def test_phone_too_long(self):
        assert not validate_phone("1" * 16).valid

    def test_hex_string_valid(self):
        assert validate_hex_string("abcd1234", "hash", expected_len=4).valid

    def test_hex_string_wrong_length(self):
        assert not validate_hex_string("abc", "hash", expected_len=4).valid

    def test_hex_string_non_hex_chars(self):
        assert not validate_hex_string("xyzg0000", "hash", expected_len=4).valid

    @pytest.mark.parametrize("ts,ok", [
        (946684800000, True),       # 2000-01-01
        (4102444800000, True),      # 2100-01-01
        (946684799999, False),      # just before
        (4102444800001, False),     # just after
        (0, False),
        (-1, False),
    ])
    def test_timestamp_boundaries(self, ts, ok):
        assert validate_timestamp(ts).valid is ok

    def test_symbol_valid(self):
        assert validate_symbol("BTC/USD").valid

    @pytest.mark.parametrize("sym", [
        "BTCUSD",
        "B/USD",
        "btc/usd",
        "",
        "A/BBBBBBBBBBB",  # too long base
    ])
    def test_symbol_invalid(self, sym):
        assert not validate_symbol(sym).valid

    def test_instrument_id_valid(self):
        assert validate_instrument_id("btcusdt").valid

    @pytest.mark.parametrize("iid", [
        "a",
        "A",
        "btc-usdt",
        "",
        "a" * 21,
    ])
    def test_instrument_id_invalid(self, iid):
        assert not validate_instrument_id(iid).valid


# ===================================================================
# 5.  Generic numeric range validator
# ===================================================================

class TestNumericRangeValidator:
    def test_within_range(self):
        result = validate_numeric_range(5.0, "x", min_val=0, max_val=10)
        assert result.valid

    def test_below_min(self):
        result = validate_numeric_range(-1.0, "x", min_val=0, max_val=10)
        assert not result.valid
        assert "min_value" in result.error_codes()

    def test_above_max(self):
        result = validate_numeric_range(11.0, "x", min_val=0, max_val=10)
        assert not result.valid
        assert "max_value" in result.error_codes()

    def test_no_bounds(self):
        result = validate_numeric_range(999.0, "x")
        assert result.valid

    def test_nan_value(self):
        result = validate_numeric_range(float("nan"), "x", min_val=0, max_val=10)
        # NaN comparisons are False, so it should fail min check
        assert not result.valid


# ===================================================================
# 6.  Enum validator
# ===================================================================

class TestEnumValidator:
    def test_valid_value(self):
        result = validate_enum("buy", "side", VALID_SIDES)
        assert result.valid

    def test_invalid_value(self):
        result = validate_enum("long", "side", VALID_SIDES)
        assert not result.valid
        assert result.errors[0].code == "invalid_value"

    def test_empty_variants(self):
        result = validate_enum("anything", "f", [])
        assert not result.valid

    def test_case_sensitive(self):
        result = validate_enum("Buy", "side", VALID_SIDES)
        assert not result.valid


# ===================================================================
# 7.  Message envelope edge cases
# ===================================================================

class TestMessageEnvelope:
    def test_valid_envelope(self, valid_envelope):
        result = valid_envelope.validate()
        assert result.valid

    def test_schema_version_too_low(self, valid_envelope):
        valid_envelope.schema_version = MIN_COMPATIBLE_VERSION - 1
        result = valid_envelope.validate()
        assert not result.valid
        assert "unsupported_version" in result.error_codes()

    def test_schema_version_too_high(self, valid_envelope):
        valid_envelope.schema_version = PROTOCOL_VERSION + 1
        result = valid_envelope.validate()
        assert not result.valid

    def test_payload_too_large(self, valid_envelope):
        valid_envelope.payload = b"x" * (MAX_MESSAGE_SIZE + 1)
        result = valid_envelope.validate()
        assert not result.valid
        assert "message_too_large" in result.error_codes()

    def test_priority_overflow(self, valid_envelope):
        valid_envelope.priority = 256
        result = valid_envelope.validate()
        assert not result.valid
        assert "invalid_priority" in result.error_codes()

    def test_flags_overflow(self, valid_envelope):
        valid_envelope.flags = 0x10000
        result = valid_envelope.validate()
        assert not result.valid
        assert "invalid_flags" in result.error_codes()

    def test_unknown_message_id_produces_warning(self, minimal_envelope):
        minimal_envelope.message_id = 0x0099
        result = minimal_envelope.validate()
        assert result.has_warnings()

    def test_known_market_message_id_no_warning(self, minimal_envelope):
        minimal_envelope.message_id = 0x1001
        result = minimal_envelope.validate()
        assert not result.has_warnings()

    def test_boundary_schema_version_min(self):
        env = MessageEnvelope(
            message_id=0x5001,
            message_type=0x01,
            schema_version=MIN_COMPATIBLE_VERSION,
        )
        assert env.validate().valid

    def test_boundary_schema_version_max(self):
        env = MessageEnvelope(
            message_id=0x5001,
            message_type=0x01,
            schema_version=PROTOCOL_VERSION,
        )
        assert env.validate().valid


# ===================================================================
# 8.  Frame validation edge cases
# ===================================================================

class TestFrame:
    def test_valid_frame(self):
        from backend.api_contract import Frame
        f = Frame(version=PROTOCOL_VERSION, payload=b"hello")
        assert f.is_valid()

    def test_version_too_low(self):
        from backend.api_contract import Frame
        f = Frame(version=MIN_COMPATIBLE_VERSION - 1)
        assert not f.is_valid()

    def test_version_too_high(self):
        from backend.api_contract import Frame
        f = Frame(version=PROTOCOL_VERSION + 1)
        assert not f.is_valid()

    def test_payload_too_large(self):
        from backend.api_contract import Frame
        f = Frame(payload=b"x" * (FRAME_MAX_PAYLOAD_SIZE + 1))
        assert not f.is_valid()

    def test_total_size_without_checksum(self):
        from backend.api_contract import Frame, FRAME_HEADER_SIZE
        f = Frame(payload=b"abc")
        assert f.total_size() == FRAME_HEADER_SIZE + 3

    def test_total_size_with_checksum(self):
        from backend.api_contract import Frame, FRAME_HEADER_SIZE
        f = Frame(payload=b"abc", checksum=0xDEADBEEF)
        assert f.total_size() == FRAME_HEADER_SIZE + 3 + 4


# ===================================================================
# 9.  RPC error code contract
# ===================================================================

class TestRpcErrorCodes:
    def test_all_codes_are_non_negative(self):
        for code in RPC_ERROR_CODES:
            assert code >= 0

    def test_error_code_0_is_ok(self):
        assert RPC_ERROR_CODES[0] == "Ok"

    def test_method_not_found_exists(self):
        assert 1 in RPC_ERROR_CODES
        assert RPC_ERROR_CODES[1] == "MethodNotFound"

    def test_serialization_error_exists(self):
        assert 10 in RPC_ERROR_CODES

    def test_error_codes_are_unique(self):
        values = list(RPC_ERROR_CODES.values())
        assert len(values) == len(set(values))


# ===================================================================
# 10.  Pattern validator edge cases
# ===================================================================

class TestPatternValidator:
    def test_matching_pattern(self):
        result = validate_pattern("abc123", "f", r"^[a-z0-9]+$")
        assert result.valid

    def test_non_matching_pattern(self):
        result = validate_pattern("ABC!", "f", r"^[a-z0-9]+$")
        assert not result.valid
        assert "pattern_mismatch" in result.error_codes()

    def test_empty_string_matches_empty_pattern(self):
        result = validate_pattern("", "f", r"^$")
        assert result.valid

    def test_regex_injection_safe(self):
        # Malicious pattern should not crash (re.search handles it)
        result = validate_pattern("aabc", "f", r"(?:a)+")
        assert result.valid


# ===================================================================
# 11.  Combine / multi-error aggregation
# ===================================================================

class TestResultCombination:
    def test_combine_two_errors(self):
        r1 = validate_order_payload({})
        r2 = validate_account_payload({})
        r1.combine(r2)
        assert not r1.valid
        assert len(r1.errors) >= 3  # 3 from order + 0 from account (amount/currency optional)

    def test_combine_valid_results(self):
        r1 = ValidationResult.ok()
        r2 = ValidationResult.ok()
        r1.combine(r2)
        assert r1.valid
        assert len(r1.errors) == 0

    def test_to_dict_shape(self):
        result = validate_order_payload({})
        d = result.to_dict()
        assert "valid" in d
        assert "errors" in d
        assert "warnings" in d
        assert isinstance(d["errors"], list)

    def test_error_to_dict_shape(self):
        result = validate_order_payload({"side": "x", "type": "y", "quantity": -1})
        for err in result.errors:
            d = err.to_dict()
            assert "field" in d
            assert "code" in d
            assert "message" in d
            assert "severity" in d


# ===================================================================
# 12.  Async helper execution (no optional plugins required)
# ===================================================================

class TestAsyncHelpers:
    """Verify async wrappers work without requiring pytest-asyncio."""

    def test_sync_validation_in_async_context(self):
        async def run():
            result = validate_order_payload({
                "side": "buy", "type": "limit", "quantity": 1, "price": 100,
            })
            return result

        result = asyncio.run(run())
        assert result.valid

    def test_async_combine_results(self):
        async def validate_all():
            r1 = validate_order_payload({
                "side": "buy", "type": "market", "quantity": 1,
            })
            r2 = validate_account_payload({"amount": 500, "currency": "EUR"})
            combined = ValidationResult.ok()
            combined.combine(r1)
            combined.combine(r2)
            return combined

        result = asyncio.run(validate_all())
        assert result.valid

    def test_async_error_propagation(self):
        async def failing_validation():
            return validate_order_payload({})

        result = asyncio.run(failing_validation())
        assert not result.valid
        assert len(result.errors) >= 3

    def test_concurrent_validations(self):
        async def concurrent():
            tasks = [
                validate_order_payload({"side": "buy", "type": "market", "quantity": i})
                for i in range(1, 6)
            ]
            return tasks

        results = asyncio.run(concurrent())
        assert all(r.valid for r in results)


# ===================================================================
# 13.  Multi-field compound errors
# ===================================================================

class TestCompoundErrors:
    """Payloads with multiple invalid fields must report all errors."""

    def test_multiple_invalid_fields_order(self):
        result = validate_order_payload({
            "side": "up",
            "type": "invalid",
            "quantity": -5,
            "price": -1,
            "time_in_force": "forever",
        })
        assert not result.valid
        codes = set(result.error_codes())
        assert "invalid_side" in codes
        assert "invalid_type" in codes
        assert "invalid_quantity" in codes
        assert "invalid_price" in codes
        assert "invalid_tif" in codes

    def test_multiple_invalid_fields_account(self):
        result = validate_account_payload({
            "amount": -100,
            "currency": "XYZ",
        })
        assert not result.valid
        codes = set(result.error_codes())
        assert "invalid_amount" in codes
        assert "invalid_currency" in codes


# ===================================================================
# 14.  Type coercion edge cases
# ===================================================================

class TestTypeCoercion:
    """Ensure validators handle unexpected types gracefully."""

    def test_quantity_as_string(self):
        result = validate_order_payload({
            "side": "buy", "type": "limit", "quantity": "ten", "price": 100,
        })
        assert not result.valid

    def test_price_as_string(self):
        result = validate_order_payload({
            "side": "buy", "type": "limit", "quantity": 1, "price": "high",
        })
        assert not result.valid

    def test_side_as_integer(self):
        result = validate_order_payload({
            "side": 1, "type": "limit", "quantity": 1, "price": 100,
        })
        assert not result.valid

    def test_amount_none(self):
        result = validate_account_payload({"currency": "USD"})
        assert result.valid  # amount is optional

    def test_currency_none(self):
        result = validate_account_payload({"amount": 100})
        assert result.valid  # currency is optional
