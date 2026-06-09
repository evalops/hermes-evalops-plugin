"""Hermes plugin hooks for EvalOps registration and trace/span ingest."""

from __future__ import annotations

import os
import time
from typing import Any

from .config import EvalOpsConfig
from .gateway_provider import EvalOpsGatewayProvider
from .platform_client import EvalOpsPlatformClient
from .redaction import json_size_guard, safe_value
from .trace_context import SessionTraceStore, TraceContext


HOOKS = [
    ("on_session_start", "on_session_start"),
    ("pre_llm_call", "pre_llm_call"),
    ("post_llm_call", "post_llm_call"),
    ("post_tool_call", "post_tool_call"),
    ("on_session_end", "on_session_end"),
]


class PluginState:
    def __init__(self, config: EvalOpsConfig | None = None, client: EvalOpsPlatformClient | None = None) -> None:
        self.config = config or EvalOpsConfig.from_env()
        self.client = client or EvalOpsPlatformClient(self.config)
        self.traces = SessionTraceStore()
        self.provider = EvalOpsGatewayProvider(self.config, self.client, self.traces)
        self.registered = False
        self.last_registration_error = ""

    def register_agent_once(self, trace: TraceContext | None = None) -> dict[str, Any]:
        if self.registered or not self.config.enabled:
            return {"skipped": True}
        trace = trace or TraceContext.new_root()
        payload = {
            "agent_id": self.config.agent_id,
            "name": self.config.agent_name,
            "version": self.config.agent_version,
            "kind": "hermes-external-agent",
            "provider": self.provider.name,
            "organization_id": self.config.organization_id,
            "workspace_id": self.config.workspace_id,
            "surfaces": ["slack", "telegram", "terminal", "cron"],
            "capabilities": [
                "github",
                "terminal",
                "calendar",
                "sentry",
                "linear",
                "delegation",
                "llm.gateway",
                "tool.span_ingest",
                "traceparent.propagation",
            ],
            "runtime": {
                "source": "hermes-evalops-plugin",
                "pid": os.getpid(),
                "cwd": os.getcwd(),
            },
        }
        try:
            response = self.client.register_agent(payload, trace)
        except Exception as exc:
            self.last_registration_error = str(exc)
            return {"error": self.last_registration_error}
        self.registered = True
        return response

    def ensure_session_trace(self, session_id: str | None, hints: dict[str, Any]) -> TraceContext:
        return self.traces.get_or_create(session_id, hints)

    def ingest_tool_span(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        if not self.config.enabled:
            return {"skipped": True}
        session_id = _session_key(kwargs)
        trace = self.ensure_session_trace(session_id, kwargs).child()
        now_ms = int(time.time() * 1000)
        duration_ms = _duration_ms(kwargs)
        payload = {
            "schema": "evalops.external_agent.tool_span.v1",
            "agent_id": self.config.agent_id,
            "organization_id": self.config.organization_id,
            "workspace_id": self.config.workspace_id,
            "session_id": session_id,
            "task_id": kwargs.get("task_id") or "",
            "tool_call_id": kwargs.get("tool_call_id") or "",
            "tool_name": kwargs.get("function_name") or kwargs.get("tool_name") or kwargs.get("name") or "unknown_tool",
            "status": _tool_status(kwargs),
            "started_at_unix_ms": now_ms - duration_ms if duration_ms is not None else None,
            "ended_at_unix_ms": now_ms,
            "duration_ms": duration_ms,
            "trace_context": {
                "trace_id": trace.trace_id,
                "span_id": trace.span_id,
                "parent_span_id": kwargs.get("parent_span_id") or "",
                "traceparent": trace.traceparent,
                "tracestate": kwargs.get("tracestate") or "",
            },
            "input": json_size_guard(safe_value(kwargs.get("args"), capture_payloads=self.config.capture_payloads)),
            "output": json_size_guard(safe_value(kwargs.get("result"), capture_payloads=self.config.capture_payloads)),
            "error": json_size_guard(safe_value(kwargs.get("error"), capture_payloads=self.config.capture_payloads)),
            "metadata": {
                "source": "hermes.post_tool_call",
                "provider": self.provider.name,
            },
        }
        return self.client.ingest_span(payload, trace)


_state = PluginState()


def register(ctx: Any) -> None:
    if not _state.config.enabled:
        return
    _register_provider(ctx, _state.provider)
    for hook_name, function_name in HOOKS:
        _register_hook(ctx, hook_name, globals()[function_name])
    if not hasattr(ctx, "register_hook"):
        _state.register_agent_once()


def on_session_start(**kwargs: Any) -> dict[str, Any]:
    trace = _state.ensure_session_trace(_session_key(kwargs), kwargs)
    registration = _state.register_agent_once(trace)
    return {"trace_id": trace.trace_id, "traceparent": trace.traceparent, "registration": registration}


def pre_llm_call(**kwargs: Any) -> dict[str, Any]:
    session_id = _session_key(kwargs)
    trace = _state.ensure_session_trace(session_id, kwargs)
    _inject_trace_mutations(kwargs, trace)
    return {"trace_id": trace.trace_id, "traceparent": trace.traceparent}


def post_llm_call(**kwargs: Any) -> dict[str, Any]:
    session_id = _session_key(kwargs)
    trace = _state.ensure_session_trace(session_id, kwargs)
    return {"trace_id": trace.trace_id, "traceparent": trace.traceparent}


def post_tool_call(**kwargs: Any) -> dict[str, Any]:
    return _state.ingest_tool_span(kwargs)


def on_session_end(**kwargs: Any) -> dict[str, Any]:
    session_id = _session_key(kwargs)
    trace = _state.ensure_session_trace(session_id, kwargs)
    _state.traces.forget(session_id)
    return {"trace_id": trace.trace_id, "traceparent": trace.traceparent}


def _register_provider(ctx: Any, provider: EvalOpsGatewayProvider) -> None:
    for method_name in ("register_llm_provider", "register_provider"):
        method = getattr(ctx, method_name, None)
        if callable(method):
            try:
                method(provider.name, provider)
            except TypeError:
                method(provider)
            return


def _register_hook(ctx: Any, hook_name: str, func: Any) -> None:
    method = getattr(ctx, "register_hook", None)
    if callable(method):
        method(hook_name, func)


def _inject_trace_mutations(kwargs: dict[str, Any], trace: TraceContext) -> None:
    for key in ("headers", "request_headers"):
        headers = kwargs.get(key)
        if isinstance(headers, dict):
            headers["traceparent"] = trace.traceparent
            headers["x-evalops-trace-id"] = trace.trace_id
    metadata = kwargs.get("metadata")
    if isinstance(metadata, dict):
        metadata["trace_id"] = trace.trace_id
        metadata["traceparent"] = trace.traceparent


def _session_key(kwargs: dict[str, Any]) -> str:
    return str(
        kwargs.get("session_id")
        or kwargs.get("session_key")
        or kwargs.get("thread_id")
        or kwargs.get("task_id")
        or "unknown-session"
    )


def _duration_ms(kwargs: dict[str, Any]) -> int | None:
    value = kwargs.get("duration_ms")
    if isinstance(value, (int, float)):
        return max(0, int(value))
    started = kwargs.get("started_at_unix_ms")
    ended = kwargs.get("ended_at_unix_ms")
    if isinstance(started, (int, float)) and isinstance(ended, (int, float)):
        return max(0, int(ended - started))
    return None


def _tool_status(kwargs: dict[str, Any]) -> str:
    if kwargs.get("error"):
        return "error"
    status = kwargs.get("status")
    if isinstance(status, str) and status:
        return status
    return "ok"
