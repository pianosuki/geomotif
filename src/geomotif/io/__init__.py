"""Getting designs out of Python, and back in again.

Five things can be written, and they answer five different questions:

===========================  ===================================  ============
What                         Written by                           Reads back
===========================  ===================================  ============
The coordinates              :func:`save_points`                  --
The design, strokes and all  :func:`save_design`                  JSON only
The recipe that made it      :func:`save_spec`                    yes
A picture of it              :func:`save_svg`, :func:`save_dxf`   --
A moving picture of it       :func:`save_gif`                     --
===========================  ===================================  ============

A spec is the one worth reaching for by default: it is a few hundred bytes
rather than a few hundred kilobytes, it survives a change of point count, and
it is what the gallery manifest and the CLI's ``--spec`` flag are built on.

SVG is for anything that displays -- a browser, a vector editor, these docs --
and DXF for anything that cuts, mills or plots. The two disagree about which
way y points, which each module handles rather than leaving to the caller.
GIF is the odd one out and the only raster format here: it is what an
animation from :mod:`geomotif.animate` is written as, since a moving picture
has no vector form that plays everywhere.

Every writer here is pure standard library, so the zero-dependency core stays
zero-dependency all the way out to the file -- LZW compression, colour tables
and all.
"""

from .dxf import save_dxf, to_dxf
from .gif import save_gif, to_gif
from .points import PointFormat, load_design, save_design, save_points
from .raster import Raster, rasterize
from .spec import from_spec, load_spec, save_spec, to_spec
from .svg import save_svg, to_svg

__all__ = [
    "PointFormat",
    "Raster",
    "from_spec",
    "load_design",
    "load_spec",
    "rasterize",
    "save_design",
    "save_dxf",
    "save_gif",
    "save_points",
    "save_spec",
    "save_svg",
    "to_dxf",
    "to_gif",
    "to_spec",
    "to_svg",
]
