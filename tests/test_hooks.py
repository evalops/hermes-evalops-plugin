from __future__ import annotations

from unittest import mock
import unittest

from hermes_evalops_plugin import hooks


class FakeContext:
    def __init__(self) -> None:
        self.hooks = {}
        self.providers = {}

    def register_hook(self, name, func):
        self.hooks[name] = func

    def register_llm_provider(self, name, provider):
        self.providers[name] = provider


class RecordingClient:
    def __init__(self) -> None:
        self.registrations = []
        self.spans = []

    def register_agent(self, payload, trace):
        self.registrations.append((payload, trace))
        return {"registered": True}

    def ingest_span(self, payload, trace):
        self.spans.append((payload, trace))
        return {"ingested": True}

    def gateway_chat_completion(self, payload, trace):
        return {"ok": True}


class HooksTest(unittest.TestCase):
    def test_register_wires_provider_and_hooks(self) -> None:
        client = RecordingClient()
        with mock.patch.object(hooks, "_state", hooks.PluginState(client=client)):
            ctx = FakeContext()
            hooks.register(ctx)

        self.assertIn("evalops-gateway", ctx.providers)
        self.assertIn("on_startup", ctx.hooks)
        self.assertIn("agent:start", ctx.hooks)
        self.assertIn("agent:end", ctx.hooks)
        self.assertIn("post_tool_call", ctx.hooks)

    def test_startup_registers_agent_once(self) -> None:
        client = RecordingClient()
        with mock.patch.object(hooks, "_state", hooks.PluginState(client=client)):
            hooks.on_startup(session_id="session-1")
            hooks.on_startup(session_id="session-1")

        self.assertEqual(len(client.registrations), 1)
        payload, trace = client.registrations[0]
        self.assertEqual(payload["agent_id"], "hermes-evalops")
        self.assertIn("llm.gateway", payload["capabilities"])
        self.assertIn("slack", payload["surfaces"])
        self.assertEqual(len(trace.trace_id), 32)

    def test_tool_span_reuses_session_trace_id(self) -> None:
        client = RecordingClient()
        with mock.patch.object(hooks, "_state", hooks.PluginState(client=client)):
            llm = hooks.pre_llm_call(session_id="session-1", metadata={})
            result = hooks.post_tool_call(
                session_id="session-1",
                task_id="task-1",
                tool_call_id="tool-1",
                function_name="terminal",
                args={"api_key": "sk-secretsecretsecret"},
                result={"ok": True},
                duration_ms=25,
            )

        self.assertEqual(result, {"ingested": True})
        payload, trace = client.spans[0]
        self.assertEqual(payload["trace_context"]["trace_id"], llm["trace_id"])
        self.assertEqual(trace.trace_id, llm["trace_id"])
        self.assertEqual(payload["tool_name"], "terminal")
        self.assertEqual(payload["input"], "[payload-capture-disabled]")
        self.assertEqual(payload["duration_ms"], 25)


if __name__ == "__main__":
    unittest.main()
