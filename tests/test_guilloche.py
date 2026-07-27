import itertools
import math

import pytest

from geomotif.motifs.guilloche import (
    GuillocheBand,
    GuillochePattern,
    GuillocheRosette,
    _weave,
)


def radii(design, center=(0.0, 0.0)):
    return [math.dist(center, point) for path in design.paths for point in path.points]


# --- the wave itself --------------------------------------------------------


@pytest.mark.parametrize("phase", [0.0, 0.7, math.pi, 5.0])
def test_the_wave_never_leaves_its_band(phase):
    for k in range(200):
        assert -1.0 <= _weave(k / 200.0, 5.0, 8.0, phase) <= 1.0


def test_one_frequency_against_itself_is_an_ordinary_sine():
    # Two waves of the same rate running opposite ways add to a plain sine
    # whose amplitude the phase merely scales -- which is exactly the comb
    # this module exists to avoid, and why the default frequencies differ.
    for k in range(50):
        u = k / 50.0
        assert _weave(u, 3.0, 3.0, 0.9) == pytest.approx(
            math.sin(math.tau * 3.0 * u) * math.cos(0.9)
        )


def test_a_shifted_phase_changes_the_shape_not_just_the_offset():
    plain = [_weave(k / 64.0, 5.0, 8.0, 0.0) for k in range(64)]
    shifted = [_weave(k / 64.0, 5.0, 8.0, 1.1) for k in range(64)]
    # Not a translation of each other: no rotation of the sample list matches.
    assert all(
        any(a != pytest.approx(b) for a, b in zip(plain, shifted[n:] + shifted[:n], strict=True))
        for n in range(64)
    )


# --- rosette ----------------------------------------------------------------


@pytest.mark.parametrize("layers", [1, 4, 20])
def test_a_rosette_draws_one_closed_stroke_per_layer(layers):
    design = GuillocheRosette(layers=layers).build()
    assert len(design.paths) == layers
    assert all(path.closed for path in design.paths)


def test_every_stroke_stays_within_its_own_layer_s_reach():
    motif = GuillocheRosette(radius=100.0, amplitude=20.0, layers=6, spread=5.0)
    lengths = radii(motif.build())
    assert min(lengths) >= 100.0 - 20.0 - 1e-9
    assert max(lengths) <= 100.0 + 5.0 * 5.0 + 20.0 + 1e-9


def test_the_layers_step_outward_by_the_spread():
    flat = GuillocheRosette(radius=100.0, amplitude=1e-9, layers=4, spread=8.0, twist=0.0)
    means = [
        math.fsum(math.dist((0.0, 0.0), p) for p in path.points) / len(path.points)
        for path in flat.build().paths
    ]
    for lower, higher in itertools.pairwise(means):
        assert higher - lower == pytest.approx(8.0, abs=1e-3)


def test_no_twist_stacks_identical_rings():
    still = GuillocheRosette(layers=3, spread=0.0, twist=0.0).build()
    first, *rest = [path.points for path in still.paths]
    assert all(other == first for other in rest)


def test_a_twist_makes_every_layer_a_different_curve():
    woven = GuillocheRosette(layers=3, spread=0.0, twist=0.4).build()
    first, *rest = [path.points for path in woven.paths]
    assert all(other != first for other in rest)


def test_the_rosette_is_drawn_where_it_is_told():
    # Compared by translation rather than by bounding box: the wave is not
    # symmetric, so the box is not centred on the motif and never should be.
    here = GuillocheRosette(layers=3).build()
    there = GuillocheRosette(layers=3, center=(30.0, -20.0)).build()
    for first, second in zip(here.paths, there.paths, strict=True):
        for (x, y), (u, v) in zip(first.points, second.points, strict=True):
            assert (u, v) == pytest.approx((x + 30.0, y - 20.0))


# --- band -------------------------------------------------------------------


@pytest.mark.parametrize("lines", [1, 5, 30])
def test_a_band_draws_one_open_stroke_per_line(lines):
    design = GuillocheBand(lines=lines).build()
    assert len(design.paths) == lines
    assert not any(path.closed for path in design.paths)


def test_the_band_is_exactly_as_long_and_as_tall_as_it_says():
    bounds = GuillocheBand(length=400.0, height=60.0, lines=24).build().bounds
    assert bounds.width == pytest.approx(400.0)
    assert bounds.height <= 60.0 + 1e-9
    assert bounds.height == pytest.approx(60.0, rel=0.05)


def test_every_line_runs_the_whole_length():
    motif = GuillocheBand(length=300.0, lines=6, center=(10.0, 4.0))
    for path in motif.build().paths:
        assert path.points[0][0] == pytest.approx(-140.0)
        assert path.points[-1][0] == pytest.approx(160.0)


def test_the_phases_divide_one_cycle_evenly():
    # Four lines a quarter cycle apart are four different curves. Sampled a
    # little way in, not at the very start: both waves cancel at u=0 whatever
    # the phase, so every line leaves the left edge at the same height.
    heights = {
        round(path.points[len(path.points) // 8][1], 6)
        for path in GuillocheBand(lines=4).build().paths
    }
    assert len(heights) == 4


# --- pattern ----------------------------------------------------------------


def test_the_pattern_is_a_rosette_a_border_and_two_rules():
    motif = GuillochePattern(layers=6, border_lines=5)
    design = motif.build()
    assert len(design.paths) == 6 + 5 + 2


def test_the_rules_can_be_left_off():
    plain = GuillochePattern(layers=4, border_lines=4, rules=False).build()
    assert len(plain.paths) == 8


def test_the_pattern_fills_its_radius_and_no_more():
    radius = 120.0
    design = GuillochePattern(radius=radius, layers=4, border_lines=6).build()
    assert max(radii(design)) == pytest.approx(radius, rel=1e-6)
    assert design.bounds.width == pytest.approx(2.0 * radius)


def test_the_middle_is_left_for_the_rosette():
    motif = GuillochePattern(radius=150.0, border_height=30.0, layers=4, border_lines=4)
    assert max(radii(motif.rosette().build())) <= 150.0 - 30.0 + 1e-9


def test_a_border_that_would_swallow_the_middle_is_refused():
    with pytest.raises(ValueError, match="swallows"):
        GuillochePattern(radius=100.0, border_height=100.0)


# --- shared -----------------------------------------------------------------


@pytest.mark.parametrize(
    "make",
    [
        lambda: GuillocheRosette(layers=0),
        lambda: GuillocheRosette(layers=10_000),
        lambda: GuillocheRosette(radius=0.0),
        lambda: GuillocheRosette(amplitude=0.0),
        lambda: GuillocheBand(lines=0),
        lambda: GuillocheBand(length=0.0),
        lambda: GuillocheBand(height=-1.0),
        lambda: GuillochePattern(layers=0),
        lambda: GuillochePattern(border_lines=0),
        lambda: GuillochePattern(radius=0.0),
        lambda: GuillochePattern(border_height=0.0),
    ],
)
def test_bad_parameters_are_refused(make):
    with pytest.raises(ValueError):
        make()


def test_meta_records_the_parameters():
    design = GuillocheRosette(layers=3, petals=9.0).build()
    assert design.meta["motif"] == "guilloche.rosette"
    assert design.meta["layers"] == 3
    assert design.meta["petals"] == 9.0
