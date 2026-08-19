"""Draw Confdence home-screen icons with Palatino on paper."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "icons"
BG = (243, 239, 230, 255)
INK = (143, 29, 29, 255)
FONTS = (
    "/System/Library/Fonts/Supplemental/Palatino.ttc",
    "/Library/Fonts/Palatino.ttc",
    "/System/Library/Fonts/NewYork.ttf",
)


def _font(size: int) -> ImageFont.FreeTypeFont:
    last = None
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError as exc:
            last = exc
    raise SystemExit(f"no Palatino/New York font: {last}")


def _draw(size: int, pad_ratio: float = 0.0) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)
    inner = size * (1 - pad_ratio)
    font = _font(int(inner * 0.72))
    letter = "C"
    box = draw.textbbox((0, 0), letter, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    x = (size - w) / 2 - box[0]
    y = (size - h) / 2 - box[1] - size * 0.03
    draw.text((x, y), letter, font=font, fill=INK)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    _draw(192).save(OUT / "icon-192.png")
    _draw(512).save(OUT / "icon-512.png")
    _draw(512, pad_ratio=0.18).save(OUT / "icon-512-maskable.png")
    _draw(180).save(OUT / "apple-touch-icon.png")
    print(f"wrote icons in {OUT}")


if __name__ == "__main__":
    main()
