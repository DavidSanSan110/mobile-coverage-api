"""Download the ARCEP antenna CSV and produce data/processed/antennas.parquet."""

from __future__ import annotations

import warnings
from pathlib import Path

import httpx
import polars as pl

CSV_URL = "https://data.arcep.fr/mobile/sites/2018_T1/Metropole/2018_T1_sites_Metropole.csv"
RAW_PATH = Path("data/raw/2018_T1_sites_Metropole.csv")
OUTPUT_PATH = Path("data/processed/antennas.parquet")

# MCC-MNC codes confirmed from the actual CSV.
# 20813 (SFR) is not present in this dataset but is safe to include.
OPERATOR_MAP: dict[str, str] = {
    "20801": "orange",
    "20810": "sfr",
    "20813": "sfr",
    "20815": "free",
    "20820": "bouygues",
}


def download_csv(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in response.iter_bytes():
                fh.write(chunk)
    size_mb = dest.stat().st_size / 1_048_576
    print(f"Downloaded {size_mb:.1f} MB -> {dest}")


def transform(df: pl.DataFrame) -> pl.DataFrame:
    """Map operator codes to names, warn on unknowns, normalise columns and types."""
    known_codes = set(OPERATOR_MAP)
    found_codes = set(df["Operateur"].cast(pl.String).unique().to_list())
    for code in sorted(found_codes - known_codes):
        warnings.warn(f"Unknown operator code: {code}", UserWarning, stacklevel=2)

    return (
        df.with_columns(
            pl.col("Operateur")
            .cast(pl.String)
            .replace_strict(
                old=list(OPERATOR_MAP.keys()),
                new=list(OPERATOR_MAP.values()),
                default=None,
            )
            .alias("operator")
        )
        .filter(pl.col("operator").is_not_null())
        .rename({"X": "x", "Y": "y", "2G": "g2", "3G": "g3", "4G": "g4"})
        .select(["operator", "x", "y", "g2", "g3", "g4"])
        .with_columns(
            pl.col("x").str.replace(",", ".").cast(pl.Float64),
            pl.col("y").str.replace(",", ".").cast(pl.Float64),
            pl.col("g2").cast(pl.Int8),
            pl.col("g3").cast(pl.Int8),
            pl.col("g4").cast(pl.Int8),
        )
    )


# X and Y use French decimal notation (comma) in parts of the file,
# so they are read as String and normalised in transform().
_CSV_SCHEMA: dict[str, type[pl.DataType]] = {
    "Operateur": pl.String,
    "X": pl.String,
    "Y": pl.String,
    "2G": pl.Int8,
    "3G": pl.Int8,
    "4G": pl.Int8,
}


def build_parquet(raw_path: Path, output_path: Path) -> None:
    df = pl.read_csv(raw_path, separator=";", schema_overrides=_CSV_SCHEMA)
    result = transform(df)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.write_parquet(output_path)
    print(f"Wrote {len(result):,} antenna records -> {output_path}")


def main() -> None:
    if not RAW_PATH.exists():
        print(f"Downloading CSV from {CSV_URL} ...")
        download_csv(CSV_URL, RAW_PATH)
    else:
        print(f"Using cached CSV at {RAW_PATH}")
    build_parquet(RAW_PATH, OUTPUT_PATH)


if __name__ == "__main__":
    main()
