import math

import pytest

from geomotif import (
    Affine,
    Bounds,
    Design,
    Path,
    clip_to,
    fit_to,
    jitter,
    layer,
    mirror_axis,
    offset_path,
    radial_repeat,
    symmetry_group,
    tile,
)

UNIT = Design((Path(((1.0, 0.0), (2.0, 0.0))),))
SQUARE = Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)), closed=True)


def approx_point(p):
    return pytest.approx(p, abs=1e-9)


def test_identity_leaves_points_alone():
    assert Affine.identity()((3.0, 4.0)) == (3.0, 4.0)
    assert Affine()((3.0, 4.0)) == (3.0, 4.0)


def test_translate():
    assert Affine.translate(5.0, -2.0)((1.0, 1.0)) == (6.0, -1.0)


def test_rotate_is_counter_clockwise_in_y_up():
    assert Affine.rotate(math.pi / 2)((1.0, 0.0)) == approx_point((0.0, 1.0))


def test_rotate_about_a_point():
    turned = Affine.rotate(math.pi, about=(5.0, 0.0))((6.0, 0.0))
    assert turned == approx_point((4.0, 0.0))


def test_scale_defaults_to_uniform():
    assert Affine.scale(2.0)((3.0, 4.0)) == (6.0, 8.0)
    assert Affine.scale(2.0, 3.0)((3.0, 4.0)) == (6.0, 12.0)


def test_scale_about_a_point_holds_it_fixed():
    m = Affine.scale(3.0, about=(10.0, 10.0))
    assert m((10.0, 10.0)) == approx_point((10.0, 10.0))
    assert m((11.0, 10.0)) == approx_point((13.0, 10.0))


def test_mirror_across_the_x_axis():
    assert Affine.mirror(0.0)((3.0, 4.0)) == approx_point((3.0, -4.0))


def test_mirror_across_the_y_axis():
    assert Affine.mirror(math.pi / 2)((3.0, 4.0)) == approx_point((-3.0, 4.0))


def test_mirror_through_a_point():
    assert Affine.mirror(0.0, through=(0.0, 5.0))((0.0, 7.0)) == approx_point((0.0, 3.0))


def test_shear():
    assert Affine.shear(2.0)((1.0, 3.0)) == (7.0, 3.0)
    assert Affine.shear(0.0, 2.0)((3.0, 1.0)) == (3.0, 7.0)


def test_composition_applies_right_hand_side_first():
    move = Affine.translate(10.0, 0.0)
    grow = Affine.scale(2.0)
    # grow @ move: translate, then scale -> (1+10)*2
    assert (grow @ move)((1.0, 0.0)) == approx_point((22.0, 0.0))
    # move @ grow: scale, then translate -> 1*2+10
    assert (move @ grow)((1.0, 0.0)) == approx_point((12.0, 0.0))


def test_composition_is_associative():
    a = Affine.rotate(0.7)
    b = Affine.scale(2.0, 3.0)
    c = Affine.translate(4.0, -1.0)
    left = ((a @ b) @ c)((5.0, 6.0))
    right = (a @ (b @ c))((5.0, 6.0))
    assert left == approx_point(right)


def test_inverse_undoes_the_transform():
    m = Affine.rotate(0.9, about=(2.0, 3.0)) @ Affine.scale(2.0, 0.5)
    point = (7.0, -4.0)
    assert m.inverse()(m(point)) == approx_point(point)


def test_singular_transform_cannot_be_inverted():
    with pytest.raises(ValueError):
        Affine.scale(0.0).inverse()


def test_determinant_reflects_area_scaling():
    assert Affine.scale(2.0, 3.0).determinant == pytest.approx(6.0)
    assert Affine.mirror(0.0).determinant == pytest.approx(-1.0)


def test_compose_refuses_foreign_types():
    with pytest.raises(TypeError):
        Affine.identity() @ 5  # type: ignore[operator]


def test_clip_rejects_segments_parallel_to_and_outside_an_edge():
    # Horizontal, and entirely above the box: no edge crossing to compute.
    path = Path(((-5.0, 50.0), (15.0, 50.0)))
    assert clip_to(Design((path,)), Bounds(0.0, 0.0, 10.0, 10.0)).paths == ()


def test_offset_tolerates_duplicate_vertices():
    # A repeated vertex has no direction of its own; it must inherit one
    # rather than punching a hole in the offset.
    path = Path(((0.0, 0.0), (5.0, 0.0), (5.0, 0.0), (10.0, 0.0)))
    offset = offset_path(path, 1.0)
    assert all(y == pytest.approx(1.0) for _, y in offset.points)


def test_offset_bevels_a_hairpin():
    # A 180-degree reversal would send a miter to infinity; the fallback must
    # keep the result finite.
    path = Path(((0.0, 0.0), (10.0, 0.0), (0.0, 0.0)))
    offset = offset_path(path, 1.0)
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in offset.points)


def test_layer_overlays_designs():
    combined = layer(UNIT, UNIT, UNIT)
    assert len(combined.paths) == 3


def test_layer_of_nothing_is_empty():
    assert len(layer()) == 0


def test_radial_repeat_makes_n_copies():
    rosette = radial_repeat(UNIT, 6)
    assert len(rosette.paths) == 6
    # The second copy sits one sixth of a turn round from the first.
    first = rosette.paths[0].points[0]
    second = rosette.paths[1].points[0]
    assert math.atan2(*reversed(second)) == pytest.approx(math.tau / 6)
    assert math.dist(first, (0.0, 0.0)) == pytest.approx(math.dist(second, (0.0, 0.0)))


