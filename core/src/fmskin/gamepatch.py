"""Installer packages: a skin plus optional changes to FM27's own files, installed on a player's PC.

A skin in the skins folder can't change what FM27's code paints (club, team and player names). A package can also
patch the game's name-colour data, the way "files only" light skins do. The installer:
  - finds the player's FM27 (Game Pass, Steam or Epic), or lets them pick it;
  - copies every game file it will change into a backup folder the player chooses, with RESTORE.txt and a record;
  - builds any artwork the skin takes from the player's own game (so a package never carries licensed files);
  - installs the skin into the player's skins folder and patches the name colours.
Restore copies the backed-up files back. An FM27 update or "Verify and repair" also restores the game files.
"""

from __future__ import annotations

import colorsys
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from . import paths
from .skinpack import PackError

PACKAGE_FILE = "skin-package.json"
RECORD_FILE = "fm-skin-backup.json"
NAME_BUNDLE = "gamemodules_assets_gameworldmatch.bundle"
NAME_ASSET = "EmbeddedDataClickedHandler"
FORMAT = 1


# ---- finding FM27 ------------------------------------------------------------------------------------------------
def _epic_installs() -> list[Path]:
    out = []
    manifests = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    for item in manifests.glob("*.item") if manifests.is_dir() else []:
        try:
            data = json.loads(item.read_text(encoding="utf-8", errors="replace"))
        except ValueError:
            continue
        if "football manager 27" in str(data.get("DisplayName", "")).lower() and data.get("InstallLocation"):
            out.append(Path(data["InstallLocation"]))
    return out


def find_installs() -> list[dict]:
    """Every FM27 install on this PC: [{store, root, bundles}]."""
    found, seen = [], set()
    candidates = [(c, "Game Pass" if "XboxGames" in str(c) else "Epic" if "Epic" in str(c) else "Steam")
                  for c in paths.windows_game_candidates()]
    for d in "CDEFGH":
        candidates.append((Path(f"{d}:\\") / "XboxGames" / paths.GAME_FOLDER / "Content", "Game Pass"))
    candidates += [(p, "Epic") for p in _epic_installs()]
    for root, store in candidates:
        bundles = paths.bundles_dir_for(root, "win32")
        key = str(root).lower()
        if key in seen or not bundles.is_dir():
            continue
        seen.add(key)
        found.append({"store": store, "root": str(root), "bundles": str(bundles)})
    return found


def check_install(root: Path) -> Path:
    bundles = paths.bundles_dir_for(root, "win32")
    if not (root / "fm.exe").is_file() or not bundles.is_dir():
        raise PackError("That folder isn't an FM27 install (it needs fm.exe and fm_Data). For Game Pass, pick the "
                        "'Content' folder inside XboxGames\\Football Manager 27.")
    return bundles


def game_running() -> bool:
    if sys.platform != "win32":
        return False
    import subprocess
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq fm.exe", "/NH"], capture_output=True, text=True).stdout
    return "fm.exe" in out.lower()


# ---- name colours ------------------------------------------------------------------------------------------------
def _hex_rgb(value: str) -> tuple[float, float, float]:
    v = value.lstrip("#")
    return int(v[0:2], 16) / 255, int(v[2:4], 16) / 255, int(v[4:6], 16) / 255


def _luminance(r: float, g: float, b: float) -> float:
    def ch(x):
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def recolour(colour: dict, target: str, background: str = "#ffffff") -> dict | None:
    """New colour for one name style, or None to keep it. Near-white names take the target colour; other colours
    too light to read on the background are darkened, keeping their hue (your club's orange stays orange)."""
    r, g, b = colour["r"], colour["g"], colour["b"]
    if min(r, g, b) > 0.93:
        tr, tg, tb = _hex_rgb(target)
        return {**colour, "r": tr, "g": tg, "b": tb}
    bg = _luminance(*_hex_rgb(background))
    ratio = lambda c: (max(bg, _luminance(*c)) + 0.05) / (min(bg, _luminance(*c)) + 0.05)
    if ratio((r, g, b)) >= 4.5:
        return None
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    while l > 0.05 and ratio(colorsys.hls_to_rgb(h, l, s)) < 4.5:
        l -= 0.02
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return {**colour, "r": nr, "g": ng, "b": nb}


def _colours(o, path=""):
    if isinstance(o, dict):
        if set(o) >= {"r", "g", "b", "a"} and len(o) == 4:
            yield path, o
            return
        for k, v in o.items():
            yield from _colours(v, f"{path}.{k}")


