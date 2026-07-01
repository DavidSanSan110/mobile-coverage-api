import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from mobile_coverage.main import app

GEOCODING_URL = "https://api-adresse.data.gouv.fr/search/"


def _ok(x: float = 654412.35, y: float = 6866689.51) -> httpx.Response:
    return httpx.Response(
        200,
        json={"features": [{"properties": {"score": 0.9, "x": x, "y": y, "label": "test"}}]},
    )


def _empty() -> httpx.Response:
    return httpx.Response(200, json={"features": []})


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        return c


class TestHealthEndpoint:
    def test_returns_200(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_status_is_ok(self, client: TestClient) -> None:
        assert client.get("/health").json()["status"] == "ok"

    def test_antennas_loaded_is_positive(self, client: TestClient) -> None:
        data = client.get("/health").json()
        assert "antennas_loaded" in data
        assert data["antennas_loaded"] > 0


class TestCoverageEndpoint:
    def test_successful_address_returns_200(self, client: TestClient) -> None:
        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            response = client.post("/coverage", json={"id1": "157 bd MacDonald 75019 Paris"})
        assert response.status_code == 200

    def test_response_includes_all_operators(self, client: TestClient) -> None:
        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            data = client.post("/coverage", json={"id1": "some address"}).json()
        assert set(data["id1"].keys()) == {"orange", "sfr", "bouygues", "free"}

    def test_response_tech_keys_use_2g_3g_4g_aliases(self, client: TestClient) -> None:
        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            data = client.post("/coverage", json={"id1": "some address"}).json()
        for operator_data in data["id1"].values():
            assert set(operator_data.keys()) == {"2G", "3G", "4G"}

    def test_coverage_values_are_booleans(self, client: TestClient) -> None:
        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            data = client.post("/coverage", json={"id1": "some address"}).json()
        for operator_data in data["id1"].values():
            for v in operator_data.values():
                assert isinstance(v, bool)

    def test_failed_geocoding_returns_address_not_found_error(self, client: TestClient) -> None:
        # One succeeds, one fails — confirms per-address error shape in a partial failure.
        def _respond(request: httpx.Request) -> httpx.Response:
            return _ok() if request.url.params.get("q") == "good" else _empty()

        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(side_effect=_respond)
            data = client.post("/coverage", json={"ok": "good", "bad": "gibberish"}).json()

        assert data["bad"] == {"error": "address_not_found"}

    def test_all_geocoding_fails_returns_503(self, client: TestClient) -> None:
        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(return_value=httpx.Response(503))
            response = client.post("/coverage", json={"id1": "addr1", "id2": "addr2"})
        assert response.status_code == 503

    def test_empty_body_returns_422(self, client: TestClient) -> None:
        response = client.post("/coverage", json={})
        assert response.status_code == 422

    def test_too_many_addresses_returns_422(self, client: TestClient) -> None:
        payload = {f"id{i}": f"addr {i}" for i in range(51)}
        response = client.post("/coverage", json=payload)
        assert response.status_code == 422

    def test_partial_failure_returns_200_with_mixed_results(self, client: TestClient) -> None:
        def _respond(request: httpx.Request) -> httpx.Response:
            return _ok() if request.url.params.get("q") == "good address" else _empty()

        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(side_effect=_respond)
            data = client.post(
                "/coverage", json={"good": "good address", "bad": "bad address"}
            ).json()

        assert "error" not in data["good"]
        assert "error" in data["bad"]

    def test_result_keys_match_input_keys(self, client: TestClient) -> None:
        with respx.mock as mock:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            data = client.post("/coverage", json={"alpha": "addr1", "beta": "addr2"}).json()
        assert set(data.keys()) == {"alpha", "beta"}


class TestCoverageLogging:
    def test_geocoding_complete_is_logged_once_per_address(self, client: TestClient) -> None:
        with respx.mock as mock, capture_logs() as cap:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            client.post("/coverage", json={"id1": "addr1", "id2": "addr2"})
        events = [e for e in cap if e.get("event") == "geocoding_complete"]
        assert len(events) == 2

    def test_geocoding_complete_status_found_on_success(self, client: TestClient) -> None:
        with respx.mock as mock, capture_logs() as cap:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            client.post("/coverage", json={"id1": "good address"})
        event = next(e for e in cap if e.get("event") == "geocoding_complete")
        assert event["status"] == "found"
        assert event["address_id"] == "id1"

    def test_geocoding_complete_status_not_found_on_failure(self, client: TestClient) -> None:
        def _respond(request: httpx.Request) -> httpx.Response:
            return _ok() if request.url.params.get("q") == "good" else _empty()

        with respx.mock as mock, capture_logs() as cap:
            mock.get(GEOCODING_URL).mock(side_effect=_respond)
            client.post("/coverage", json={"good": "good", "bad": "gibberish"})

        failed = next(
            e
            for e in cap
            if e.get("event") == "geocoding_complete" and e.get("address_id") == "bad"
        )
        assert failed["status"] == "not_found"

    def test_request_complete_is_logged_once_per_request(self, client: TestClient) -> None:
        with respx.mock as mock, capture_logs() as cap:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            client.post("/coverage", json={"id1": "some address"})
        events = [e for e in cap if e.get("event") == "request_complete"]
        assert len(events) == 1

    def test_request_complete_has_correct_counts(self, client: TestClient) -> None:
        def _respond(request: httpx.Request) -> httpx.Response:
            return _ok() if request.url.params.get("q") == "good" else _empty()

        with respx.mock as mock, capture_logs() as cap:
            mock.get(GEOCODING_URL).mock(side_effect=_respond)
            client.post("/coverage", json={"good": "good", "bad": "bad1", "bad2": "bad2"})

        event = next(e for e in cap if e.get("event") == "request_complete")
        assert event["addresses_count"] == 3
        assert event["errors_count"] == 2

    def test_request_complete_includes_latency(self, client: TestClient) -> None:
        with respx.mock as mock, capture_logs() as cap:
            mock.get(GEOCODING_URL).mock(return_value=_ok())
            client.post("/coverage", json={"id1": "some address"})
        event = next(e for e in cap if e.get("event") == "request_complete")
        assert "geocoding_latency_ms" in event
        assert "total_latency_ms" in event
