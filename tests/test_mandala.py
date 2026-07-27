import math

import pytest

from geomotif.compose import (
    Kaleidoscope,
    LayeredRings,
    Mandala,
    Ring,
    Snowflake,
    SpokePattern,
)
from geomotif.core.types import Design, Path
from geomotif.motifs import Circle, Line, RegularPolygon, Rose


class Blob:
    """Anything with a build() method is a motif, inheritance or not."""

    def build(self):
        return Design((Path(((0.0, 0.0), (10.0, 0.0), (10.0, 4.0)), closed=True),), ((2.0, 2.0),))


def turned(points, angle, about=(0.0, 0.0)):
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    cx, cy = about
    return [
        (cx + (x - cx) * cos_a - (y - cy) * sin_a, cy + (x - cx) * sin_a + (y - cy) * cos_a)
        for x, y in points
    ]


def flipped(points):
    return [(x, -y) for x, y in points]


def _cell(point, scale=1000.0):
    return (math.floor(point[0] * scale), math.floor(point[1] * scale))


def _covers(these, those, tol):
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for point in those:
        grid.setdefault(_cell(point), []).append(point)
    for point in these:
        cx, cy = _cell(point)
        near = (
            q for dx in (-1, 0, 1) for dy in (-1, 0, 1) for q in grid.get((cx + dx, cy + dy), ())
        )
        if not any(math.dist(point, q) <= tol for q in near):
            return False
    return True


def same_shape(these, those, tol=1e-6):
    """Return whether two point sets describe the same figure.

    Compared by nearest neighbour rather than by rounding: rotating a point
    and rounding does not give the same digits as rounding it and rotating,
    so an exact set comparison would fail on arithmetic rather than on
    geometry.
    """
    return _covers(these, those, tol) and _covers(those, these, tol)


def all_points(design):
    return list(design)


# --- Ring -------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 3, 12])
def test_a_ring_places_one_copy_per_count(count):
    assert len(Ring(Circle(), count, 50.0).placements()) == count


def test_mirroring_a_ring_doubles_its_copies():
    assert len(Ring(Circle(), 5, 50.0, mirror=True).placements()) == 10


def test_a_facing_copy_turns_with_its_own_angle():
    ring = Ring(Line(start=(0.0, 0.0), end=(10.0, 0.0)), 4, 50.0)
    ends = [place((10.0, 0.0)) for place in ring.placements()]
    # Each copy's far end is further out along its own ray, so the four ends
    # sit on a circle of radius sixty, one per quadrant.
    for end in ends:
        assert math.dist((0.0, 0.0), end) == pytest.approx(60.0)


def test_an_upright_copy_keeps_its_own_angle():
    ring = Ring(Line(start=(0.0, 0.0), end=(10.0, 0.0)), 4, 50.0, face=False)
    for place in ring.placements():
        start, end = place((0.0, 0.0)), place((10.0, 0.0))
        assert end[1] - start[1] == pytest.approx(0.0)
        assert end[0] - start[0] == pytest.approx(10.0)


def test_the_phase_turns_the_whole_ring():
    plain = Ring(Circle(), 6, 50.0).placements()
    turned_ring = Ring(Circle(), 6, 50.0, phase=math.pi / 2.0).placements()
    for before, after in zip(plain, turned_ring, strict=True):
        x, y = before((0.0, 0.0))
        assert after((0.0, 0.0)) == pytest.approx((-y, x))


def test_a_ring_of_nothing_buildable_is_refused():
    with pytest.raises(TypeError, match="build"):
        Ring("not a motif", 4, 50.0)  # type: ignore[arg-type]


# --- Mandala ----------------------------------------------------------------


def test_a_mandala_draws_every_ring_s_every_copy():
    rings = (
        Ring(RegularPolygon(sides=3, radius=10.0), 8, 60.0),
        Ring(Circle(radius=5.0), 12, 110.0),
    )
    assert len(Mandala(rings=rings).build().paths) == 8 + 12


def test_the_unit_may_be_anything_that_builds():
    design = Mandala(rings=(Ring(Blob(), 5, 40.0),)).build()
    assert len(design.paths) == 5
    assert len(design.points) == 5


