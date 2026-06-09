# hermes-evalops-plugin

Standalone spike for the Hermes custom provider + plugin path EvalOps needs once
EVA-157 lands.

It intentionally does not fork Hermes. The repo contains a normal Python package
plus a Hermes-style plugin directory:

- `plugins/evalops/plugin.yaml` declares the plugin and hook names.
- `plugins/evalops/__init__.py` loads the package from `src/` for local demos.
- `src/hermes_evalops_plugin/gateway_provider.py` implements an OpenAI-shaped,
  EvalOps gateway-backed LLM provider.
- `src/hermes_evalops_plugin/hooks.py` registers the provider, registers the
  external agent on `on_session_start`, ingests `post_tool_call` spans,
  and propagates session trace IDs.
- `examples/hermes-config.yaml` shows the Hermes `custom_providers` fragment for
  `evalops-gateway`.

The wire endpoints are configurable placeholders so the spike can demo now and
swap to the scoped `agent-mcp` registration path when EVA-157 is merged.

## Quick Demo

```sh
cd /Users/jonathanhaas/hermes-evalops-plugin
PYTHONPATH=src python3 -m unittest discover -s tests
python3 examples/demo_plugin_flow.py
```

## Install

See [docs/install-config.md](/Users/jonathanhaas/hermes-evalops-plugin/docs/install-config.md).
