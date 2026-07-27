"""geomotif -- generate and plot geometric designs.

A **motif** is a parameterized recipe for geometry; applying a **transform**
to what it produced gives a **design**, which is what you plot or export.
That is the whole mental model::

    from geomotif import PowerSpacing
    from geomotif.motifs import SpiralBetween

    design = SpiralBetween((200, 0), (20, 0), turns=3).generate(
        120, spacing=PowerSpacing(2.5)
    )

    for x, y in design:
        ...

Point placement is **arc-length exact**: equal spacing means the same real
x,y distance between every consecutive pair of points, however tightly the
curve winds. Because resampling is generic over polylines, that applies to
every motif -- yours included.

Writing your own takes one method::

    from dataclasses import dataclass
    from geomotif import Design, Motif, Path, register

    @register("my-shape")
    @dataclass(frozen=True, slots=True)
    class MyShape(Motif):
        def build(self) -> Design:
            return Design((Path(((0.0, 0.0), (10.0, 10.0))),))

or none at all, if one of the bases in :mod:`geomotif.bases` already describes
the kind of thing you are drawing -- then you write the maths and nothing else.

Motif classes live in :mod:`geomotif.motifs`, not here: the catalogue is far
too large for a flat namespace. This module exports the core model, the motif
bases, the spacing curves, the transform layer and the registry -- the things
you build *with*. See :mod:`geomotif.core.registry` for lookup by name.

Plotting helpers (require matplotlib, ``pip install 'geomotif[plot]'``)
live in :mod:`geomotif.plotting`.
"""

from .bases import (
    Curve,
    LatticeTiling,
    LSystemMotif,
    MultiCurveMotif,
    ParametricMotif,
    PolarMotif,
    PolygonMotif,
    SegmentMotif,
    SubstitutionTiling,
)
from .core.motif import Distribution, Motif, SupportsBuild
from .core.registry import register
from .core.sampling import (
    ArcTable,
    Placement,
    densify,
    resample,
    resample_path,
    samples_for_turns,
)
from .core.spacing import (
    CircularSpacing,
    CompositeSpacing,
    CubicSpacing,
    ExponentialSpacing,
    LinearSpacing,
    Mode,
    PowerSpacing,
    QuadraticSpacing,
    ReversedSpacing,
    SineSpacing,
    SmoothstepSpacing,
    SpacingCurve,
    SpacingLike,
    TableSpacing,
    coerce_spacing,
)
from .core.transform import (
    Affine,
    clip_to,
    fit_to,
    jitter,
    layer,
    mirror_axis,
    offset_path,
    radial_repeat,
    symmetry_group,
    tile,
)
from .core.types import Bounds, Design, Path, Point
from .io import PointFormat, save_points

__version__ = "0.1.0"

__all__ = [
    "Affine",
    "ArcTable",
    "Bounds",
    "CircularSpacing",
    "CompositeSpacing",
    "CubicSpacing",
    "Curve",
    "Design",
    "Distribution",
    "ExponentialSpacing",
    "LSystemMotif",
    "LatticeTiling",
    "LinearSpacing",
    "Mode",
    "Motif",
    "MultiCurveMotif",
    "ParametricMotif",
    "Path",
    "Placement",
    "Point",
    "PointFormat",
    "PolarMotif",
    "PolygonMotif",
    "PowerSpacing",
    "QuadraticSpacing",
    "ReversedSpacing",
    "SegmentMotif",
    "SineSpacing",
    "SmoothstepSpacing",
    "SpacingCurve",
    "SpacingLike",
    "SubstitutionTiling",
    "SupportsBuild",
    "TableSpacing",
    "__version__",
    "clip_to",
    "coerce_spacing",
    "densify",
    "fit_to",
    "jitter",
    "layer",
    "mirror_axis",
    "offset_path",
    "radial_repeat",
    "register",
    "resample",
    "resample_path",
    "samples_for_turns",
    "save_points",
    "symmetry_group",
    "tile",
]
