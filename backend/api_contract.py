#!/usr/bin/env python3
"""
API contract helpers for the Tent of Trials backend.

Defines the schema / shape of API requests and responses so that client and
server speak the same language — and fail loudly when they don't.

Usage:
    from backend.api_contract import validate_payload, ContractError, make_response

    payload = {"action": "register", "user_id": "abc-123"}
    schema = {
        "action":   {"required": True,  "type": str},
        "user_id":  {"required": False, "type": str},
        "ttl_secs": {"required": False, "type": int},
    }

    result = validate_payload(payload, schema)          # raises on failure
    print(make_response(200, "ok", {"id": "evt-456"}))
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional, Tuple, Type, Union


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ContractError(Exception):
    """Raised when a payload violates the contract schema."""

    def __init__(self, message: str, code: str = "CONTRACT_VIOLATION",
                 fields: Optional[Dict[str, str]] = None) -> None:
        self.message = message
        self.code = code
        self.fields = fields or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error":   self.code,
            "message": self.message,
            "fields":  self.fields,
        }

    def to_response(self, status_code: int = 400) -> Dict[str, Any]:
        return {
            "status":  status_code,
            "body":    self.to_dict(),
        }


# ---------------------------------------------------------------------------
# Schema types
# ---------------------------------------------------------------------------

FieldSchema = Dict[str, Any]
# Keys understood by validate_payload:
#   required  – bool, default False
#   type      – Python type or tuple of types
#   min_len   – int (strings / lists)
#   max_len   – int (strings / lists)
#   pattern   – compiled regex (strings)
#   choices   – list of allowed values
#   nullable  – bool, default False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_payload(payload: Any, schema: Dict[str, FieldSchema],
                     allow_extra: bool = False) -> Dict[str, Any]:
    """Validate *payload* against *schema*.

    Parameters
    ----------
    payload : dict
        The incoming data to validate.
    schema : dict of str → dict
        Describes each field and its constraints.
    allow_extra : bool
        If False (default), unknown keys trigger an error.

    Returns
    -------
    dict
        *payload* unchanged on success.

    Raises
    ------
    ContractError
        On first violation with a descriptive message and field-level detail.
    """
    errors: Dict[str, str] = {}

    if not isinstance(payload, dict):
        raise ContractError(
            "Payload must be a JSON object (dict)",
            code="INVALID_PAYLOAD_TYPE",
            fields={"_root": f"Expected dict, got {type(payload).__name__}"},
        )

    # ── Check for extra keys ──────────────────────────────────────
    if not allow_extra:
        extra = set(payload) - set(schema)
        if extra:
            # Report the first one only to avoid noise
            key = next(iter(sorted(extra)))
            errors[key] = "Unknown field"

    # ── Validate each schema field ─────────────────────────────────
    for field, rules in schema.items():
        present = field in payload
        value = payload.get(field)

        # ----- required: must exist and have non-None value -----
        if rules.get("required"):
            if not present or value is None:
                errors[field] = "Field is required"
                continue

        # ----- skip optional fields that are absent -----
        if not present:
            continue

        # ----- nullable -----
        if value is None and rules.get("nullable", False):
            continue

        # ----- type -----
        expected_type: Union[Type, Tuple[Type, ...]] = rules.get("type", str)  # noqa: F821
        if isinstance(expected_type, type):
            expected_type = (expected_type,)

        # For union types like str | int (passed as tuple).
        # We also accept Optional[X] as (X, type(None)).
        if not isinstance(value, expected_type):
            type_names = " | ".join(t.__name__ for t in expected_type)
            errors[field] = f"Expected {type_names}, got {type(value).__name__}"
            continue

        # ----- string constraints -----
        if isinstance(value, str):
            if "min_len" in rules and len(value) < rules["min_len"]:
                errors[field] = f"Must be ≥ {rules['min_len']} characters"
                continue
            if "max_len" in rules and len(value) > rules["max_len"]:
                errors[field] = f"Must be ≤ {rules['max_len']} characters"
                continue
            if "pattern" in rules and not rules["pattern"].search(value):
                errors[field] = "Does not match required pattern"
                continue

        # ----- list constraints -----
        if isinstance(value, (list, tuple)):
            if "min_len" in rules and len(value) < rules["min_len"]:
                errors[field] = f"Must have ≥ {rules['min_len']} items"
                continue
            if "max_len" in rules and len(value) > rules["max_len"]:
                errors[field] = f"Must have ≤ {rules['max_len']} items"
                continue

        # ----- numeric constraints -----
        if isinstance(value, (int, float)):
            if "min" in rules and value < rules["min"]:
                errors[field] = f"Must be ≥ {rules['min']}"
                continue
            if "max" in rules and value > rules["max"]:
                errors[field] = f"Must be ≤ {rules['max']}"
                continue

        # ----- choices -----
        if "choices" in rules and value not in rules["choices"]:
            choices_str = ", ".join(repr(c) for c in rules["choices"])
            errors[field] = f"Must be one of: {choices_str}"
            continue

    if errors:
        first_field = next(iter(errors))
        raise ContractError(
            message=f"Validation failed on field '{first_field}': {errors[first_field]}",
            code="VALIDATION_ERROR",
            fields=errors,
        )

    return payload


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------

def make_response(status: int, message: str,
                  data: Optional[Any] = None,
                  meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build a standardised API response envelope."""
    body: Dict[str, Any] = {
        "status":  status,
        "message": message,
    }
    if data is not None:
        body["data"] = data
    if meta is not None:
        body["meta"] = meta
    return body


def success_response(data: Any = None, message: str = "ok",
                     meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Shorthand for a 200 response."""
    return make_response(200, message, data=data, meta=meta)


def error_response(status: int, message: str,
                   details: Optional[Any] = None) -> Dict[str, Any]:
    """Shorthand for an error response."""
    return make_response(status, message, data={"error": details} if details else None)


def merge_contracts(*schemas: Dict[str, FieldSchema]) -> Dict[str, FieldSchema]:
    """Merge multiple schema dicts (later fields override earlier ones)."""
    merged: Dict[str, FieldSchema] = {}
    for s in schemas:
        merged.update(s)
    return merged


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------

async def async_validate(payload: Any, schema: Dict[str, FieldSchema],
                         allow_extra: bool = False) -> Dict[str, Any]:
    """Async wrapper around *validate_payload* for use in async handlers."""
    return validate_payload(payload, schema, allow_extra=allow_extra)


# ---------------------------------------------------------------------------
# CLI smoke-test (only when run directly)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import doctest
    results = doctest.testmod()
    sys.exit(0 if results.failed == 0 else 1)
