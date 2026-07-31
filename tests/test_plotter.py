import math

import pytest

from geomotif import Design, Path, Style, layer, styled, styles_of
from geomotif.core import registry
from geomotif.io.plotter import (
    PAPER,
    on_page,
    optimize,
    page_size,
    pen_up_distance,
    save_plotter_svg,
    to_plotter_svg,
    to_vpype,
)
from geomotif.motifs import TruchetTiling
from tests.readback import svg_layers, svg_root, svg_strokes

#: Four segments that make a square, handed over in a deliberately silly order
#: and with two of them running backwards -- which is what a design built cell
#: by cell actually looks like.
SCATTERED = Design(
    paths=(
        Path(((10.0, 0.0), (10.0, 10.0))),
        Path(((0.0, 10.0), (0.0, 0.0))),
        Path(((10.0, 10.0), (0.0, 10.0))),
        Path(((0.0, 0.0), (10.0, 0.0))),
    )
)


def drawn(design):
    return math.fsum(path.length for path in design.paths)


def drawn_width(text):
    xs = [x for points, _ in svg_strokes(text) for x, _ in points]
    return max(xs) - min(xs)


# --- paper ------------------------------------------------------------------


def test_a4_is_a4():
    assert page_size("a4") == (210.0, 297.0)
    assert page_size("A4 ") == (210.0, 297.0)
    assert page_size("a4", landscape=True) == (297.0, 210.0)


def test_an_unknown_paper_lists_the_ones_there_are():
    with pytest.raises(KeyError, match="a4"):
        page_size("a9")


def test_every_paper_is_taller_than_it_is_wide():
    # They are all listed portrait, and landscape is the caller's decision.
    assert all(width < height for width, height in PAPER.values())


def test_a_design_lands_inside_the_margin():
    placed = on_page(TruchetTiling().build(), paper="a4", margin=15.0)
    bounds = placed.bounds
    assert bounds.min_x >= 15.0 - 1e-9
    assert bounds.min_y >= 15.0 - 1e-9
    assert bounds.max_x <= 210.0 - 15.0 + 1e-9
    assert bounds.max_y <= 297.0 - 15.0 + 1e-9


def test_the_written_svg_lands_inside_the_margin_too():
    # Not the same assertion as the one above: on_page places the design, and
    # the writer used to fit it a second time and scale the margin straight
    # back out to the paper edge.
    for margin in (0.0, 15.0, 40.0):
        strokes = svg_strokes(to_plotter_svg(TruchetTiling().build(), paper="a4", margin=margin))
        xs = [x for points, _ in strokes for x, _ in points]
        ys = [y for points, _ in strokes for _, y in points]
        assert min(xs) >= margin - 1e-6
        assert min(ys) >= margin - 1e-6
        assert max(xs) <= 210.0 - margin + 1e-6
        assert max(ys) <= 297.0 - margin + 1e-6


def test_a_wider_margin_draws_a_smaller_picture():
    design = TruchetTiling().build()
    narrow = drawn_width(to_plotter_svg(design, paper="a4", margin=5.0))
    wide = drawn_width(to_plotter_svg(design, paper="a4", margin=40.0))
    assert wide < narrow


def test_the_page_is_y_down_like_everything_that_prints():
    up = Design(paths=(Path(((0.0, 0.0), (0.0, 100.0))),))
    placed = on_page(up, paper="a4")
    assert placed.paths[0].points[0][1] > placed.paths[0].points[1][1]


# --- the file ---------------------------------------------------------------


def test_the_svg_is_measured_in_real_millimetres():
    root = svg_root(to_plotter_svg(TruchetTiling().build(), paper="a4"))
    assert root.get("width") == "210mm"
    assert root.get("height") == "297mm"
    # The viewBox is the same numbers without the unit, so one user unit is
    # one millimetre and a 0.35 stroke is a 0.35mm pen.
    assert root.get("viewBox") == "0 0 210 297"


def test_a_plain_svg_is_still_unitless():
    from geomotif import to_svg

    assert svg_root(to_svg(TruchetTiling().build(), width=200)).get("width") == "200"


