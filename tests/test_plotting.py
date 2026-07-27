import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from geomotif import Design, Path, PowerSpacing, SmoothstepSpacing  # noqa: E402
from geomotif.motifs import BarnsleyFern, GoldenSpiral, RegularPolygon  # noqa: E402
from geomotif.plotting import (  # noqa: E402
    DARK,
    LIGHT,
    plot_comparison,
    plot_design,
    plot_grid,
    spacing_label,
)

SQUARE = RegularPolygon(sides=4, radius=100.0).build()

MIXED = Design(
    paths=(Path(((0.0, 0.0), (10.0, 0.0))), Path(((0.0, 5.0), (10.0, 5.0)))),
    points=((2.0, 8.0), (3.0, 9.0)),
)


def test_every_stroke_becomes_a_line():
    ax = plot_design(MIXED)
    assert len(ax.lines) == 2


def test_a_closed_path_is_drawn_closed():
    # The closing segment is implied in the data and has to be added here, or
    # a square renders as three sides.
    ax = plot_design(SQUARE)
    assert len(ax.lines[0].get_xdata()) == 5


def test_loose_points_are_always_drawn():
    # A scatter motif has nothing else to show, so they are not optional the
    # way a stroke's vertices are.
    ax = plot_design(BarnsleyFern(count=100).build())
    assert sum(len(c.get_offsets()) for c in ax.collections) == 100


def test_stroke_vertices_are_drawn_only_when_asked():
    assert sum(len(c.get_offsets()) for c in plot_design(SQUARE).collections) == 0
    ax = plot_design(SQUARE, show_points=True)
    assert sum(len(c.get_offsets()) for c in ax.collections) == 4


def test_the_strokes_can_be_left_out():
    assert len(plot_design(MIXED, show_paths=False).lines) == 0


def test_a_guide_replaces_the_line_but_not_the_markers():
    guide = GoldenSpiral().generate(400)
    sparse = GoldenSpiral().generate(20)
    ax = plot_design(sparse, guide=guide, show_points=True)
    assert len(ax.lines[0].get_xdata()) == 400
    assert sum(len(c.get_offsets()) for c in ax.collections) == 20


def test_a_center_is_marked():
    ax = plot_design(SQUARE, center=(0.0, 0.0))
    assert len(ax.collections) == 1


def test_endpoints_can_be_labelled():
    ax = plot_design(SQUARE, label_endpoints=True)
    assert [text.get_text() for text in ax.texts] == ["start", "end"]


def test_the_palette_reaches_the_axes():
    assert (
        plot_design(SQUARE, palette=DARK).get_facecolor()
        != plot_design(SQUARE, palette=LIGHT).get_facecolor()
    )


def test_a_title_is_set():
    assert plot_design(SQUARE, title="a square").get_title() == "a square"


def test_a_grid_hides_the_axes_it_does_not_fill():
    fig = plot_grid([("one", SQUARE, {}), ("two", MIXED, {}), ("three", SQUARE, {})], ncols=2)
    assert [ax.get_visible() for ax in fig.axes] == [True, True, True, False]


def test_a_single_panel_grid_works():
    # subplots(1, 1) hands back a bare Axes rather than an array, which is
    # exactly the case a flatten() would trip over.
    assert len(plot_grid([("only", SQUARE, {})], ncols=1).axes) == 1


def test_a_panel_can_override_what_the_grid_shares():
    fig = plot_grid([("a", SQUARE, {}), ("b", SQUARE, {"show_paths": False})], show_paths=True)
    assert len(fig.axes[0].lines) == 1
    assert len(fig.axes[1].lines) == 0


def test_a_grid_with_no_panels_is_refused():
    with pytest.raises(ValueError, match="no panels"):
        plot_grid([])


def test_a_comparison_titles_each_panel_with_its_curve():
    fig = plot_comparison(GoldenSpiral(), [None, PowerSpacing(2.5)], count=30, guide_count=100)
    assert [ax.get_title() for ax in fig.axes] == [
        "equal spacing",
        "PowerSpacing(exponent=2.5, mode='in')",
    ]


def test_a_comparison_draws_the_same_geometry_every_time():
    # Only where the points land changes; that is the whole premise.
    fig = plot_comparison(GoldenSpiral(), [None, SmoothstepSpacing()], count=30, guide_count=100)
    first, second = (ax.lines[0].get_xydata().tolist() for ax in fig.axes)
    assert first == second


def test_a_comparison_of_nothing_is_refused():
    with pytest.raises(ValueError, match="empty list"):
        plot_comparison(GoldenSpiral(), [])


@pytest.mark.parametrize(
    ("spacing", "expected"),
    [
        (None, "equal spacing"),
        (PowerSpacing(3.0), "PowerSpacing(exponent=3.0, mode='in')"),
        (SmoothstepSpacing(), "SmoothstepSpacing()"),
    ],
)
def test_a_spacing_curve_labels_itself(spacing, expected):
    assert spacing_label(spacing) == expected


def test_a_plain_function_labels_itself_by_name():
    def ease_by_hand(t):
        return t

    assert spacing_label(ease_by_hand) == "ease_by_hand"


def test_a_curve_with_no_repr_falls_back_to_its_class_name():
    class Homegrown(SmoothstepSpacing):
        __repr__ = object.__repr__

    assert spacing_label(Homegrown()) == "Homegrown"
