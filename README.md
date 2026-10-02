# ha-automation-mcp

MCP server for the [Home Assistant Automation API](https://github.com/aderik/ha-automation-api)
custom integration. It exposes the integration's REST API as MCP tools, so an
AI agent can manage Home Assistant without anyone pasting YAML:

- automations: list, read (live state and YAML), create/update, delete, trigger
- managed package: helpers (`input_*`), template entities, `history_stats`
  sensors, notify groups
- Lovelace dashboards: dashboards, views and cards
- registries: entities, devices, config entries (reload / enable / disable / remove)
- recorder history, reload and restart
- native HA: entity state and service calls

## Requirements

- Home Assistant with the `automation_api` integration (>= 1.0.0) installed via HACS
- A long-lived access token of an **administrator** (profile → Security)
- For the managed package tools, packages enabled in `configuration.yaml`:

  ```yaml
  homeassistant:
    packages: !include_dir_named packages
  ```

## Configuration

| Variable     | Required | Description |
|--------------|----------|-------------|
| `HA_URL`     | yes      | Base URL, e.g. `http://homeassistant.local:8123` |
| `HA_TOKEN`   | yes      | Long-lived access token of an administrator, used for every call |

## Install and run

The server speaks MCP over stdio. Install it as a tool with
[uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/aderik/ha-automation-mcp
```

That puts `ha-automation-mcp` on your `PATH`. To run it without installing:

```bash
uvx --from git+https://github.com/aderik/ha-automation-mcp ha-automation-mcp
```

### Claude Code

```bash
claude mcp add ha-automation -s user \
  -e HA_URL=http://homeassistant.local:8123 \
  -e HA_TOKEN=... \
  -- ha-automation-mcp
```

### LogicForce

Under **Settings → MCP connections**:

| Field     | Value |
|-----------|-------|
| Name      | `ha-automation` |
| Transport | `stdio` |
| Command   | `uvx` |
| Arguments | `["--from", "git+https://github.com/aderik/ha-automation-mcp@v1.0.0", "ha-automation-mcp"]` |
| Secrets   | `{"HA_URL": "http://<ha-host>:8123", "HA_TOKEN": "..."}` |

The first start in a container downloads Python and the server (about half a
minute); LogicForce allows for that, and later starts are cached. To upgrade,
change the tag in the arguments.
