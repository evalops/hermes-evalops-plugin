# Install and Config

This spike is self-contained and can be loaded as a Hermes plugin without
forking Hermes.

## Local Install

```sh
cd hermes-evalops-plugin
python3 -m pip install -e .
```

For a plugin-directory demo, point Hermes at:

```text
<repo-root>/plugins/evalops
```

The plugin entrypoint also injects this repo's `src/` path, so editable install
is convenient but not required for a local demo.

## Hermes Provider Config

Add the EvalOps gateway as a custom provider:

```yaml
custom_providers:
  - name: evalops-gateway
    base_url: https://llm-gateway.evalops.dev/v1
    api_key_env: EVALOPS_API_KEY
    api_mode: chat_completions
    model: deepseek/deepseek-v4-pro

model:
  provider: custom:evalops-gateway
  default: deepseek/deepseek-v4-pro
```

Then run Hermes with provider `evalops-gateway`. LLM spans are expected to be
captured by the gateway once EVA-157 is deployed; the plugin attaches
`x-evalops-trace-id` so gateway spans and tool spans join the same session
trace.

## Environment

Required for live gateway calls:

```sh
export HERMES_EVALOPS_GATEWAY_URL="https://llm-gateway.evalops.dev/v1"
export HERMES_EVALOPS_GATEWAY_TOKEN="***"  # Identity bootstrap key or issued agent token
```

Required for live registration/span ingest (agent-mcp is live at
`https://app.evalops.dev/mcp`, auth required):

```sh
export HERMES_EVALOPS_PLATFORM_URL="https://app.evalops.dev"
export HERMES_EVALOPS_PLATFORM_TOKEN="***"  # Same identity token
export HERMES_EVALOPS_ORGANIZATION_ID="org_evalops"
export HERMES_EVALOPS_WORKSPACE_ID="evalops"
```

Useful knobs:

```sh
export HERMES_EVALOPS_AGENT_ID="hermes-evalops"
export HERMES_EVALOPS_AGENT_NAME="Hermes EvalOps"
export HERMES_EVALOPS_GATEWAY_MODEL="evalops-default"
export HERMES_EVALOPS_CAPTURE_PAYLOADS="0"
export HERMES_EVALOPS_TIMEOUT_SECONDS="10"
```

EVA-157 swap points (current defaults use in-process MCP stubs):

```sh
# Current defaults — run against local stubs with no network or credentials:
#   HERMES_EVALOPS_REGISTRATION_ENDPOINT=mcp
#   HERMES_EVALOPS_SPAN_INGEST_ENDPOINT=mcp:self_diagnostic
#
# Once EVA-157 lands and agent-mcp is publicly exposed, swap to:
export HERMES_EVALOPS_REGISTRATION_ENDPOINT="mcp"
export HERMES_EVALOPS_SPAN_INGEST_ENDPOINT="/v1/agent-runtime/external-spans"
```

The `mcp` registration endpoint connects to the platform's agent-mcp
StreamableHTTP endpoint. The `mcp:self_diagnostic` span ingest posts tool spans
as self-diagnostic events through the same MCP session. Once EVA-157 ships,
replace `mcp:self_diagnostic` with the scoped span ingest path.

## Runtime Behavior

On Hermes Python hook `on_session_start`, the plugin registers an external
Hermes agent with EvalOps using:

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
