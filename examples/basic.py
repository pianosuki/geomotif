"""Minimal example: generate a spiral of points and export the coordinates.

Run with the package installed (``pip install -e .`` from the repo root).
"""

from geomotif import PowerSpacing, generate_spiral, save_points

# 16 points spiraling in toward the origin, gaps easing gradually wider.
points = generate_spiral(
    start=(200, 0),
    end=(20, 0),
    num_points=16,
    turns=1,
    spacing=PowerSpacing(1.4),
)

for i, (x, y) in enumerate(points, start=1):
    print(f"point {i:2d}: x={x:7.1f}  y={y:7.1f}")

# Export for use in other tools; precision=0 writes whole integers.
save_points(points, "points.csv", precision=1)
save_points(points, "points.txt", precision=0)
print("wrote points.csv and points.txt")
