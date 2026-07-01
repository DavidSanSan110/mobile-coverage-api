from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_path: Path = Path("data/processed/antennas.parquet")
    geocoding_api_url: str = "https://api-adresse.data.gouv.fr/search/"
    geocoding_score_threshold: float = Field(default=0.4, ge=0.0, le=1.0)
    geocoding_timeout_seconds: float = Field(default=10.0, gt=0)
    max_addresses_per_request: int = Field(default=50, gt=0, le=500)
    cors_origins: list[str] = Field(default=["http://localhost:5173"])
    log_format: Literal["console", "json"] = "console"
