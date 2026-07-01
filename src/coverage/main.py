from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from coverage.config import Settings
from coverage.data.loader import build_kdtrees, load_parquet
from coverage.logging_config import configure_logging
from coverage.middleware import RequestIdMiddleware
from coverage.router import router

_settings = Settings()
configure_logging(_settings.log_format)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    df = load_parquet(_settings.data_path)
    app.state.settings = _settings
    app.state.trees = build_kdtrees(df)
    app.state.antennas_loaded = len(df)
    yield


app = FastAPI(title="mobile-coverage-api", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
