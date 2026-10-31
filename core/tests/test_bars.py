import pytest
from PIL import Image

from fmskin import bars, skinpack
from fmskin.skinpack import PackError
from fmskin.validate import validate_pack


def test_club_everywhere_writes_nothing(skins_root):
    pack = skinpack.create_pack(skins_root, "Club")
    bars.apply(pack, {})
    assert pack.sheets() == ["tokens.uss"]


def test_gradient_and_solid_areas(skins_root):
    pack = skinpack.create_pack(skins_root, "Bars")
    bars.apply(pack, {"topBar": {"mode": "gradient", "colours": ["#005f46", "#00966e"]},
                      "backdrop": {"mode": "solid", "colours": ["#06121c"], "stripes": True}})
    assert pack.sheets() == ["tokens.uss", "screen-global.uss"]
    sheet = (pack.path / "screen-global.uss").read_text()
    assert '#MainNav { background-image: url("assets/images/topBar.png")' in sheet
    assert "SISafeAreaElement#Overview, #Card-frame > *" in sheet
    assert "#EntityGradient" not in sheet  # sub bar left on club colours
    top = Image.open(pack.path / "assets/images/topBar.png")
    assert top.getpixel((0, 0)) == (0, 95, 70) and top.getpixel((top.width - 1, 0)) == (0, 150, 110)
    assert [p for p in validate_pack(pack) if p.severity == "error"] == []
    assert bars.current(pack)["topBar"]["mode"] == "gradient"


def test_own_picture_and_bad_input(skins_root, tmp_path):
    pack = skinpack.create_pack(skins_root, "Pic")
    pic = tmp_path / "stadium.jpg"
    Image.new("RGB", (64, 36), (10, 20, 30)).save(pic)
    bars.apply(pack, {"backdrop": {"mode": "image", "source": str(pic)}})
    assert (pack.path / "assets/images/backdrop.jpg").is_file()
    with pytest.raises(PackError):
        bars.apply(pack, {"topBar": {"mode": "solid", "colours": ["green"]}})
