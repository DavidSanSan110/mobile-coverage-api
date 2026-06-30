"""Load the processed antenna parquet and build per-combination KDTrees."""

from pathlib import Path

import polars as pl
from scipy.spatial import cKDTree

OPERATORS: tuple[str, ...] = ("orange", "sfr", "bouygues", "free")
TECH_COLS: dict[str, str] = {"2G": "g2", "3G": "g3", "4G": "g4"}

# Maps (operator, technology) -> cKDTree of antenna coordinates in Lambert93 metres.
# Combinations with zero antennas (Free 2G) are absent from the dict.
Trees = dict[tuple[str, str], cKDTree]


def load_parquet(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path)


def build_kdtrees(df: pl.DataFrame) -> Trees:
    """Build one cKDTree per (operator, technology) combination.

    Combinations with zero qualifying antennas are skipped so callers
    can use `trees.get((op, tech))` and treat None as no coverage.
    """
    trees: Trees = {}
    for operator in OPERATORS:
        op_df = df.filter(pl.col("operator") == operator)
        for tech, col in TECH_COLS.items():
            coords = op_df.filter(pl.col(col) == 1).select(["x", "y"]).to_numpy()
            if len(coords) == 0:
                continue
            trees[(operator, tech)] = cKDTree(coords)
    return trees
