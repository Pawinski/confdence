"""MCP tool bodies. Every call goes through consent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mcp_auth import AuthRequired, agent_state, connect_state, require_agent, require_session
from mcp_consent import ConsentOff, is_enabled, load_consent, load_snapshot, save_snapshot

VALID_ABO = {"A", "B", "AB", "O"}
VALID_RH = {"+", "-"}
VALID_SOURCES = {"self", "lab", "booklet"}
VALID_SEV = {"sev1", "sev2", "sev3", "sev4"}
VALID_STATUS = {"active", "monitoring", "resolved"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nid(prefix: str) -> str:
    return prefix + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")


def status() -> dict[str, Any]:
    return {
        "enabled": is_enabled(),
        "auth": connect_state(),
        "agent": agent_state(),
        "consent": load_consent(),
    }


def get_record() -> dict[str, Any]:
    return load_snapshot()


def update_record(patch: dict[str, Any]) -> dict[str, Any]:
    snap = load_snapshot()
    record = dict(snap.get("record") or {})
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")
    for key in (
        "display_name",
        "preferred_lang",
        "blood_abo",
        "blood_rh",
        "blood_source",
        "blood_confirmed_on",
        "allergies",
        "medications",
        "conditions",
        "hospitals",
        "professionals",
        "emergency_name",
        "emergency_phone",
    ):
        if key in patch:
            record[key] = patch[key]
    abo, rh = record.get("blood_abo"), record.get("blood_rh")
    if abo and abo not in VALID_ABO:
        raise ValueError("invalid blood_abo")
    if rh and rh not in VALID_RH:
        raise ValueError("invalid blood_rh")
    if bool(abo) != bool(rh):
        raise ValueError("incomplete blood type")
    if abo and record.get("blood_source") not in VALID_SOURCES:
        raise ValueError("invalid blood_source")
    record["blood_type"] = f"{abo}{rh}" if abo and rh else None
    record["updated_at"] = _now()
    save_snapshot(record, snap.get("incidents") or [])
    return {"record": record}


def list_incidents() -> list[Any]:
    return list(load_snapshot().get("incidents") or [])


def declare_incident(
    title: str,
    severity: str = "sev3",
    commander_name: str = "",
    commander_phone: str = "",
) -> dict[str, Any]:
    title = (title or "").strip()
    if not title:
        raise ValueError("title required")
    if severity not in VALID_SEV:
        raise ValueError("invalid severity")
    snap = load_snapshot()
    incidents = list(snap.get("incidents") or [])
    now = _now()
    inc = {
        "id": _nid("inc_"),
        "title": title[:120],
        "severity": severity,
        "status": "active",
        "commander_name": (commander_name or "")[:80],
        "commander_phone": (commander_phone or "")[:32],
        "commander_notified_at": None,
        "created_at": now,
        "resolved_at": None,
        "events": [
            {
                "id": _nid("evt_"),
                "at": now,
                "kind": "declared",
                "text": title,
            }
        ],
    }
    incidents.insert(0, inc)
    save_snapshot(snap.get("record") or {}, incidents)
    return inc


def _mutate_incident(incident_id: str, fn: Any) -> dict[str, Any]:
    snap = load_snapshot()
    incidents = list(snap.get("incidents") or [])
    found = None
    for i, inc in enumerate(incidents):
        if inc.get("id") == incident_id:
            found = fn(dict(inc))
            incidents[i] = found
            break
    if found is None:
        raise ValueError("incident not found")
    save_snapshot(snap.get("record") or {}, incidents)
    return found


def add_incident_event(incident_id: str, kind: str, text: str) -> dict[str, Any]:
    if kind not in {"note", "step"}:
        raise ValueError("kind must be note or step")
    trimmed = (text or "").strip()
    if not trimmed:
        raise ValueError("empty")

    def add(inc: dict[str, Any]) -> dict[str, Any]:
        events = list(inc.get("events") or [])
        events.append({"id": _nid("evt_"), "at": _now(), "kind": kind, "text": trimmed[:500]})
        inc["events"] = events
        return inc

    return _mutate_incident(incident_id, add)


def set_incident_status(incident_id: str, status_value: str) -> dict[str, Any]:
    if status_value not in VALID_STATUS:
        raise ValueError("invalid status")

    def set_status(inc: dict[str, Any]) -> dict[str, Any]:
        inc["status"] = status_value
        inc["resolved_at"] = _now() if status_value == "resolved" else None
        events = list(inc.get("events") or [])
        events.append(
            {
                "id": _nid("evt_"),
                "at": _now(),
                "kind": "status",
                "text": status_value,
                "status": status_value,
            }
        )
        inc["events"] = events
        return inc

    return _mutate_incident(incident_id, set_status)


def call(name: str, arguments: dict[str, Any] | None = None) -> Any:
    args = arguments or {}
    if name == "mcp_status":
        return status()
    require_session()
    require_agent()
    if not is_enabled():
        raise ConsentOff(
            "MCP is off. The user must enable it in Confdence and accept every risk."
        )
    if name == "get_record":
        return get_record()
    if name == "update_record":
        return update_record(args.get("patch") or args)
    if name == "list_incidents":
        return list_incidents()
    if name == "declare_incident":
        return declare_incident(
            str(args.get("title") or ""),
            str(args.get("severity") or "sev3"),
            str(args.get("commander_name") or ""),
            str(args.get("commander_phone") or ""),
        )
    if name == "add_incident_note":
        return add_incident_event(str(args.get("incident_id") or ""), "note", str(args.get("text") or ""))
    if name == "add_incident_step":
        return add_incident_event(str(args.get("incident_id") or ""), "step", str(args.get("text") or ""))
    if name == "set_incident_status":
        return set_incident_status(str(args.get("incident_id") or ""), str(args.get("status") or ""))
    raise ValueError("unknown tool: " + name)


def dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)
