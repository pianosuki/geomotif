import itertools
import math
import random

import pytest

from geomotif import ArcTable, Design, Path, PowerSpacing, densify, resample, resample_path
from geomotif.core.sampling import samples_for_turns

LINE = Path(((0.0, 0.0), (200.0, 0.0)))
SQUARE = Path(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)), closed=True)


def circle(radius=100.0, samples=2048):
    def at(u):
        angle = math.tau * u
        return (radius * math.cos(angle), radius * math.sin(angle))

    return Path(densify(at, samples=samples))


def gaps(points):
    return [math.dist(a, b) for a, b in itertools.pairwise(points)]


def test_densify_returns_one_more_point_than_segments():
    points = densify(lambda u: (u, 0.0), samples=8)
    assert len(points) == 9
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (1.0, 0.0)


def test_densify_honors_the_domain():
    points = densify(lambda u: (u, 0.0), samples=4, domain=(2.0, 6.0))
    assert points[0] == (2.0, 0.0)
    assert points[-1] == (6.0, 0.0)


def test_densify_rejects_zero_samples():
    with pytest.raises(ValueError):
        densify(lambda u: (u, 0.0), samples=0)


def test_samples_scale_with_turns():
    # The heuristic must not go below the floor, and must grow with winding.
    assert samples_for_turns(0.0) == 512
    assert samples_for_turns(8.0) > samples_for_turns(2.0)


def test_arc_table_measures_total_length():
    table = ArcTable(LINE.points)
    assert table.total == pytest.approx(200.0)


def test_arc_table_closed_includes_the_seam():
    assert ArcTable(SQUARE.points, closed=True).total == pytest.approx(40.0)


def test_arc_table_interpolates_within_a_segment():
    table = ArcTable(((0.0, 0.0), (10.0, 0.0)))
    assert table.point_at(2.5) == pytest.approx((2.5, 0.0))
    assert table.point_at_fraction(0.5) == pytest.approx((5.0, 0.0))


def test_arc_table_clamps_out_of_range_distances():
    table = ArcTable(((0.0, 0.0), (10.0, 0.0)))
    assert table.point_at(-5.0) == (0.0, 0.0)
    assert table.point_at(999.0) == (10.0, 0.0)


def test_arc_table_handles_zero_length():
    table = ArcTable(((3.0, 3.0), (3.0, 3.0)))
    assert table.total == 0.0
    assert table.point_at(1.0) == (3.0, 3.0)


def test_arc_table_rejects_empty_input():
    with pytest.raises(ValueError):
        ArcTable(())


@pytest.mark.parametrize(
    "order",
    [
        "increasing",  # what resampling actually asks for, and the fast case
        "decreasing",  # the walk has to seek backwards rather than run off
        "shuffled",  # no order at all: still every answer, still in place
    ],
)
def test_a_batch_of_lookups_answers_exactly_as_one_at_a_time_would(order):
    # points_at walks the table once for a run of ordered distances instead of
    # bisecting it per distance. That is only allowed to be faster, never
    # different -- including to the last bit, since a resampled design's
    # coordinates are compared against goldens elsewhere.
    table = ArcTable(circle().points)
    wanted = [i * table.total / 400 for i in range(401)]
    match order:
        case "decreasing":
            wanted.reverse()
        case "shuffled":
            wanted = random.Random(7).sample(wanted, len(wanted))
    assert table.points_at(wanted) == tuple(table.point_at(d) for d in wanted)


def test_a_batch_of_lookups_clamps_and_interpolates_like_a_single_one():
    table = ArcTable(((0.0, 0.0), (10.0, 0.0)))
    assert table.points_at([-5.0, 2.5, 999.0]) == ((0.0, 0.0), (2.5, 0.0), (10.0, 0.0))
    assert table.points_at_fractions([0.0, 0.5, 1.0]) == ((0.0, 0.0), (5.0, 0.0), (10.0, 0.0))


def test_a_batch_of_lookups_on_a_zero_length_polyline_gives_its_one_place():
    table = ArcTable(((3.0, 3.0), (3.0, 3.0)))
    assert table.points_at([0.0, 1.0, 2.0]) == ((3.0, 3.0),) * 3


# --- segment ----------------------------------------------------------------


def test_a_segment_keeps_the_vertices_between_its_ends_as_they_were():
    # A piece of the polyline, not a resampling of one: the ends are exact and
    # everything between them arrives at the resolution it was built at.
    table = ArcTable(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (20.0, 10.0)))
    assert table.segment(5.0, 25.0) == ((5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (15.0, 10.0))


def test_a_segment_spanning_everything_is_the_polyline_itself():
    points = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0))
    table = ArcTable(points)
    assert table.segment(0.0, table.total) == points


