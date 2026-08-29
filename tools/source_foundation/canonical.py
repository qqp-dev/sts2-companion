"""Strict JSON handling and deterministic serialization (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from .errors import FoundationError


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FoundationError(f"malformed JSON: duplicate key {key!r}")
        result[key] = value
    return result


def strict_json_bytes(data: bytes, context: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FoundationError(f"{context}: invalid UTF-8: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except FoundationError as exc:
        raise FoundationError(f"{context}: {exc}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise FoundationError(f"{context}: malformed JSON: {exc}") from exc


def compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def witness_sha256(value: Any) -> str:
    return hashlib.sha256(compact_json_bytes(value)).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def atomic_write(destination: Path, data: bytes) -> None:
    """Replace destination only after all bytes exist, using its own directory."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = handle.name
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
        temporary = None
    except OSError as exc:
        raise FoundationError(f"cannot atomically write {destination}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
