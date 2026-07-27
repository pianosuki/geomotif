import itertools
import math

import pytest

from geomotif.motifs.illusions import (
    CafeWall,
    ImpossibleCube,
    MoirePattern,
    NeckerCube,
    PenroseStairs,
    PenroseTriangle,
    _crossings_of,
    _inside,
    _isometric,
    _outside,
)

ROOT3 = math.sqrt(3.0)


def perimeter(points):
    return math.fsum(
        math.dist(points[i], points[(i + 1) % len(points)]) for i in range(len(points))
    )


def drawn(design):
    return math.fsum(path.length for path in design.paths)


# --- the projection everything leans on -------------------------------------


@pytest.mark.parametrize("t", [0.5, 1.0, 7.25])
def test_a_step_of_t_along_all_three_axes_lands_nowhere(t):
    # The one fact that makes an impossible figure possible: a walk that fails
    # to close in space by (t, t, t) closes exactly on the page.
    assert _isometric((t, t, t)) == pytest.approx((0.0, 0.0))


def test_going_up_looks_the_same_as_going_away_along_both_axes():
    assert _isometric((0.0, 0.0, 1.0)) == pytest.approx(_isometric((-1.0, -1.0, 0.0)))


def test_the_two_horizontal_axes_lean_opposite_ways():
    east = _isometric((1.0, 0.0, 0.0))
    north = _isometric((0.0, 1.0, 0.0))
    assert east == pytest.approx((ROOT3 / 2.0, -0.5))
    assert north == pytest.approx((-ROOT3 / 2.0, -0.5))


# --- hiding one thing behind another ----------------------------------------


def test_a_line_crossing_a_square_comes_back_in_two_pieces():
    square = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
    across = ((-3.0, 0.0), (3.0, 0.0), (3.0, 0.2), (-3.0, 0.2))
    pieces = _outside(across, square)
    assert len(pieces) == 2
    for piece in pieces:
        # Checked at the middle of each piece rather than at its ends: a cut
        # lands exactly on the blocker's edge, which counts as inside.
        for a, b in itertools.pairwise(piece):
            assert not _inside(square, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))


def test_a_line_through_a_corner_is_not_cut_into_slivers():
    # Two of the blocker's edges are met at the same instant, which must not
    # leave a zero-length piece behind.
    square = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
    through = ((-3.0, -3.0), (3.0, 3.0), (3.0, -3.0))
    for piece in _outside(through, square):
        for a, b in itertools.pairwise(piece):
            assert math.dist(a, b) > 1e-9


def test_something_wholly_outside_comes_back_whole():
    square = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
    away = ((5.0, 5.0), (6.0, 5.0), (6.0, 6.0), (5.0, 6.0))
    (piece,) = _outside(away, square)
    assert math.fsum(math.dist(piece[i], piece[i + 1]) for i in range(len(piece) - 1)) == (
        pytest.approx(4.0)
    )


# --- the tribar -------------------------------------------------------------


def test_the_tribar_is_three_beams_of_six_corners():
    beams = PenroseTriangle().beams()
    assert len(beams) == 3
    assert all(len(beam) == 6 for beam in beams)


def test_the_three_beams_are_one_beam_turned():
    beams = PenroseTriangle(thickness=0.2).beams()
    for k in (1, 2):
        turn = k * math.tau / 3.0
        cos, sin = math.cos(turn), math.sin(turn)
        for (x, y), (u, v) in zip(beams[0], beams[k], strict=True):
            assert (u, v) == pytest.approx((x * cos - y * sin, x * sin + y * cos))


def test_each_beam_ends_where_the_next_one_starts():
    # What makes the three joints ordinary right angles: turning a beam by a
    # third of a revolution has to move it exactly one beam-length along.
    beams = PenroseTriangle(thickness=0.2).beams()
    for k in range(3):
        far = beams[k][3]  # the far tip of the beam
        near = beams[(k + 1) % 3][0]  # the near tip of the next one
        assert math.dist(far, near) < 0.7


def test_something_is_always_hidden():
    motif = PenroseTriangle(size=200.0)
    whole = math.fsum(perimeter(beam) for beam in motif.beams())
    reach = max(abs(x) for beam in motif.beams() for x, _ in beam)
    assert drawn(motif.build()) < whole * 200.0 / (2.0 * reach)


def test_the_tribar_is_the_width_it_says():
    assert PenroseTriangle(size=180.0).build().bounds.width == pytest.approx(180.0)


def test_all_three_beams_get_the_same_treatment():
    # Each beam hides the same amount of the next one, so the three come out
    # the same length: nothing about the figure singles one of them out.
    motif = PenroseTriangle(size=120.0, thickness=0.22)
    beams = motif.beams()
    hidden = [
        perimeter(beam)
        - math.fsum(
            math.dist(piece[i], piece[i + 1])
            for piece in _outside(beam, beams[(k + 1) % 3])
            for i in range(len(piece) - 1)
        )
        for k, beam in enumerate(beams)
    ]
    assert hidden == pytest.approx([hidden[0]] * 3)
    assert hidden[0] > 0.0


