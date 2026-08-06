from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

StableId = Annotated[
    str,
    Field(pattern=r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", min_length=1, max_length=128),
]
SemanticVersion = Annotated[
    str,
    Field(
        pattern=(
            r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
            r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
            r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
        )
    ),
]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
EvidenceRef = Annotated[str, Field(pattern=r"^sha256:[a-f0-9]{64}$")]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
