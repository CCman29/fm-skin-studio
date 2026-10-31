"""Plain-English names, descriptions and areas for FM27's theme settings (which are named like --colours-ui-soft)."""

from __future__ import annotations

import re

# Hand-written labels for the settings people touch most. Everything else gets a generated name.
CURATED = {
    "--layout-modules-block-surface": ("Content panels", "Background of the main content panels: news, tables, fixtures, messages."),
    "--layout-modules-tiles-background": ("Side tiles", "Background of smaller tiles such as budgets, reports and the data hub."),
    "--layout-surfaces-cards-surface": ("Cards", "Background of cards such as General Performance and profile cards."),
    "--layout-surfaces-modules-modal": ("Pop-ups and dialogs", "Background of pop-up windows and dialogs."),
    "--colours-ui-soft": ("Base surface (soft)", "Shared base colour that tiles, cards and many panels are built from."),
    "--colours-ui-base": ("Base surface (standard)", "Shared base colour for darker panels and report areas."),
    "--colours-ui-strong": ("Base surface (strong)", "Shared base colour for raised areas such as pop-ups."),
    "--global-background": ("Page base layer", "The layer behind the background art; mostly hidden by the art itself."),
    "--layout-ui-global-background": ("Page base layer (alt)", "Second page base layer, also behind the background art."),
    "--global-text-primary": ("Main text", "Most headings and body text."),
    "--global-text-secondary": ("Secondary text", "Dimmer text: labels, dates, captions."),
    "--brand-theme-ui-base": ("Primary buttons and selected tabs", "Filled buttons, selected tabs and toggles."),
    "--brand-theme-ui-soft": ("Primary buttons (hover)", "Buttons and tabs while the mouse is over them."),
    "--brand-theme-accent": ("Accent and links", "Highlighted figures, links and accents (e.g. budgets)."),
    "--continue-button-standard-surface": ("Continue button", "The big Continue button in the top right."),
    "--data-tables-background": ("Table rows", "Background of normal table rows."),
    "--data-tables-background-accent": ("Table rows (alternate)", "Background of every other table row."),
    "--global-lift-surface-base": ("Raised items", "Slightly lighter boxes that sit on top of panels."),
    "--global-sink-surface-base": ("Sunken items", "Slightly darker wells inside panels."),
    "--core-controls-surface-pc-default": ("Dropdowns and inputs", "Background of dropdowns, search boxes and inputs."),
    "--layout-modules-block-border-colour": ("Content panel borders", "Outline around the main content panels."),
}

AREAS = {
    "Panels & surfaces": "Backgrounds of panels, tiles, cards and pop-ups.",
    "Text": "Colours of headings, body text and captions.",
    "Buttons & controls": "Buttons, tabs, toggles, dropdowns and inputs.",
    "Tables": "Rows, headers and highlights in tables and lists.",
    "Charts & graphs": "Lines, bars, axes and fills in charts.",
    "Data & ratings": "Ratings, form, status colours and data highlights.",
    "Tactics & pitch": "Pitch, positions and tactics screens.",
    "Match": "Match day screens and the match overlay.",
    "Borders & lines": "Outlines, dividers and separators.",
    "Typography": "Fonts and text styles.",
    "Spacing & sizes": "Sizes, spacing and corner rounding (advanced).",
    "Palette": "The base colour palette other settings are built from. Changing one changes everything built on it.",
    "Other": "Settings that don't fit elsewhere.",
}

_NOISE = {"colours", "colour", "color", "colors", "layout", "global", "theme", "core", "modules", "surfaces", "ui",
          "figma", "foundation", "brand", "fm25", "fm26", "fm27"}
_SHADES = {"strong", "soft", "deep", "base", "light", "dark", "default", "hover", "pressed", "disabled", "active",
           "selected", "accent"}
_WORDS = {"bg": "background", "alt": "alternative", "txt": "text", "btn": "button", "pc": "", "uwcl": "UWCL", "ucl": "UCL",
          "uel": "UEL", "efl": "EFL", "fwc": "World Cup", "pl": "Premier League", "ip": "in possession",
          "oop": "out of possession", "xg": "xG", "gk": "goalkeeper", "dm": "DM", "am": "AM", "tdd": "deadline day"}


def humanize(token: str) -> str:
    words = [w for w in token.lstrip("-").split("-") if w]
    m = re.fullmatch(r"colours-alpha-(dark|light|transparent)-(\d+)", token.lstrip("-"))
    if m:
        return f"{'Dark' if m.group(1) == 'dark' else 'Light' if m.group(1) == 'light' else 'Clear'} overlay {m.group(2)}%"
    shades = []
    while len(words) > 1 and words[-1] in _SHADES:
        shades.insert(0, words.pop())
    words = [_WORDS.get(w, w) for w in words if w not in _NOISE] or words
    text = " ".join(w for w in words if w)
    text = re.sub(r"\b(\d+)\b", r"\1", text).strip()
    label = text[:1].upper() + text[1:] if text else token
    return f"{label} ({', '.join(shades)})" if shades else label


_USE_WORDS = {"background-color": "backgrounds", "color": "text", "-unity-background-image-tint-color": "icon tint",
              "border-color": "borders", "border-top-color": "borders", "border-bottom-color": "borders",
              "border-left-color": "borders", "border-right-color": "borders", "-unity-text-outline-color": "text outline"}


def used_for(uses: dict[str, int]) -> str:
    seen: list[str] = []
    for prop in uses:
        word = _USE_WORDS.get(prop, "other settings" if prop == "var" else prop.replace("-", " "))
        if word not in seen:
            seen.append(word)
    return ", ".join(seen[:3])


def describe(token: str, tok: dict) -> dict:
    label, desc = CURATED.get(token, (tok.get("key") or humanize(token), None))
    return {"label": label, "description": desc or tok.get("key") or "", "usedFor": used_for(tok.get("uses") or {}),
            "technical": tok.get("kind") in ("keyword", "number", "asset") and not token.startswith("--typography-family")}
