"""Minimal example: generate a spiral design and export the coordinates.

Run with the package installed (``pip install -e .`` from the repo root).
"""

from geomotif import PowerSpacing, save_points
from geomotif.motifs import SpiralBetween

# 16 points spiraling in toward the origin, gaps easing gradually wider.
spiral = SpiralBetween(start=(200, 0), end=(20, 0), turns=1)
design = spiral.generate(16, spacing=PowerSpacing(1.4))

for i, (x, y) in enumerate(design, start=1):
    print(f"point {i:2d}: x={x:7.1f}  y={y:7.1f}")

# Export for use in other tools; precision=0 writes whole integers.
save_points(design, "points.csv", precision=1)
save_points(design, "points.txt", precision=0)
print("wrote points.csv and points.txt")
