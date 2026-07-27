"""The motif catalogue.

Motifs are imported from their family modules rather than from the top-level
package: there will eventually be well over a hundred of them, and a flat
namespace that large is unusable. Import what you need::

    from geomotif.motifs import SpiralBetween
    from geomotif.motifs.spirals import SpiralBetween

or construct one by name through :mod:`geomotif.core.registry`.
"""

from .spirals import SpiralBetween

__all__ = ["SpiralBetween"]
