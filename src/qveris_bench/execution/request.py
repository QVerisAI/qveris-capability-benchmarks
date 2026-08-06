from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TransportRequest:
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    json_body: dict[str, Any] | None = None
    bearer_token: str | None = None
    timeout_seconds: float = 30
