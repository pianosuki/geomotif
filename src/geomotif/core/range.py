"""Concise min/max/step metadata for a motif parameter.

A parameter's range used to be guessed -- in :mod:`geomotif.explore` and in
the web explorer -- from its default alone, because a dataclass field carried
no other bound. ``Range`` lets a motif declare the bound next to the default,
in the same line, and have every consumer read it from the same place::

    from dataclasses import dataclass, field

    from geomotif import Range

    @dataclass(frozen=True, slots=True)
    class Rose:
        n: int = field(default=5, metadata=Range(1, 50, step=1))

``Range`` is a mapping (``min``, ``max``, ``step`` are its keys) so it slots
straight into :func:`dataclasses.field`'s ``metadata=`` argument, which is how
``help`` text is already plumbed. A field that carries one carries both; the
keys are additive, and a parameter without a ``Range`` still falls back to the
heuristic, so curation is incremental.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

__all__ = ["Range"]


@dataclass(frozen=True, slots=True)
class Range(Mapping[str, float | None]):
    """A min/max/step bound for a parameter, as a field-metadata mapping.

    Parameters
    ----------
    min : float, optional
        Smallest sensible value, inclusive.
    max : float, optional
        Largest sensible value, inclusive.
    step : float, optional
        Granularity for an integer or quantized parameter. ``None`` means any
        value in the range is meaningful, which is the case for most floats.

    Any of the three may be ``None`` to leave that bound unset; a consumer
    then falls back to its own heuristic for the missing axis. The common
    case is to set all three, and the commonest still is ``Range(lo, hi,
    step=1)`` for an integer count.

    Examples
    --------
    >>> from dataclasses import field
    >>> field(default=5, metadata=Range(1, 50, step=1)).metadata.get("min")
    1
    """

    min: float | None = None
    max: float | None = None
    step: float | None = None

    def __getitem__(self, key: str) -> float | None:
        match key:
            case "min":
                return self.min
            case "max":
                return self.max
            case "step":
                return self.step
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(("min", "max", "step"))

    def __len__(self) -> int:
        return 3
