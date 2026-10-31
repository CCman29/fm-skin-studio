"""Full-theme recipe: everything we learned in game, applied from a small palette.

A skin built from this covers, in one go (each item proven in FM27, see findings.md):
- every panel surface (content panels, side tiles, cards, base surfaces, pop-ups) and table rows;
- text colours, primary buttons / selected tabs / accents, unselected tabs and controls on the backdrop;
- the Continue button (normal, match and processing states) and the processing pop-up's "Next match" header;
- the Tactics screen, whose greens are fixed values in many rules (pitch grass stays green);
- bars & backgrounds (top bar, sub bar, page header, backdrop) via bars.py, optionally a Continue button picture;
- and it refuses nothing but reports surfaces too light for FM27's always-white text (contrast.py).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import bars, contrast
from .skinpack import PackError, SkinPack


@dataclass
class Palette:
    panel: str = "#0a1e5c"           # content panels (drawn ~90% opaque)
    tile: str = "#0e2876"            # side tiles, cards, tactics tiles
    dark: str = "#08184e"            # header strips, sunken areas
    accent: str = "#2e68d6"          # primary buttons, selected tabs, active toggles
    accent_hover: str = "#4680e8"
    highlight: str = "#84c8ff"       # accent text such as budget figures
    text: str = "#ffffff"
    text_secondary: str = "#b8c6e4"
    border: str = "#4664aa"
    continue_colour: str = "#04145a"
    processing: tuple[str, str] = ("#2e68d6", "#08184e")
    top_bar: tuple[str, str] = ("#0a1a5c", "#061038")
    sub_bar: tuple[str, str] = ("#103f98", "#06123d")
    page_header: tuple[str, str] = ("#0e2470", "#071442")
    backdrop: tuple[str, str] = ("#3f4c70", "#1c2648")
    backdrop_stripes: str | None = None
    backdrop_image: str | None = None    # a picture file instead of the backdrop gradient
    continue_image: str | None = None    # a button-shaped picture for the Continue button (see bars/findings)
    panel_opacity: float = 0.9
    notes: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "Palette":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        for key in ("processing", "top_bar", "sub_bar", "page_header", "backdrop"):
            if key in known and isinstance(known[key], list):
                known[key] = tuple(known[key])
        return cls(**known)


def _rgb(hex_colour: str, alpha: float | None = None) -> str:
    c = contrast.parse(hex_colour)
    if not c:
        raise PackError(f"Colours must be #rrggbb or rgb(), got '{hex_colour}'")
    r, g, b = (round(x) for x in c[:3])
    return f"rgba({r}, {g}, {b}, {alpha})" if alpha is not None and alpha < 1 else f"rgb({r}, {g}, {b})"


def tokens_for(p: Palette) -> dict[str, str]:
    panel, tile, dark = _rgb(p.panel, p.panel_opacity), _rgb(p.tile), _rgb(p.dark)
    accent, hover = _rgb(p.accent), _rgb(p.accent_hover)
    cont = _rgb(p.continue_colour)
    return {
        # panel surfaces
        "--layout-modules-block-surface": panel,
        "--layout-modules-tiles-background": tile,
        "--layout-modules-tiles-surface-default": tile,
        "--layout-surfaces-cards-surface": tile,
        "--layout-surfaces-modules-modal": tile,
        "--colours-ui-soft": tile,
        "--colours-ui-base": dark,
        "--colours-ui-strong": tile,
        "--layout-modules-block-border-colour": _rgb(p.border),
        "--global-background": _rgb(p.backdrop[1]),
        "--layout-ui-global-background": _rgb(p.backdrop[1]),
        # text and accents
        "--global-text-primary": _rgb(p.text),
        "--global-text-secondary": _rgb(p.text_secondary),
        "--brand-theme-ui-base": accent,
        "--brand-theme-ui-soft": hover,
        "--brand-theme-accent": _rgb(p.highlight),
        # tables
        "--data-tables-background": "rgba(255, 255, 255, 0)",
        "--data-tables-background-accent": "rgba(255, 255, 255, 0.05)",
        # unselected tabs / toggles / dropdowns, which also sit straight on the backdrop (Calendar screen)
        "--buttons-toggle-notactive-surface": _rgb(p.tile, 0.95),
        "--buttons-toggle-notactive-surface-hover": hover,
        "--buttons-toggle-notactive-background": _rgb(p.tile, 0.95),
        "--core-controls-surface-pc-default": _rgb(p.tile, 0.95),
        "--core-controls-surface-pc-hover": hover,
        "--core-controls-surface-pc-pressed": dark,
        # Continue button (normal / match / processing / standard states)
        "--continue-button-default-background": cont,
        "--continue-button-default-background-hover": accent,
        "--continue-button-default-background-secondary": accent,
        "--continue-button-default-border": _rgb(p.border),
        "--continue-button-default-grad-l": "rgba(0, 0, 0, 0)",
        "--continue-button-default-grad-r": "rgba(0, 0, 0, 0)",
        "--continue-button-standard-surface": cont,
        "--continue-button-standard-surface-gradient-l": "rgba(0, 0, 0, 0)",
        "--continue-button-standard-surface-gradient-r": "rgba(0, 0, 0, 0)",
        "--continue-button-standard-surface-hover-gradient-l": "rgba(0, 0, 0, 0)",
        "--continue-button-standard-surface-hover-gradient-r": "rgba(0, 0, 0, 0)",
        # Tactics screen tokens (grass token --colours-tactics-base-50 deliberately untouched)
        "--pitch-tile-default-background": tile,
        "--colours-tactics-base-00": hover,
        "--colours-tactics-base-20": accent,
        "--colours-tactics-base-40": accent,
        "--colours-tactics-base-60": dark,
        "--colours-tactics-base-80": dark,
        "--colours-tactics-teaminstruction-background": tile,
    }


def tactics_sheet(p: Palette) -> str:
    panel, tile, dark, accent, border = _rgb(p.panel, p.panel_opacity), _rgb(p.tile), _rgb(p.dark), _rgb(p.accent), _rgb(p.border)
    hl = _rgb(p.accent, 0.5)
    return f"""/* Managed by FM Skin Studio (theme recipe): Tactics screen. Its greens are fixed values in many rules, so each
   panel rule is overridden. The pitch grass (.tactics-collapsable-pitch-grass-colour) stays green. */
