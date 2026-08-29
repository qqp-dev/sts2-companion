from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
import struct
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from source_extractor.ast import evaluate_expression, validate_expression, validate_selection
from source_extractor.canonical import canonical_json_bytes
from source_extractor.cil_safety import validate_cil_slice
from source_extractor.encounters import _compile_fixed_selection, _derive_fixed_slot_names
from source_extractor.localization import require_localized_text
from source_extractor.errors import SourceExtractionError
from source_extractor.input_gate import regenerate_after_gate
from source_extractor.pck import read_selected


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
            with self.assertRaisesRegex(SourceExtractionError, "unsupported PCK format"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_unsupported_pack_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", pack_flags=3)
            with self.assertRaisesRegex(SourceExtractionError, "unsupported PCK pack flags"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_unsupported_entry_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", entry_flags=1)
            with self.assertRaisesRegex(SourceExtractionError, "unsupported PCK entry flags"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_out_of_bounds_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", stored_offset=3, entry_length=2)
            with self.assertRaisesRegex(SourceExtractionError, "entry out of bounds"):
                read_selected(path, "localization/eng/encounters.json")

    def test_rejects_selected_entry_md5_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.pck"
            _write_pck(path, b"{}", md5=b"\0" * 16)
            with self.assertRaisesRegex(SourceExtractionError, "PCK MD5 mismatch"):
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

            with self.assertRaisesRegex(SourceExtractionError, "SHA-256 mismatch"):
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
            with self.assertRaisesRegex(SourceExtractionError, "release metadata mismatch"):
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
            with self.assertRaisesRegex(SourceExtractionError, "malformed JSON"):
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


class NormalizedExpressionTests(unittest.TestCase):
    @staticmethod
    def integer(value: int) -> dict:
        return {"kind": "constant", "value": value, "valueType": "integer"}

    @staticmethod
    def decimal(value: str) -> dict:
        return {"kind": "constant", "value": value, "valueType": "decimal"}

    @staticmethod
    def variable(name: str, value_type: str = "integer", domain=None) -> dict:
        if domain is None:
            domain = {"minimum": 0}
        return {"domain": domain, "kind": "stateVariable", "name": name, "valueType": value_type}

    def test_constants_ascension_ranges_and_arithmetic(self):
        ascension = {
            "atOrAbove": self.integer(20), "below": self.integer(10),
            "kind": "ascensionSelect", "threshold": 8, "valueType": "integer",
        }
        expression = {
            "kind": "arithmetic", "operands": [ascension, self.integer(3)],
            "operator": "add", "valueType": "integer",
        }
        range_expression = {
            "kind": "range", "minimum": expression,
            "maximum": {**expression, "operands": [ascension, self.integer(5)]},
            "valueType": "integerRange",
        }
        self.assertEqual(validate_expression(range_expression), "integerRange")
        self.assertEqual(evaluate_expression(range_expression, {"ascension": 7}), {"minimum": 13, "maximum": 15})
        self.assertEqual(evaluate_expression(range_expression, {"ascension": 8}), {"minimum": 23, "maximum": 25})

    def test_conditionals_state_inputs_player_scaling_and_decimal_conversion(self):
        players = self.variable("playerCount", domain={"minimum": 1})
        base = self.variable("baseHp", "decimal", {"minimum": "0"})
        factor = {
            "actIndex": self.variable("actIndex", domain={"minimum": 0, "maximum": 2}),
            "boss": self.variable("bossRoom", "boolean", [False, True]),
            "factors": {"act1": "1.1", "act2": "1.2", "act3Boss": "1.3", "act3NonBoss": "1.2"},
            "kind": "actRoomFactor", "valueType": "decimal",
        }
        expression = {
            "condition": {"kind": "compare", "left": players, "operator": "lessOrEqual", "right": self.integer(1), "valueType": "boolean"},
            "kind": "conditional", "valueType": "decimal", "whenTrue": base,
            "whenFalse": {
                "kind": "arithmetic", "operator": "multiply", "valueType": "decimal",
                "operands": [base, {"expression": players, "fromType": "integer", "kind": "convert", "mode": "exact", "toType": "decimal", "valueType": "decimal"}, factor],
            },
        }
        self.assertEqual(validate_expression(expression), "decimal")
        self.assertEqual(evaluate_expression(expression, {"actIndex": 0, "baseHp": "51", "bossRoom": False, "playerCount": 1}), Decimal("51"))
        self.assertEqual(evaluate_expression(expression, {"actIndex": 2, "baseHp": "51", "bossRoom": True, "playerCount": 2}), Decimal("132.6"))

    def test_explicit_rounding_modes(self):
        source = self.decimal("2.5")
        for mode, expected in (("truncateTowardZero", 2), ("floor", 2), ("ceiling", 3), ("nearestEven", 2)):
            expression = {"expression": source, "fromType": "decimal", "kind": "convert", "mode": mode, "toType": "integer", "valueType": "integer"}
            self.assertEqual(evaluate_expression(expression, {}), expected)
        negative = {"expression": self.decimal("-2.9"), "fromType": "decimal", "kind": "convert", "mode": "truncateTowardZero", "toType": "integer", "valueType": "integer"}
        self.assertEqual(evaluate_expression(negative, {}), -2)

    def test_missing_or_out_of_domain_state_fails(self):
        variable = self.variable("phase", domain={"minimum": 1, "maximum": 3})
        with self.assertRaisesRegex(SourceExtractionError, "missing state input"):
            evaluate_expression(variable, {})
        with self.assertRaisesRegex(SourceExtractionError, "outside declared domain"):
            evaluate_expression(variable, {"phase": 4})

    def test_unknown_kind_operator_fields_and_cyclic_depth_fail(self):
        with self.assertRaisesRegex(SourceExtractionError, "unsupported expression kind"):
            validate_expression({"kind": "wikiFallback", "valueType": "integer"})
        with self.assertRaisesRegex(SourceExtractionError, "unsupported arithmetic operator"):
            validate_expression({"kind": "arithmetic", "operands": [self.integer(1), self.integer(2)], "operator": "pow", "valueType": "integer"})
        with self.assertRaisesRegex(SourceExtractionError, "unknown fields"):
            validate_expression({"kind": "constant", "value": 1, "valueType": "integer", "prose": "one"})
        cyclic = {"kind": "arithmetic", "operator": "add", "operands": [], "valueType": "integer"}
        cyclic["operands"] = [self.integer(1), cyclic]
        with self.assertRaisesRegex(SourceExtractionError, "depth limit"):
            validate_expression(cyclic)


class RosterAstTests(unittest.TestCase):
    @staticmethod
    def fixed(name: str) -> dict:
        return {"kind": "fixed", "model": "MONSTER." + name}

    def test_selection_cardinality_membership_and_draw_semantics(self):
        choice = {"choices": [self.fixed("A"), self.fixed("B"), self.fixed("C")], "constraint": "modelCountLimit", "count": 2, "draws": "withoutReplacement", "kind": "filteredChoice"}
        selection = {"children": [self.fixed("ROOT"), choice], "kind": "sequence", "order": "fixed"}
        self.assertEqual(validate_selection(selection, known_models={"MONSTER.ROOT", "MONSTER.A", "MONSTER.B", "MONSTER.C"}), (3, 3, {"MONSTER.ROOT", "MONSTER.A", "MONSTER.B", "MONSTER.C"}))
        repeat = {"count": 2, "draws": "independent", "kind": "repeat", "selection": {"choices": [self.fixed("A"), self.fixed("B")], "kind": "uniformChoice"}}
        self.assertEqual(validate_selection(repeat)[:2], (2, 2))
        weighted = {"choices": [self.fixed("A"), self.fixed("B")], "kind": "weightedChoice", "weights": [1, 3]}
        self.assertEqual(validate_selection(weighted)[:2], (1, 1))
        permutation = {"kind": "permutation", "selection": selection}
        self.assertEqual(validate_selection(permutation)[:2], (3, 3))

    def test_unresolved_model_malformed_ast_and_depth_fail(self):
        with self.assertRaisesRegex(SourceExtractionError, "unresolved model"):
            validate_selection(self.fixed("MISSING"), known_models={"MONSTER.KNOWN"})
        with self.assertRaisesRegex(SourceExtractionError, "at least two choices"):
            validate_selection({"choices": [self.fixed("A")], "kind": "uniformChoice"})
        node = self.fixed("A")
        for _ in range(40):
            node = {"kind": "permutation", "selection": node}
        with self.assertRaisesRegex(SourceExtractionError, "depth limit"):
            validate_selection(node)


class FixedRosterCompilerTests(unittest.TestCase):
    MODEL = "MegaCrit.Sts2.Core.Models.ModelDb::Monster sig:1001001e00 generic:MegaCrit.Sts2.Core.Models.Monsters.{}"
    TO_MUTABLE = "MegaCrit.Sts2.Core.Models.MonsterModel::ToMutable sig:20001288e4"
    SLOT_CTOR = "<TypeSpec:151182e9021288e40e>::.ctor sig:20020113001301"
    ARRAY_CTOR = "<TypeSpec:1512b74801151182e9021288e40e>::.ctor sig:2001011d1300"
    SINGLE_CTOR = "<TypeSpec:1512b75001151182e9021288e40e>::.ctor sig:2001011300"
    SLOT_ARRAY_CTOR = "<TypeSpec:1512b748010e>::.ctor sig:2001011d1300"
    SLOT_TYPE = "TypeSpec:151182e9021288e40e"

    @staticmethod
    def instruction(opcode: str, operand=None) -> dict:
        return {"opcode": opcode, "operand": operand}

    def monster_slot(self, simple: str) -> list[dict]:
        return [
            self.instruction("call", self.MODEL.format(simple)),
            self.instruction("callvirt", self.TO_MUTABLE),
            self.instruction("ldnull"),
            self.instruction("newobj", self.SLOT_CTOR),
        ]

    @staticmethod
    def record(instructions: list[dict]) -> dict:
        return {"instructions": instructions, "symbolSignature": "Synthetic::GenerateMonsters sig:test"}

    def test_fixed_compiler_follows_returned_collection_not_call_site_order(self):
        instructions = [
            *self.monster_slot("Alpha"), self.instruction("stloc.0"),
            *self.monster_slot("Beta"), self.instruction("stloc.1"),
            self.instruction("ldc.i4.2"), self.instruction("newarr", self.SLOT_TYPE),
            self.instruction("dup"), self.instruction("ldc.i4.0"), self.instruction("ldloc.1"),
            self.instruction("stelem", self.SLOT_TYPE),
            self.instruction("dup"), self.instruction("ldc.i4.1"), self.instruction("ldloc.0"),
            self.instruction("stelem", self.SLOT_TYPE),
            self.instruction("newobj", self.ARRAY_CTOR), self.instruction("ret"),
        ]
        selection = _compile_fixed_selection(self.record(instructions))
        self.assertEqual(
            [item["model"] for item in selection["children"]],
            ["MONSTER.BETA", "MONSTER.ALPHA"],
        )

    def test_unused_model_call_and_unproved_branch_fail_closed(self):
        unused = [
            *self.monster_slot("Unused"),
            *self.monster_slot("Returned"),
            self.instruction("newobj", self.SINGLE_CTOR), self.instruction("ret"),
        ]
        with self.assertRaisesRegex(SourceExtractionError, "residual evaluation stack"):
            _compile_fixed_selection(self.record(unused))
        branch = [
            *self.monster_slot("Only"), self.instruction("newobj", self.SINGLE_CTOR),
            self.instruction("br.s", 1), self.instruction("ret"),
        ]
        with self.assertRaisesRegex(SourceExtractionError, "unsupported branch"):
            _compile_fixed_selection(self.record(branch))

    def test_unknown_call_and_malformed_collection_fail_closed(self):
        unknown = self.monster_slot("Only")
        unknown[1] = self.instruction("callvirt", self.TO_MUTABLE + " changed")
        unknown.extend([self.instruction("newobj", self.SINGLE_CTOR), self.instruction("ret")])
        with self.assertRaisesRegex(SourceExtractionError, "unknown call/signature"):
            _compile_fixed_selection(self.record(unknown))

        wrong_invocation = self.monster_slot("Only")
        wrong_invocation[1] = self.instruction("call", self.TO_MUTABLE)
        wrong_invocation.extend([self.instruction("newobj", self.SINGLE_CTOR), self.instruction("ret")])
        with self.assertRaisesRegex(SourceExtractionError, "unrecognized invocation opcode"):
            _compile_fixed_selection(self.record(wrong_invocation))

        malformed = [
            *self.monster_slot("Only"), self.instruction("stloc.0"),
            self.instruction("ldc.i4.2"), self.instruction("newarr", self.SLOT_TYPE),
            self.instruction("dup"), self.instruction("ldc.i4.0"), self.instruction("ldloc.0"),
            self.instruction("stelem", self.SLOT_TYPE),
            self.instruction("newobj", self.ARRAY_CTOR), self.instruction("ret"),
        ]
        with self.assertRaisesRegex(SourceExtractionError, "incomplete fixed roster array"):
            _compile_fixed_selection(self.record(malformed))

    def slot_getter(self, names: list[str]) -> list[dict]:
        count_opcode = f"ldc.i4.{len(names)}"
        instructions = [self.instruction(count_opcode), self.instruction("newarr", "System.String")]
        for index, name in enumerate(names):
            instructions.extend([
                self.instruction("dup"), self.instruction(f"ldc.i4.{index}"),
                self.instruction("ldstr", "string:" + name), self.instruction("stelem.ref"),
            ])
        instructions.extend([self.instruction("newobj", self.SLOT_ARRAY_CTOR), self.instruction("ret")])
        return instructions

    def test_fixed_slot_getter_derives_count_and_rejects_unknown_cardinality(self):
        self.assertEqual(_derive_fixed_slot_names(self.slot_getter(["one", "two", "three", "four"])), [
            "string:one", "string:two", "string:three", "string:four",
        ])
        missing = self.slot_getter(["one", "two"])
        del missing[6:10]
        with self.assertRaisesRegex(SourceExtractionError, "not a proven fixed string array"):
            _derive_fixed_slot_names(missing)
        dynamic = self.slot_getter(["one"])
        dynamic[0] = self.instruction("newobj", "Synthetic::get_UnknownSlotCount sig:test")
        with self.assertRaisesRegex(SourceExtractionError, "unknown call/signature"):
            _derive_fixed_slot_names(dynamic)
        with self.assertRaisesRegex(SourceExtractionError, "no proven fixed cardinality"):
            _derive_fixed_slot_names([])


class SyntheticFailClosedTests(unittest.TestCase):
    def test_unknown_opcode_call_signature_and_branch_fail(self):
        allowed = {"ldc.i4.1", "call", "ret"}
        calls = {"Known.Type::Method sig:0000"}
        validate_cil_slice(
            [{"opcode": "ldc.i4.1", "operand": None}, {"opcode": "call", "operand": "Known.Type::Method sig:0000"}, {"opcode": "ret", "operand": None}],
            allowed_opcodes=allowed,
            allowed_calls=calls,
        )
        with self.assertRaisesRegex(SourceExtractionError, "unknown opcode"):
            validate_cil_slice([{"opcode": "localloc", "operand": None}], allowed_opcodes=allowed, allowed_calls=calls)
        with self.assertRaisesRegex(SourceExtractionError, "unknown call/signature"):
            validate_cil_slice([{"opcode": "call", "operand": "Known.Type::Method sig:ffff"}], allowed_opcodes=allowed, allowed_calls=calls)
        with self.assertRaisesRegex(SourceExtractionError, "unsupported branch"):
            validate_cil_slice([{"opcode": "br.s", "operand": 4}], allowed_opcodes=allowed, allowed_calls=calls)

    def test_missing_and_invalid_localization_fail(self):
        self.assertEqual(require_localized_text({"KEY.name": "Exact"}, "KEY.name"), "Exact")
        with self.assertRaisesRegex(SourceExtractionError, "missing localization"):
            require_localized_text({}, "KEY.name")
        with self.assertRaisesRegex(SourceExtractionError, "invalid localization"):
            require_localized_text({"KEY.name": ""}, "KEY.name")


if __name__ == "__main__":
    unittest.main()
