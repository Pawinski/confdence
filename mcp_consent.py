"""On-disk MCP consent. Off unless the current version is fully acknowledged."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONSENT_VERSION = "2026-08-18"
REQUIRED_ACKS = (
    "agents_read",
    "agents_write",
    "law5",
    "leaves_device",
    "can_revoke",
)


class ConsentOff(Exception):
    pass


def home() -> Path:
    raw = os.environ.get("CONFDENCE_HOME")
    return Path(raw).expanduser() if raw else Path.home() / ".confdence"


def consent_path() -> Path:
    return home() / "consent.json"


def record_path() -> Path:
    return home() / "record.json"


def incidents_path() -> Path:
    return home() / "incidents.json"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_consent() -> dict[str, Any]:
    path = consent_path()
    if not path.exists():
        return {"version": CONSENT_VERSION, "enabled": False, "acknowledged": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": CONSENT_VERSION, "enabled": False, "acknowledged": []}
    if not isinstance(data, dict):
        return {"version": CONSENT_VERSION, "enabled": False, "acknowledged": []}
    return data


def is_enabled(data: dict[str, Any] | None = None) -> bool:
    row = data if data is not None else load_consent()
    if not row.get("enabled"):
        return False
    if row.get("version") != CONSENT_VERSION:
        return False
    acks = set(row.get("acknowledged") or [])
    return set(REQUIRED_ACKS).issubset(acks)


def require() -> None:
    if not is_enabled():
        raise ConsentOff(
            "MCP is off. Turn it on in Confdence and accept every risk, "
            "then install the agent pack."
        )


def _write(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def enable(acknowledged: list[str]) -> dict[str, Any]:
    from mcp_auth import has_password

    if not has_password():
        raise ValueError("set a password before enabling MCP")
    acks = [a for a in REQUIRED_ACKS if a in set(acknowledged)]
    if set(acks) != set(REQUIRED_ACKS):
        missing = [a for a in REQUIRED_ACKS if a not in set(acknowledged)]
        raise ValueError("missing acknowledgements: " + ",".join(missing))
    row = {
        "version": CONSENT_VERSION,
        "enabled": True,
        "consented_at": utcnow(),
        "acknowledged": list(REQUIRED_ACKS),
    }
    _write(consent_path(), row)
    return row


def disable() -> dict[str, Any]:
    row = {
        "version": CONSENT_VERSION,
        "enabled": False,
        "consented_at": None,
        "acknowledged": [],
        "disabled_at": utcnow(),
    }
    _write(consent_path(), row)
    return row


def save_snapshot(record: dict[str, Any], incidents: list[Any]) -> None:
    from mcp_auth import require_session

    require()
    require_session()
    _write(record_path(), record)
    _write(incidents_path(), incidents)


def load_snapshot() -> dict[str, Any]:
    require()
    record: dict[str, Any] = {}
    incidents: list[Any] = []
    if record_path().exists():
        record = json.loads(record_path().read_text(encoding="utf-8"))
    if incidents_path().exists():
        loaded = json.loads(incidents_path().read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            incidents = loaded
    return {"record": record, "incidents": incidents}


def install_pack(path: Path) -> dict[str, Any]:
    from mcp_auth import has_password, install_agent_hash, install_verifier

    data = json.loads(path.read_text(encoding="utf-8"))
    auth = data.get("auth")
    if isinstance(auth, dict) and not has_password():
        install_verifier(auth)
    agent = data.get("agent")
    if isinstance(agent, dict) and agent.get("hash"):
        install_agent_hash(agent)
    consent = data.get("consent") or {}
    enable(list(consent.get("acknowledged") or []))
    record = data.get("record") if isinstance(data.get("record"), dict) else {}
    incidents = data.get("incidents") if isinstance(data.get("incidents"), list) else []
    _write(record_path(), record)
    _write(incidents_path(), incidents)
    return load_consent()


def main() -> None:
    parser = argparse.ArgumentParser(description="Confdence MCP consent")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("disable")
    inst = sub.add_parser("install")
    inst.add_argument("pack")
    args = parser.parse_args()
    if args.cmd == "status":
        print(json.dumps({"enabled": is_enabled(), "consent": load_consent()}, indent=2))
        return
    if args.cmd == "disable":
        print(json.dumps(disable(), indent=2))
        return
    print(json.dumps(install_pack(Path(args.pack)), indent=2))


if __name__ == "__main__":
    main()
