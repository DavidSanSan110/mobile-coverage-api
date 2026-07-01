from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mobile_coverage.config import Settings
from mobile_coverage.data.loader import build_kdtrees, load_parquet
from mobile_coverage.logging_config import configure_logging
from mobile_coverage.middleware import RequestIdMiddleware
from mobile_coverage.router import router

_settings = Settings()
configure_logging(_settings.log_format)

_FRONTEND_DIST = Path("frontend/dist")


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

# Serve the Vue SPA when the built dist exists.
# Absent in local dev (use Vite's dev server instead); present in Docker.
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
