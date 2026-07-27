import math

import pytest

from geomotif.motifs.knots import (
    CelticGrid,
    CircularCelticKnot,
    EndlessKnot,
    SquareCelticKnot,
    Triquetra,
    _break_at,
    _crossings,
    _interlace,
    _over_under,
    _rounded,
)

ROOT3 = math.sqrt(3.0)

#: One of every knot, at a size small enough to reason about.
EVERY = [
    Triquetra(radius=60.0),
    Triquetra(radius=60.0, ring=True),
    CircularCelticKnot(radius=70.0, amplitude=22.0),
    SquareCelticKnot(size=160.0, amplitude=18.0),
    EndlessKnot(size=150.0),
    CelticGrid(cols=3, rows=2, size=40.0),
]
NAMES = [
    "triquetra",
    "triquetra-ring",
    "circular",
    "square",
    "endless",
    "grid",
]


def weave(motif):
    """Return a motif's loops, its crossings, and who goes over at each visit."""
    loops = motif.loops() if hasattr(motif, "loops") else (motif.loop(),)
    crossings = _crossings(loops)
    return loops, crossings, _over_under(loops, crossings)


def perimeter(points, *, closed=True):
    total = math.fsum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))
    return total + (math.dist(points[-1], points[0]) if closed else 0.0)


# --- rounding ---------------------------------------------------------------


def test_rounding_a_corner_cuts_it_off_rather_than_moving_it():
    square = ((-10.0, -10.0), (10.0, -10.0), (10.0, 10.0), (-10.0, 10.0))
    rounded = _rounded(square, 4.0)
    assert perimeter(rounded) < perimeter(square)
    for corner in square:
        assert all(math.dist(corner, p) > 1e-9 for p in rounded)
        assert min(math.dist(corner, p) for p in rounded) < 4.0


def test_a_corner_is_never_cut_past_the_middle_of_its_own_side():
    # Asking for more rounding than the side can give must not overrun the
    # neighbouring corner and turn the polygon inside out.
    thin = ((0.0, 0.0), (2.0, 0.0), (2.0, 40.0), (0.0, 40.0))
    rounded = _rounded(thin, 50.0)
    assert all(-1e-9 <= x <= 2.0 + 1e-9 for x, _ in rounded)


def test_no_rounding_leaves_the_corners_exactly_where_they_were():
    square = ((-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0))
    assert _rounded(square, 0.0) == square


# --- breaking a loop --------------------------------------------------------


def test_a_loop_with_no_holes_comes_back_in_one_piece():
    ring = tuple((math.cos(i / 20.0 * math.tau), math.sin(i / 20.0 * math.tau)) for i in range(20))
    (whole,) = _break_at(ring, [])
    assert perimeter(whole, closed=False) == pytest.approx(perimeter(ring))


def test_a_hole_at_the_seam_does_not_split_the_stroke_in_two():
    # The point list has to start somewhere, and that somewhere must not turn
    # into a break the caller never asked for.
    ring = tuple((math.cos(i / 40.0 * math.tau), math.sin(i / 40.0 * math.tau)) for i in range(40))
    assert len(_break_at(ring, [(1.0, 2.0)])) == 1
    assert len(_break_at(ring, [(1.0, 2.0), (3.0, 4.0)])) == 2


def test_two_holes_that_overlap_leave_one_gap_rather_than_a_sliver():
    square = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    (stroke,) = _break_at(square, [(2.0, 6.0), (4.0, 9.0)])
    assert perimeter(stroke, closed=False) == pytest.approx(40.0 - 7.0)


def test_a_loop_that_crosses_nothing_is_drawn_whole_and_closed():
    apart = tuple(
        tuple((x + math.cos(i / 24.0 * math.tau), math.sin(i / 24.0 * math.tau)) for i in range(24))
        for x in (-10.0, 10.0)
    )
    paths = _interlace(apart, 0.2)
    assert len(paths) == 2
    assert all(path.closed for path in paths)


