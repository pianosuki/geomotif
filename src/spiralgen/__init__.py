"""spiralgen -- generate precisely spaced points along arbitrary spirals.

Public API::

    from spiralgen import generate_spiral, PowerSpacing

    points = generate_spiral(start=(456, 192), end=(276, 192),
                             num_points=200, turns=3,
                             spacing=PowerSpacing(2.5))

Plotting helpers (require matplotlib, ``pip install 'spiralgen[plot]'``)
live in :mod:`spiralgen.plotting`.
"""

from .curves import (
    CircularSpacing,
    CubicSpacing,
    ExponentialSpacing,
    LinearSpacing,
    PowerSpacing,
    QuadraticSpacing,
    SineSpacing,
    SmoothstepSpacing,
    SpacingCurve,
)
from .generator import Point, generate_spiral
from .io import PointFormat, save_points

__version__ = "0.1.0"

__all__ = [
    "CircularSpacing",
    "CubicSpacing",
    "ExponentialSpacing",
    "LinearSpacing",
    "Point",
    "PointFormat",
    "PowerSpacing",
    "QuadraticSpacing",
    "SineSpacing",
    "SmoothstepSpacing",
    "SpacingCurve",
    "__version__",
    "generate_spiral",
    "save_points",
]
