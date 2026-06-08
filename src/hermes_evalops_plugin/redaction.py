"""Small payload safety helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
import re
from typing import Any


SENSITIVE_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|passwd|authorization|credential)", re.I)
SECRET_VALUE_RE = re.compile(
    r"(?i)(sk-[a-z0-9_-]{12,}|ops_[a-z0-9_-]{24,}|"
    r"bearer\s+[a-z0-9._~+/=-]{16,}|eyj[a-z0-9._-]{20,})"
)
MAX_STRING_CHARS = 1800
MAX_JSON_CHARS = 8000


def safe_value(value: Any, *, capture_payloads: bool = False, depth: int = 0) -> Any:
    if not capture_payloads:
        return "[payload-capture-disabled]"
    if depth > 4:
        return "[depth-limit]"
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:80]:
            key_text = str(key)
            out[key_text] = "[REDACTED]" if SENSITIVE_KEY_RE.search(key_text) else safe_value(
                item,
                capture_payloads=capture_payloads,
                depth=depth + 1,
            )
        return out
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [safe_value(item, capture_payloads=capture_payloads, depth=depth + 1) for item in list(value)[:80]]
    if isinstance(value, str):
        redacted = SECRET_VALUE_RE.sub("[REDACTED]", value)
        return redacted[:MAX_STRING_CHARS] + ("...[truncated]" if len(redacted) > MAX_STRING_CHARS else "")
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return safe_value(str(value), capture_payloads=capture_payloads, depth=depth + 1)


def json_size_guard(value: Any) -> Any:
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return str(value)[:MAX_STRING_CHARS]
    if len(encoded) <= MAX_JSON_CHARS:
        return value
    return encoded[:MAX_JSON_CHARS] + "...[truncated]"

