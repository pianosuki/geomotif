"""The motif contract: the one thing you implement to extend the library.

A motif is a parameterized recipe for geometry. Implement :meth:`Motif.build`
-- usually a few lines of maths -- and arc-length resampling, every spacing
curve, the transform layer, export and CLI exposure all come with it.

Two entry points, deliberately separated:

* :meth:`Motif.build` -- the motif's own idea of itself, at its native
  resolution. This is what you write.
* :meth:`Motif.generate` -- what you actually plot: a specific number of
  points, distributed the way you asked. This is what you call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from .sampling import resample

if TYPE_CHECKING:
    from .sampling import Placement
    from .spacing import SpacingLike
    from .types import Design

__all__ = ["Distribution", "Motif", "SupportsBuild"]

#: How a total point count is spread across a design's paths.
type Distribution = Literal["length", "even", "per_path"]


@runtime_checkable
class SupportsBuild(Protocol):
    """Structural contract -- any object with ``build()`` works everywhere.

    Following the :class:`typing.SupportsInt` convention, this is the
    structural twin of :class:`Motif`: anything that can build a design is
    accepted wherever a motif is, so nobody is ever *forced* to inherit.
    """

    def build(self) -> Design: ...


class Motif(ABC):
    """Convenience base: implement :meth:`build`, inherit everything else.

    The ABC exists to hand you :meth:`generate` and registration, not to
    police the type -- see :class:`SupportsBuild` if you would rather not
    inherit at all.
    """

    @abstractmethod
    def build(self) -> Design:
        """Return the design at its natural/native resolution."""

    def generate(
        self,
        count: int | None = None,
        *,
        step: float | None = None,
        spacing: SpacingLike | None = None,
        distribute: Distribution = "length",
        by: Placement = "length",
    ) -> Design:
        """Build, then resample to ``count`` points (or a fixed ``step`` distance).

        Parameters
        ----------
        count : int, optional
            Total number of points to return. Must be >= 2.
        step : float, optional
            Fixed real distance between consecutive points, letting the count
            fall out of the geometry. Mutually exclusive with ``count``.
        spacing : SpacingCurve or callable, optional
            Distribution of points along the path. Defaults to equal spacing.
        distribute : {"length", "even", "per_path"}, optional
            How ``count`` is split across a multi-path design.
        by : {"length", "parameter"}, optional
            Place points by real distance along the curve (the default), or
            by even steps through its parametrization.

        Returns
        -------
        Design
            The resampled design, ready to plot or export.
        """
        return resample(
            self.build(),
            count,
            step=step,
            spacing=spacing,
            distribute=distribute,
            by=by,
        )
