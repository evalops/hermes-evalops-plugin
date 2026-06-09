"""Configuration for the Hermes EvalOps plugin spike."""

from __future__ import annotations

from dataclasses import dataclass
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class EvalOpsConfig:
    enabled: bool
    capture_payloads: bool
    agent_id: str
    agent_type: str
    agent_name: str
    agent_version: str
    auth_provider: str
    organization_id: str
    workspace_id: str
    gateway_url: str
    gateway_token: str
    gateway_model: str
    platform_url: str
    platform_token: str
    registration_endpoint: str
    span_ingest_endpoint: str
    timeout_seconds: float

    @classmethod
    def from_env(cls) -> "EvalOpsConfig":
        return cls(
            enabled=_env_bool("HERMES_EVALOPS_ENABLED", True),
            capture_payloads=_env_bool("HERMES_EVALOPS_CAPTURE_PAYLOADS", False),
            agent_id=os.getenv("HERMES_EVALOPS_AGENT_ID", "hermes-evalops"),
            agent_type=os.getenv("HERMES_EVALOPS_AGENT_TYPE", "hermes"),
            agent_name=os.getenv("HERMES_EVALOPS_AGENT_NAME", "Hermes EvalOps Spike"),
            agent_version=os.getenv("HERMES_EVALOPS_AGENT_VERSION", "0.1.0"),
            auth_provider=os.getenv("HERMES_EVALOPS_AUTH_PROVIDER", "openai"),
            organization_id=os.getenv("HERMES_EVALOPS_ORGANIZATION_ID", ""),
            workspace_id=os.getenv("HERMES_EVALOPS_WORKSPACE_ID", ""),
            gateway_url=os.getenv("HERMES_EVALOPS_GATEWAY_URL", ""),
            gateway_token=os.getenv("HERMES_EVALOPS_GATEWAY_TOKEN", ""),
            gateway_model=os.getenv("HERMES_EVALOPS_GATEWAY_MODEL", "evalops-default"),
            platform_url=os.getenv("HERMES_EVALOPS_PLATFORM_URL", ""),
            platform_token=os.getenv("HERMES_EVALOPS_PLATFORM_TOKEN", ""),
            registration_endpoint=os.getenv(
                "HERMES_EVALOPS_REGISTRATION_ENDPOINT",
                "mcp",
            ),
            span_ingest_endpoint=os.getenv(
                "HERMES_EVALOPS_SPAN_INGEST_ENDPOINT",
                "mcp:self_diagnostic",
            ),
            timeout_seconds=_env_float("HERMES_EVALOPS_TIMEOUT_SECONDS", 10.0),
        )
