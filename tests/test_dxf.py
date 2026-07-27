import pytest

from geomotif import Design, Path, save_dxf, to_dxf
from geomotif.motifs import BarnsleyFern, RegularPolygon
from tests.readback import dxf_header, dxf_pairs, dxf_points, dxf_polylines, dxf_records

SQUARE = RegularPolygon(sides=4, radius=100.0)

MIXED = Design(
    paths=(
        Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=True),
        Path(((0.0, 0.0), (5.0, 5.0))),
    ),
    points=((2.0, 8.0), (3.0, 9.0)),
)


def test_every_group_code_has_a_value():
    # The whole format is pairs of lines; an odd count means a truncated one.
    assert dxf_pairs(to_dxf(MIXED))


def test_the_file_says_it_is_r12():
    # AC1009 is what makes it R12 rather than something a 1992 reader chokes on.
    assert dxf_header(to_dxf(MIXED))["$ACADVER"] == ["AC1009"]


def test_the_file_records_its_own_extents():
    bounds = SQUARE.build().bounds
    header = dxf_header(to_dxf(SQUARE.build()))
    assert [float(v) for v in header["$EXTMIN"]] == [bounds.min_x, bounds.min_y, 0.0]
    assert [float(v) for v in header["$EXTMAX"]] == [bounds.max_x, bounds.max_y, 0.0]


def test_the_sections_arrive_in_order_and_are_all_closed():
    kinds = [kind for kind, _ in dxf_records(to_dxf(MIXED))]
    assert kinds.count("SECTION") == kinds.count("ENDSEC") == 3
    assert kinds[-1] == "EOF"


def test_a_stroke_becomes_a_polyline_with_every_vertex():
    (points, closed), *_ = dxf_polylines(to_dxf(SQUARE.build()))
    assert len(points) == 4
    assert closed


def test_a_closed_polyline_carries_the_flag_rather_than_a_repeated_vertex():
    points, closed = dxf_polylines(to_dxf(SQUARE.build()))[0]
    assert closed
    assert points[0] != points[-1]


def test_an_open_stroke_is_not_flagged_closed():
    assert dxf_polylines(to_dxf(MIXED))[1][1] is False


def test_loose_points_become_point_entities():
    assert dxf_points(to_dxf(MIXED)) == [(2.0, 8.0), (3.0, 9.0)]
    assert len(dxf_points(to_dxf(BarnsleyFern(count=150).build()))) == 150


def test_y_is_not_flipped():
    # DXF is y-up, the same convention the motifs are written in. Unlike SVG,
    # nothing is mirrored on the way out.
    design = Design(paths=(Path(((0.0, 0.0), (0.0, 100.0))),))
    assert dxf_polylines(to_dxf(design))[0][0] == [(0.0, 0.0), (0.0, 100.0)]


def test_the_design_keeps_its_own_measurements():
    points, _ = dxf_polylines(to_dxf(SQUARE.build()))[0]
    assert sorted(points) == sorted(
        (round(x, 4), round(y, 4)) for x, y in SQUARE.build().paths[0].points
    )


def test_everything_sits_on_layer_zero_by_default():
    layers = {codes.get(8) for kind, codes in dxf_records(to_dxf(MIXED)) if 8 in codes}
    assert layers == {"0"}


def test_a_named_layer_is_declared_as_well_as_used():
    text = to_dxf(MIXED, layer="CUTS")
    declared = [codes.get(2) for kind, codes in dxf_records(text) if kind == "LAYER"]
    assert "CUTS" in declared
    assert {codes.get(8) for _, codes in dxf_records(text) if 8 in codes} == {"CUTS"}


@pytest.mark.parametrize(
    "layer",
    ["", "has space", "x" * 32, "curly{}", "naïve"],
)
def test_a_layer_name_r12_would_reject_is_refused(layer):
    with pytest.raises(ValueError, match="layer name"):
        to_dxf(MIXED, layer=layer)


def test_precision_rounds_the_coordinates():
    points, _ = dxf_polylines(to_dxf(SQUARE.build(), precision=1))[0]
    assert all(round(x, 1) == x and round(y, 1) == y for x, y in points)


def test_an_empty_design_is_refused():
    with pytest.raises(ValueError, match="empty design"):
        to_dxf(Design())


def test_a_negative_precision_is_refused():
    with pytest.raises(ValueError, match="precision"):
        to_dxf(MIXED, precision=-1)


def test_save_dxf_writes_the_file(tmp_path):
    out = save_dxf(SQUARE.build(), tmp_path / "square.dxf", layer="CUT", precision=2)
    assert out.read_text() == to_dxf(SQUARE.build(), layer="CUT", precision=2)
