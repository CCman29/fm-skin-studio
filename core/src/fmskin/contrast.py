"""Warn when a pack makes surfaces too light for the text FM27 always draws in white.

Club / team / player / competition name links, selected menu items and card titles are coloured white by the game's
code (EmbeddedDataClickedHandler style data), so no skin can darken them. Surfaces they sit on must stay dark enough.
"""

from __future__ import annotations

import re
from pathlib import Path

MIN_RATIO = 3.0  # white text against the surface; below this names become hard to read
BEHIND = (60, 70, 90)  # assumed colour behind see-through surfaces (mid backdrop)

# token -> what the player sees
SURFACES = {
    "--layout-modules-block-surface": "Content panels",
    "--layout-modules-tiles-background": "Side tiles",
    "--layout-surfaces-cards-surface": "Cards",
    "--colours-ui-soft": "Base surface (soft)",
    "--layout-surfaces-modules-modal": "Pop-ups and dialogs",
    "--data-tables-background": "Table rows",
    "--data-tables-background-accent": "Table rows (alternate)",
}
# Tabs, dropdowns and day/column labels sit straight on the backdrop and are white too (seen on the Calendar screen).
BAR_AREAS = {"topBar": "Top menu bar", "pageHeader": "Page header", "backdrop": "Page backdrop"}

_RGB = re.compile(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*(?:,\s*([\d.]+)\s*)?\)")


def parse(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    m = _RGB.fullmatch(value.strip())
    if m:
        return float(m[1]), float(m[2]), float(m[3]), float(m[4]) if m[4] is not None else 1.0
    h = re.fullmatch(r"#?([0-9a-fA-F]{6})", value.strip())
    if h:
        n = int(h[1], 16)
        return float(n >> 16 & 255), float(n >> 8 & 255), float(n & 255), 1.0
    return None


def luminance(rgb) -> float:
    def ch(x):
        s = x / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(rgb[0]) + 0.7152 * ch(rgb[1]) + 0.0722 * ch(rgb[2])


def white_ratio(rgba, behind=BEHIND) -> float:
    r, g, b, a = rgba
    seen = tuple(c * a + bc * (1 - a) for c, bc in zip((r, g, b), behind))
    return 1.05 / (luminance(seen) + 0.05)


def resolve(name: str, overrides: dict, game: dict, depth: int = 0) -> str | None:
    value = overrides.get(name, (game.get(name) or {}).get("value"))
    m = re.fullmatch(r"\s*var\((--[\w-]+)(?:,.*)?\)\s*", value or "")
    if m and depth < 20:
        return resolve(m.group(1), overrides, game, depth + 1)
    return value


def _image_average(path: Path):
    try:
        from PIL import Image
        with Image.open(path) as im:
            r, g, b = im.convert("RGB").resize((1, 1)).getpixel((0, 0))
        return float(r), float(g), float(b), 1.0
    except Exception:
        return None


def light_surfaces(overrides: dict, game: dict, bars: dict | None = None, images: Path | None = None) -> list[dict]:
    """Surfaces that white text can't be read on: [{area, token, ratio}] (ratio = contrast of white on it)."""
    out = []
    for token, area in SURFACES.items():
        if token not in overrides:  # only judge what the pack changed
            continue
        rgba = parse(resolve(token, overrides, game))
        if rgba and rgba[3] > 0.15:
            ratio = white_ratio(rgba)
            if ratio < MIN_RATIO:
                out.append({"area": area, "token": token, "ratio": round(ratio, 1)})
    for key, area in BAR_AREAS.items():
        setting = (bars or {}).get(key) or {}
        mode = setting.get("mode", "club")
        if mode in ("solid", "gradient"):
            colours = [parse(c) for c in setting.get("colours") or []][: 1 if mode == "solid" else 2]
            ratios = [white_ratio(c) for c in colours if c]
        elif mode == "image" and images is not None:
            avg = next((_image_average(p) for p in images.glob(f"{key}.*")), None)
            ratios = [white_ratio(avg)] if avg else []
        else:
            ratios = []
        if ratios and min(ratios) < MIN_RATIO:
            out.append({"area": area, "token": f"bars:{key}", "ratio": round(min(ratios), 1)})
    return out


WARNING_TEXT = ("{area} is too light for FM27's white text (contrast {ratio}:1, needs {min}:1). Club, team and player "
                "names, card titles and menu text are always white in FM27 and can't be recoloured by a skin.")
