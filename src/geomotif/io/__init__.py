"""Getting designs out of Python, and back in again.

Four things can be written, and they answer four different questions:

===========================  ===================================  ============
What                         Written by                           Reads back
===========================  ===================================  ============
The coordinates              :func:`save_points`                  --
The design, strokes and all  :func:`save_design`                  JSON only
The recipe that made it      :func:`save_spec`                    yes
A picture of it              :func:`save_svg`, :func:`save_dxf`   --
===========================  ===================================  ============

A spec is the one worth reaching for by default: it is a few hundred bytes
rather than a few hundred kilobytes, it survives a change of point count, and
it is what the gallery manifest and the CLI's ``--spec`` flag are built on.

SVG is for anything that displays -- a browser, a vector editor, these docs --
and DXF for anything that cuts, mills or plots. The two disagree about which
way y points, which each module handles rather than leaving to the caller.

Every writer here is pure standard library, so the zero-dependency core stays
zero-dependency all the way out to the file.
"""

from .dxf import save_dxf, to_dxf
from .points import PointFormat, load_design, save_design, save_points
from .spec import from_spec, load_spec, save_spec, to_spec
from .svg import save_svg, to_svg

__all__ = [
    "PointFormat",
    "from_spec",
    "load_design",
    "load_spec",
    "save_design",
    "save_dxf",
    "save_points",
    "save_spec",
    "save_svg",
    "to_dxf",
    "to_spec",
    "to_svg",
]
