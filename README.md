# mobile-coverage-api

[![CI](https://github.com/DavidSanSan110/mobile-coverage-api/actions/workflows/ci.yml/badge.svg)](https://github.com/DavidSanSan110/mobile-coverage-api/actions/workflows/ci.yml)

A REST API that accepts French addresses and returns 2G / 3G / 4G mobile coverage for Orange, SFR, Bouygues, and Free Mobile. Includes a Vue 3 frontend, structured JSON logging, a Locust load-test suite, and a fully automated CI/CD pipeline.

**Live demo:** [https://coverage-api.ddns.net](https://coverage-api.ddns.net)

---

## Quick start

### Simplest path — Docker

```bash
git clone https://github.com/DavidSanSan110/mobile-coverage-api.git
cd mobile-coverage-api
make install
make run-docker
```

Visit [http://localhost:8000](http://localhost:8000).

### Local dev (hot-reload on both API and frontend)

```bash
make install
make run-local   # backgrounds API on :8000, starts Vite on :5173
```

Visit [http://localhost:5173](http://localhost:5173). The Vite dev server proxies API calls to the backend so both sides hot-reload independently.

> **Windows:** `make run-local` requires Git Bash or WSL. In PowerShell run `make dev-api` and `make dev-frontend` in two separate terminals instead.

### From scratch (no pre-built parquet)

The processed antenna file is committed to the repo so reviewers can run the API immediately. If you want to rebuild it from the original ARCEP data:

```bash
make install
make preprocess   # downloads CSV (~2.9 MB) and builds data/processed/antennas.parquet
make run-local
```

---

## Makefile reference

| Target | What it does |
|---|---|
| `make install` | Create `.venv`, install all Python and Node dependencies |
| `make run-local` | Start API on `:8000` + Vite on `:5173` (backgrounds API) |
| `make run-docker` | Copy `.env.example` → `.env` if missing, then `docker compose up --build` |
| `make dev-api` | Backend only, auto-reload |
| `make dev-frontend` | Frontend Vite dev server only |
| `make test` | Run pytest with branch coverage report |
| `make lint` | `ruff check` |
| `make format` | `ruff format` + `ruff check --fix` |
| `make typecheck` | `mypy` strict |
| `make check` | Run all pre-commit hooks against every file |
| `make preprocess` | Download antenna CSV and rebuild the parquet |
| `make clean` | Remove `.venv`, caches, coverage artefacts |

---

## API

### `POST /coverage`

Accepts a JSON object mapping arbitrary string keys to French address strings. Returns coverage per address per operator.

```bash
curl -X POST https://coverage-api.ddns.net/coverage \
  -H "Content-Type: application/json" \
  -d '{
    "home":   "157 boulevard MacDonald 75019 Paris",
    "office": "10 rue de Rivoli 75001 Paris"
  }'
```

Response:

```json
{
  "home": {
    "orange":   { "2G": true,  "3G": true, "4G": true  },
    "sfr":      { "2G": true,  "3G": true, "4G": true  },
    "bouygues": { "2G": true,  "3G": true, "4G": true  },
    "free":     { "2G": false, "3G": true, "4G": true  }
  },
  "office": {
    "orange":   { "2G": true,  "3G": true, "4G": true  },
    "sfr":      { "2G": true,  "3G": true, "4G": true  },
    "bouygues": { "2G": true,  "3G": true, "4G": true  },
    "free":     { "2G": false, "3G": true, "4G": true  }
  }
}
```

**Batch size limit:** 50 addresses per request (configurable). Exceeding it returns HTTP 422.

**Error handling:**

| Scenario | HTTP status | Response shape |
|---|---|---|
| All addresses geocoded successfully | 200 | `{ id: OperatorCoverage }` |
| Some addresses fail geocoding | 200 | Mixed — successful IDs return coverage, failed IDs return `{ "error": "address_not_found" }` |
| All addresses fail geocoding | 503 | `{ "detail": "geocoding service unavailable" }` |
| Batch exceeds limit | 422 | `{ "detail": "Too many addresses: ..." }` |

Error values: `address_not_found`, `geocoding_timeout`, `geocoding_error`.

### `GET /health`

```bash
curl https://coverage-api.ddns.net/health
```

```json
{ "status": "ok", "antennas_loaded": 77504 }
```

`antennas_loaded` is the number of antenna rows loaded from the parquet file at startup. A value of 0 or a non-200 response indicates a data loading failure.

---

## Configuration

All values are overridable via environment variable or `.env` file. See [.env.example](.env.example) for the full list with descriptions.

| Variable | Default | Description |
|---|---|---|
| `DATA_PATH` | `data/processed/antennas.parquet` | Path to the processed antenna parquet |
| `GEOCODING_API_URL` | `https://api-adresse.data.gouv.fr/search/` | Geocoding endpoint |
| `GEOCODING_TIMEOUT_SECONDS` | `10.0` | Per-address HTTP timeout |
| `GEOCODING_SCORE_THRESHOLD` | `0.4` | Minimum geocoding confidence (0.0–1.0) |
| `MAX_ADDRESSES_PER_REQUEST` | `50` | Batch size cap (HTTP 422 if exceeded) |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `LOG_FORMAT` | `console` | `console` for dev, `json` for production |

---

## Architecture and design decisions

### Lambert93 comes directly from the geocoding API — no coordinate conversion needed

The assignment appendix suggests using `pyproj` to convert WGS84 coordinates returned by the geocoding API into Lambert93 to match the antenna CSV. In practice, the API already returns Lambert93 `x` / `y` in its response properties:

```json
{ "properties": { "label": "...", "x": 654412.35, "y": 6866689.51, "score": 0.82 } }
```

This was discovered by calling the API directly — not assumed from documentation. Lambert93 is a conformal projection used by French public datasets. Distances up to 30 km have negligible distortion, so Euclidean arithmetic in metres is sufficient for coverage checks. No `pyproj`, no coordinate transformation, no dependency.

### Per-combination KDTree — O(log n) spatial queries, zero infrastructure

The antenna dataset has ~77 000 rows. For each coverage query the question is: *is there an antenna of operator X and technology Y within radius R of point (x, y)?*

The naive approach (iterate all 77 000 rows per query) is O(n). With 50 addresses × 4 operators × 3 technologies that is 600 brute-force scans per request. `scipy.spatial.cKDTree` answers radius queries in O(log n) — it is a k-d tree built from the antenna coordinates, implemented in C.

One tree is built per `(operator, technology)` combination, not one global tree. This lets each query use the exact radius for that technology (2G = 30 km, 3G = 5 km, 4G = 10 km). A single global tree would require using the largest radius (30 km) for every query, returning far more candidates than needed and requiring a Python-level filter. The 11 per-combination trees are tighter, faster, and simpler.

There are 11 trees, not 12. Free Mobile has zero 2G antennas — they launched in 2012, after 2G was already mature, and built a 3G/4G-only network. A missing key in the tree dictionary means no coverage for that combination; no special-casing needed.

Memory cost: 11 trees × ~7 000 antennas each × 2 coordinates × 8 bytes ≈ 12 MB total. The trees are built once at startup and held in `app.state` for the lifetime of the process.

### Concurrent geocoding with `asyncio.gather`

Every address in a batch requires one HTTP call to `api-adresse.data.gouv.fr`. If these were made sequentially, a batch of 20 addresses would take 20× the latency of a single geocoding call (~120 seconds at ~6 s per call).

`asyncio.gather` fires all geocoding coroutines concurrently. The batch latency equals the latency of the slowest individual call, not the sum. The Locust load test confirms this: a batch of 5 addresses has a median latency of 6.1 s vs. 5.9 s for a single address.

`return_exceptions=True` is critical. Without it, a single geocoding failure cancels all other in-flight requests and raises immediately. With it, failures are returned as exception objects alongside successful results. The route handler inspects each result: exceptions become per-address `{"error": "..."}` objects, successful results become coverage grids. A single bad address does not destroy the response for the rest of the batch.

### Partial vs total failure — HTTP 200 vs HTTP 503

If some addresses fail geocoding but others succeed, the response is HTTP 200 with a mixed body. The client can inspect each result individually. Returning 4xx or 5xx because one address was unresolvable would break callers who sent 49 valid addresses alongside 1 bad one.

If every address fails — which typically means the geocoding API itself is unavailable — the response is HTTP 503. This distinguishes an infrastructure problem (retriable, should alert) from a bad-input problem. HTTP 200 with an all-errors body would mislead monitoring systems and retry logic.

### Data loaded once at startup via FastAPI lifespan

The parquet file is read and the KDTrees are built during the FastAPI `lifespan` context manager, before the first request is served. The result is stored in `app.state`. Every route handler reads from `request.app.state.trees` — the data is in memory, no disk I/O per request.

The `GET /health` endpoint exposes `antennas_loaded` — the row count from the parquet file. This makes data loading failures immediately visible to any deployment healthcheck without having to send a real coverage request. If the parquet file is missing or corrupt, the health endpoint returns a non-200 or reports `antennas_loaded: 0`, and the CI deploy step fails before traffic is rerouted.

### Structured logging with request-level correlation

Every log line is a JSON object in production (`LOG_FORMAT=json`). Each request is tagged with a short UUID injected by middleware, so all log lines for a single request share the same `request_id` and can be correlated in any log aggregation system.

Two events are logged per request:

- `geocoding_complete` — once per address, with `status` (`found` / `not_found` / `timeout` / `error`)
- `request_complete` — once per request, with `addresses_count`, `errors_count`, `geocoding_latency_ms`, `total_latency_ms`

This makes error-rate monitoring a direct query: `count(status="not_found") / count(event="geocoding_complete")`. No regex parsing of free-text strings.

### No database

The antenna data is static, read-only, and fits entirely in memory (~12 MB for the KDTrees). A database would add network round-trips, connection pool management, schema migrations, and operational overhead for zero benefit. The correct time to add a database is when the data needs real-time updates or grows beyond available memory — neither applies here.

---

## What I would do differently in production

**Geocoding result cache.** The same address is likely to be queried repeatedly. A Redis cache keyed on the normalised address string with a 24-hour TTL would eliminate redundant geocoding API calls, cut latency to microseconds for repeated queries, and make the application resilient to geocoding API outages for known addresses.

**Rate limiting on the geocoding API.** The current implementation fires up to 50 concurrent requests per batch. Under heavy load this could trigger rate limiting from `api-adresse.data.gouv.fr`. A semaphore limiting concurrent geocoding calls (e.g. `asyncio.Semaphore(10)`) plus exponential back-off on 429 responses would make the application a better citizen.

**API authentication.** The endpoint is currently open. A real deployment would require at minimum an API key validated against a token store, with per-key rate limits to prevent abuse.

**Antenna data refresh pipeline.** ARCEP publishes updated antenna data quarterly. An automated pipeline that downloads the latest CSV, rebuilds the parquet, and triggers a rolling restart would keep coverage data current without manual intervention.

**Horizontal scaling.** The application is stateless after startup — all per-request state lives in local variables, not shared memory. Multiple instances behind a load balancer would work correctly. The only consideration is startup time (parquet load + KDTree build takes ~1 second), which is negligible for rolling deployments.

---

## Deployment

The application deploys automatically on every push to `main` after CI passes. The deploy workflow runs on a self-hosted GitHub Actions runner on the Oracle server.

### Required GitHub secret

| Secret | Value |
|---|---|
| `APP_ENV` | Full contents of the production `.env` file |

Example value for `APP_ENV`:

```
DATA_PATH=data/processed/antennas.parquet
LOG_FORMAT=json
CORS_ORIGINS=["https://coverage-api.ddns.net"]
GEOCODING_TIMEOUT_SECONDS=10.0
```

> **Important:** the secret is written to disk via `printf '%s' "$APP_ENV" > .env`. Direct `echo "${{ secrets.APP_ENV }}"` will corrupt JSON values like `CORS_ORIGINS` due to shell quote expansion.

### Stack

The production stack uses Caddy as a TLS-terminating reverse proxy in front of FastAPI. Caddy provisions and auto-renews the Let's Encrypt certificate — no manual cert management.

```
Client → Caddy:443 (HTTPS) → coverage-api:8000 (HTTP, internal)
```

Required open ports on the server: **80** (ACME HTTP-01 challenge) and **443** (HTTPS). Port 8000 should not be exposed publicly.
