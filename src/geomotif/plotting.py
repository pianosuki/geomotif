"""Matplotlib helpers for looking at a design.

Kept out of the core so the engine stays dependency-free; importing this
module is the only thing that needs matplotlib
(``pip install 'geomotif[plot]'``).

Three functions, for three questions:

* :func:`plot_design` -- what does this design look like?
* :func:`plot_grid` -- how do these designs compare?
* :func:`plot_comparison` -- what does a spacing curve actually *do*?

The last is the library's headline idea in one image: the same motif, the same
point count, sampled by different curves.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    raise ImportError(
        "geomotif.plotting requires matplotlib. Install it with: pip install 'geomotif[plot]'"
    ) from None

from .core.sampling import resample
from .core.style import point_styles_of, styles_of

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .core.motif import SupportsBuild
    from .core.spacing import SpacingLike
    from .core.style import Style
    from .core.types import Design, Point

__all__ = [
    "DARK",
    "LIGHT",
    "Palette",
    "Panel",
    "plot_comparison",
    "plot_design",
    "plot_grid",
    "spacing_label",
]

#: One cell of a :func:`plot_grid`: a title, what to draw, and whatever extra
#: keyword arguments :func:`plot_design` should get for that cell alone.
type Panel = tuple[str, Design, dict[str, Any]]


@dataclass(frozen=True, slots=True)
class Palette:
    """Every colour a figure is drawn in.

    Gathered into one value rather than left as module constants so that a
    dark-mode figure is a different argument, not a different code path.
    """

    page: str
    surface: str
    primary_ink: str
    secondary_ink: str
    muted: str
    gridline: str
    baseline: str
    series: str


#: The default: paper-white, for a light docs theme or a printed page.
LIGHT = Palette(
    page="#f9f9f7",
    surface="#fcfcfb",
    primary_ink="#0b0b0b",
    secondary_ink="#52514e",
    muted="#898781",
    gridline="#e1e0d9",
    baseline="#c3c2b7",
    series="#2a78d6",
)

#: The same figure for a dark docs theme. Ink and paper swap; the series
#: colour lightens, because #2a78d6 on near-black is barely there.
DARK = Palette(
    page="#14141a",
    surface="#1b1b22",
    primary_ink="#f2f2ef",
    secondary_ink="#c9c8c3",
    muted="#7c7b85",
    gridline="#2c2c36",
    baseline="#3d3d49",
    series="#69a8f0",
)


def plot_design(
    design: Design,
    *,
    ax: Any = None,
    title: str | None = None,
    color: str | None = None,
    show_paths: bool = True,
    show_points: bool = False,
    dot_size: float = 14.0,
    linewidth: float = 1.4,
    guide: Design | None = None,
    center: Point | None = None,
    label_endpoints: bool = False,
    palette: Palette = LIGHT,
    grid: bool = True,
) -> Any:
    """Draw a design onto ``ax`` (a new figure if omitted) and return the axes.

    Parameters
    ----------
    design : Design
        What to draw. Its strokes become lines and its loose points become
        markers -- always, since a loose point is the only thing a scatter
        motif has to show.
    ax : matplotlib.axes.Axes, optional
        Target axes; a new styled figure is created when omitted.
    title : str, optional
        Panel title, drawn in secondary ink.
    color : str, optional
        Series colour for lines and markers. Defaults to the palette's. A
        stroke carrying a style of its own (:mod:`geomotif.core.style`) is
        drawn in that colour and width instead, so a two-pen design looks on
        screen the way it will come off the plotter.
    show_paths : bool, optional
        Draw the strokes.
    show_points : bool, optional
        Draw a marker at every *vertex* of every stroke -- the "here is where
        the points landed" view this library exists for. Off by default,
        because a motif with four thousand vertices becomes a smear.
    dot_size, linewidth : float, optional
        Marker area and line width, in matplotlib's usual units.
    guide : Design, optional
        A denser version of the same geometry, drawn as the smooth line under
        the markers. Without it the line connects the sample points
        themselves, which looks polygonal when the spacing is wide.
    center : (float, float), optional
        Mark a point of interest -- a spiral's centre -- with a small cross.
    label_endpoints : bool, optional
        Direct-label the design's first and last points "start" / "end".
    palette : Palette, optional
        :data:`LIGHT` or :data:`DARK`.
    grid : bool, optional
        Draw the background grid.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6))
        fig.patch.set_facecolor(palette.page)
    _style_axes(ax, title, palette, grid=grid)
    ink = color if color is not None else palette.series

    if show_paths:
        drawn = guide if guide is not None else design
        # A faint line under visible markers, a solid one on its own: the
        # markers are the subject when they are there, and the line is not.
        alpha = 0.45 if show_points else 0.9
        for path, style in zip(drawn.paths, styles_of(drawn), strict=True):
            xs = [p[0] for p in path.points]
            ys = [p[1] for p in path.points]
            if path.closed and len(path.points) > 2:
                xs.append(xs[0])
                ys.append(ys[0])
            ax.plot(
                xs,
                ys,
                color=_ink_for(style, ink),
                linewidth=_width_for(style, linewidth),
                alpha=alpha,
                zorder=2,
            )

    markers: list[Point] = list(design.points)
    colours = [_ink_for(style, ink) for style in point_styles_of(design)]
    if show_points:
        markers = [p for path in design.paths for p in path.points] + markers
        colours = [
            _ink_for(style, ink)
            for path, style in zip(design.paths, styles_of(design), strict=True)
            for _ in path.points
        ] + colours
    if markers:
        ax.scatter(
            [p[0] for p in markers],
            [p[1] for p in markers],
            s=dot_size,
            color=colours,
            edgecolors=palette.surface,
            linewidths=0.6,
            zorder=3,
        )

    if center is not None:
        ax.scatter(
            [center[0]],
            [center[1]],
            marker="+",
            s=48,
            color=palette.muted,
            linewidths=1.2,
            zorder=3,
        )

    if label_endpoints:
        ends = list(design)
        for (x, y), text, ha in ((ends[0], "start", "left"), (ends[-1], "end", "right")):
            ax.annotate(
                text,
                (x, y),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
                color=palette.secondary_ink,
                ha=ha,
                zorder=4,
            )
    return ax


