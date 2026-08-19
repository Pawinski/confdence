"""Password + short session. Agents cannot connect until this is unlocked."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp_consent import home, utcnow, _write

ALGO = "pbkdf2-sha256"
ITERS = 210_000
DKLEN = 32
MIN_PASSWORD = 10
SESSION_TTL = timedelta(hours=12)
LOCKOUT_AFTER = 5
LOCKOUT_MINUTES = 15
AUTH_COOKIE = "confdence_auth"


class AuthRequired(Exception):
    pass


class LockedOut(Exception):
    pass


def auth_path() -> Path:
    return home() / "auth.json"


def session_path() -> Path:
    return home() / "session.json"


def guard_path() -> Path:
    return home() / "unlock-guard.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(iso: str) -> datetime:
    return datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _digest(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERS, dklen=DKLEN)


def has_password() -> bool:
    path = auth_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("salt") and data.get("hash"))


def verifier() -> dict[str, Any] | None:
    if not has_password():
        return None
    return json.loads(auth_path().read_text(encoding="utf-8"))


def install_verifier(row: dict[str, Any]) -> None:
    if row.get("algo") != ALGO:
        raise ValueError("unsupported auth algo")
    if not row.get("salt") or not row.get("hash"):
        raise ValueError("invalid verifier")
    _write(
        auth_path(),
        {
            "algo": ALGO,
            "iters": int(row.get("iters") or ITERS),
            "salt": str(row["salt"]),
            "hash": str(row["hash"]),
            "created_at": row.get("created_at") or utcnow(),
        },
    )


def set_password(password: str) -> dict[str, Any]:
    pw = (password or "").strip()
    if len(pw) < MIN_PASSWORD:
        raise ValueError("password too short")
    salt = secrets.token_bytes(16)
    digest = _digest(pw, salt)
    row = {
        "algo": ALGO,
        "iters": ITERS,
        "salt": salt.hex(),
        "hash": digest.hex(),
        "created_at": utcnow(),
    }
    _write(auth_path(), row)
    return unlock(pw)


def _guard() -> dict[str, Any]:
    path = guard_path()
    if not path.exists():
        return {"fails": 0, "locked_until": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"fails": 0, "locked_until": None}
    return data if isinstance(data, dict) else {"fails": 0, "locked_until": None}


def _check_lockout() -> None:
    row = _guard()
    until = row.get("locked_until")
    if until:
        try:
            if _parse(until) > _now():
                raise LockedOut("too many unlock attempts")
        except ValueError:
            pass


def _fail() -> None:
    row = _guard()
    fails = int(row.get("fails") or 0) + 1
    locked_until = None
    if fails >= LOCKOUT_AFTER:
        locked_until = (_now() + timedelta(minutes=LOCKOUT_MINUTES)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        fails = 0
    _write(guard_path(), {"fails": fails, "locked_until": locked_until})


def _clear_fails() -> None:
    _write(guard_path(), {"fails": 0, "locked_until": None})


def verify_password(password: str) -> bool:
    if not has_password():
        return False
    row = verifier() or {}
    try:
        salt = bytes.fromhex(str(row["salt"]))
        expected = bytes.fromhex(str(row["hash"]))
        iters = int(row.get("iters") or ITERS)
    except (KeyError, ValueError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iters, dklen=DKLEN
    )
    return hmac.compare_digest(digest, expected)


def session_valid() -> bool:
    path = session_path()
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        expires = _parse(str(data["expires_at"]))
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return False
    return expires > _now() and bool(data.get("token_hash"))


def cookie_matches(token: str | None) -> bool:
    if not token or not session_valid():
        return False
    data = json.loads(session_path().read_text(encoding="utf-8"))
    expected = str(data.get("token_hash") or "")
    got = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return hmac.compare_digest(got, expected)


def unlock(password: str) -> dict[str, Any]:
    _check_lockout()
    if not has_password():
        raise AuthRequired("set a password first")
    if not verify_password(password):
        _fail()
        raise AuthRequired("bad password")
    _clear_fails()
    token = secrets.token_urlsafe(32)
    expires = _now() + SESSION_TTL
    _write(
        session_path(),
        {
            "token_hash": hashlib.sha256(token.encode("utf-8")).hexdigest(),
            "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    return {"token": token, "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%SZ")}


def lock() -> None:
    path = session_path()
    if path.exists():
        path.unlink()


def require_session() -> None:
    if not has_password():
        raise AuthRequired("set a password before agents can connect")
    if not session_valid():
        raise AuthRequired("unlock before agents can connect")


def connect_state() -> str:
    if not has_password():
        return "no_password"
    if not session_valid():
        return "locked"
    return "unlocked"


def main() -> None:
    parser = argparse.ArgumentParser(description="Confdence MCP auth")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("set")
    sub.add_parser("unlock")
    sub.add_parser("lock")
    args = parser.parse_args()
    if args.cmd == "status":
        print(
            json.dumps(
                {
                    "has_password": has_password(),
                    "unlocked": session_valid(),
                    "state": connect_state(),
                },
                indent=2,
            )
        )
        return
    if args.cmd == "lock":
        lock()
        print(json.dumps({"unlocked": False}))
        return
    pw = getpass.getpass("Password: ")
    if args.cmd == "set":
        print(json.dumps({"ok": True, "expires_at": set_password(pw)["expires_at"]}))
        return
    print(json.dumps({"ok": True, "expires_at": unlock(pw)["expires_at"]}))


if __name__ == "__main__":
    main()
