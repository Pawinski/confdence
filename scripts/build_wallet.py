"""Inline static assets into a single AirDrop-friendly HTML file."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
OUT = ROOT / "confdence.html"


def main() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    css = (STATIC / "css" / "app.css").read_text(encoding="utf-8")
    scripts = [
        (STATIC / "js" / "copy.js").read_text(encoding="utf-8"),
        (STATIC / "js" / "store.js").read_text(encoding="utf-8"),
        (STATIC / "js" / "incidents.js").read_text(encoding="utf-8"),
        (STATIC / "js" / "mcp.js").read_text(encoding="utf-8"),
        (STATIC / "js" / "card.js").read_text(encoding="utf-8"),
        (STATIC / "js" / "app.js").read_text(encoding="utf-8"),
    ]
    html = html.replace(
        '<link rel="manifest" href="manifest.json">\n  ',
        "",
    )
    html = html.replace(
        '<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">\n  ',
        "",
    )
    html = html.replace(
        '<link rel="stylesheet" href="css/app.css">',
        "<style>\n" + css + "\n</style>",
    )
    bundle = "\n".join(scripts)
    html = html.replace(
        """  <script src="js/copy.js"></script>
  <script src="js/store.js"></script>
  <script src="js/incidents.js"></script>
  <script src="js/mcp.js"></script>
  <script src="js/card.js"></script>
  <script src="js/app.js"></script>""",
        "<script>\n" + bundle + "\n</script>",
    )
    if 'href="css/app.css"' in html or 'src="js/' in html:
        raise SystemExit("build did not inline all assets")
    OUT.write_text(html, encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