# --- the staircase ----------------------------------------------------------


def miss(motif):
    """Return how far the walk fails to come back to where it started."""
    corners = motif.walk()
    start, end = corners[0], corners[-1]
    return (end[0] - start[0], end[1] - start[1], end[2] - start[2])


def test_the_walk_fails_to_close_by_the_same_amount_on_all_three_axes():
    # The heart of the figure. Four flights of rising steps cannot come back
    # to where they started, and this is exactly by how much they miss.
    error = miss(PenroseStairs(steps=5, rise=0.4))
    assert error[0] == pytest.approx(error[1]) == pytest.approx(error[2])
    assert error[0] > 0.0


def test_and_that_amount_is_invisible_on_the_page():
    assert _isometric(miss(PenroseStairs(steps=7, rise=0.25))) == pytest.approx(
        (0.0, 0.0), abs=1e-9
    )


@pytest.mark.parametrize(("steps", "rise"), [(3, 0.2), (5, 0.4), (9, 0.15)])
def test_every_single_step_goes_up(steps, rise):
    corners = PenroseStairs(steps=steps, rise=rise).walk()
    for i in range(0, len(corners), 3):
        foot, top, tread = corners[i : i + 3]
        assert top[2] - foot[2] == pytest.approx(rise)
        assert tread[2] == pytest.approx(top[2])


def test_the_long_flights_are_longer_by_four_rises():
    # Which is not a fudge: it is what makes the closing error come out equal
    # on all three axes rather than only on the vertical one.
    corners = PenroseStairs(steps=4, rise=0.3).walk()
    treads = [math.dist(corners[i + 1][:2], corners[i + 2][:2]) for i in range(0, len(corners), 3)]
    assert sorted({round(t, 9) for t in treads}) == pytest.approx([1.0, 1.0 + 4.0 * 0.3])


def test_the_staircase_closes_up_on_the_page():
    design = PenroseStairs(steps=5).build()
    band = design.paths[0]
    assert band.closed
    assert math.dist(band.points[0], band.points[-1]) < design.bounds.width


def test_the_staircase_is_the_width_it_says():
    assert PenroseStairs(size=300.0).build().bounds.width == pytest.approx(300.0)


def test_more_steps_means_more_strokes():
    assert len(PenroseStairs(steps=7).build().paths) > len(PenroseStairs(steps=3).build().paths)


# --- the cubes --------------------------------------------------------------


def test_a_necker_cube_is_twelve_whole_edges():
    design = NeckerCube().build()
    assert len(design.paths) == 12
    assert all(len(path.points) == 2 for path in design.paths)


def test_the_far_face_is_the_near_face_moved():
    edges = NeckerCube(size=100.0, depth=0.5, angle=math.pi / 3.0).edges()
    offsets = {
        (round(b[0] - a[0], 9), round(b[1] - a[1], 9))
        for a, b in edges[8:]  # the four joins
    }
    assert len(offsets) == 1


def test_the_two_faces_cross_each_other_exactly_twice():
    # Two crossings is what the impossible cube is made of: one break each
    # way, and the drawing contradicts itself.
    assert len(_crossings_of(NeckerCube().edges())) == 2


def test_the_impossible_cube_breaks_one_edge_of_each_face():
    motif = ImpossibleCube(size=200.0)
    edges = motif.edges()
    design = motif.build()
    short = set()
    for index, (start, end) in enumerate(edges):
        along = math.fsum(
            path.length
            for path in design.paths
            if _on(path.points[0], start, end) and _on(path.points[-1], start, end)
        )
        if along < math.dist(start, end) - 1e-6:
            short.add(index)
    assert len([i for i in short if i < 4]) == 1, "one near edge broken"
    assert len([i for i in short if 4 <= i < 8]) == 1, "and one far edge"


def _on(point, start, end, tol=1e-6):
    return math.dist(point, start) + math.dist(point, end) - math.dist(start, end) < tol


def test_the_breaks_cost_exactly_what_they_should():
    plain = drawn(NeckerCube(size=200.0).build())
    broken = drawn(ImpossibleCube(size=200.0, gap=0.05).build())
    assert plain - broken == pytest.approx(2.0 * 2.0 * 0.05 * 200.0)


def test_both_cubes_are_the_width_they_say():
    assert NeckerCube(size=150.0).build().bounds.width == pytest.approx(150.0)
    assert ImpossibleCube(size=150.0).build().bounds.width == pytest.approx(150.0)


def test_the_cube_lands_where_it_is_told():
    assert NeckerCube(size=100.0, center=(7.0, -3.0)).build().bounds.center == pytest.approx(
        (7.0, -3.0)
    )


# --- the cafe wall ----------------------------------------------------------


def test_the_dark_tiles_alternate_with_the_paper():
    motif = CafeWall(cols=6, rows=4, hatch=3)
    design = motif.build()
    tiles = [path for path in design.paths if path.closed]
    assert len(tiles) == 6 * 4 // 2


