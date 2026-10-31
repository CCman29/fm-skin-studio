"""Build and cache an index of the user's FM27 install: theme tokens, stylesheets, screen layouts, screen trees.

Everything stays on the user's machine in the cache folder; nothing here is meant for export.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import gamedata, stylesheet
from .paths import GamePaths

INDEX_VERSION = 8

# The handful of surfaces that paint most of the UI, shown first in Global settings ("Main surfaces").
KEY_SURFACES = {
    "--layout-modules-block-surface": "Content blocks (main panels: news, tables, fixtures, messages)",
    "--layout-modules-tiles-background": "Tiles and side cards (budgets, reports, data hub)",
    "--layout-surfaces-cards-surface": "Cards",
    "--layout-surfaces-modules-modal": "Pop-ups and dialogs",
    "--colours-ui-soft": "Base surface: soft (feeds tiles and cards)",
    "--colours-ui-base": "Base surface: standard",
    "--colours-ui-strong": "Base surface: strong (feeds pop-ups)",
    "--global-background": "Page base layer (behind the background art)",
    "--global-text-primary": "Main text",
    "--global-text-secondary": "Secondary text",
    "--brand-theme-ui-base": "Primary buttons, selected tabs and toggles",
    "--brand-theme-ui-soft": "Primary buttons: hover",
    "--brand-theme-accent": "Accent highlights and links",
    "--continue-button-standard-surface": "Continue button",
    "--data-tables-background": "Table background",
    "--data-tables-background-accent": "Table alternate rows",
}
BASE_SHEETS = {"AlwaysAppliedStyleSheet", "default", "FigmaStyleVariables", "FigmaGeneratedVariableStyles"}
BREAKPOINTS = {0: "NONE", 1: "Small", 2: "Standard", 3: "Large", 4: "Phone_Portrait", 5: "Phone_Landscape"}

# Token groups for the Global settings screen, checked in order. Name rules first, then what the token paints.
_NAME_GROUPS = [
    ("Panels & surfaces", r"^--(layout-modules-(block|tiles)-(surface|background)|layout-surfaces-.*(surface|modal)|"
                          r"layout-ui-tiles-.*background|layout-ui-global-background|global-background|"
                          r"global-(lift|sink)-surface|colours-ui-(base|soft|strong))"),
    ("Match", r"match|dugout|momentum|lower-third"),
    ("Tactics & pitch", r"tactic|pitch|formation|position-"),
    ("Tables", r"data-tables|table"),
    ("Typography", r"typography|font"),
    ("Charts & graphs", r"(^--|-)(chart|graph)|line-colour|fill-colour|axis|track-colour|start-colour|end-colour|"
                        r"increasing|decreasing|current-colour|spider|pie-"),
    ("Buttons & controls", r"button|control|toggle|interaction|dropdown|slider|stepper|checkbox|tab-"),
    ("Data & ratings", r"^--(data|status|linear|chart|colours-data|colours-chart|colours-player|rating)"),
    ("Typography", r"typography|font"),
    ("Spacing & sizes", r"padding|margin|gap|radius|border-width|dimensions|width|height|size-|spacing"),
    ("Palette", r"^--colours-(base|brand|alpha|linear|ui)-"),
]
_PROPERTY_GROUPS = [
    ("Panels & surfaces", ("background-color", "-unity-background-image-tint-color")),
    ("Text", ("color", "-unity-text-outline-color")),
    ("Borders & lines", ("border-color", "border-top-color", "border-bottom-color", "border-left-color", "border-right-color")),
]


def cache_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "FMSkinStudio"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FMSkinStudio" / "cache"


def _value_kind(value: str) -> str:
    v = value.strip()
    if v.startswith(("rgb", "#")) or v in ("transparent",):
        return "color"
    if v.startswith("url(") or v.startswith("resource("):
        return "asset"
    if re.fullmatch(r"-?[\d.]+(px|%|deg|s|ms)?", v):
        return "dimension" if not re.fullmatch(r"-?[\d.]+", v) else "number"
    if v.startswith("var("):
        return "reference"
    return "keyword"


def _var_name(value: str) -> str | None:
    m = re.fullmatch(r"var\((--[\w-]+)(?:,.*)?\)", value.strip())
    return m.group(1) if m else None


def resolve(tokens: dict[str, dict], name: str, depth: int = 0) -> str | None:
    tok = tokens.get(name)
    if not tok or depth > 16:
        return None
    ref = _var_name(tok["value"])
    return resolve(tokens, ref, depth + 1) if ref else tok["value"]


def _token_group(name: str, usage: Counter) -> str:
    for group, pattern in _NAME_GROUPS[:-1]:
        if re.search(pattern, name):
            return group
    if usage:
        best = max(_PROPERTY_GROUPS, key=lambda g: sum(usage[p] for p in g[1]))
        if sum(usage[p] for p in best[1]) > 0:
            return best[0]
    if re.search(_NAME_GROUPS[-1][1], name):
        return "Palette"
    return "Other"


def screen_name(composition_name: str) -> str:
    """'TrainingOverviewGridComposition-Large' -> 'TrainingOverview'."""
    base = re.split(r"[-_](?:NONE|Small|Standard|Large|Phone_Portrait|Phone_Landscape)\b", composition_name)[0]
    return re.sub(r"(Grid)?Composition$", "", base) or composition_name


def area_of(name: str) -> str:
    areas = [("Match", r"Match|HalfTime|Dugout|PreMatch|PostMatch"), ("Tactics", r"Tactic|Instruction|SetPiece|Formation"),
             ("Training", r"Training|Coach"), ("Squad", r"Squad|Player(?!s?Involved)|Selection"),
             ("Scouting & recruitment", r"Scout|Recruit|Shortlist|Transfer|Loan|Contract"),
             ("Club & staff", r"Club|Staff|Board|Finance|Facilit"), ("Competitions", r"Competition|League|Cup|Fixture"),
             ("Data hub", r"DataHub|Analytics|Stats|Report"), ("Inbox & news", r"Portal|News|Inbox|Message|Feedback"),
             ("Game setup & menus", r"MainMenu|GameCreation|Manager|Setup|Start"), ("Cards", r"Card|Tile|Template")]
    for area, pattern in areas:
        if re.search(pattern, name):
            return area
    return "Other"


def _panel(raw: dict) -> dict:
    loc = raw.get("m_location", {})
    return {
        "id": raw.get("m_elementID", ""),
        "x": loc.get("x", 0), "y": loc.get("y", 0), "w": loc.get("width", 1), "h": loc.get("height", 1),
        "minW": raw.get("m_minSize", {}).get("x", 1), "minH": raw.get("m_minSize", {}).get("y", 1),
        "maxW": raw.get("m_maxSize", {}).get("x", 100), "maxH": raw.get("m_maxSize", {}).get("y", 100),
        "locked": bool(raw.get("m_isLocked")), "optional": bool(raw.get("m_isOptional")),
    }


def _composition(tree: dict, bundle: str) -> dict:
    slices = tree.get("m_optionalSlices") or {}
    optional = {zone: [_panel(p) for p in slices.get(key) or []]
                for zone, key in (("topLeft", "m_topLeft"), ("top", "m_top"), ("topRight", "m_topRight"),
                                  ("left", "m_left"), ("right", "m_right"), ("bottomLeft", "m_bottomLeft"),
                                  ("bottom", "m_bottom"), ("bottomRight", "m_bottomRight"))}
    panels = [_panel(p) for p in tree.get("m_gridComponents") or []]
    name = tree.get("m_Name", "")
    editable = any(not p["locked"] for p in panels) and (
        len(panels) > 1 or any(p["minW"] != p["maxW"] or p["minH"] != p["maxH"] for p in panels))
    return {
        "name": name, "screen": screen_name(name), "area": area_of(name), "bundle": bundle,
        "breakpoint": BREAKPOINTS.get(tree.get("m_gridBreakpoint", 0), "NONE"),
        "inMatch": bool(re.search(r"InMatch|-IM\b|Match", name)),
        "panels": panels, "optional": {k: v for k, v in optional.items() if v}, "editable": editable,
        "allowedTags": tree.get("m_allowedTags") or [],
    }


def _catalogue(graph, set_key, set_tree: dict) -> list[dict]:
    """Panels a screen may hold: id, tags and the discrete sizes the game offers for each."""
    pptrs = list(set_tree.get("m_gridElementDescriptions") or [])
    for group in set_tree.get("m_tileGroups") or []:
        pptrs += group.get("m_tiles") or []
    out, seen = [], set()
    for pptr in pptrs:
        desc = graph.resolve(set_key, pptr) if set_key else None
        if not desc:
            continue
        pid = desc.get("<ID>k__BackingField") or desc.get("m_Name", "")
        if pid in seen:
            continue
        seen.add(pid)
        sizes, configs = [], []
        for cfg in desc.get("<Configurations>k__BackingField") or []:
            size = cfg.get("Size") or {}
            wh = [size.get("x"), size.get("y")]
            if wh not in sizes:
                sizes.append(wh)
            guid = (cfg.get("AssetRef") or {}).get("m_AssetGUID")
            if guid:
                configs.append({"size": wh, "uxml": guid})
        out.append({"id": pid, "name": desc.get("<Name>k__BackingField") or pid,
                    "tags": desc.get("<Tags>k__BackingField") or [], "sizes": sorted(sizes), "configs": configs})
    return out


_TEXT_RUN = re.compile(b"[\\x20-\\x7e\\xc0-\\xff]{3,}")


def _fallback_text(data: dict) -> str | None:
    """English fallback text carried inside a TranslationID text binding, when there is one."""
    raw = (((data.get("TextBinding") or {}).get("m_visualFunction") or {}).get("m_inputs") or {})
    arg = ((raw.get("m_variable") or {}).get("m_argumentBytes")) or []
    if not arg:
        return None
    runs = [r.decode("latin-1") for r in _TEXT_RUN.findall(bytes(arg)) if b"VisualScripting" not in r and b"Translation" not in r]
    return runs[-1] if runs else None


def _uxml_tree(tree: dict, inline_rules: list | None = None) -> dict:
    """Compact element tree from a VisualTreeAsset stored with Unity's serialized-reference format."""
    refs = {r["rid"]: r for r in (tree.get("references") or {}).get("RefIds", [])}
    cc = tree.get("m_ContentContainerId")

    def data_fields(rid: int) -> dict:
        data = (refs.get(rid) or {}).get("data") or {}
        return {k: v for k, v in data.items() if isinstance(v, (str, int, float, bool)) and v not in ("", None)
                and not k.startswith("m_") and len(str(v)) < 200}

    def node(rid: int, depth: int = 0) -> dict | None:
        ref = refs.get(rid)
        if not ref or depth > 64:
            return None
        d = ref.get("data") or {}
        out: dict = {"t": (d.get("m_FullTypeName") or ref["type"].get("class", "")).split(".")[-1]}
        if d.get("m_Classes"):
            out["c"] = d["m_Classes"]
        if d.get("m_TemplateAlias"):
            out["tpl"] = d["m_TemplateAlias"]
        if cc is not None and d.get("m_Id") == cc:
            out["cc"] = 1  # the template's content container: an instance's own children go here
        sd_rid = (d.get("m_SerializedData") or {}).get("rid", -2)
        fields = data_fields(sd_rid)
        if fields:
            out["d"] = fields
        text = _fallback_text((refs.get(sd_rid) or {}).get("data") or {})
        if text:
            out["txt"] = text
        rule = d.get("m_RuleIndex", -1)
        if inline_rules is not None and 0 <= rule < len(inline_rules):
            out["s"] = inline_rules[rule]
        kids = [node(c["rid"], depth + 1) for c in d.get("m_Children") or []]
        kids = [k for k in kids if k]
        if kids:
            out["ch"] = kids
        return out

    root = node((tree.get("m_VisualTree") or {}).get("rid", -2))
    usings = {u.get("alias"): u.get("path") for u in tree.get("m_Usings") or [] if u.get("alias")}
    return {"name": tree.get("m_Name", ""), "root": root, "templates": usings}


