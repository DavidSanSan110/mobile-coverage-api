import polars as pl
import pytest
from scipy.spatial import cKDTree

from coverage.data.loader import OPERATORS, TECH_COLS, Trees, build_kdtrees
from coverage.services.coverage import RADII, get_coverage, is_covered


@pytest.fixture
def single_tree() -> cKDTree:
    """One antenna at the origin."""
    return cKDTree([[0.0, 0.0]])


@pytest.fixture
def small_df() -> pl.DataFrame:
    """Minimal parquet-like DataFrame with known antenna positions."""
    return pl.DataFrame(
        {
            "operator": ["orange", "sfr", "bouygues", "free", "free", "free"],
            "x": [0.0, 1000.0, 2000.0, 3000.0, 3000.0, 3000.0],
            "y": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "g2": pl.Series([1, 1, 1, 0, 0, 0], dtype=pl.Int8),
            "g3": pl.Series([1, 1, 1, 1, 1, 1], dtype=pl.Int8),
            "g4": pl.Series([1, 1, 1, 0, 1, 1], dtype=pl.Int8),
        }
    )


@pytest.fixture
def built_trees(small_df: pl.DataFrame) -> Trees:
    return build_kdtrees(small_df)


class TestRadiiConstants:
    def test_2g_radius_is_30km(self) -> None:
        assert RADII["2G"] == 30_000

    def test_3g_radius_is_5km(self) -> None:
        assert RADII["3G"] == 5_000

    def test_4g_radius_is_10km(self) -> None:
        assert RADII["4G"] == 10_000


class TestIsCovered:
    def test_point_well_inside_radius_is_covered(self, single_tree: cKDTree) -> None:
        assert is_covered(single_tree, x=5_000.0, y=0.0, radius=10_000) is True

    def test_point_well_outside_radius_is_not_covered(self, single_tree: cKDTree) -> None:
        assert is_covered(single_tree, x=10_001.0, y=0.0, radius=10_000) is False

    def test_point_at_exact_boundary_is_covered(self, single_tree: cKDTree) -> None:
        # query_ball_point uses <= r (inclusive boundary)
        assert is_covered(single_tree, x=10_000.0, y=0.0, radius=10_000) is True

    def test_none_tree_is_never_covered(self) -> None:
        assert is_covered(None, x=0.0, y=0.0, radius=10_000) is False

    def test_2g_radius_covers_25km(self, single_tree: cKDTree) -> None:
        assert is_covered(single_tree, x=25_000.0, y=0.0, radius=RADII["2G"]) is True

    def test_2g_radius_does_not_cover_30001m(self, single_tree: cKDTree) -> None:
        assert is_covered(single_tree, x=30_001.0, y=0.0, radius=RADII["2G"]) is False

    def test_3g_radius_covers_4999m(self, single_tree: cKDTree) -> None:
        assert is_covered(single_tree, x=4_999.0, y=0.0, radius=RADII["3G"]) is True

    def test_3g_radius_does_not_cover_5001m(self, single_tree: cKDTree) -> None:
        assert is_covered(single_tree, x=5_001.0, y=0.0, radius=RADII["3G"]) is False


class TestBuildKdtrees:
    def test_free_2g_tree_is_absent(self, built_trees: Trees) -> None:
        # Free Mobile has zero 2G antennas in the dataset
        assert ("free", "2G") not in built_trees

    def test_known_operator_tech_pairs_have_trees(self, built_trees: Trees) -> None:
        assert ("orange", "2G") in built_trees
        assert ("orange", "3G") in built_trees
        assert ("orange", "4G") in built_trees

    def test_trees_contain_correct_antenna_count(self, built_trees: Trees) -> None:
        # orange has one antenna with 2G=1 in small_df
        assert built_trees[("orange", "2G")].n == 1

    def test_operators_constant_covers_all_four(self) -> None:
        assert set(OPERATORS) == {"orange", "sfr", "bouygues", "free"}

    def test_tech_cols_maps_all_three_technologies(self) -> None:
        assert set(TECH_COLS.keys()) == {"2G", "3G", "4G"}


class TestGetCoverage:
    def test_covered_point_returns_true(self, built_trees: Trees) -> None:
        # orange antenna at (0, 0), querying at (5000, 0) within 4G radius
        assert get_coverage(built_trees, "orange", "4G", x=5_000.0, y=0.0) is True

    def test_uncovered_point_returns_false(self, built_trees: Trees) -> None:
        assert get_coverage(built_trees, "orange", "4G", x=50_000.0, y=0.0) is False

    def test_free_2g_always_returns_false(self, built_trees: Trees) -> None:
        # Free has no 2G tree — must return False regardless of position
        assert get_coverage(built_trees, "free", "2G", x=0.0, y=0.0) is False

    def test_2g_covers_point_outside_4g_range(self, built_trees: Trees) -> None:
        # orange antenna at (0,0): outside 4G (10km) but inside 2G (30km)
        assert get_coverage(built_trees, "orange", "4G", x=15_000.0, y=0.0) is False
        assert get_coverage(built_trees, "orange", "2G", x=15_000.0, y=0.0) is True