def plot_grid(
    panels: Sequence[Panel],
    *,
    ncols: int = 2,
    panel_size: float = 4.4,
    suptitle: str | None = None,
    palette: Palette = LIGHT,
    **shared: Any,
) -> Any:
    """Draw several designs as a grid of panels and return the figure.

    Parameters
    ----------
    panels : sequence of (str, Design, dict)
        Each entry is ``(title, design, extra)``, where ``extra`` is passed
        through to :func:`plot_design` for that panel alone.
    ncols : int, optional
        Panels per row.
    panel_size : float, optional
        Side length of each square panel, in inches.
    suptitle : str, optional
        Figure-level title, drawn in primary ink.
    palette : Palette, optional
        Applied to every panel.
    **shared
        Passed to :func:`plot_design` for every panel; a panel's own ``extra``
        wins where the two disagree.
    """
    if not panels:
        raise ValueError("cannot plot a grid with no panels")
    count = len(panels)
    nrows = (count + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(panel_size * ncols, panel_size * nrows))
    fig.patch.set_facecolor(palette.page)
    axes = [axes] if count == 1 and ncols == 1 else list(axes.flat)

    # axes can outnumber panels when the count isn't a multiple of ncols; the
    # leftovers are hidden below, so the zip is meant to truncate.
    for ax, (title, design, extra) in zip(axes, panels, strict=False):
        plot_design(design, ax=ax, title=title, palette=palette, **{**shared, **extra})
    for ax in axes[count:]:
        ax.set_visible(False)

    if suptitle:
        fig.suptitle(suptitle, color=palette.primary_ink, fontsize=13)
    fig.tight_layout()
    return fig


def plot_comparison(
    motif: SupportsBuild,
    spacings: Sequence[SpacingLike | None],
    *,
    count: int = 120,
    guide_count: int = 800,
    ncols: int = 2,
    panel_size: float = 4.4,
    suptitle: str | None = None,
    palette: Palette = LIGHT,
) -> Any:
    """Draw one motif sampled by several spacing curves, side by side.

    This is the library's whole premise in one figure: the same curve and the
    same number of points every time, and only where they land changes.

    Parameters
    ----------
    motif : Motif
        What to sample. ``None`` in ``spacings`` means equal spacing.
    spacings : sequence
        One panel per entry.
    count : int, optional
        Points per panel.
    guide_count : int, optional
        Points in the smooth line drawn underneath.
    ncols, panel_size, suptitle, palette
        As for :func:`plot_grid`.
    """
    if not spacings:
        raise ValueError("cannot compare an empty list of spacing curves")
    # Built once and resampled per panel, rather than generate()d per panel:
    # the geometry is identical in every one, and that is the point.
    base = motif.build()
    guide = resample(base, guide_count)
    panels: list[Panel] = [
        (spacing_label(spacing), resample(base, count, spacing=spacing), {}) for spacing in spacings
    ]
    return plot_grid(
        panels,
        ncols=ncols,
        panel_size=panel_size,
        suptitle=suptitle,
        palette=palette,
        show_points=True,
        guide=guide,
    )


def spacing_label(spacing: SpacingLike | None) -> str:
    """Return a panel title for a spacing curve, however it was expressed."""
    if spacing is None:
        return "equal spacing"
    name: str | None = getattr(spacing, "__name__", None)
    if name:
        return name
    # Most curves have a __repr__ worth showing; the parameterless ones do
    # not, and "<...LinearSpacing object at 0x7f...>" is not a panel title.
    text = repr(spacing)
    return type(spacing).__name__ if text.startswith("<") else text


def _ink_for(style: Style | None, fallback: str) -> str:
    """Return the colour a styled stroke asks for, or the figure's own."""
    if style is None or style.stroke is None:
        return fallback
    return style.stroke


def _width_for(style: Style | None, fallback: float) -> float:
    """Return the width a styled stroke asks for, or the figure's own."""
    if style is None or style.width is None:
        return fallback
    return style.width


def _style_axes(ax: Any, title: str | None, palette: Palette, *, grid: bool) -> None:
    ax.set_facecolor(palette.surface)
    ax.set_axisbelow(True)
    ax.grid(grid, color=palette.gridline, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_color(palette.baseline)
        spine.set_linewidth(0.8)
    ax.tick_params(colors=palette.muted, labelsize=8, length=3, width=0.8)
    ax.set_aspect("equal", adjustable="datalim")
    if title:
        ax.set_title(title, color=palette.secondary_ink, fontsize=10, pad=10)
