"""Exact, mixed-version-safe input gate (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping

from .canonical import atomic_write, strict_json_bytes
from .errors import FoundationError

EXPECTED_INPUTS: dict[str, dict[str, Any]] = {
    "release_info.json": {
        "size": 150,
        "sha256": "9e5dbce5bcd8ff3b7b432291200220642408e31b8bae7bba14f39aeb6914cd51",
    },
    "data_sts2_linuxbsd_x86_64/sts2.dll": {
        "size": 9_756_160,
        "sha256": "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f",
    },
    "data_sts2_linuxbsd_x86_64/sts2.xml": {
        "size": 5_650_972,
        "sha256": "a88331870d38cdb84d8fc371ab3d7fb619afa25c8c7249a47aaa77e1c7bf4286",
    },
    "SlayTheSpire2.pck": {
        "size": 1_990_363_992,
        "sha256": "42443027622a6a82de8ab21e81ed5b68e522c0f5647fb6a26a74c4a0970a0d34",
    },
}

EXPECTED_RELEASE: dict[str, Any] = {
    "version": "v0.111.0",
    "commit": "41cef1ea",
    "branch": "v0.111.0",
    "main_assembly_hash": 1_579_942_752,
}


@dataclass(frozen=True)
class VerifiedInput:
    relative_path: str
    path: Path
    size: int
    sha256: str


@dataclass(frozen=True)
class VerifiedInputs:
    game_root: Path
    files: tuple[VerifiedInput, ...]
    release: dict[str, Any]

    def by_relative_path(self, relative_path: str) -> VerifiedInput:
        for item in self.files:
            if item.relative_path == relative_path:
                return item
        raise KeyError(relative_path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as exc:
        raise FoundationError(f"cannot read input {path}: {exc}") from exc
    return digest.hexdigest()


def verify_inputs(
    game_root: Path,
    *,
    expected_inputs: Mapping[str, Mapping[str, Any]] = EXPECTED_INPUTS,
    expected_release: Mapping[str, Any] = EXPECTED_RELEASE,
) -> VerifiedInputs:
    """Hash every input before parsing release metadata; report no partial facts."""
    root = Path(game_root).expanduser().resolve()
    failures: list[str] = []
    verified: list[VerifiedInput] = []

    # Keep manifest order deterministic but do not stop early: all existing files
    # are hashed before the gate decides whether this is one coherent build.
    for relative_path in sorted(expected_inputs):
        expected = expected_inputs[relative_path]
        path = root / relative_path
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            failures.append(f"missing {relative_path}")
            continue
        except OSError as exc:
            failures.append(f"cannot stat {relative_path}: {exc}")
            continue
        try:
            digest = sha256_file(path)
        except FoundationError as exc:
            failures.append(str(exc))
            continue
        if type(expected.get("size")) is not int or not isinstance(expected.get("sha256"), str):
            raise FoundationError(f"invalid extractor input manifest entry: {relative_path}")
        if size != expected["size"]:
            failures.append(
                f"size mismatch for {relative_path}: got {size}, expected {expected['size']}"
            )
        if digest != expected["sha256"]:
            failures.append(
                f"SHA-256 mismatch for {relative_path}: got {digest}, expected {expected['sha256']}"
            )
        verified.append(VerifiedInput(relative_path, path, size, digest))

    if failures:
        raise FoundationError("input gate failed; " + "; ".join(failures))

    release_input = next(
        item for item in verified if item.relative_path == "release_info.json"
    )
    try:
        release_bytes = release_input.path.read_bytes()
    except OSError as exc:
        raise FoundationError(f"cannot read release_info.json: {exc}") from exc
    release = strict_json_bytes(release_bytes, "release_info.json")
    if not isinstance(release, dict):
        raise FoundationError("release_info.json: top level must be an object")

    release_failures: list[str] = []
    for key, expected_value in expected_release.items():
        value = release.get(key)
        # bool is an int subclass; it is not valid assembly-hash metadata.
        if type(value) is not type(expected_value) or value != expected_value:
            release_failures.append(
                f"{key}={value!r}, expected {expected_value!r}"
            )
    if release_failures:
        raise FoundationError(
            "release metadata mismatch (possible mixed-version inputs); "
            + "; ".join(release_failures)
        )

    return VerifiedInputs(root, tuple(verified), dict(release))


def regenerate_after_gate(
    game_root: Path,
    destination: Path,
    builder: Callable[[VerifiedInputs], bytes],
    *,
    expected_inputs: Mapping[str, Mapping[str, Any]] = EXPECTED_INPUTS,
    expected_release: Mapping[str, Any] = EXPECTED_RELEASE,
) -> None:
    """Testable gate/build/atomic-write orchestration used by the CLI."""
    verified = verify_inputs(
        game_root,
        expected_inputs=expected_inputs,
        expected_release=expected_release,
    )
    data = builder(verified)
    if not isinstance(data, bytes):
        raise FoundationError("extractor builder did not return bytes")
    atomic_write(Path(destination), data)
