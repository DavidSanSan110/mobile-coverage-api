from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator


class TechCoverage(BaseModel):
    """2G/3G/4G coverage flags for one operator, serialised with technology aliases."""

    model_config = ConfigDict(serialize_by_alias=True)

    g2: bool = Field(serialization_alias="2G")
    g3: bool = Field(serialization_alias="3G")
    g4: bool = Field(serialization_alias="4G")


class OperatorCoverage(BaseModel):
    """Coverage results across all four operators for a successfully geocoded address."""

    orange: TechCoverage
    sfr: TechCoverage
    bouygues: TechCoverage
    free: TechCoverage


class AddressError(BaseModel):
    """Error result for an address that could not be geocoded."""

    error: str


class HealthResponse(BaseModel):
    status: str
    antennas_loaded: int


class CoverageRequest(RootModel[dict[str, str]]):
    """Request body: a mapping of caller-chosen IDs to French address strings."""

    @model_validator(mode="after")
    def validate_non_empty(self) -> "CoverageRequest":
        if not self.root:
            raise ValueError("At least one address is required")
        return self
