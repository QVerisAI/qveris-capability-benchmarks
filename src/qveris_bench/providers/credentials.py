from __future__ import annotations

import re
from collections.abc import Mapping

ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SECRET_FINGERPRINTS = (
    re.compile(r"^AKIA[0-9A-Z]{16}$"),
    re.compile(r"^gh[pousr]_[A-Za-z0-9]{20,}$"),
    re.compile(r"^sk-[A-Za-z0-9_-]{20,}$"),
)


class CredentialReferenceError(ValueError):
    pass


def validate_credential_reference(value: str) -> str:
    if any(pattern.fullmatch(value) for pattern in SECRET_FINGERPRINTS):
        raise CredentialReferenceError(
            "credential value is not an environment reference"
        )
    if not ENVIRONMENT_NAME.fullmatch(value):
        raise CredentialReferenceError(
            "credential reference must be an uppercase environment variable name"
        )
    return value


def missing_credential_references(
    references: tuple[str, ...], environment: Mapping[str, str]
) -> tuple[str, ...]:
    validated = tuple(validate_credential_reference(value) for value in references)
    return tuple(name for name in validated if not environment.get(name))
