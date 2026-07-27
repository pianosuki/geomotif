import math

import pytest

from geomotif import Affine, Bounds, Design, Path

SQUARE = Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)), closed=True)
DIAGONAL = Path(((0.0, 0.0), (3.0, 4.0)))


def test_path_normalizes_to_float_tuples():
    # Annotated as tuple[Point, ...] so callers are nudged toward the stored
    # form, but any sequence of numeric pairs is normalized at runtime.
    path = Path([(1, 2), (3, 4)])  # type: ignore[arg-type]
    assert path.points == ((1.0, 2.0), (3.0, 4.0))
    assert all(isinstance(x, float) for x, _ in path.points)


def test_path_rejects_non_finite_coordinates():
    with pytest.raises(ValueError):
        Path(((0.0, 0.0), (math.inf, 1.0)))
    with pytest.raises(ValueError):
        Path(((0.0, 0.0), (math.nan, 1.0)))


def test_path_rejects_malformed_points():
    with pytest.raises(TypeError):
        Path(((0.0, 0.0), (1.0, 2.0, 3.0)))  # type: ignore[arg-type]


def test_path_length_is_polyline_length():
    assert DIAGONAL.length == pytest.approx(5.0)


def test_closed_path_length_includes_the_seam():
    assert SQUARE.length == pytest.approx(40.0)


def test_two_point_closed_path_is_not_double_counted():
    # Closing a two-point path retraces the segment it already has; counting
    # that twice would report a length no plotter would ever draw.
    assert Path(((0.0, 0.0), (5.0, 0.0)), closed=True).length == pytest.approx(5.0)


def test_path_iteration_and_length():
    assert list(DIAGONAL) == [(0.0, 0.0), (3.0, 4.0)]
    assert len(DIAGONAL) == 2


def test_bounds_from_points():
    b = Bounds.from_points([(1.0, 5.0), (-2.0, 3.0), (4.0, -1.0)])
    assert (b.min_x, b.min_y, b.max_x, b.max_y) == (-2.0, -1.0, 4.0, 5.0)
    assert b.width == 6.0
    assert b.height == 6.0
    assert b.center == (1.0, 2.0)


def test_bounds_of_empty_set_rejected():
    with pytest.raises(ValueError):
        Bounds.from_points([])


def test_bounds_reject_inverted_extents():
    with pytest.raises(ValueError):
        Bounds(10.0, 0.0, 0.0, 10.0)


def test_bounds_union_and_padding():
    a = Bounds(0.0, 0.0, 1.0, 1.0)
    b = Bounds(2.0, -1.0, 3.0, 0.0)
    assert a.union(b) == Bounds(0.0, -1.0, 3.0, 1.0)
    assert a.padded(1.0) == Bounds(-1.0, -1.0, 2.0, 2.0)


def test_bounds_containment():
    b = Bounds(0.0, 0.0, 10.0, 10.0)
    assert (5.0, 5.0) in b
    assert (11.0, 5.0) not in b


def test_design_iterates_paths_then_loose_points():
    design = Design((DIAGONAL,), ((9.0, 9.0),))
    assert list(design) == [(0.0, 0.0), (3.0, 4.0), (9.0, 9.0)]
    assert len(design) == 3


def test_design_add_concatenates():
    combined = Design((DIAGONAL,)) + Design((SQUARE,), ((1.0, 1.0),))
    assert len(combined.paths) == 2
    assert combined.points == ((1.0, 1.0),)


def test_design_add_merges_meta_right_biased():
    left = Design(meta={"motif": "a", "shared": 1})
    right = Design(meta={"motif": "b"})
    assert (left + right).meta == {"motif": "b", "shared": 1}


def test_design_add_keeps_the_only_meta_present():
    left = Design((DIAGONAL,), meta={"motif": "a"})
    assert (left + Design()).meta == {"motif": "a"}


def test_design_bounds_span_everything():
    design = Design((DIAGONAL,), ((-1.0, 20.0),))
    assert design.bounds == Bounds(-1.0, 0.0, 3.0, 20.0)


def test_design_transformed_applies_to_paths_and_points():
    design = Design((DIAGONAL,), ((1.0, 1.0),))
    moved = design.transformed(Affine.translate(10.0, 0.0))
    assert moved.paths[0].points[0] == (10.0, 0.0)
    assert moved.points == ((11.0, 1.0),)


def test_design_transformed_preserves_closed_flag():
    assert Design((SQUARE,)).transformed(Affine.identity()).paths[0].closed is True


def test_design_flipped_y():
    flipped = Design((DIAGONAL,), ((1.0, 2.0),)).flipped_y()
    assert flipped.paths[0].points == ((0.0, -0.0), (3.0, -4.0))
    assert flipped.points == ((1.0, -2.0),)


def test_fit_scales_uniformly_and_centers():
    # A 10x10 square into a 100x50 canvas: limited by height, so scale 5 and
    # centered horizontally with 25 units of slack on each side.
    fitted = Design((SQUARE,)).fit(100.0, 50.0)
    b = fitted.bounds
    assert b.width == pytest.approx(50.0)
    assert b.height == pytest.approx(50.0)
    assert b.min_x == pytest.approx(25.0)
    assert b.min_y == pytest.approx(0.0)


def test_fit_respects_padding():
    fitted = Design((SQUARE,)).fit(100.0, 100.0, padding=10.0)
    b = fitted.bounds
    assert b.min_x == pytest.approx(10.0)
    assert b.max_x == pytest.approx(90.0)


def test_fit_flip_y_inverts_vertically():
    fitted = Design((DIAGONAL,)).fit(100.0, 100.0, flip_y=True)
    ys = [y for _, y in fitted]
    assert ys[0] == pytest.approx(100.0)
    assert ys[-1] == pytest.approx(0.0)


def test_fit_of_degenerate_design_translates_without_scaling():
    # A single point has no extent, so there is no finite scale that fills a
    # canvas from nothing; it should be placed, not blown up.
    fitted = Design((Path(((5.0, 5.0),)),)).fit(100.0, 100.0)
    assert fitted.paths[0].points == ((50.0, 50.0),)


def test_fit_rejects_impossible_canvases():
    design = Design((SQUARE,))
    with pytest.raises(ValueError):
        design.fit(0.0, 10.0)
    with pytest.raises(ValueError):
        design.fit(10.0, 10.0, padding=-1.0)
    with pytest.raises(ValueError):
        design.fit(10.0, 10.0, padding=6.0)


def test_path_bounds():
    assert DIAGONAL.bounds == Bounds(0.0, 0.0, 3.0, 4.0)


def test_design_add_refuses_foreign_types():
    with pytest.raises(TypeError):
        Design() + 5  # type: ignore[operator]


def test_design_defaults_are_empty():
    design = Design()
    assert len(design) == 0
    assert design.meta == {}
