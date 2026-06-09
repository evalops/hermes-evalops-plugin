# hermes-evalops-plugin

A Hermes plugin that routes LLM calls through the EvalOps gateway and reports
agent registration and tool spans back to the EvalOps platform. It loads as a
standalone Hermes plugin and does not fork Hermes.

## What it does

- **Gateway provider** (`evalops-gateway`) — an OpenAI-shaped LLM provider that
  sends Hermes chat completions through the EvalOps gateway.
- **Agent registration** — on `on_session_start`, registers the running Hermes
  agent with EvalOps: agent ID/name/version, org/workspace, surfaces, and
  capabilities.
- **Span ingest** — on `post_tool_call`, builds an
  `evalops.external_agent.tool_span.v1` payload and posts it to the span ingest
  endpoint.
- **Trace propagation** — stamps `traceparent` and `x-evalops-trace-id` so the
  gateway's LLM spans and the plugin's tool spans join the same session trace.

Outbound payloads pass through `redaction.py`, which strips keys matching
`api_key`, `token`, `secret`, `password`, `authorization`, and `credential`.
Tool-argument and result capture is off by default.

## Layout

| Path | Purpose |
|------|---------|
| `plugins/evalops/plugin.yaml` | Plugin manifest: hook names and provider name. |
| `plugins/evalops/__init__.py` | Loads the package from `src/` for local demos. |
| `src/hermes_evalops_plugin/gateway_provider.py` | OpenAI-shaped, gateway-backed LLM provider. |
| `src/hermes_evalops_plugin/hooks.py` | Provider + agent registration, span ingest, trace propagation. |
| `src/hermes_evalops_plugin/platform_client.py` | HTTP client for registration and span ingest. |
| `src/hermes_evalops_plugin/redaction.py` | Strips sensitive keys before payloads leave the process. |
| `examples/hermes-config.yaml` | Hermes `custom_providers` fragment for `evalops-gateway`. |

## Quick demo

```sh
cd hermes-evalops-plugin
PYTHONPATH=src python3 -m unittest discover -s tests
python3 examples/demo_plugin_flow.py
```

The demo exercises the registration, gateway, and span-ingest paths against
in-process stubs, so it runs with no network access and no credentials.

## Install and config

See [docs/install-config.md](docs/install-config.md) for the editable install,
the Hermes provider fragment, and the environment variables.

## Status

The registration and span-ingest endpoints are configurable placeholders, so the
plugin can run against stubs today and swap to the scoped `agent-mcp`
registration path once EVA-157 lands. Override
`HERMES_EVALOPS_REGISTRATION_ENDPOINT` and `HERMES_EVALOPS_SPAN_INGEST_ENDPOINT`
to point at the final endpoints.