def test_a_segment_clamps_to_the_ends_rather_than_running_past_them():
    table = ArcTable(((0.0, 0.0), (10.0, 0.0)))
    assert table.segment(-99.0, 999.0) == ((0.0, 0.0), (10.0, 0.0))


def test_a_segment_given_its_ends_backwards_reads_them_the_right_way_round():
    table = ArcTable(((0.0, 0.0), (10.0, 0.0)))
    assert table.segment(8.0, 2.0) == table.segment(2.0, 8.0)


def test_a_segment_that_collapses_to_a_point_is_that_point():
    table = ArcTable(((0.0, 0.0), (10.0, 0.0)))
    assert table.segment(4.0, 4.0) == ((4.0, 0.0),)


def test_a_closed_polylines_segment_can_cross_the_seam():
    square = ArcTable(((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)), closed=True)
    assert square.total == pytest.approx(40.0)
    assert square.segment(35.0, 40.0)[-1] == (0.0, 0.0)  # back round to the start


def test_equal_spacing_is_equal_real_distance():
    # The crown jewel: on a curve whose radius is constant but sampled
    # unevenly in parameter, every gap must still come out the same.
    out = resample_path(circle(), 120)
    g = gaps(out.points)
    assert max(g) / min(g) < 1.05


def test_straight_line_gaps_are_exact():
    out = resample_path(LINE, 11)
    for gap in gaps(out.points):
        assert gap == pytest.approx(20.0, abs=1e-6)


def test_endpoints_are_preserved():
    out = resample_path(LINE, 37)
    assert out.points[0] == pytest.approx((0.0, 0.0))
    assert out.points[-1] == pytest.approx((200.0, 0.0))