def test_a_broken_stroke_is_shorter_than_the_loop_by_the_holes():
    square = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    (stroke,) = _break_at(square, [(2.0, 5.0)])
    assert perimeter(stroke, closed=False) == pytest.approx(40.0 - 3.0)


# --- the weave, for every knot ----------------------------------------------


@pytest.mark.parametrize("motif", EVERY, ids=NAMES)
def test_a_knot_actually_crosses_itself(motif):
    _, crossings, _ = weave(motif)
    assert crossings


@pytest.mark.parametrize("motif", EVERY, ids=NAMES)
def test_one_strand_goes_over_and_one_under_at_every_crossing(motif):
    _, crossings, over = weave(motif)
    for i in range(len(crossings)):
        assert over[2 * i] != over[2 * i + 1]


@pytest.mark.parametrize("motif", EVERY, ids=NAMES)
def test_the_crossings_alternate_along_every_strand(motif):
    # The property that makes a drawing read as woven rather than as a pile
    # of loops: follow any strand and it goes over, under, over, under.
    loops, crossings, over = weave(motif)
    for index in range(len(loops)):
        along = []
        for visit, crossing in enumerate(c for c in crossings for _ in (0, 1)):
            side = crossing[:3] if visit % 2 == 0 else crossing[3:]
            if side[0] == index:
                along.append((side[1], side[2], over[visit]))
        along.sort()
        for (_, _, first), (_, _, second) in zip(along, along[1:] + along[:1], strict=True):
            assert first != second


@pytest.mark.parametrize("motif", EVERY, ids=NAMES)
def test_the_under_strand_is_the_one_with_the_gaps(motif):
    # Half the visits go under, so half the crossings leave a break, and the
    # drawn length falls short of the loops' by that much.
    loops, _, over = weave(motif)
    whole = math.fsum(perimeter(loop) for loop in loops)
    drawn = math.fsum(path.length for path in motif.build().paths)
    assert drawn < whole
    assert sum(1 for passes in over if not passes) == len(over) // 2


@pytest.mark.parametrize("motif", EVERY, ids=NAMES)
def test_nothing_is_drawn_as_a_closed_loop_where_it_is_broken(motif):
    for path in motif.build().paths:
        assert not path.closed or len(path.points) > 2


# --- the triquetra ----------------------------------------------------------


def test_the_three_circles_pass_through_each_other_s_middles():
    left, middle, right = Triquetra(radius=50.0).centers()
    assert math.dist(left, middle) == pytest.approx(50.0)
    assert math.dist(middle, right) == pytest.approx(50.0)
    assert math.dist(right, left) == pytest.approx(50.0)


