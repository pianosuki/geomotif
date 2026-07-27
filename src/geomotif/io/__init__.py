"""Getting designs out of Python, and back in again.

Three things can be written, and they answer three different questions:

===========================  ===================================  ============
What                         Written by                           Reads back
===========================  ===================================  ============
The coordinates              :func:`save_points`                  --
The design, strokes and all  :func:`save_design`                  JSON only
The recipe that made it      :func:`save_spec`                    yes
===========================  ===================================  ============

A spec is the one worth reaching for by default: it is a few hundred bytes
rather than a few hundred kilobytes, it survives a change of point count, and
it is what the gallery manifest and the CLI's ``--spec`` flag are built on.

Every writer here is pure standard library, so the zero-dependency core stays
zero-dependency all the way out to the file.
"""

from .points import PointFormat, load_design, save_design, save_points
from .spec import from_spec, load_spec, save_spec, to_spec

__all__ = [
    "PointFormat",
    "from_spec",
    "load_design",
    "load_spec",
    "save_design",
    "save_points",
    "save_spec",
    "to_spec",
]
