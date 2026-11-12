"""Attribute colours a skin suggests (player attributes 1-20: number, cell background and border per band).

FM27 has this built in as a player preference, not a skin setting: Preferences > Attribute Colours, where each band
has a threshold and text, background and border colour pickers (AttributeColourSelectionTemplate in the game's UI).
FM27 reads it from the player's preferences, so a skin can't switch it on by itself. The studio keeps a skin's
suggested bands with the skin (fmskinstudio.json "attributeColours"), previews them, and installer packages show
players exactly what to enter.
"""

from __future__ import annotations

import re

from . import contrast
from .skinpack import PackError, SkinPack

MIN_BANDS, MAX_BANDS = 2, 6
READABLE = 3.0  # number against its background
_HEX = re.compile(r"#[0-9a-fA-F]{6}")


def ratio(a: str, b: str) -> float:
    ca, cb = contrast.parse(a), contrast.parse(b)
    if not ca or not cb:
        return 0.0
    la, lb = sorted((contrast.luminance(ca), contrast.luminance(cb)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def normalise(bands: list[dict]) -> list[dict]:
    """Bands sorted from the highest; each covers values from its 'from' up to the next band. The lowest starts at 1."""
    if not isinstance(bands, list) or not MIN_BANDS <= len(bands) <= MAX_BANDS:
        raise PackError(f"Use {MIN_BANDS} to {MAX_BANDS} attribute bands")
    out = []
    for b in bands:
        try:
            start = int(b["from"])
        except (KeyError, TypeError, ValueError):
            raise PackError("Each band needs a starting value ('from', 1-20)") from None
        if not 1 <= start <= 20:
            raise PackError(f"Band starts must be 1-20, got {start}")
        row = {"from": start, "label": str(b.get("label") or "").strip()[:30]}
        for key in ("text", "background", "border"):
            colour = str(b.get(key) or "").strip()
            if not _HEX.fullmatch(colour):
                raise PackError(f"Band {start}: {key} colour must look like #37003c")
            row[key] = colour.lower()
        out.append(row)
    out.sort(key=lambda r: -r["from"])
    starts = [r["from"] for r in out]
    if len(set(starts)) != len(starts):
        raise PackError("Two bands start at the same value")
    if starts[-1] != 1:
        raise PackError("The lowest band must start at 1")
    return out


def ranges(bands: list[dict]) -> list[tuple[int, int, dict]]:
    """(low, high, band) for each band, highest first."""
    out, top = [], 20
    for b in bands:
        out.append((b["from"], top, b))
        top = b["from"] - 1
    return out


def warnings(bands: list[dict]) -> list[str]:
    out = []
    for low, high, b in ranges(bands):
        r = ratio(b["text"], b["background"])
        if r < READABLE:
            out.append(f"{low}-{high}: the numbers are hard to read on that background (contrast {r:.1f}:1, aim for "
                       f"{READABLE:.0f}:1). A darker background or a different number colour helps.")
    return out


def get(pack: SkinPack) -> list[dict]:
    return list(pack.info.get("attributeColours") or [])


def set_for(pack: SkinPack, bands: list[dict] | None) -> dict:
    """Save (or clear, with None/[]) a skin's suggested attribute colours. Only the skin's own marker file changes."""
    pack._require_managed()
    clean = normalise(bands) if bands else None
    pack._write_info(attributeColours=clean)
    return {"bands": clean or [], "warnings": warnings(clean) if clean else []}


def lines(bands: list[dict]) -> list[str]:
    return [f"{low:>2}-{high:<2}  {b['label'] + ': ' if b.get('label') else ''}number {b['text']}, background {b['background']}, "
            f"border {b['border']}" for low, high, b in ranges(bands)]


def instructions(bands: list[dict]) -> str:
    """How a player sets them in FM27 (they're a game preference, so a skin can't set them)."""
    body = "\n".join("    " + line for line in lines(bands))
    return ("ATTRIBUTE COLOURS (optional, set in FM27)\n"
            "  This skin is designed with these attribute colours. FM27 keeps attribute colours in your own preferences,\n"
            "  so a skin can't switch them on: open Preferences, find Attribute Colours, and for each band set the\n"
            "  threshold (the lowest value of the band) and the text, background and border colours:\n"
            f"{body}\n")
