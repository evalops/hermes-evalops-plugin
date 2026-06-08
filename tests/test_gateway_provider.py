from __future__ import annotations

import unittest

from hermes_evalops_plugin.config import EvalOpsConfig
from hermes_evalops_plugin.gateway_provider import EvalOpsGatewayProvider


class RecordingClient:
    def __init__(self) -> None:
        self.calls = []

    def gateway_chat_completion(self, payload, trace):
        self.calls.append((payload, trace))
        return {"ok": True}


class GatewayProviderTest(unittest.TestCase):
    def test_posts_openai_shaped_payload_with_trace_metadata(self) -> None:
        config = EvalOpsConfig.from_env()
        client = RecordingClient()
        provider = EvalOpsGatewayProvider(config=config, client=client)

        response = provider.chat_completion(
            [{"role": "user", "content": "hello"}],
            model="evalops-test",
            session_id="session-1",
            temperature=0.2,
        )

        self.assertEqual(response, {"ok": True})
        payload, trace = client.calls[0]
        self.assertEqual(payload["model"], "evalops-test")
        self.assertEqual(payload["messages"][0]["content"], "hello")
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(payload["metadata"]["trace_id"], trace.trace_id)
        self.assertEqual(payload["metadata"]["traceparent"], trace.traceparent)


if __name__ == "__main__":
    unittest.main()

