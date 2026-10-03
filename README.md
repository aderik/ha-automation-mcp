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

## Comparison

How this server (together with the
[`automation_api`](https://github.com/aderik/ha-automation-api) integration)
compares with the two obvious alternatives:

- **Built-in `mcp_server`**: the
  [Model Context Protocol Server](https://www.home-assistant.io/integrations/mcp_server/)
  integration in Home Assistant core (since 2025.2). It gives MCP clients
  access to the Assist API, limited to the entities you
  [expose](https://www.home-assistant.io/voice_control/voice_remote_expose_devices/)
  to it. It controls and reads devices; it does not edit configuration.
- **ha-mcp**: [homeassistant-ai/ha-mcp](https://github.com/homeassistant-ai/ha-mcp),
  the unofficial community server. Its
  [README](https://github.com/homeassistant-ai/ha-mcp#-features) lists 87
  tools (checked against v8.6.0); the tool names below come from that list.
  Its own
  [comparison with the built-in server](https://github.com/homeassistant-ai/ha-mcp#-ha-mcp-vs-home-assistants-built-in-mcp-server)
  is the source for the built-in column where the Home Assistant docs are silent.
- **This MCP**: the 58 tools in [`server.py`](server.py).

✅ = supported, partly = with the stated limitation, ❌ = not available.

| Capability | Built-in `mcp_server` | ha-mcp | This MCP |
|---|---|---|---|
| Call services, control devices | partly: Assist intents, exposed entities only | ✅ `ha_call_service`, `ha_bulk_control` | ✅ `call_service` |
| Read entity state | partly: exposed entities only | ✅ `ha_get_state`, `ha_get_overview` | ✅ `get_state`, `list_entities` |
| Search entities | ❌ | ✅ `ha_search` (fuzzy, deep config search) | partly: `list_entities` filters on domain, area and substring |
| Automations: list, read, create/update, delete | ❌ | ✅ `ha_config_get_automation`, `ha_config_set_automation`, `ha_config_remove_automation` | ✅ `list_automations`, `get_automation`, `get_automation_yaml`, `create_or_update_automation`, `delete_automation`, `trigger_automation` |
| Automation traces | ❌ | ✅ `ha_get_automation_traces` | ❌ |
| Scripts | ❌ | ✅ `ha_config_get_script`, `ha_config_set_script`, `ha_config_remove_script` | ❌ |
| Scenes | ❌ | ✅ `ha_config_get_scene`, `ha_config_set_scene`, `ha_config_remove_scene` | ❌ |
| Blueprints | ❌ | ✅ `ha_manage_blueprints` | ❌ |
| `input_*` helpers | ❌ | ✅ `ha_config_list_helpers`, `ha_config_set_helper`, `ha_remove_helpers_integrations` | ✅ `list_helpers`, `get_helper`, `upsert_helper`, `delete_helper` |
| Other helpers (counter, timer, schedule, utility meter, …) | ❌ | ✅ `ha_config_set_helper` | ❌ |
| Template entities | ❌ | ✅ `ha_config_set_helper` (as config entry) | ✅ `list_template_entities`, `get_template_entity`, `upsert_template_entity`, `delete_template_entity` (as YAML) |
| `history_stats` sensors | ❌ | ✅ `ha_config_set_helper` (as config entry) | ✅ `list_history_stats_sensors`, `get_history_stats_sensor`, `upsert_history_stats_sensor`, `delete_history_stats_sensor` (as YAML) |
| Notify groups | ❌ | ✅ `ha_config_set_helper` (`group` helper) | ✅ `list_notify_groups`, `get_notify_group`, `upsert_notify_group`, `delete_notify_group` (as YAML) |
| Managed config as one readable YAML package | ❌ | partly: `ha_config_get_yaml`, `ha_config_set_yaml` (beta, feature flags and extra component entry) | ✅ `get_managed_package`, `overwrite_managed_package` |
| Dashboards: create, read, edit, delete | ❌ | ✅ `ha_config_get_dashboard`, `ha_config_set_dashboard`, `ha_config_delete_dashboard` | ✅ `list_dashboards`, `create_dashboard`, `update_dashboard_metadata`, `delete_dashboard`, `get_dashboard_config`, `set_dashboard_config` |
| Dashboard edits per view and per card | ❌ | ✅ `ha_config_set_dashboard` | ✅ `append_dashboard_view`, `replace_dashboard_view`, `delete_dashboard_view`, `append_dashboard_card`, `replace_dashboard_card`, `delete_dashboard_card` |
| Dashboard resources, screenshots | ❌ | ✅ `ha_config_set_dashboard_resource`, `ha_get_dashboard_screenshot` (beta) | ❌ |
| Entity registry | ❌ | ✅ `ha_get_entity`, `ha_set_entity`, `ha_remove_entity` | ✅ `list_registry_entities`, `get_registry_entity`, `update_registry_entity`, `delete_registry_entity` |
| Device registry | ❌ | ✅ `ha_get_device`, `ha_set_device`, `ha_remove_device` | ✅ `list_devices`, `get_device`, `update_device`, `delete_device` |
| Areas and floors | ❌ | ✅ `ha_list_floors_areas`, `ha_set_area_or_floor`, `ha_remove_area_or_floor` | partly: `list_areas` (read-only, no floors) |
| Zones, groups, labels, categories | ❌ | ✅ `ha_set_zone`, `ha_config_set_group`, `ha_config_set_label`, `ha_config_set_category` | ❌ |
| Config entries: list, enable, disable, remove | ❌ | ✅ `ha_get_integration`, `ha_set_integration`, `ha_remove_helpers_integrations` | ✅ `list_config_entries`, `get_config_entry`, `reload_config_entry`, `enable_config_entry`, `disable_config_entry`, `remove_config_entry` |
| Config entries: add, change options, reconfigure | ❌ | ✅ `ha_set_integration` | ❌ |
| Recorder history | ❌ | ✅ `ha_get_history` | ✅ `get_history` (with per-entity change counts) |
| Long-term statistics | ❌ | ✅ `ha_get_history` (`source="statistics"`) | ❌ |
| Home Assistant logs | ❌ | ✅ `ha_get_logs` | partly: `get_automation_api_log` returns only the integration's own log |
| Log of every write the agent made | ❌ | partly: automatic edit backups | ✅ `get_automation_api_log` |
| Reload and restart | ❌ | ✅ `ha_reload_core`, `ha_restart` | ✅ `reload_config`, `restart_home_assistant` |
| Backup and restore | ❌ | ✅ `ha_manage_backup` | ❌ |
| HACS, apps (add-ons), updates | ❌ | ✅ `ha_manage_hacs`, `ha_manage_app`, `ha_manage_updates` | ❌ |
| Template evaluation | ❌ | ✅ `ha_eval_template` | ❌ |
| Calendar events, to-do items | partly: Assist intents on exposed entities | ✅ `ha_config_set_calendar_event`, `ha_set_todo_item` | ❌ (only through `call_service`) |
| Files in the config directory | ❌ | partly: `ha_read_file`, `ha_write_file` (beta) | ❌ |
| ZHA / Matter / Thread radios | ❌ | ✅ `ha_manage_radio` | ❌ |
| Camera snapshots, energy preferences, themes, Assist pipelines | ❌ | ✅ `ha_get_camera_image`, `ha_manage_energy_prefs`, `ha_manage_theme`, `ha_manage_pipeline` | ❌ |
| Read-only mode, per-tool enable/disable | partly: "Control Home Assistant" option | ✅ `ha_manage_security_policy` | ❌ |
| Transport | Streamable HTTP at `/api/mcp` | HTTP (in-process component, app, Docker) or stdio | stdio |
| Authentication | OAuth or long-lived access token | secret URL, optionally Home Assistant sign-in; long-lived token for Docker/stdio | long-lived access token of an administrator (`HA_TOKEN`) |
| Needs a custom integration | no, part of core | recommended install is the HA-MCP custom component | yes, `automation_api` |

### Where this MCP is the better fit

- **Configuration lands in YAML you can read and version.** Helpers, template
  entities, `history_stats` sensors and notify groups are written to one
  package file, `packages/automation_api.yaml`, and automations to
  `automations.yaml`. `get_managed_package` returns the whole package and
  `get_automation_yaml` the raw automation YAML, so the result can be reviewed
  and committed to git. ha-mcp creates the same entity types as config entries
  in Home Assistant's internal storage.
- **One typed tool per operation.** Template entities, `history_stats` sensors
  and notify groups each have their own list/get/upsert/delete tools, and
  dashboards can be edited per view or per card (`replace_dashboard_card` and
  friends) without sending the full dashboard config.
- **An audit trail.** The integration logs every create, update, delete and
  trigger; `get_automation_api_log` returns that log.
- **A small surface.** 58 tools against 87, all backed by one integration, and
  Home Assistant's own bearer-token authentication on every call (the token
  must belong to an administrator).
- **`get_history` returns change counts per entity**, which shows a flapping
  sensor without reading the full history.

Compared with the built-in `mcp_server`, the difference is one of purpose: the
built-in server controls devices exposed to Assist, this one manages
configuration and sees every entity.

### What is still missing

Gaps relative to ha-mcp, as input for follow-up work:

- Scripts and scenes (create, edit, delete)
- Blueprints
- Automation traces for debugging
- Backup and restore
- HACS, apps (add-ons) and update management
- Home Assistant core and integration logs
- Long-term statistics
- Template evaluation
- Adding integrations, changing their options and reconfiguring config entries
- Helpers beyond `input_*`: counter, timer, schedule, utility meter and other
  config-flow helpers
- Writing areas; floors, zones, groups, labels and categories
- Calendar events and to-do items as dedicated tools
- Dashboard resources and screenshots
- ZHA / Matter / Thread radio management
- Camera snapshots, energy preferences, themes, Assist pipelines
- Fuzzy search across entities and configuration
- A read-only mode and per-tool enable/disable
- An HTTP transport and OAuth; this server is stdio with a long-lived token

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
