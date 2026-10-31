import pytest
from PIL import Image

from fmskin import coded, screenmap, skinpack
from fmskin.skinpack import PackError


def test_catalog_only_lists_layouts_the_game_has():
    rows = screenmap.catalog({"Portal-Large", "TrainingOverviewGridComposition-Large"})
    assert [r["label"] for r in rows] == ["Home (Portal)", "Training Overview"]
    assert rows[1]["ownBackdrop"] and not rows[0]["ownBackdrop"]


def test_tokens_follow_classes_on_the_screen():
    by_token = {"--a": [(".panel .title", "color")], "--b": [(".table.row", "background-color")],
                "--c": [("#Only-a-name", "color")]}
    tree = {"c": ["panel"], "ch": [{"c": ["title"]}, {"c": ["table"]}]}
    hits = screenmap.tokens_for_classes(by_token, screenmap.classes_in(tree))
    assert hits == {"--a": 1}  # --b needs both classes on one element; name-only rules can't be matched


def test_coded_area_picture_hide_and_reset(skins_root, tmp_path):
    pic = tmp_path / "news.png"
    Image.new("RGB", (64, 36), (10, 10, 30)).save(pic)
    pack = skinpack.create_pack(skins_root, "Coded")
    coded.apply(pack, "news-backgrounds", "image", str(pic))
    sheet = (pack.path / "screen-coded.uss").read_text()
    assert "#DynamicBackgroundImage_Club" in sheet and 'url("assets/images/news.png")' in sheet
    coded.apply(pack, "news-backgrounds", "hide")
    assert "opacity: 0" in (pack.path / "screen-coded.uss").read_text()
    out = coded.apply(pack, "news-backgrounds", "default")
    assert "DynamicBackground" not in (pack.path / "screen-coded.uss").read_text()
    assert next(a for a in out["areas"] if a["id"] == "news-backgrounds")["state"] == {"mode": "default"}


def test_coded_areas_a_skin_cannot_change_are_refused(skins_root):
    pack = skinpack.create_pack(skins_root, "Refuse")
    with pytest.raises(PackError):
        coded.apply(pack, "name-links", "hide")
    with pytest.raises(PackError):
        coded.apply(pack, "continue", "hide")  # pictures only
