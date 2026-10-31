"""Check a skin pack against the rules FM27's skin loader applies (see findings.md), before the game sees it."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from . import contrast, layouts, uss
from .skinpack import FONT_EXTS, IMAGE_EXTS, SkinPack

ERROR, WARNING, INFO = "error", "warning", "info"

# Seen in game (FM27, Unity 6000.3.18f1): the skin loader creates fonts from file paths, which the UI text engine
# rejects ("FontAsset is invalid. Please assign a Source Font File."); text falls back to a wider font and the log
# fills with warnings. Use one of the game's own fonts (fonts.builtin) until SI fixes it.
FONT_FILES_BLOCKED = ("FM27 can't load font files from skins yet (game bug): text falls back to a wider font and "
                      "Player.log fills with warnings. Use one of the game's built-in fonts instead.")


@dataclass
class Problem:
    severity: str
    file: str
    line: int
    message: str

    def to_json(self) -> dict:
        return asdict(self)


def _inside(root: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_sheet(pack: SkinPack, rel: str, known_tokens: set[str], local_tokens: set[str],
                 out: list[Problem], seen: set[Path]) -> None:
    path = pack.path / rel
    if path.resolve() in seen:
        return
    seen.add(path.resolve())
    doc = uss.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
    # The game confines a sheet's @import and url() targets to the folder the sheet itself is in.
    root = path.parent
    for line, msg in doc.errors:
        out.append(Problem(ERROR, rel, line, msg))
    for target, line in doc.imports:
        imported = path.parent / target
        if "://" in target or not _inside(root, imported):
            out.append(Problem(ERROR, rel, line, f"@import '{target}' is outside this sheet's folder; the game drops it"))
        elif not imported.is_file():
            out.append(Problem(ERROR, rel, line, f"@import '{target}' names a missing file; the game drops it"))
        else:
            _check_sheet(pack, imported.relative_to(pack.path).as_posix(), known_tokens, local_tokens, out, seen)
    if not doc.rules and not doc.imports:
        out.append(Problem(WARNING, rel, 1, "Sheet has no rules; the game will report 0 applied rules"))
    for rule in doc.rules:
        for d in rule.decls:
            problem = uss.check_value(d.value)
            if problem:
                out.append(Problem(ERROR, rel, d.line, f"'{d.name}': {problem}"))
            if d.name.startswith("--") and known_tokens and d.name not in known_tokens:
                out.append(Problem(INFO, rel, d.line, f"'{d.name}' isn't a token the game uses (new variable or typo?)"))
            for ref in uss.VAR_RE.findall(d.value):
                if known_tokens and ref not in known_tokens and ref not in local_tokens:
                    out.append(Problem(WARNING, rel, d.line, f"var({ref}) doesn't exist in the game or this pack"))
            for func, target in uss.asset_refs(d.value):
                if target.startswith("game-asset:"):
                    out.append(Problem(ERROR, rel, d.line, "Refers to a built-in game asset; pick your own file instead"))
                    continue
                asset = path.parent / target
                if "://" in target or not _inside(root, asset):
                    out.append(Problem(ERROR, rel, d.line, f"{func}('{target}') is outside this sheet's folder; "
                                                           "the game drops it"))
                elif asset.suffix.lower() not in FONT_EXTS | IMAGE_EXTS:
                    out.append(Problem(ERROR, rel, d.line, f"{func}('{target}'): only .png/.jpg/.jpeg/.ttf/.otf load"))
                elif not asset.is_file():
                    out.append(Problem(ERROR, rel, d.line, f"{func}('{target}') could not be resolved (file missing)"))
                elif asset.suffix.lower() in FONT_EXTS:
                    out.append(Problem(ERROR, rel, d.line, FONT_FILES_BLOCKED))


def validate_pack(pack: SkinPack, game_tokens: dict | None = None, compositions: list[dict] | None = None) -> list[Problem]:
    out: list[Problem] = []
    raw = pack.path / "skin.json"
    if not raw.is_file():
        return [Problem(ERROR, "skin.json", 0, "Missing skin.json; the game ignores this folder")]
    try:
        manifest = json.loads(raw.read_text(encoding="utf-8-sig"))
    except ValueError as e:
        return [Problem(ERROR, "skin.json", getattr(e, "lineno", 0), f"skin.json is malformed: {e}")]
    if not isinstance(manifest, dict):
        return [Problem(ERROR, "skin.json", 1, "skin.json must be an object like {\"Name\": ..., \"Sheets\": [...]}")]
    for key in manifest:
        if key.lower() in ("name", "sheets") and key not in ("Name", "Sheets"):
            out.append(Problem(ERROR, "skin.json", 1, f"Key '{key}' must be spelled '{key.capitalize()}' (case-sensitive)"))
    if not str(manifest.get("Name") or "").strip():
        out.append(Problem(WARNING, "skin.json", 1, "No Name; the game will show the folder name"))
    sheets = manifest.get("Sheets")
    if not isinstance(sheets, list) or not sheets:
        out.append(Problem(ERROR, "skin.json", 1, "skin.json lists no sheets; the game ignores this skin"))
        return out

    known = set(game_tokens or {})
    local: set[str] = set()
    for rel in sheets:
        p = pack.path / str(rel)
        if p.is_file() and p.suffix.lower() == ".uss":
            local |= set(uss.read_tokens(p.read_text(encoding="utf-8-sig", errors="replace")))
    seen: set[Path] = set()
    for rel in sheets:
        rel = str(rel)
        target = pack.path / rel
        if "://" in rel or not _inside(pack.path, target):
            out.append(Problem(ERROR, "skin.json", 1, f"Sheet '{rel}' escapes the skin folder; the whole skin is ignored"))
        elif not target.is_file():
            out.append(Problem(ERROR, "skin.json", 1, f"Sheet '{rel}' is missing; the whole skin is ignored"))
        elif target.suffix.lower() != ".uss":
            out.append(Problem(ERROR, "skin.json", 1, f"Sheet '{rel}' isn't a .uss file; the game won't load it"))
        else:
            _check_sheet(pack, rel, known, local, out, seen)

    for hit in contrast.light_surfaces(pack.tokens(), game_tokens or {}, pack.info.get("bars"), pack.path / "assets" / "images"):
        where = "screen-global.uss" if hit["token"].startswith("bars:") else "tokens.uss"
        out.append(Problem(WARNING, where, 0, contrast.WARNING_TEXT.format(min=contrast.MIN_RATIO, **hit)))

    if compositions is not None:
        by_name = {c["name"]: c for c in compositions}
        for f in pack.layout_files():
            rel = f"layouts/{f.name}"
            default = by_name.get(f.name)
            if not default:
                out.append(Problem(WARNING, rel, 0, "No screen in this game version has this layout name"))
            try:
                data = layouts.load(f)
            except ValueError as e:
                out.append(Problem(ERROR, rel, 0, f"Not valid layout JSON: {e}"))
                continue
            for issue in layouts.check(data, default["columns"] if default else 20, default):
                out.append(Problem(ERROR, rel, 0, f"{issue.panel}: {issue.message}"))
    return out
