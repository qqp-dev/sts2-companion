"""Strict stdlib-only localization joins."""

from __future__ import annotations

from typing import Any, Mapping

from .errors import SourceExtractionError


def require_localized_text(localization: Mapping[str, Any], key: str) -> str:
    if key not in localization:
        raise SourceExtractionError(f"missing localization key {key}")
    value = localization[key]
    if not isinstance(value, str) or not value:
        raise SourceExtractionError(f"invalid localization value for {key}")
    return value
