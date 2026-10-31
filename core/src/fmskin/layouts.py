"""Panel layouts ("grid compositions").

FM27 reads a player's custom layouts from <persistent>/CustomGridCompositions/<CompositionName>, one compact
JSON file per screen and breakpoint. Packs keep their layouts in <pack>/layouts/ and only copy them to the
player's folder on an explicit "Use this pack's layouts" (with a backup first).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .skinpack import SkinPack


def backups_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FMSkinStudio" / "layout-backups"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FMSkinStudio" / "layout-backups"


def load(path: Path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def dumps(data: dict) -> bytes:
    """Same shape as the game's writer: compact, UTF-8, no BOM, key order preserved."""
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(dumps(data))
    os.replace(tmp, path)


@dataclass
class Issue:
    panel: str
    message: str


def _rect(c: dict) -> tuple[int, int, int, int]:
    loc = c["m_location"]
    return loc["x"], loc["y"], loc["width"], loc["height"]


def check(layout: dict, columns: int, default: dict | None = None) -> list[Issue]:
    """Guard-rails: inside the grid, within each panel's min/max, no overlaps, locked panels untouched,
    and only panels the screen defines."""
    issues: list[Issue] = []
    comps = layout.get("m_gridComponents") or []
    default_panels: dict[str, dict] = {}
    catalogue: dict[str, dict] = {}
    if default:
        default_panels = {p["id"]: p for p in default["panels"]}
        default_panels.update({p["id"]: p for zone in default.get("optional", {}).values() for p in zone})
        catalogue = {p["id"]: p for p in default.get("catalogue") or []}
    for c in comps:
        pid = c.get("m_elementID", "?")
        x, y, w, h = _rect(c)
        (mnx, mny), (mxx, mxy) = _limits(c)
        ref = default_panels.get(pid)
        if default and pid not in default_panels and pid not in catalogue:
            issues.append(Issue(pid, "This screen doesn't have this panel"))
        if x < 0 or y < 0 or x + w > columns:
            issues.append(Issue(pid, f"Outside the grid (screen is {columns} columns wide)"))
        if not (mnx <= w <= mxx) or not (mny <= h <= mxy):
            issues.append(Issue(pid, f"Size {w}x{h} is outside this slot's {mnx}x{mny} to {mxx}x{mxy}"))
        if ref and ref["locked"] and (x, y, w, h) != (ref["x"], ref["y"], ref["w"], ref["h"]):
            issues.append(Issue(pid, "This panel is locked by the game and can't be moved or resized"))
    for i, a in enumerate(comps):
        ax, ay, aw, ah = _rect(a)
        for b in comps[i + 1:]:
            bx, by, bw, bh = _rect(b)
            if ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah:
                issues.append(Issue(a.get("m_elementID", "?"), f"Overlaps {b.get('m_elementID', '?')}"))
    return issues


def _limits(c: dict) -> tuple[tuple[int, int], tuple[int, int]]:
    """A slot's min and max size. The game stores 100 for "no limit" and 0 for "not set" (kept at its minimum).
    Any size in between is allowed: FM27 saves sizes like 10x10 that its panel files don't list, so the panel
    files' sizes are only what the content was designed at, not a rule."""
    mn, mx = c.get("m_minSize", {}), c.get("m_maxSize", {})
    mnx, mny = mn.get("x", 1) or 1, mn.get("y", 1) or 1
    mxx, mxy = mx.get("x", 100) or mnx, mx.get("y", 100) or mny
    return (mnx, mny), (mxx, mxy)


def allowed_sizes(layout: dict, panel_id: str, default: dict | None, columns: int = 20, rows: int = 16) -> list[list[int]]:
    """Every size the editor may offer for a placed panel: within its slot's min/max and the grid."""
    comp = next((c for c in layout.get("m_gridComponents") or [] if c.get("m_elementID") == panel_id), None)
    if not comp:
        return []
    (mnx, mny), (mxx, mxy) = _limits(comp)
    return [[w, h] for w in range(mnx, min(mxx, columns) + 1) for h in range(mny, min(mxy, rows) + 1)]


def place(layout: dict, moves: dict[str, dict], columns: int, default: dict | None = None) -> tuple[dict, list[Issue]]:
    """Return a copy of `layout` with panels moved/resized ({id: {x,y,w,h}}) and the guard-rail result.
    Only m_location values change; everything else (ids, references, flags) is kept verbatim."""
    out = json.loads(json.dumps(layout))
    known = {c.get("m_elementID"): c for c in out.get("m_gridComponents") or []}
    for pid, rect in moves.items():
        c = known.get(pid)
        if c is None:
            return out, [Issue(pid, "Panel isn't placed on this layout")]
        loc = c["m_location"]
        for key, src in (("x", "x"), ("y", "y"), ("width", "w"), ("height", "h")):
            if src in rect:
                loc[key] = int(rect[src])
    return out, check(out, columns, default)


def player_layouts(layouts_dir: Path) -> list[str]:
    return sorted(p.name for p in layouts_dir.iterdir() if p.is_file() and not p.name.endswith(".tmp")) \
        if layouts_dir.is_dir() else []


def save_to_pack(pack: SkinPack, name: str, layout: dict) -> Path:
    pack._require_managed()
    target = pack.layouts_dir() / Path(name).name
    write(target, layout)
    pack._write_info()
    return target


def apply_pack_layouts(pack: SkinPack, layouts_dir: Path, backups: Path | None = None) -> dict:
    """Copy the pack's layouts into the player's folder after backing up every file that will change."""
    files = pack.layout_files()
    if not files:
        return {"applied": [], "backup": None}
    backup_id = time.strftime("%Y%m%d-%H%M%S")
    backup_dir = (backups or backups_root()) / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for f in files:
        existing = layouts_dir / f.name
        if existing.is_file():
            shutil.copy2(existing, backup_dir / f.name)
        else:
            created.append(f.name)
    (backup_dir / "backup.json").write_text(json.dumps(
        {"pack": pack.id, "layoutsDir": str(layouts_dir), "created": created,
         "replaced": [f.name for f in files if f.name not in created]}, indent=2), encoding="utf-8")
    layouts_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copyfile(f, layouts_dir / f.name)
    return {"applied": [f.name for f in files], "backup": backup_id}


def list_backups(backups: Path | None = None) -> list[dict]:
    root = backups or backups_root()
    out = []
    for d in sorted(root.iterdir(), reverse=True) if root.is_dir() else []:
        meta = d / "backup.json"
        if meta.is_file():
            out.append({"id": d.name} | json.loads(meta.read_text(encoding="utf-8")))
    return out


def restore(backup_id: str | None = None, backups: Path | None = None) -> dict:
    """Undo an apply: put replaced files back and remove files the apply created."""
    available = list_backups(backups)
    entry = next((b for b in available if b["id"] == backup_id), None) if backup_id else (available[0] if available else None)
    if not entry:
        raise FileNotFoundError("No layout backup to restore")
    backup_dir = (backups or backups_root()) / entry["id"]
    layouts_dir = Path(entry["layoutsDir"])
    for name in entry.get("replaced", []):
        shutil.copy2(backup_dir / name, layouts_dir / name)
    for name in entry.get("created", []):
        (layouts_dir / name).unlink(missing_ok=True)
    return {"restored": entry["replaced"], "removed": entry["created"], "backup": entry["id"]}