.layout-block-tactics {{ background-color: {panel}; border-color: {border}; }}
.tactics-collapsable-pitch-container, .tactics-collapsable-pitch-container-with-darker-header,
.tactics-collapsable-pitch-container-with-darker-header-borderless {{ background-color: {tile}; }}
.tactics-collapsable-pitch-header {{ background-color: {dark}; }}
.tactics-subs-block {{ background-color: {tile}; }}
.tactics-statusicon .scaling-icons-condition-level-injured-size-small-16px, .tactics-statusicon .game-concepts-abroad-plane_small,
.tactics-statusicon .game-concepts-red-card_small, .tactics-statusicon .restricted-low {{ background-color: {tile}; }}
.buttons-button-primary-tactics {{ background-color: {accent}; }}
.tactics-row-highlight-highlighted {{ background-color: {hl}; }}
.frame-tactics-nav-menu, .tactics-collapsable-pitch-border, .tactics-pitch-visualiser-property-1-ip-oop {{ border-color: {border}; }}
.tactics-radio-buttons .unity-radio-button-group__child-active {{ background-color: {accent}; }}
.tactics-multiple-choice-option-button-selected {{ background-color: {accent}; }}
.squad-depth-fmc-header {{ background-color: {dark}; }}
/* Tactics top bar (TacticalPlannerHeader): gradient frame plus two rows painted on top of it. */
.frame-tactics-nav-menu {{ --start-colour: {tile}; --end-colour: {panel}; }}
.tactics-nav-primary-actions-property-1-base {{ background-color: {tile}; }}
.tactics-nav-secondary-actions-property-1-team-shape {{ background-color: {dark}; }}
"""


def processing_sheet(p: Palette) -> str:
    return (f"/* Managed by FM Skin Studio (theme recipe): processing pop-up 'Next match' header. */\n"
            f".processingpanelheader.sigradient {{ --start-colour: {_rgb(p.processing[0])}; --end-colour: {_rgb(p.processing[1])}; }}\n")


def continue_sheet(url: str) -> str:
    # The button's inner background layer is painted from code; the sheen layer above it is not (confirmed in game).
    return (f"/* Managed by FM Skin Studio (theme recipe): Continue button picture on the sheen layer. */\n"
            f"#continue-button-gradient {{ background-image: {url}; -unity-background-scale-mode: stretch-to-fill; }}\n"
            f"#continue-button-gradient .continue-button---gradient {{ opacity: 0; }}\n")


def apply(pack: SkinPack, palette: Palette) -> dict:
    """Write the whole theme into a pack (its own folder; nothing else is touched). Returns readability warnings."""
    pack._require_managed()
    pack.set_tokens(tokens_for(palette))
    pack.write_screen_sheet("tactics", tactics_sheet(palette))
    pack.write_screen_sheet("processing", processing_sheet(palette))
    record = asdict(palette)
    if palette.continue_image:
        url = pack.add_asset(Path(palette.continue_image))
        pack.write_screen_sheet("continue", continue_sheet(url))
        record["continue_image"] = url[5:-2]  # url("assets/images/x.png") -> packaged path
    backdrop = ({"mode": "image", "source": palette.backdrop_image} if palette.backdrop_image else
                {"mode": "gradient", "colours": list(palette.backdrop), "angle": "diagonal",
                 "stripes": bool(palette.backdrop_stripes), "stripeColour": palette.backdrop_stripes or "#000000"})
    bars.apply(pack, {
        "topBar": {"mode": "gradient", "colours": list(palette.top_bar), "angle": "horizontal"},
        "subBar": {"mode": "gradient", "colours": list(palette.sub_bar), "angle": "horizontal"},
        "pageHeader": {"mode": "gradient", "colours": list(palette.page_header), "angle": "horizontal"},
        "backdrop": backdrop,
    })
    if palette.backdrop_image:
        record["backdrop_image"] = (pack.info.get("bars") or {}).get("backdrop", {}).get("source")
    pack._write_info(recipe=record)
    warnings = contrast.light_surfaces(pack.tokens(), {}, pack.info.get("bars"), pack.path / "assets" / "images")
    return {"warnings": warnings, "sheets": pack.sheets()}
