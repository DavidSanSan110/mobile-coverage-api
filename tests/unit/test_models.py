import pytest
from pydantic import ValidationError

from coverage.models import (
    AddressError,
    CoverageRequest,
    HealthResponse,
    OperatorCoverage,
    TechCoverage,
)


class TestTechCoverage:
    def test_serializes_with_technology_alias_keys(self) -> None:
        tc = TechCoverage(g2=True, g3=False, g4=True)
        data = tc.model_dump()
        assert set(data.keys()) == {"2G", "3G", "4G"}

    def test_coverage_flags_are_preserved(self) -> None:
        tc = TechCoverage(g2=True, g3=False, g4=True)
        data = tc.model_dump()
        assert data["2G"] is True
        assert data["3G"] is False
        assert data["4G"] is True


class TestOperatorCoverage:
    def test_serializes_all_four_operators(self) -> None:
        cov = OperatorCoverage(
            orange=TechCoverage(g2=True, g3=True, g4=False),
            sfr=TechCoverage(g2=True, g3=False, g4=True),
            bouygues=TechCoverage(g2=False, g3=True, g4=True),
            free=TechCoverage(g2=False, g3=True, g4=False),
        )
        data = cov.model_dump()
        assert set(data.keys()) == {"orange", "sfr", "bouygues", "free"}
        assert set(data["orange"].keys()) == {"2G", "3G", "4G"}


class TestAddressError:
    def test_stores_error_message(self) -> None:
        err = AddressError(error="address_not_found")
        assert err.error == "address_not_found"


class TestHealthResponse:
    def test_stores_status_and_count(self) -> None:
        h = HealthResponse(status="ok", antennas_loaded=77503)
        assert h.status == "ok"
        assert h.antennas_loaded == 77503


class TestCoverageRequest:
    def test_accepts_valid_address_dict(self) -> None:
        req = CoverageRequest.model_validate({"id1": "157 bd MacDonald 75019 Paris"})
        assert req.root == {"id1": "157 bd MacDonald 75019 Paris"}

    def test_rejects_empty_dict(self) -> None:
        with pytest.raises(ValidationError):
            CoverageRequest.model_validate({})

    def test_preserves_multiple_ids(self) -> None:
        req = CoverageRequest.model_validate({"a": "addr 1", "b": "addr 2"})
        assert set(req.root.keys()) == {"a", "b"}
