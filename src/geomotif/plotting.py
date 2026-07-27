"""Matplotlib helpers for visualizing generated spiral points.

Kept separate from the core generator so :func:`geomotif.generate_spiral`
stays dependency-free; only importing this module requires matplotlib
(``pip install 'geomotif[plot]'``).
"""

from collections.abc import Sequence
from typing import Any

try:
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    raise ImportError(
        "geomotif.plotting requires matplotlib. Install it with: pip install 'geomotif[plot]'"
    ) from None

from .generator import Point

__all__ = ["plot_spiral", "plot_spiral_grid"]

type Panel = tuple[str, Sequence[Point], dict[str, Any]]

# Chart chrome (light mode)
SURFACE = "#fcfcfb"
PAGE = "#f9f9f7"
PRIMARY_INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES = "#2a78d6"


def _style_axes(ax: Any, title: str | None = None) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_axisbelow(True)
    ax.grid(True, color=GRIDLINE, linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_color(BASELINE)
        spine.set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=8, length=3, width=0.8)
    ax.set_aspect("equal", adjustable="datalim")
    if title:
        ax.set_title(title, color=SECONDARY_INK, fontsize=10, pad=10)


def plot_spiral(
    points: Sequence[Point],
    *,
    ax: Any = None,
    title: str | None = None,
    color: str = SERIES,
    show_path: bool = True,
    show_points: bool = True,
    label_endpoints: bool = True,
    center: Point | None = None,
    path: Sequence[Point] | None = None,
) -> Any:
    """Draw one spiral onto ``ax`` (a new figure if omitted) and return the axes.

    Parameters
    ----------
    points : list[tuple[float, float]]
        Output of :func:`geomotif.generate_spiral`.
    ax : matplotlib.axes.Axes, optional
        Target axes; a new styled figure is created when omitted.
    title : str, optional
        Panel title (drawn in secondary ink).
    color : str, optional
        Series color for both the path line and the point markers.
    show_path : bool, optional
        Draw a thin connecting line along the path.
    show_points : bool, optional
        Draw a marker at every generated point.
    label_endpoints : bool, optional
        Direct-label the first and last points "start" / "end".
    center : (float, float), optional
        If given, mark the spiral's center with a small cross.
    path : list[tuple[float, float]], optional
        A dense version of the same spiral to draw as the smooth guide line.
        When omitted, the line connects the sample points themselves, which
        looks polygonal when spacing between points is large.
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 6))
        fig.patch.set_facecolor(PAGE)
    _style_axes(ax, title)

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    if show_path:
        line = path if path is not None else points
        ax.plot(
            [p[0] for p in line],
            [p[1] for p in line],
            color=color,
            linewidth=1.4,
            alpha=0.45,
            zorder=2,
        )
    if show_points:
        ax.scatter(xs, ys, s=14, color=color, edgecolors=SURFACE, linewidths=0.6, zorder=3)

    if center is not None:
        ax.scatter(
            [center[0]], [center[1]], marker="+", s=48, color=MUTED, linewidths=1.2, zorder=3
        )

    if label_endpoints and points:
        for (x, y), text, ha in ((points[0], "start", "left"), (points[-1], "end", "right")):
            ax.annotate(
                text,
                (x, y),
                textcoords="offset points",
                xytext=(6, 6),
                fontsize=8,
                color=SECONDARY_INK,
                ha=ha,
                zorder=4,
            )
    return ax


def plot_spiral_grid(
    panels: Sequence[Panel],
    *,
    ncols: int = 2,
    panel_size: float = 4.4,
    suptitle: str | None = None,
) -> Any:
    """Draw several spirals as a grid of panels and return the figure.

    Parameters
    ----------
    panels : list[(str, list[points], dict)]
        Each entry is ``(title, points, extra_kwargs)`` where ``extra_kwargs``
        is passed through to :func:`plot_spiral` (may be ``{}``).
    ncols : int, optional
        Panels per row.
    panel_size : float, optional
        Side length of each square panel in inches.
    suptitle : str, optional
        Figure-level title (drawn in primary ink).
    """
    n = len(panels)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(panel_size * ncols, panel_size * nrows))
    fig.patch.set_facecolor(PAGE)
    axes = [axes] if n == 1 else list(axes.flat)

    # axes can outnumber panels when n isn't a multiple of ncols; the
    # leftover axes are hidden below, so the zip is meant to truncate.
    for ax, (title, points, extra) in zip(axes, panels, strict=False):
        plot_spiral(points, ax=ax, title=title, **extra)
    for ax in axes[n:]:
        ax.set_visible(False)

    if suptitle:
        fig.suptitle(suptitle, color=PRIMARY_INK, fontsize=13)
    fig.tight_layout()
    return fig
