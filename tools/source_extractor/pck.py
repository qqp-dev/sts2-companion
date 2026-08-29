"""Small read-only Godot PCK v3 selective reader (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import struct

from .errors import SourceExtractionError

_U32 = struct.Struct("<I")
_U64 = struct.Struct("<Q")
_HEADER = struct.Struct("<5I2Q")
_MAX_U64 = (1 << 64) - 1
_MAX_PATH_BYTES = 1 << 20
_MAX_SELECTED_BYTES = 16 << 20
_SUPPORTED_FORMAT = 3
_SUPPORTED_PACK_FLAGS = 2
_SUPPORTED_ENTRY_FLAGS = 0


@dataclass(frozen=True)
class PckInfo:
    format: int
    godot_version: tuple[int, int, int]
    pack_flags: int
    file_base: int
    directory_offset: int
    file_count: int
    size: int


@dataclass(frozen=True)
class PckEntry:
    path: str
    stored_offset: int
    physical_offset: int
    size: int
    md5: str
    flags: int


def _exact(handle, count: int, context: str) -> bytes:
    data = handle.read(count)
    if len(data) != count:
        raise SourceExtractionError(
            f"PCK {context}: truncated at offset {handle.tell() - len(data)} "
            f"(wanted {count} bytes, got {len(data)})"
        )
    return data


def _checked_path(raw: bytes, index: int) -> str:
    # Godot stores a four-byte-aligned length. Already-aligned paths need no
    # terminator; other paths have trailing NUL padding only.
    path_bytes = raw.rstrip(b"\0")
    if not path_bytes or b"\0" in path_bytes:
        raise SourceExtractionError(f"PCK entry {index}: malformed path padding")
    try:
        path = path_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceExtractionError(f"PCK entry {index}: invalid UTF-8 path: {exc}") from exc
    pure = PurePosixPath(path)
    if (
        pure.is_absolute()
        or "\\" in path
        or any(part in ("", ".", "..") for part in pure.parts)
    ):
        raise SourceExtractionError(f"PCK entry {index}: unsafe path {path!r}")
    return path


def read_selected(pck_path: Path, selected_path: str) -> tuple[bytes, PckEntry, PckInfo]:
    """Read exactly one selected entry after validating the complete directory."""
    path = Path(pck_path)
    try:
        pack_size = path.stat().st_size
        handle = path.open("rb")
    except OSError as exc:
        raise SourceExtractionError(f"cannot open PCK {path}: {exc}") from exc

    with handle:
        if _exact(handle, 4, "magic") != b"GDPC":
            raise SourceExtractionError("PCK magic mismatch: expected GDPC")
        (
            pack_format,
            major,
            minor,
            patch,
            pack_flags,
            file_base,
            directory_offset,
        ) = _HEADER.unpack(_exact(handle, _HEADER.size, "header"))
        if pack_format != _SUPPORTED_FORMAT:
            raise SourceExtractionError(
                f"unsupported PCK format {pack_format}; expected {_SUPPORTED_FORMAT}"
            )
        if pack_flags != _SUPPORTED_PACK_FLAGS:
            raise SourceExtractionError(
                f"unsupported PCK pack flags {pack_flags}; expected {_SUPPORTED_PACK_FLAGS}"
            )
        if file_base < 4 + _HEADER.size or file_base > pack_size:
            raise SourceExtractionError(f"PCK file base out of bounds: {file_base}")
        if directory_offset < file_base or directory_offset > pack_size - 4:
            raise SourceExtractionError(
                f"PCK directory offset out of bounds: {directory_offset} for {pack_size} bytes"
            )

        handle.seek(directory_offset)
        file_count = _U32.unpack(_exact(handle, 4, "directory count"))[0]
        # Every entry needs path-length + at least four path bytes + offset,
        # length, MD5, and flags. Bound count before iterating attacker data.
        remaining = pack_size - directory_offset - 4
        if file_count > remaining // 44:
            raise SourceExtractionError(
                f"PCK directory count {file_count} cannot fit in {remaining} bytes"
            )

        entries: dict[str, PckEntry] = {}
        for index in range(file_count):
            path_size = _U32.unpack(_exact(handle, 4, f"entry {index} path length"))[0]
            if path_size < 4 or path_size > _MAX_PATH_BYTES or path_size % 4:
                raise SourceExtractionError(
                    f"PCK entry {index}: invalid padded path length {path_size}"
                )
            entry_path = _checked_path(
                _exact(handle, path_size, f"entry {index} path"), index
            )
            stored_offset = _U64.unpack(
                _exact(handle, 8, f"entry {index} offset")
            )[0]
            length = _U64.unpack(_exact(handle, 8, f"entry {index} length"))[0]
            expected_md5 = _exact(handle, 16, f"entry {index} MD5").hex()
            entry_flags = _U32.unpack(
                _exact(handle, 4, f"entry {index} flags")
            )[0]
            if entry_flags != _SUPPORTED_ENTRY_FLAGS:
                raise SourceExtractionError(
                    f"unsupported PCK entry flags {entry_flags} for {entry_path}"
                )
            if entry_path in entries:
                raise SourceExtractionError(f"duplicate PCK path {entry_path!r}")
            if stored_offset > _MAX_U64 - file_base:
                raise SourceExtractionError(f"PCK entry offset overflow for {entry_path}")
            physical_offset = file_base + stored_offset
            if physical_offset > directory_offset or length > directory_offset - physical_offset:
                raise SourceExtractionError(
                    f"PCK entry out of bounds for {entry_path}: "
                    f"offset {physical_offset}, length {length}, directory {directory_offset}"
                )
            entries[entry_path] = PckEntry(
                entry_path,
                stored_offset,
                physical_offset,
                length,
                expected_md5,
                entry_flags,
            )

        info = PckInfo(
            pack_format,
            (major, minor, patch),
            pack_flags,
            file_base,
            directory_offset,
            file_count,
            pack_size,
        )
        entry = entries.get(selected_path)
        if entry is None:
            raise SourceExtractionError(f"PCK entry not found: {selected_path}")
        if entry.size > _MAX_SELECTED_BYTES:
            raise SourceExtractionError(
                f"selected PCK entry is unexpectedly large: {entry.size} bytes"
            )
        handle.seek(entry.physical_offset)
        data = _exact(handle, entry.size, f"entry data {selected_path}")
        try:
            actual_md5 = hashlib.md5(data, usedforsecurity=False).hexdigest()
        except TypeError:  # Python builds without the keyword.
            actual_md5 = hashlib.md5(data).hexdigest()
        if actual_md5 != entry.md5:
            raise SourceExtractionError(
                f"PCK MD5 mismatch for {selected_path}: got {actual_md5}, expected {entry.md5}"
            )
        return data, entry, info
