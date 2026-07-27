"""Demo entry point: generate a few spirals and plot them with matplotlib.

Installed as the ``spiralgen-demo`` console command; also runnable as
``python -m spiralgen``. Requires the plotting extra
(``pip install 'spiralgen[plot]'``).

Usage::

    spiralgen-demo             # open an interactive plot window
    spiralgen-demo out.png     # save the figure to a file instead
"""

import sys
from typing import Any

from .curves import ExponentialSpacing, PowerSpacing, SmoothstepSpacing
from .generator import generate_spiral

CENTER = (0, 0)

# Each entry's kwargs dict mixes tuples/int/bool/callables, so it's typed
# loosely as Any -- these are just **-unpacked straight into generate_spiral.
EXAMPLES: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    (
        "Equal spacing — 3 turns inward, clockwise",
        {"start": (200, 0), "end": (20, 0), "num_points": 120, "turns": 3},
        {},
    ),
    (
        "PowerSpacing(2.5, 'in') — spacing gradually increases",
        {
            "start": (200, 0),
            "end": (20, 0),
            "num_points": 120,
            "turns": 3,
            "spacing": PowerSpacing(2.5, mode="in"),
        },
        {},
    ),
    (
        "ExponentialSpacing('out') — dense finish, counter-clockwise",
        {
            "start": (0, 150),
            "end": (0, 20),
            "num_points": 120,
            "turns": 4,
            "clockwise": False,
            "spacing": ExponentialSpacing(mode="out", strength=6),
        },
        {},
    ),
    (
        "SmoothstepSpacing — outward, dense at both ends",
        {
            "start": (20, 0),
            "end": (-160, 160),
            "num_points": 120,
            "turns": 2,
            "spacing": SmoothstepSpacing(),
        },
        {},
    ),
]


def main(argv: list[str] | None = None) -> None:
    try:
        from .plotting import plot_spiral_grid
    except ImportError:
        raise SystemExit("The demo needs matplotlib: pip install 'spiralgen[plot]'") from None

    args = sys.argv[1:] if argv is None else argv

    panels = []
    for title, spiral_kwargs, plot_kwargs in EXAMPLES:
        spiral_kwargs.setdefault("center", CENTER)
        points = generate_spiral(**spiral_kwargs)
        # Dense equal-spaced copy of the same geometry, drawn as the smooth
        # guide line under the actual sample points.
        guide = generate_spiral(**{**spiral_kwargs, "num_points": 800, "spacing": None})
        plot_kwargs.setdefault("center", spiral_kwargs["center"])
        plot_kwargs.setdefault("path", guide)
        panels.append((title, points, plot_kwargs))

    fig = plot_spiral_grid(panels, ncols=2, suptitle="spiralgen demo")

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
