import json

import pytest

from geomotif import Design, Path, load_design, save_design, save_points
from geomotif.motifs import PolarExpression, SpiralBetween, Star

POINTS = [(1.25, -2.5), (0.0, 3.14159), (100.0, 200.0)]

#: Two strokes and a loose point: the three things a design file has to keep
#: apart, and the only shape that can tell a flat export from a structured one.
MIXED = Design(
    paths=(
        Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)), closed=True),
        Path(((20.0, 20.0), (30.0, 30.0))),
    ),
    points=((99.0, 99.0),),
)


def test_csv_export(tmp_path):
    out = save_points(POINTS, tmp_path / "points.csv")
    lines = out.read_text().splitlines()
    assert lines[0] == "x,y"
    assert lines[1] == "1.25,-2.5"
    assert len(lines) == 1 + len(POINTS)


def test_txt_export_tab_separated(tmp_path):
    out = save_points(POINTS, tmp_path / "points.txt")
    lines = out.read_text().splitlines()
    assert lines[0] == "1.25\t-2.5"
    assert len(lines) == len(POINTS)


def test_tsv_suffix_maps_to_txt(tmp_path):
    out = save_points(POINTS, tmp_path / "points.tsv")
    assert "\t" in out.read_text().splitlines()[0]


def test_json_export_round_trips(tmp_path):
    out = save_points(POINTS, tmp_path / "points.json")
    data = json.loads(out.read_text())
    assert data == [[x, y] for x, y in POINTS]


def test_precision_zero_writes_integers(tmp_path):
    out = save_points(POINTS, tmp_path / "points.txt", precision=0)
    first = out.read_text().splitlines()[0]
    assert first == "1\t-2"  # banker's rounding on .25/.5 toward even


def test_precision_rounds_decimals(tmp_path):
    out = save_points(POINTS, tmp_path / "points.csv", precision=2)
    assert out.read_text().splitlines()[2] == "0.0,3.14"


def test_explicit_fmt_overrides_suffix(tmp_path):
    out = save_points(POINTS, tmp_path / "points.dat", fmt="json")
    assert json.loads(out.read_text())


def test_unknown_suffix_rejected(tmp_path):
    with pytest.raises(ValueError):
        save_points(POINTS, tmp_path / "points.xyz")


def test_export_generated_design(tmp_path):
    # A Design is itself an iterable of points, so it needs no unwrapping.
    design = SpiralBetween((200, 0), (20, 0), turns=1).generate(16)
    out = save_points(design, tmp_path / "spiral.csv", precision=1)
    assert len(out.read_text().splitlines()) == 17


def test_an_unknown_explicit_format_is_refused(tmp_path):
    # Deliberately off the Literal: the check exists for callers who are not
    # running a type checker, which is most of the ones passing a string.
    with pytest.raises(ValueError, match="unknown format"):
        save_points(POINTS, tmp_path / "points.dat", fmt="parquet")  # type: ignore[arg-type]


# --- save_design: the strokes are what a flat export loses -----------------


def test_csv_names_the_stroke_each_point_belongs_to(tmp_path):
    lines = save_design(MIXED, tmp_path / "d.csv").read_text().splitlines()
    assert lines[0] == "path,x,y"
    assert [line.split(",")[0] for line in lines[1:]] == ["0", "0", "0", "1", "1", ""]


def test_a_loose_point_belongs_to_no_stroke(tmp_path):
    # An empty path cell, not a sentinel index: a loose point is not stroke -1.
    last = save_design(MIXED, tmp_path / "d.csv").read_text().splitlines()[-1]
    assert last == ",99.0,99.0"


def test_txt_puts_a_blank_line_where_the_pen_lifts(tmp_path):
    blocks = save_design(MIXED, tmp_path / "d.txt").read_text().split("\n\n")
    assert [len(block.strip().splitlines()) for block in blocks] == [3, 2, 1]


