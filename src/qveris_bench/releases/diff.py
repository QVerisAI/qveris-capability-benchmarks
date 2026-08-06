from __future__ import annotations

from typing import Any


def diff_releases(before: dict[str, Any], after: dict[str, Any]) -> tuple[str, ...]:
    keys = set(before) | set(after)
    return tuple(sorted(key for key in keys if before.get(key) != after.get(key)))