def test_power_spacing_increases_gaps():
    out = resample_path(circle(), 40, spacing=PowerSpacing(2))
    g = gaps(out.points)
    assert g[0] < g[len(g) // 2] < g[-1]


def test_power_out_decreases_gaps():
    out = resample_path(circle(), 40, spacing=PowerSpacing(2, mode="out"))
    g = gaps(out.points)
    assert g[0] > g[len(g) // 2] > g[-1]


def test_parametric_mode_compresses_where_the_curve_tightens():
    # A path whose vertices bunch up in space but not in index: parametric
    # placement follows the index, so the gaps come out visibly unequal.
    points = tuple((float(i * i), 0.0) for i in range(50))
    path = Path(points)
    by_length = gaps(resample_path(path, 30).points)
    by_parameter = gaps(resample_path(path, 30, by="parameter").points)
    assert max(by_length) / min(by_length) < 1.05
    assert max(by_parameter) / min(by_parameter) > 3


def test_closed_path_does_not_duplicate_the_seam():
    out = resample_path(SQUARE, 8)
    assert out.closed is True
    assert len(out.points) == 8
    assert math.dist(out.points[0], out.points[-1]) > 1e-6


def test_step_mode_gives_fixed_distances():
    out = resample_path(LINE, step=25.0)
    assert len(out.points) == 9  # 0, 25, ... 200
    for gap in gaps(out.points):
        assert gap == pytest.approx(25.0)


def test_step_mode_drops_the_short_remainder():
    out = resample_path(LINE, step=30.0)
    assert len(out.points) == 7  # 0, 30, ... 180; the last 20 units are dropped
    assert out.points[-1] == pytest.approx((180.0, 0.0))


def test_zero_length_path_collapses_gracefully():
    flat = Path(((50.0, 50.0), (50.0, 50.0), (50.0, 50.0)))
    out = resample_path(flat, 5)
    assert len(out.points) == 5
    assert all(p == pytest.approx((50.0, 50.0)) for p in out.points)


def test_arc_table_exposes_its_vertices():
    table = ArcTable(SQUARE.points, closed=True)
    assert len(table.vertices) == 5  # four corners plus the closing repeat


def test_parametric_mode_on_a_single_vertex():
    out = resample_path(Path(((2.0, 2.0),)), 4, by="parameter")
    assert out.points == ((2.0, 2.0),) * 4


def test_step_mode_on_a_zero_length_path_yields_one_point():
    flat = Path(((7.0, 7.0), (7.0, 7.0)))
    assert resample_path(flat, step=1.0).points == ((7.0, 7.0),)


def test_step_mode_rejects_parametric_placement():
    with pytest.raises(ValueError):
        resample_path(LINE, step=5.0, by="parameter")


def test_empty_path_cannot_be_resampled():
    with pytest.raises(ValueError):
        resample_path(Path(()), 5)


def test_more_paths_than_points_keeps_only_the_longest():
    short = Path(((0.0, 0.0), (1.0, 0.0)))
    medium = Path(((0.0, 1.0), (5.0, 1.0)))
    long = Path(((0.0, 2.0), (50.0, 2.0)))
    out = resample(Design((short, medium, long)), 2)
    # Exactly the requested total, spent on the two longest paths.
    assert sum(len(p) for p in out.paths) == 2
    assert len(out.paths) == 2


def test_zero_length_paths_split_the_count_evenly():
    flat = Path(((1.0, 1.0), (1.0, 1.0)))
    out = resample(Design((flat, flat)), 10)
    assert [len(p) for p in out.paths] == [5, 5]


def test_resample_rejects_a_count_below_two():
    with pytest.raises(ValueError):
        resample(Design((LINE,)), 1)


def test_resample_path_argument_validation():
    with pytest.raises(ValueError):
        resample_path(LINE)
    with pytest.raises(ValueError):
        resample_path(LINE, 10, step=5.0)
    with pytest.raises(ValueError):
        resample_path(LINE, 1)
    with pytest.raises(ValueError):
        resample_path(LINE, step=-1.0)
    with pytest.raises(ValueError):
        resample_path(LINE, step=5.0, spacing=PowerSpacing(2))
    with pytest.raises(ValueError):
        resample_path(LINE, 10, by="sideways")  # type: ignore[arg-type]


def test_resample_by_length_allocates_proportionally():
    short = Path(((0.0, 0.0), (10.0, 0.0)))
    long = Path(((0.0, 5.0), (90.0, 5.0)))
    out = resample(Design((short, long)), 100)
    assert sum(len(p) for p in out.paths) == 100
    # Roughly 10:90, with one point reserved per path before apportioning.
    assert len(out.paths[0]) == pytest.approx(11, abs=2)
    assert len(out.paths[1]) == pytest.approx(89, abs=2)


def test_resample_by_length_is_exact_for_awkward_counts():
    paths = tuple(Path(((0.0, float(i)), (float(i + 1), float(i)))) for i in range(7))
    out = resample(Design(paths), 101)
    assert sum(len(p) for p in out.paths) == 101


def test_resample_even_splits_equally():
    short = Path(((0.0, 0.0), (1.0, 0.0)))
    long = Path(((0.0, 5.0), (99.0, 5.0)))
    out = resample(Design((short, long)), 100, distribute="even")
    assert [len(p) for p in out.paths] == [50, 50]


def test_resample_even_rejects_counts_that_starve_paths():
    design = Design((LINE, LINE, LINE))
    with pytest.raises(ValueError):
        resample(design, 5, distribute="even")


def test_resample_per_path_gives_each_path_the_full_count():
    out = resample(Design((LINE, SQUARE)), 20, distribute="per_path")
    assert [len(p) for p in out.paths] == [20, 20]


def test_resample_rejects_unknown_distribution():
    with pytest.raises(ValueError):
        resample(Design((LINE,)), 10, distribute="spirally")  # type: ignore[arg-type]


def test_resample_leaves_loose_points_alone():
    design = Design((LINE,), ((1.0, 1.0), (2.0, 2.0)))
    out = resample(design, 10)
    assert out.points == ((1.0, 1.0), (2.0, 2.0))


def test_resample_preserves_meta():
    design = Design((LINE,), meta={"motif": "line"})
    assert resample(design, 10).meta == {"motif": "line"}


def test_resample_of_a_pointless_design_is_a_no_op():
    design = Design(points=((1.0, 1.0),))
    assert resample(design, 10) is design


def test_resample_step_applies_to_every_path():
    out = resample(Design((LINE, LINE)), step=50.0)
    assert [len(p) for p in out.paths] == [5, 5]


def test_design_resampled_matches_the_function():
    design = Design((LINE,))
    assert design.resampled(9).paths[0].points == resample(design, 9).paths[0].points


def test_resample_is_idempotent_at_the_same_count():
    # Not bit-exact: the second pass measures the 64-gon the first pass
    # produced rather than the original curve. Measured as a displacement
    # against the radius, the drift is under a part in a million.
    once = resample_path(circle(radius=100.0), 64)
    twice = resample_path(once, 64)
    for a, b in zip(once.points, twice.points, strict=True):
        assert math.dist(a, b) < 1e-3
