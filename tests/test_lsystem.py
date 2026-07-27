import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

import pytest

from geomotif import LSystemMotif


@dataclass(frozen=True, slots=True)
class Koch(LSystemMotif):
    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F--F+F"}
    angle = math.pi / 3


@dataclass(frozen=True, slots=True)
class Snowflake(LSystemMotif):
    axiom = "F--F--F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F+F--F+F"}
    angle = math.pi / 3
    closed = True


@dataclass(frozen=True, slots=True)
class Tree(LSystemMotif):
    axiom = "F"
    rules: ClassVar[Mapping[str, str]] = {"F": "F[+F][-F]"}
    angle = math.pi / 6


@dataclass(frozen=True, slots=True)
class Hilbert(LSystemMotif):
    """X and Y drive the rewriting without ever drawing anything."""

    axiom = "X"
    rules: ClassVar[Mapping[str, str]] = {"X": "+YF-XFX-FY+", "Y": "-XF+YFY+FX-"}
    angle = math.pi / 2


def test_depth_zero_is_the_axiom():
    assert Koch(depth=0).expand() == "F"


def test_expansion_applies_every_rule_simultaneously():
    assert Koch(depth=1).expand() == "F+F--F+F"
    assert Koch(depth=2).expand().count("F") == 16


def test_koch_curve_has_the_analytic_length():
    # Each round replaces one segment with four of the same step length, so a
    # unit-step curve of depth n is exactly 4**n long.
    assert Koch(depth=3).build().paths[0].length == pytest.approx(4.0**3)


def test_snowflake_has_the_analytic_perimeter():
    assert Snowflake(depth=2).build().paths[0].length == pytest.approx(3.0 * 4.0**2)


def test_step_scales_the_whole_curve():
    assert Koch(depth=2, step=3.0).build().paths[0].length == pytest.approx(3.0 * 4.0**2)


def test_a_single_stroke_is_one_path():
    assert len(Koch(depth=3).build().paths) == 1


def test_closed_grammars_close_the_path_and_drop_the_seam():
    path = Snowflake(depth=2).build().paths[0]
    assert path.closed is True
    # 48 drawing moves make 49 vertices; the last one lands back on the first.
    assert len(path.points) == 48
    assert math.dist(path.points[0], path.points[-1]) == pytest.approx(1.0)


def test_a_closed_grammar_that_does_not_meet_itself_is_still_closed():
    # The class asserts the stroke is a loop; if the geometry disagrees the
    # seam is drawn rather than silently discarding the mismatch.
    @dataclass(frozen=True, slots=True)
    class Gap(LSystemMotif):
        axiom = "F+F+F"
        angle = math.pi / 2
        closed = True

    path = Gap(depth=0).build().paths[0]
    assert path.closed is True
    assert len(path.points) == 4


def test_branches_become_separate_strokes():
    assert len(Tree(depth=2).build().paths) > 1


def test_branching_starts_a_new_stroke_at_the_fork():
    # The first branch continues the stroke it grew out of -- it is physically
    # attached to the trunk -- and closing the branch resumes at the fork.
    assert [path.points[0] for path in Tree(depth=1).build().paths] == [(0.0, 0.0), (1.0, 0.0)]


def test_unbalanced_branch_close_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Broken(LSystemMotif):
        axiom = "F]F"
        angle = math.pi / 2

    with pytest.raises(ValueError, match="branch stack"):
        Broken(depth=0).build()


def test_lowercase_symbols_move_without_drawing():
    @dataclass(frozen=True, slots=True)
    class Dashes(LSystemMotif):
        axiom = "FfF"
        angle = math.pi / 2

    design = Dashes(depth=0).build()
    assert len(design.paths) == 2
    assert design.bounds.max_x == 3.0


def test_grammar_only_symbols_draw_nothing():
    design = Hilbert(depth=2).build()
    # Every vertex sits on the integer lattice the F moves walk; an X or Y
    # that drew would put one somewhere else.
    assert all(abs(x - round(x)) < 1e-9 and abs(y - round(y)) < 1e-9 for x, y in design)


def test_plus_turns_counter_clockwise():
    @dataclass(frozen=True, slots=True)
    class Corner(LSystemMotif):
        axiom = "F+F"
        angle = math.pi / 2

    assert Corner(depth=0).build().paths[0].points[-1] == pytest.approx((1.0, 1.0))


def test_minus_turns_clockwise():
    @dataclass(frozen=True, slots=True)
    class Corner(LSystemMotif):
        axiom = "F-F"
        angle = math.pi / 2

    assert Corner(depth=0).build().paths[0].points[-1] == pytest.approx((1.0, -1.0))


def test_pipe_turns_around():
    @dataclass(frozen=True, slots=True)
    class Doubled(LSystemMotif):
        axiom = "F|F"
        angle = math.pi / 2

    assert Doubled(depth=0).build().paths[0].points[-1] == pytest.approx((0.0, 0.0))


def test_start_angle_rotates_the_result():
    @dataclass(frozen=True, slots=True)
    class Up(LSystemMotif):
        axiom = "F"
        angle = math.pi / 2

    assert Up(depth=0, start_angle=math.pi / 2).build().paths[0].points[-1] == pytest.approx(
        (0.0, 1.0)
    )


def test_missing_axiom_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Empty(LSystemMotif):
        angle = math.pi / 2

    with pytest.raises(ValueError, match="axiom"):
        Empty().build()


def test_a_grammar_that_draws_nothing_is_an_error():
    @dataclass(frozen=True, slots=True)
    class Silent(LSystemMotif):
        axiom = "X"
        angle = math.pi / 2

    with pytest.raises(ValueError, match="drew nothing"):
        Silent().build()


def test_negative_depth_is_an_error():
    with pytest.raises(ValueError, match="depth"):
        Koch(depth=-1).build()


def test_non_positive_step_is_an_error():
    with pytest.raises(ValueError, match="step"):
        Koch(step=0.0).build()


def test_runaway_expansion_is_capped():
    @dataclass(frozen=True, slots=True)
    class Explosive(LSystemMotif):
        axiom = "F"
        rules: ClassVar[Mapping[str, str]] = {"F": "F" * 2048}
        angle = math.pi / 2

    with pytest.raises(ValueError, match="symbols"):
        Explosive(depth=2).expand()


def test_generate_resamples_an_lsystem():
    assert len(Koch(depth=3).generate(200)) == 200


def test_meta_records_the_parameters():
    meta = Koch(depth=2, step=0.5).build().meta
    assert meta["motif"] == "Koch"
    assert meta["depth"] == 2
    assert meta["step"] == 0.5
