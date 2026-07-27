import pytest

from geomotif import Design, Path, save_svg, to_svg
from geomotif.motifs import BarnsleyFern, RegularPolygon, Star
from tests.readback import svg_dots, svg_find, svg_number, svg_root, svg_strokes

SQUARE = RegularPolygon(sides=4, radius=100.0)

MIXED = Design(
    paths=(
        Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=True),
        Path(((0.0, 0.0), (5.0, 5.0))),
    ),
    points=((2.0, 8.0),),
)


def test_the_document_is_well_formed_xml():
    # ElementTree does the checking; a writer that emits a broken attribute
    # would otherwise only be caught by whatever opens the file later.
    root = svg_root(to_svg(SQUARE.build()))
    assert root.get("viewBox")


def test_a_stroke_becomes_a_path_with_every_vertex():
    strokes = svg_strokes(to_svg(SQUARE.build()))
    assert len(strokes) == 1
    assert len(strokes[0][0]) == 4


def test_a_closed_path_closes_and_does_not_repeat_its_seam():
    (points, closed), *_ = svg_strokes(to_svg(SQUARE.build()))
    assert closed
    assert points[0] != points[-1]


def test_a_two_point_path_is_never_closed():
    # Its closing segment would retrace the only segment it has -- the same
    # reason Path.length refuses to count it twice.
    design = Design(paths=(Path(((0.0, 0.0), (10.0, 10.0)), closed=True),))
    assert svg_strokes(to_svg(design))[0][1] is False


def test_the_design_lands_where_the_canvas_says():
    # A square of radius 100 fitted into 200x200 with no padding: each corner
    # at the middle of an edge, and y flipped from the maths convention.
    points, _ = svg_strokes(to_svg(SQUARE.build(), width=200, height=200, padding=0))[0]
    assert sorted(points) == [(0.0, 100.0), (100.0, 0.0), (100.0, 200.0), (200.0, 100.0)]


def test_y_points_down_by_default():
    # The topmost point of the design must come out with the smallest y.
    design = Design(paths=(Path(((0.0, 0.0), (0.0, 100.0))),))
    points, _ = svg_strokes(to_svg(design, padding=0))[0]
    assert points[0][1] > points[1][1]


def test_the_flip_can_be_turned_off():
    design = Design(paths=(Path(((0.0, 0.0), (0.0, 100.0))),))
    points, _ = svg_strokes(to_svg(design, padding=0, flip_y=False))[0]
    assert points[0][1] < points[1][1]


def test_every_stroke_gets_its_own_element_by_default():
    assert len(svg_find(to_svg(MIXED), "path")) == 2
    assert len(svg_strokes(to_svg(MIXED))) == 2


def test_the_strokes_can_be_merged_into_one_element():
    text = to_svg(MIXED, group_by_path=False)
    assert len(svg_find(text, "path")) == 1
    # ...still two subpaths, so nothing has been joined that was not joined.
    assert len(svg_strokes(text)) == 2


def test_loose_points_become_circles():
    design = BarnsleyFern(count=200).build()
    assert len(svg_dots(to_svg(design))) == 200


def test_a_dot_is_as_heavy_as_a_line_unless_told_otherwise():
    circle = svg_find(to_svg(MIXED, stroke_width=3.0), "circle")[0]
    assert circle.get("r") == "3"
    assert svg_find(to_svg(MIXED, dot_radius=0.5), "circle")[0].get("r") == "0.5"


def test_dots_can_be_left_out():
    assert svg_find(to_svg(MIXED, dot_radius=0), "circle") == []


def test_there_is_no_background_unless_asked_for():
    assert svg_find(to_svg(MIXED), "rect") == []
    assert svg_find(to_svg(MIXED, background="#fff"), "rect")[0].get("fill") == "#fff"


def test_the_document_labels_itself_with_its_motif():
    assert svg_find(to_svg(Star(points=7).build()), "title")[0].text == "star"


def test_an_explicit_title_wins():
    assert svg_find(to_svg(MIXED, title="my drawing"), "title")[0].text == "my drawing"


def test_a_design_with_no_motif_gets_no_title():
    assert svg_find(to_svg(MIXED), "title") == []


def test_text_and_attributes_are_escaped():
    # Not paranoia: a title comes from metadata, and a colour from whatever
    # the caller passed. Either can carry a quote or an angle bracket.
    text = to_svg(MIXED, title='a <b> & "c"', stroke='#000" onload="x')
    assert svg_find(text, "title")[0].text == 'a <b> & "c"'
    assert svg_find(text, "g")[0].get("stroke") == '#000" onload="x'


def test_trailing_zeros_are_dropped():
    text = to_svg(SQUARE.build(), width=200, height=200, padding=0)
    assert '"100 0' in text or "M 100 0" in text
    assert "100.000" not in text


def test_precision_rounds_the_coordinates():
    points, _ = svg_strokes(to_svg(SQUARE.build(), width=201, precision=1))[0]
    assert all(round(x, 1) == x and round(y, 1) == y for x, y in points)


def test_precision_zero_writes_whole_numbers():
    text = to_svg(SQUARE.build(), width=201, precision=0)
    assert "." not in text.split("<path")[1].split("/>")[0]


def test_giving_only_a_width_keeps_the_proportions():
    root = svg_root(to_svg(Star(points=5).build(), width=400, padding=0))
    bounds = Star(points=5).build().bounds
    assert svg_number(root, "width") == 400
    assert svg_number(root, "height") == pytest.approx(400 * bounds.height / bounds.width, abs=1e-3)


def test_giving_only_a_height_keeps_the_proportions():
    root = svg_root(to_svg(Star(points=5).build(), height=400, padding=0))
    bounds = Star(points=5).build().bounds
    assert svg_number(root, "height") == 400
    assert svg_number(root, "width") == pytest.approx(400 * bounds.width / bounds.height, abs=1e-3)


def test_with_no_size_at_all_the_design_keeps_its_own():
    bounds = SQUARE.build().bounds
    root = svg_root(to_svg(SQUARE.build(), padding=10))
    assert svg_number(root, "width") == bounds.width + 20
    assert svg_number(root, "height") == bounds.height + 20


def test_a_design_flat_in_one_axis_still_gets_a_canvas():
    # A horizontal line has no height; a canvas of zero would be refused by
    # fit(), and a straight line is a perfectly reasonable thing to export.
    flat = Design(paths=(Path(((0.0, 0.0), (100.0, 0.0))),))
    root = svg_root(to_svg(flat, padding=0))
    assert svg_number(root, "height") > 0


def test_an_empty_design_is_refused():
    with pytest.raises(ValueError, match="empty design"):
        to_svg(Design())


def test_nonsense_options_are_refused():
    with pytest.raises(ValueError, match="padding"):
        to_svg(MIXED, padding=-1)
    with pytest.raises(ValueError, match="precision"):
        to_svg(MIXED, precision=-1)


def test_padding_larger_than_the_canvas_is_refused():
    with pytest.raises(ValueError, match="no room"):
        to_svg(MIXED, width=10, height=10, padding=20)


def test_save_svg_writes_the_file(tmp_path):
    out = save_svg(SQUARE.build(), tmp_path / "square.svg", width=100)
    assert out.read_text() == to_svg(SQUARE.build(), width=100)
    assert out.read_text().endswith("</svg>\n")
