"""Skin packs: self-contained folders in the game's skins root, loadable from FM27's Preferences.

Safety rules (spec D3 / R3a):
- every project is its own pack folder, created by this tool and marked with MARKER;
- the tool never writes to, renames or deletes a folder without that marker;
- name clashes get a numeric suffix, never an overwrite.
"""

from __future__ import annotations

import json
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__, uss

MARKER = "fmskinstudio.json"
TOKENS_SHEET = "tokens.uss"
# Screen sheets live in the pack root: FM27 resolves url()/@import relative to, and confined to, the folder of
# the sheet itself, so every sheet sits next to assets/ and can reference "assets/...".
SCREEN_PREFIX = "screen-"
ASSETS_DIR = "assets"
LAYOUTS_DIR = "layouts"
FONT_EXTS = {".ttf", ".otf"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


class PackError(Exception):
    pass


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] or "skin"


def unique_folder(skins_root: Path, wanted: str) -> Path:
    candidate, n = skins_root / wanted, 2
    while candidate.exists():
        candidate, n = skins_root / f"{wanted}-{n}", n + 1
    return candidate


def read_skin_json(folder: Path) -> dict:
    try:
        return json.loads((folder / "skin.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def list_skins(skins_root: Path) -> list[dict]:
    if not skins_root.is_dir():
        return []
    out = []
    for folder in sorted(p for p in skins_root.iterdir() if p.is_dir()):
        manifest = read_skin_json(folder)
        out.append({"id": folder.name, "name": (manifest.get("Name") or "").strip() or folder.name,
                    "path": str(folder), "managed": (folder / MARKER).is_file(),
                    "sheets": manifest.get("Sheets") or []})
    return out


@dataclass
class SkinPack:
    path: Path

    @property
    def id(self) -> str:
        return self.path.name

    @property
    def managed(self) -> bool:
        return (self.path / MARKER).is_file()

    def _require_managed(self) -> None:
        if not self.managed:
            raise PackError(f"'{self.path.name}' was not created by FM Skin Studio; duplicate it as a new pack to edit it.")

    # ---- metadata -------------------------------------------------------------------------
    @property
    def skin_json(self) -> dict:
        return read_skin_json(self.path)

    @property
    def name(self) -> str:
        return (self.skin_json.get("Name") or "").strip() or self.path.name

    @property
    def info(self) -> dict:
        try:
            return json.loads((self.path / MARKER).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _write_info(self, **changes) -> None:
        info = self._portable(self.info | changes | {"updated": time.strftime("%Y-%m-%dT%H:%M:%S")})
        (self.path / MARKER).write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    def _portable(self, value):
        """Packs get shared: never record a path from the author's PC. Absolute paths become the packaged copy's
        pack-relative path (assets/images/x.png) when there is one, else just the file name."""
        if isinstance(value, dict):
            return {k: self._portable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._portable(v) for v in value]
        if isinstance(value, str) and (re.match(r"^[A-Za-z]:[\\/]", value) or value.startswith(("/", "\\\\"))):
            name = re.split(r"[\\/]", value)[-1]
            for sub in ("images", "fonts"):
                if (self.path / ASSETS_DIR / sub / name).is_file():
                    return f"{ASSETS_DIR}/{sub}/{name}"
            return name
        return value

    def sheets(self) -> list[str]:
        return list(self.skin_json.get("Sheets") or [])

    def write_skin_json(self, name: str | None = None, extra_sheets: list[str] | None = None) -> None:
        """Rewrite skin.json: tokens sheet first, then per-screen sheets, then any other sheets kept from before."""
        self._require_managed()
        screens = sorted(p.name for p in self.path.glob(f"{SCREEN_PREFIX}*.uss"))
        others = [s for s in (extra_sheets if extra_sheets is not None else self.sheets())
                  if s != TOKENS_SHEET and not s.startswith(SCREEN_PREFIX)]
        sheets = ([TOKENS_SHEET] if (self.path / TOKENS_SHEET).is_file() else []) + screens + others
        data = {"Name": name if name is not None else self.name, "Sheets": sheets}
        (self.path / "skin.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._write_info()

    def rename(self, name: str) -> None:
        self.write_skin_json(name=name.strip() or self.path.name)

    # ---- theme ----------------------------------------------------------------------------
    def tokens(self) -> dict[str, str]:
        f = self.path / TOKENS_SHEET
        return uss.read_tokens(f.read_text(encoding="utf-8")) if f.is_file() else {}

    def token_selectors(self) -> dict[str, str]:
        f = self.path / TOKENS_SHEET
        blocks = uss.read_token_rules(f.read_text(encoding="utf-8")) if f.is_file() else {}
        return {name: sel for sel, block in blocks.items() for name in block}

    def set_tokens(self, changes: dict[str, str | None], groups: dict[str, str] | None = None,
                   selectors: dict[str, str] | None = None) -> dict[str, str]:
        """Merge token edits (None removes an override) and rewrite tokens.uss.

        `selectors` maps a token to the selector the game defines it on when that isn't :root
        (e.g. chart colours), so the override wins over the game's own rule.
        """
        self._require_managed()
        tokens = self.tokens()
        where = self.token_selectors() | (selectors or {})
        for name, value in changes.items():
            if not name.startswith("--"):
                raise PackError(f"Not a theme token: {name}")
            if value is None:
                tokens.pop(name, None)
            else:
                tokens[name] = value.strip()
        (self.path / TOKENS_SHEET).write_text(
            uss.render_tokens(tokens, groups, {n: s for n, s in where.items() if n in tokens}), encoding="utf-8")
        self.write_skin_json()
        return tokens

    def screen_sheet(self, screen: str) -> str:
        f = self.path / f"{SCREEN_PREFIX}{slugify(screen)}.uss"
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    def write_screen_sheet(self, screen: str, text: str) -> str:
        self._require_managed()
        rel = f"{SCREEN_PREFIX}{slugify(screen)}.uss"
        target = self.path / rel
        if text.strip():
            target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        elif target.exists():
            target.unlink()
        self.write_skin_json()
        return rel

    def add_asset(self, source: Path) -> str:
        """Copy a font or image into the pack; returns the url() value to use from a sheet in the pack root."""
        self._require_managed()
        ext = source.suffix.lower()
        if ext in FONT_EXTS:
            sub = "fonts"
        elif ext in IMAGE_EXTS:
            sub = "images"
        else:
            raise PackError(f"Unsupported file type {ext}: fonts must be .ttf/.otf, images .png/.jpg/.jpeg")
        dest_dir = self.path / ASSETS_DIR / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / re.sub(r"[^\w.\-]+", "_", source.name)
        shutil.copyfile(source, dest)
        return f'url("{ASSETS_DIR}/{sub}/{dest.name}")'

    # ---- layouts stored inside the pack ---------------------------------------------------
    def layouts_dir(self) -> Path:
        return self.path / LAYOUTS_DIR

    def layout_files(self) -> list[Path]:
        d = self.layouts_dir()
        return sorted(p for p in d.iterdir() if p.is_file()) if d.is_dir() else []


def create_pack(skins_root: Path, name: str, source: SkinPack | None = None) -> SkinPack:
    """Create a brand-new pack folder. With `source`, copy that skin's files in first (Duplicate as new pack)."""
    skins_root.mkdir(parents=True, exist_ok=True)
    folder = unique_folder(skins_root, slugify(name))
    if source:
        shutil.copytree(source.path, folder, ignore=shutil.ignore_patterns(MARKER))
    else:
        folder.mkdir()
    pack = SkinPack(folder)
    (folder / MARKER).write_text(json.dumps({
        "tool": "FM Skin Studio", "toolVersion": __version__, "game": "Football Manager 27",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "duplicatedFrom": source.id if source else None,
    }, indent=2), encoding="utf-8")
    if not (folder / TOKENS_SHEET).exists():
        (folder / TOKENS_SHEET).write_text(uss.render_tokens({}), encoding="utf-8")
    pack.write_skin_json(name=name.strip() or folder.name, extra_sheets=source.sheets() if source else [])
    return pack


def delete_pack(pack: SkinPack) -> None:
    pack._require_managed()
    shutil.rmtree(pack.path)


def export_pack(pack: SkinPack, dest: Path) -> Path:
    """Zip only the pack's own files (never game assets) into a .fmskin archive."""
    dest = dest if dest.suffix else dest.with_suffix(".fmskin")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(pack.path.rglob("*")):
            if f.is_file():
                zf.write(f, f"{pack.id}/{f.relative_to(pack.path).as_posix()}")
    return dest


def import_pack(archive: Path, skins_root: Path) -> SkinPack:
    """Unpack a .fmskin as a NEW pack folder (never over an existing one)."""
    with zipfile.ZipFile(archive) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        tops = {n.split("/", 1)[0] for n in names}
        if len(tops) != 1 or not any(n.endswith("/skin.json") and n.count("/") == 1 for n in names):
            raise PackError("Not a skin pack: expected one folder containing skin.json")
        top = tops.pop()
        skins_root.mkdir(parents=True, exist_ok=True)
        folder = unique_folder(skins_root, slugify(top))
        for n in names:
            rel = Path(n.split("/", 1)[1])
            if rel.is_absolute() or ".." in rel.parts:
                raise PackError(f"Unsafe path in archive: {n}")
            target = folder / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(n))
    pack = SkinPack(folder)
    if not pack.managed:
        (folder / MARKER).write_text(json.dumps({"tool": "FM Skin Studio", "toolVersion": __version__,
                                                 "importedFrom": archive.name}, indent=2), encoding="utf-8")
    return pack
