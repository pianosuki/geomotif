"""Base classes that turn a formula, a grammar or a rule into a motif.

Pick the one that matches how your design is *defined*, not what it looks
like:

============================  ==========================================
Base                          You implement
============================  ==========================================
:class:`ParametricMotif`      ``position(u) -> Point``
:class:`PolarMotif`           ``radius(theta) -> float``
:class:`MultiCurveMotif`      ``curves() -> Iterable[Curve]``
:class:`LSystemMotif`         an axiom, rewrite rules and a turn angle
:class:`SegmentMotif`         ``nodes()`` and ``edges()``
:class:`LatticeTiling`        ``cell()`` and ``basis()``
:class:`SubstitutionTiling`   ``seed()``, ``subdivide()`` and ``outline()``
============================  ==========================================

Anything that fits none of them subclasses :class:`~geomotif.Motif` directly
and writes ``build()`` by hand, which is one method. The bases are a
convenience, never a requirement.
"""

from .lsystem import LSystemMotif
from .parametric import Curve, MultiCurveMotif, ParametricMotif, PolarMotif
from .segments import SegmentMotif
from .tiling import LatticeTiling, SubstitutionTiling

__all__ = [
    "Curve",
    "LSystemMotif",
    "LatticeTiling",
    "MultiCurveMotif",
    "ParametricMotif",
    "PolarMotif",
    "SegmentMotif",
    "SubstitutionTiling",
]
