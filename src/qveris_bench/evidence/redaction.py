from __future__ import annotations

import re
from dataclasses import dataclass

_PATTERNS = (
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)[^\s\\\"']+"),
    re.compile(r"(?i)((?:x-)?api[-_ ]?key\s*[:=]\s*[\"']?)[^\s\\\"',}&]+"),
    re.compile(r"(?i)([?&](?:api[-_ ]?key|token|access_token)=)[^&#\s]+"),
    re.compile(r"(?i)(\"(?:api[-_ ]?key|token|access_token)\"\s*:\s*\")[^\"]+"),
    re.compile(
        r"(?i)(\"(?:authorization|x-api-key|accessToken|access_token)\"\s*:\s*\")[^\"]+"
    ),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"(?<!\w)(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?!\w)"),
    re.compile(r"(?i)(account(?:_id)?\s*[:=]\s*)[^\s,}&]+"),
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    changed: bool


def redact_text(text: str) -> RedactionResult:
    sanitized = text
    for pattern in _PATTERNS:
        sanitized = pattern.sub(_replacement, sanitized)
    return RedactionResult(text=sanitized, changed=sanitized != text)


def _replacement(match: re.Match[str]) -> str:
    if match.lastindex:
        return f"{match.group(1)}[REDACTED]"
    return "[REDACTED]"
