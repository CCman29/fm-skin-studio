"""Integration checks against a real FM27 install. Skipped where the game isn't installed."""

import pytest

from fmskin import index, layouts, paths

pytestmark = pytest.mark.game
GAME = paths.detect()
needs_game = pytest.mark.skipif(not GAME.bundles or not GAME.bundles.is_dir(), reason="FM27 not installed")


@pytest.fixture(scope="module")
def game_index():
    idx = index.open_index(GAME)
    if idx is None:
        idx = index.build_index(GAME)
    return idx


@needs_game
def test_index_contents(game_index):
    m = game_index.manifest()
    assert m["tokens"] > 1500 and m["compositions"] > 1500 and m["screens"] > 1000
    tokens = game_index.tokens()
    assert tokens["--layout-modules-block-surface"]["group"] == "Panels & surfaces"
    assert tokens["--global-text-primary"]["kind"] == "color"
    assert any(c["inMatch"] for c in game_index.compositions())


@needs_game
def test_player_layouts_round_trip_byte_for_byte(game_index):
    """Every layout the game wrote must survive load -> dumps unchanged, and pass the guard-rails."""
    if not GAME.layouts_dir or not GAME.layouts_dir.is_dir():
        pytest.skip("player has no custom layouts")
    by_name = {c["name"]: c for c in game_index.compositions()}
    for name in layouts.player_layouts(GAME.layouts_dir):
        raw = (GAME.layouts_dir / name).read_bytes()
        assert layouts.dumps(layouts.load(GAME.layouts_dir / name)) == raw, name
        default = by_name.get(name)
        assert default, f"{name} has no default composition in the index"
        assert layouts.check(layouts.load(GAME.layouts_dir / name), default["columns"], default) == []
