"""Light (white-panel) themes: the colouring FM27 needs beyond its tokens.

FM27 was drawn for dark panels. On white panels a lot of it disappears: text, icons, dividers and outlines that the
game colours white with fixed values, and the game's white tint tokens (--colours-alpha-light-N), which it uses
both for text and for fills (hovers, selected rows, steppers). Learned building EPL White (2026-11-11, in game):

- fixed white text -> the skin's text colour, except on purple/dark/coloured backgrounds (KEEP_WHITE);
- the white tint tokens -> the text colour at near-full strength, so text stays crisp...
- ...and every rule that uses them as a FILL gets a soft wash of the text colour instead (otherwise hovers and
  selected rows turn into solid slabs with the same-coloured text on them);
- fixed white icon tints -> the text colour; white/pale dividers and outlines -> thin lines of the text colour, and
  selection markers (active tab underline...) -> the skin's highlight colour;
- fills that end up dark get white text and icons inside;
- FM's icon, switch-outline and chart-line tokens that are white -> the text colour;
- selected toggles and tabs -> a pale tint of the highlight colour, so their text stays the text colour;
- the main menu (a dark 3D scene with its own tiles) keeps FM27's own dark look.

Everything is written into the pack's own sheets (screen-lighttext / screen-lightsurfaces / screen-lighttweaks /
screen-mainmenu); nothing outside the pack is touched.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import contrast, uss
from .skinpack import PackError, SkinPack

# built-in rules with fixed white text that stay white: they sit on purple, dark or coloured backgrounds
KEEP_WHITE = re.compile(
    r"button-tertiary|primary|dialog-button|tactic|pitch|badge|pill|rating|position|piechart|income|expenditure|"
    r"speakto-button|secondary-navigation|navigation-secondary|match-|tifo|spider|knowledge|progress-timeline|"
    r"calendar-day-current|close-button|grid-element|iphone|ige-|manager-creation|testin|buyin|"
    r"continue|processing|notification|stage-tree|analysis-status|transfer-interest|data_display|sicharttextsmall", re.I)
FIXED_LIGHT = re.compile(r"^(rgba?\(\s*2[0-5]\d|var\(--colours-(base-neutral-white|brand-foundation-white))")
SKIP_SHEETS = ("PremierLeague", "UEFA", "Bundesliga", "EFL", "FIFA", "LaLiga", "SerieA", "Ligue", "MLS", "Eredivisie",
               "MatchUI", "Controller", "Images", "Icons", "iPhone")
ALPHA_LIGHT = re.compile(r"var\(--colours-alpha-light-(?:alpha-)?(\d+)\)")
NOT_ICON = re.compile(r"card|frame|surface|panel|backdrop|block|background-image|scroll|dragger|bib-colour", re.I)
BORDERS = ("border-color", "border-top-color", "border-bottom-color", "border-left-color", "border-right-color")
SELECTION = re.compile(r"active|selected|checked|focus|current")
TEXT, TEXT_SOFT = "var(--global-text-primary)", "var(--global-text-secondary)"

# FM27 tokens that draw icons, outlines and chart lines white or pale lavender
ICON_TOKENS = ("--core-controls-icon-default", "--global-surface-icon-standard", "--layout-ui-core-controls-icon-default",
               "--buttons-icons-default", "--buttons-global-icon-surface", "--global-icon-surface",
               "--interaction-global-icon-surface", "--buttons-text-default")
LIGHT_SHEETS = ("lighttext", "lightsurfaces", "lighttweaks", "mainmenu")


def _rgb(colour: str) -> tuple[int, int, int]:
    c = contrast.parse(colour or "")
    if not c:
        raise PackError(f"Colours must be #rrggbb or rgb(), got '{colour}'")
    return tuple(round(x) for x in c[:3])  # type: ignore[return-value]


def _rgba(rgb: tuple[int, int, int], a: float) -> str:
    return f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {a:.2f})"


def _mix_white(rgb: tuple[int, int, int], share: float) -> str:
    return "rgb({}, {}, {})".format(*(round(255 + (c - 255) * share) for c in rgb))


def is_light(colour: str) -> bool:
    """True for panel colours a light theme is needed on (FM27's white text can't be read on them)."""
    c = contrast.parse(colour or "")
    return bool(c) and contrast.white_ratio((*c[:3], 1.0)) < contrast.MIN_RATIO


class _Resolver:
    def __init__(self, game_tokens: dict, overrides: dict):
        self.game, self.over = game_tokens, overrides

    def __call__(self, v: str | None, depth: int = 0):
        v = (v or "").strip()
        if v.startswith("var(") and depth < 15:
            n = v[4:].split(",")[0].split(")")[0].strip()
            nxt = self.over.get(n) or (self.game.get(n) or {}).get("value")
            return self(nxt, depth + 1) if nxt else None
        return v

    def name(self, v: str) -> str | None:
        v = v.strip()
        return v[4:].split(",")[0].split(")")[0].strip() if v.startswith("var(") else None


def _rules(index):
    for name, sh in index.sheets().items():
        if any(s in name for s in SKIP_SHEETS) or not sh.get("uss"):
            continue
        for rule in uss.parse(sh["uss"]).rules:
            yield rule


def tokens(game_tokens: dict, text: str, highlight: str) -> dict[str, str]:
    """Token changes a light theme needs (the pack's own colours are passed in)."""
    t, h = _rgb(text), _rgb(highlight)
    out = {name: _rgba(t, 0.92 if int(m.group(1)) >= 65 else 0.70 if int(m.group(1)) >= 35 else int(m.group(1)) / 100)
           for name in game_tokens
           for m in [re.fullmatch(r"--colours-alpha-light-(?:alpha-)?(\d+)", name)] if m and m.group(1) != "0"}
    out.update({n: TEXT for n in ICON_TOKENS})
    out.update({
        "--layout-tiles-heading": TEXT,
        "--layout-surfaces-breadcrumb-title-active": TEXT,
        "--layout-surfaces-breadcrumb-title-inactive": TEXT_SOFT,
        "--modal-text-primary": TEXT,
        "--colours-ui-text-strong": TEXT,
        "--colours-ui-text-soft": TEXT_SOFT,
        # selected toggles, tabs and segmented options: a pale tint of the highlight with its edge, text stays dark
        "--buttons-toggle-active-primary-surface": _mix_white(h, 0.18),
        "--buttons-toggle-active-primary-hover": _mix_white(h, 0.26),
        "--buttons-toggle-active-primary-border": "rgb({}, {}, {})".format(*h),
        # unselected controls: near-white
        "--buttons-toggle-notactive-surface": "rgba(255, 255, 255, 0.94)",
        "--buttons-toggle-notactive-background": "rgba(255, 255, 255, 0.94)",
        "--buttons-toggle-notactive-surface-hover": "rgba(255, 255, 255, 1)",
        "--core-controls-surface-pc-default": "rgba(255, 255, 255, 0.94)",
        "--core-controls-surface-pc-hover": "rgba(255, 255, 255, 1)",
        # switches, selection outlines and chart lines that were white
        "--interaction-input-switch-border-color-default": _rgba(t, 0.45),
        "--interaction-input-switch-border-color-active-hover": "rgb({}, {}, {})".format(*h),
        "--theme-core-overlay-border-selected": "rgb({}, {}, {})".format(*t),
        "--visualiser-pitch-thematic-border": _rgba(t, 0.35),
        "--data-tables-border-selected": _rgba(t, 0.35),
        "--datapoint-stroke-colour": _rgba(t, 0.4),
        "--colours-chart-ability-line": "rgb({}, {}, {})".format(*t),
        "--chart-colour-21": "rgb({}, {}, {})".format(*t),
        "--track-colour": _rgba(t, 0.15),
        "--colours-chart-recruitment-datapoint-fill": _rgba(t, 0.75),
        # disabled primary buttons: a pale fill so their label reads
        "--buttons-primary-surface-disabled": _mix_white(t, 0.08),
        "--buttons-primary-border-disabled": _rgba(t, 0.2),
    })
    return out


def text_sheet(index, game_tokens: dict) -> tuple[str, int]:
    """FM27 rules that colour text white with fixed values -> the skin's text colour (not on coloured backgrounds)."""
    resolve = _Resolver(game_tokens, {})
    seen, out = set(), []
    for rule in _rules(index):
        for d in rule.decls:
            if d.name != "color" or not FIXED_LIGHT.match(d.value.strip()):
                continue
            c = contrast.parse(resolve(d.value) or "")
            sel = rule.selector.strip()
            if not c or min(c[:3]) < 199 or sel in seen or KEEP_WHITE.search(sel):
                continue
            seen.add(sel)
            out.append(f"{sel} {{ color: {TEXT_SOFT if c[3] < 0.9 else TEXT}; }}")
    head = ("/* Managed by FM Skin Studio (light theme): FM27 colours these texts white with fixed values; on light\n"
            "   panels they use the skin's text colour. Text on dark or coloured backgrounds stays white. */\n")
    return head + "\n".join(out) + "\n", len(out)


def surface_sheet(index, game_tokens: dict, overrides: dict, text: str, highlight: str) -> tuple[str, dict]:
    """Icons, lines and tint fills FM27 draws white; white text and icons inside fills that end up dark."""
    resolve = _Resolver(game_tokens, overrides)
    t, h = _rgb(text), "rgb({}, {}, {})".format(*_rgb(highlight))

    def neutral_light(v):
        c = contrast.parse(resolve(v) or "")
        return c if c and min(c[:3]) >= 200 and max(c[:3]) - min(c[:3]) <= 30 and c[3] > 0.25 else None

    def dark_fill(v):
        c = contrast.parse(resolve(v) or "")
        return bool(c) and c[3] > 0.6 and 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] < 90

    icons, lines, washes, on_dark, seen = [], [], [], [], set()
    for rule in _rules(index):
        sel = rule.selector.strip()
        if KEEP_WHITE.search(sel):
            continue
        for d in rule.decls:
            v, key = d.value.strip(), (sel, d.name)
            if key in seen:
                continue
            if d.name == "-unity-background-image-tint-color" and not NOT_ICON.search(sel):
                c = neutral_light(v)
                if c and not v.startswith("var(--global-text"):
                    seen.add(key)
                    icons.append(f"{sel} {{ -unity-background-image-tint-color: {TEXT if c[3] >= 0.8 else TEXT_SOFT}; }}")
            elif d.name in BORDERS:
                m = ALPHA_LIGHT.fullmatch(v)
                if m or (neutral_light(v) and "--layout-modules-block-border-colour" not in v):
                    seen.add(key)
                    if SELECTION.search(sel) and (not m or int(m.group(1)) >= 50):
                        lines.append(f"{sel} {{ {d.name}: {h}; }}")  # selection markers stay strong
                    else:
                        a = min(0.12 + int(m.group(1)) / 100 * 0.45, 0.45) if m else 0.22
                        lines.append(f"{sel} {{ {d.name}: {_rgba(t, a)}; }}")
            elif d.name == "background-color":
                m = ALPHA_LIGHT.fullmatch(v)
                if m and int(m.group(1)) >= 4:
                    seen.add(key)
                    washes.append(f"{sel} {{ background-color: {_rgba(t, min(0.04 + int(m.group(1)) / 100 * 0.3, 0.26))}; }}")
                elif re.search(r"divider|separator|(^|[-_])line([-_]|$)", sel) and neutral_light(v):
                    seen.add(key)
                    lines.append(f"{sel} {{ background-color: {_rgba(t, 0.18)}; }}")
                elif resolve.name(v) in overrides and dark_fill(v):
                    seen.add(key)
                    parts = [p.strip() for p in sel.split(",")]
                    on_dark.append(", ".join(f"{p} SIText, {p} .sitext, {p} Label" for p in parts) + " { color: rgb(255, 255, 255); }")
                    on_dark.append(", ".join(f"{p} SIImage, {p} VisualElement" for p in parts)
                                   + " { -unity-background-image-tint-color: rgb(255, 255, 255); }")
    stats = {"icons": len(icons), "lines": len(lines), "washes": len(washes), "onDark": len(on_dark) // 2}
    head = ("/* Managed by FM Skin Studio (light theme): icons, lines and tint fills FM27 draws white, in the skin's\n"
            "   text colour; white text and icons inside dark fills. */\n")
    return head + "\n".join(["/* icons */", *icons, "/* dividers and outlines */", *lines,
                             "/* soft fills */", *washes, "/* inside dark fills */", *on_dark]) + "\n", stats


def fixes_sheet(*, sub_bar_dark: bool, continue_dark: bool, menu_colour: str, panel_texture: str | None = None) -> str:
    """Hand-checked fixes (in game, White Sky Sports Light and EPL White) for parts the rules above can't reach."""
    m = "rgb({}, {}, {})".format(*_rgb(menu_colour))
    out = [
        "/* Managed by FM Skin Studio (light theme): fixes checked in game. */",
        ".si-dropdown__selection-arrow, .siscrollview--repeat-button { -unity-background-image-tint-color: var(--global-text-primary); }",
        ".nd-flat-black, .nav-on-dark .nd-flat-black { -unity-background-image-tint-color: var(--global-text-primary); }",
        ".buttons-controls-pc-default--active-false VisualElement, .buttons-controls-pc-default--active-false SIImage,",
        ".buttons-controls-pc-default--active-false Image { -unity-background-image-tint-color: var(--global-text-primary); }",
        "/* drop-down menus: section menus get dark text; the top-menu drop-downs are drawn white in code, so that menu is coloured */",
        ".fm-menu-dropdown-row SIText, .fm-menu-dropdown-row .body-md, .si-dropdown .virtualised-list__item .body-md,",
        ".cascading-menu__folder, .cascading-menu__folder__entry .sitext, .cascading-menu__folder__entry .body-md { color: var(--global-text-primary); }",
        ".fm-menu-dropdown-row SIImage, .fm-menu-dropdown-row VisualElement, .cascading-menu__folder__entry VisualElement,",
        ".cascading-menu__folder__entry SIImage { -unity-background-image-tint-color: var(--global-text-primary); }",
        f".sub-dropdown-content-container {{ background-color: {m}; }}",
        ".sub-dropdown-content-container * { color: rgb(255, 255, 255); -unity-background-image-tint-color: rgb(255, 255, 255); }",
        ".sub-dropdown-content-container:hover:enabled { background-color: var(--brand-theme-primary); }",
        ".sub-dropdown-content-container SIText, .sub-dropdown-content-container .sitext, .sub-dropdown-content-container .body-md,",
        ".si-dropdown .sub-dropdown-content-container .body-md, .sub-dropdown-content-container .fm-menu-dropdown-row SIText,",
        ".sub-dropdown-content-container .fm-menu-dropdown-row .body-md { color: rgb(255, 255, 255); }",
        ".sub-dropdown-content-container .fm-menu-dropdown-row SIImage, .sub-dropdown-content-container .fm-menu-dropdown-row VisualElement {",
        "    -unity-background-image-tint-color: rgb(255, 255, 255); }",
        "/* close (X) buttons on pop-ups: FM draws them white */",
        ".close-button, .close-button * { color: var(--global-text-primary); -unity-background-image-tint-color: var(--global-text-primary); }",
        "/* news story headers FM paints in club colours: white text */",
        ".news-story-header .primary-text-colour, .news-story-header .secondary-text-colour, .news-story-header SIText { color: rgb(255, 255, 255); }",
        "/* tactics pitch: light player cards so the (dark) name colours read */",
        ".tactics-position-details-layout { background-color: rgba(253, 252, 253, 0.95); border-radius: 4px; }",
        "/* save-loading screen: FM lays a dark texture over the card */",
        ".panel-load-game-style-bar { background-image: none; background-color: rgba(253, 252, 253, 0.97); }",
        ".badge-string-thematic-default-size-small-status-neutral-text { color: var(--global-text-primary); }",
    ]
    if sub_bar_dark:
        out += [
            "/* dark sub-bar: its tabs, section drop-down and quick links stay white */",
            ".secondary-navigation-tab-text, .navigation-secondary-text-portal-default-active-false .secondary-navigation-tab-text,",
            ".secondary-navigation-tab-dropdown .secondary-navigation-tab-text, .bookmarks-button, .bookmarks-button .sitext { color: rgb(255, 255, 255); }",
            ".secondary-navigation-tab-icon, .secondary-navigation-tab-dropdown > .si-dropdown__arrow,",
            ".bookmarks-button .ui-concepts-size-small, .bookmarks-button .ui-concepts-size-medium,",
            ".bookmarks-button .game-concepts-size-small, .bookmarks-button .game-concepts-size-medium {",
            "    -unity-background-image-tint-color: rgb(255, 255, 255); }",
        ]
    if continue_dark:
        out += [
            "/* dark Continue button: white label and icons */",
            ".continue-button SIText, .continue-button .white, .continue-button .sitext { color: rgb(255, 255, 255); }",
            ".continue-button SIImage, .continue-button .ui-concepts-size-small, .continue-button .game-concepts-size-small {",
            "    -unity-background-image-tint-color: rgb(255, 255, 255); }",
        ]
    if panel_texture:
        out += [
            "/* panels: a picture (texture) instead of a flat colour */",
            ".siblock-border, .figma-base-card-template-inner-frame, .CardBackground,",
            ".figma-base-card-modal-surface.figma-base-card-template-inner-frame, .figma-base-card-modal-surface .figma-base-card-template-inner-frame {",
            f"    background-image: {panel_texture}; -unity-background-scale-mode: scale-and-crop;",
            "    -unity-background-image-tint-color: rgb(255, 255, 255); }",
        ]
    return "\n".join(out) + "\n"


def main_menu_sheet(pack: SkinPack, game_tokens: dict, extra: dict[str, str] | None = None) -> str:
    """The main menu is a dark 3D scene with its own tiles: there the skin's tokens go back to FM27's own values."""
    stock = []
    for name in sorted(pack.tokens()):
        value = (game_tokens.get(name) or {}).get("resolved")
        if value and not value.startswith(("var(", "url(", "resource(")) and "typography" not in name:
            stock.append(f"    {name}: {value};")
    stock += [f"    {k}: {v};" for k, v in (extra or {}).items()]
    return ("/* Managed by FM Skin Studio (light theme): the main menu keeps FM27's own dark look. */\n"
            "#MainMenu, #MainMenu TemplateContainer {\n" + "\n".join(stock) + "\n}\n")


def _dark(colour: str | None) -> bool:
    c = contrast.parse(colour or "")
    return bool(c) and 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2] < 110


