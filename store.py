"""SQLite store for the local single-patient record."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ISO = "%Y-%m-%dT%H:%M:%SZ"
VALID_ABO = {"A", "B", "AB", "O"}
VALID_RH = {"+", "-"}
VALID_SOURCES = {"self", "lab", "booklet"}
VALID_SEVERITY = {"mild", "moderate", "severe"}
SEVERITY_ALIASES = {
    "légère": "mild",
    "legere": "mild",
    "modérée": "moderate",
    "moderee": "moderate",
    "sévère": "severe",
    "severe": "severe",
    "sévere": "severe",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(ISO)


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, ISO).replace(tzinfo=timezone.utc)


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS patient (
                    id INTEGER PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    preferred_lang TEXT NOT NULL DEFAULT 'fr',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS facts (
                    patient_id INTEGER PRIMARY KEY REFERENCES patient(id),
                    blood_abo TEXT,
                    blood_rh TEXT,
                    blood_source TEXT,
                    blood_confirmed_on TEXT,
                    allergies_json TEXT NOT NULL DEFAULT '[]',
                    medications_json TEXT NOT NULL DEFAULT '[]',
                    conditions_json TEXT NOT NULL DEFAULT '[]',
                    hospitals_json TEXT NOT NULL DEFAULT '[]',
                    professionals_json TEXT NOT NULL DEFAULT '[]',
                    emergency_name TEXT,
                    emergency_phone TEXT,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    patient_id INTEGER NOT NULL REFERENCES patient(id),
                    expires_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS shares (
                    id TEXT PRIMARY KEY,
                    token TEXT UNIQUE NOT NULL,
                    patient_id INTEGER NOT NULL REFERENCES patient(id),
                    label TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_expires
                    ON sessions(expires_at);
                CREATE INDEX IF NOT EXISTS idx_shares_token
                    ON shares(token);
                """
            )
            cols = {
                row[1] for row in conn.execute("PRAGMA table_info(facts)").fetchall()
            }
            if "hospitals_json" not in cols:
                conn.execute(
                    "ALTER TABLE facts ADD COLUMN hospitals_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "professionals_json" not in cols:
                conn.execute(
                    "ALTER TABLE facts ADD COLUMN professionals_json TEXT NOT NULL DEFAULT '[]'"
                )

    def seed_demo_if_empty(self) -> int:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM patient LIMIT 1").fetchone()
            if row:
                return int(row["id"])
            now = iso(utcnow())
            cur = conn.execute(
                "INSERT INTO patient (display_name, preferred_lang, created_at) VALUES (?, ?, ?)",
                ("Alexander Pawinski", "fr", now),
            )
            patient_id = int(cur.lastrowid)
            conn.execute(
                """
                INSERT INTO facts (
                    patient_id, blood_abo, blood_rh, blood_source, blood_confirmed_on,
                    allergies_json, medications_json, conditions_json,
                    hospitals_json, professionals_json,
                    emergency_name, emergency_phone, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    None,
                    None,
                    None,
                    None,
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    None,
                    None,
                    now,
                ),
            )
            return patient_id

    def demo_patient_id(self) -> int | None:
        with self.connect() as conn:
            row = conn.execute("SELECT id FROM patient LIMIT 1").fetchone()
            return int(row["id"]) if row else None

    def create_session(self, patient_id: int, token: str, ttl: timedelta) -> None:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO sessions (token, patient_id, expires_at) VALUES (?, ?, ?)",
                (token, patient_id, iso(utcnow() + ttl)),
            )

    def session_patient(self, token: str) -> int | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT patient_id, expires_at FROM sessions WHERE token = ?",
                (token,),
            ).fetchone()
            if not row:
                return None
            if parse_iso(row["expires_at"]) < utcnow():
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                return None
            return int(row["patient_id"])

    def delete_session(self, token: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def get_record(self, patient_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            patient = conn.execute(
                "SELECT id, display_name, preferred_lang FROM patient WHERE id = ?",
                (patient_id,),
            ).fetchone()
            if not patient:
                return None
            facts = conn.execute(
                "SELECT * FROM facts WHERE patient_id = ?",
                (patient_id,),
            ).fetchone()
            if not facts:
                return None
            return _record(patient, facts)

    def update_record(self, patient_id: int, body: dict[str, Any]) -> dict[str, Any]:
        display_name = _clean_text(body.get("display_name"), 80)
        lang = body.get("preferred_lang")
        if lang not in {"fr", "en"}:
            lang = None
        blood_abo = body.get("blood_abo") or None
        blood_rh = body.get("blood_rh") or None
        blood_source = body.get("blood_source") or None
        if blood_abo is not None and blood_abo not in VALID_ABO:
            raise ValueError("invalid blood_abo")
        if blood_rh is not None and blood_rh not in VALID_RH:
            raise ValueError("invalid blood_rh")
        if bool(blood_abo) != bool(blood_rh):
            raise ValueError("incomplete blood type")
        if blood_abo and blood_source not in VALID_SOURCES:
            raise ValueError("invalid blood_source")
        if not blood_abo:
            blood_source = None
        confirmed = _clean_date(body.get("blood_confirmed_on"))
        allergies = _clean_allergies(body.get("allergies"))
        medications = _clean_meds(body.get("medications"))
        conditions = _clean_conditions(body.get("conditions"))
        hospitals = _clean_hospitals(body.get("hospitals"))
        professionals = _clean_professionals(body.get("professionals"))
        emergency_name = _clean_text(body.get("emergency_name"), 80)
        emergency_phone = _clean_text(body.get("emergency_phone"), 32)
        now = iso(utcnow())
        with self.connect() as conn:
            if display_name:
                conn.execute(
                    "UPDATE patient SET display_name = ? WHERE id = ?",
                    (display_name, patient_id),
                )
            if lang:
                conn.execute(
                    "UPDATE patient SET preferred_lang = ? WHERE id = ?",
                    (lang, patient_id),
                )
            conn.execute(
                """
                UPDATE facts SET
                    blood_abo = ?, blood_rh = ?, blood_source = ?,
                    blood_confirmed_on = ?,
                    allergies_json = ?, medications_json = ?, conditions_json = ?,
                    hospitals_json = ?, professionals_json = ?,
                    emergency_name = ?, emergency_phone = ?, updated_at = ?
                WHERE patient_id = ?
                """,
                (
                    blood_abo,
                    blood_rh,
                    blood_source,
                    confirmed,
                    json.dumps(allergies, ensure_ascii=False),
                    json.dumps(medications, ensure_ascii=False),
                    json.dumps(conditions, ensure_ascii=False),
                    json.dumps(hospitals, ensure_ascii=False),
                    json.dumps(professionals, ensure_ascii=False),
                    emergency_name,
                    emergency_phone,
                    now,
                    patient_id,
                ),
            )
        record = self.get_record(patient_id)
        if record is None:
            raise RuntimeError("record missing after update")
        return record

    def create_share(
        self,
        patient_id: int,
        share_id: str,
        token: str,
        ttl: timedelta,
        label: str | None,
    ) -> dict[str, Any]:
        now = utcnow()
        expires = now + ttl
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO shares (id, token, patient_id, label, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (share_id, token, patient_id, label, iso(now), iso(expires)),
            )
        return {
            "id": share_id,
            "token": token,
            "label": label,
            "created_at": iso(now),
            "expires_at": iso(expires),
            "revoked": False,
        }

    def list_shares(self, patient_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, token, label, created_at, expires_at, revoked_at
                FROM shares WHERE patient_id = ?
                ORDER BY created_at DESC
                """,
                (patient_id,),
            ).fetchall()
        return [_share_public(row, include_token=False) for row in rows]

    def get_share_by_id(self, share_id: str, patient_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT id, token, label, created_at, expires_at, revoked_at
                FROM shares WHERE id = ? AND patient_id = ?
                """,
                (share_id, patient_id),
            ).fetchone()
        return _share_public(row, include_token=True) if row else None

    def revoke_share(self, share_id: str, patient_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute(
                """
                UPDATE shares SET revoked_at = ?
                WHERE id = ? AND patient_id = ? AND revoked_at IS NULL
                """,
                (iso(utcnow()), share_id, patient_id),
            )
            return cur.rowcount == 1

    def open_share(self, token: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT s.id, s.token, s.patient_id, s.label, s.created_at,
                       s.expires_at, s.revoked_at
                FROM shares s WHERE s.token = ?
                """,
                (token,),
            ).fetchone()
            if not row:
                return None
            if row["revoked_at"] or parse_iso(row["expires_at"]) < utcnow():
                return None
            record = self.get_record(int(row["patient_id"]))
            if not record:
                return None
            return {
                "share": _share_public(row, include_token=False),
                "record": record,
            }


def _record(patient: sqlite3.Row, facts: sqlite3.Row) -> dict[str, Any]:
    abo = facts["blood_abo"]
    rh = facts["blood_rh"]
    return {
        "id": int(patient["id"]),
        "display_name": patient["display_name"],
        "preferred_lang": patient["preferred_lang"],
        "blood_abo": abo,
        "blood_rh": rh,
        "blood_type": f"{abo}{rh}" if abo and rh else None,
        "blood_source": facts["blood_source"],
        "blood_confirmed_on": facts["blood_confirmed_on"],
        "allergies": json.loads(facts["allergies_json"] or "[]"),
        "medications": json.loads(facts["medications_json"] or "[]"),
        "conditions": json.loads(facts["conditions_json"] or "[]"),
        "hospitals": json.loads(
            facts["hospitals_json"] if "hospitals_json" in facts.keys() else "[]"
        ),
        "professionals": json.loads(
            facts["professionals_json"] if "professionals_json" in facts.keys() else "[]"
        ),
        "emergency_name": facts["emergency_name"],
        "emergency_phone": facts["emergency_phone"],
        "updated_at": facts["updated_at"],
    }


def _share_public(row: sqlite3.Row, include_token: bool) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "label": row["label"],
        "created_at": row["created_at"],
        "expires_at": row["expires_at"],
        "revoked": bool(row["revoked_at"]),
        "expired": parse_iso(row["expires_at"]) < utcnow(),
    }
    if include_token:
        payload["token"] = row["token"]
    return payload