def test_a_unit_that_is_not_one_cannot_reach_the_document():
    # The one value this writer glues into an attribute rather than escaping
    # into it, so it is checked against the list instead.
    from geomotif import to_svg

    with pytest.raises(ValueError, match="units must be one of"):
        to_svg(TruchetTiling().build(), width=200, units='mm" onload="alert(1)')


def test_the_paper_can_be_turned_on_its_side():
    root = svg_root(to_plotter_svg(TruchetTiling().build(), paper="a3", landscape=True))
    assert (root.get("width"), root.get("height")) == ("420mm", "297mm")


def test_the_layers_survive_to_the_file():
    two = layer(styled(SCATTERED, layer="pen1"), styled(TruchetTiling().build(), layer="pen2"))
    assert svg_layers(to_plotter_svg(two)) == ["pen1", "pen2"]


def test_the_file_is_written(tmp_path):
    target = save_plotter_svg(TruchetTiling().build(), tmp_path / "plot.svg", paper="a5")
    assert svg_root(target.read_text()).get("width") == "148mm"


# --- optimizing -------------------------------------------------------------


def test_four_loose_segments_become_one_closed_loop():
    out = optimize(SCATTERED)
    assert len(out.paths) == 1
    assert out.paths[0].closed is True
    assert len(out.paths[0].points) == 4  # the seam is implied, never repeated


def test_optimizing_draws_exactly_the_same_ink():
    for name in ("tiling.square", "tiling.truchet", "mandala", "girih.tenfold"):
        design = registry.create(name, **registry.describe(name).example).build()
        assert drawn(optimize(design)) == pytest.approx(drawn(design), rel=1e-9)


def test_the_pen_travels_less_with_it_than_without():
    design = TruchetTiling().build()
    assert pen_up_distance(optimize(design)) < pen_up_distance(design) / 2


def test_merging_can_be_turned_off_on_its_own():
    out = optimize(SCATTERED, merge=False)
    assert len(out.paths) == len(SCATTERED.paths)
    assert pen_up_distance(out) < pen_up_distance(SCATTERED)


def test_sorting_can_be_turned_off_on_its_own():
    # Merging alone still reduces the travel, because there is less to travel
    # between -- but the strokes stay in the order they arrived.
    out = optimize(SCATTERED, sort=False)
    assert len(out.paths) == 1


def test_nothing_is_joined_that_does_not_touch():
    apart = Design(
        paths=(
            Path(((0.0, 0.0), (10.0, 0.0))),
            Path(((10.5, 0.0), (20.0, 0.0))),
        )
    )
    assert len(optimize(apart).paths) == 2
    assert len(optimize(apart, tolerance=1.0).paths) == 1


def test_a_tolerance_of_zero_demands_exactly_the_same_coordinates():
    nearly = Design(
        paths=(
            Path(((0.0, 0.0), (10.0, 0.0))),
            Path(((10.000001, 0.0), (20.0, 0.0))),
        )
    )
    assert len(optimize(nearly, tolerance=0.0).paths) == 2


def test_a_negative_tolerance_is_refused():
    with pytest.raises(ValueError):
        optimize(SCATTERED, tolerance=-1.0)


def test_strokes_on_different_layers_are_never_joined():
    # They are drawn by different pens; joining them would draw one of them in
    # the wrong colour.
    split = layer(
        styled(Design(paths=(Path(((0.0, 0.0), (10.0, 0.0))),)), layer="pen1"),
        styled(Design(paths=(Path(((10.0, 0.0), (20.0, 0.0))),)), layer="pen2"),
    )
    out = optimize(split)
    assert len(out.paths) == 2
    assert [style and style.layer for style in styles_of(out)] == ["pen1", "pen2"]


def test_strokes_of_different_colours_on_one_layer_are_not_joined_either():
    split = layer(
        styled(Design(paths=(Path(((0.0, 0.0), (10.0, 0.0))),)), stroke="red"),
        styled(Design(paths=(Path(((10.0, 0.0), (20.0, 0.0))),)), stroke="blue"),
    )
    assert len(optimize(split).paths) == 2


