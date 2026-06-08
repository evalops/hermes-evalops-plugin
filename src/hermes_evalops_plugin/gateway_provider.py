"""Gateway-backed Hermes LLM provider shim."""

from __future__ import annotations

from typing import Any

from .config import EvalOpsConfig
from .platform_client import EvalOpsPlatformClient
from .trace_context import SessionTraceStore, TraceContext, trace_context_from_hints


class EvalOpsGatewayProvider:
    """OpenAI-shaped provider that sends Hermes LLM calls through EvalOps Gateway."""

    name = "evalops-gateway"

    def __init__(
        self,
        config: EvalOpsConfig | None = None,
        client: EvalOpsPlatformClient | None = None,
        traces: SessionTraceStore | None = None,
    ) -> None:
        self.config = config or EvalOpsConfig.from_env()
        self.client = client or EvalOpsPlatformClient(self.config)
        self.traces = traces or SessionTraceStore()

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        trace = self._trace_for(session_id, metadata, kwargs)
        payload: dict[str, Any] = {
            "model": model or self.config.gateway_model,
            "messages": messages,
            "metadata": {
                "provider": self.name,
                "agent_id": self.config.agent_id,
                "organization_id": self.config.organization_id,
                "workspace_id": self.config.workspace_id,
                "session_id": session_id or "",
                "trace_id": trace.trace_id,
                "traceparent": trace.traceparent,
                **(metadata or {}),
            },
        }
        if tools is not None:
            payload["tools"] = tools
        for key in ("temperature", "max_tokens", "top_p", "stream", "tool_choice"):
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]
        return self.client.gateway_chat_completion(payload, trace)

    def complete(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.chat_completion(*args, **kwargs)

    def create_chat_completion(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.chat_completion(*args, **kwargs)

    def _trace_for(
        self,
        session_id: str | None,
        metadata: dict[str, Any] | None,
        kwargs: dict[str, Any],
    ) -> TraceContext:
        hints: dict[str, Any] = {}
        hints.update(metadata or {})
        hints.update(kwargs)
        hinted = trace_context_from_hints(hints)
        if hinted is not None:
            return hinted
        return self.traces.get_or_create(session_id, hints)