def test_a_mandala_is_as_symmetric_as_its_least_symmetric_ring():
    # Rings of eight and twelve leave the whole figure fourfold, which is the
    # kind of thing you want to be able to see in the output rather than
    # reason about in your head.
    rings = (
        Ring(RegularPolygon(sides=3, radius=9.0), 8, 60.0),
        Ring(RegularPolygon(sides=4, radius=7.0), 12, 110.0),
    )
    points = all_points(Mandala(rings=rings).build())
    assert same_shape(turned(points, math.tau / 4.0), points)
    assert not same_shape(turned(points, math.tau / 8.0), points)


def test_a_mandala_is_drawn_where_it_is_told():
    here = Mandala(rings=(Ring(Circle(radius=8.0), 6, 50.0),)).build()
    there = Mandala(rings=(Ring(Circle(radius=8.0), 6, 50.0),), center=(20.0, 5.0)).build()
    assert there.bounds.center == pytest.approx(
        (here.bounds.center[0] + 20.0, here.bounds.center[1] + 5.0)
    )


def test_a_mandala_with_no_rings_is_refused():
    with pytest.raises(ValueError, match="at least one ring"):
        Mandala(rings=())


# --- Kaleidoscope -----------------------------------------------------------


@pytest.mark.parametrize(("group", "copies"), [("C1", 1), ("C6", 6), ("D3", 6), ("D6", 12)])
def test_the_group_decides_how_many_copies_there_are(group, copies):
    unit = Rose(n=3, size=80.0)
    strokes = len(unit.build().paths)
    assert len(Kaleidoscope(unit=unit, group=group).build().paths) == strokes * copies


def test_a_cyclic_kaleidoscope_is_invariant_under_its_own_turn():
    points = all_points(
        Kaleidoscope(unit=Line(start=(20.0, 0.0), end=(70.0, 30.0)), group="C5").build()
    )
    assert same_shape(turned(points, math.tau / 5.0), points)


def test_a_dihedral_kaleidoscope_is_also_invariant_under_reflection():
    points = all_points(
        Kaleidoscope(unit=Line(start=(20.0, 0.0), end=(70.0, 30.0)), group="D4").build()
    )
    assert same_shape(turned(points, math.tau / 4.0), points)
    # Reflecting in each sector's bisector generates mirror lines at every
    # half sector, and the x-axis is one of them.
    assert same_shape(flipped(points), points)


def test_the_group_is_case_insensitive_and_forgiving_of_space():
    assert len(Kaleidoscope(unit=Circle(), group=" d3 ").build().paths) == 6


@pytest.mark.parametrize("group", ["", "X6", "C", "six", "D-2"])
def test_a_group_that_is_not_a_group_is_refused(group):
    with pytest.raises(ValueError, match="C6"):
        Kaleidoscope(unit=Circle(), group=group)


# --- SpokePattern -----------------------------------------------------------


@pytest.mark.parametrize("count", [1, 6, 60])
def test_a_spoke_pattern_draws_one_line_per_spoke(count):
    design = SpokePattern(count=count).build()
    assert len(design.paths) == count
    assert all(len(path.points) == 2 for path in design.paths)


def test_every_spoke_runs_from_the_inner_circle_to_the_outer():
    motif = SpokePattern(count=9, inner=30.0, outer=90.0, center=(4.0, -6.0))
    for path in motif.build().paths:
        assert math.dist((4.0, -6.0), path.points[0]) == pytest.approx(30.0)
        assert math.dist((4.0, -6.0), path.points[1]) == pytest.approx(90.0)


def test_stagger_shortens_every_second_spoke():
    motif = SpokePattern(count=8, inner=20.0, outer=100.0, stagger=0.5)
    reaches = [round(math.dist((0.0, 0.0), path.points[1]), 6) for path in motif.build().paths]
    assert reaches[0::2] == pytest.approx([100.0] * 4)
    assert reaches[1::2] == pytest.approx([60.0] * 4)


def test_spokes_may_start_at_the_middle():
    motif = SpokePattern(count=6, inner=0.0, outer=50.0)
    assert all(path.points[0] == pytest.approx((0.0, 0.0)) for path in motif.build().paths)


# --- LayeredRings -----------------------------------------------------------


def test_evenly_spaced_rings_step_by_the_step():
    assert LayeredRings(count=4, inner=10.0, step=15.0).radii() == pytest.approx(
        [10.0, 25.0, 40.0, 55.0]
    )


