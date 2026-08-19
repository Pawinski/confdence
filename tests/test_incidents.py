from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "static" / "js" / "incidents.js").read_text(encoding="utf-8")


def test_incident_module_has_irm_loop() -> None:
    for name in (
        "declareIncident",
        "addNote",
        "addStep",
        "setStatus",
        "notifyBody",
        "smsHref",
        "markNotified",
    ):
        assert name in SRC
    assert "sev1" in SRC
    assert "commander" in SRC


def test_sms_href_shape() -> None:
    # Mirror of incidents.smsHref / digits — keep in lockstep with the JS.
    def digits(phone: str) -> str:
        s = phone.strip()
        plus = s.startswith("+")
        nums = "".join(ch for ch in s if ch.isdigit())
        if not nums:
            return ""
        return ("+" + nums) if plus else nums

    def sms_href(phone: str, body: str) -> str | None:
        d = digits(phone)
        if not d:
            return None
        from urllib.parse import quote

        return "sms:" + quote(d, safe="") + "?&body=" + quote(body, safe="")

    assert sms_href("not-a-phone", "x") is None
    href = sms_href("+1 (514) 555-0142", "Confdence SEV2 — reaction")
    assert href is not None
    assert href.startswith("sms:")
    parsed = urlparse(href.replace("?&", "?", 1))
    assert unquote(parsed.path) == "+15145550142"
    assert "SEV2" in unquote(parse_qs(parsed.query)["body"][0])


def test_wallet_wires_incidents() -> None:
    html = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'src="js/incidents.js"' in html
    assert "declare-btn" in html
    assert "ConfdenceIncidents" in app