NO_TEXTURE = ""  # pass as panel_texture to take a texture off again


def apply(pack: SkinPack, index, game_tokens: dict, *, text: str, highlight: str, menu_colour: str | None = None,
          sub_bar: str | None = None, continue_colour: str | None = None, panel_texture: Path | str | None = None,
          main_menu_extra: dict[str, str] | None = None) -> dict:
    """Make a pack with light panels readable everywhere FM27 draws white. Writes only into the pack.

    panel_texture: a picture for the panels; None keeps the pack's current one, NO_TEXTURE removes it."""
    pack._require_managed()
    before = pack.info.get("lightTheme") or {}
    pack.set_tokens(tokens(game_tokens, text, highlight))
    text_css, n_text = text_sheet(index, game_tokens)
    pack.write_screen_sheet("lighttext", text_css)
    surfaces, stats = surface_sheet(index, game_tokens, pack.tokens(), text, highlight)
    pack.write_screen_sheet("lightsurfaces", surfaces)
    if panel_texture:
        texture = pack.add_asset(Path(panel_texture))[5:-2]  # url("assets/images/x.jpg") -> assets/images/x.jpg
    elif panel_texture is None and before.get("panelTexture") and (pack.path / before["panelTexture"]).is_file():
        texture = before["panelTexture"]
    else:
        texture = None
    if main_menu_extra is None:
        main_menu_extra = before.get("mainMenuExtra") or {}
    pack.write_screen_sheet("lighttweaks", fixes_sheet(sub_bar_dark=_dark(sub_bar), continue_dark=_dark(continue_colour),
                                                       menu_colour=menu_colour or text,
                                                       panel_texture=f'url("{texture}")' if texture else None))
    pack.write_screen_sheet("mainmenu", main_menu_sheet(pack, game_tokens, main_menu_extra))
    pack._write_info(lightTheme={"text": text, "highlight": highlight, "menuColour": menu_colour, "subBar": sub_bar,
                                 "continueColour": continue_colour, "panelTexture": texture,
                                 "mainMenuExtra": main_menu_extra or None})
    return {"textRules": n_text, **stats, "panelTexture": texture}


