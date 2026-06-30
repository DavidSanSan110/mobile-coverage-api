import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from coverage.data.loader import build_kdtrees, load_parquet


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    data_path = Path(os.getenv("DATA_PATH", "data/processed/antennas.parquet"))
    df = load_parquet(data_path)
    app.state.trees = build_kdtrees(df)
    yield


app = FastAPI(title="mobile-coverage-api", lifespan=lifespan)
