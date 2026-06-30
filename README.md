# mobile-coverage-api

A REST API that accepts French addresses and returns mobile network coverage
(2G / 3G / 4G) for all four major operators: Orange, SFR, Bouygues, and Free Mobile.

## Quick start

### Prerequisites

- [uv](https://docs.astral.sh/uv/) >= 0.4
- Docker + Docker Compose (optional, for containerised runs)

### Run locally

```bash
# Install all dependencies and create .venv
make install

# Activate the virtual environment
source .venv/bin/activate        # Linux / Mac
.venv\Scripts\Activate.ps1       # Windows PowerShell

# Download antenna data and build the processed parquet file
make preprocess

# Start the development server (auto-reload enabled)
make dev
```

The API is available at <http://localhost:8000>.  
Interactive docs: <http://localhost:8000/docs>

### Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

## API

### `POST /coverage`

Accepts a JSON object mapping arbitrary IDs to French address strings.
Returns coverage per address per operator.

```bash
curl -X POST http://localhost:8000/coverage \
  -H "Content-Type: application/json" \
  -d '{"id1": "157 boulevard Mac Donald 75019 Paris"}'
```

Response:

```json
{
  "id1": {
    "orange":   { "2G": true,  "3G": true,  "4G": false },
    "sfr":      { "2G": true,  "3G": false, "4G": false },
    "bouygues": { "2G": true,  "3G": true,  "4G": true  },
    "free":     { "2G": false, "3G": true,  "4G": true  }
  }
}
```

Partial failures (one address cannot be geocoded) return HTTP 200 with a
per-address `{"error": "..."}` object. If every address fails, the response
is HTTP 503.

### `GET /health`

```json
{ "status": "ok", "antennas_loaded": 77503 }
```

## Development

```bash
make install     # create .venv and install all deps
make dev         # run dev server with auto-reload
make test        # run pytest with coverage report
make lint        # ruff check
make format      # ruff format + ruff check --fix
make typecheck   # mypy strict
make check       # run all pre-commit hooks against every file
```

## Configuration

All values are overridable via environment variable or `.env` file.
See [.env.example](.env.example) for the full list.

| Variable | Default | Description |
|---|---|---|
| `GEOCODING_API_URL` | `https://api-adresse.data.gouv.fr/search/` | Geocoding endpoint |
| `GEOCODING_TIMEOUT_SECONDS` | `10.0` | Per-address timeout (seconds) |
| `GEOCODING_SCORE_THRESHOLD` | `0.4` | Minimum geocoding confidence score |
| `MAX_ADDRESSES_PER_REQUEST` | `50` | Batch size limit (HTTP 422 if exceeded) |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `LOG_FORMAT` | `console` | `console` (dev) or `json` (production) |
| `DATA_PATH` | `data/processed/antennas.parquet` | Path to processed antenna data |