import httpx
import pytest
import respx

from coverage.services.geocoding import (
    AddressNotFoundError,
    GeocodingServiceError,
    GeoPoint,
    geocode_address,
    geocode_batch,
)

GEOCODING_URL = "https://api-adresse.data.gouv.fr/search/"
SCORE_THRESHOLD = 0.4
TIMEOUT = 5.0


def _feature(score: float = 0.95, x: float = 654412.35, y: float = 6866689.51) -> dict[str, object]:
    return {"properties": {"score": score, "x": x, "y": y, "label": "test address"}}


def _ok(score: float = 0.95, x: float = 654412.35, y: float = 6866689.51) -> httpx.Response:
    return httpx.Response(200, json={"features": [_feature(score, x, y)]})


def _empty() -> httpx.Response:
    return httpx.Response(200, json={"features": []})


class TestGeocodeAddress:
    async def test_success_returns_geopoint_with_correct_coordinates(
        self, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_ok(x=654412.35, y=6866689.51))
        async with httpx.AsyncClient() as client:
            result = await geocode_address(
                client,
                "157 bd MacDonald 75019 Paris",
                geocoding_url=GEOCODING_URL,
                score_threshold=SCORE_THRESHOLD,
            )
        assert isinstance(result, GeoPoint)
        assert result.x == pytest.approx(654412.35)
        assert result.y == pytest.approx(6866689.51)

    async def test_score_exactly_at_threshold_is_accepted(
        self, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_ok(score=0.4))
        async with httpx.AsyncClient() as client:
            result = await geocode_address(
                client,
                "some address",
                geocoding_url=GEOCODING_URL,
                score_threshold=0.4,
            )
        assert isinstance(result, GeoPoint)

    async def test_score_below_threshold_raises_address_not_found(
        self, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_ok(score=0.39))
        async with httpx.AsyncClient() as client:
            with pytest.raises(AddressNotFoundError):
                await geocode_address(
                    client,
                    "ambiguous address",
                    geocoding_url=GEOCODING_URL,
                    score_threshold=0.4,
                )

    async def test_empty_features_raises_address_not_found(
        self, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_empty())
        async with httpx.AsyncClient() as client:
            with pytest.raises(AddressNotFoundError):
                await geocode_address(
                    client,
                    "gibberish",
                    geocoding_url=GEOCODING_URL,
                    score_threshold=SCORE_THRESHOLD,
                )

    async def test_503_raises_geocoding_service_error(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=httpx.Response(503))
        async with httpx.AsyncClient() as client:
            with pytest.raises(GeocodingServiceError):
                await geocode_address(
                    client,
                    "some address",
                    geocoding_url=GEOCODING_URL,
                    score_threshold=SCORE_THRESHOLD,
                )

    async def test_429_raises_geocoding_service_error(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=httpx.Response(429))
        async with httpx.AsyncClient() as client:
            with pytest.raises(GeocodingServiceError):
                await geocode_address(
                    client,
                    "some address",
                    geocoding_url=GEOCODING_URL,
                    score_threshold=SCORE_THRESHOLD,
                )

    async def test_timeout_propagates_as_httpx_timeout_exception(
        self, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(GEOCODING_URL).mock(side_effect=httpx.TimeoutException("timed out"))
        async with httpx.AsyncClient() as client:
            with pytest.raises(httpx.TimeoutException):
                await geocode_address(
                    client,
                    "some address",
                    geocoding_url=GEOCODING_URL,
                    score_threshold=SCORE_THRESHOLD,
                )


class TestGeocodeBatch:
    async def test_all_succeed_returns_dict_of_geopoints(
        self, respx_mock: respx.MockRouter
    ) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_ok())
        results = await geocode_batch(
            {"id1": "address one", "id2": "address two"},
            geocoding_url=GEOCODING_URL,
            score_threshold=SCORE_THRESHOLD,
            timeout=TIMEOUT,
        )
        assert len(results) == 2
        assert all(isinstance(v, GeoPoint) for v in results.values())

    async def test_result_keys_match_input_keys(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_ok())
        results = await geocode_batch(
            {"alpha": "address one", "beta": "address two"},
            geocoding_url=GEOCODING_URL,
            score_threshold=SCORE_THRESHOLD,
            timeout=TIMEOUT,
        )
        assert set(results.keys()) == {"alpha", "beta"}

    async def test_partial_failure_captures_exception_without_dropping_successes(
        self, respx_mock: respx.MockRouter
    ) -> None:
        def _respond(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("q", "")
            return _ok() if q == "good address" else _empty()

        respx_mock.get(GEOCODING_URL).mock(side_effect=_respond)
        results = await geocode_batch(
            {"good": "good address", "bad": "bad address"},
            geocoding_url=GEOCODING_URL,
            score_threshold=SCORE_THRESHOLD,
            timeout=TIMEOUT,
        )
        assert isinstance(results["good"], GeoPoint)
        assert isinstance(results["bad"], AddressNotFoundError)

    async def test_all_fail_returns_all_exceptions(self, respx_mock: respx.MockRouter) -> None:
        respx_mock.get(GEOCODING_URL).mock(return_value=_empty())
        results = await geocode_batch(
            {"id1": "bad1", "id2": "bad2"},
            geocoding_url=GEOCODING_URL,
            score_threshold=SCORE_THRESHOLD,
            timeout=TIMEOUT,
        )
        assert all(isinstance(v, Exception) for v in results.values())

    async def test_single_timeout_does_not_cancel_other_requests(
        self, respx_mock: respx.MockRouter
    ) -> None:
        def _respond(request: httpx.Request) -> httpx.Response:
            q = request.url.params.get("q", "")
            if q == "slow":
                raise httpx.TimeoutException("timed out")
            return _ok()

        respx_mock.get(GEOCODING_URL).mock(side_effect=_respond)
        results = await geocode_batch(
            {"ok": "fast address", "slow": "slow"},
            geocoding_url=GEOCODING_URL,
            score_threshold=SCORE_THRESHOLD,
            timeout=TIMEOUT,
        )
        assert isinstance(results["ok"], GeoPoint)
        assert isinstance(results["slow"], httpx.TimeoutException)
