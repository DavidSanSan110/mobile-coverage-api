import warnings

import polars as pl
import pytest

from scripts.preprocess import OPERATOR_MAP, transform


def _raw_df(operateur: list[int] | None = None) -> pl.DataFrame:
    """Minimal DataFrame matching the real CSV schema (Operateur as Int64)."""
    ops: list[int] = operateur if operateur is not None else [20801, 20810, 20820, 20815]
    n = len(ops)
    return pl.DataFrame(
        {
            "Operateur": pl.Series(ops, dtype=pl.Int64),
            "X": pl.Series(["873749.0"] * n, dtype=pl.String),
            "Y": pl.Series(["6568847.0"] * n, dtype=pl.String),
            "2G": pl.Series([1] * n, dtype=pl.Int8),
            "3G": pl.Series([1] * n, dtype=pl.Int8),
            "4G": pl.Series([0] * n, dtype=pl.Int8),
        }
    )


class TestOperatorMap:
    def test_all_four_operators_present(self) -> None:
        assert set(OPERATOR_MAP.values()) == {"orange", "sfr", "bouygues", "free"}

    def test_known_codes_map_to_correct_names(self) -> None:
        assert OPERATOR_MAP["20801"] == "orange"
        assert OPERATOR_MAP["20810"] == "sfr"
        assert OPERATOR_MAP["20820"] == "bouygues"
        assert OPERATOR_MAP["20815"] == "free"

    def test_unknown_code_not_in_map(self) -> None:
        assert "99999" not in OPERATOR_MAP


class TestTransform:
    def test_output_columns_are_normalised(self) -> None:
        result = transform(_raw_df())
        assert result.columns == ["operator", "x", "y", "g2", "g3", "g4"]

    def test_coordinate_dtype_is_float64(self) -> None:
        result = transform(_raw_df())
        assert result["x"].dtype == pl.Float64
        assert result["y"].dtype == pl.Float64

    def test_coverage_flag_dtype_is_int8(self) -> None:
        result = transform(_raw_df())
        assert result["g2"].dtype == pl.Int8
        assert result["g3"].dtype == pl.Int8
        assert result["g4"].dtype == pl.Int8

    def test_known_operators_are_mapped_to_names(self) -> None:
        result = transform(_raw_df())
        assert set(result["operator"].to_list()) == {"orange", "sfr", "bouygues", "free"}

    def test_all_rows_preserved_when_all_operators_known(self) -> None:
        result = transform(_raw_df())
        assert len(result) == 4

    def test_unknown_operator_row_is_dropped(self) -> None:
        df = _raw_df(operateur=[20801, 99999])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = transform(df)
        assert len(result) == 1
        assert result["operator"][0] == "orange"

    def test_unknown_operator_emits_warning(self) -> None:
        df = _raw_df(operateur=[20801, 99999])
        with pytest.warns(UserWarning, match="Unknown operator code: 99999"):
            transform(df)

    def test_french_decimal_comma_is_normalised(self) -> None:
        df = pl.DataFrame(
            {
                "Operateur": pl.Series([20801], dtype=pl.Int64),
                "X": pl.Series(["887003,31"], dtype=pl.String),
                "Y": pl.Series(["6568847,50"], dtype=pl.String),
                "2G": pl.Series([1], dtype=pl.Int8),
                "3G": pl.Series([1], dtype=pl.Int8),
                "4G": pl.Series([0], dtype=pl.Int8),
            }
        )
        result = transform(df)
        assert result["x"][0] == pytest.approx(887003.31)
        assert result["y"][0] == pytest.approx(6568847.50)