def patch_names(bundle: Path, target: str, background: str = "#ffffff") -> tuple[bytes, list[str]]:
    """The name-colour bundle with names recoloured, plus what changed. The game file itself isn't touched."""
    import UnityPy
    env = UnityPy.load(bundle.read_bytes())  # from memory: the file must stay free to be replaced
    changed = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        if tree.get("m_Name") != NAME_ASSET:
            continue
        for path, colour in list(_colours(tree)):
            new = recolour(colour, target, background)
            if new:
                colour.update(new)
                changed.append(path.lstrip("."))
        obj.save_typetree(tree)
        break
    else:
        raise PackError("This FM27 version's name colours weren't found; the skin is installed without them")
    data = env.file.save(packer="original")
    check = UnityPy.load(data)  # read it back: a file FM27 can't open must never be written
    if not any(o.type.name == "MonoBehaviour" and o.read_typetree().get("m_Name") == NAME_ASSET for o in check.objects
               if o.type.name == "MonoBehaviour"):
        raise PackError("The patched name colours couldn't be read back; nothing was changed")
    return data, changed


# ---- artwork taken from the player's own game -----------------------------------------------------------------
def _cover(im, w, h):
    from PIL import Image
    r = max(w / im.width, h / im.height)
    im = im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def _game_objects(bundles: Path, wanted: dict[str, set[str]]) -> dict[str, object]:
    """{name: texture image or font bytes} for the named objects in the named bundles."""
    import UnityPy
    out = {}
    for bundle, names in wanted.items():
        env = UnityPy.load((bundles / bundle).read_bytes())
        for obj in env.objects:
            if obj.type.name not in ("Texture2D", "Font"):
                continue
            try:
                name = obj.peek_name()
            except Exception:
                continue
            if name in names and name not in out:
                data = obj.read()
                out[name] = data.image if obj.type.name == "Texture2D" else bytes(data.m_FontData)
    return out