def reapply(pack: SkinPack, index, game_tokens: dict, **changes) -> dict:
    """Apply again with the pack's saved light-theme settings, changing only what's passed (e.g. panel_texture)."""
    saved = pack.info.get("lightTheme")
    if not saved:
        raise PackError("This skin doesn't use the light theme (its panels are dark)")
    args = {"text": saved["text"], "highlight": saved["highlight"], "menu_colour": saved.get("menuColour"),
            "sub_bar": saved.get("subBar"), "continue_colour": saved.get("continueColour")}
    return apply(pack, index, game_tokens, **(args | changes))


def remove(pack: SkinPack, game_tokens: dict) -> None:
    """Take a light theme out of a pack again (its panels turned dark): its sheets and its token changes."""
    if not any((pack.path / f"screen-{s}.uss").is_file() for s in LIGHT_SHEETS) and not pack.info.get("lightTheme"):
        return
    for s in LIGHT_SHEETS:
        pack.write_screen_sheet(s, "")
    keep = {"--buttons-toggle-notactive-surface", "--buttons-toggle-notactive-background",  # the recipe sets these
            "--buttons-toggle-notactive-surface-hover", "--core-controls-surface-pc-default", "--core-controls-surface-pc-hover"}
    pack.set_tokens({n: None for n in tokens(game_tokens, "#000000", "#000000") if n not in keep})
    pack._write_info(lightTheme=None)
