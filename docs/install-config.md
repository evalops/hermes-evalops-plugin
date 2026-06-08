# Install and Config

This spike is self-contained and can be loaded as a Hermes plugin without
forking Hermes.

## Local Install

```sh
cd /Users/jonathanhaas/hermes-evalops-plugin
python3 -m pip install -e .
```

For a plugin-directory demo, point Hermes at:

```text
/Users/jonathanhaas/hermes-evalops-plugin/plugins/evalops
```

The plugin entrypoint also injects this repo's `src/` path, so editable install
is convenient but not required for a local demo.

## Hermes Provider Config

Add the EvalOps gateway as a custom provider:

```yaml
custom_providers:
  evalops-gateway:
    base_url: https://llm-gateway.evalops.dev/v1
    api_key_env: EVALOPS_API_KEY
    api_mode: chat_completions

model:
  provider: evalops-gateway
```

Then run Hermes with provider `evalops-gateway`. LLM spans are expected to be
captured by the gateway once EVA-157 is deployed; the plugin attaches
`x-evalops-trace-id` so gateway spans and tool spans join the same session
trace.

## Environment

Required for live gateway calls:

```sh
export HERMES_EVALOPS_GATEWAY_URL="https://gateway.evalops.example/v1/chat/completions"
export HERMES_EVALOPS_GATEWAY_TOKEN="..."
```

Required for live registration/span ingest:

```sh
export HERMES_EVALOPS_PLATFORM_URL="https://platform.evalops.example"
export HERMES_EVALOPS_PLATFORM_TOKEN="..."
export HERMES_EVALOPS_ORGANIZATION_ID="org_..."
export HERMES_EVALOPS_WORKSPACE_ID="ws_..."
```

Useful knobs:

```sh
export HERMES_EVALOPS_AGENT_ID="hermes-evalops"
export HERMES_EVALOPS_AGENT_NAME="Hermes EvalOps"
export HERMES_EVALOPS_GATEWAY_MODEL="evalops-default"
export HERMES_EVALOPS_CAPTURE_PAYLOADS="0"
export HERMES_EVALOPS_TIMEOUT_SECONDS="10"
```

EVA-157 swap points:

```sh
export HERMES_EVALOPS_REGISTRATION_ENDPOINT="/v1/agent-mcp/external-agents/register"
export HERMES_EVALOPS_SPAN_INGEST_ENDPOINT="/v1/agent-runtime/external-spans"
```

Those defaults are intentionally contract-shaped placeholders. Once EVA-157
lands, replace them with the final scoped `agent-mcp` registration and span
ingest endpoints, or replace `EvalOpsPlatformClient` with generated clients.

## Runtime Behavior

At startup or `agent:start`, the plugin registers an external Hermes agent with
EvalOps using:

- agent ID/name/version
- organization/workspace
- surfaces: `slack`, `telegram`, `terminal`, `cron`
- capabilities: `github`, `terminal`, `calendar`, `sentry`, `linear`,
  `delegation`, `llm.gateway`, `tool.span_ingest`, `traceparent.propagation`
- local runtime metadata

For LLM calls, `evalops-gateway` posts OpenAI-shaped chat completion payloads to
`HERMES_EVALOPS_GATEWAY_URL` and stamps:

- `traceparent`
- `x-evalops-trace-id`
- `x-evalops-span-id`

For `post_tool_call`, the plugin expects Hermes hook fields such as
`function_name`, `args`, `result`, `duration_ms`, and `status`. It builds an
`evalops.external_agent.tool_span.v1` payload and posts it to the configured
span ingest endpoint. Payload capture is disabled by default; enable it only for
local demos or approved evidence paths.

## Demo Checklist

1. Run `PYTHONPATH=src python3 -m unittest discover -s tests`.
2. Run `python3 examples/demo_plugin_flow.py`.
3. Configure Hermes to load `plugins/evalops`.
4. Set gateway/platform URLs and tokens.
5. Start a Hermes session using provider `evalops-gateway`.
6. Confirm one startup registration and one `post_tool_call` span arrive with
   the same session trace ID.
