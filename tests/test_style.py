import pytest

from geomotif import (
    Bounds,
    Design,
    Path,
    Style,
    by_layer,
    clip_to,
    layer,
    layer_names,
    load_design,
    point_styles_of,
    save_design,
    styled,
    styles_of,
    to_dxf,
    to_svg,
)
from geomotif.core.types import PATH_STYLE_KEY
from geomotif.motifs import Circle, RegularPolygon
from tests.readback import (
    dxf_entity_colors,
    dxf_entity_layers,
    dxf_layer_table,
    svg_dots,
    svg_find,
    svg_layers,
    svg_strokes,
)

TRIANGLE = Design(paths=(Path(((0.0, 0.0), (10.0, 0.0), (5.0, 8.0)), closed=True),))

MIXED = Design(
    paths=(
        Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=True),
        Path(((0.0, 0.0), (5.0, 5.0))),
    ),
    points=((2.0, 8.0), (3.0, 9.0)),
)


# --- the value type ---------------------------------------------------------


def test_an_unset_style_is_falsy():
    assert not Style()
    assert Style(layer="pen1")


def test_a_style_refuses_a_width_of_nothing():
    with pytest.raises(ValueError):
        Style(width=0.0)


def test_a_style_refuses_a_blank_layer_name():
    with pytest.raises(ValueError):
        Style(layer="   ")


def test_merging_keeps_what_the_other_style_does_not_state():
    base = Style(layer="pen1", stroke="black")
    assert base.merged(Style(stroke="red")) == Style(layer="pen1", stroke="red")
    assert base.merged(None) == base


# --- applying styles --------------------------------------------------------


def test_styling_reaches_every_stroke_and_every_loose_point():
    design = styled(MIXED, layer="pen1")
    assert styles_of(design) == (Style(layer="pen1"),) * 2
    assert point_styles_of(design) == (Style(layer="pen1"),) * 2


def test_styling_twice_adds_rather_than_replaces():
    design = styled(styled(MIXED, layer="pen1"), stroke="red")
    assert styles_of(design)[0] == Style(layer="pen1", stroke="red")


def test_styling_with_nothing_to_say_changes_nothing():
    assert styled(MIXED) is MIXED


def test_a_design_with_no_styles_reports_none_per_stroke():
    assert styles_of(MIXED) == (None, None)
    assert layer_names(MIXED) == ()


def test_the_motif_metadata_survives_being_styled():
    design = styled(Circle(radius=10.0).build(), layer="pen1")
    assert design.meta["motif"] == "circle"


def test_junk_under_the_style_key_reads_as_no_style():
    # The metadata is a plain mapping anything may write to. A writer that
    # exploded on someone else's value would be worse than one that drew.
    design = Design(paths=MIXED.paths, meta={PATH_STYLE_KEY: ("not a style", 7)})
    assert styles_of(design) == (None, None)


# --- surviving the operations -----------------------------------------------


def test_overlaying_keeps_both_designs_styles():
    red = styled(TRIANGLE, layer="pen1", stroke="red")
    blue = styled(Design(points=((1.0, 1.0),)), layer="pen2", stroke="blue")
    combined = layer(red, blue)
    assert layer_names(combined) == ("pen1", "pen2")
    assert styles_of(combined) == (Style(layer="pen1", stroke="red"),)
    assert point_styles_of(combined) == (Style(layer="pen2", stroke="blue"),)


def test_overlaying_an_unstyled_design_leaves_a_gap_rather_than_a_shift():
    styled_part = styled(TRIANGLE, stroke="red")
    combined = styled_part + TRIANGLE
    assert styles_of(combined) == (Style(stroke="red"), None)
    assert styles_of(TRIANGLE + styled_part) == (None, Style(stroke="red"))


def test_styles_survive_a_transform():
    design = styled(TRIANGLE, stroke="red").flipped_y().fit(100.0, 100.0)
    assert styles_of(design) == (Style(stroke="red"),)


