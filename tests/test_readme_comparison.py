"""Checks that the README comparison section stays in line with server.py."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _server_tools() -> set[str]:
    """Names of all functions decorated with @mcp.tool() in server.py."""
    tree = ast.parse((ROOT / "server.py").read_text(encoding="utf-8"))
    tools = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if ast.unparse(dec).startswith("mcp.tool"):
                tools.add(node.name)
    return tools


def _comparison_section() -> str:
    match = re.search(r"^## Comparison\n(.*?)(?=^## )", README, re.M | re.S)
    assert match, "README.md has no '## Comparison' section"
    return match.group(1)


def _table_rows() -> list[list[str]]:
    rows = []
    for line in _comparison_section().splitlines():
        if not line.startswith("|") or set(line) <= set("|- "):
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def test_table_compares_the_three_options():
    header = _table_rows()[0]
    assert header == ["Capability", "Built-in `mcp_server`", "ha-mcp", "This MCP"]
    assert all(len(row) == 4 for row in _table_rows())


def test_every_checkmark_for_this_mcp_names_existing_tools():
    tools = _server_tools()
    checked = 0
    for capability, _builtin, _ha_mcp, ours in _table_rows()[1:]:
        if not ours.startswith("✅"):
            continue
        checked += 1
        # A parenthesised remark may mention non-tool names; drop it.
        named = re.findall(r"`(\w+)`", re.sub(r"\(.*?\)", "", ours))
        assert named, f"{capability!r}: ✅ without a tool name"
        missing = [name for name in named if name not in tools]
        assert not missing, f"{capability!r}: not in server.py: {missing}"
    assert checked > 0


def test_partly_cells_for_this_mcp_name_existing_tools():
    tools = _server_tools()
    for capability, _builtin, _ha_mcp, ours in _table_rows()[1:]:
        if not ours.startswith("partly"):
            continue
        named = re.findall(r"`(\w+)`", ours)
        assert named and set(named) <= tools, capability


def test_tool_count_matches_server():
    count = len(_server_tools())
    assert f"the {count} tools in [`server.py`](server.py)" in _comparison_section()


def test_tools_named_in_prose_exist():
    section = _comparison_section()
    prose = section[section.index("### Where this MCP is the better fit"):]
    tools = _server_tools()
    for name in re.findall(r"`(\w+)`", prose):
        if "_" in name and not name.startswith(("input_", "history_", "mcp_")):
            assert name in tools, name


def test_section_links_to_sources():
    section = _comparison_section()
    assert "https://www.home-assistant.io/integrations/mcp_server/" in section
    assert "https://github.com/homeassistant-ai/ha-mcp" in section
    assert "https://github.com/aderik/ha-automation-api" in section


def test_section_lists_what_is_missing():
    section = _comparison_section()
    assert "### What is still missing" in section
    missing = section[section.index("### What is still missing"):]
    assert len(re.findall(r"^- ", missing, re.M)) >= 5
