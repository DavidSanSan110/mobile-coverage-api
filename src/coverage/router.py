import httpx
from fastapi import APIRouter, HTTPException, Request

from coverage.config import Settings
from coverage.data.loader import Trees
from coverage.models import (
    AddressError,
    CoverageRequest,
    HealthResponse,
    OperatorCoverage,
    TechCoverage,
)
from coverage.services.coverage import get_coverage
from coverage.services.geocoding import AddressNotFoundError, geocode_batch

router = APIRouter()


def _classify_error(exc: BaseException) -> str:
    if isinstance(exc, AddressNotFoundError):
        return "address_not_found"
    if isinstance(exc, httpx.TimeoutException):
        return "geocoding_timeout"
    return "geocoding_error"


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

    geocoding_results = await geocode_batch(
        addresses,
        geocoding_url=settings.geocoding_api_url,
        score_threshold=settings.geocoding_score_threshold,
        timeout=settings.geocoding_timeout_seconds,
    )

    if all(isinstance(v, BaseException) for v in geocoding_results.values()):
        raise HTTPException(status_code=503, detail="geocoding service unavailable")

    output: dict[str, OperatorCoverage | AddressError] = {}
    for addr_id, result in geocoding_results.items():
        if isinstance(result, BaseException):
            output[addr_id] = AddressError(error=_classify_error(result))
        else:
            output[addr_id] = OperatorCoverage(
                orange=_tech_coverage(trees, "orange", result.x, result.y),
                sfr=_tech_coverage(trees, "sfr", result.x, result.y),
                bouygues=_tech_coverage(trees, "bouygues", result.x, result.y),
                free=_tech_coverage(trees, "free", result.x, result.y),
            )

    return output