def _clean_text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    return text[:limit]


def _clean_date(value: Any) -> str | None:
    text = _clean_text(value, 10)
    if not text:
        return None
    datetime.strptime(text, "%Y-%m-%d")
    return text


def _clean_allergies(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    cleaned: list[dict[str, str]] = []
    for raw in items[:20]:
        if not isinstance(raw, dict):
            continue
        name = _clean_text(raw.get("name"), 80)
        if not name:
            continue
        raw_sev = str(raw.get("severity") or "").strip().lower()
        severity = SEVERITY_ALIASES.get(raw_sev, raw_sev)
        if severity not in VALID_SEVERITY:
            severity = "moderate"
        detail = _clean_text(raw.get("detail"), 160) or ""
        cleaned.append({"name": name, "severity": severity, "detail": detail})
    return cleaned


def _clean_meds(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    cleaned: list[dict[str, str]] = []
    for raw in items[:20]:
        if not isinstance(raw, dict):
            continue
        name = _clean_text(raw.get("name"), 80)
        if not name:
            continue
        cleaned.append(
            {
                "name": name,
                "dose": _clean_text(raw.get("dose"), 40) or "",
                "schedule": _clean_text(raw.get("schedule"), 80) or "",
            }
        )
    return cleaned


def _clean_conditions(value: Any) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    cleaned: list[dict[str, str]] = []
    for raw in items[:20]:
        if not isinstance(raw, dict):
            continue
        name = _clean_text(raw.get("name"), 80)
        if not name:
            continue
        cleaned.append(
            {
                "name": name,
                "since": _clean_text(raw.get("since"), 10) or "",
            }
        )
    return cleaned


def _clean_named(value: Any, extra: list[tuple[str, int]]) -> list[dict[str, str]]:
    items = value if isinstance(value, list) else []
    cleaned: list[dict[str, str]] = []
    for raw in items[:20]:
        if not isinstance(raw, dict):
            continue
        name = _clean_text(raw.get("name"), 80)
        if not name:
            continue
        row = {"name": name}
        for key, limit in extra:
            row[key] = _clean_text(raw.get(key), limit) or ""
        cleaned.append(row)
    return cleaned


def _clean_hospitals(value: Any) -> list[dict[str, str]]:
    return _clean_named(value, [("city", 80), ("note", 160)])


def _clean_professionals(value: Any) -> list[dict[str, str]]:
    return _clean_named(value, [("role", 80), ("phone", 32)])
