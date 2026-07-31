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
    snap,
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


# --- snap ------------------------------------------------------------------


def test_snap_defaults_to_whole_units():
    design = Design(points=((0.4, 0.6), (-1.2, 2.7)))
    assert list(snap(design)) == [(0.0, 1.0), (-1.0, 3.0)]


def test_snap_takes_a_grid_no_number_of_decimals_can_express():
    design = Design(points=((103.2, 103.4), (0.24, 0.26)))
    assert list(snap(design, 0.5)) == [(103.0, 103.5), (0.0, 0.5)]
    assert list(snap(design, 5.0)) == [(105.0, 105.0), (0.0, 0.0)]


def test_snap_does_not_leave_binary_floating_point_noise():
    # 3 * 0.1 is 0.30000000000000004 if you reach it by multiplying, which is
    # the wrong answer to give someone who asked for tidy numbers.
    snapped = snap(Design(points=((0.31, 0.29),)), 0.1)
    assert list(snapped) == [(0.3, 0.3)]
    assert repr(snapped.points[0][0]) == "0.3"


def test_snap_keeps_a_design_on_its_grid():
    design = Design((Path(((1.3, 4.8), (9.6, 0.2))),))
    for x, y in snap(design, 0.25):
        assert x % 0.25 == pytest.approx(0.0, abs=1e-9)
        assert y % 0.25 == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("half-even", [(2.0, -2.0), (2.0, -2.0)]),
        ("half-up", [(3.0, -3.0), (2.0, -2.0)]),
        ("floor", [(2.0, -3.0), (1.0, -2.0)]),
        ("ceil", [(3.0, -2.0), (2.0, -1.0)]),
        ("trunc", [(2.0, -2.0), (1.0, -1.0)]),
    ],
)
def test_snap_modes_resolve_a_halfway_point_their_own_way(mode, expected):
    halves = Design(points=((2.5, -2.5), (1.5, -1.5)))
    assert list(snap(halves, mode=mode, drop_duplicates=False)) == expected


def test_half_up_goes_away_from_zero_so_a_mirror_image_stays_one():
    design = Design(points=((2.5, 0.5),))
    mirrored = Design(points=((-2.5, -0.5),))
    snapped = snap(design, mode="half-up")
    assert list(snapped) == [(3.0, 1.0)]
    assert list(snap(mirrored, mode="half-up")) == [(-3.0, -1.0)]


def test_snap_rejects_a_step_that_is_not_a_grid():
    for step in (0.0, -1.0, math.inf, math.nan):
        with pytest.raises(ValueError):
            snap(UNIT, step)


def test_snap_rejects_an_unknown_mode():
    with pytest.raises(ValueError, match="half-even"):
        snap(UNIT, mode="nearest")  # type: ignore[arg-type]


def test_snap_drops_the_points_a_coarse_grid_stacked_up():
    path = Path(((0.0, 0.0), (0.1, 0.1), (0.2, 0.2), (5.0, 5.0)))
    assert snap(Design((path,))).paths[0].points == ((0.0, 0.0), (5.0, 5.0))


def test_keeping_duplicates_preserves_the_point_count_exactly():
    path = Path(((0.0, 0.0), (0.1, 0.1), (0.2, 0.2), (5.0, 5.0)))
    snapped = snap(Design((path,)), drop_duplicates=False)
    assert len(snapped.paths[0].points) == 4
    assert snapped.paths[0].points[:3] == ((0.0, 0.0),) * 3


def test_snap_drops_a_seam_that_has_closed_itself():
    # The closing segment is implied, so a final point that has landed on the
    # first would have the pen draw it twice.
    square = Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.4, 0.4)), closed=True)
    snapped = snap(Design((square,)))
    assert snapped.paths[0].points == ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    assert snapped.paths[0].closed is True


def test_snap_drops_a_stroke_with_nothing_left_to_draw():
    collapsing = Path(((0.1, 0.1), (0.2, 0.2)))
    design = Design((collapsing, Path(((0.0, 0.0), (5.0, 5.0)))))
    assert len(snap(design).paths) == 1
    assert len(snap(design, drop_duplicates=False).paths) == 2


def test_snap_carries_the_style_of_a_stroke_that_survived():
    from geomotif import Style, styled, styles_of

    doomed = styled(Design((Path(((0.1, 0.1), (0.2, 0.2))),)), stroke="#a00")
    kept = styled(Design((Path(((0.0, 0.0), (5.0, 5.0))),)), stroke="#00a")
    # The collapsed stroke takes its colour with it rather than leaving the
    # list one long and shifting every colour after it onto the wrong stroke.
    assert styles_of(snap(layer(doomed, kept))) == (Style(stroke="#00a"),)


def test_snap_carries_loose_point_styles_across_too():
    from geomotif import Style, point_styles_of, styled

    stacked = styled(Design(points=((0.1, 0.1), (0.2, 0.2))), stroke="#a00")
    apart = styled(Design(points=((5.0, 5.0),)), stroke="#00a")
    snapped = snap(stacked + apart)
    assert point_styles_of(snapped) == (Style(stroke="#a00"), Style(stroke="#00a"))


def test_snap_leaves_a_design_that_is_already_on_the_grid_alone():
    design = Design((SQUARE,))
    assert snap(design).paths[0].points == SQUARE.points


def test_snapped_matches_the_function():
    design = Design((Path(((1.3, 4.8), (9.6, 0.2))),))
    assert design.snapped(0.5).paths[0].points == snap(design, 0.5).paths[0].points


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