def test_radial_repeat_with_mirror_doubles_the_copies():
    assert len(radial_repeat(UNIT, 6, mirror=True).paths) == 12


def test_radial_repeat_rejects_zero():
    with pytest.raises(ValueError):
        radial_repeat(UNIT, 0)


def test_symmetry_group_cyclic_and_dihedral():
    assert len(symmetry_group(UNIT, "C5").paths) == 5
    assert len(symmetry_group(UNIT, "D5").paths) == 10
    assert len(symmetry_group(UNIT, "c5").paths) == 5


def test_symmetry_group_rejects_nonsense():
    with pytest.raises(ValueError):
        symmetry_group(UNIT, "Z5")
    with pytest.raises(ValueError):
        symmetry_group(UNIT, "C")


def test_mirror_axis_doubles_the_design():
    mirrored = mirror_axis(UNIT, 0.0)
    assert len(mirrored.paths) == 2


def test_tile_fills_a_lattice():
    tiled = tile(UNIT, 3, 4, dx=10.0, dy=20.0)
    assert len(tiled.paths) == 12
    assert tiled.bounds.max_x == pytest.approx(2.0 + 20.0)
    assert tiled.bounds.max_y == pytest.approx(60.0)


def test_tile_stagger_offsets_odd_rows():
    tiled = tile(UNIT, 1, 2, dx=10.0, dy=10.0, stagger=0.5)
    assert tiled.paths[1].points[0][0] == pytest.approx(1.0 + 5.0)


def test_tile_rejects_empty_lattices():
    with pytest.raises(ValueError):
        tile(UNIT, 0, 3, dx=1.0, dy=1.0)


def test_jitter_is_reproducible_from_a_seed():
    a = jitter(UNIT, 1.0, seed=7)
    b = jitter(UNIT, 1.0, seed=7)
    c = jitter(UNIT, 1.0, seed=8)
    assert a.paths[0].points == b.paths[0].points
    assert a.paths[0].points != c.paths[0].points


def test_jitter_stays_within_the_amount():
    jittered = jitter(UNIT, 0.25, seed=1)
    for before, after in zip(UNIT.paths[0].points, jittered.paths[0].points, strict=True):
        assert abs(after[0] - before[0]) <= 0.25
        assert abs(after[1] - before[1]) <= 0.25


def test_jitter_does_not_touch_the_global_rng():
    import random

    random.seed(1234)
    expected = random.random()
    random.seed(1234)
    jitter(UNIT, 1.0, seed=99)
    assert random.random() == expected


def test_jitter_rejects_negative_amounts():
    with pytest.raises(ValueError):
        jitter(UNIT, -1.0)


def test_fit_to_matches_the_method():
    design = Design((SQUARE,))
    assert fit_to(design, 50.0, 50.0).bounds == design.fit(50.0, 50.0).bounds


def test_clip_keeps_the_inside_and_trims_the_rest():
    path = Path(((-5.0, 5.0), (15.0, 5.0)))
    clipped = clip_to(Design((path,)), Bounds(0.0, 0.0, 10.0, 10.0))
    assert len(clipped.paths) == 1
    assert clipped.paths[0].points[0] == approx_point((0.0, 5.0))
    assert clipped.paths[0].points[-1] == approx_point((10.0, 5.0))


def test_clip_drops_paths_that_miss_entirely():
    path = Path(((100.0, 100.0), (200.0, 200.0)))
    assert clip_to(Design((path,)), Bounds(0.0, 0.0, 10.0, 10.0)).paths == ()


def test_clip_splits_a_path_that_leaves_and_returns():
    # Out of the box in the middle, so the result must be two strokes rather
    # than one with a shortcut drawn across the gap.
    path = Path(((1.0, 1.0), (1.0, 50.0), (9.0, 50.0), (9.0, 1.0)))
    clipped = clip_to(Design((path,)), Bounds(0.0, 0.0, 10.0, 10.0))
    assert len(clipped.paths) == 2


def test_clip_opens_closed_paths():
    clipped = clip_to(Design((SQUARE,)), Bounds(-1.0, -1.0, 5.0, 11.0))
    assert all(not p.closed for p in clipped.paths)


def test_clip_filters_loose_points():
    design = Design(points=((1.0, 1.0), (50.0, 50.0)))
    assert clip_to(design, Bounds(0.0, 0.0, 10.0, 10.0)).points == ((1.0, 1.0),)


def test_offset_of_a_straight_line_is_parallel():
    line = Path(((0.0, 0.0), (10.0, 0.0)))
    offset = offset_path(line, 2.0)
    assert offset.points == (approx_point((0.0, 2.0)), approx_point((10.0, 2.0)))


def test_negative_offset_goes_the_other_way():
    line = Path(((0.0, 0.0), (10.0, 0.0)))
    assert offset_path(line, -2.0).points[0] == approx_point((0.0, -2.0))


def test_offset_miters_a_right_angle():
    # Two unit-length segments meeting at 90 degrees: the outer corner sits
    # sqrt(2) away along the bisector, not 1.
    corner = Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0)))
    offset = offset_path(corner, 1.0)
    assert offset.points[1] == approx_point((9.0, 1.0))


def test_offset_preserves_closure_and_point_count():
    offset = offset_path(SQUARE, 1.0)
    assert offset.closed is True
    assert len(offset.points) == len(SQUARE.points)


def test_offset_of_a_degenerate_path_is_unchanged():
    single = Path(((1.0, 1.0),))
    assert offset_path(single, 5.0) == single
