from __future__ import annotations

from typing import Annotated

from pydantic import Field, HttpUrl

from qveris_bench.models.base import FrozenModel, StableId
from qveris_bench.models.enums import AccessPathType

EnvironmentVariable = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]*$")]


class ProviderProfile(FrozenModel):
    provider_id: StableId
    official_name: str = Field(min_length=1)
    website: HttpUrl
    market_coverage: tuple[str, ...] = ()
    testing_authorization: str = Field(min_length=1)
    qveris_integration: bool = False


class AccessPath(FrozenModel):
    access_path_id: StableId
    provider_id: StableId
    path_type: AccessPathType
    credential_env: tuple[EnvironmentVariable, ...] = ()
    official_source: HttpUrl
    plan_name: str | None = None
    authorization: str | None = None
    canonical_interface: str = Field(min_length=1)
    agent_trial_eligible: bool
