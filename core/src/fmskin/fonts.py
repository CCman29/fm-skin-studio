"""Bundled free fonts (SIL OFL) chosen to match the game's default font metrics, so spacing doesn't break.

Width/line-height figures in catalog.json are relative to the game's defaults (ABC Social / ABC Social Condensed),
measured on sample UI text. Adding a font copies the .ttf and its licence into the pack.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .skinpack import ASSETS_DIR, PackError, SkinPack

FONT_DIR = Path(__file__).with_name("fonts")
# body: most text (default ABC Social); condensed: small labels such as table headers and pitch roles
# (ABC Social Condensed); headings: title-style headings and menu bar (FM Universe, the "thematic" family).
ROLE_TOKENS = {
    "body": "--typography-family-primary",
    "condensed": "--typography-family-condensed",
    "headings": "--typography-family-thematic",
}


# FM27 currently can't use font files from skins (see validate.FONT_FILES_BLOCKED). The bundled fonts stay in the
# catalogue for when that's fixed, but use_font refuses them unless explicitly allowed.
FONT_FILES_WORK = False

# The game's own font families a skin can point a role at with var(); nothing is copied or shipped.
# Only families defined in the always-applied base sheets work everywhere. Competition fonts (Premier League,
# Champions, Europa, EFL, Bundesliga, World Cup) live in competition theme sheets that are only active on those
# competitions' screens; elsewhere var() resolves to nothing and text falls back (seen in game).
BUILTIN = [
    {"id": "abc-social", "family": "ABC Social", "token": "--typography-family-primary", "note": "default body"},
    {"id": "abc-social-condensed", "family": "ABC Social Condensed", "token": "--typography-family-condensed",
     "note": "default labels"},
    {"id": "fm-universe", "family": "FM Universe", "token": "--typography-family-thematic", "note": "default headings"},
    {"id": "noto-sans", "family": "Noto Sans", "token": "--typography-family-international",
     "note": "wider than ABC Social; widest script coverage"},
]


def catalog() -> dict:
    data = json.loads((FONT_DIR / "catalog.json").read_text(encoding="utf-8"))
    return data | {"fontFilesWork": FONT_FILES_WORK, "builtin": BUILTIN}


def use_builtin(pack: SkinPack, builtin_id: str, role: str, groups: dict[str, str] | None = None) -> dict:
    """Point a role at one of the game's own fonts (no files copied)."""
    if role not in ROLE_TOKENS:
        raise PackError(f"Unknown font role '{role}' (use {', '.join(ROLE_TOKENS)})")
    font = next((f for f in BUILTIN if f["id"] == builtin_id), None)
    if not font:
        raise PackError(f"No built-in font '{builtin_id}'")
    token = ROLE_TOKENS[role]
    value = None if font["token"] == token else f"var({font['token']})"
    pack.set_tokens({token: value}, groups)
    _prune_unused(pack)
    return {"role": role, "token": token, "font": font}


def find(font_id: str) -> dict:
    font = next((f for f in catalog()["fonts"] if f["id"] == font_id), None)
    if not font:
        raise PackError(f"No bundled font '{font_id}'")
    return font


def use_font(pack: SkinPack, font_id: str, role: str, groups: dict[str, str] | None = None,
             allow_broken: bool = False) -> dict:
    """Copy a bundled font (+ licence) into the pack and point the role's typography token at it."""
    if not (FONT_FILES_WORK or allow_broken):
        raise PackError("FM27 can't load font files from skins yet (game bug); pick a built-in font for now")
    if role not in ROLE_TOKENS:
        raise PackError(f"Unknown font role '{role}' (use {', '.join(ROLE_TOKENS)})")
    pack._require_managed()
    font = find(font_id)
    dest_dir = pack.path / ASSETS_DIR / "fonts"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FONT_DIR / font["file"], dest_dir / font["file"])
    for lic in (FONT_DIR / "licenses").glob(f"{font['id']}-*.txt"):
        shutil.copyfile(lic, dest_dir / lic.name)
    token = ROLE_TOKENS[role]
    pack.set_tokens({token: f'url("{ASSETS_DIR}/fonts/{font["file"]}")'}, groups)
    _prune_unused(pack)
    return {"role": role, "token": token, "font": font}


def reset_font(pack: SkinPack, role: str) -> None:
    pack.set_tokens({ROLE_TOKENS[role]: None})
    _prune_unused(pack)


def _prune_unused(pack: SkinPack) -> None:
    """Remove bundled font files (and their licences) no token points at any more."""
    used = " ".join(pack.tokens().values())
    bundled = {f["file"]: f["id"] for f in catalog()["fonts"]}
    fonts_dir = pack.path / ASSETS_DIR / "fonts"
    for f in fonts_dir.glob("*.ttf") if fonts_dir.is_dir() else []:
        if f.name in bundled and f.name not in used:
            try:
                f.unlink()
            except PermissionError:
                continue  # FM27 keeps loaded font files open while running; tidied up on a later save
            for lic in fonts_dir.glob(f"{bundled[f.name]}-*.txt"):
                lic.unlink(missing_ok=True)