def test_the_three_arcs_join_into_one_closed_strand():
    (loop,) = Triquetra(radius=40.0).loops()
    steps = [math.dist(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]
    # No jump anywhere, including from the last point back to the first: the
    # half-circles meet end to end rather than merely overlapping.
    assert max(steps) < 3.0 * min(steps)


def test_the_triquetra_is_a_trefoil():
    _, crossings, _ = weave(Triquetra(radius=40.0))
    assert len(crossings) == 3


def test_the_crossings_sit_on_the_three_circle_middles():
    # Two circles a radius apart meet at the third one's middle and again on
    # the far side; the far ones are where the arcs join, so what is left to
    # cross is the middles.
    motif = Triquetra(radius=40.0)
    (loop,) = motif.loops()
    for index, piece, here, *_ in _crossings((loop,)):
        assert index == 0
        start, end = loop[piece], loop[(piece + 1) % len(loop)]
        point = (start[0] + here * (end[0] - start[0]), start[1] + here * (end[1] - start[1]))
        assert min(math.dist(point, m) for m in motif.centers()) < 1.0


def test_the_ring_weaves_through_all_three_lobes():
    plain = len(_crossings(Triquetra(radius=40.0).loops()))
    ringed = len(_crossings(Triquetra(radius=40.0, ring=True).loops()))
    assert ringed == plain + 6


def test_the_triquetra_points_up():
    design = Triquetra(radius=40.0).build()
    highest = max(design, key=lambda p: p[1])
    assert highest[0] == pytest.approx(0.0, abs=1e-6)


# --- one strand round a frame -----------------------------------------------


@pytest.mark.parametrize(("lobes", "wraps"), [(3, 2), (5, 2), (7, 3), (5, 4)])
def test_a_wound_knot_is_one_continuous_strand(lobes, wraps):
    loop = CircularCelticKnot(radius=80.0, amplitude=20.0, lobes=lobes, wraps=wraps).loop()
    steps = [math.dist(loop[i], loop[(i + 1) % len(loop)]) for i in range(len(loop))]
    # Including the step from the last point back to the first: a winding that
    # did not close would show up as one long jump there.
    assert max(steps) < 3.0 * min(steps)


@pytest.mark.parametrize(("lobes", "wraps"), [(3, 2), (5, 2), (7, 2), (7, 3)])
def test_a_wound_knot_crosses_itself_once_per_lobe_per_extra_wrap(lobes, wraps):
    motif = CircularCelticKnot(radius=80.0, amplitude=25.0, lobes=lobes, wraps=wraps)
    _, crossings, _ = weave(motif)
    assert len(crossings) == lobes * (wraps - 1)


def test_the_strand_stays_between_its_two_radii():
    motif = CircularCelticKnot(radius=90.0, amplitude=20.0)
    reach = [math.dist((0.0, 0.0), p) for p in motif.loop()]
    assert min(reach) >= 70.0 - 1e-9
    assert max(reach) <= 110.0 + 1e-9


def test_a_winding_that_would_fall_into_separate_loops_is_refused():
    with pytest.raises(ValueError, match="separate loops"):
        CircularCelticKnot(lobes=6, wraps=2)
    with pytest.raises(ValueError, match="separate loops"):
        SquareCelticKnot(lobes=9, wraps=3)


def test_the_frame_gets_squarer_as_squareness_rises():
    # A true square would reach sqrt(2) as far at the corner as at the side;
    # the squircle approaches that from below and never passes it.
    def stretch(squareness):
        motif = SquareCelticKnot(size=200.0, amplitude=1e-9, squareness=squareness)
        assert motif.spine(0.0) == pytest.approx(100.0)
        return motif.spine(math.pi / 4.0) / motif.spine(0.0)

    assert 1.0 < stretch(3.0) < stretch(6.0) < stretch(20.0) < math.sqrt(2.0)


def test_a_squareness_of_two_is_a_circle():
    motif = SquareCelticKnot(squareness=2.0)
    assert motif.spine(0.0) == pytest.approx(motif.spine(math.pi / 3.0))


# --- the endless knot -------------------------------------------------------


def test_the_endless_knot_is_one_strand_and_not_two():
    # The whole point of the name, and the reason one of the four corners
    # swaps its pair over instead of nesting like the other three: walking
    # the strand reaches all eight lines and comes back to where it started.
    corners = EndlessKnot(size=100.0, roundness=0.0).loop()
    lines = {
        (round(a[0], 6), round(a[1], 6), round(b[0], 6), round(b[1], 6))
        for a, b in zip(corners, corners[1:] + corners[:1], strict=True)
        if math.dist(a, b) > 60.0
    }
    assert len(lines) == 8


def test_the_endless_knot_visits_every_one_of_its_sixteen_ends():
    corners = EndlessKnot(size=100.0, roundness=0.0).loop()
    # Eight strands, two ends each, plus one elbow per join.
    assert len(corners) == 8 * 2 + 8


def test_the_weave_is_four_strands_each_way():
    _, crossings, _ = weave(EndlessKnot(size=150.0))
    # Sixteen crossings in the grid, plus the ones the swapped corner makes.
    assert len(crossings) >= 16


def test_the_endless_knot_is_the_size_it_says():
    bounds = EndlessKnot(size=180.0).build().bounds
    assert bounds.width == pytest.approx(180.0)
    assert bounds.height == pytest.approx(180.0)


# --- the plait --------------------------------------------------------------


def test_the_plait_turns_only_at_the_frame():
    motif = CelticGrid(cols=4, rows=3, size=20.0)
    for strand in motif.turns():
        for x, y in strand:
            assert x in (0, 8) or y in (0, 6)


def test_no_strand_ever_reaches_a_corner_of_the_frame():
    # A strand at a corner could only turn back on itself. Every corner's
    # coordinates add to an even number and every strand lives on the odd ones.
    motif = CelticGrid(cols=5, rows=4, size=20.0)
    corners = {(0, 0), (10, 0), (0, 8), (10, 8)}
    for strand in motif.turns():
        assert not corners & set(strand)


def test_every_strand_node_is_on_the_odd_diagonal():
    for strand in CelticGrid(cols=3, rows=3, size=20.0).turns():
        for x, y in strand:
            assert (x + y) % 2 == 1


@pytest.mark.parametrize(("cols", "rows"), [(1, 1), (3, 2), (4, 3), (5, 5)])
def test_a_plait_of_any_size_closes_up(cols, rows):
    for loop in CelticGrid(cols=cols, rows=rows, size=20.0).loops():
        assert len(loop) >= 3


def test_a_barrier_turns_the_strands_that_meet_it():
    plain = CelticGrid(cols=4, rows=3, size=20.0)
    broken = CelticGrid(cols=4, rows=3, size=20.0, breaks=((4, 3, "v"),))
    assert [len(s) for s in broken.turns()] != [len(s) for s in plain.turns()]
    assert any((4, 3) in strand for strand in broken.turns())


def test_the_panel_is_the_size_it_says():
    bounds = CelticGrid(cols=4, rows=3, size=50.0, roundness=0.0).build().bounds
    assert bounds.width == pytest.approx(200.0)
    assert bounds.height == pytest.approx(150.0)


@pytest.mark.parametrize(
    ("barrier", "why"),
    [
        ((4, 3, "x"), "turned"),
        ((0, 3, "h"), "inside"),
        ((4, 6, "h"), "inside"),
        ((4, 2, "h"), "even"),
    ],
)
def test_a_barrier_in_the_wrong_place_is_refused(barrier, why):
    with pytest.raises(ValueError, match=why):
        CelticGrid(cols=4, rows=3, breaks=(barrier,))


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: Triquetra(radius=0.0),
        lambda: Triquetra(gap=0.0),
        lambda: Triquetra(gap=0.9),
        lambda: CircularCelticKnot(radius=-1.0),
        lambda: CircularCelticKnot(amplitude=0.0),
        lambda: CircularCelticKnot(amplitude=500.0),
        lambda: CircularCelticKnot(lobes=1),
        lambda: CircularCelticKnot(wraps=0),
        lambda: CircularCelticKnot(resolution=4),
        lambda: SquareCelticKnot(size=0.0),
        lambda: SquareCelticKnot(amplitude=0.0),
        lambda: SquareCelticKnot(squareness=1.0),
        lambda: SquareCelticKnot(resolution=2),
        lambda: EndlessKnot(size=0.0),
        lambda: EndlessKnot(roundness=2.0),
        lambda: CelticGrid(cols=0),
        lambda: CelticGrid(size=0.0),
        lambda: CelticGrid(roundness=-1.0),
        lambda: CelticGrid(gap=0.6),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_a_knot_too_finely_sampled_to_check_is_refused():
    with pytest.raises(ValueError, match="straight pieces"):
        CircularCelticKnot(lobes=41, wraps=2, resolution=200).build()


def test_meta_records_the_parameters():
    design = CelticGrid(cols=3, rows=2, size=25.0).build()
    assert design.meta["motif"] == "knot.celtic-grid"
    assert design.meta["cols"] == 3
    assert design.meta["size"] == 25.0
