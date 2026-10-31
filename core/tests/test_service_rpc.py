import io
import json

from fmskin import rpc
from fmskin.service import Service


def make_service(tmp_path, skins_root):
    settings = tmp_path / "settings.json"
    svc = Service(settings_path=settings, cache=tmp_path / "cache", backups=tmp_path / "backups", drafts_dir=tmp_path / "drafts")
    svc.set_settings(paths={"user_docs": str(skins_root.parent), "persistent": str(tmp_path / "persist"),
                            "game_root": str(tmp_path / "no-game")})
    return svc


def test_pack_flow_without_game(tmp_path, skins_root, foreign_skin):
    svc = make_service(tmp_path, skins_root)
    created = svc.create_pack("Studio Test")
    assert created["managed"] and created["sheets"] == ["tokens.uss"]
    svc.set_tokens(created["id"], {"--global-text-primary": "rgb(255, 230, 0)"})
    assert svc.pack(created["id"])["tokens"] == {"--global-text-primary": "rgb(255, 230, 0)"}
    assert [p for p in svc.validate(created["id"]) if p["severity"] == "error"] == []
    ids = {p["id"] for p in svc.packs()}
    assert {"studio-test", "someone-elses-skin"} <= ids


def test_rpc_round_trip(tmp_path, skins_root):
    svc = make_service(tmp_path, skins_root)
    requests = "\n".join(json.dumps(r) for r in [
        {"id": 1, "method": "ping"},
        {"id": 2, "method": "packs.create", "params": {"name": "Via RPC"}},
        {"id": 3, "method": "packs.setTokens", "params": {"pack": "someone-elses-skin", "changes": {"--a": "rgb(1,2,3)"}}},
        {"id": 4, "method": "nope"},
        {"id": 5, "method": "shutdown"},
    ]) + "\n"
    out = io.StringIO()
    rpc.serve(svc, io.StringIO(requests), out)
    lines = [json.loads(l) for l in out.getvalue().splitlines()]
    by_id = {l.get("id"): l for l in lines if "id" in l}
    assert lines[0]["event"] == "ready"
    assert by_id[1]["result"]["ok"] is True
    assert by_id[2]["result"]["id"] == "via-rpc"
    assert "No skin" in by_id[3]["error"]["message"]
    assert by_id[4]["error"]["type"] == "MethodNotFound"


def test_edits_stay_in_the_working_copy_until_saved(tmp_path, skins_root):
    import zipfile
    svc = make_service(tmp_path, skins_root)
    pid = svc.create_pack("Draft Test")["id"]
    real = skins_root / pid
    before = (real / "tokens.uss").read_text()
    opened = svc.draft_open(pid)
    assert opened["open"] and not opened["dirty"] and not opened["resumed"]
    svc.set_tokens(pid, {"--global-text-primary": "rgb(1, 2, 3)"})
    assert (real / "tokens.uss").read_text() == before  # the real skin is untouched
    status = svc.draft_status(pid)
    assert status["dirty"] and status["changes"]["changed"] == ["tokens.uss"]
    assert svc.pack(pid)["tokens"] == {"--global-text-primary": "rgb(1, 2, 3)"}  # the editor sees the edit
    assert svc.draft_open(pid)["resumed"]  # reopening keeps unsaved work

    backups = tmp_path / "my backups"
    result = svc.draft_save(pid, backup=True, backup_dir=str(backups))
    assert "rgb(1, 2, 3)" in (real / "tokens.uss").read_text()
    with zipfile.ZipFile(result["backup"]) as z:  # the backup holds the skin as it was before saving
        assert z.read(f"{pid}/tokens.uss").decode().splitlines() == before.splitlines()
    assert not svc.draft_status(pid)["dirty"]
    assert svc.settings()["backupFolder"] == str(backups)

    svc.set_tokens(pid, {"--global-text-primary": "rgb(9, 9, 9)"})
    svc.draft_discard(pid)
    assert svc.pack(pid)["tokens"] == {"--global-text-primary": "rgb(1, 2, 3)"}  # discarding goes back to the saved skin


def test_foreign_skins_are_never_opened_for_editing(tmp_path, skins_root, foreign_skin):
    import pytest
    from fmskin.skinpack import PackError
    svc = make_service(tmp_path, skins_root)
    with pytest.raises(PackError):
        svc.draft_open("someone-elses-skin")


def test_save_without_backup_share_zip_and_picked_skins_folder(tmp_path, skins_root):
    import zipfile
    svc = make_service(tmp_path, skins_root)
    pid = svc.create_pack("Share Test")["id"]
    svc.draft_open(pid)
    svc.set_tokens(pid, {"--global-text-primary": "rgb(4, 5, 6)"})
    assert svc.draft_save(pid)["backup"] is None  # no backup unless asked
    assert "rgb(4, 5, 6)" in (skins_root / pid / "tokens.uss").read_text()

    out = svc.share_pack(pid, str(tmp_path / "out" / "my skin"))
    assert out.endswith("my skin.zip")
    with zipfile.ZipFile(out) as z:
        assert f"{pid}/skin.json" in z.namelist() and f"{pid}/tokens.uss" in z.namelist()

    other = tmp_path / "Other Skins"
    svc.set_skins_folder(str(other))  # e.g. the game's own skins folder wasn't found
    assert svc.get_paths()["skins_root"] == str(other)
    saved = svc.draft_save(pid)
    assert saved["savedTo"] == str(other / pid) and (other / pid / "skin.json").is_file()


def test_lists_skins_with_unsaved_changes(tmp_path, skins_root):
    svc = make_service(tmp_path, skins_root)
    a, b = svc.create_pack("Alpha")["id"], svc.create_pack("Beta")["id"]
    svc.draft_open(a); svc.draft_open(b)
    assert svc.draft_dirty() == []
    svc.set_tokens(b, {"--global-text-primary": "rgb(7, 7, 7)"})
    assert svc.draft_dirty() == [{"id": b, "name": "Beta"}]
    svc.draft_save(b)
    assert svc.draft_dirty() == []


def test_an_unedited_working_copy_follows_changes_made_outside_the_studio(tmp_path, skins_root):
    import os, time
    svc = make_service(tmp_path, skins_root)
    pid = svc.create_pack("Outside")["id"]
    svc.draft_open(pid)
    real = skins_root / pid / "tokens.uss"
    real.write_text(real.read_text() + "/* changed by another tool */\n")  # e.g. a script, or another copy of the app
    assert not svc.draft_status(pid)["dirty"] and svc.draft_dirty() == []
    svc.draft_open(pid)  # reopening refreshes the copy instead of keeping the old version
    assert "another tool" in (tmp_path / "drafts" / pid / "tokens.uss").read_text()

    # copies made before the starting point was recorded: an older copy isn't treated as the user's edits
    (tmp_path / "drafts" / f"{pid}.base.json").unlink()
    draft = tmp_path / "drafts" / pid / "tokens.uss"
    draft.write_text("/* old copy */\n")
    old = time.time() - 3600
    os.utime(draft, (old, old))
    assert not svc.draft_status(pid)["dirty"]
    draft.write_text("/* a real edit */\n")  # newer than the skin on disk: the user's edit
    assert svc.draft_status(pid)["dirty"]
