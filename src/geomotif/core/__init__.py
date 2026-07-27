"""The engine: value types, sampling, spacing, transforms and the registry.

Everything here is motif-agnostic. Concrete geometry lives in
:mod:`geomotif.motifs`; this package is what makes writing one cheap.
"""

from .motif import Distribution, Motif, SupportsBuild
from .sampling import ArcTable, Placement, densify, resample, resample_path, samples_for_turns
from .spacing import (
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
from .transform import (
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
from .types import EMPTY_META, Bounds, Design, Path, Point

__all__ = [
    "EMPTY_META",
    "Affine",
    "ArcTable",
    "Bounds",
    "CircularSpacing",
    "CompositeSpacing",
    "CubicSpacing",
    "Design",
    "Distribution",
    "ExponentialSpacing",
    "LinearSpacing",
    "Mode",
    "Motif",
    "Path",
    "Placement",
    "Point",
    "PowerSpacing",
    "QuadraticSpacing",
    "ReversedSpacing",
    "SineSpacing",
    "SmoothstepSpacing",
    "SpacingCurve",
    "SpacingLike",
    "SupportsBuild",
    "TableSpacing",
    "clip_to",
    "coerce_spacing",
    "densify",
    "fit_to",
    "jitter",
    "layer",
    "mirror_axis",
    "offset_path",
    "radial_repeat",
    "resample",
    "resample_path",
    "samples_for_turns",
    "symmetry_group",
    "tile",
]
