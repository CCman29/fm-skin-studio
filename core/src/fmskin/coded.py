"""Game-painted areas: parts of FM27 whose look is set by the game's code at run time, not by its stylesheets.

A skin can't change that code. What it can do (each confirmed in game unless marked "untested") is draw its own
picture over the area or hide the code-painted layer. Each entry explains what drives the area, what a skin can do,
and what can't be done, so the editor can be honest about it. Evidence: re-work/fm27-skinning/findings.md.
"""

from __future__ import annotations

from pathlib import Path

from .skinpack import PackError, SkinPack

SHEET_NAME = "coded"  # -> screen-coded.uss

# kind: "bars" = handled by the Bars & backgrounds tab (area), "image" = picture over `target`,
# "hide" = hide the painted layer, None = nothing a skin can do.
AREAS = [
    {"id": "top-bar", "title": "Top menu bar", "where": "Every screen",
     "drivenBy": "The game paints your club's colours onto the bar from code (a club-theme style setter).",
     "skin": "Draw your own picture or gradient over it.", "kind": "bars", "area": "topBar", "tested": True},
    {"id": "sub-bar", "title": "Sub-navigation bar", "where": "Every screen",
     "drivenBy": "Gradient layers filled with the club, competition, player or nation colours of the page you're on.",
     "skin": "Cover them with your own picture or gradient; the coloured layers are hidden.", "kind": "bars",
     "area": "subBar", "tested": True},
    {"id": "page-header", "title": "Page header", "where": "Club, player, team and competition pages",
     "drivenBy": "A gradient bound to the page's club colours. Once bound, it ignores stylesheet colours.",
     "skin": "Paint over it from the elements inside it.", "kind": "bars", "area": "pageHeader", "tested": True},
    {"id": "backdrop", "title": "Page backdrop", "where": "Most screens",
     "drivenBy": "Club art and render layers set from code; some screens bind their own picture.",
     "skin": "Show your own picture on the screen's content layer (one picture, or one per screen).",
     "kind": "bars", "area": "backdrop", "tested": True},
    {"id": "continue", "title": "Continue button background", "where": "Top right, every screen",
     "drivenBy": "The button's fill layer is painted from code in the club or competition style.",
     "skin": "Put a picture on its sheen layer; the CONTINUE text and chevrons stay on top.", "kind": "image",
     "target": "#continue-button-gradient", "extra": "#continue-button-gradient .continue-button---gradient { opacity: 0; }",
     "size": "756 x 141 px (a wide button shape)", "tested": True},
    {"id": "processing", "title": "Processing pop-up header", "where": "While the game is processing",
     "drivenBy": "A gradient whose two colours come from style variables (pink/purple by default).",
     "skin": "Change its two colours (set by the full theme), or put a picture over it.", "kind": "image",
     "target": ".processingpanelheader.sigradient", "size": "1024 x 128 px", "tested": False},
    {"id": "news-backgrounds", "title": "News story backgrounds", "where": "News items and news cards",
     "drivenBy": "Club, competition and nation pictures chosen by the story's subject (DynamicBackgroundImage_*).",
     "skin": "Hide the club/competition art so the panel colour shows, or use one picture for all stories.",
     "kind": "image", "target": "#DynamicBackgroundImage_Club, #DynamicBackgroundImage_Comp, #DynamicBackgroundImage_Nation",
     "hide": "#DynamicBackgroundImage_Club, #DynamicBackgroundImage_Comp, #DynamicBackgroundImage_Nation { opacity: 0; }",
     "size": "1280 x 720 px", "tested": False},
    {"id": "name-links", "title": "Club, team and player name colours", "where": "Every list, table and message",
     "drivenBy": "Clickable names are coloured from data inside the game (white; orange for your club; blue for other "
                 "human managers). That data isn't a stylesheet.",
     "skin": None, "kind": None,
     "cannot": "No skin can recolour them. Keep every panel, row and tile dark enough for white text (the studio "
               "warns you when one is too light)."},
    {"id": "kits", "title": "Kits, shirt numbers and club badges", "where": "Pitch, line-ups, profiles",
     "drivenBy": "Drawn from each club's database colours and the game's graphics.",
     "skin": None, "kind": None,
     "cannot": "Skins can't change them. Badges and faces come from FM's own graphics packs, which are separate from skins."},
    {"id": "competition-themes", "title": "Competition screens", "where": "League, cup and international pages",
     "drivenBy": "Licensed competitions load their own theme sheet (colours and fonts) on top of yours.",
     "skin": None, "kind": None,
     "cannot": "Your colours apply around them; their own fonts and accent colours stay. A skin can't remove a "
               "competition's theme."},
]

LOGIC_NOTE = ("The code behind these areas is part of the game program itself (compiled), not a file a skin can "
              "replace. Changing it would mean modifying the game install: every update would undo it, an Xbox / "
              "Game Pass install may repair it as damaged, it would apply to every skin, and it can't be shared as a "
              "skin. FM Skin Studio only writes skin packs, so it covers these areas with pictures or hides them "
              "instead.")


def listing(pack: SkinPack | None) -> dict:
    state = (pack.info.get("coded") or {}) if pack else {}
    return {"areas": [a | {"state": state.get(a["id"], {"mode": "default"})} for a in AREAS], "logicNote": LOGIC_NOTE}


def apply(pack: SkinPack, area_id: str, mode: str, source: str | None = None) -> dict:
    """mode: default | image | hide. Rewrites screen-coded.uss from the pack's saved choices."""
    pack._require_managed()
    area = next((a for a in AREAS if a["id"] == area_id), None)
    if not area or area["kind"] != "image":
        raise PackError("This area is handled in Bars & backgrounds, or a skin can't change it")
    if mode == "hide" and "hide" not in area:
        raise PackError("This area can't be hidden; use a picture instead")
    state = dict(pack.info.get("coded") or {})
    if mode == "image":
        if not source:
            raise PackError("Pick a picture (.png or .jpg)")
        url = pack.add_asset(Path(source))
        state[area_id] = {"mode": "image", "url": url}
    elif mode == "hide":
        state[area_id] = {"mode": "hide"}
    else:
        state.pop(area_id, None)
    rules = ["/* Managed by FM Skin Studio: game-painted areas covered or hidden by this skin. */"]
    for a in AREAS:
        s = state.get(a["id"])
        if not s:
            continue
        if s["mode"] == "image":
            rules.append(f"{a['target']} {{ background-image: {s['url']}; -unity-background-scale-mode: stretch-to-fill; }}")
            if a.get("extra"):
                rules.append(a["extra"])
        elif s["mode"] == "hide":
            rules.append(a["hide"])
    pack.write_screen_sheet(SHEET_NAME, "\n".join(rules) + "\n")
    pack._write_info(coded=state)
    return listing(pack)
