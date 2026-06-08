"""Session trace context helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import secrets
from typing import Any


TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    sampled: bool = True

    @property
    def traceparent(self) -> str:
        flags = "01" if self.sampled else "00"
        return f"00-{self.trace_id}-{self.span_id}-{flags}"

    def child(self) -> "TraceContext":
        return TraceContext(trace_id=self.trace_id, span_id=_new_span_id(), sampled=self.sampled)

    @classmethod
    def new_root(cls) -> "TraceContext":
        return cls(trace_id=_new_trace_id(), span_id=_new_span_id())

    @classmethod
    def from_traceparent(cls, traceparent: str) -> "TraceContext | None":
        match = TRACEPARENT_RE.match(traceparent.strip().lower())
        if not match:
            return None
        trace_id, span_id, flags = match.groups()
        return cls(trace_id=trace_id, span_id=span_id, sampled=bool(int(flags, 16) & 1))


class SessionTraceStore:
    def __init__(self) -> None:
        self._sessions: dict[str, TraceContext] = {}

    def get_or_create(self, session_id: str | None, hints: dict[str, Any] | None = None) -> TraceContext:
        key = session_id or "unknown-session"
        hinted = trace_context_from_hints(hints or {})
        if hinted is not None:
            self._sessions[key] = hinted
            return hinted
        existing = self._sessions.get(key)
        if existing is not None:
            return existing
        trace = TraceContext.new_root()
        self._sessions[key] = trace
        return trace

    def forget(self, session_id: str | None) -> None:
        self._sessions.pop(session_id or "unknown-session", None)


def trace_context_from_hints(hints: dict[str, Any]) -> TraceContext | None:
    for key in ("traceparent", "w3c_traceparent", "w3c.traceparent"):
        value = hints.get(key)
        if isinstance(value, str):
            parsed = TraceContext.from_traceparent(value)
            if parsed is not None:
                return parsed
    trace_id = _clean_hex(hints.get("trace_id") or hints.get("session_trace_id"), 32)
    span_id = _clean_hex(hints.get("span_id") or hints.get("parent_span_id"), 16)
    if trace_id:
        return TraceContext(trace_id=trace_id, span_id=span_id or _new_span_id())
    env_traceparent = os.getenv("TRACEPARENT") or os.getenv("HERMES_EVALOPS_TRACEPARENT")
    if env_traceparent:
        return TraceContext.from_traceparent(env_traceparent)
    env_trace_id = _clean_hex(os.getenv("TRACE_ID") or os.getenv("HERMES_EVALOPS_TRACE_ID"), 32)
    if env_trace_id:
        return TraceContext(trace_id=env_trace_id, span_id=_new_span_id())
    return None


def inject_trace_headers(headers: dict[str, str], trace: TraceContext) -> dict[str, str]:
    headers["traceparent"] = trace.traceparent
    headers["x-evalops-trace-id"] = trace.trace_id
    headers["x-evalops-span-id"] = trace.span_id
    return headers


def _clean_hex(value: Any, length: int) -> str:
    if not isinstance(value, str):
        return ""
    lowered = value.strip().lower()
    if len(lowered) == length and all(ch in "0123456789abcdef" for ch in lowered):
        return lowered
    return ""


def _new_trace_id() -> str:
    return secrets.token_hex(16)


def _new_span_id() -> str:
    return secrets.token_hex(8)

