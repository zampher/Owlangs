#!/usr/bin/env python3
"""Render drag-to-Applications DMG background (1:1 with Finder window 660×350 pt)."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Must match dmg_finder_layout.applescript: bounds 660×350; icons at {155,135} & {455,135}.
WIDTH = 660
HEIGHT = 350

BG = (248, 248, 250)
TEXT_COLOR = (70, 70, 75)
TEXT_LEFT = 220
TEXT_TOP = 150
TEXT_SIZE = 22
TEXT_MAX_WIDTH = WIDTH - TEXT_LEFT - 44
INSTALL_LINE = "Drag and Drop"

# Icons ~y=135 (128pt); keep arrow well below icon + label area.
ARROW_Y = 200
ARROW_SHAFT_X0 = 210
ARROW_SHAFT_X1 = 350
ARROW_CURVE_DEPTH = 32  # smile arc: control point below the chord (downward bend)
ARROW_COLOR = (0, 122, 255)
ARROW_HEAD_LEN = 22
ARROW_HEAD_HALF_W = 11
SHAFT_WIDTH = 5


def _font_at_size(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _fit_install_font(draw: ImageDraw.ImageDraw) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for size in range(TEXT_SIZE, 14, -1):
        font = _font_at_size(size)
        bbox = draw.textbbox((0, 0), INSTALL_LINE, font=font)
        if bbox[2] - bbox[0] <= TEXT_MAX_WIDTH:
            return font
    return _font_at_size(14)


def _bezier(t: float, p0, p1, p2) -> tuple[float, float]:
    u = 1 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def _draw_smile_arrow(draw: ImageDraw.ImageDraw) -> None:
    """Downward smile arc (left → right) with a solid arrowhead on the tangent at the end."""
    x0, x1 = ARROW_SHAFT_X0, ARROW_SHAFT_X1
    y = ARROW_Y
    start = (x0, y)
    end = (x1, y)
    control = ((x0 + x1) / 2, y + ARROW_CURVE_DEPTH)

    pts = [_bezier(i / 56, start, control, end) for i in range(57)]
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=ARROW_COLOR, width=SHAFT_WIDTH)

    ex, ey = pts[-1]
    px, py = pts[-2]
    ang = math.atan2(ey - py, ex - px)
    tip = (
        ex + ARROW_HEAD_LEN * math.cos(ang),
        ey + ARROW_HEAD_LEN * math.sin(ang),
    )
    left = (
        ex - ARROW_HEAD_HALF_W * math.sin(ang),
        ey + ARROW_HEAD_HALF_W * math.cos(ang),
    )
    right = (
        ex + ARROW_HEAD_HALF_W * math.sin(ang),
        ey - ARROW_HEAD_HALF_W * math.cos(ang),
    )
    draw.polygon([tip, left, right], fill=ARROW_COLOR)


def render(output_path: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    install_font = _fit_install_font(draw)
    draw.text(
        (TEXT_LEFT, TEXT_TOP),
        INSTALL_LINE,
        font=install_font,
        fill=TEXT_COLOR,
        anchor="lt",
    )

    _draw_smile_arrow(draw)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"DMG background written: {output_path} ({WIDTH}x{HEIGHT})")


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <output.png>", file=sys.stderr)
        return 1
    render(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
