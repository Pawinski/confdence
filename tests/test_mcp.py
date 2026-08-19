import json
import os
from pathlib import Path

os.environ["HEALTH_TESTING"] = "1"

import mcp_auth
import mcp_consent
import mcp_tools
from fastapi.testclient import TestClient

import main
from mcp_auth import AuthRequired
from mcp_consent import CONSENT_VERSION, REQUIRED_ACKS, ConsentOff


def _home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "confdence-home"
    monkeypatch.setenv("CONFDENCE_HOME", str(root))
    return root


def test_mcp_off_by_default(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    assert mcp_consent.is_enabled() is False
    status = mcp_tools.call("mcp_status")
    assert status["enabled"] is False


def test_tools_refuse_without_consent(tmp_path: Path, monkeypatch) -> None:
    _unlock(tmp_path, monkeypatch)
    monkeypatch.setenv("CONFDENCE_AGENT_TOKEN", mcp_auth.mint_agent_token())
    try:
        mcp_tools.call("get_record")
        assert False, "expected ConsentOff"
    except ConsentOff:
        pass


def test_partial_acks_do_not_enable(tmp_path: Path, monkeypatch) -> None:
    _unlock(tmp_path, monkeypatch)
    try:
        mcp_consent.enable(["agents_read"])
        assert False, "expected ValueError"
    except ValueError:
        pass
    assert mcp_consent.is_enabled() is False


def _unlock(tmp_path: Path, monkeypatch, password: str = "correct-horse") -> None:
    _home(tmp_path, monkeypatch)
    mcp_auth.set_password(password)


def test_enable_requires_password(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    try:
        mcp_consent.enable(list(REQUIRED_ACKS))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_tools_refuse_when_locked(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    mcp_auth.set_password("correct-horse")
    mcp_consent.enable(list(REQUIRED_ACKS))
    mcp_auth.lock()
    try:
        mcp_tools.call("get_record")
        assert False, "expected AuthRequired"
    except AuthRequired:
        pass


def test_enable_then_read_write(tmp_path: Path, monkeypatch) -> None:
    _unlock(tmp_path, monkeypatch)
    mcp_consent.enable(list(REQUIRED_ACKS))
    assert mcp_consent.is_enabled() is True
    monkeypatch.setenv("CONFDENCE_AGENT_TOKEN", mcp_auth.mint_agent_token())
    mcp_tools.call(
        "update_record",
        {
            "display_name": "Alexander Pawinski",
            "blood_abo": "O",
            "blood_rh": "+",
            "blood_source": "lab",
        },
    )
    snap = mcp_tools.call("get_record")
    assert snap["record"]["blood_type"] == "O+"
    inc = mcp_tools.call("declare_incident", {"title": "reaction", "severity": "sev2"})
    assert inc["status"] == "active"
    mcp_tools.call("add_incident_note", {"incident_id": inc["id"], "text": "started"})
    mcp_consent.disable()
    assert mcp_consent.is_enabled() is False
    try:
        mcp_tools.call("get_record")
        assert False, "expected ConsentOff"
    except ConsentOff:
        pass


def test_stale_consent_version_is_off(tmp_path: Path, monkeypatch) -> None:
    home = _home(tmp_path, monkeypatch)
    home.mkdir(parents=True)
    (home / "consent.json").write_text(
        json.dumps(
            {
                "version": "old",
                "enabled": True,
                "acknowledged": list(REQUIRED_ACKS),
            }
        ),
        encoding="utf-8",
    )
    assert mcp_consent.is_enabled() is False


def test_install_pack(tmp_path: Path, monkeypatch) -> None:
    _unlock(tmp_path, monkeypatch)
    pack = tmp_path / "pack.json"
    pack.write_text(
        json.dumps(
            {
                "consent": {
                    "version": CONSENT_VERSION,
                    "enabled": True,
                    "acknowledged": list(REQUIRED_ACKS),
                },
                "record": {"display_name": "Alexander Pawinski", "blood_abo": None},
                "incidents": [],
            }
        ),
        encoding="utf-8",
    )
    mcp_consent.install_pack(pack)
    assert mcp_consent.is_enabled() is True
    token = mcp_auth.mint_agent_token()
    monkeypatch.setenv("CONFDENCE_AGENT_TOKEN", token)
    assert mcp_tools.call("get_record")["record"]["display_name"] == "Alexander Pawinski"


def test_agent_must_present_token(tmp_path: Path, monkeypatch) -> None:
    _unlock(tmp_path, monkeypatch)
    mcp_consent.enable(list(REQUIRED_ACKS))
    try:
        mcp_tools.call("get_record")
        assert False, "expected AuthRequired"
    except AuthRequired:
        pass
    token = mcp_auth.mint_agent_token()
    monkeypatch.setenv("CONFDENCE_AGENT_TOKEN", "wrong-token")
    try:
        mcp_tools.call("get_record")
        assert False, "expected AuthRequired"
    except AuthRequired:
        pass
    monkeypatch.setenv("CONFDENCE_AGENT_TOKEN", token)
    assert "record" in mcp_tools.call("get_record")


def test_server_refuses_agent_without_token(tmp_path: Path, monkeypatch) -> None:
    _unlock(tmp_path, monkeypatch)
    mcp_consent.enable(list(REQUIRED_ACKS))
    mcp_auth.mint_agent_token()
    import subprocess
    import sys

    env = os.environ.copy()
    env["CONFDENCE_HOME"] = str(tmp_path / "confdence-home")
    env.pop("CONFDENCE_AGENT_TOKEN", None)
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "mcp_server.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1
    assert "agent must authenticate" in result.stderr


def test_server_will_not_start_when_locked(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    import subprocess
    import sys

    env = os.environ.copy()
    env["CONFDENCE_HOME"] = str(tmp_path / "confdence-home")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "mcp_server.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1
    assert "authenticate first" in result.stderr


def test_ui_requires_consent_copy() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "static" / "index.html").read_text(encoding="utf-8")
    js = (root / "static" / "js" / "mcp.js").read_text(encoding="utf-8")
    assert "mcp-dialog" in html
    assert 'disabled' in html
    assert "enabled: false" in js
    assert "agents_read" in js
    assert "law5" in js


def test_api_consent_gate(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    client = TestClient(main.app)
    client.get("/")
    token = client.cookies["health_csrf"]
    status = client.get("/api/mcp/status").json()
    assert status["enabled"] is False
    assert status["has_password"] is False
    unauth = client.post(
        "/api/mcp/consent",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"enabled": True, "acknowledged": list(REQUIRED_ACKS)},
    )
    assert unauth.status_code == 401
    sett = client.post(
        "/api/auth/set",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"password": "correct-horse"},
    )
    assert sett.status_code == 200
    token = client.cookies["health_csrf"]
    denied = client.post(
        "/api/mcp/consent",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"enabled": True, "acknowledged": ["agents_read"]},
    )
    assert denied.status_code == 400
    ok = client.post(
        "/api/mcp/consent",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"enabled": True, "acknowledged": list(REQUIRED_ACKS)},
    )
    assert ok.status_code == 200
    assert ok.json()["enabled"] is True
    snap = client.put(
        "/api/mcp/snapshot",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"record": {"display_name": "Alexander Pawinski"}, "incidents": []},
    )
    assert snap.status_code == 200
    off = client.post(
        "/api/mcp/consent",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"enabled": False},
    )
    assert off.json()["enabled"] is False


def test_bad_unlock_is_refused(tmp_path: Path, monkeypatch) -> None:
    _home(tmp_path, monkeypatch)
    mcp_auth.set_password("correct-horse")
    mcp_auth.lock()
    try:
        mcp_auth.unlock("wrong-password-value")
        assert False, "expected AuthRequired"
    except AuthRequired:
        pass
    assert mcp_auth.session_valid() is False
