from __future__ import annotations

from typing import Any


class FrozenAgentInputError(ValueError):
    pass


def merge_frozen_parameters(
    frozen_parameters: dict[str, Any],
    proposed_parameters: dict[str, object],
    exposed_parameter_names: tuple[str, ...],
) -> dict[str, Any]:
    if set(proposed_parameters) != set(exposed_parameter_names):
        raise FrozenAgentInputError("agent proposed unexpected parameters")
    for name in exposed_parameter_names:
        if name not in frozen_parameters:
            raise FrozenAgentInputError("agent parameter is not frozen")
        if proposed_parameters[name] != frozen_parameters[name]:
            raise FrozenAgentInputError("agent proposed a value outside the frozen run")
    return dict(frozen_parameters)