def _inline_css(rule) -> str:
    return "; ".join(f"{d.name}: {d.value}" for d in rule.declarations)


@dataclass
class GameIndex:
    root: Path

    def _load(self, name: str):
        with gzip.open(self.root / f"{name}.json.gz", "rt", encoding="utf-8") as fh:
            return json.load(fh)

    def manifest(self) -> dict:
        return json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))

    def tokens(self) -> dict[str, dict]:
        return self._load("tokens")

    def sheets(self) -> dict[str, dict]:
        return self._load("sheets")

    def compositions(self) -> list[dict]:
        """Each composition carries `catalogue` (allowed panels + sizes) when the game defines one."""
        comps = self._load("compositions")
        sets = self._load("element_sets")
        for c in comps:
            catalogue = sets.get(c.get("elementSet", ""), [])
            tags = set(c.get("allowedTags") or [])
            c["catalogue"] = [p for p in catalogue if not tags or tags & set(p["tags"])]
        return comps

    def screens(self) -> dict[str, dict]:
        return self._load("uxml")

    def screen_guids(self) -> dict[str, str]:
        return self._load("uxml_guids")


def _write(path: Path, name: str, data) -> None:
    with gzip.open(path / f"{name}.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))


def open_index(paths: GamePaths, cache: Path | None = None) -> GameIndex | None:
    build = paths.game_build()
    if not build:
        return None
    root = (cache or cache_root()) / build
    manifest = root / "manifest.json"
    if manifest.is_file() and json.loads(manifest.read_text(encoding="utf-8")).get("version") == INDEX_VERSION:
        return GameIndex(root)
    return None


def build_index(paths: GamePaths, cache: Path | None = None, progress: gamedata.Progress | None = None,
                include_uxml: bool = True) -> GameIndex:
    if not paths.bundles or not paths.bundles.is_dir():
        raise FileNotFoundError("FM27 game data not found")
    build = paths.game_build() or "unknown"
    root = (cache or cache_root()) / build
    root.mkdir(parents=True, exist_ok=True)
    report = progress or (lambda *_: None)

    # Stylesheets and tokens
    sheets: dict[str, dict] = {}
    definitions: dict[str, list[dict]] = defaultdict(list)
    usage: dict[str, Counter] = defaultdict(Counter)
    referenced_by: dict[str, set[str]] = defaultdict(set)
    style_bundles = gamedata.bundles(paths.bundles, gamedata.STYLE_BUNDLES)
    for i, bundle in enumerate(style_bundles):
        report("stylesheets", i, len(style_bundles))
        for tree in gamedata.monobehaviours(bundle):
            if not stylesheet.is_stylesheet(tree):
                continue
            sheet = stylesheet.decode(tree)
            if not sheet.name or sheet.name in sheets:
                continue
            sheets[sheet.name] = {"bundle": bundle.name, "uss": sheet.to_uss(), "rules": len(sheet.rules)}
            for rule in sheet.rules:
                for decl in rule.declarations:
                    if decl.is_custom:
                        definitions[decl.name].append({"sheet": sheet.name, "selector": ", ".join(rule.selectors),
                                                       "value": decl.value})
                    for ref in decl.var_refs:
                        if decl.is_custom:
                            referenced_by[ref].add(decl.name)
                        else:
                            usage[ref][decl.name] += 1

    effective: dict[str, Counter] = {}

    def effective_usage(name: str, seen: frozenset = frozenset()) -> Counter:
        """Direct property usage plus the usage of every token that references this one via var()."""
        if name in effective:
            return effective[name]
        total = Counter(usage[name])
        for parent in referenced_by.get(name, ()):
            if parent not in seen:
                total.update(effective_usage(parent, seen | {name}))
        effective[name] = total
        return total

    tokens: dict[str, dict] = {}
    for name, defs in definitions.items():
        base = next((d for d in defs if d["sheet"] in BASE_SHEETS and d["selector"] == ":root"),
                    next((d for d in defs if d["selector"] == ":root"), defs[0]))
        tokens[name] = {"value": base["value"], "sheet": base["sheet"], "selector": base["selector"],
                        "overrides": [d for d in defs if d is not base][:20],
                        "uses": dict(effective_usage(name).most_common(6)),
                        "useCount": sum(effective_usage(name).values()),
                        "referencedBy": sorted(referenced_by.get(name, ()))[:12]}
    for name, tok in tokens.items():
        tok["resolved"] = resolve(tokens, name)
        tok["kind"] = _value_kind(tok["resolved"] or tok["value"])
        tok["group"] = _token_group(name, effective_usage(name))
        if name in KEY_SURFACES:
            tok["key"] = KEY_SURFACES[name]
    _write(root, "tokens", tokens)
    _write(root, "sheets", sheets)

    # Screen layouts + each screen's panel catalogue (which panels it can hold, at which sizes)
    compositions = []
    graph = gamedata.ObjectGraph()
    raw_compositions = []
    layout_bundles = gamedata.bundles(paths.bundles, gamedata.LAYOUT_BUNDLES)
    for i, bundle in enumerate(layout_bundles):
        report("layouts", i, len(layout_bundles))
        for tree, key in graph.add_bundle(bundle):
            if "m_gridComponents" in tree:
                raw_compositions.append((tree, key, bundle.name))
    element_sets: dict[str, list[dict]] = {}
    for tree, key, bundle_name in raw_compositions:
        comp = _composition(tree, bundle_name)
        set_tree = graph.resolve(key, tree.get("m_gridElementSet"))
        if set_tree:
            set_name = set_tree.get("m_Name", "")
            comp["elementSet"] = set_name
            if set_name not in element_sets:
                set_key = graph.key_of(key, tree["m_gridElementSet"])
                element_sets[set_name] = _catalogue(graph, set_key, set_tree)
        compositions.append(comp)
    columns = Counter()
    for comp in compositions:
        for p in comp["panels"]:
            columns[comp["breakpoint"]] = max(columns[comp["breakpoint"]], p["x"] + p["w"])
    for comp in compositions:
        comp["columns"] = columns[comp["breakpoint"]] or 20
    _write(root, "compositions", compositions)
    _write(root, "element_sets", element_sets)

    # Screen structure trees
    uxml_count = 0
    if include_uxml:
        trees, guids = {}, {}
        uxml_bundles = gamedata.bundles(paths.bundles, gamedata.UXML_BUNDLES)
        for i, bundle in enumerate(uxml_bundles):
            report("screens", i, len(uxml_bundles))
            items = list(gamedata.monobehaviours_with_keys(bundle, with_path_id=True))
            inline = {pid: [_inline_css(r) for r in stylesheet.decode(t).rules]
                      for t, _, pid in items if stylesheet.is_stylesheet(t) and t.get("m_Name") == "inlineStyle"}
            for t, guid, _ in items:
                if "m_VisualTree" in t and t.get("m_Name"):
                    sheet = (t.get("inlineSheet") or {}).get("m_PathID")
                    trees[t["m_Name"]] = _uxml_tree(t, inline.get(sheet)) | {"bundle": bundle.name, "guid": guid}
                    if guid:
                        guids[guid] = t["m_Name"]
        uxml_count = len(trees)
        _write(root, "uxml", trees)
        _write(root, "uxml_guids", guids)

    manifest = {"version": INDEX_VERSION, "build": build, "tokens": len(tokens), "sheets": len(sheets),
                "compositions": len(compositions), "screens": uxml_count, "columns": dict(columns)}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    report("done", 1, 1)
    return GameIndex(root)
