import math

import pytest

from geomotif.motifs.graphs import ModularMultiplication
from geomotif.motifs.stringart import (
    StringArtCircle,
    StringArtCorner,
    StringArtEnvelope,
    StringArtPolygon,
    _frame,
    _ring,
)


def segments(motif):
    """Return each drawn segment as its two endpoints."""
    return [(path.points[0], path.points[-1]) for path in motif.build().paths]


def on_the_line(point, a, b):
    """Return the cross product that vanishes when ``point`` is on line ``a``-``b``."""
    return (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])


def along_the_segment(point, a, b):
    """Return where ``point`` falls along ``a``-``b``: 0 at ``a``, 1 at ``b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    return ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (dx * dx + dy * dy)


# --- the strung corner ------------------------------------------------------


@pytest.mark.parametrize("count", [1, 4, 20])
def test_a_strung_corner_draws_one_thread_per_nail(count):
    assert len(segments(StringArtCorner(count=count))) == count + 1


def test_the_two_arms_are_the_first_and_last_threads():
    threads = segments(StringArtCorner(count=6, arm_a=(100.0, 0.0), arm_b=(0.0, 50.0)))
    assert threads[0][0] == pytest.approx((0.0, 0.0))
    assert threads[0][1] == pytest.approx((0.0, 50.0))
    assert threads[-1][0] == pytest.approx((100.0, 0.0))
    assert threads[-1][1] == pytest.approx((0.0, 0.0))


@pytest.mark.parametrize(("width", "height"), [(200.0, 200.0), (300.0, 80.0), (50.0, 400.0)])
def test_the_strung_corner_envelopes_a_parabola(width, height):
    # The thread that leaves one arm a fraction t along it arrives at the
    # other 1-t along, so the two distances always sum to the same total --
    # and the curve every such line touches is sqrt(x/a) + sqrt(y/b) = 1, a
    # parabola tilted to sit in the corner. Its tangency point is known
    # exactly, so each thread is checked against its own.
    count = 24
    art = StringArtCorner(count=count, arm_a=(width, 0.0), arm_b=(0.0, height))
    for i, (a, b) in enumerate(segments(art)):
        t = i / count
        touch = (t * t * width, (1.0 - t) ** 2 * height)
        assert on_the_line(touch, a, b) == pytest.approx(0.0, abs=1e-6)
        assert 0.0 <= along_the_segment(touch, a, b) <= 1.0
        assert math.sqrt(touch[0] / width) + math.sqrt(touch[1] / height) == pytest.approx(1.0)


def test_an_oblique_corner_still_works():
    art = StringArtCorner(count=8, corner=(10.0, 10.0), arm_a=(90.0, 40.0), arm_b=(-30.0, 70.0))
    threads = segments(art)
    assert len(threads) == 9
    for a, b in threads:
        assert math.dist(a, b) > 0.0


def test_more_nails_do_not_move_the_parabola():
    coarse = StringArtCorner(count=5).build().bounds
    fine = StringArtCorner(count=200).build().bounds
    assert coarse.width == pytest.approx(fine.width)
    assert coarse.height == pytest.approx(fine.height)


# --- the strung polygon -----------------------------------------------------


@pytest.mark.parametrize(("sides", "count"), [(3, 4), (5, 16), (8, 3)])
def test_a_strung_polygon_laces_every_corner(sides, count):
    assert len(segments(StringArtPolygon(sides=sides, count=count))) == sides * (count + 1)


def test_each_threads_two_ends_are_a_whole_side_apart_around_the_corner():
    # The corner construction: distance out along one arm plus distance out
    # along the other always adds up to one full side, which is what makes the
    # envelope a parabola at every corner.
    sides, count, radius = 5, 10, 100.0
    art = StringArtPolygon(sides=sides, count=count, radius=radius, rotation=0.0)
    nodes = art.nodes()
    span = count + 1
    side = math.dist(nodes[0], nodes[count])
    for e in range(sides):
        corner = nodes[e * span]  # edge e starts at corner e
        for i in range(span):
            near = nodes[(e - 1) % sides * span + i]
            far = nodes[e * span + i]
            assert math.dist(corner, near) + math.dist(corner, far) == pytest.approx(side)


def test_the_polygon_edges_are_themselves_threads():
    art = StringArtPolygon(sides=4, count=5, radius=100.0, rotation=0.0)
    lengths = sorted(math.dist(a, b) for a, b in segments(art))
    assert lengths[-1] == pytest.approx(100.0 * math.sqrt(2.0))


def test_the_strung_polygon_fits_its_radius():
    bounds = StringArtPolygon(sides=6, radius=90.0, rotation=0.0, center=(5.0, 5.0)).build().bounds
    assert bounds.max_x == pytest.approx(95.0)
    assert bounds.min_x == pytest.approx(-85.0)


# --- the general engine -----------------------------------------------------


def test_the_default_curves_are_a_circle_and_the_square_around_it():
    for k in range(9):
        t = k / 8.0
        assert math.dist((0.0, 0.0), _ring(t)) == pytest.approx(120.0)
        x, y = _frame(t)
        assert max(abs(x), abs(y)) == pytest.approx(120.0)


def test_the_square_frame_is_evenly_spaced_along_its_perimeter():
    steps = [math.dist(_frame(k / 64.0), _frame((k + 1) / 64.0)) for k in range(64)]
    # Every step but the four that turn a corner is a straight run of the same
    # length; the corner ones cut across and come out shorter.
    assert sorted(steps)[-1] == pytest.approx(sorted(steps)[4])


def test_strung_against_itself_the_engine_is_the_times_table():
    count = 60
    engine = StringArtEnvelope(
        count=count,
        rule=lambda i: 3 * i,
        curve=lambda t: (100.0 * math.cos(math.tau * t), 100.0 * math.sin(math.tau * t)),
        partner=None,
    )
    table = ModularMultiplication(modulus=count, factor=3, radius=100.0, rotation=0.0)
    engine_threads = sorted(
        tuple(sorted((tuple(round(c, 9) for c in a), tuple(round(c, 9) for c in b))))
        for a, b in segments(engine)
    )
    table_threads = sorted(
        tuple(sorted((tuple(round(c, 9) for c in a), tuple(round(c, 9) for c in b))))
        for a, b in segments(table)
    )
    assert engine_threads == table_threads


def test_a_partner_curve_doubles_the_nails():
    assert len(StringArtEnvelope(count=30, partner=None).nodes()) == 30
    assert len(StringArtEnvelope(count=30).nodes()) == 60


def test_each_thread_runs_from_one_curve_to_the_other():
    art = StringArtEnvelope(count=40)
    for a, b in segments(art):
        assert math.dist((0.0, 0.0), a) == pytest.approx(120.0)
        assert max(abs(b[0]), abs(b[1])) == pytest.approx(120.0)


def test_the_rule_decides_which_nail_each_thread_reaches():
    art = StringArtEnvelope(count=12, rule=lambda i: i + 5, partner=None)
    nodes = art.nodes()
    assert set(art.edges()) == {(i, (i + 5) % 12) for i in range(12)}
    assert len(nodes) == 12


def test_a_rule_that_stays_put_draws_nothing_rather_than_a_dot():
    # Strung against itself, a nail mapped to itself is a self-loop, and
    # SegmentMotif drops those -- so a rule that never moves leaves an empty
    # design rather than a pile of zero-length threads.
    art = StringArtEnvelope(count=10, rule=lambda i: i, partner=None)
    assert art.build().paths == ()


def test_a_rule_may_return_anything_at_all():
    art = StringArtEnvelope(count=8, rule=lambda i: -3 * i - 100, partner=None)
    assert all(0 <= j < 8 for _, j in art.edges())


# --- the alias --------------------------------------------------------------


def test_circle_string_art_is_the_times_table_under_another_name():
    assert StringArtCircle is ModularMultiplication


# --- validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: StringArtCorner(count=0),
        lambda: StringArtCorner(arm_a=(0.0, 0.0)),
        lambda: StringArtCorner(corner=(5.0, 5.0), arm_b=(5.0, 5.0)),
        lambda: StringArtPolygon(sides=2),
        lambda: StringArtPolygon(count=0),
        lambda: StringArtPolygon(radius=0.0),
        lambda: StringArtEnvelope(count=1),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_meta_records_the_parameters():
    design = StringArtPolygon(sides=7, count=9).build()
    assert design.meta["motif"] == "string-art.polygon"
    assert design.meta["sides"] == 7
    assert design.meta["count"] == 9