def test_a_merged_stroke_keeps_the_style_of_what_it_was_made_from():
    out = optimize(styled(SCATTERED, stroke="red", layer="pen1"))
    assert styles_of(out) == (Style(layer="pen1", stroke="red"),)


def test_layers_come_out_in_the_order_they_went_in():
    two = layer(styled(SCATTERED, layer="second"), styled(TruchetTiling().build(), layer="first"))
    first, *_ = styles_of(optimize(two))
    assert first == Style(layer="second")


def test_loose_points_and_metadata_are_carried_through():
    design = Design(paths=SCATTERED.paths, points=((5.0, 5.0),), meta={"motif": "test"})
    out = optimize(design)
    assert out.points == ((5.0, 5.0),)
    assert out.meta["motif"] == "test"


def test_an_already_closed_path_is_left_closed():
    square = Design(paths=(Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=True),))
    assert optimize(square).paths[0].closed is True


def test_a_design_with_nothing_in_it_optimizes_to_nothing():
    assert optimize(Design()).paths == ()


# --- measuring --------------------------------------------------------------


def test_pen_up_counts_the_trip_to_the_first_stroke():
    design = Design(paths=(Path(((3.0, 4.0), (10.0, 4.0))),))
    assert pen_up_distance(design) == pytest.approx(5.0)
    assert pen_up_distance(design, start=(3.0, 4.0)) == pytest.approx(0.0)


def test_pen_up_counts_the_hops_between_strokes():
    design = Design(
        paths=(
            Path(((0.0, 0.0), (10.0, 0.0))),
            Path(((10.0, 5.0), (0.0, 5.0))),
        )
    )
    assert pen_up_distance(design) == pytest.approx(5.0)


# --- vpype ------------------------------------------------------------------


def test_vpype_receives_the_layers_and_the_page():
    vpype = pytest.importorskip("vpype")
    two = layer(styled(SCATTERED, layer="pen1"), styled(TruchetTiling().build(), layer="pen2"))
    document = to_vpype(two, paper="a3", margin=20.0)

    per_mm = vpype.convert_length("1mm")
    assert [round(value / per_mm, 3) for value in document.page_size] == [297.0, 420.0]
    assert list(document.layers) == [1, 2]
    names = [document.layers[i].property(vpype.METADATA_FIELD_NAME) for i in (1, 2)]
    assert names == ["pen1", "pen2"]
    assert min(document.bounds()) / per_mm == pytest.approx(20.0)


def test_vpype_sees_a_closed_path_as_a_line_that_comes_back():
    pytest.importorskip("vpype")
    square = Design(paths=(Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=True),))
    document = to_vpype(square)
    line = document.layers[1][0]
    assert line[0] == line[-1]  # vpype has no closed flag, so the seam is written out


def test_this_libraries_optimizer_holds_up_against_vpypes():
    # Not a claim to beat it -- vpype's is the reference implementation. Within
    # a quarter is enough to say the greedy pass here is doing its job.
    vpype_cli = pytest.importorskip("vpype_cli")
    design = TruchetTiling().build()
    theirs = vpype_cli.execute("linemerge linesort", to_vpype(design)).pen_up_length()
    ours = to_vpype(optimize(design)).pen_up_length()
    assert ours < theirs * 1.25
    assert ours < to_vpype(design).pen_up_length() / 2


def test_the_svg_this_writes_is_the_svg_vpype_reads(tmp_path):
    # The whole point of writing layers as Inkscape's groups and sizing the
    # page in millimetres: the file goes straight into a plotter toolchain.
    vpype = pytest.importorskip("vpype")
    two = layer(styled(SCATTERED, layer="pen1"), styled(TruchetTiling().build(), layer="pen2"))
    target = save_plotter_svg(two, tmp_path / "plot.svg", paper="a4")
    assert len(svg_strokes(target.read_text())) == len(two.paths)

    document = vpype.read_multilayer_svg(str(target), quantization=0.1)
    per_mm = vpype.convert_length("1mm")
    assert [round(value / per_mm) for value in document.page_size] == [210, 297]
    assert len(document.layers) == 2
    names = [layers.property(vpype.METADATA_FIELD_NAME) for layers in document.layers.values()]
    assert sorted(names) == ["pen1", "pen2"]
