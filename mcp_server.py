#!/usr/bin/env python3
"""Confdence MCP server. Will not start until the holder is unlocked and has consented."""

from __future__ import annotations

import sys


def _refuse() -> int:
    from mcp_auth import connect_state
    from mcp_consent import is_enabled

    state = connect_state()
    if state != "unlocked":
        sys.stderr.write(
            "Confdence MCP: authenticate first "
            f"({state}). python3 mcp_auth.py unlock\n"
        )
        return 1
    if not is_enabled():
        sys.stderr.write(
            "Confdence MCP: consent is off. Enable it in the app, then install the pack.\n"
        )
        return 1
    return 0


def _run() -> None:
    from mcp.server.fastmcp import FastMCP

    from mcp_auth import AuthRequired
    from mcp_consent import ConsentOff
    from mcp_tools import call, dump

    mcp = FastMCP("confdence")

    def _tool(name: str, **kwargs: object) -> str:
        try:
            return dump(call(name, kwargs))
        except AuthRequired as exc:
            return dump({"error": "auth_required", "message": str(exc)})
        except ConsentOff as exc:
            return dump({"error": "consent_off", "message": str(exc)})
        except ValueError as exc:
            return dump({"error": "invalid", "message": str(exc)})

    @mcp.tool()
    def mcp_status() -> str:
        """Whether the user has authenticated and turned Confdence MCP on."""
        return _tool("mcp_status")

    @mcp.tool()
    def get_record() -> str:
        """Read the patient's record and incidents. Requires unlock and consent."""
        return _tool("get_record")

    @mcp.tool()
    def update_record(patch: dict) -> str:
        """Update fields on the patient's record. Requires unlock and consent."""
        return _tool("update_record", patch=patch)

    @mcp.tool()
    def list_incidents() -> str:
        """List health incidents. Requires unlock and consent."""
        return _tool("list_incidents")

    @mcp.tool()
    def declare_incident(
        title: str,
        severity: str = "sev3",
        commander_name: str = "",
        commander_phone: str = "",
    ) -> str:
        """Declare a health incident. Requires unlock and consent."""
        return _tool(
            "declare_incident",
            title=title,
            severity=severity,
            commander_name=commander_name,
            commander_phone=commander_phone,
        )

    @mcp.tool()
    def add_incident_note(incident_id: str, text: str) -> str:
        """Append a note to an incident log. Requires unlock and consent."""
        return _tool("add_incident_note", incident_id=incident_id, text=text)

    @mcp.tool()
    def add_incident_step(incident_id: str, text: str) -> str:
        """Append a step to an incident log. Requires unlock and consent."""
        return _tool("add_incident_step", incident_id=incident_id, text=text)

    @mcp.tool()
    def set_incident_status(incident_id: str, status: str) -> str:
        """Set incident status: active, monitoring, or resolved."""
        return _tool("set_incident_status", incident_id=incident_id, status=status)

    mcp.run()


if __name__ == "__main__":
    code = _refuse()
    if code:
        sys.exit(code)
    _run()
