import os
from datetime import timedelta
from pathlib import Path

os.environ["HEALTH_TESTING"] = "1"

from fastapi.testclient import TestClient

import main
from store import Store


def _client(tmp_path: Path) -> TestClient:
    main.store = Store(tmp_path / "health.db")
    main.store.seed_demo_if_empty()
    return TestClient(main.app)


def _csrf(client: TestClient) -> str:
    client.get("/")
    return client.cookies["health_csrf"]


def _login(client: TestClient) -> None:
    token = _csrf(client)
    res = client.post(
        "/api/session",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={},
    )
    assert res.status_code == 200


def test_healthz(tmp_path: Path) -> None:
    client = _client(tmp_path)
    res = client.get("/healthz")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_home_is_offline_wallet(tmp_path: Path) -> None:
    client = _client(tmp_path)
    res = client.get("/")
    assert res.status_code == 200
    assert "Confdence" in res.text
    assert "Camille" not in res.text
    assert "Ouvrir le dossier démo" not in res.text


def test_me_requires_session(tmp_path: Path) -> None:
    client = _client(tmp_path)
    assert client.get("/api/me").status_code == 401


def test_session_requires_csrf(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.get("/")
    res = client.post("/api/session", json={})
    assert res.status_code == 403


def test_seed_is_owner_without_invented_facts(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client)
    record = client.get("/api/me").json()["record"]
    assert record["display_name"] == "Alexander Pawinski"
    assert record["blood_type"] is None
    assert record["allergies"] == []


def test_update_blood_type(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client)
    token = client.cookies["health_csrf"]
    res = client.put(
        "/api/me",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={
            "display_name": "Alexander Pawinski",
            "blood_abo": "A",
            "blood_rh": "-",
            "blood_source": "self",
            "blood_confirmed_on": "2026-01-15",
            "allergies": [],
            "medications": [],
            "conditions": [],
        },
    )
    assert res.status_code == 200
    assert res.json()["record"]["blood_type"] == "A-"
    assert res.json()["record"]["blood_source"] == "self"


def test_update_hospitals_and_professionals(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client)
    token = client.cookies["health_csrf"]
    res = client.put(
        "/api/me",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={
            "display_name": "Alexander Pawinski",
            "blood_abo": None,
            "blood_rh": None,
            "hospitals": [{"name": "CHUM", "city": "Montréal", "note": "rattachement"}],
            "professionals": [
                {"name": "Dre Martin", "role": "médecin de famille", "phone": "514-555-0100"}
            ],
        },
    )
    assert res.status_code == 200
    record = res.json()["record"]
    assert record["hospitals"][0]["name"] == "CHUM"
    assert record["professionals"][0]["role"] == "médecin de famille"


def test_rejects_bad_blood_type(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client)
    token = client.cookies["health_csrf"]
    res = client.put(
        "/api/me",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={"blood_abo": "Z", "blood_rh": "+", "blood_source": "lab"},
    )
    assert res.status_code == 400


def test_share_create_view_revoke(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _login(client)
    token = client.cookies["health_csrf"]
    client.put(
        "/api/me",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={
            "display_name": "Alexander Pawinski",
            "blood_abo": "O",
            "blood_rh": "+",
            "blood_source": "lab",
            "allergies": [],
            "medications": [],
            "conditions": [],
        },
    )
    created = client.post(
        "/api/shares",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
        json={},
    )
    assert created.status_code == 200
    body = created.json()
    page = client.get(f"/s/{body['share']['token']}")
    assert "O+" in page.text
    assert "Alexander Pawinski" in page.text
    assert "<svg" in body["qr_svg"]
    public = client.get(f"/s/{body['share']['token']}/json")
    assert public.json()["record"]["blood_type"] == "O+"

    revoked = client.delete(
        f"/api/shares/{body['share']['id']}",
        headers={"X-CSRF-Token": token, "Origin": "http://testserver"},
    )
    assert revoked.status_code == 200
    assert client.get(f"/s/{body['share']['token']}").status_code == 404


def test_expired_share_is_gone(tmp_path: Path) -> None:
    db = tmp_path / "health.db"
    store = Store(db)
    patient_id = store.seed_demo_if_empty()
    store.create_share(patient_id, "sid", "tok123", timedelta(hours=-1), None)
    main.store = store
    client = TestClient(main.app)
    assert client.get("/s/tok123").status_code == 404
