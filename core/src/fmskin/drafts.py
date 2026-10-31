"""Working copies: edits never touch the real skin until the user saves.

Opening a pack in the studio copies it to a private working folder; every edit goes there. Saving first zips the
current real skin into a backup folder the user chose, then copies the working folder's changes into the real skin
(file by file, so FM27 can keep the skin selected while it runs). An unsaved working copy survives a restart.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import zipfile
from pathlib import Path

from .skinpack import MARKER, PackError


def drafts_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FMSkinStudio" / "drafts"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FMSkinStudio" / "drafts"


def _files(folder: Path) -> dict[str, str]:
    """Relative path -> content hash for every file in a skin folder."""
    out = {}
    for f in folder.rglob("*"):
        if f.is_file() and not f.name.endswith(".tmp"):
            out[f.relative_to(folder).as_posix()] = hashlib.sha1(f.read_bytes()).hexdigest()
    return out


def _base_file(root: Path, name: str) -> Path:
    return root / f"{name}.base.json"  # kept beside the working copy, so it never ends up in the skin


def _write_base(real: Path, root: Path) -> None:
    _base_file(root, real.name).write_text(json.dumps(_files(real)), encoding="utf-8")


def _base(root: Path, name: str) -> dict | None:
    try:
        return json.loads(_base_file(root, name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _refresh(real: Path, draft: Path, root: Path) -> None:
    shutil.rmtree(draft)
    shutil.copytree(real, draft)
    _write_base(real, root)


def open_draft(real: Path, root: Path) -> tuple[Path, bool]:
    """The working copy for a skin, made from the real one if there isn't one yet. Returns (folder, existed).
    A working copy with no edits of its own follows the skin on disk: if the skin was changed outside the studio
    since the copy was made, the copy is refreshed instead of looking like unsaved work (and overwriting it on save)."""
    if not (real / MARKER).is_file():
        raise PackError("Only skins made with FM Skin Studio can be edited (this keeps other skins safe)")
    draft = root / real.name
    if (draft / "skin.json").is_file():
        if not edited(real, draft, root):
            if _files(real) != _files(draft):
                _refresh(real, draft, root)
            elif _base(root, real.name) is None:
                _write_base(real, root)
        return draft, True
    if draft.exists():
        shutil.rmtree(draft)
    draft.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(real, draft)
    _write_base(real, root)
    return draft, False


def edited(real: Path, draft: Path, root: Path) -> bool:
    """Whether the working copy holds the user's own edits (not just an older copy of the skin)."""
    now = _files(draft)
    base = _base(root, real.name)
    if base is not None:
        return any(now.get(k) != v for k, v in base.items() if k != MARKER) or any(k not in base for k in now if k != MARKER)
    # copies made before the base was recorded: a file only counts as an edit if the copy's version is the newer one
    on_disk = _files(real)
    for rel in set(now) | set(on_disk):
        if rel == MARKER or now.get(rel) == on_disk.get(rel):
            continue
        d, r = draft / rel, real / rel
        if not r.exists() or not d.exists() or d.stat().st_mtime > r.stat().st_mtime:
            return True
    return False


def changes(real: Path, draft: Path) -> dict[str, list[str]]:
    a, b = _files(real), _files(draft)
    return {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)),
            "changed": sorted(k for k in set(a) & set(b) if a[k] != b[k] and k != MARKER)}


def is_dirty(real: Path, draft: Path, root: Path | None = None) -> bool:
    if root is not None:
        return edited(real, draft, root)
    return any(changes(real, draft).values())


def backup(real: Path, backup_dir: Path) -> Path:
    """Zip the real skin folder into the user's backup folder (the skin folder sits at the top of the zip)."""
    if not backup_dir or not str(backup_dir).strip():
        raise PackError("Choose a backup folder first")
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if backup_dir.resolve() == real.resolve() or real.resolve() in backup_dir.resolve().parents:
        raise PackError("Pick a backup folder outside the skin itself")
    target = backup_dir / f"{real.name}-backup-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(real.rglob("*")):
            if f.is_file():
                z.write(f, f"{real.name}/{f.relative_to(real).as_posix()}")
    return target


def save(real: Path, draft: Path, backup_dir: Path | None = None) -> dict:
    """Make the real skin match the working copy, backing up the previous version first when a folder is given.
    `real` may not exist yet (saving to a skins folder the user picked): then the whole skin is written there."""
    if real.exists() and not (real / MARKER).is_file():
        raise PackError(f"{real} holds a skin that wasn't made with FM Skin Studio, so it isn't replaced")
    archive = backup(real, backup_dir) if backup_dir and real.exists() else None
    if not real.exists():
        shutil.copytree(draft, real)
        _write_base(real, draft.parent)
        return {"backup": None, "added": sorted(_files(draft)), "changed": [], "removed": [], "savedTo": str(real)}
    diff = changes(real, draft)
    for rel in diff["added"] + diff["changed"] + [MARKER]:
        src, dst = draft / rel, real / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".tmp")
            shutil.copyfile(src, tmp)
            os.replace(tmp, dst)
    for rel in diff["removed"]:
        (real / rel).unlink(missing_ok=True)
    _write_base(real, draft.parent)
    return {"backup": str(archive) if archive else None, **diff, "savedTo": str(real)}


def share_zip(folder: Path, dest: Path, name: str) -> Path:
    """A standard .zip (the format Windows' "Compressed (zipped) folder" makes) with the skin folder at the top,
    ready to unzip into someone's FM27 skins folder."""
    dest = dest if dest.suffix.lower() == ".zip" else dest.with_suffix(".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob("*")):
            if f.is_file() and not f.name.endswith(".tmp"):
                z.write(f, f"{name}/{f.relative_to(folder).as_posix()}")
    return dest


def discard(draft: Path) -> None:
    if draft.exists():
        shutil.rmtree(draft)
    _base_file(draft.parent, draft.name).unlink(missing_ok=True)