def build_game_art(bundles: Path, recipes: list[dict], dest: Path) -> list[str]:
    """Make the skin's files that come from the player's own FM27 (fonts, logos, backgrounds), following the
    package's recipes: [{file, bundle, object, ...steps}]. Steps: crop [x0,y0,x1,y1], lighten (share of the original
    kept), darken (share of black mixed in), size [w, h], gradient [from, to, w, h]; logo {object, bundle, size,
    right | align: center, opacity} is drawn on top."""
    from PIL import Image
    wanted: dict[str, set[str]] = {}
    for r in recipes:
        wanted.setdefault(r["bundle"], set()).add(r["object"])
        if r.get("logo"):
            wanted.setdefault(r["logo"]["bundle"], set()).add(r["logo"]["object"])
    objects = _game_objects(bundles, wanted)
    made = []
    for r in recipes:
        src = objects.get(r["object"])
        if src is None:
            raise PackError(f"This FM27 version doesn't have '{r['object']}' that the skin uses")
        target = dest / r["file"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(src, bytes):
            target.write_bytes(src)
        else:
            if r.get("gradient"):
                a, b, w, h = r["gradient"]
                a, b = _hex_rgb(a), _hex_rgb(b)
                im = Image.new("RGB", (w, h))
                px = im.load()
                for x in range(w):
                    t = x / max(1, w - 1)
                    c = tuple(round(255 * (a[i] + (b[i] - a[i]) * t)) for i in range(3))
                    for y in range(h):
                        px[x, y] = c
            else:
                rgba = src.convert("RGBA")
                bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                bg.alpha_composite(rgba)
                im = bg.convert("RGB")
                if r.get("crop"):
                    im = im.crop(tuple(r["crop"]))
                if "lighten" in r:
                    im = Image.blend(Image.new("RGB", im.size, "white"), im, float(r["lighten"]))
                if r.get("size"):
                    im = _cover(im, *r["size"])
            if r.get("logo"):
                spec = r["logo"]
                logo_src = objects[spec["object"]].convert("RGBA")
                size = int(spec.get("size", im.height - 20))
                logo = logo_src.resize((size, size), Image.LANCZOS)
                if "opacity" in spec:  # a faint watermark
                    alpha = logo.getchannel("A").point(lambda v: round(v * float(spec["opacity"])))
                    logo.putalpha(alpha)
                x = (im.width - size) // 2 if spec.get("align") == "center" else im.width - size - int(spec.get("right", 150))
                canvas = im.convert("RGBA")
                canvas.alpha_composite(logo, (x, (im.height - size) // 2))
                im = canvas.convert("RGB")
            if "darken" in r:  # keep backgrounds dark enough behind white panels
                im = Image.blend(im, Image.new("RGB", im.size, "black"), float(r["darken"]))
            if target.suffix.lower() == ".png":
                im.save(target)
            else:
                im.save(target, quality=92)
        made.append(r["file"])
    return made


# ---- install and restore -----------------------------------------------------------------------------------------
def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


RESTORE_TEXT = """FM27 skin backup - {skin}
Made {when} by the {skin} installer (FM Skin Studio).

What was changed
  Game folder: {game}
{files}
  Skin folder added: {skin_dir}
{previous}
How to put everything back
  1. Close Football Manager 27.
  2. Easiest: run the installer again and choose "Restore a backup", then pick this folder.
  3. By hand: copy every file from the "game-files" folder here into the game folder above, keeping the same
     sub-folders (fm_Data\\StreamingAssets\\aa\\StandaloneWindows64), and replace the files there.
  4. Or let the store repair the game: Xbox app > Football Manager 27 > Manage > Files > Verify and repair;
     Steam > Football Manager 27 > Properties > Installed Files > Verify integrity of game files;
     Epic > Library > Football Manager 27 > ... > Manage > Verify.
  5. To remove the skin itself, delete its folder (above) and pick another skin in FM27's Preferences.

Keep this folder until you've uninstalled the skin. FM27 updates also put the original game files back; run the
installer again after an update to re-apply the skin.
"""


def install(package: Path, game_root: Path, backup_root: Path, skins_root: Path, log=print) -> dict:
    """Install a package on this PC. Nothing in the game folder changes until its backup is safely written."""
    manifest = json.loads((package / PACKAGE_FILE).read_text(encoding="utf-8"))
    if int(manifest.get("format", 1)) > FORMAT:
        raise PackError("This skin needs a newer installer")
    if game_running():
        raise PackError("Close Football Manager 27 first")
    bundles = check_install(game_root)
    stamp = time.strftime("%Y-%m-%d %H%M%S")
    backup = backup_root / f"{manifest['name']} backup {stamp}"
    (backup / "game-files").mkdir(parents=True, exist_ok=True)
    skin_dir = skins_root / manifest["skinFolder"]
    record = {"format": FORMAT, "skin": manifest["name"], "game": str(game_root), "skinFolder": str(skin_dir),
              "made": stamp, "files": [], "previousSkin": None}

    # 1. what will change, backed up first
    patched = None
    if manifest.get("nameColours"):
        bundle = bundles / NAME_BUNDLE
        log("Preparing the name colours...")
        nc = manifest["nameColours"]
        patched, changed = patch_names(bundle, nc["colour"], nc.get("background", "#ffffff"))
        rel = bundle.relative_to(game_root)
        (backup / "game-files" / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundle, backup / "game-files" / rel)
        record["files"].append({"path": str(rel), "sha256": _sha(bundle), "changed": changed})
    if skin_dir.exists():
        shutil.copytree(skin_dir, backup / "previous-skin" / skin_dir.name)
        record["previousSkin"] = str(backup / "previous-skin" / skin_dir.name)
    (backup / RECORD_FILE).write_text(json.dumps(record, indent=2), encoding="utf-8")
    files = "\n".join(f"    {f['path']} (name colours)" for f in record["files"]) or "    (no game files)"
    previous = (f"  The skin folder already existed; the old copy is in previous-skin\\{skin_dir.name}.\n"
                if record["previousSkin"] else "")
    (backup / "RESTORE.txt").write_text(RESTORE_TEXT.format(skin=manifest["name"], when=stamp, game=game_root,
                                                            files=files, skin_dir=skin_dir, previous=previous),
                                        encoding="utf-8")
    log(f"Backup saved in {backup}")

    # 2. the skin, with any artwork taken from this player's own game
    log("Installing the skin...")
    staging = skins_root / f".{manifest['skinFolder']}.installing"
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(package / "skin", staging)
    if manifest.get("fromGame"):
        log("Building the artwork from your FM27...")
        build_game_art(bundles, manifest["fromGame"], staging)
    shutil.rmtree(skin_dir, ignore_errors=True)
    staging.rename(skin_dir)

    # 3. the game file, last
    if patched is not None:
        log("Applying the name colours...")
        target = bundles / NAME_BUNDLE
        tmp = target.with_suffix(".skin-new")
        tmp.write_bytes(patched)
        os.replace(tmp, target)
    log("Done.")
    return {"backup": str(backup), "skin": str(skin_dir), "patched": [f["path"] for f in record["files"]]}


def restore(backup: Path, log=print) -> dict:
    """Put back everything a backup holds: game files, and the skin folder as it was (or remove the added one)."""
    record_file = backup / RECORD_FILE
    if not record_file.is_file():
        raise PackError("That folder isn't a skin backup (it has no fm-skin-backup.json)")
    record = json.loads(record_file.read_text(encoding="utf-8"))
    if game_running():
        raise PackError("Close Football Manager 27 first")
    game = Path(record["game"])
    for f in record["files"]:
        src = backup / "game-files" / f["path"]
        dst = game / f["path"]
        if not src.is_file():
            raise PackError(f"The backup is missing {f['path']}")
        log(f"Restoring {f['path']}...")
        shutil.copy2(src, dst)
    skin_dir = Path(record["skinFolder"])
    shutil.rmtree(skin_dir, ignore_errors=True)
    if record.get("previousSkin") and Path(record["previousSkin"]).is_dir():
        shutil.copytree(record["previousSkin"], skin_dir)
    log("Restored.")
    return {"restored": [f["path"] for f in record["files"]], "skin": str(skin_dir)}
