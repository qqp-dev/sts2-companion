from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from source_foundation.canonical import canonical_json_bytes
from source_foundation.errors import FoundationError
from source_foundation.input_gate import regenerate_after_gate
from source_foundation.pck import read_selected


def _padded_path(path: str) -> bytes:
    raw = path.encode("utf-8")
    return raw + b"\0" * ((-len(raw)) % 4)


def _write_pck(
    path: Path,
    data: bytes,
    *,
    selected_path: str = "localization/eng/encounters.json",
    pack_format: int = 3,
    pack_flags: int = 2,
    entry_flags: int = 0,
    stored_offset: int = 0,
    entry_length: int | None = None,
    md5: bytes | None = None,
) -> None:
    file_base = 112
    directory_offset = file_base + len(data)
    encoded_path = _padded_path(selected_path)
    directory = b"".join(
        (
            struct.pack("<I", 1),
            struct.pack("<I", len(encoded_path)),
            encoded_path,
            struct.pack("<Q", stored_offset),
            struct.pack("<Q", len(data) if entry_length is None else entry_length),
            hashlib.md5(data).digest() if md5 is None else md5,
            struct.pack("<I", entry_flags),
        )
    )
    header = b"GDPC" + struct.pack(
        "<5I2Q", pack_format, 4, 5, 1, pack_flags, file_base, directory_offset
    )
    assert len(header) == 40
    path.write_bytes(header + b"\0" * (file_base - len(header)) + data + directory)


def _manifest(root: Path, relative_paths: list[str]) -> dict[str, dict[str, object]]:
    result = {}
    for relative_path in relative_paths:
        data = (root / relative_path).read_bytes()
        result[relative_path] = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    return result


class PckReaderTests(unittest.TestCase):
    def test_selective_read_validates_and_returns_selected_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            payload = b'{"EXAMPLE.title":"Exact title"}\n'
            _write_pck(path, payload)
            data, entry, info = read_selected(
                path, "localization/eng/encounters.json"
            )
            self.assertEqual(data, payload)
            self.assertEqual(entry.md5, hashlib.md5(payload).hexdigest())
            self.assertEqual(entry.flags, 0)
            self.assertEqual(info.format, 3)
            self.assertEqual(info.pack_flags, 2)
            self.assertEqual(info.file_count, 1)

    def test_rejects_unsupported_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", pack_format=4)
            with self.assertRaisesRegex(FoundationError, "unsupported PCK format"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_unsupported_pack_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", pack_flags=3)
            with self.assertRaisesRegex(FoundationError, "unsupported PCK pack flags"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_unsupported_entry_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", entry_flags=1)
            with self.assertRaisesRegex(FoundationError, "unsupported PCK entry flags"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_out_of_bounds_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", stored_offset=3, entry_length=2)
            with self.assertRaisesRegex(FoundationError, "entry out of bounds"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_selected_entry_md5_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", md5=b"\0" * 16)
            with self.assertRaisesRegex(FoundationError, "PCK MD5 mismatch"):
                read_selected(path, "localization/eng/encounters.json")


class InputGateTests(unittest.TestCase):
    relative_paths = [
        "release_info.json",
        "data_sts2_linuxbsd_x86_64/sts2.dll",
        "data_sts2_linuxbsd_x86_64/sts2.xml",
        "SlayTheSpire2.pck",
    ]
    expected_release = {
        "version": "test-version",
        "commit": "test-commit",
        "branch": "test-branch",
        "main_assembly_hash": 123,
    }

    def _root(self, directory: str, release: dict | None = None) -> Path:
        root = Path(directory) / "game"
        (root / "data_sts2_linuxbsd_x86_64").mkdir(parents=True)
        metadata = self.expected_release if release is None else release
        (root / "release_info.json").write_text(json.dumps(metadata), encoding="utf-8")
        (root / "data_sts2_linuxbsd_x86_64/sts2.dll").write_bytes(b"dll")
        (root / "data_sts2_linuxbsd_x86_64/sts2.xml").write_bytes(b"xml")
        (root / "SlayTheSpire2.pck").write_bytes(b"pck")
        return root

    def test_bad_hash_does_not_call_builder_or_replace_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            manifest = _manifest(root, self.relative_paths)
            (root / "data_sts2_linuxbsd_x86_64/sts2.dll").write_bytes(b"bad")
            destination = Path(directory) / "artifact.json"
            destination.write_bytes(b"KEEP")
            called = False

            def builder(_verified):
                nonlocal called
                called = True
                return b"REPLACE"

            with self.assertRaisesRegex(FoundationError, "SHA-256 mismatch"):
                regenerate_after_gate(
                    root,
                    destination,
                    builder,
                    expected_inputs=manifest,
                    expected_release=self.expected_release,
                )
            self.assertFalse(called)
            self.assertEqual(destination.read_bytes(), b"KEEP")

    def test_bad_release_metadata_does_not_replace_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            bad_release = dict(self.expected_release, version="wrong-version")
            root = self._root(directory, bad_release)
            manifest = _manifest(root, self.relative_paths)
            destination = Path(directory) / "artifact.json"
            destination.write_bytes(b"KEEP")
            with self.assertRaisesRegex(FoundationError, "release metadata mismatch"):
                regenerate_after_gate(
                    root,
                    destination,
                    lambda _verified: b"REPLACE",
                    expected_inputs=manifest,
                    expected_release=self.expected_release,
                )
            self.assertEqual(destination.read_bytes(), b"KEEP")

    def test_malformed_release_json_does_not_replace_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            (root / "release_info.json").write_bytes(b'{"version":')
            manifest = _manifest(root, self.relative_paths)
            destination = Path(directory) / "artifact.json"
            destination.write_bytes(b"KEEP")
            with self.assertRaisesRegex(FoundationError, "malformed JSON"):
                regenerate_after_gate(
                    root,
                    destination,
                    lambda _verified: b"REPLACE",
                    expected_inputs=manifest,
                    expected_release=self.expected_release,
                )
            self.assertEqual(destination.read_bytes(), b"KEEP")

    def test_success_replaces_only_after_builder_returns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self._root(directory)
            manifest = _manifest(root, self.relative_paths)
            destination = Path(directory) / "artifact.json"
            destination.write_bytes(b"OLD")
            regenerate_after_gate(
                root,
                destination,
                lambda _verified: b"NEW",
                expected_inputs=manifest,
                expected_release=self.expected_release,
            )
            self.assertEqual(destination.read_bytes(), b"NEW")


class CanonicalSerializationTests(unittest.TestCase):
    def test_serialization_is_order_independent_and_byte_stable(self):
        first = {"z": [3, {"b": 2, "a": 1}], "a": "title"}
        second = {"a": "title", "z": [3, {"a": 1, "b": 2}]}
        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(
            canonical_json_bytes(first),
            b'{\n  "a": "title",\n  "z": [\n    3,\n    {\n      "a": 1,\n      "b": 2\n    }\n  ]\n}\n',
        )


if __name__ == "__main__":
    unittest.main()
