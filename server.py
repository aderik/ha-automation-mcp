"""MCP server for the Home Assistant Automation API custom component.

Connects to a Home Assistant instance running the `automation_api` HACS
integration (https://github.com/aderik/ha-automation-api) and exposes its
REST surface as MCP tools.

Environment variables:
    HA_URL       Base URL of Home Assistant, e.g. http://homeassistant.local:8123
    HA_TOKEN     Long-lived access token of an administrator. The Automation
                 API (>= 1.0.0) and the native HA endpoints share it.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


HA_URL = os.environ.get("HA_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")


def _require_config() -> None:
    missing = [k for k, v in (("HA_URL", HA_URL), ("HA_TOKEN", HA_TOKEN)) if not v]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {HA_TOKEN}", "Content-Type": "application/json"}


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
    raw_text: bool = False,
) -> Any:
    _require_config()
    url = f"{HA_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.request(
            method,
            url,
            params=params,
            json=json,
            headers=_headers(),
        )
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text
            return {"error": True, "status": r.status_code, "detail": detail}
        if raw_text:
            return r.text
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.text


mcp = FastMCP("ha-automation-api")


@mcp.tool()
async def list_automations() -> Any:
    """List every automation known to Home Assistant.

    Returns the entity_id, slug id, friendly name, current state, and last
    trigger timestamp for each automation (as reported by the state machine).
    """
    return await _request("GET", "/api/automation_api/automations")


@mcp.tool()
async def get_automation(automation_id: str) -> Any:
    """Get a single automation by id (e.g. 'solaredge_power_notify').

    Returns live state + attributes. Use `get_automation_yaml` for the raw
    YAML config (triggers / conditions / actions).
    """
    return await _request(
        "GET", "/api/automation_api/automations", params={"id": automation_id}
    )


@mcp.tool()
async def get_automation_yaml(automation_id: str | None = None) -> Any:
    """Return raw YAML config from automations.yaml.

    Pass `automation_id` for a single automation, or omit to get everything.
    """
    params = {"id": automation_id} if automation_id else None
    return await _request(
        "GET", "/api/automation_api/automations_yaml", params=params
    )


@mcp.tool()
async def create_or_update_automation(
    id: str,
    name: str,
    trigger: list[dict[str, Any]],
    action: list[dict[str, Any]],
    condition: list[dict[str, Any]] | None = None,
    description: str = "",
    mode: str = "single",
) -> Any:
    """Create or update an automation (written to automations.yaml + reloaded).

    Args:
        id: Stable slug (no 'automation.' prefix), e.g. 'living_room_lights_on'.
        name: Friendly name shown in the UI.
        trigger: List of HA trigger dicts.
        action: List of HA action dicts.
        condition: Optional list of HA condition dicts.
        description: Free-form description.
        mode: HA mode — 'single', 'restart', 'queued', or 'parallel'.
    """
    payload: dict[str, Any] = {
        "id": id,
        "name": name,
        "trigger": trigger,
        "action": action,
        "condition": condition or [],
        "description": description,
        "mode": mode,
    }
    return await _request("POST", "/api/automation_api/automations", json=payload)


@mcp.tool()
async def delete_automation(automation_id: str) -> Any:
    """Delete an automation by id (removes it from automations.yaml)."""
    return await _request(
        "DELETE",
        "/api/automation_api/automations",
        params={"id": automation_id},
    )


@mcp.tool()
async def trigger_automation(automation_id: str) -> Any:
    """Manually fire an automation's actions, bypassing triggers + conditions.

    Accepts either the slug ('my_auto') or the full entity_id ('automation.my_auto').
    """
    return await _request(
        "POST",
        "/api/automation_api/trigger",
        json={"id": automation_id},
    )


@mcp.tool()
async def list_areas() -> Any:
    """List every area (room) defined in Home Assistant."""
    return await _request("GET", "/api/automation_api/areas")


@mcp.tool()
async def list_entities(
    domain: str | None = None,
    area: str | None = None,
    search: str | None = None,
) -> Any:
    """List Home Assistant entities with optional filters.

    Args:
        domain: Filter by domain, e.g. 'light', 'switch', 'sensor'.
        area:   Filter by area name (case-insensitive), e.g. 'Woonkamer'.
        search: Substring match against entity_id or friendly name.
    """
    params: dict[str, Any] = {}
    if domain:
        params["domain"] = domain
    if area:
        params["area"] = area
    if search:
        params["search"] = search
    return await _request(
        "GET", "/api/automation_api/entities", params=params or None
    )


@mcp.tool()
async def get_automation_api_log() -> Any:
    """Return the Automation API log file (automation_api.log).

    Contains a record of every create/update/delete/trigger the integration
    has performed via REST, WebSocket, or service calls.
    """
    return await _request(
        "GET", "/api/automation_api/log", raw_text=True
    )


# ---------------------------------------------------------------------------
# Managed configuration (automation_api >= 0.5.0)
# ---------------------------------------------------------------------------
#
# These tools manage the contents of `<config>/packages/automation_api.yaml`.
# Requires a one-time setup in configuration.yaml:
#     homeassistant:
#       packages: !include_dir_named packages
# and a single HA restart after that.

HELPER_DOMAINS = {
    "input_boolean",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "input_button",
}

TEMPLATE_TYPES = {"sensor", "binary_sensor", "switch", "button", "number", "select"}


@mcp.tool()
async def get_managed_package() -> Any:
    """Return the full managed package file as JSON (helpers, templates, etc.)."""
    return await _request("GET", "/api/automation_api/package")


@mcp.tool()
async def overwrite_managed_package(content: dict[str, Any]) -> Any:
    """Overwrite the entire managed package file (expert / bulk migration use).

    Triggers homeassistant.reload_all afterwards. Prefer the targeted
    upsert_* tools for day-to-day changes.
    """
    return await _request("PUT", "/api/automation_api/package", json=content)


@mcp.tool()
async def upsert_helper(
    domain: str, helper_id: str, config: dict[str, Any]
) -> Any:
    """Create or update a helper (reloads the domain automatically).

    Args:
        domain: One of input_boolean / input_datetime / input_number /
                input_select / input_text / input_button.
        helper_id: Slug used as the helper id, e.g. 'moestuin_startdatum'.
        config: Full YAML config dict for the helper. Examples:
            input_boolean → {"name": "...", "initial": true, "icon": "mdi:bell"}
            input_datetime → {"name": "...", "has_date": true, "has_time": false}
            input_number  → {"name": "...", "min": 0, "max": 100, "step": 1}
    """
    if domain not in HELPER_DOMAINS:
        return {"error": f"unsupported domain: {domain}"}
    return await _request(
        "PUT",
        f"/api/automation_api/helpers/{domain}/{helper_id}",
        json=config,
    )


@mcp.tool()
async def delete_helper(domain: str, helper_id: str) -> Any:
    """Delete a helper from the managed package and reload the domain."""
    return await _request(
        "DELETE", f"/api/automation_api/helpers/{domain}/{helper_id}"
    )


@mcp.tool()
async def list_helpers(domain: str) -> Any:
    """List helpers of the given domain in the managed package."""
    return await _request("GET", f"/api/automation_api/helpers/{domain}")


@mcp.tool()
async def get_helper(domain: str, helper_id: str) -> Any:
    """Return the config of a single helper in the managed package."""
    return await _request(
        "GET", f"/api/automation_api/helpers/{domain}/{helper_id}"
    )


@mcp.tool()
async def upsert_template_entity(
    template_type: str, name: str, config: dict[str, Any]
) -> Any:
    """Create or update a template entity (reloads the template domain).

    Args:
        template_type: One of sensor / binary_sensor / switch / button /
                       number / select.
        name: Display name; also the unique key used for upsert.
        config: Template config (e.g. {"state": "{{ ... }}",
                "unit_of_measurement": "d", "icon": "mdi:sprout",
                "unique_id": "...", ...}).
    """
    if template_type not in TEMPLATE_TYPES:
        return {"error": f"unsupported template type: {template_type}"}
    return await _request(
        "PUT",
        f"/api/automation_api/template/{template_type}/{name}",
        json=config,
    )


@mcp.tool()
async def delete_template_entity(template_type: str, name: str) -> Any:
    """Delete a template entity by type + name (reloads template domain)."""
    return await _request(
        "DELETE", f"/api/automation_api/template/{template_type}/{name}"
    )


@mcp.tool()
async def list_template_entities(template_type: str) -> Any:
    """List all template entities of the given type in the managed package."""
    return await _request("GET", f"/api/automation_api/template/{template_type}")


@mcp.tool()
async def get_template_entity(template_type: str, name: str) -> Any:
    """Return the config of a single template entity by type + name."""
    return await _request(
        "GET", f"/api/automation_api/template/{template_type}/{name}"
    )


@mcp.tool()
async def upsert_history_stats_sensor(name: str, config: dict[str, Any]) -> Any:
    """Create or update a history_stats sensor entry.

    A HA restart is required for it to take effect (response includes
    restart_required=true). Example config:
        {"entity_id": "binary_sensor.moestuin_regent",
         "state": "on", "type": "time",
         "end": "{{ now() }}", "duration": {"hours": 2}}
    """
    return await _request(
        "PUT",
        f"/api/automation_api/history_stats/{name}",
        json=config,
    )


@mcp.tool()
async def delete_history_stats_sensor(name: str) -> Any:
    """Delete a history_stats sensor (HA restart required)."""
    return await _request("DELETE", f"/api/automation_api/history_stats/{name}")


@mcp.tool()
async def list_history_stats_sensors() -> Any:
    """List all history_stats sensors in the managed package."""
    return await _request("GET", "/api/automation_api/history_stats")


@mcp.tool()
async def get_history_stats_sensor(name: str) -> Any:
    """Return the config of a single history_stats sensor."""
    return await _request("GET", f"/api/automation_api/history_stats/{name}")


@mcp.tool()
async def upsert_notify_group(
    name: str, services: list[str], extra: dict[str, Any] | None = None
) -> Any:
    """Create or update a notify platform:group entry.

    After writing, HA must be restarted before `notify.<name>` becomes
    available (notify does not support hot reload).

    Args:
        name: Group name; service becomes `notify.<name>`.
        services: List of notify services to aggregate, e.g.
                  ["mobile_app_sm_s911b", "mobile_app_s25"].
        extra: Optional extra top-level keys to include on the group entry.
    """
    payload: dict[str, Any] = {"services": services}
    if extra:
        payload.update(extra)
    return await _request(
        "PUT",
        f"/api/automation_api/notify_group/{name}",
        json=payload,
    )


@mcp.tool()
async def delete_notify_group(name: str) -> Any:
    """Delete a notify group (HA restart required)."""
    return await _request("DELETE", f"/api/automation_api/notify_group/{name}")


@mcp.tool()
async def list_notify_groups() -> Any:
    """List all notify groups in the managed package."""
    return await _request("GET", "/api/automation_api/notify_group")


@mcp.tool()
async def get_notify_group(name: str) -> Any:
    """Return the config of a single notify group."""
    return await _request("GET", f"/api/automation_api/notify_group/{name}")


@mcp.tool()
async def reload_config(domains: list[str] | None = None) -> Any:
    """Reload HA config.

    With no arguments → calls homeassistant.reload_all.
    With a list of domains → reloads each individually (input_boolean,
    input_datetime, template, automation, script, scene, ...).
    """
    body: dict[str, Any] = {}
    if domains:
        body["domains"] = domains
    return await _request("POST", "/api/automation_api/reload", json=body)


@mcp.tool()
async def restart_home_assistant() -> Any:
    """Schedule a Home Assistant restart (fire-and-forget).

    Use after creating/updating/deleting notify groups or history_stats
    sensors, which have no reload service.
    """
    return await _request("POST", "/api/automation_api/restart", json={})


# ---------------------------------------------------------------------------
# Lovelace dashboards (automation_api >= 0.6.0)
# ---------------------------------------------------------------------------
#
# Use "default" as url_path to target the Overview dashboard.


@mcp.tool()
async def list_dashboards() -> Any:
    """List every Lovelace dashboard (url_path, title, mode, icon)."""
    return await _request("GET", "/api/automation_api/lovelace/dashboards")


@mcp.tool()
async def create_dashboard(
    url_path: str,
    title: str,
    icon: str | None = None,
    show_in_sidebar: bool = True,
    require_admin: bool = False,
) -> Any:
    """Create a new storage-mode Lovelace dashboard.

    The dashboard is immediately visible under Settings → Dashboards and at
    `/lovelace-<url_path>`. It starts empty; add views and cards separately.

    Args:
        url_path: URL slug — e.g. 'moestuin' yields /lovelace-moestuin.
        title: Sidebar title.
        icon: MDI icon, e.g. 'mdi:sprout'.
        show_in_sidebar: Whether to show in the left sidebar.
        require_admin: Admin‑only access.
    """
    body: dict[str, Any] = {
        "url_path": url_path,
        "title": title,
        "show_in_sidebar": show_in_sidebar,
        "require_admin": require_admin,
    }
    if icon:
        body["icon"] = icon
    return await _request("POST", "/api/automation_api/lovelace/dashboards", json=body)


@mcp.tool()
async def update_dashboard_metadata(url_path: str, changes: dict[str, Any]) -> Any:
    """Update dashboard metadata (title, icon, show_in_sidebar, require_admin).

    Cannot modify the default/Overview dashboard's metadata.
    """
    return await _request(
        "PATCH",
        f"/api/automation_api/lovelace/dashboards/{url_path}",
        json=changes,
    )


@mcp.tool()
async def delete_dashboard(url_path: str) -> Any:
    """Delete a custom dashboard. The default Overview cannot be deleted."""
    return await _request(
        "DELETE", f"/api/automation_api/lovelace/dashboards/{url_path}"
    )


@mcp.tool()
async def get_dashboard_config(url_path: str = "default") -> Any:
    """Return the full Lovelace config of a dashboard.

    Structure: {"title": ..., "views": [{"title": ..., "cards": [...]}, ...]}.
    """
    return await _request("GET", f"/api/automation_api/lovelace/config/{url_path}")


@mcp.tool()
async def set_dashboard_config(url_path: str, config: dict[str, Any]) -> Any:
    """Overwrite the entire Lovelace config of a dashboard.

    `config` must contain at least `{"views": [...]}`.
    """
    return await _request(
        "PUT", f"/api/automation_api/lovelace/config/{url_path}", json=config
    )


@mcp.tool()
async def append_dashboard_view(url_path: str, view: dict[str, Any]) -> Any:
    """Append a view to a dashboard.

    A view looks like::
        {"title": "Moestuin", "path": "moestuin", "icon": "mdi:sprout",
         "cards": [ ... ]}
    """
    return await _request(
        "POST", f"/api/automation_api/lovelace/view/{url_path}", json=view
    )


@mcp.tool()
async def replace_dashboard_view(
    url_path: str, view_index: int, view: dict[str, Any]
) -> Any:
    """Replace the view at the given index."""
    return await _request(
        "PUT",
        f"/api/automation_api/lovelace/view/{url_path}/{view_index}",
        json=view,
    )


@mcp.tool()
async def delete_dashboard_view(url_path: str, view_index: int) -> Any:
    """Delete the view at the given index."""
    return await _request(
        "DELETE", f"/api/automation_api/lovelace/view/{url_path}/{view_index}"
    )


@mcp.tool()
async def append_dashboard_card(
    url_path: str, view_index: int, card: dict[str, Any]
) -> Any:
    """Append a card to the given view.

    `card` is any valid Lovelace card config (e.g. `{"type": "entities", ...}`).
    """
    return await _request(
        "POST",
        f"/api/automation_api/lovelace/card/{url_path}/{view_index}",
        json=card,
    )


@mcp.tool()
async def replace_dashboard_card(
    url_path: str, view_index: int, card_index: int, card: dict[str, Any]
) -> Any:
    """Replace a specific card within a view."""
    return await _request(
        "PUT",
        f"/api/automation_api/lovelace/card/{url_path}/{view_index}/{card_index}",
        json=card,
    )


@mcp.tool()
async def delete_dashboard_card(
    url_path: str, view_index: int, card_index: int
) -> Any:
    """Delete a specific card from a view."""
    return await _request(
        "DELETE",
        f"/api/automation_api/lovelace/card/{url_path}/{view_index}/{card_index}",
    )


# ---------------------------------------------------------------------------
# Registry management (automation_api >= 0.7.0)
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_registry_entities(
    domain: str | None = None,
    platform: str | None = None,
    device_id: str | None = None,
    area_id: str | None = None,
    config_entry_id: str | None = None,
    disabled: bool | None = None,
) -> Any:
    """List entries from HA's entity_registry with full details.

    Returns each entity with `unique_id`, `platform` (integration name),
    `device_id`, `area_id`, `name` (user-set), `original_name` (from
    integration), `disabled_by`, `hidden_by`, `config_entry_id`. Use this
    to find duplicates, orphans, or filter by integration.
    """
    params: dict[str, Any] = {}
    if domain:
        params["domain"] = domain
    if platform:
        params["platform"] = platform
    if device_id:
        params["device_id"] = device_id
    if area_id:
        params["area_id"] = area_id
    if config_entry_id:
        params["config_entry_id"] = config_entry_id
    if disabled is not None:
        params["disabled"] = "true" if disabled else "false"
    return await _request(
        "GET", "/api/automation_api/entity_registry", params=params or None
    )


@mcp.tool()
async def get_registry_entity(entity_id: str) -> Any:
    """Get full registry details for a single entity_id."""
    return await _request("GET", f"/api/automation_api/entity_registry/{entity_id}")


@mcp.tool()
async def update_registry_entity(entity_id: str, changes: dict[str, Any]) -> Any:
    """Mutate a registry entity. Supported keys in `changes`:
    `name`, `icon`, `area_id`, `new_entity_id` (rename),
    `disabled_by` (bool), `hidden_by` (bool).
    """
    return await _request(
        "PATCH", f"/api/automation_api/entity_registry/{entity_id}", json=changes
    )


@mcp.tool()
async def delete_registry_entity(entity_id: str) -> Any:
    """Remove an entity from the registry. Active integrations may re-add
    it on reload — use `delete_device` or `remove_config_entry` instead
    if the entity belongs to a still-active integration."""
    return await _request(
        "DELETE", f"/api/automation_api/entity_registry/{entity_id}"
    )


@mcp.tool()
async def list_devices(
    area_id: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    integration: str | None = None,
    config_entry_id: str | None = None,
    disabled: bool | None = None,
) -> Any:
    """List devices from HA's device_registry.

    Each item has `id`, `name`, `name_by_user`, `manufacturer`, `model`,
    `area_id`, `config_entries` (list of entry ids), `identifiers`,
    `connections`, `disabled_by`. Filter by integration to scope (e.g.
    'tuya' to find all Tuya devices).
    """
    params: dict[str, Any] = {}
    if area_id:
        params["area_id"] = area_id
    if manufacturer:
        params["manufacturer"] = manufacturer
    if model:
        params["model"] = model
    if integration:
        params["integration"] = integration
    if config_entry_id:
        params["config_entry_id"] = config_entry_id
    if disabled is not None:
        params["disabled"] = "true" if disabled else "false"
    return await _request(
        "GET", "/api/automation_api/device_registry", params=params or None
    )


@mcp.tool()
async def get_device(device_id: str) -> Any:
    """Get full registry details for a single device id."""
    return await _request("GET", f"/api/automation_api/device_registry/{device_id}")


@mcp.tool()
async def update_device(device_id: str, changes: dict[str, Any]) -> Any:
    """Mutate a device. Supported keys: `name_by_user`, `area_id`,
    `disabled_by` (bool)."""
    return await _request(
        "PATCH", f"/api/automation_api/device_registry/{device_id}", json=changes
    )


@mcp.tool()
async def delete_device(device_id: str) -> Any:
    """Remove a device from the registry. Cascades to all entities of
    that device. The owning integration may re-add it on next discovery."""
    return await _request(
        "DELETE", f"/api/automation_api/device_registry/{device_id}"
    )


@mcp.tool()
async def list_config_entries(domain: str | None = None) -> Any:
    """List installed integrations (config entries).

    Each item has `entry_id`, `domain`, `title`, `state`, `disabled_by`,
    `supports_unload`, `supports_remove_device`. Filter by `domain`
    (integration name like 'tuya' or 'wiz').
    """
    params = {"domain": domain} if domain else None
    return await _request("GET", "/api/automation_api/config_entries", params=params)


@mcp.tool()
async def get_config_entry(entry_id: str) -> Any:
    """Get full details for a single config entry."""
    return await _request("GET", f"/api/automation_api/config_entries/{entry_id}")


@mcp.tool()
async def reload_config_entry(entry_id: str) -> Any:
    """Reload an integration without restarting HA."""
    return await _request(
        "POST", f"/api/automation_api/config_entries/{entry_id}/reload", json={}
    )


@mcp.tool()
async def disable_config_entry(entry_id: str) -> Any:
    """Soft-disable an integration (its devices/entities go unavailable
    but registry entries remain)."""
    return await _request(
        "POST", f"/api/automation_api/config_entries/{entry_id}/disable", json={}
    )


@mcp.tool()
async def enable_config_entry(entry_id: str) -> Any:
    """Re-enable a previously disabled integration."""
    return await _request(
        "POST", f"/api/automation_api/config_entries/{entry_id}/enable", json={}
    )


@mcp.tool()
async def remove_config_entry(entry_id: str) -> Any:
    """Fully remove an integration. Cascades: all its devices and
    entities are removed from the registries. Irreversible — to restore,
    re-add the integration via Settings → Devices & services."""
    return await _request(
        "DELETE", f"/api/automation_api/config_entries/{entry_id}"
    )


# ---------------------------------------------------------------------------
# Recorder-backed history (automation_api >= 0.8.0)
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_history(
    entity_id: str,
    hours: float | None = None,
    days: float | None = None,
    start: str | None = None,
    end: str | None = None,
    significant: bool = False,
    minimal: bool = True,
    no_attributes: bool = True,
) -> Any:
    """Fetch state-change history for one or more entities from HA's recorder.

    Default window: last 24 hours. Use this to diagnose flapping sensors
    (count of changes) or to inspect when an automation last ran.

    Args:
        entity_id: A single entity id, or comma-separated list for multiple
                   (e.g. 'sensor.x,sensor.y').
        hours: Window length in hours, ending at `end` (default now).
        days: Window length in days. Ignored if `hours` is set.
        start: ISO-format start datetime (e.g. '2026-05-22T00:00:00+00:00').
               Overrides `hours`/`days`.
        end: ISO-format end datetime (default: now).
        significant: If true, use `get_significant_states` (HA's filtered
                     view). Default false = every recorded state change.
        minimal: Smaller response shape (state + last_changed only).
                 Default true.
        no_attributes: Strip attributes from the response. Default true.

    Returns: {start, end, counts: {entity_id: n}, items: {entity_id: [...]}}.
    `counts` is the quickest way to see how often a sensor flipped.
    """
    params: dict[str, Any] = {"entity_id": entity_id}
    if hours is not None:
        params["hours"] = str(hours)
    if days is not None:
        params["days"] = str(days)
    if start:
        params["start"] = start
    if end:
        params["end"] = end
    if significant:
        params["significant"] = "true"
    if not minimal:
        params["minimal"] = "false"
    if not no_attributes:
        params["no_attributes"] = "false"
    return await _request("GET", "/api/automation_api/history", params=params)


# ---------------------------------------------------------------------------
# Native HA REST API
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_state(entity_id: str) -> Any:
    """Get the current state of any HA entity via the native REST API."""
    return await _request("GET", f"/api/states/{entity_id}")


@mcp.tool()
async def call_service(
    domain: str,
    service: str,
    data: dict[str, Any] | None = None,
) -> Any:
    """Call any Home Assistant service via the native REST API.

    Example: domain='light', service='turn_on',
    data={'entity_id': 'light.kitchen', 'brightness': 200}.
    """
    return await _request(
        "POST", f"/api/services/{domain}/{service}", json=data or {}
    )


def main() -> None:
    try:
        _require_config()
    except RuntimeError as e:
        print(f"[ha-automation-mcp] {e}", file=sys.stderr)
        sys.exit(1)
    mcp.run()


if __name__ == "__main__":
    main()
