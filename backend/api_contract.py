"""Backend API contract validation helpers.

Mirrors the Rust validation logic in backend/src/protocol/validate.rs and
backend/src/protocol/messages.rs so that edge-case behaviour can be
exercised with deterministic, network-free pytest cases.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# ---------------------------------------------------------------------------
# Constants (mirrored from Rust)
# ---------------------------------------------------------------------------

PROTOCOL_VERSION: int = 3
MIN_COMPATIBLE_VERSION: int = 2
MAX_MESSAGE_SIZE: int = 10 * 1024 * 1024
FRAME_MAX_PAYLOAD_SIZE: int = 16 * 1024 * 1024
DEFAULT_TIMEOUT_MS: int = 30_000

FRAME_MAGIC: int = 0x544F5446  # "TOTF"
FRAME_HEADER_SIZE: int = 24

VALID_SIDES: Tuple[str, ...] = ("buy", "sell")
VALID_ORDER_TYPES: Tuple[str, ...] = ("market", "limit", "stop", "stop_limit")
VALID_TIME_IN_FORCE: Tuple[str, ...] = ("gtc", "ioc", "fok", "day", "gtd")
VALID_CURRENCIES: Tuple[str, ...] = (
    "USD", "EUR", "GBP", "BTC", "ETH", "USDT", "USDC",
)

VALID_MESSAGE_ID_RANGES: Dict[str, Tuple[int, int]] = {
    "market": (0x1000, 0x1FFF),
    "order": (0x2000, 0x2FFF),
    "account": (0x3000, 0x3FFF),
    "user": (0x4000, 0x4FFF),
    "system": (0x5000, 0x5FFF),
    "admin": (0x6000, 0x6FFF),
    "custom": (0x7000, 0x7FFF),
}

# RPC method IDs (subset)
RPC_METHOD_IDS: Dict[int, str] = {
    0x0001: "GetInstruments",
    0x0002: "GetOrderBook",
    0x0003: "GetTicker",
    0x0010: "PlaceOrder",
    0x0011: "CancelOrder",
    0x0030: "GetAccount",
    0x0100: "Authenticate",
    0x1000: "HealthCheck",
}


# ---------------------------------------------------------------------------
# Validation severity
# ---------------------------------------------------------------------------

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Validation result types
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    field: str
    code: str
    message: str
    severity: Severity = Severity.ERROR

    def to_dict(self) -> Dict[str, str]:
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
        }


@dataclass
class ValidationResult:
    valid: bool = True
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # -- helpers -----------------------------------------------------------

    def add_error(self, fld: str, code: str, message: str) -> None:
        self.valid = False
        self.errors.append(
            ValidationError(field=fld, code=code, message=message)
        )

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def combine(self, other: "ValidationResult") -> None:
        self.valid = self.valid and other.valid
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def error_codes(self) -> List[str]:
        return [e.code for e in self.errors]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": self.warnings,
        }

    # -- factories ---------------------------------------------------------

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(valid=True)

    @classmethod
    def error(cls, fld: str, code: str, message: str) -> "ValidationResult":
        r = cls(valid=False)
        r.add_error(fld, code, message)
        return r


# ---------------------------------------------------------------------------
# Field validators
# ---------------------------------------------------------------------------

def validate_required(value: Any, field_name: str) -> ValidationResult:
    if value is None:
        return ValidationResult.error(field_name, "required", "Field is required")
    return ValidationResult.ok()


def validate_string_length(
    value: str,
    field_name: str,
    min_len: Optional[int] = None,
    max_len: Optional[int] = None,
) -> ValidationResult:
    result = ValidationResult.ok()
    length = len(value)
    if min_len is not None and length < min_len:
        result.add_error(field_name, "min_length", f"Must be at least {min_len} characters")
    if max_len is not None and length > max_len:
        result.add_error(field_name, "max_length", f"Must be at most {max_len} characters")
    return result


def validate_numeric_range(
    value: float,
    field_name: str,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
) -> ValidationResult:
    result = ValidationResult.ok()
    if math.isnan(value):
        result.add_error(field_name, "invalid_value", "Value must not be NaN")
        return result
    if math.isinf(value):
        result.add_error(field_name, "invalid_value", "Value must not be infinite")
        return result
    if min_val is not None and value < min_val:
        result.add_error(field_name, "min_value", f"Must be at least {min_val}")
    if max_val is not None and value > max_val:
        result.add_error(field_name, "max_value", f"Must be at most {max_val}")
    return result


def validate_pattern(value: str, field_name: str, pattern: str) -> ValidationResult:
    if re.search(pattern, value):
        return ValidationResult.ok()
    return ValidationResult.error(
        field_name, "pattern_mismatch",
        f"Does not match required pattern: {pattern}",
    )


def validate_enum(value: str, field_name: str, variants: Sequence[str]) -> ValidationResult:
    if value in variants:
        return ValidationResult.ok()
    return ValidationResult.error(
        field_name, "invalid_value",
        f"Must be one of: {list(variants)}",
    )


def validate_email(value: str, field_name: str = "email") -> ValidationResult:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\Z"
    return validate_pattern(value, field_name, pattern)


def validate_uuid(value: str, field_name: str = "id") -> ValidationResult:
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z"
    return validate_pattern(value, field_name, pattern)


def validate_phone(phone: str, field_name: str = "phone") -> ValidationResult:
    digits = "".join(c for c in phone if c.isdigit())
    if 10 <= len(digits) <= 15:
        return ValidationResult.ok()
    return ValidationResult.error(
        field_name, "invalid_phone",
        f"Phone must have 10-15 digits, got {len(digits)}",
    )


def validate_hex_string(value: str, field_name: str, expected_len: int) -> ValidationResult:
    if len(value) == expected_len * 2 and all(c in "0123456789abcdefABCDEF" for c in value):
        return ValidationResult.ok()
    return ValidationResult.error(
        field_name, "invalid_hex",
        f"Must be a hex string of length {expected_len * 2}",
    )


def validate_timestamp(ts: int, field_name: str = "timestamp") -> ValidationResult:
    if 946684800000 <= ts <= 4102444800000:
        return ValidationResult.ok()
    return ValidationResult.error(
        field_name, "invalid_timestamp",
        "Timestamp must be between 2000-01-01 and 2100-01-01 (epoch millis)",
    )


def validate_symbol(symbol: str, field_name: str = "symbol") -> ValidationResult:
    pattern = r"^[A-Z0-9]{2,10}/[A-Z0-9]{2,10}\Z"
    return validate_pattern(value=symbol, field_name=field_name, pattern=pattern)


def validate_instrument_id(instrument_id: str, field_name: str = "instrument_id") -> ValidationResult:
    pattern = r"^[a-z0-9]{2,20}\Z"
    return validate_pattern(value=instrument_id, field_name=field_name, pattern=pattern)


def validate_price(price: float, field_name: str = "price") -> ValidationResult:
    result = ValidationResult.ok()
    if price <= 0.0:
        result.add_error(field_name, "invalid_price", "Price must be positive")
    elif price >= 1_000_000_000.0:
        result.add_error(field_name, "max_exceeded", "Price exceeds maximum")
    return result


def validate_quantity(qty: float, field_name: str = "quantity") -> ValidationResult:
    result = ValidationResult.ok()
    if qty <= 0.0:
        result.add_error(field_name, "invalid_quantity", "Quantity must be positive")
    elif qty >= 100_000_000.0:
        result.add_error(field_name, "max_exceeded", "Quantity exceeds maximum")
    return result


# ---------------------------------------------------------------------------
# Message-level validators
# ---------------------------------------------------------------------------

def validate_order_payload(payload: Dict[str, Any]) -> ValidationResult:
    """Validate an order payload (mirrors validate_order_payload in Rust)."""
    result = ValidationResult.ok()

    # side
    side = payload.get("side")
    if side is None:
        result.add_error("side", "required", "Side is required")
    elif side not in VALID_SIDES:
        result.add_error("side", "invalid_side", f"Invalid side: {side}. Must be 'buy' or 'sell'")

    # type
    order_type = payload.get("type")
    if order_type is None:
        result.add_error("type", "required", "Order type is required")
    elif order_type not in VALID_ORDER_TYPES:
        result.add_error("type", "invalid_type", f"Invalid order type: {order_type}")

    # quantity
    qty = payload.get("quantity")
    if qty is None:
        result.add_error("quantity", "required", "Quantity is required")
    elif not isinstance(qty, (int, float)):
        result.add_error("quantity", "invalid_type", "Quantity must be numeric")
    elif math.isnan(qty) or math.isinf(qty):
        result.add_error("quantity", "invalid_quantity", "Quantity must be a finite number")
    elif qty <= 0.0:
        result.add_error("quantity", "invalid_quantity", "Quantity must be positive")
    elif qty > 1_000_000.0:
        result.add_error("quantity", "max_exceeded", "Quantity exceeds maximum allowed")

    # price (required for non-market orders)
    if order_type is not None and order_type != "market":
        price = payload.get("price")
        if price is None:
            result.add_error("price", "required", "Price is required for non-market orders")
        elif not isinstance(price, (int, float)):
            result.add_error("price", "invalid_type", "Price must be numeric")
        elif price <= 0.0:
            result.add_error("price", "invalid_price", "Price must be positive")

    # time_in_force (optional, defaults to gtc)
    tif = payload.get("time_in_force")
    if tif is not None and tif not in VALID_TIME_IN_FORCE:
        result.add_error(
            "time_in_force", "invalid_tif",
            f"Invalid time_in_force: {tif}. Must be one of {list(VALID_TIME_IN_FORCE)}",
        )

    return result


def validate_account_payload(payload: Dict[str, Any]) -> ValidationResult:
    """Validate an account payload (mirrors validate_account_payload in Rust)."""
    result = ValidationResult.ok()

    amount = payload.get("amount")
    if amount is not None:
        if not isinstance(amount, (int, float)):
            result.add_error("amount", "invalid_type", "Amount must be numeric")
        elif amount <= 0.0:
            result.add_error("amount", "invalid_amount", "Amount must be positive")
        elif amount > 1_000_000_000.0:
            result.add_error("amount", "max_exceeded", "Amount exceeds maximum")

    currency = payload.get("currency")
    if currency is not None and currency not in VALID_CURRENCIES:
        result.add_error(
            "currency", "invalid_currency",
            f"Unsupported currency: {currency}",
        )

    return result


# ---------------------------------------------------------------------------
# Message envelope helpers
# ---------------------------------------------------------------------------

@dataclass
class MessageEnvelope:
    message_id: int
    message_type: int
    schema_version: int
    correlation_id: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    timestamp: int = 0
    priority: int = 0
    flags: int = 0
    payload: bytes = b""
    checksum: Optional[int] = None

    def validate(self) -> ValidationResult:
        result = ValidationResult.ok()

        if self.schema_version < MIN_COMPATIBLE_VERSION or self.schema_version > PROTOCOL_VERSION:
            result.add_error(
                "schema_version", "unsupported_version",
                f"Schema version {self.schema_version} not in "
                f"[{MIN_COMPATIBLE_VERSION}, {PROTOCOL_VERSION}]",
            )

        if len(self.payload) > MAX_MESSAGE_SIZE:
            result.add_error(
                "payload", "message_too_large",
                f"Payload size {len(self.payload)} exceeds max {MAX_MESSAGE_SIZE}",
            )

        if self.priority > 255:
            result.add_error(
                "priority", "invalid_priority",
                f"Priority must be 0-255, got {self.priority}",
            )

        if self.flags > 0xFFFF:
            result.add_error(
                "flags", "invalid_flags",
                f"Flags must be 0-0xFFFF, got {self.flags}",
            )

        # Validate message_id is in a known range
        domain = _message_id_domain(self.message_id)
        if domain is None:
            result.add_warning(
                f"Message ID 0x{self.message_id:04X} is not in a known domain range",
            )

        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "message_type": self.message_type,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "flags": self.flags,
            "payload_size": len(self.payload),
            "has_checksum": self.checksum is not None,
        }


def _message_id_domain(message_id: int) -> Optional[str]:
    for domain, (lo, hi) in VALID_MESSAGE_ID_RANGES.items():
        if lo <= message_id <= hi:
            return domain
    return None


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------

@dataclass
class Frame:
    version: int = PROTOCOL_VERSION
    message_type: int = 0
    flags: int = 0
    payload: bytes = b""
    sequence: int = 0
    checksum: Optional[int] = None

    def is_valid(self) -> bool:
        return (
            MIN_COMPATIBLE_VERSION <= self.version <= PROTOCOL_VERSION
            and len(self.payload) <= FRAME_MAX_PAYLOAD_SIZE
        )

    def total_size(self) -> int:
        return FRAME_HEADER_SIZE + len(self.payload) + (4 if self.checksum is not None else 0)


# ---------------------------------------------------------------------------
# RPC helpers
# ---------------------------------------------------------------------------

@dataclass
class RpcError:
    code: int
    message: str
    method_id: Optional[int] = None
    request_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "method_id": self.method_id,
            "request_id": self.request_id,
        }


RPC_ERROR_CODES: Dict[int, str] = {
    0: "Ok",
    1: "MethodNotFound",
    2: "InvalidRequest",
    3: "InvalidResponse",
    4: "Timeout",
    5: "InternalError",
    6: "NotAuthenticated",
    7: "PermissionDenied",
    8: "RateLimited",
    9: "ServiceUnavailable",
    10: "SerializationError",
    11: "DeserializationError",
}
