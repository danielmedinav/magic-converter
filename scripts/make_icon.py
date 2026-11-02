"""Generate resources/icon.png and resources/icon.ico (violet tile + white sparkle)."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "resources"
S = 1024  # draw large, downsample for smooth edges

TOP_LEFT = (0x9F, 0x84, 0xFF)
BOTTOM_RIGHT = (0x5B, 0x3B, 0xE8)


def gradient(size: int) -> Image.Image:
    small = Image.new("RGB", (256, 256))
    px = small.load()
    for y in range(256):
        for x in range(256):
            t = (x + y) / 510
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(TOP_LEFT, BOTTOM_RIGHT))
    return small.resize((size, size), Image.Resampling.BICUBIC)


def sparkle(cx: float, cy: float, r: float, p: float = 2.6, n: int = 400) -> list[tuple[float, float]]:
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        pts.append((cx + r * math.copysign(abs(c) ** p, c), cy + r * math.copysign(abs(s) ** p, s)))
    return pts


def main() -> None:
    OUT.mkdir(exist_ok=True)
    margin = int(S * 0.06)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((margin, margin, S - margin, S - margin),
                                           radius=int(S * 0.22), fill=255)
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tile.paste(gradient(S), mask=mask)

    # soft drop shadow
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow.paste((40, 20, 90, 110), mask=mask.filter(ImageFilter.GaussianBlur(S * 0.02)))
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.alpha_composite(shadow, (0, int(S * 0.012)))
    canvas.alpha_composite(tile)

    draw = ImageDraw.Draw(canvas)
    draw.polygon(sparkle(S * 0.46, S * 0.54, S * 0.30), fill=(255, 255, 255, 255))
    draw.polygon(sparkle(S * 0.72, S * 0.28, S * 0.11), fill=(255, 255, 255, 235))
    draw.polygon(sparkle(S * 0.75, S * 0.74, S * 0.06), fill=(255, 255, 255, 200))

    canvas.resize((512, 512), Image.Resampling.LANCZOS).save(OUT / "icon.png")
    canvas.save(OUT / "icon.ico", sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    print(f"Wrote {OUT / 'icon.png'} and {OUT / 'icon.ico'}")


if __name__ == "__main__":
    main()
