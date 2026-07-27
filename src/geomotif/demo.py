"""Demo entry point: generate a few spirals and plot them with matplotlib.

Installed as the ``geomotif-demo`` console command; also runnable as
``python -m geomotif``. Requires the plotting extra
(``pip install 'geomotif[plot]'``).

Usage::

    geomotif-demo             # open an interactive plot window
    geomotif-demo out.png     # save the figure to a file instead
"""

import sys

from .core.spacing import ExponentialSpacing, PowerSpacing, SmoothstepSpacing, SpacingLike
from .motifs.spirals import SpiralBetween

CENTER = (0.0, 0.0)

# Each entry pairs a motif with the spacing curve to sample it by -- the two
# halves of the library's headline idea, shown side by side.
EXAMPLES: list[tuple[str, SpiralBetween, SpacingLike | None]] = [
    (
        "Equal spacing — 3 turns inward, clockwise",
        SpiralBetween((200, 0), (20, 0), center=CENTER, turns=3),
        None,
    ),
    (
        "PowerSpacing(2.5, 'in') — spacing gradually increases",
        SpiralBetween((200, 0), (20, 0), center=CENTER, turns=3),
        PowerSpacing(2.5, mode="in"),
    ),
    (
        "ExponentialSpacing('out') — dense finish, counter-clockwise",
        SpiralBetween((0, 150), (0, 20), center=CENTER, turns=4, clockwise=False),
        ExponentialSpacing(mode="out", strength=6),
    ),
    (
        "SmoothstepSpacing — outward, dense at both ends",
        SpiralBetween((20, 0), (-160, 160), center=CENTER, turns=2),
        SmoothstepSpacing(),
    ),
]


def main(argv: list[str] | None = None) -> None:
    """Plot the showcase grid, or save it to the file named on the command line."""
    try:
        from .plotting import Panel, plot_grid
    except ImportError:
        raise SystemExit("The demo needs matplotlib: pip install 'geomotif[plot]'") from None

    args = sys.argv[1:] if argv is None else argv

    panels: list[Panel] = []
    for title, motif, spacing in EXAMPLES:
        # A dense equal-spaced copy of the same geometry is drawn as the
        # smooth guide line under the sample points.
        extra = {"center": motif.center, "guide": motif.generate(800)}
        panels.append((title, motif.generate(120, spacing=spacing), extra))

    fig = plot_grid(
        panels,
        ncols=2,
        suptitle="geomotif demo",
        show_points=True,
        label_endpoints=True,
    )

    if args:
        out = args[0]
        fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
        print(f"saved {out}")
        return

    import matplotlib
    import matplotlib.pyplot as plt

    # File-only backends can't open a window; fall back to saving a PNG
    # instead of show()ing into the void.
    if matplotlib.get_backend().lower() in {
        "agg",
        "pdf",
        "ps",
        "svg",
        "pgf",
        "template",
        "cairo",
    }:
        out = "spiral-demo.png"
        fig.savefig(out, dpi=150, facecolor=fig.get_facecolor())
        print(
            f"No GUI backend available for matplotlib — saved {out} instead.\n"
            "To get an interactive window, install one of:\n"
            "  pip install PyQt6        (inside this venv)\n"
            "  your OS's Tk package     (e.g. 'sudo pacman -S tk', "
            "'sudo apt install python3-tk')"
        )
    else:
        plt.show()


if __name__ == "__main__":
    main()
