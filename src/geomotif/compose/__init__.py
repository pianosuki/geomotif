"""Motifs made out of other motifs.

Everything in :mod:`geomotif.motifs` draws a shape. Everything here arranges
shapes somebody else drew: a mandala is rings of a repeated unit, a
kaleidoscope is one unit under a symmetry group, a snowflake is one arm
reflected and turned six ways.

They are motifs like any other -- they subclass :class:`~geomotif.Motif`,
they build a :class:`~geomotif.Design`, they resample and export and register
like the rest -- so a composed figure can itself be the unit of another
composition. What makes them different is only that their most interesting
parameter is another motif::

    from geomotif.compose import Mandala, Ring
    from geomotif.motifs import RegularPolygon, Rose

    Mandala(rings=(
        Ring(Rose(n=5, size=30.0), count=8, radius=60.0),
        Ring(RegularPolygon(sides=3, radius=18.0), count=16, radius=120.0),
    ))

Anything with a ``build()`` method works as that parameter, which is the
whole point of :class:`~geomotif.SupportsBuild`.

That parameter is called ``unit`` rather than ``motif`` throughout, because
``motif`` is the key :func:`~geomotif.core.registry.spec` reserves for a
design's own name in :attr:`~geomotif.Design.meta` -- a field of that name
would overwrite it and the design could not be rebuilt from its own spec.
"""

from .mandala import Kaleidoscope, LayeredRings, Mandala, Ring, Snowflake, SpokePattern

__all__ = [
    "Kaleidoscope",
    "LayeredRings",
    "Mandala",
    "Ring",
    "Snowflake",
    "SpokePattern",
]
