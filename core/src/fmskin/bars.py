"""Bars & backgrounds: cover FM27's club-coloured areas with the pack's own images.

The game paints club colours in code, which a stylesheet can't override; a stylesheet background-image draws over
them, and the club gradient layers can be hidden. Rules below were each confirmed in game (findings.md, rounds 2-5).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

from .skinpack import ASSETS_DIR, PackError, SkinPack

SHEET_NAME = "global"  # -> screen-global.uss in the pack root

AREAS = {
    "topBar": {
        "label": "Top menu bar",
        "size": (1024, 8),
        "hide": "#MainNav .navigation-header-gradient { display: none; }",
        "targets": ["#MainNav"],
        "scale": "stretch-to-fill",
    },
    "subBar": {
        "label": "Sub-navigation bar",
        "size": (1024, 8),
        "hide": "#EntityGradient SIGradient { opacity: 0; }",
        "targets": ["#EntityGradient"],
        "scale": "stretch-to-fill",
    },
    "pageHeader": {
        "label": "Page header (club, player, team pages)",
        "size": (1024, 8),
        "hide": ".entity-background-header #LogoFrame { margin-right: 0; }",
        "targets": [".entity-background-header #LogoFrame", ".entity-background-header #ContentFrame"],
        "scale": "stretch-to-fill",
    },
    "backdrop": {
        "label": "Page backdrop",
        "size": (1920, 1080),
        "hide": "",
        "targets": ["SISafeAreaElement#Overview", "#Card-frame > *"],
        "scale": "scale-and-crop",
    },
}
MODES = ("club", "solid", "gradient", "image")
_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _rgb(hex_colour: str) -> tuple[int, int, int]:
    m = _HEX.match(hex_colour.strip())
    if not m:
        raise PackError(f"Colours must be #rrggbb, got '{hex_colour}'")
    v = m.group(1)
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)


def render(area: str, setting: dict) -> Image.Image | None:
    """Image for an area setting: {mode, colours: [#hex, #hex], angle: 'horizontal'|'vertical'|'diagonal', stripes}."""
    mode = setting.get("mode", "club")
    if mode == "club":
        return None
    w, h = AREAS[area]["size"]
    colours = [_rgb(c) for c in (setting.get("colours") or ["#0a0f1e"])]
    if mode == "solid" or len(colours) == 1:
        im = Image.new("RGB", (w, h), colours[0])
    else:
        a, b = colours[0], colours[1]
        im = Image.new("RGB", (w, h))
        px = im.load()
        direction = setting.get("angle", "horizontal")
        for y in range(h):
            for x in range(w):
                t = x / (w - 1) if direction == "horizontal" else y / (h - 1) if direction == "vertical" \
                    else (x / (w - 1) + y / (h - 1)) / 2
                px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    if setting.get("stripes") and area == "backdrop":
        accent = _rgb(setting.get("stripeColour") or "#14303a")
        draw = ImageDraw.Draw(im)
        for x in range(-h, w, 120):
            draw.line([(x, h), (x + h, 0)], fill=accent, width=30)
    return im


def apply(pack: SkinPack, settings: dict[str, dict], uploads: dict[str, str] | None = None) -> str:
    """Write area images + screen-global.uss for all non-club areas. Returns the sheet path."""
    pack._require_managed()
    images = pack.path / ASSETS_DIR / "images"
    images.mkdir(parents=True, exist_ok=True)
    blocks = ["/* Managed by FM Skin Studio: bars & backgrounds (covers the game's club colours). */"]
    settings = dict(settings)
    for area, spec in AREAS.items():
        setting = settings.get(area) or {"mode": "club"}
        if setting.get("mode") not in MODES:
            raise PackError(f"Unknown mode for {area}: {setting.get('mode')}")
        if setting["mode"] == "club":
            continue
        target_file = images / f"{area}.png"
        if setting["mode"] == "image":
            src = (uploads or {}).get(area) or setting.get("source")
            src = (pack.path / src) if src and not Path(src).is_absolute() else src  # saved sources are pack-relative
            if src and Path(src).is_file():
                if Path(src).suffix.lower() not in (".png", ".jpg", ".jpeg"):
                    raise PackError("Background pictures must be .png or .jpg")
                target_file = images / f"{area}{Path(src).suffix.lower()}"
                if Path(src).resolve() != target_file.resolve():
                    shutil.copyfile(src, target_file)
            elif not any(images.glob(f"{area}.*")):
                raise PackError(f"Pick a picture for {spec['label']}")
            else:
                target_file = next(images.glob(f"{area}.*"))
        else:
            render(area, setting).save(target_file)
        url = f"{ASSETS_DIR}/images/{target_file.name}"
        if setting["mode"] == "image":
            settings[area] = {**setting, "source": url}  # record the packaged copy, not the author's file
        if spec["hide"]:
            blocks.append(spec["hide"])
        blocks.append(f"{', '.join(spec['targets'])} {{ background-image: url(\"{url}\"); "
                      f"-unity-background-scale-mode: {spec['scale']}; }}")
    # club colour flag off on text/images (keeps club tint off the page header tint); only when anything is themed
    if len(blocks) > 1:
        blocks.append(".fm-club-primary-color { --color-primary: false; }")
        blocks.append(".fm-club-secondary-color { --color-secondary: false; }")
    rel = pack.write_screen_sheet(SHEET_NAME, "\n".join(blocks) + "\n" if len(blocks) > 1 else "")
    pack._write_info(bars=settings)
    return rel


def current(pack: SkinPack) -> dict:
    saved = pack.info.get("bars") or {}
    return {area: saved.get(area, {"mode": "club"}) | {"label": spec["label"]} for area, spec in AREAS.items()}