def test_resampling_drops_the_style_of_a_stroke_it_drops():
    # Three strokes and a budget of two points: the shortest is allocated
    # nothing and disappears, and its color must not slide onto a survivor.
    def stroke(length: float, color: str) -> Design:
        return styled(Design(paths=(Path(((0.0, 0.0), (length, 0.0))),)), stroke=color)

    design = layer(stroke(100.0, "red"), stroke(50.0, "green"), stroke(0.1, "blue"))
    resampled = design.resampled(2)
    assert len(resampled.paths) == 2
    assert styles_of(resampled) == (Style(stroke="red"), Style(stroke="green"))


def test_clipping_carries_a_stroke_style_onto_every_fragment_it_becomes():
    # A line crossing the box twice comes back as two strokes, both the
    # color of the one they were cut from.
    crossing = Design(paths=(Path(((-10.0, 0.0), (-1.0, 0.0), (-1.0, 10.0), (10.0, 10.0))),))
    design = styled(crossing, stroke="red")
    clipped = clip_to(design, Bounds(-5.0, -5.0, 5.0, 5.0))
    assert len(clipped.paths) >= 1
    assert set(styles_of(clipped)) == {Style(stroke="red")}


def test_clipping_drops_the_styles_of_the_points_it_drops():
    design = Design(points=((0.0, 0.0), (100.0, 100.0)))
    design = styled(design, stroke="red")
    clipped = clip_to(design, Bounds(-1.0, -1.0, 1.0, 1.0))
    assert clipped.points == ((0.0, 0.0),)
    assert point_styles_of(clipped) == (Style(stroke="red"),)


# --- splitting by layer -----------------------------------------------------


def test_layers_come_back_in_the_order_they_were_drawn():
    combined = layer(
        styled(TRIANGLE, layer="second"),
        styled(TRIANGLE, layer="first"),
    )
    assert layer_names(combined) == ("second", "first")


def test_splitting_by_layer_keeps_each_layers_own_geometry():
    outline = styled(TRIANGLE, layer="pen1")
    dots = styled(Design(points=((1.0, 1.0), (2.0, 2.0))), layer="pen2")
    split = by_layer(layer(outline, dots))
    assert list(split) == ["pen1", "pen2"]
    assert len(split["pen1"].paths) == 1
    assert split["pen1"].points == ()
    assert split["pen2"].points == ((1.0, 1.0), (2.0, 2.0))
    assert point_styles_of(split["pen2"]) == (Style(layer="pen2"),) * 2


def test_unlayered_geometry_splits_under_the_key_none():
    split = by_layer(styled(TRIANGLE, stroke="red"))
    assert list(split) == [None]


# --- what the writers do with them ------------------------------------------


def test_svg_writes_a_layer_as_the_group_inkscape_reads():
    combined = layer(styled(TRIANGLE, layer="pen1"), styled(TRIANGLE, layer="pen2"))
    assert svg_layers(to_svg(combined)) == ["pen1", "pen2"]


def test_svg_leaves_an_unstyled_design_exactly_as_it_was():
    # The gallery, the README's images and the snapshot tests all depend on
    # this: adding styles to the library must not restyle anything.
    plain = RegularPolygon(sides=5, radius=100.0).build()
    assert "inkscape" not in to_svg(plain)
    assert to_svg(plain) == to_svg(styled(plain))


def test_svg_writes_a_stroke_color_only_where_it_differs():
    text = to_svg(layer(styled(TRIANGLE, stroke="crimson"), TRIANGLE))
    colored, plain = svg_find(text, "path")
    assert colored.get("stroke") == "crimson"
    assert plain.get("stroke") is None


def test_svg_gives_a_styled_dot_its_own_color_and_radius():
    design = styled(Design(points=((0.0, 0.0), (10.0, 10.0))), stroke="crimson", width=3.0)
    circle = svg_find(to_svg(design), "circle")[0]
    assert circle.get("fill") == "crimson"
    assert circle.get("r") == "3"


