"""Getting designs out of Python, and back in again.

Five things can be written, and they answer five different questions:

==========================  ====================================  ===========
What                        Written by                            Reads back
==========================  ====================================  ===========
The coordinates             :func:`save_points`                   --
The design, strokes and all :func:`save_design`                   JSON only
The recipe that made it     :func:`save_spec`                     yes
A picture of it             :func:`save_svg`, :func:`save_dxf`    --
A still picture of it       :func:`save_png`, :func:`save_jpeg` --
A moving picture of it      :func:`save_gif`                      --
==========================  ====================================  ===========

A spec is the one worth reaching for by default: it is a few hundred bytes
rather than a few hundred kilobytes, it survives a change of point count, and
it is what the gallery manifest and the CLI's ``--spec`` flag are built on.

SVG is for anything that displays -- a browser, a vector editor, these docs --
and DXF for anything that cuts, mills or plots. The two disagree about which
way y points, which each module handles rather than leaving to the caller.
The two rasters are the still and the moving picture: :func:`save_png` and
:func:`save_jpeg` write the finished design as one frame (a PNG lossless, a
JPEG lossy and smaller), and :func:`save_gif` writes the animation from
:mod:`geomotif.animate`, since a moving picture has no vector form that plays
everywhere.

:mod:`geomotif.io.plotter` is the SVG writer again with a pen plotter in mind:
real millimeters on a named sheet of paper, and a pass that joins strokes up
and orders them so the pen wastes less time in the air.

Every writer here is pure standard library, so the zero-dependency core stays
zero-dependency all the way out to the file -- LZW and zlib compression,
color tables, chunk CRCs and all.
"""

from .dxf import save_dxf, to_dxf
from .gif import save_gif, to_gif
from .jpeg import save_jpeg, to_jpeg
from .plotter import save_plotter_svg, to_plotter_svg, to_vpype
from .png import save_png, to_png
from .points import PointFormat, load_design, save_design, save_points
from .raster import Raster, colors_in, colours_in, quantize, rasterize, rasterize_rgba
from .spec import from_spec, load_spec, save_spec, to_spec
from .svg import save_svg, to_svg

__all__ = [
    "PointFormat",
    "Raster",
    "colors_in",
    "colours_in",
    "from_spec",
    "load_design",
    "load_spec",
    "quantize",
    "rasterize",
    "rasterize_rgba",
    "save_design",
    "save_dxf",
    "save_gif",
    "save_jpeg",
    "save_plotter_svg",
    "save_png",
    "save_points",
    "save_spec",
    "save_svg",
    "to_dxf",
    "to_gif",
    "to_jpeg",
    "to_plotter_svg",
    "to_png",
    "to_spec",
    "to_svg",
    "to_vpype",
]
