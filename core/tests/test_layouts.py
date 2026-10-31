import json

from conftest import default_for, make_layout

from fmskin import layouts, skinpack

PANELS = [
    {"id": "Calendar", "x": 0, "y": 1, "w": 16, "h": 9, "minW": 12, "minH": 8},
    {"id": "Bar", "x": 0, "y": 0, "w": 16, "h": 1, "minW": 16, "minH": 1, "maxH": 1, "locked": True},
    {"id": "A", "x": 16, "y": 0, "w": 4, "h": 2, "minW": 4, "minH": 2, "maxW": 4, "maxH": 2},
    {"id": "B", "x": 16, "y": 2, "w": 4, "h": 2, "minW": 4, "minH": 2, "maxW": 4, "maxH": 2},
]


def test_dumps_is_compact_and_order_preserving():
    data = make_layout(PANELS)
    raw = layouts.dumps(data)
    assert b" " not in raw.replace(b'"Fullscreen"', b"")
    assert list(json.loads(raw)) == list(data)


def test_swap_same_size_panels_is_allowed():
    data = make_layout(PANELS)
    new, issues = layouts.place(data, {"A": {"y": 2}, "B": {"y": 0}}, 20, default_for(data))
    assert issues == []
    assert new["m_gridComponents"][2]["m_location"]["y"] == 2
    # only m_location changed
    for a, b in zip(data["m_gridComponents"], new["m_gridComponents"]):
        assert {k: v for k, v in a.items() if k != "m_location"} == {k: v for k, v in b.items() if k != "m_location"}


def test_guard_rails():
    data = make_layout(PANELS)
    default = default_for(data)
    _, issues = layouts.place(data, {"A": {"w": 6}}, 20, default)
    assert any("outside this slot" in i.message for i in issues)
    _, issues = layouts.place(data, {"A": {"x": 18}}, 20, default)
    assert any("Outside the grid" in i.message for i in issues)
    _, issues = layouts.place(data, {"A": {"y": 2}}, 20, default)
    assert any("Overlaps" in i.message for i in issues)
    _, issues = layouts.place(data, {"Bar": {"y": 1}}, 20, default)
    assert any("locked" in i.message for i in issues)
    _, issues = layouts.place(data, {"Nope": {"x": 0}}, 20, default)
    assert issues and "isn't placed" in issues[0].message


def test_catalogue_panels_and_sizes():
    data = make_layout(PANELS)
    default = default_for(data)
    default["catalogue"] = [{"id": "A", "tags": [], "sizes": [[2, 2], [4, 2], [4, 4]]},
                            {"id": "Extra", "tags": [], "sizes": [[4, 2]]}]
    data["m_gridComponents"][3]["m_elementID"] = "Extra"  # swapped in from the catalogue, like the game allows
    assert layouts.check(data, 20, default) == []
    # FM27 saves any size within a slot's min/max (e.g. 10x10 where the panel files only list 8x8), so that's the rule
    loose = make_layout([{"id": "A", "x": 16, "y": 0, "w": 4, "h": 2, "minW": 2, "minH": 1, "maxW": 8, "maxH": 4}])
    _, issues = layouts.place(loose, {"A": {"w": 3}}, 20, default)
    assert issues == []
    assert layouts.allowed_sizes(loose, "A", default, 20) == [[w, h] for w in range(2, 9) for h in range(1, 5)]
    fixed = make_layout([{"id": "A", "x": 0, "y": 0, "w": 4, "h": 2, "minW": 4, "minH": 2, "maxW": 0, "maxH": 0}])
    assert layouts.allowed_sizes(fixed, "A", default, 20) == [[4, 2]]  # max 0 = not set: stays at its minimum


def test_apply_and_restore(tmp_path, skins_root):
    pack = skinpack.create_pack(skins_root, "L")
    player_dir = tmp_path / "CustomGridCompositions"
    player_dir.mkdir()
    mine = player_dir / "TestGridComposition-Large"
    mine.write_bytes(b'{"mine":true}')
    layouts.save_to_pack(pack, "TestGridComposition-Large", make_layout(PANELS))
    layouts.save_to_pack(pack, "OtherGridComposition-Large", make_layout(PANELS))
    backups = tmp_path / "backups"

    result = layouts.apply_pack_layouts(pack, player_dir, backups)
    assert sorted(result["applied"]) == ["OtherGridComposition-Large", "TestGridComposition-Large"]
    assert mine.read_bytes() != b'{"mine":true}'

    undo = layouts.restore(None, backups)
    assert mine.read_bytes() == b'{"mine":true}'
    assert not (player_dir / "OtherGridComposition-Large").exists()
    assert undo["removed"] == ["OtherGridComposition-Large"]
