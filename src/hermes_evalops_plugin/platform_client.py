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
        return self._post_json(
            urljoin(self.config.platform_url.rstrip("/") + "/", self.config.registration_endpoint.lstrip("/")),
            payload,
            trace,
            token=self.config.platform_token,
        )

    def ingest_span(self, payload: dict[str, Any], trace: TraceContext) -> dict[str, Any]:
        if not self.config.platform_url:
            return {"skipped": True, "reason": "HERMES_EVALOPS_PLATFORM_URL not set"}
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

