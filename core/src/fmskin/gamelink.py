"""Game Link: an optional, opt-in add-on that runs a small plugin inside FM27.

It installs a pinned BepInEx 6 build (the standard Unity mod loader) plus the FM Skin Studio plugin into the game
folder, records every file it adds, and removes exactly those files again. The plugin reloads skins, takes
screenshots and applies the selected skin's name colour; it never touches saves or game logic. The studio talks to it over a local socket
(127.0.0.1 only) with a token the plugin writes into its config folder.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sys
import urllib.request
import zipfile
from pathlib import Path

from .skinpack import PackError

BEPINEX_BUILD = "6.0.0-be.791+b782da4"
BEPINEX_URL = ("https://builds.bepinex.dev/projects/bepinex_be/791/"
               "BepInEx-Unity.IL2CPP-win-x64-6.0.0-be.791%2Bb782da4.zip")
BEPINEX_SHA256 = "bb1c510909b69522733791f3a0817a487379a52da6468a492f1c9c19b3ec6f9a"  # be.791, verified 2026-10-31
PLUGIN_DIR = "FMSkinStudio.GameLink"
PORT = 47827
TOKEN_FILE = "FMSkinStudio.GameLink.token"


def studio_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "FMSkinStudio"
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FMSkinStudio"


RECORD = "FMSkinStudio.GameLink.json"  # kept in the game folder: what Game Link added, so removal is exact


def _record_file(game: Path) -> Path:
    return game / RECORD


def _record(game: Path) -> dict:
    try:
        return json.loads(_record_file(game).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_record(game: Path, data: dict) -> None:
    _record_file(game).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _game_running() -> bool:
    if sys.platform != "win32":
        return False
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq fm.exe", "/NH"], capture_output=True, text=True).stdout
    return "fm.exe" in out.lower()


def status(game: Path | None, plugin_dll: Path | None = None) -> dict:
    if not game or not (game / "fm.exe").is_file():
        return {"available": False, "reason": "FM27 install not found"}
    bep = game / "BepInEx"
    rec = _record(game)
    log = bep / "LogOutput.log"
    log_tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-40:] if log.is_file() else []
    plugin = bep / "plugins" / PLUGIN_DIR / f"{PLUGIN_DIR}.dll"
    return {
        "available": True,
        "loader": (game / "winhttp.dll").is_file() and (bep / "core").is_dir(),
        "loaderOurs": bool(rec.get("loader")),
        "loaderBuild": rec.get("build"),
        "bindings": (bep / "interop").is_dir() and any((bep / "interop").glob("*.dll")),
        "plugin": plugin.is_file(),
        "pluginBundled": bool(plugin_dll and plugin_dll.is_file()),
        "gameRunning": _game_running(),
        "connected": ping(game) is not None,
        "otherPlugins": sorted(p.name for p in (bep / "plugins").iterdir() if p.name != PLUGIN_DIR) if (bep / "plugins").is_dir() else [],
        "logErrors": [l for l in log_tail if "[Error" in l or "[Fatal" in l][-8:],
    }


def _download(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / f"BepInEx-{BEPINEX_BUILD.replace('+', '_')}.zip"
    if not target.is_file():
        tmp = target.with_suffix(".part")
        req = urllib.request.Request(BEPINEX_URL, headers={"User-Agent": "FM-Skin-Studio"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
        except OSError as e:
            tmp.unlink(missing_ok=True)
            raise PackError(f"Couldn't download BepInEx (check your internet connection): {getattr(e, 'reason', e)}") from None
        os.replace(tmp, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    if BEPINEX_SHA256 and digest != BEPINEX_SHA256:
        target.unlink(missing_ok=True)
        raise PackError("The downloaded BepInEx didn't match the expected build; nothing was installed")
    return target


def install(game: Path, plugin_dll: Path | None) -> dict:
    """Add the loader (unless the game already has BepInEx) and the plugin. Every added file is recorded."""
    if not (plugin_dll and plugin_dll.is_file()):
        raise PackError("The Game Link helper is missing from this copy of FM Skin Studio")
    if _game_running():
        raise PackError("Close Football Manager 27 first")
    rec = _record(game) or {"files": [], "dirs": []}
    added: list[str] = list(rec.get("files", []))
    try:
        _install_files(game, plugin_dll, rec, added)
    except PermissionError:
        raise PackError("Windows didn't allow changes to the FM27 folder. Run FM Skin Studio as administrator once to "
                        "set up Game Link, or install FM27 outside Program Files") from None
    finally:  # always record what was added, so Remove can undo a partial install
        rec["files"] = added
        if added:
            _write_record(game, rec)
    return status(game, plugin_dll)


def _install_files(game: Path, plugin_dll: Path | None, rec: dict, added: list[str]) -> None:
    unfinished = bool(added) and not rec.get("loader")  # an earlier install stopped part-way: finish it
    if unfinished or not (game / "winhttp.dll").is_file():
        archive = _download(studio_dir() / "cache")
        with zipfile.ZipFile(archive) as z:
            for info in z.infolist():
                rel = Path(info.filename)
                if info.is_dir() or rel.is_absolute() or ".." in rel.parts:
                    continue
                out = game / rel
                if out.exists():
                    continue  # never overwrite anything already in the game folder
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                added.append(rel.as_posix())
        rec.update(loader=True, build=BEPINEX_BUILD, sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        cfg = game / "BepInEx" / "config" / "BepInEx.cfg"
        if not cfg.exists():  # no console window for players; BepInEx fills in its other settings on first launch
            cfg.parent.mkdir(parents=True, exist_ok=True)
            cfg.write_text("[Logging.Console]\n\nEnabled = false\n", encoding="utf-8")
            added.append(cfg.relative_to(game).as_posix())
    if plugin_dll and plugin_dll.is_file():
        dest = game / "BepInEx" / "plugins" / PLUGIN_DIR / plugin_dll.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(plugin_dll, dest)
        rel = dest.relative_to(game).as_posix()
        if rel not in added:
            added.append(rel)


def remove(game: Path) -> dict:
    """Remove what Game Link added. BepInEx's own generated folders go too when we installed it and no other mods use it."""
    if _game_running():
        raise PackError("Close Football Manager 27 first")
    rec = _record(game)
    shutil.rmtree(game / "BepInEx" / "plugins" / PLUGIN_DIR, ignore_errors=True)
    (game / "BepInEx" / "config" / TOKEN_FILE).unlink(missing_ok=True)
    others = [p for p in (game / "BepInEx" / "plugins").iterdir()] if (game / "BepInEx" / "plugins").is_dir() else []
    kept_loader = False
    if rec.get("loader"):
        if others:
            kept_loader = True  # other mods rely on BepInEx: leave the loader in place
        else:
            for rel in rec.get("files", []):
                (game / rel).unlink(missing_ok=True)
            shutil.rmtree(game / "BepInEx", ignore_errors=True)  # incl. generated interop/cache/config/logs
    _record_file(game).unlink(missing_ok=True)
    return {"removed": True, "keptLoader": kept_loader, "otherPlugins": [p.name for p in others]}


# ---- talking to the plugin ---------------------------------------------------------------------------------------
def _token(game: Path) -> str | None:
    try:
        return (game / "BepInEx" / "config" / TOKEN_FILE).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def request(game: Path, command: str, timeout: float = 5.0, **args) -> dict:
    token = _token(game)
    if not token:
        raise PackError("Game Link isn't running (start FM27 with Game Link installed)")
    with socket.create_connection(("127.0.0.1", PORT), timeout=timeout) as s:
        s.sendall((json.dumps({"token": token, "command": command, **args}) + "\n").encode("utf-8"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    reply = json.loads(buf.decode("utf-8") or "{}")
    if reply.get("error"):
        raise PackError(reply["error"])
    return reply


def ping(game: Path) -> dict | None:
    try:
        return request(game, "ping", timeout=1.0)
    except (OSError, PackError, ValueError):
        return None
