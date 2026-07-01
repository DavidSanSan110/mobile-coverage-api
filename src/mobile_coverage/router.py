import time

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request

from mobile_coverage.config import Settings
from mobile_coverage.data.loader import Trees
from mobile_coverage.models import (
    AddressError,
    CoverageRequest,
    HealthResponse,
    OperatorCoverage,
    TechCoverage,
)
from mobile_coverage.services.coverage import get_coverage
from mobile_coverage.services.geocoding import AddressNotFoundError, geocode_batch

router = APIRouter()
log = structlog.get_logger()


def _classify_error(exc: BaseException) -> str:
    if isinstance(exc, AddressNotFoundError):
        return "address_not_found"
    if isinstance(exc, httpx.TimeoutException):
        return "geocoding_timeout"
    return "geocoding_error"


def _geocoding_status(exc: BaseException) -> str:
    if isinstance(exc, AddressNotFoundError):
        return "not_found"
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    return "error"


def _tech_coverage(trees: Trees, operator: str, x: float, y: float) -> TechCoverage:
    return TechCoverage(
        g2=get_coverage(trees, operator, "2G", x, y),
        g3=get_coverage(trees, operator, "3G", x, y),
        g4=get_coverage(trees, operator, "4G", x, y),
    )


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    return HealthResponse(
        status="ok",
        antennas_loaded=request.app.state.antennas_loaded,
    )


@router.post("/coverage")
async def coverage(
    request: Request,
    body: CoverageRequest,
) -> dict[str, OperatorCoverage | AddressError]:
    settings: Settings = request.app.state.settings
    trees: Trees = request.app.state.trees
    addresses = dict(body.root)

    if len(addresses) > settings.max_addresses_per_request:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Too many addresses: {len(addresses)} exceeds "
                f"maximum of {settings.max_addresses_per_request}"
            ),
        )

    total_start = time.monotonic()
    geocoding_start = time.monotonic()
    geocoding_results = await geocode_batch(
        addresses,
        geocoding_url=settings.geocoding_api_url,
        score_threshold=settings.geocoding_score_threshold,
        timeout=settings.geocoding_timeout_seconds,
    )
    geocoding_ms = int((time.monotonic() - geocoding_start) * 1000)

    if all(isinstance(v, BaseException) for v in geocoding_results.values()):
        raise HTTPException(status_code=503, detail="geocoding service unavailable")

    errors_count = 0
    output: dict[str, OperatorCoverage | AddressError] = {}
    for addr_id, result in geocoding_results.items():
        if isinstance(result, BaseException):
            errors_count += 1
            log.info(
                "geocoding_complete",
                address_id=addr_id,
                status=_geocoding_status(result),
            )
            output[addr_id] = AddressError(error=_classify_error(result))
        else:
            log.info("geocoding_complete", address_id=addr_id, status="found")
            output[addr_id] = OperatorCoverage(
                orange=_tech_coverage(trees, "orange", result.x, result.y),
                sfr=_tech_coverage(trees, "sfr", result.x, result.y),
                bouygues=_tech_coverage(trees, "bouygues", result.x, result.y),
                free=_tech_coverage(trees, "free", result.x, result.y),
            )

    log.info(
        "request_complete",
        addresses_count=len(addresses),
        errors_count=errors_count,
        geocoding_latency_ms=geocoding_ms,
        total_latency_ms=int((time.monotonic() - total_start) * 1000),
    )

    return output
