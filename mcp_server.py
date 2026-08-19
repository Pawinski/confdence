#!/usr/bin/env python3
"""Confdence MCP server. Tools refuse until on-disk consent is current."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_consent import ConsentOff
from mcp_tools import call, dump

mcp = FastMCP("confdence")


def _run(name: str, **kwargs: object) -> str:
    try:
        return dump(call(name, kwargs))
    except ConsentOff as exc:
        return dump({"error": "consent_off", "message": str(exc)})
    except ValueError as exc:
        return dump({"error": "invalid", "message": str(exc)})


@mcp.tool()
def mcp_status() -> str:
    """Whether the user has turned Confdence MCP on and accepted the risks."""
    return _run("mcp_status")


@mcp.tool()
def get_record() -> str:
    """Read the patient's record and incidents. Requires MCP consent."""
    return _run("get_record")


@mcp.tool()
def update_record(patch: dict) -> str:
    """Update fields on the patient's record. Requires MCP consent."""
    return _run("update_record", patch=patch)


@mcp.tool()
def list_incidents() -> str:
    """List health incidents. Requires MCP consent."""
    return _run("list_incidents")


@mcp.tool()
def declare_incident(
    title: str,
    severity: str = "sev3",
    commander_name: str = "",
    commander_phone: str = "",
) -> str:
    """Declare a health incident. Requires MCP consent."""
    return _run(
        "declare_incident",
        title=title,
        severity=severity,
        commander_name=commander_name,
        commander_phone=commander_phone,
    )


@mcp.tool()
def add_incident_note(incident_id: str, text: str) -> str:
    """Append a note to an incident log. Requires MCP consent."""
    return _run("add_incident_note", incident_id=incident_id, text=text)


@mcp.tool()
def add_incident_step(incident_id: str, text: str) -> str:
    """Append a step to an incident log. Requires MCP consent."""
    return _run("add_incident_step", incident_id=incident_id, text=text)


@mcp.tool()
def set_incident_status(incident_id: str, status: str) -> str:
    """Set incident status: active, monitoring, or resolved. Requires MCP consent."""
    return _run("set_incident_status", incident_id=incident_id, status=status)


if __name__ == "__main__":
    mcp.run()
