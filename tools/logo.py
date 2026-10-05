"""Builds the ToolBridge logo from its construction, so it can be regenerated exactly.

The mark is a Warren truss: three panels, seven triangles tiling a trapezoid, every member the same
thickness. The wordmark is IBM Plex Sans SemiBold (SIL Open Font License), converted to outlines so
the logo does not depend on installed fonts.

    pip install fonttools
    python tools/logo.py path/to/IBMPlexSans[wdth,wght].ttf     ->  docs/logo/*.svg
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

NAVY, LIGHT = "#0B1F3A", "#E6EDF3"
PANELS, PANEL_W, HEIGHT, MEMBER = 3, 20, 30, 4.0        # the grid: 60 x 30, members 4 thick
TEXT_SIZE, GAP = 44, 14                                  # cap height of Plex at 44 ~ the mark's height
OUT = Path(__file__).resolve().parents[1] / "docs" / "logo"


def _poly(pts) -> str:
    return "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in pts) + " Z"


def _clockwise(pts):
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
    return pts if area < 0 else pts[::-1]


def _offset(pts, dist):
    """Move every edge of a convex polygon by dist along its normal (sharp, mitred corners)."""
    pts, lines = _clockwise(pts), []
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        dx, dy = x2 - x1, y2 - y1
        n = math.hypot(dx, dy)
        lines.append(((x1 + dy / n * dist, y1 - dx / n * dist), (dx, dy)))
    out = []
    for (p, r), (q, s) in zip(lines[-1:] + lines[:-1], lines):
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / (r[0] * s[1] - r[1] * s[0])
        out.append((p[0] + t * r[0], p[1] + t * r[1]))
    return out


def truss_path() -> str:
    P, H, W = PANEL_W, HEIGHT, PANELS * PANEL_W
    outer = [(0, H), (P / 2, 0), (W - P / 2, 0), (W, H)]
    panels = [[(P * i, H), (P * i + P / 2, 0), (P * i + P, H)] for i in range(PANELS)] + \
             [[(P * i + P / 2, 0), (P * i + 1.5 * P, 0), (P * i + P, H)] for i in range(PANELS - 1)]
    return " ".join([_poly(_offset(outer, -MEMBER / 2))] + [_poly(_offset(p, MEMBER / 2)) for p in panels])


def word_path(font_file: str, text: str, size: float, x0: float, baseline: float) -> tuple[str, float]:
    font = instancer.instantiateVariableFont(TTFont(font_file), {"wght": 600, "wdth": 100})
    glyphs, cmap, scale = font.getGlyphSet(), font.getBestCmap(), size / font["head"].unitsPerEm
    x, parts = 0.0, []
    for ch in text:
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x0 + x * scale, baseline)))
        parts.append(pen.getCommands())
        x += font["hmtx"][name][0]
    return " ".join(parts), x * scale


def main(font_file: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    W, H, m = PANELS * PANEL_W, HEIGHT, MEMBER
    truss = truss_path()
    word, word_w = word_path(font_file, "ToolBridge", TEXT_SIZE, W + GAP, H)
    for name, ink in (("toolbridge-logo", NAVY), ("toolbridge-logo-dark", LIGHT)):
        (OUT / f"{name}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-m} -12 {W + GAP + word_w + 2 * m:.2f} {H + 24}" '
            f'role="img" aria-label="ToolBridge"><path fill="{ink}" fill-rule="evenodd" d="{truss}"/>'
            f'<path fill="{ink}" d="{word}"/></svg>\n', encoding="utf-8")
    (OUT / "toolbridge-mark.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-m} {-m - (W - H) / 2} {W + 2 * m} {W + 2 * m}" '
        f'role="img" aria-label="ToolBridge"><path fill="{NAVY}" fill-rule="evenodd" d="{truss}"/></svg>\n',
        encoding="utf-8")
    print("\n".join(str(p) for p in sorted(OUT.glob("*.svg"))))


if __name__ == "__main__":
    main(sys.argv[1])
