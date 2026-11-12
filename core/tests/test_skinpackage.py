import json
import zipfile
from pathlib import Path

import pytest

from fmskin import gamepatch, installer_app, skinpack, skinpackage
from fmskin.skinpack import PackError


def test_recolour_makes_names_readable_on_white():
    white = {"r": 1.0, "g": 1.0, "b": 1.0, "a": 0.0}
    assert gamepatch.recolour(white, "#37003c") == {"r": 55 / 255, "g": 0.0, "b": 60 / 255, "a": 0.0}
    yellow = {"r": 0.97, "g": 1.0, "b": 0.07, "a": 0.0}  # "your players": unreadable on white
    darker = gamepatch.recolour(yellow, "#37003c")
    assert darker and darker["r"] < 0.6 and darker["b"] < darker["r"]  # darkened, still yellow-ish
    dark_red = {"r": 0.6, "g": 0.0, "b": 0.1, "a": 0.0}
    assert gamepatch.recolour(dark_red, "#37003c") is None  # already readable: left alone


def _fake_game(tmp_path):
    game = tmp_path / "FM27"
    (game / "fm_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64").mkdir(parents=True)
    (game / "fm.exe").write_bytes(b"x")
    return game


def test_package_install_and_restore(skins_root, tmp_path, monkeypatch):
    monkeypatch.setattr(gamepatch, "game_running", lambda: False)  # the real FM27 may be open on this PC
    pack = skinpack.create_pack(skins_root, "Night Shift")
    pack.set_tokens({"--global-text-primary": "rgb(10, 20, 30)"})
    (pack.path / "LOCAL-USE-ONLY.txt").write_text("not for sharing", encoding="utf-8")
    exe = tmp_path / "installer.exe"
    exe.write_bytes(b"MZ")
    assert skinpackage.options_for(pack)["suggestedColour"] == "#0a141e"
    zip_path = skinpackage.make_package(pack, tmp_path / "out" / "Night Shift Installer.zip", None, "A test", exe=exe)
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        z.extractall(tmp_path / "out")
    top = "Night Shift Installer"
    assert f"{top}/Install Night Shift.exe" in names and f"{top}/README.txt" in names
    assert f"{top}/package/skin/tokens.uss" in names
    assert not any(n.endswith("LOCAL-USE-ONLY.txt") for n in names)
    manifest = json.loads((tmp_path / "out" / top / "package" / gamepatch.PACKAGE_FILE).read_text(encoding="utf-8"))
    assert manifest["skinFolder"] == pack.path.name and "nameColours" not in manifest

    game, skins, backups = _fake_game(tmp_path), tmp_path / "player-skins", tmp_path / "backups"
    skins.mkdir()
    (skins / pack.path.name).mkdir()  # an older copy of the skin is kept in the backup
    (skins / pack.path.name / "old.txt").write_text("old", encoding="utf-8")
    result = gamepatch.install(tmp_path / "out" / top / "package", game, backups, skins, log=lambda m: None)
    installed = skins / pack.path.name
    assert (installed / "tokens.uss").is_file() and not (installed / "old.txt").exists()
    backup = next(backups.iterdir())
    assert (backup / "RESTORE.txt").is_file() and "Verify and repair" in (backup / "RESTORE.txt").read_text(encoding="utf-8")
    assert result["patched"] == []
    gamepatch.restore(backup, log=lambda m: None)
    assert (installed / "old.txt").read_text(encoding="utf-8") == "old"


def test_install_refuses_a_folder_that_isnt_fm27(tmp_path):
    with pytest.raises(PackError):
        gamepatch.check_install(tmp_path)


def test_restore_needs_a_backup_folder(tmp_path):
    assert installer_app.main(["--restore", str(tmp_path)]) == 2


def test_reinstall_then_restore_puts_the_true_original_back(tmp_path, monkeypatch):
    """Installing twice must not back up the already-changed file as the "original" (user report 2026-11-11)."""
    import shutil
    import time
    monkeypatch.setattr(gamepatch, "game_running", lambda: False)

    def fake_patch(bundle, colour, background="#ffffff"):
        data = bundle.read_bytes()
        return data.replace(b"WHITE", b"PURPLE"), (["a name"] if b"WHITE" in data else [])
    monkeypatch.setattr(gamepatch, "patch_names", fake_patch)
    game = _fake_game(tmp_path)
    bundle = game / "fm_Data" / "StreamingAssets" / "aa" / "StandaloneWindows64" / gamepatch.NAME_BUNDLE
    bundle.write_bytes(b"names WHITE")
    pkg = tmp_path / "pkg"
    (pkg / "skin").mkdir(parents=True)
    (pkg / "skin" / "skin.json").write_text("{}", encoding="utf-8")
    (pkg / gamepatch.PACKAGE_FILE).write_text(json.dumps({"format": 1, "name": "Purple", "skinFolder": "purple",
                                                          "nameColours": {"colour": "#37003c"}}), encoding="utf-8")
    backups, skins = tmp_path / "backups", tmp_path / "skins"
    skins.mkdir()
    gamepatch.install(pkg, game, backups, skins, log=lambda m: None)
    assert bundle.read_bytes() == b"names PURPLE"
    time.sleep(1.1)  # backups are named by the second
    second = gamepatch.install(pkg, game, backups, skins, log=lambda m: None)
    assert bundle.read_bytes() == b"names PURPLE"
    kept = Path(second["backup"]) / "game-files" / bundle.relative_to(game)
    assert kept.read_bytes() == b"names WHITE"  # the true original, not the changed file
    gamepatch.restore(Path(second["backup"]), log=lambda m: None)
    assert bundle.read_bytes() == b"names WHITE"

    # a backup made by an older installer over the changed file still restores the original from its neighbour
    bundle.write_bytes(b"names PURPLE")
    broken = backups / "Purple backup 2099-01-01 000000"
    shutil.copytree(second["backup"], broken)
    (broken / "game-files" / bundle.relative_to(game)).write_bytes(b"names PURPLE")
    record = json.loads((broken / gamepatch.RECORD_FILE).read_text(encoding="utf-8"))
    record["files"] = [{"path": record["files"][0]["path"], "sha256": "x", "changed": []}]
    (broken / gamepatch.RECORD_FILE).write_text(json.dumps(record), encoding="utf-8")
    gamepatch.restore(broken, log=lambda m: None)
    assert bundle.read_bytes() == b"names WHITE"

    # with no original anywhere, a reinstall refuses rather than backing up the changed file
    lonely = tmp_path / "other-backups"
    bundle.write_bytes(b"names PURPLE")
    with pytest.raises(PackError):
        gamepatch.install(pkg, game, lonely, skins, log=lambda m: None)
    assert not list(lonely.glob("*/game-files"))