def test_svg_still_merges_the_strokes_that_share_a_style():
    text = to_svg(styled(MIXED, stroke="red"), group_by_path=False)
    assert len(svg_find(text, "path")) == 1
    assert len(svg_strokes(text)) == 2


def test_svg_stops_merging_where_the_styling_changes():
    text = to_svg(layer(styled(TRIANGLE, stroke="red"), TRIANGLE), group_by_path=False)
    assert len(svg_find(text, "path")) == 2


def test_svg_keeps_the_dots_of_a_layer_with_its_strokes():
    design = styled(MIXED, layer="pen1")
    assert svg_layers(to_svg(design)) == ["pen1"]
    assert len(svg_dots(to_svg(design))) == 2


def test_dxf_declares_every_layer_it_uses():
    combined = layer(styled(TRIANGLE, layer="PEN1"), styled(TRIANGLE, layer="PEN2"))
    text = to_dxf(combined)
    assert dxf_layer_table(text) == ["0", "PEN1", "PEN2"]
    assert dxf_entity_layers(text) == [("POLYLINE", "PEN1"), ("POLYLINE", "PEN2")]


def test_dxf_leaves_unstyled_geometry_on_the_layer_it_was_given():
    text = to_dxf(MIXED, layer="INK")
    assert dxf_layer_table(text) == ["INK"]
    assert {name for _, name in dxf_entity_layers(text)} == {"INK"}


def test_dxf_writes_the_colors_it_can_name_and_leaves_the_rest():
    text = to_dxf(layer(styled(TRIANGLE, stroke="red"), styled(TRIANGLE, stroke="#ff8800")))
    assert dxf_entity_colors(text) == [1, None]


def test_dxf_refuses_a_layer_name_it_could_not_write():
    with pytest.raises(ValueError, match="not a DXF R12 layer name"):
        to_dxf(styled(TRIANGLE, layer="pen one"))


def test_styles_survive_a_design_file(tmp_path):
    design = styled(Circle(radius=10.0).build(), layer="pen1", stroke="red", width=0.5)
    reloaded = load_design(save_design(design, tmp_path / "design.json"))
    assert styles_of(reloaded) == (Style(layer="pen1", stroke="red", width=0.5),)


# --- select_styles ----------------------------------------------------------
#
# The function a third-party operator has to call, tested on its own rather
# than only through the operators here that already call it.


def test_select_styles_reorders_the_list_to_match_reordered_strokes():
    from geomotif.core.types import select_styles

    design = layer(styled(TRIANGLE, stroke="red"), styled(TRIANGLE, stroke="blue"))
    reversed_meta = select_styles(design.meta, paths=[1, 0])
    assert reversed_meta[PATH_STYLE_KEY] == (Style(stroke="blue"), Style(stroke="red"))


def test_select_styles_repeats_a_style_for_a_stroke_that_was_split():
    from geomotif.core.types import select_styles

    design = styled(TRIANGLE, stroke="red")
    assert select_styles(design.meta, paths=[0, 0, 0])[PATH_STYLE_KEY] == (Style(stroke="red"),) * 3


def test_select_styles_gives_an_index_it_has_no_style_for_no_style():
    from geomotif.core.types import select_styles

    design = styled(TRIANGLE, stroke="red")
    assert select_styles(design.meta, paths=[0, 7])[PATH_STYLE_KEY] == (Style(stroke="red"), None)


def test_select_styles_leaves_the_half_it_was_not_told_about_alone():
    from geomotif.core.types import POINT_STYLE_KEY, select_styles

    design = styled(Design(points=((0.0, 0.0), (1.0, 1.0))), stroke="red")
    kept = select_styles(design.meta, paths=[])
    assert kept[POINT_STYLE_KEY] == (Style(stroke="red"),) * 2


def test_select_styles_hands_back_styleless_metadata_untouched():
    from geomotif.core.types import select_styles

    meta = {"motif": "circle"}
    assert select_styles(meta, paths=[3, 1]) is meta
