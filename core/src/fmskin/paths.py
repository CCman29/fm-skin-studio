"""Locate the FM27 install and the per-user folders the game reads skins and layouts from.

Windows locations were confirmed against a real install; macOS locations follow Unity's
conventions and still need confirming on a Mac (see spec D6).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

GAME_FOLDER = "Football Manager 27"
COMPANY = "Sports Interactive"


@dataclass
class GamePaths:
    platform: str
    game_root: Path | None = None  # folder holding fm_Data (Windows) or Data (macOS)
    bundles: Path | None = None  # StreamingAssets/aa/<target>
    user_docs: Path | None = None  # game "documents" folder (graphics/, skins/ ...)
    persistent: Path | None = None  # Unity persistentDataPath (layouts, Player.log on Windows)
    player_log: Path | None = None
    skins_dir: Path | None = None  # a skins folder the user picked (when the game's own isn't found)
    problems: list[str] = field(default_factory=list)

    @property
    def skins_root(self) -> Path | None:
        if self.skins_dir:
            return self.skins_dir
        return self.user_docs / "skins" if self.user_docs else None

    @property
    def layouts_dir(self) -> Path | None:
        return self.persistent / "CustomGridCompositions" if self.persistent else None

    def game_build(self) -> str | None:
        """Identifier that changes whenever the game's content catalog changes."""
        if not self.bundles:
            return None
        catalog_hash = self.bundles.parent / "catalog.hash"
        if catalog_hash.is_file():
            return catalog_hash.read_text(encoding="utf-8", errors="replace").strip()
        catalog = self.bundles.parent / "catalog.bin"
        if catalog.is_file():
            return hashlib.sha1(catalog.read_bytes()).hexdigest()
        return None

    def to_json(self) -> dict:
        data = {k: (str(v) if isinstance(v, Path) else v) for k, v in asdict(self).items()}
        data["skins_root"] = str(self.skins_root) if self.skins_root else None
        data["layouts_dir"] = str(self.layouts_dir) if self.layouts_dir else None
        data["game_build"] = self.game_build()
        return data


def _windows_documents() -> Path:
    """The real Documents folder (honours OneDrive / folder redirection)."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

        documents = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(documents), 0, None, ctypes.byref(out)) == 0:
            path = Path(out.value)
            ctypes.windll.ole32.CoTaskMemFree(out)
            return path
    except Exception:
        pass
    return Path.home() / "Documents"


def _steam_libraries(steam_root: Path) -> list[Path]:
    libs = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    if vdf.is_file():
        for match in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="replace")):
            libs.append(Path(match.group(1).replace("\\\\", "\\")))
    return libs


def windows_game_candidates(env: dict[str, str] | None = None) -> list[Path]:
    env = env if env is not None else dict(os.environ)
    candidates: list[Path] = []
    for drive in ("C:", "D:", "E:", "F:"):
        candidates.append(Path(drive + "\\") / "XboxGames" / GAME_FOLDER / "Content")
    for base in (env.get("ProgramFiles(x86)"), env.get("ProgramFiles")):
        if base:
            for lib in _steam_libraries(Path(base) / "Steam"):
                candidates.append(lib / "steamapps" / "common" / GAME_FOLDER)
    for drive in ("D:", "E:", "F:"):
        candidates.append(Path(drive + "\\") / "SteamLibrary" / "steamapps" / "common" / GAME_FOLDER)
    if env.get("ProgramFiles"):
        candidates.append(Path(env["ProgramFiles"]) / "Epic Games" / GAME_FOLDER)
    return candidates


def mac_game_candidates(home: Path) -> list[Path]:
    steam = home / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / GAME_FOLDER
    roots = [Path("/Applications"), home / "Applications", steam]
    candidates = []
    for root in roots:
        for app in (f"{GAME_FOLDER}.app", "fm.app"):
            candidates.append(root / app / "Contents" / "Resources" / "Data")
    return candidates


def bundles_dir_for(game_root: Path, platform: str) -> Path:
    if platform == "darwin":
        return game_root / "StreamingAssets" / "aa" / "StandaloneOSX"
    return game_root / "fm_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64"


def detect(overrides: dict[str, str] | None = None, platform: str | None = None, home: Path | None = None) -> GamePaths:
    """Find all paths; any key of `overrides` (game_root, user_docs, persistent, player_log, skins) wins."""
    overrides = {k: v for k, v in (overrides or {}).items() if v}
    platform = platform or ("darwin" if sys.platform == "darwin" else "win32" if os.name == "nt" else sys.platform)
    home = home or Path.home()
    paths = GamePaths(platform=platform)

    if "game_root" in overrides:
        paths.game_root = Path(overrides["game_root"])
    else:
        candidates = mac_game_candidates(home) if platform == "darwin" else windows_game_candidates()
        paths.game_root = next((c for c in candidates if bundles_dir_for(c, platform).is_dir()), None)
    if paths.game_root:
        paths.bundles = bundles_dir_for(paths.game_root, platform)
        if not paths.bundles.is_dir():
            paths.problems.append(f"No game data under {paths.bundles}")
    else:
        paths.problems.append("Football Manager 27 install not found; set it in Settings.")

    if platform == "darwin":
        support = home / "Library" / "Application Support" / COMPANY / GAME_FOLDER
        paths.user_docs = Path(overrides.get("user_docs", support))
        paths.persistent = Path(overrides.get("persistent", support))
        default_log = home / "Library" / "Logs" / COMPANY / GAME_FOLDER / "Player.log"
    else:
        paths.user_docs = Path(overrides.get("user_docs", _windows_documents() / COMPANY / GAME_FOLDER))
        paths.persistent = Path(overrides.get("persistent", home / "AppData" / "LocalLow" / COMPANY / GAME_FOLDER))
        default_log = paths.persistent / "Player.log"
    paths.player_log = Path(overrides.get("player_log", default_log))
    if "skins" in overrides:
        paths.skins_dir = Path(overrides["skins"])

    if not paths.user_docs.is_dir():
        paths.problems.append(f"Game user folder not found at {paths.user_docs} (run FM27 once).")
    return paths
