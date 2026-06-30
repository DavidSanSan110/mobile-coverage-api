"""Coverage query logic using per-combination KDTrees."""

from scipy.spatial import cKDTree

from coverage.data.loader import Trees

RADII: dict[str, int] = {
    "2G": 30_000,
    "3G": 5_000,
    "4G": 10_000,
}


def is_covered(tree: cKDTree | None, x: float, y: float, radius: int) -> bool:
    """Return True if (x, y) is within radius metres of any antenna in tree."""
    if tree is None:
        return False
    return bool(tree.query_ball_point([x, y], radius))


def get_coverage(trees: Trees, operator: str, tech: str, x: float, y: float) -> bool:
    """Return True if the given operator/technology covers the point (x, y)."""
    return is_covered(trees.get((operator, tech)), x, y, RADII[tech])
