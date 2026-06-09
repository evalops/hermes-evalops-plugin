"""Tiny local demo for the plugin without a Hermes runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hermes_evalops_plugin import hooks  # noqa: E402


@dataclass
class DemoContext:
    hooks: dict[str, object] = field(default_factory=dict)
    providers: dict[str, object] = field(default_factory=dict)

    def register_hook(self, name: str, func: object) -> None:
        self.hooks[name] = func

    def register_llm_provider(self, name: str, provider: object) -> None:
        self.providers[name] = provider


class RecordingClient:
    def __init__(self) -> None:
        self.registrations: list[dict[str, object]] = []
        self.spans: list[dict[str, object]] = []

    def register_agent(self, payload, trace):
        self.registrations.append({"payload": payload, "traceparent": trace.traceparent})
        return {"ok": True}

    def ingest_span(self, payload, trace):
        self.spans.append({"payload": payload, "traceparent": trace.traceparent})
        return {"ok": True}

    def gateway_chat_completion(self, payload, trace):
        return {"id": "demo", "choices": [{"message": {"role": "assistant", "content": "ok"}}]}


def main() -> None:
    client = RecordingClient()
    with mock.patch.object(hooks, "_state", hooks.PluginState(client=client)):
        ctx = DemoContext()
        hooks.register(ctx)
        ctx.hooks["on_session_start"](session_id="demo-session", surface="terminal")
        llm_trace = ctx.hooks["pre_llm_call"](session_id="demo-session", metadata={})
        ctx.hooks["post_tool_call"](
            session_id="demo-session",
            task_id="task-1",
            tool_call_id="tool-1",
            function_name="terminal",
            args={"cmd": "date"},
            result={"stdout": "Mon Jun 8"},
            duration_ms=42,
        )
    print("provider:", sorted(ctx.providers))
    print("hooks:", sorted(ctx.hooks))
    print("traceparent:", llm_trace["traceparent"])
    print("registrations:", len(client.registrations))
    print("spans:", len(client.spans))
    print("span trace id:", client.spans[0]["payload"]["trace_context"]["trace_id"])


if __name__ == "__main__":
    main()
