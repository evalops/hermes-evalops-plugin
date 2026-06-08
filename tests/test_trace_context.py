from __future__ import annotations

import unittest

from hermes_evalops_plugin.trace_context import SessionTraceStore, TraceContext


class TraceContextTest(unittest.TestCase):
    def test_traceparent_round_trips(self) -> None:
        trace = TraceContext.new_root()
        parsed = TraceContext.from_traceparent(trace.traceparent)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.trace_id, trace.trace_id)
        self.assertEqual(parsed.span_id, trace.span_id)

    def test_session_store_reuses_trace_id(self) -> None:
        store = SessionTraceStore()
        first = store.get_or_create("session-1")
        second = store.get_or_create("session-1")
        child = second.child()

        self.assertEqual(first.trace_id, second.trace_id)
        self.assertEqual(first.trace_id, child.trace_id)
        self.assertNotEqual(second.span_id, child.span_id)


if __name__ == "__main__":
    unittest.main()

