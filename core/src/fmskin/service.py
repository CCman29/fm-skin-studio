"""Operations exposed to the desktop app (via rpc.py) and the CLI. All inputs/outputs are JSON-friendly."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import re

from . import __version__, bars, coded, drafts, fonts, gamedata, index, labels, layouts, logwatch, paths, preview, recipe, screenmap, skinpack, uss, validate
from .skinpack import PackError, SkinPack


def settings_file() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FMSkinStudio" / "settings.json"
    return Path(os.environ.get("APPDATA", Path.home())) / "FMSkinStudio" / "settings.json"


def _data_url(file: Path, max_width: int) -> str:
    import base64
    import io

    from PIL import Image
    im = Image.open(file).convert("RGB")
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


class Service:
    def __init__(self, settings_path: Path | None = None, cache: Path | None = None, backups: Path | None = None,
                 drafts_dir: Path | None = None):
        self.settings_path = settings_path or settings_file()
        self.cache, self.backups = cache, backups
        self.drafts_dir = drafts_dir or drafts.drafts_root()
        self._index: index.GameIndex | None = None
        self._comps: dict[str, dict] | None = None
        self._tokens: dict[str, dict] | None = None

    # ---- settings & paths --------------------------------------------------------------------
    def settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def set_settings(self, **changes) -> dict:
        data = self.settings() | {k: v for k, v in changes.items()}
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._index = self._comps = self._tokens = None
        return data

    @property
    def paths(self) -> paths.GamePaths:
        return paths.detect(self.settings().get("paths"))

    def ping(self) -> dict:
        return {"ok": True, "version": __version__}

    def get_paths(self) -> dict:
        return self.paths.to_json()

    # ---- index -------------------------------------------------------------------------------
    def index_status(self) -> dict:
        idx = index.open_index(self.paths, self.cache)
        return {"ready": idx is not None, "manifest": idx.manifest() if idx else None}

    def build_index(self, progress=None) -> dict:
        self._index = index.build_index(self.paths, self.cache, progress)
        self._comps = self._tokens = None
        return self._index.manifest()

    def _idx(self) -> index.GameIndex:
        if self._index is None:
            self._index = index.open_index(self.paths, self.cache)
            if self._index is None:
                raise RuntimeError("The game index isn't built yet")
        return self._index

    def _compositions(self) -> dict[str, dict]:
        if self._comps is None:
            self._comps = {c["name"]: c for c in self._idx().compositions()}
        return self._comps

    def _game_tokens(self) -> dict[str, dict]:
        if self._tokens is None:
            self._tokens = self._idx().tokens()
        return self._tokens

    # ---- theme -------------------------------------------------------------------------------
    def token_groups(self) -> dict:
        counts: dict[str, int] = {}
        for tok in self._game_tokens().values():
            counts[tok["group"]] = counts.get(tok["group"], 0) + 1
        return counts

    def tokens(self, pack: str | None = None, group: str | None = None, search: str | None = None,
               kind: str | None = None) -> list[dict]:
        overrides = self._pack(pack).tokens() if pack else {}
        out = []
        for name, tok in self._game_tokens().items():
            if group and tok["group"] != group:
                continue
            if kind and tok["kind"] != kind:
                continue
            if search and search.lower() not in name.lower():
                continue
            out.append({"name": name, "default": tok["value"], "resolved": tok["resolved"], "kind": tok["kind"],
                        "group": tok["group"], "selector": tok["selector"], "useCount": tok["useCount"],
                        "uses": tok["uses"], "referencedBy": tok.get("referencedBy", []), "key": tok.get("key"),
                        "override": overrides.get(name)} | labels.describe(name, tok))
        return sorted(out, key=lambda t: (-t["useCount"], t["name"]))

    def areas(self) -> dict:
        return labels.AREAS

    # ---- real-screen preview -----------------------------------------------------------------
    def _preview_cache(self) -> Path:
        return self._idx().root / "preview"

    def preview_assets(self) -> dict:
        """CSS for the preview (game stylesheets converted) + the game's own fonts, both cached locally."""
        cache = self._preview_cache()
        cache.mkdir(exist_ok=True)
        import hashlib  # the converted CSS depends on the preview code too: a new version gets a new file
        stamp = hashlib.sha1(preview.BASE_CSS.encode() + str(index.INDEX_VERSION).encode()).hexdigest()[:10]
        css_file, fonts_file = cache / f"theme-{stamp}.css", cache / "fonts.css"
        if not css_file.is_file():
            css_file.write_text(preview.build_css(self._idx().sheets()), encoding="utf-8")
        if not fonts_file.is_file():
            data = gamedata.fonts(self.paths.bundles, set(preview.FONT_FILES)) if self.paths.bundles else {}
            fonts_file.write_text(preview.font_faces(data), encoding="utf-8")
        return {"css": css_file.read_text(encoding="utf-8"), "fonts": fonts_file.read_text(encoding="utf-8")}

    def _screens_data(self) -> tuple[dict, dict]:
        if getattr(self, "_uxml", None) is None:
            self._uxml = (self._idx().screens(), self._idx().screen_guids())
        return self._uxml

    def preview_panel(self, name: str) -> dict:
        screens, guids = self._screens_data()
        tree = preview.render_tree(guids.get(name, name), screens, guids)
        if tree is None:
            raise KeyError(f"No screen file named {name}")
        return {"name": guids.get(name, name), "tree": tree}

    def preview_screen(self, name: str, pack: str | None = None) -> dict:
        """A grid screen: each placed panel with the screen file the game uses for it at that size."""
        detail = self.screen(name, pack)
        catalogue = {c["id"]: c for c in detail.get("catalogue") or []}
        placed = detail["layout"] or [{"id": p["id"], "x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"]}
                                      for p in detail["panels"]]
        screens, guids = self._screens_data()
        panels = []
        for p in placed:
            configs = (catalogue.get(p["id"]) or {}).get("configs") or []
            match = next((c for c in configs if c["size"] == [p["w"], p["h"]]), configs[0] if configs else None)
            uxml = guids.get(match["uxml"]) if match else None
            panels.append({"id": p["id"], "x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "uxml": uxml,
                           "tree": preview.render_tree(uxml, screens, guids) if uxml else None})
        return {"name": name, "columns": detail["columns"], "panels": panels}

    def _usage_index(self) -> tuple[dict, dict]:
        """token -> [(selector, property)] from the preview sheets; class -> screen files using it."""
        if getattr(self, "_usage", None) is None:
            sheets = self._idx().sheets()
            by_token: dict[str, list] = {}
            for sheet_name in preview.PREVIEW_SHEETS:
                if sheet_name not in sheets:
                    continue
                for rule in uss.parse(sheets[sheet_name]["uss"]).rules:
                    for d in rule.decls:
                        for ref in uss.VAR_RE.findall(d.value):
                            by_token.setdefault(ref, []).append((rule.selector, d.name))
            by_class: dict[str, set] = {}
            screens, _ = self._screens_data()

            def walk(node, owner):
                if not node:
                    return
                for c in node.get("c") or []:
                    by_class.setdefault(c, set()).add(owner)
                for ch in node.get("ch") or []:
                    walk(ch, owner)
            for sname, s in screens.items():
                walk(s.get("root"), sname)
            self._usage = (by_token, by_class)
        return self._usage

    def _panel_files(self) -> dict[str, set[str]]:
        """Screen files used as panels on real screens -> the screen layouts (compositions) that can show them."""
        if getattr(self, "_panels_cache", None) is None:
            _, guids = self._screens_data()
            out: dict[str, set[str]] = {}
            for comp in self._compositions().values():
                for entry in comp.get("catalogue") or []:
                    for c in entry.get("configs") or []:
                        if c["uxml"] in guids:
                            out.setdefault(guids[c["uxml"]], set()).add(comp["name"])
            self._panels_cache = out
        return self._panels_cache

    def token_usage(self, token: str, limit: int = 12) -> dict:
        """Where a setting shows up: the rules using it (directly or through settings built on it) and the screen
        files containing those elements, best example first."""
        by_token, by_class = self._usage_index()
        game = self._game_tokens()
        names, frontier = [token], [token]
        for _ in range(3):  # follow settings that are built on this one
            frontier = [r for t in frontier for r in (game.get(t) or {}).get("referencedBy", []) if r not in names]
            names += frontier
        rules = [(sel, prop, t) for t in names for sel, prop in by_token.get(t, [])]
        hits: dict[str, int] = {}
        selectors = []
        for sel, prop, _ in rules:
            last = re.split(r"\s*>\s*|\s+", sel.split(",")[0].strip())[-1]
            classes = re.findall(r"\.([^\s.#:>*]+)", last)
            if not classes:
                continue
            files = set.intersection(*[by_class.get(c, set()) for c in classes])
            for f in files:
                hits[f] = hits.get(f, 0) + 1
            selectors.append({"selector": sel, "property": prop, "files": len(files)})

        on_screens = self._panel_files()

        def score(f: str) -> tuple:
            # panels that really sit on screens first, then the ones this setting paints most
            return (f not in on_screens, -hits[f], len(f))
        files = sorted(hits, key=score)
        layouts: dict[str, int] = {}
        for f in files[:60]:
            for comp in on_screens.get(f, ()):
                layouts[comp] = layouts.get(comp, 0) + hits[f]
        comps = self._compositions()
        on = sorted(layouts, key=lambda c: (comps[c]["breakpoint"] != "Large", bool(re.search(r"-(FMC|IM)\b|InMatch", c)),
                                            -layouts[c]))
        seen, screens_list = set(), []
        for c in on:
            if comps[c]["screen"] not in seen:
                seen.add(comps[c]["screen"])
                screens_list.append({"layout": c, "screen": comps[c]["screen"], "area": comps[c]["area"]})
        return {"token": token, "via": names[1:12], "selectors": selectors[:40], "screens": files[:limit],
                "onScreens": screens_list[:10],
                "highlight": sorted({c for s in selectors[:200] for c in re.findall(r"\.([^\s.#:>*]+)",
                                     re.split(r"\s*>\s*|\s+", s["selector"].split(",")[0].strip())[-1])})}

    def sheet(self, name: str) -> dict:
        s = self._idx().sheets().get(name)
        if not s:
            raise KeyError(f"No stylesheet named {name}")
        return {"name": name} | s

    # ---- screens -----------------------------------------------------------------------------
    def screens(self, search: str | None = None, area: str | None = None, breakpoint: str | None = None,
                editable_only: bool = False, match_only: bool = False) -> list[dict]:
        rows = []
        for c in self._compositions().values():
            if search and search.lower() not in c["name"].lower():
                continue
            if area and c["area"] != area:
                continue
            if breakpoint and c["breakpoint"] != breakpoint:
                continue
            if editable_only and not c["editable"]:
                continue
            if match_only and not c["inMatch"]:
                continue
            rows.append({k: c[k] for k in ("name", "screen", "area", "breakpoint", "inMatch", "editable", "columns")}
                        | {"panels": len(c["panels"])})
        return sorted(rows, key=lambda r: (r["area"], r["screen"], r["breakpoint"]))

    def screen(self, name: str, pack: str | None = None) -> dict:
        comp = self._compositions().get(name)
        if not comp:
            raise KeyError(f"No screen layout named {name}")
        layout, source = self._layout(name, pack)
        placed = []
        if layout:
            for c in layout.get("m_gridComponents") or []:
                loc = c["m_location"]
                placed.append({"id": c["m_elementID"], "x": loc["x"], "y": loc["y"], "w": loc["width"], "h": loc["height"],
                               "sizes": layouts.allowed_sizes(layout, c["m_elementID"], comp, comp["columns"]),
                               "locked": next((p["locked"] for p in comp["panels"] if p["id"] == c["m_elementID"]), False)})
        return comp | {"layout": placed, "layoutSource": source}

    def _layout(self, name: str, pack: str | None) -> tuple[dict | None, str | None]:
        if pack:
            f = self._pack(pack).layouts_dir() / name
            if f.is_file():
                return layouts.load(f), "pack"
        player = self.paths.layouts_dir
        if player and (player / name).is_file():
            return layouts.load(player / name), "player"
        return None, None

    # ---- packs -------------------------------------------------------------------------------
    def _skins_root(self) -> Path:
        root = self.paths.skins_root
        if not root:
            raise RuntimeError("Skins folder unknown; set the game user folder in Settings")
        return root

    def _real_pack(self, pack_id: str) -> SkinPack:
        folder = self._skins_root() / pack_id
        if not (folder / "skin.json").is_file() or folder.parent.resolve() != self._skins_root().resolve():
            raise KeyError(f"No skin '{pack_id}'")
        return SkinPack(folder)

    def _pack(self, pack_id: str) -> SkinPack:
        """The pack being edited: its working copy while one is open (edits never touch the real skin until saved)."""
        real = self._real_pack(pack_id)
        draft = self.drafts_dir / real.path.name
        return SkinPack(draft) if (draft / "skin.json").is_file() else real

    # ---- working copies (save only on request) -----------------------------------------------
    def draft_open(self, pack: str) -> dict:
        real = self._real_pack(pack)
        folder, existed = drafts.open_draft(real.path, self.drafts_dir)
        return {"resumed": existed} | self.draft_status(pack)

    def draft_status(self, pack: str) -> dict:
        real = self._real_pack(pack)
        folder = self.drafts_dir / real.path.name
        skins = self.paths.skins_root
        base = {"backupFolder": self.settings().get("backupFolder"), "skinsFolder": str(skins) if skins else None,
                "skinsFolderFound": bool(skins and skins.is_dir())}
        if not (folder / "skin.json").is_file():
            return base | {"open": False, "dirty": False, "changes": {"added": [], "removed": [], "changed": []}}
        diff = drafts.changes(real.path, folder)
        return base | {"open": True, "dirty": drafts.is_dirty(real.path, folder, self.drafts_dir), "changes": diff}

    def draft_dirty(self) -> list[dict]:
        """Skins whose working copy has changes that aren't saved yet."""
        out = []
        if not self.drafts_dir.is_dir():
            return out
        for folder in sorted(self.drafts_dir.iterdir()):
            if not (folder / "skin.json").is_file():
                continue
            try:
                real = self._real_pack(folder.name)
            except (KeyError, RuntimeError):
                continue
            if drafts.is_dirty(real.path, folder, self.drafts_dir):
                out.append({"id": folder.name, "name": SkinPack(folder).name})
        return out

    def set_skins_folder(self, folder: str) -> dict:
        """Remember a skins folder the user picked (used when the game's own skins folder isn't found)."""
        overrides = dict(self.settings().get("paths") or {})
        overrides["skins"] = str(Path(folder))
        self.set_settings(paths=overrides)
        return self.get_paths()

    def set_backup_folder(self, folder: str) -> dict:
        self.set_settings(backupFolder=str(Path(folder)))
        return {"backupFolder": str(Path(folder))}

    def draft_save(self, pack: str, backup: bool = False, backup_dir: str | None = None) -> dict:
        """Save the working copy into the skins folder; back up the previous version first if asked. The skins folder
        may be one the user just picked, where this skin doesn't exist yet."""
        name = Path(pack).name
        folder = self.drafts_dir / name
        if not (folder / "skin.json").is_file():
            raise PackError("Nothing to save: this skin isn't open for editing")
        target = self.paths.skins_root
        if not target:
            raise PackError("Choose the skins folder to save into")
        directory = None
        if backup:
            directory = backup_dir or self.settings().get("backupFolder")
            if not directory:
                raise PackError("Choose a backup folder first")
            self.set_settings(backupFolder=str(Path(directory)))
        return drafts.save(Path(target) / name, folder, Path(directory) if directory else None)

    def share_pack(self, pack: str, dest: str) -> str:
        """Compress the skin as you see it in the studio into a .zip to share."""
        p = self._pack(pack)
        return str(drafts.share_zip(p.path, Path(dest), self._real_pack(pack).path.name))

    def draft_discard(self, pack: str) -> dict:
        real = self._real_pack(pack)
        drafts.discard(self.drafts_dir / real.path.name)
        return self.draft_open(pack)

    def packs(self) -> list[dict]:
        return skinpack.list_skins(self._skins_root())

    def create_pack(self, name: str, source: str | None = None) -> dict:
        pack = skinpack.create_pack(self._skins_root(), name, self._pack(source) if source else None)
        return self.pack(pack.id)

    def pack(self, pack: str) -> dict:
        p = self._pack(pack)
        return {"id": p.id, "name": p.name, "path": str(self._real_pack(pack).path), "managed": p.managed, "sheets": p.sheets(),
                "tokens": p.tokens(), "layouts": [f.name for f in p.layout_files()], "info": p.info}

    def set_tokens(self, pack: str, changes: dict[str, str | None]) -> dict:
        target = self._pack(pack)
        try:
            game = self._game_tokens()
        except RuntimeError:
            game = {}
        names = set(target.tokens()) | set(changes)
        groups = {n: game[n]["group"] for n in names if n in game}
        selectors = {n: game[n]["selector"] for n in changes if n in game and game[n]["selector"] != ":root"}
        return target.set_tokens(changes, groups, selectors)

    def rename_pack(self, pack: str, name: str) -> dict:
        self._pack(pack).rename(name)
        return self.pack(pack)

    def screen_sheet(self, pack: str, screen: str) -> str:
        return self._pack(pack).screen_sheet(screen)

    def write_screen_sheet(self, pack: str, screen: str, text: str) -> str:
        return self._pack(pack).write_screen_sheet(screen, text)

    # ---- screen editor -----------------------------------------------------------------------
    def pack_image(self, pack: str, path: str, max_width: int = 1280) -> str:
        """A picture inside a pack as a data URL, scaled down, for the preview (pack-relative paths only)."""
        target = self._pack(pack)
        file = (target.path / path).resolve()
        if target.path.resolve() not in file.parents or not file.is_file():
            raise KeyError(f"No picture {path} in this pack")
        return _data_url(file, max_width)

    def local_image(self, path: str, max_width: int = 1280) -> str:
        """A picture the user just picked (not in a pack yet), scaled down, for the live preview."""
        file = Path(path)
        if file.suffix.lower() not in (".png", ".jpg", ".jpeg") or not file.is_file():
            raise KeyError(f"No picture at {path}")
        return _data_url(file, max_width)

    def reference_shots(self) -> dict:
        return self.settings().get("referenceShots") or {}

    def set_reference_shot(self, layout: str, file: str | None) -> dict:
        """The user's own in-game screenshot for a screen, shown next to the preview. Stays on this PC (studio
        settings), never written into a pack."""
        shots = dict(self.reference_shots())
        if file:
            if Path(file).suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                raise PackError("Pick a .png, .jpg or .webp screenshot")
            shots[layout] = str(Path(file))
        else:
            shots.pop(layout, None)
        self.set_settings(referenceShots=shots)
        return shots

    def reference_image(self, layout: str) -> str | None:
        f = self.reference_shots().get(layout)
        return _data_url(Path(f), 1600) if f and Path(f).is_file() else None

    def pick_settings(self, classes: list[str]) -> list[str]:
        """Settings that style one clicked element (by its classes), plus the settings they're built from."""
        by_token, _ = self._usage_index()
        found = list(screenmap.tokens_for_classes(by_token, set(classes)))
        game = self._game_tokens()
        for t in list(found):
            for ref in uss.VAR_RE.findall((game.get(t) or {}).get("value") or ""):
                if ref not in found:
                    found.append(ref)
        return found

    def screen_catalog(self) -> list[dict]:
        return screenmap.catalog(set(self._compositions()))

    def screen_settings(self, name: str) -> dict:
        """Settings that paint something on this screen (directly, or through a setting they're built from).
        Every one of them is game-wide: the count says how many style rules across the game share it."""
        if getattr(self, "_screen_settings", None) is None:
            self._screen_settings = {}
        if name not in self._screen_settings:
            present: set[str] = set()
            for p in self.preview_screen(name)["panels"]:
                screenmap.classes_in(p["tree"], present)
            by_token, _ = self._usage_index()
            direct = screenmap.tokens_for_classes(by_token, present)
            game = self._game_tokens()
            found = dict(direct)
            frontier = list(direct)
            for _ in range(3):  # settings these are built from also change this screen
                nxt = []
                for t in frontier:
                    for ref in uss.VAR_RE.findall((game.get(t) or {}).get("value") or ""):
                        if ref not in found:
                            found[ref] = 0
                            nxt.append(ref)
                frontier = nxt
            self._screen_settings[name] = {"direct": direct, "all": found}
        data = self._screen_settings[name]
        rows = []
        for t in self.tokens():
            looks = "colour" if str(t["resolved"] or "").startswith(("rgb", "#")) else \
                "shape" if "radius" in t["name"] else None
            if t["name"] in data["all"] and t["name"] != "--none" and not t["technical"] and looks:
                rows.append(t | {"onScreen": data["direct"].get(t["name"], 0), "via": t["name"] not in data["direct"], "looks": looks})
        rows.sort(key=lambda r: (r["via"], -r["onScreen"], -r["useCount"]))
        return {"name": name, "settings": rows}

    def screen_backdrop(self, pack: str, key: str, file: str | None = None) -> dict:
        """A picture for one screen group only (training / recruit / club); None removes it."""
        target = self._pack(pack)
        if key not in screenmap.BACKDROP_HOOKS:
            raise PackError("This screen uses the main backdrop (set it in Bars & backgrounds)")
        state = dict(target.info.get("screenBackdrops") or {})
        if file:
            state[key] = target.add_asset(Path(file))
        else:
            state.pop(key, None)
        rules = ["/* Managed by FM Skin Studio: a different backdrop per screen (credits in CREDITS.txt). */"]
        rules += [f"{screenmap.BACKDROP_HOOKS[k]} {{ background-image: {u}; -unity-background-scale-mode: scale-and-crop; }}"
                  for k, u in state.items()]
        target.write_screen_sheet("backdrops", "\n".join(rules) + "\n")
        target._write_info(screenBackdrops=state)
        return state

    def screen_backdrops(self, pack: str) -> dict:
        target = self._pack(pack)
        state = dict(target.info.get("screenBackdrops") or {})
        if not state:  # packs built before this was recorded: read the sheet
            text = target.screen_sheet("backdrops") or ""
            for k, sel in screenmap.BACKDROP_HOOKS.items():
                m = re.search(re.escape(sel) + r"\s*\{\s*background-image:\s*(url\([^)]*\))", text)
                if m:
                    state[k] = m.group(1)
        return state

    def coded_areas(self, pack: str | None = None) -> dict:
        return coded.listing(self._pack(pack) if pack else None)

    def set_coded_area(self, pack: str, area: str, mode: str, file: str | None = None) -> dict:
        return coded.apply(self._pack(pack), area, mode, file)

    def add_asset(self, pack: str, file: str) -> str:
        return self._pack(pack).add_asset(Path(file))

    def font_catalog(self) -> dict:
        return fonts.catalog()

    def use_font(self, pack: str, font: str, role: str) -> dict:
        target = self._pack(pack)
        names = set(target.tokens()) | {fonts.ROLE_TOKENS.get(role, "")}
        try:
            game = self._game_tokens()
        except RuntimeError:
            game = {}
        return fonts.use_font(target, font, role, {n: game[n]["group"] for n in names if n in game})

    def apply_recipe(self, pack: str, palette: dict) -> dict:
        """Full theme from a palette: panels, text, tabs, Continue button, processing card, Tactics screen, bars."""
        return recipe.apply(self._pack(pack), recipe.Palette.from_json(palette))

    def recipe_preview(self, palette: dict) -> dict:
        """The settings a palette would set, for a live preview: nothing is written."""
        return recipe.tokens_for(recipe.Palette.from_json(palette))

    def recipe_fields(self) -> dict[str, list[str]]:
        """For each colour in the simple picker, the settings it changes (found by changing just that colour)."""
        from dataclasses import replace
        base = recipe.Palette()
        before = recipe.tokens_for(base)
        out = {}
        for name in ("panel", "tile", "dark", "accent", "highlight", "continue_colour", "text", "text_secondary", "border"):
            after = recipe.tokens_for(replace(base, **{name: "#123457"}))
            out[name] = sorted(k for k in after if after[k] != before.get(k))
        return out

    def recipe_defaults(self) -> dict:
        from dataclasses import asdict
        return asdict(recipe.Palette())

    def bars(self, pack: str) -> dict:
        return bars.current(self._pack(pack))

    def set_bars(self, pack: str, settings: dict) -> dict:
        target = self._pack(pack)
        bars.apply(target, {k: {kk: vv for kk, vv in v.items() if kk != "label"} for k, v in settings.items()})
        return bars.current(target)

    def use_builtin_font(self, pack: str, font: str, role: str) -> dict:
        return fonts.use_builtin(self._pack(pack), font, role)

    def reset_font(self, pack: str, role: str) -> dict:
        fonts.reset_font(self._pack(pack), role)
        return self.pack(pack)

    def validate(self, pack: str) -> list[dict]:
        try:
            game_tokens, comps = self._game_tokens(), list(self._compositions().values())
        except RuntimeError:
            game_tokens, comps = None, None
        return [p.to_json() for p in validate.validate_pack(self._pack(pack), game_tokens, comps)]

    def export_pack(self, pack: str, dest: str, backup_dir: str | None = None) -> str:
        """Export what's being edited; the skin as it is on disk is backed up first when a folder is given."""
        if backup_dir:
            drafts.backup(self._real_pack(pack).path, Path(backup_dir))
            self.set_settings(backupFolder=str(Path(backup_dir)))
        return str(skinpack.export_pack(self._pack(pack), Path(dest)))

    def import_pack(self, file: str) -> dict:
        return self.pack(skinpack.import_pack(Path(file), self._skins_root()).id)

    def delete_pack(self, pack: str) -> dict:
        real = self._real_pack(pack)
        drafts.discard(self.drafts_dir / real.path.name)
        skinpack.delete_pack(real)
        return {"deleted": pack}

    # ---- layouts -----------------------------------------------------------------------------
    def place_panels(self, pack: str, name: str, moves: dict[str, dict], save: bool = True) -> dict:
        comp = self._compositions().get(name)
        layout, _ = self._layout(name, pack)
        if not comp or not layout:
            raise KeyError("Customise this screen once in FM27 first, so the game creates its layout file")
        new, issues = layouts.place(layout, moves, comp["columns"], comp)
        if issues:
            return {"saved": False, "issues": [vars(i) for i in issues]}
        if save:
            layouts.save_to_pack(self._pack(pack), name, new)
        return {"saved": save, "issues": []}

    def apply_layouts(self, pack: str) -> dict:
        target = self.paths.layouts_dir
        if not target:
            raise RuntimeError("Layouts folder unknown")
        return layouts.apply_pack_layouts(self._pack(pack), target, self.backups)

    def layout_backups(self) -> list[dict]:
        return layouts.list_backups(self.backups)

    def restore_layouts(self, backup: str | None = None) -> dict:
        return layouts.restore(backup, self.backups)

    # ---- game log ----------------------------------------------------------------------------
    def log_events(self, offset: int = 0) -> dict:
        log = self.paths.player_log
        events, new_offset = logwatch.read_since(log, offset) if log else ([], 0)
        return {"events": [e.to_json() for e in events], "offset": new_offset}


ERRORS = (PackError, KeyError, RuntimeError, FileNotFoundError, ValueError)