def test_each_dark_tile_is_a_square_with_its_hatching():
    motif = CafeWall(cols=4, rows=2, size=20.0, hatch=5)
    design = motif.build()
    tiles = [p for p in design.paths if p.closed]
    lines = [p for p in design.paths if not p.closed]
    assert len(tiles) == 4
    for tile in tiles:
        assert tile.length == pytest.approx(80.0)
    # Five hatch lines per tile, plus the one mortar line between two rows.
    assert len(lines) == 4 * 5 + 1


def test_every_mortar_line_is_dead_level():
    # The whole point: they are exactly horizontal and exactly parallel.
    motif = CafeWall(cols=7, rows=5, size=30.0)
    width = 7 * 30.0
    mortar = [
        p
        for p in motif.build().paths
        if not p.closed and math.dist(p.points[0], p.points[-1]) == pytest.approx(width)
    ]
    assert len(mortar) == 4
    for line in mortar:
        assert line.points[0][1] == pytest.approx(line.points[-1][1])


def test_every_other_row_is_shifted_and_the_rest_are_not():
    motif = CafeWall(cols=4, rows=4, size=20.0, shift=0.5)
    lefts = sorted({round(min(x for x, _ in p.points), 6) for p in motif.build().paths if p.closed})
    steps = {round(b - a, 6) for a, b in itertools.pairwise(lefts)}
    assert 10.0 in steps  # half a tile: the shifted rows


def test_no_shift_is_a_plain_checkerboard():
    motif = CafeWall(cols=4, rows=4, size=20.0, shift=0.0)
    lefts = {round(min(x for x, _ in p.points), 6) for p in motif.build().paths if p.closed}
    assert len(lefts) == 4


# --- moire ------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["rings", "lines", "radial"])
def test_a_moire_is_two_patterns_of_the_same_size(kind):
    design = MoirePattern(kind=kind, count=12).build()
    assert len(design.paths) == 24


def test_the_rings_are_closed_and_the_gratings_are_not():
    assert all(p.closed for p in MoirePattern(kind="rings", count=5).build().paths)
    assert not any(p.closed for p in MoirePattern(kind="lines", count=5).build().paths)
    assert not any(p.closed for p in MoirePattern(kind="radial", count=5).build().paths)


def test_the_second_pattern_is_the_one_that_moves():
    motif = MoirePattern(kind="lines", count=6, offset=40.0)
    first = motif.family(motif.center, 0.0)
    second = motif.family((40.0, 0.0), 0.0)
    for a, b in zip(first, second, strict=True):
        for (x, y), (u, v) in zip(a.points, b.points, strict=True):
            assert (u, v) == pytest.approx((x + 40.0, y))


def test_turning_the_second_grating_changes_it():
    straight = MoirePattern(kind="lines", angle=0.0).build()
    tilted = MoirePattern(kind="lines", angle=0.3).build()
    assert [p.points for p in straight.paths] != [p.points for p in tilted.paths]


def test_rings_do_not_care_how_far_you_turn_them():
    # Concentric circles look the same at every angle, so only the offset can
    # make fringes -- which is what the docstring promises.
    assert [p.points for p in MoirePattern(angle=0.0).build().paths] == [
        p.points for p in MoirePattern(angle=1.0).build().paths
    ]


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: PenroseTriangle(size=0.0),
        lambda: PenroseTriangle(thickness=0.0),
        lambda: PenroseTriangle(thickness=0.7),
        lambda: PenroseStairs(size=-1.0),
        lambda: PenroseStairs(rise=0.0),
        lambda: PenroseStairs(width=0.0),
        lambda: PenroseStairs(steps=0),
        lambda: PenroseStairs(steps=99),
        lambda: NeckerCube(size=0.0),
        lambda: NeckerCube(depth=0.0),
        lambda: NeckerCube(depth=1.5),
        lambda: NeckerCube(angle=0.0),
        lambda: NeckerCube(angle=2.0),
        lambda: ImpossibleCube(gap=0.0),
        lambda: ImpossibleCube(gap=0.4),
        lambda: CafeWall(size=0.0),
        lambda: CafeWall(cols=0),
        lambda: CafeWall(rows=-1),
        lambda: CafeWall(mortar=-1.0),
        lambda: CafeWall(shift=2.0),
        lambda: CafeWall(hatch=0),
        lambda: CafeWall(cols=200, rows=200),
        lambda: MoirePattern(spacing=0.0),
        lambda: MoirePattern(count=0),
        lambda: MoirePattern(count=10_000),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_a_bad_moire_kind_is_refused():
    with pytest.raises(ValueError, match="kind"):
        MoirePattern(kind="grid")  # type: ignore[arg-type]


def test_meta_records_the_parameters():
    design = PenroseTriangle(size=150.0, thickness=0.3).build()
    assert design.meta["motif"] == "illusion.penrose-triangle"
    assert design.meta["size"] == 150.0
    assert design.meta["thickness"] == 0.3