def test_txt_of_a_single_stroke_has_no_blank_lines(tmp_path):
    one = Design(paths=(Path(((0.0, 0.0), (1.0, 1.0))),))
    assert "\n\n" not in save_design(one, tmp_path / "d.txt").read_text()


def test_json_keeps_the_strokes_and_the_closed_flag(tmp_path):
    data = json.loads(save_design(MIXED, tmp_path / "d.json").read_text())
    assert [entry["closed"] for entry in data["paths"]] == [True, False]
    assert data["points"] == [[99.0, 99.0]]


def test_precision_applies_to_strokes_and_loose_points_alike(tmp_path):
    design = Star(points=5).build() + Design(points=((1.234567, 8.7654321),))
    data = json.loads(save_design(design, tmp_path / "d.json", precision=2).read_text())
    assert data["points"] == [[1.23, 8.77]]
    assert all(round(x, 2) == x for x, _ in data["paths"][0]["points"])


def test_a_design_round_trips_through_json(tmp_path):
    back = load_design(save_design(MIXED, tmp_path / "d.json"))
    assert [(p.points, p.closed) for p in back.paths] == [(p.points, p.closed) for p in MIXED.paths]
    assert back.points == MIXED.points


def test_the_recipe_rides_along_and_comes_back(tmp_path):
    design = Star(points=7).build()
    back = load_design(save_design(design, tmp_path / "d.json"))
    assert back.meta["motif"] == "star"
    assert back.meta["points"] == 7
    # The metadata that comes back is the metadata a motif would have set, so
    # a loaded design satisfies the same contract the conformance suite checks.
    assert dict(back.meta) == dict(design.meta)


def test_the_recipe_can_be_left_out(tmp_path):
    data = json.loads(save_design(Star().build(), tmp_path / "d.json", meta=False).read_text())
    assert "meta" not in data


def test_a_design_with_no_recipe_writes_none(tmp_path):
    data = json.loads(save_design(MIXED, tmp_path / "d.json").read_text())
    assert "meta" not in data


def test_a_recipe_that_cannot_be_written_says_so(tmp_path):
    design = PolarExpression().build()
    with pytest.raises(TypeError, match="formula"):
        save_design(design, tmp_path / "d.json")
    # ...and the points still export once you stop asking for the recipe.
    assert save_design(design, tmp_path / "d.json", meta=False).exists()


def test_a_flat_array_of_pairs_loads_as_loose_points(tmp_path):
    # What save_points writes. The two shapes are an array and an object, so
    # there is nothing to guess at.
    out = save_points(POINTS, tmp_path / "flat.json")
    loaded = load_design(out)
    assert loaded.paths == ()
    assert loaded.points == tuple(POINTS)


def test_a_file_that_is_neither_shape_is_refused(tmp_path):
    target = tmp_path / "d.json"
    target.write_text('"just a string"')
    with pytest.raises(ValueError, match="not a design file"):
        load_design(target)


def test_a_stroke_without_points_is_refused(tmp_path):
    target = tmp_path / "d.json"
    target.write_text(json.dumps({"paths": [{"closed": True}], "points": []}))
    with pytest.raises(ValueError, match=r"paths\[0\]"):
        load_design(target)


def test_a_point_that_is_not_a_pair_is_refused(tmp_path):
    target = tmp_path / "d.json"
    target.write_text(json.dumps({"paths": [], "points": [[1.0, 2.0], [3.0]]}))
    with pytest.raises(ValueError, match=r"points\[1\]"):
        load_design(target)


def test_points_that_are_not_an_array_are_refused(tmp_path):
    target = tmp_path / "d.json"
    target.write_text(json.dumps({"points": {"x": 1}}))
    with pytest.raises(ValueError, match="must be an array"):
        load_design(target)


def test_save_design_infers_the_format_like_save_points(tmp_path):
    assert save_design(MIXED, tmp_path / "d.tsv").read_text().count("\t") == 6
    with pytest.raises(ValueError, match="cannot infer format"):
        save_design(MIXED, tmp_path / "d.xyz")
