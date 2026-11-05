"""
Backend API contract helpers.

Provides typed request/response wrappers, structured error objects,
and validation utilities used by backend API handlers.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, TypeVar, Generic, Callable, Awaitable
from enum import Enum


class ContractErrorCode(str, Enum):
    INVALID_PAYLOAD = "INVALID_PAYLOAD"
    MISSING_FIELD = "MISSING_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    VALUE_OUT_OF_RANGE = "VALUE_OUT_OF_RANGE"
    ASYNC_ERROR = "ASYNC_ERROR"
    INTERNAL = "INTERNAL"


@dataclass
class ContractError:
    """Structured contract error returned to callers."""
    code: ContractErrorCode
    message: str
    field: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": True,
            "code": self.code.value,
            "message": self.message,
            "field": self.field,
            "details": self.details,
        }


T = TypeVar("T")


@dataclass
class ContractResult(Generic[T]):
    """Result wrapper — either value or error, never both."""
    value: Optional[T] = None
    error: Optional[ContractError] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        if self.ok:
            return {"error": False, "value": self.value}
        return self.error.to_dict()


def validate_required(payload: Dict[str, Any], required: List[str]) -> Optional[ContractError]:
    """Validate that all required fields are present and not None."""
    if not isinstance(payload, dict):
        return ContractError(
            code=ContractErrorCode.INVALID_PAYLOAD,
            message="Payload must be a JSON object",
        )
    for field_name in required:
        if field_name not in payload or payload[field_name] is None:
            return ContractError(
                code=ContractErrorCode.MISSING_FIELD,
                message=f"Missing required field: {field_name}",
                field=field_name,
            )
    return None


def validate_types(payload: Dict[str, Any], type_map: Dict[str, type]) -> List[ContractError]:
    """Validate field types. Returns list of errors (empty = all OK)."""
    errors: List[ContractError] = []
    for field_name, expected_type in type_map.items():
        if field_name not in payload or payload[field_name] is None:
            continue
        value = payload[field_name]
        # Handle bool vs int quirk in Python
        if expected_type is int and isinstance(value, bool):
            errors.append(ContractError(
                code=ContractErrorCode.TYPE_MISMATCH,
                message=f"Field '{field_name}' expected int, got bool",
                field=field_name,
            ))
            continue
        if not isinstance(value, expected_type):
            errors.append(ContractError(
                code=ContractErrorCode.TYPE_MISMATCH,
                message=f"Field '{field_name}' expected {expected_type.__name__}, got {type(value).__name__}",
                field=field_name,
            ))
    return errors


def validate_range(payload: Dict[str, Any], ranges: Dict[str, tuple]) -> List[ContractError]:
    """Validate numeric field ranges. ranges = {field: (min, max)}."""
    errors: List[ContractError] = []
    for field_name, (lo, hi) in ranges.items():
        if field_name not in payload or payload[field_name] is None:
            continue
        val = payload[field_name]
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            errors.append(ContractError(
                code=ContractErrorCode.TYPE_MISMATCH,
                message=f"Field '{field_name}' must be numeric for range check",
                field=field_name,
            ))
            continue
        if val < lo or val > hi:
            errors.append(ContractError(
                code=ContractErrorCode.VALUE_OUT_OF_RANGE,
                message=f"Field '{field_name}' must be between {lo} and {hi}",
                field=field_name,
                details={"min": lo, "max": hi, "actual": val},
            ))
    return errors


def build_result(payload: Optional[Dict[str, Any]],
                 required: Optional[List[str]] = None,
                 type_map: Optional[Dict[str, type]] = None,
                 ranges: Optional[Dict[str, tuple]] = None) -> ContractResult[Dict[str, Any]]:
    """Full validation pipeline — returns ContractResult."""
    if payload is None:
        return ContractResult(error=ContractError(
            code=ContractErrorCode.INVALID_PAYLOAD, message="Payload is None"))
    if required:
        err = validate_required(payload, required)
        if err:
            return ContractResult(error=err)
    if type_map:
        for err in validate_types(payload, type_map):
            return ContractResult(error=err)
    if ranges:
        for err in validate_range(payload, ranges):
            return ContractResult(error=err)
    return ContractResult(value=payload)


async def async_call(fn: Callable[..., Awaitable[Any]], *args, **kwargs) -> ContractResult[Any]:
    """Safe async wrapper — catches exceptions as ContractError."""
    try:
        result = await fn(*args, **kwargs)
        return ContractResult(value=result)
    except ContractError as ce:
        return ContractResult(error=ce)
    except Exception as e:
        return ContractResult(error=ContractError(
            code=ContractErrorCode.ASYNC_ERROR,
            message=f"Async call failed: {e}",
            details={"exception_type": type(e).__name__},
        ))


def sync_call(fn: Callable[..., Any], *args, **kwargs) -> ContractResult[Any]:
    """Safe sync wrapper — catches exceptions as ContractError."""
    try:
        result = fn(*args, **kwargs)
        return ContractResult(value=result)
    except ContractError as ce:
        return ContractResult(error=ce)
    except Exception as e:
        return ContractResult(error=ContractError(
            code=ContractErrorCode.INTERNAL,
            message=f"Sync call failed: {e}",
            details={"exception_type": type(e).__name__},
        ))
