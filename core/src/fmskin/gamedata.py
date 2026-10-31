"""Thin wrapper over UnityPy for the bundle groups the studio needs."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import UnityPy

STYLE_BUNDLES = ("ui-styles_",)
LAYOUT_BUNDLES = ("ui-tileslayouts_", "ui-tactics_", "ui-dynamiccardcollections_")
UXML_BUNDLES = ("ui-visualtreeassets_",)
MATCH_BUNDLES = ("ui-match_",)

Progress = Callable[[str, int, int], None]


def bundles(bundle_dir: Path, prefixes: tuple[str, ...]) -> list[Path]:
    return sorted(p for p in bundle_dir.glob("*.bundle") if p.name.startswith(prefixes))


class ObjectGraph:
    """MonoBehaviours from several bundles, with PPtr ({m_FileID, m_PathID}) resolution across them."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, int], tuple[dict, str, list[str]]] = {}

    def add_bundle(self, bundle: Path) -> Iterator[tuple[dict, tuple[str, int]]]:
        env = UnityPy.load(str(bundle))
        for obj in env.objects:
            if obj.type.name != "MonoBehaviour":
                continue
            try:
                tree = obj.read_typetree()
            except Exception:
                continue
            cab = obj.assets_file.name.lower()
            externals = [e.path.replace("\\", "/").split("/")[-1].lower() for e in obj.assets_file.externals]
            key = (cab, obj.path_id)
            self._objects[key] = (tree, cab, externals)
            yield tree, key

    def resolve(self, owner: tuple[str, int], pptr: dict | None) -> dict | None:
        if not pptr or not pptr.get("m_PathID"):
            return None
        entry = self._objects.get(owner)
        if not entry:
            return None
        _, cab, externals = entry
        fid = pptr.get("m_FileID", 0)
        target_cab = cab if fid == 0 else (externals[fid - 1] if 0 < fid <= len(externals) else None)
        found = self._objects.get((target_cab, pptr["m_PathID"])) if target_cab else None
        return found[0] if found else None

    def key_of(self, owner: tuple[str, int], pptr: dict) -> tuple[str, int] | None:
        entry = self._objects.get(owner)
        if not entry or not pptr.get("m_PathID"):
            return None
        _, cab, externals = entry
        fid = pptr.get("m_FileID", 0)
        target_cab = cab if fid == 0 else (externals[fid - 1] if 0 < fid <= len(externals) else None)
        return (target_cab, pptr["m_PathID"]) if target_cab else None


def monobehaviours_with_keys(bundle: Path, with_path_id: bool = False) -> Iterator[tuple]:
    """Like monobehaviours(), plus the asset's addressable GUID (the bundle container key) when it has one."""
    env = UnityPy.load(str(bundle))
    keys: dict[int, str] = {}
    for key, ref in env.container.items():
        try:
            keys.setdefault(ref.path_id, key)
        except AttributeError:
            continue
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        yield (tree, keys.get(obj.path_id), obj.path_id) if with_path_id else (tree, keys.get(obj.path_id))


def fonts(bundle_dir: Path, names: set[str]) -> dict[str, bytes]:
    """Raw font files by name (for the local preview only; never exported)."""
    out: dict[str, bytes] = {}
    for bundle in sorted(bundle_dir.glob("ui-fonts*.bundle")) + sorted(bundle_dir.glob("ui-styles_assets_default.bundle")):
        env = UnityPy.load(str(bundle))
        for obj in env.objects:
            if obj.type.name != "Font":
                continue
            try:
                font = obj.read()
            except Exception:
                continue
            if font.m_Name in names and font.m_Name not in out and getattr(font, "m_FontData", None):
                out[font.m_Name] = bytes(font.m_FontData)
    return out


def monobehaviours(bundle: Path) -> Iterator[dict]:
    """Yield the typetree of every readable MonoBehaviour in a bundle."""
    env = UnityPy.load(str(bundle))
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            yield obj.read_typetree()
        except Exception:
            continue
