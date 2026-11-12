"""Turn a skin into an installer package players can download and run (see gamepatch for what installing does).

<Skin> Installer.zip
  Install <Skin>.exe          the installer (finds FM27, backs up, installs; also restores backups)
  package/skin-package.json   what to install: name, skin folder, name colours, artwork made from the player's game
  package/skin/...            the skin's files (without anything the player's own FM27 provides)
  README.txt                  install, manual install, backup and restore instructions
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

from . import attributecolours, gamepatch
from .skinpack import MARKER, PackError, SkinPack

INSTALLER_NAME = "FM27-Skin-Installer.exe"
LEAVE_OUT = {"LOCAL-USE-ONLY.txt"}

README = """{name} - Football Manager 27 skin
{description}
Made with FM Skin Studio.

WHAT THE INSTALLER DOES
{changes}
INSTALL (recommended)
  1. Close Football Manager 27.
  2. Extract this zip anywhere (right-click > Extract All).
  3. Double-click "Install {name}.exe". Windows may ask for permission: the installer needs it to change FM27's own
     files{admin_note}.
  4. Check the FM27 install it found (Game Pass, Steam or Epic), choose a folder for the backup, click Install.
  5. Start FM27, open Preferences and choose "{name}" as the skin. Press Reload Skin if FM27 was already open.

BACKUP AND RESTORE
  Before changing anything the installer copies every file it will change into the backup folder you chose
  ("{name} backup <date>"), with RESTORE.txt explaining what changed. To undo:
    - run "Install {name}.exe" again and click "Restore a backup...", then pick that backup folder; or
    - copy the files from the backup's "game-files" folder back into your FM27 folder (same sub-folders); or
    - let your store repair FM27: Xbox app > Manage > Files > Verify and repair; Steam > Properties > Installed
      Files > Verify integrity of game files; Epic > Manage > Verify.
  FM27 updates also restore the game's original files: run the installer again after an update.

MANUAL INSTALL (skin only)
  Copy the folder package\\skin into your skins folder and rename it "{folder}":
    Documents\\Sports Interactive\\Football Manager 27\\skins\\{folder}
{manual_note}
UNINSTALL
  Restore your backup (above), or delete the skins\\{folder} folder and pick another skin in Preferences.
{attributes}"""


def _slug(text: str) -> str:
    return re.sub(r"[^\w\- ]+", "", text).strip() or "Skin"


def _hex(value: str | None) -> str | None:
    m = re.fullmatch(r"\s*rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+).*\)\s*", value or "")
    if m:
        return "#" + "".join(f"{int(x):02x}" for x in m.groups())
    return value if value and re.fullmatch(r"#[0-9a-fA-F]{6}", value) else None


def installer_exe() -> Path:
    """The installer program shipped with the studio (or built locally in development)."""
    if getattr(sys, "frozen", False):  # packaged: resources/core/fmskin-core.exe, resources/installer/<exe>
        candidates = [Path(sys.executable).resolve().parent.parent / "installer" / INSTALLER_NAME]
    else:
        root = Path(__file__).resolve().parents[2]  # core/
        candidates = [root / "pkg" / INSTALLER_NAME, root / "pkg" / "installer" / INSTALLER_NAME]
    for c in candidates:
        if c.is_file():
            return c
    raise PackError("The skin installer isn't included in this copy of FM Skin Studio")


def options_for(pack: SkinPack) -> dict:
    """What a package of this skin would do, for the studio to show before making one."""
    info = pack.info
    return {"name": pack.name, "folder": pack.path.name, "suggestedColour": _hex(pack.tokens().get("--global-text-primary")),
            "fromGame": [r["file"] for r in info.get("fromGame") or []], "description": info.get("description", ""),
            "attributeColours": attributecolours.get(pack)}


def make_package(pack: SkinPack, dest: Path, name_colour: str | None = None, description: str = "",
                 exe: Path | None = None) -> Path:
    """Write "<Skin> Installer.zip". name_colour (#rrggbb) also patches FM27's name colours when installed."""
    if name_colour and not re.fullmatch(r"#[0-9a-fA-F]{6}", name_colour):
        raise PackError("Name colour must look like #37003c")
    exe = exe or installer_exe()
    info = pack.info
    from_game = info.get("fromGame") or []
    built = {r["file"] for r in from_game}
    name = _slug(pack.name)
    manifest = {"format": gamepatch.FORMAT, "name": pack.name, "skinFolder": pack.path.name,
                "description": description or info.get("description", ""), "fromGame": from_game}
    if name_colour:
        manifest["nameColours"] = {"colour": name_colour.lower(), "background": "#ffffff"}
    bands = attributecolours.get(pack)
    if bands:
        manifest["attributeColours"] = bands

    changes = ["  - Copies the skin into your FM27 skins folder (Documents\\Sports Interactive\\Football Manager 27\\skins)."]
    if name_colour:
        changes.append(f"  - Changes FM27's colours for club, team and player names to {name_colour.lower()} so they're readable on\n"
                       "    this skin. This edits one of FM27's own files (fm_Data\\StreamingAssets\\aa\\StandaloneWindows64\\\n"
                       f"    {gamepatch.NAME_BUNDLE}), which is backed up first. It affects every skin until restored.")
    if from_game:
        changes.append("  - Makes some of the skin's fonts and artwork from your own copy of FM27, so none of the game's\n"
                       "    licensed files are inside this download.")
    manual = ("  A manual install doesn't change the name colours or make the artwork from your game, so names stay white\n"
              "  and some pictures or fonts will be missing. Use the installer for the full skin.\n") if (name_colour or from_game) else ""
    readme = README.format(name=pack.name, description=manifest["description"], changes="\n".join(changes) + "\n",
                           admin_note=" (Steam installs live in Program Files)" if name_colour else "",
                           folder=pack.path.name, manual_note=manual,
                           attributes=("\n" + attributecolours.instructions(bands)) if bands else "")

    dest.parent.mkdir(parents=True, exist_ok=True)
    top = f"{name} Installer"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(exe, f"{top}/Install {name}.exe")
        z.writestr(f"{top}/README.txt", readme)
        z.writestr(f"{top}/package/{gamepatch.PACKAGE_FILE}", json.dumps(manifest, indent=2))
        for f in sorted(pack.path.rglob("*")):
            rel = f.relative_to(pack.path).as_posix()
            if f.is_dir() or rel in built or f.name in LEAVE_OUT or rel.startswith("."):
                continue
            if f.name == MARKER:  # keep the studio marker, without anything about the author's PC
                data = {k: v for k, v in json.loads(f.read_text(encoding="utf-8")).items() if k not in ("fromGame",)}
                z.writestr(f"{top}/package/skin/{rel}", json.dumps(data, indent=2))
                continue
            z.write(f, f"{top}/package/skin/{rel}")
    return dest
