"""HTTP clients for EvalOps gateway and platform spike endpoints."""

from __future__ import annotations

import json
from typing import Any
from urllib import request
from urllib.error import HTTPError
from urllib.parse import urljoin

from .config import EvalOpsConfig
from .trace_context import TraceContext, inject_trace_headers


class EvalOpsHTTPError(RuntimeError):
    pass


class EvalOpsPlatformClient:
    def __init__(self, config: EvalOpsConfig) -> None:
        self.config = config
        self.mcp_session_id = ""

    def gateway_chat_completion(self, payload: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        if not self.config.gateway_url:
            raise EvalOpsHTTPError("HERMES_EVALOPS_GATEWAY_URL is required for gateway completions")
        return self._post_json(
            self.config.gateway_url,
            payload,
            trace,
            token=self.config.gateway_token,
        )

    def register_agent(self, payload: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        if not self.config.platform_url:
            return {"skipped": True, "reason": "HERMES_EVALOPS_PLATFORM_URL not set"}
        if self.config.registration_endpoint == "mcp":
            arguments = {
                "agent_type": payload.get("agent_type") or "hermes",
                "provider": payload.get("provider") or self.config.auth_provider,
                "surface": "hermes-gateway",
                "workspace_id": self.config.workspace_id or self.config.organization_id,
                "capabilities": payload.get("capabilities") or [],
                "ttl_seconds": 3600,
            }
            if self.config.platform_token:
                arguments["user_token"] = self.config.platform_token
            return self.call_mcp_tool("evalops_register", arguments, trace)
        return self._post_json(
            urljoin(self.config.platform_url.rstrip("/") + "/", self.config.registration_endpoint.lstrip("/")),
            payload,
            trace,
            token=self.config.platform_token,
        )

    def ingest_span(self, payload: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        if not self.config.platform_url:
            return {"skipped": True, "reason": "HERMES_EVALOPS_PLATFORM_URL not set"}
        if self.config.span_ingest_endpoint == "mcp:self_diagnostic":
            message = json.dumps(
                {
                    "event": "hermes.post_tool_call",
                    "tool_name": payload.get("tool_name"),
                    "status": payload.get("status"),
                    "session_id": payload.get("session_id"),
                    "trace_id": payload.get("trace_context", {}).get("trace_id"),
                    "duration_ms": payload.get("duration_ms"),
                },
                separators=(",", ":"),
            )
            return self.call_mcp_tool(
                "evalops_report_self_diagnostic",
                {
                    "severity": "info" if payload.get("status") == "ok" else "warning",
                    "category": "tool",
                    "message": message,
                    "trace_id": payload.get("trace_context", {}).get("trace_id") or trace.trace_id,
                    "run_id": payload.get("task_id") or payload.get("session_id") or "",
                },
                trace,
            )
        return self._post_json(
            urljoin(self.config.platform_url.rstrip("/") + "/", self.config.span_ingest_endpoint.lstrip("/")),
            payload,
            trace,
            token=self.config.platform_token,
        )

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        trace: TraceContext,
        *,
        token: str,
    ) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "hermes-evalops-plugin/0.1.0",
        }
        if token:
            headers["authorization"] = f"Bearer {token}"
        inject_trace_headers(headers, trace)
        req = request.Request(url, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvalOpsHTTPError(f"POST {url} failed with {exc.code}: {detail}") from exc
        if not raw:
            return {}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {"raw": raw.decode("utf-8", errors="replace")}
        return decoded if isinstance(decoded, dict) else {"data": decoded}

    def call_mcp_tool(self, name: str, arguments: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        endpoint = self._mcp_endpoint()
        if not self.mcp_session_id:
            self.mcp_session_id = self._mcp_initialize(endpoint, trace)
            self._mcp_post(
                endpoint,
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
                trace,
                session_id=self.mcp_session_id,
            )
        response = self._mcp_post(
            endpoint,
            {
                "jsonrpc": "2.0",
                "id": f"hermes-evalops-{name}",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
            trace,
            session_id=self.mcp_session_id,
        )
        result = response.get("result")
        if isinstance(result, dict):
            structured = result.get("structuredContent")
            if isinstance(structured, dict):
                return structured
            content = result.get("content")
            if isinstance(content, list) and content and isinstance(content[0], dict):
                text = content[0].get("text")
                if isinstance(text, str):
                    try:
                        decoded = json.loads(text)
                    except json.JSONDecodeError:
                        return {"text": text}
                    if isinstance(decoded, dict):
                        return decoded
        if "error" in response:
            raise EvalOpsHTTPError(f"MCP tool {name} failed: {response['error']}")
        return response

    def _mcp_endpoint(self) -> str:
        if self.config.platform_url.rstrip("/").endswith("/mcp"):
            return self.config.platform_url
        return urljoin(self.config.platform_url.rstrip("/") + "/", "mcp")

    def _mcp_initialize(self, endpoint: str, trace: TraceContext) -> str:
        response, headers = self._mcp_post_raw(
            endpoint,
            {
                "jsonrpc": "2.0",
                "id": "hermes-evalops-initialize",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "hermes-evalops-plugin", "version": self.config.agent_version},
                },
            },
            trace,
            session_id="",
        )
        session_id = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        if not session_id:
            raise EvalOpsHTTPError(f"MCP initialize did not return Mcp-Session-Id: {response}")
        return session_id

    def _mcp_post(
        self,
        endpoint: str,
        payload: dict[str, Any],
        trace: TraceContext,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        response, _ = self._mcp_post_raw(endpoint, payload, trace, session_id=session_id)
        return response

    def _mcp_post_raw(
        self,
        endpoint: str,
        payload: dict[str, Any],
        trace: TraceContext,
        *,
        session_id: str,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        headers = {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "user-agent": "hermes-evalops-plugin/0.1.0",
            "mcp-protocol-version": "2025-06-18",
        }
        if session_id:
            headers["mcp-session-id"] = session_id
        inject_trace_headers(headers, trace)
        req = request.Request(endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                raw = response.read()
                response_headers = {key.lower(): value for key, value in response.headers.items()}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvalOpsHTTPError(f"POST {endpoint} failed with {exc.code}: {detail}") from exc
        return _decode_mcp_response(raw), response_headers


def _decode_mcp_response(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return {}
    if text.startswith("event:") or "\ndata:" in text or text.startswith("data:"):
        data_lines = []
        for line in text.splitlines():
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
        text = "\n".join(data_lines).strip()
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    return decoded if isinstance(decoded, dict) else {"data": decoded}
