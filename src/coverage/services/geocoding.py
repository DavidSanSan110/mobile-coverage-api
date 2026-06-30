"""Async geocoding client wrapping api-adresse.data.gouv.fr."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class GeoPoint:
    """Lambert93 coordinates returned by the geocoding API."""

    x: float
    y: float


class AddressNotFoundError(Exception):
    """Raised when geocoding returns no results or a score below threshold."""


class GeocodingServiceError(Exception):
    """Raised when the upstream geocoding API returns a 4xx/5xx response."""


async def geocode_address(
    client: httpx.AsyncClient,
    address: str,
    *,
    geocoding_url: str,
    score_threshold: float,
) -> GeoPoint:
    """Geocode a single French address and return Lambert93 coordinates.

    Raises:
        GeocodingServiceError: upstream returned 429 or 503.
        AddressNotFoundError: no results or confidence score below threshold.
        httpx.TimeoutException: request timed out.
    """
    response = await client.get(geocoding_url, params={"q": address, "limit": 1})

    if response.status_code in (429, 503):
        raise GeocodingServiceError(f"Geocoding service returned HTTP {response.status_code}")
    response.raise_for_status()

    features: list[dict[str, object]] = response.json().get("features", [])
    if not features:
        raise AddressNotFoundError(f"No results for address: {address!r}")

    props = features[0]["properties"]
    assert isinstance(props, dict)
    score = float(props["score"])

    if score < score_threshold:
        raise AddressNotFoundError(
            f"Low confidence {score:.2f} < {score_threshold} for address: {address!r}"
        )

    return GeoPoint(x=float(props["x"]), y=float(props["y"]))


async def geocode_batch(
    addresses: dict[str, str],
    *,
    geocoding_url: str,
    score_threshold: float,
    timeout: float,
) -> dict[str, GeoPoint | BaseException]:
    """Geocode multiple addresses concurrently using asyncio.gather.

    Returns a dict mapping each ID to either a GeoPoint (success) or an
    exception (failure). Never raises — all failures are captured so that
    one bad address does not discard results for the others.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        tasks = [
            geocode_address(
                client,
                address,
                geocoding_url=geocoding_url,
                score_threshold=score_threshold,
            )
            for address in addresses.values()
        ]
        raw: list[GeoPoint | BaseException] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

    return dict(zip(addresses.keys(), raw, strict=True))