def test_growth_spreads_the_rings_as_they_go():
    radii = LayeredRings(count=4, inner=10.0, step=10.0, growth=2.0).radii()
    assert radii == pytest.approx([10.0, 20.0, 40.0, 80.0])


def test_each_ring_is_a_closed_circle_of_its_own_radius():
    motif = LayeredRings(count=3, inner=20.0, step=20.0, center=(5.0, 5.0))
    for path, radius in zip(motif.build().paths, motif.radii(), strict=True):
        assert path.closed
        assert all(math.dist((5.0, 5.0), p) == pytest.approx(radius) for p in path.points)


# --- Snowflake --------------------------------------------------------------


def test_a_snowflake_has_sixfold_symmetry():
    points = all_points(Snowflake(seed=3).build())
    assert same_shape(turned(points, math.tau / 6.0), points)


def test_a_snowflake_is_mirrored_down_every_arm():
    points = all_points(Snowflake(seed=3).build())
    assert same_shape(flipped(points), points)


def test_the_same_seed_grows_the_same_crystal():
    first = Snowflake(seed=11).build()
    second = Snowflake(seed=11).build()
    assert [p.points for p in first.paths] == [p.points for p in second.paths]


def test_a_different_seed_grows_a_different_crystal():
    first = Snowflake(seed=1).build()
    second = Snowflake(seed=2).build()
    assert [p.points for p in first.paths] != [p.points for p in second.paths]


def test_growth_never_touches_the_global_random_stream():
    import random

    random.seed(1234)
    expected = random.random()
    random.seed(1234)
    Snowflake(seed=99).build()
    assert random.random() == expected


@pytest.mark.parametrize(("depth", "branches"), [(0, 4), (1, 3), (2, 2), (3, 1)])
def test_the_arm_grows_one_stroke_per_branch_at_every_level(depth, branches):
    # A spine plus two branches per foot, recursively -- so the count is the
    # geometric series in twice the branch count, whatever the jitter does to
    # where the feet land.
    grown = len(Snowflake(depth=depth, branches=branches, seed=5).arm().paths)
    assert grown <= sum((2 * branches) ** level for level in range(depth + 1))
    assert grown >= 1


def test_a_given_arm_is_used_instead_of_a_grown_one():
    arm = Line(start=(0.0, 0.0), end=(100.0, 0.0))
    flake = Snowflake(unit=arm).build()
    # One stroke, mirrored to two, turned six ways -- and the mirror of a
    # stroke lying along the axis is itself, so every point stays on a spoke.
    assert len(flake.paths) == 12
    assert flake.bounds.width == pytest.approx(200.0)


def test_a_snowflake_is_drawn_where_it_is_told():
    flake = Snowflake(seed=4, center=(30.0, -10.0)).build()
    assert flake.bounds.center == pytest.approx((30.0, -10.0), abs=1e-6)


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: Ring(Circle(), 0, 50.0),
        lambda: Ring(Circle(), 10_000, 50.0),
        lambda: SpokePattern(count=0),
        lambda: SpokePattern(inner=-1.0),
        lambda: SpokePattern(inner=90.0, outer=50.0),
        lambda: SpokePattern(stagger=1.0),
        lambda: LayeredRings(count=0),
        lambda: LayeredRings(inner=0.0),
        lambda: LayeredRings(step=0.0),
        lambda: LayeredRings(growth=0.0),
        lambda: Snowflake(size=0.0),
        lambda: Snowflake(branches=-1),
        lambda: Snowflake(depth=5),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_something_that_cannot_build_is_refused():
    with pytest.raises(TypeError, match="build"):
        Kaleidoscope(unit=42)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="build"):
        Snowflake(unit="arm")  # type: ignore[arg-type]


def test_meta_records_the_parameters():
    design = SpokePattern(count=11, inner=5.0).build()
    assert design.meta["motif"] == "spoke-pattern"
    assert design.meta["count"] == 11
    assert design.meta["inner"] == 5.0


def test_a_branch_that_would_grow_past_the_tip_is_skipped():
    # Feet march out along the spine and are jittered, so with enough of them
    # the last one can be thrown past the end. It is dropped rather than
    # sprouting a branch off thin air.
    crowded = len(Snowflake(branches=20, depth=1, seed=2).arm().paths)
    assert crowded < 1 + 2 * 20
