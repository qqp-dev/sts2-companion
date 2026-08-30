from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

from source_extractor.ast import evaluate_expression, validate_expression, validate_graph, validate_operation, validate_selection
from source_extractor.canonical import canonical_json_bytes
from source_extractor.cil_safety import validate_cil_slice
from source_extractor.cil_eval import CilDataFlow, CilType, Invocation, SymbolicValue, decode_method_signature, value_expression
from source_extractor.invocations import ClosedWorldInvocationAudit
from source_extractor.initial_state import _claim_helper, _power_apply
from source_extractor.hp_pipeline import _require_exact_opcodes, _require_order, validate_hp_pipeline
from source_extractor.inheritance import attach_behavior_applicability, resolve_behavior_applicability
from source_extractor.identity import resolve_observed_identity, validate_observation_identities
from source_extractor.placement import decode_factory_collection, validate_placement
from source_extractor.behavior import _canonical_for_type, _intent_records
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

    def test_cli_remainder_is_typed_and_truncates_toward_zero(self):
        def rem(left, right):
            return {"kind": "arithmetic", "operator": "remainder", "operands": [
                {"kind": "constant", "value": left, "valueType": "integer"},
                {"kind": "constant", "value": right, "valueType": "integer"},
            ], "valueType": "integer"}
        self.assertEqual(validate_expression(rem(5, 3)), "integer")
        self.assertEqual(evaluate_expression(rem(5, 3), {}), 2)
        self.assertEqual(evaluate_expression(rem(-5, 3), {}), -2)
        with self.assertRaisesRegex(SourceExtractionError, "remainder by zero"):
            evaluate_expression(rem(1, 0), {})
        bad = rem(5, 3)
        bad["operands"].append({"kind": "constant", "value": 1, "valueType": "integer"})
        with self.assertRaisesRegex(SourceExtractionError, "operand cardinality"):
            validate_expression(bad)

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


class HpPipelineCilMutationTests(unittest.TestCase):
    @staticmethod
    def record(rows):
        return {
            "instructions": [{"opcode": opcode, "operand": operand} for opcode, operand in rows],
            "symbolSignature": "Synthetic::HpPipeline sig:00",
        }

    def test_conversion_multiplication_and_cap_order_fail_closed(self):
        helper = self.record([
            ("call", "System.Decimal::op_Implicit sig:x"),
            ("call", "System.Decimal::op_Multiply sig:x"),
            ("call", "MultiplayerScalingModel::GetMultiplayerScaling sig:x"),
            ("call", "System.Decimal::op_Multiply sig:x"),
        ])
        chain = ("Decimal::op_Implicit", "Decimal::op_Multiply", "GetMultiplayerScaling", "Decimal::op_Multiply")
        _require_order(helper, chain, label="test helper")
        removed = deepcopy(helper); removed["instructions"].pop(0)
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered"):
            _require_order(removed, chain, label="test helper")
        early = deepcopy(helper); early["instructions"][0], early["instructions"][1] = early["instructions"][1], early["instructions"][0]
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered"):
            _require_order(early, chain, label="test helper")

        setter = self.record([
            ("call", "System.Decimal::op_Explicit sig:x"),
            ("ldc.i4", 999999999),
            ("call", "System.Math::Min sig:x"),
            ("call", "Creature::set_MaxHp sig:x"),
        ])
        exact = (("call", "System.Decimal::op_Explicit sig:x"), ("ldc.i4", 999999999),
                 ("call", "System.Math::Min sig:x"), ("call", "Creature::set_MaxHp sig:x"))
        _require_exact_opcodes(setter, exact, label="test cap")
        moved = deepcopy(setter); moved["instructions"][0], moved["instructions"][1] = moved["instructions"][1], moved["instructions"][0]
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered opcode"):
            _require_exact_opcodes(moved, exact, label="test cap")
        no_explicit = deepcopy(setter); no_explicit["instructions"].pop(0)
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered opcode"):
            _require_exact_opcodes(no_explicit, exact, label="test cap")

    def test_one_player_and_int32_wire_order_fail_closed(self):
        bypass = self.record([("ldarg.2", None), ("ldc.i4.1", None), ("bne.un.s", 6)])
        branch = (("ldarg.2", None), ("ldc.i4.1", None), ("bne.un.s", 6))
        _require_exact_opcodes(bypass, branch, label="test bypass")
        missing = deepcopy(bypass); missing["instructions"].pop()
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered opcode"):
            _require_exact_opcodes(missing, branch, label="test bypass")

        wire = self.record([
            ("ldfld", "CreatureState::currentHp"), ("ldc.i4.s", 32), ("callvirt", "PacketWriter::WriteInt"),
            ("ldfld", "CreatureState::maxHp"), ("ldc.i4.s", 32), ("callvirt", "PacketWriter::WriteInt"),
        ])
        expected = tuple((row["opcode"], row["operand"]) for row in wire["instructions"])
        _require_exact_opcodes(wire, expected, label="test wire")
        decimal_wire = deepcopy(wire); decimal_wire["instructions"][2]["operand"] = "PacketWriter::WriteDecimal"
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered opcode"):
            _require_exact_opcodes(decimal_wire, expected, label="test wire")
        wrong_order = deepcopy(wire); wrong_order["instructions"][0]["operand"] = "CreatureState::maxHp"
        with self.assertRaisesRegex(SourceExtractionError, "missing or reordered opcode"):
            _require_exact_opcodes(wrong_order, expected, label="test wire")

    def test_checked_pipeline_document_and_unsupported_ast_fail(self):
        pipeline = json.loads((REPO_ROOT / "data/game-v0.111.0-source.json").read_text())["hpPipeline"]
        validate_hp_pipeline(pipeline)
        bad = deepcopy(pipeline)
        bad["assignment"]["conversion"]["kind"] = "castByName"
        with self.assertRaisesRegex(SourceExtractionError, "malformed AST|conversion"):
            validate_hp_pipeline(bad)


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


class CombatAstTests(unittest.TestCase):
    def test_reference_and_combat_query_are_closed(self):
        reference = {"kind": "reference", "reference": "MegaCrit.Sts2.Core.Models.Monsters.Aeonglass::get_EbbDamage sig:200008", "valueType": "integer"}
        self.assertEqual(validate_expression(reference, expected_type="integer"), "integer")
        compiled = {**reference, "compiled": {"kind": "constant", "value": 22, "valueType": "integer"}}
        self.assertEqual(evaluate_expression(compiled, {}), 22)
        with self.assertRaisesRegex(SourceExtractionError, "cannot evaluate unresolved method reference"):
            evaluate_expression(reference, {})
        query = {"kind": "combatQuery", "query": "powerAmount", "valueType": "integer"}
        self.assertEqual(evaluate_expression(query, {"query:powerAmount": 4}), 4)
        with self.assertRaisesRegex(SourceExtractionError, "unsupported combat query"):
            validate_expression({"kind": "combatQuery", "query": "wikiGuess", "valueType": "integer"})

    def test_operations_and_graphs_fail_closed(self):
        proof = {
            "assemblySha256": "a" * 64, "cilInstructionsSha256": "b" * 64,
            "metadataSignature": "2001", "methodBodySha256": "c" * 64,
            "normalizedInstructionsSha256": "d" * 64, "normalizedSliceSha256": "e" * 64,
            "semanticWitnessSha256": "f" * 64, "symbolSignature": "AttackCommand::FromMonster sig:2001",
        }
        op = {"kind": "attack", "operationId": "MONSTER.X#A/op/0",
              "provenance": {"semanticWitnessSha256": "a" * 64},
              "sinkSymbolSignature": "DamageCmd::Attack sig:0001",
              "target": "allOpponentsOfSourceMonster", "targetProvenance": proof,
              "value": {"kind": "constant", "value": "7", "valueType": "decimal"}}
        validate_operation(op)
        with self.assertRaisesRegex(SourceExtractionError, "unsupported operation kind"):
            validate_operation({**op, "kind": "wikiEffect"})
        for missing in ("target", "targetProvenance", "value"):
            with self.assertRaisesRegex(SourceExtractionError, "missing fields"):
                validate_operation({key: value for key, value in op.items() if key != missing})
        common = {"operationId": "MONSTER.X#A/op/1", "provenance": {}, "sourceOrder": 4}
        kill = {**common, "kind": "kill", "sinkSymbolSignature": "CreatureCmd::Kill sig:0002",
                "target": "sourceMonster", "playDeathEffects": {"kind": "constant", "value": False, "valueType": "boolean"}}
        validate_operation(kill)
        with self.assertRaisesRegex(SourceExtractionError, "missing fields"):
            validate_operation({key: value for key, value in kill.items() if key != "playDeathEffects"})
        remove = {**common, "kind": "removePower", "sinkSymbolSignature": "PowerCmd::Remove sig:0001",
                  "target": "sourceMonster", "model": "POWER.SOAR_POWER"}
        validate_operation(remove)
        runtime_remove = {**common, "kind": "removePower", "sinkSymbolSignature": "PowerCmd::Remove sig:0001",
                          "target": "runtimeSelectedPowerInstance", "modelContract": {
                              "classification": "runtimeSelectedPowerInstance", "sourceKinds": ["call"],
                              "sourceSymbolSignature": "IEnumerator::get_Current sig:2000"}}
        validate_operation(runtime_remove)
        with self.assertRaisesRegex(SourceExtractionError, "exactly one"):
            validate_operation({**runtime_remove, "model": "POWER.FAKE"})
        state_write = {**common, "kind": "stateWrite", "sinkSymbolSignature": "Monster::set_Ready sig:2001",
                       "memberSymbolSignature": "Monster::set_Ready sig:2001", "target": "sourceMonster",
                       "value": {"kind": "constant", "value": True, "valueType": "boolean"}}
        validate_operation(state_write)
        graph = {
            "canonicalMonster": "MONSTER.X", "graphId": "GRAPH.X", "sourceType": "X",
            "topology": {}, "provenance": {"semanticWitnessSha256": "b" * 64},
            "initial": "GRAPH.X/A",
            "nodes": [{"kind": "move", "nodeId": "GRAPH.X/A", "moveId": "MONSTER.X#A"}],
            "edges": [{"kind": "followUp", "from": "GRAPH.X/A", "to": "GRAPH.X/A"}],
        }
        validate_graph(graph, known_moves={"MONSTER.X#A"})
        with self.assertRaisesRegex(SourceExtractionError, "unresolved move"):
            validate_graph(graph, known_moves={"MONSTER.OTHER#A"})
        with self.assertRaisesRegex(SourceExtractionError, "unsupported graph node"):
            validate_graph({**graph, "nodes": [{"kind": "wikiPattern", "nodeId": "GRAPH.X/A"}]})


class CilSemanticEvaluatorTests(unittest.TestCase):
    @staticmethod
    def ins(opcode, operand=None, offset=None):
        row = {"opcode": opcode, "operand": operand}
        row["offsetDiagnostic"] = offset
        return row

    def flow(self, rows):
        normalized = [self.ins(op, arg, i) for i, (op, arg) in enumerate(rows)]
        evaluator = CilDataFlow(normalized)
        return evaluator, evaluator.run()

    def test_signature_controls_static_instance_and_argument_order(self):
        static = decode_method_signature("X::Sink sig:0002010808")
        instance = decode_method_signature("X::Fluent sig:20010808")
        self.assertFalse(static.has_this)
        self.assertEqual(len(static.parameters), 2)
        self.assertTrue(instance.has_this)
        evaluator, calls = self.flow([
            ("ldarg.0", None), ("ldc.i4.2", None),
            ("callvirt", "X::Fluent sig:20010808"), ("pop", None), ("ret", None),
        ])
        invocation = calls[2]
        self.assertEqual(invocation.receiver.kind, "argument")
        self.assertEqual(invocation.arguments[0].data, 2)

    def test_decoy_getter_and_constants_do_not_replace_exact_sink_arguments(self):
        _, calls = self.flow([
            ("ldarg.0", None), ("call", "X::get_Decoy sig:000008"), ("pop", None),
            ("ldc.i4.s", 99), ("pop", None),
            ("ldc.i4.5", None), ("ldc.i4.8", None),
            ("call", "X::Sink sig:0002010808"), ("ret", None),
        ])
        invocation = calls[7]
        self.assertEqual([item.data for item in invocation.arguments], [5, 8])
        self.assertEqual(value_expression(invocation.arguments[0], field_name="amount", instruction_index=7)["value"], 5)

    def test_locals_arithmetic_and_exact_conversion_are_preserved(self):
        _, calls = self.flow([
            ("ldc.i4.2", None), ("stloc.0", None), ("ldloc.0", None),
            ("ldc.i4.3", None), ("mul", None),
            ("call", "System.Decimal::op_Implicit sig:000111844908"),
            ("call", "X::Sink sig:000101118449"), ("ret", None),
        ])
        expression = value_expression(calls[6].arguments[0], field_name="amount", instruction_index=6)
        self.assertEqual(expression["kind"], "convert")
        self.assertEqual(expression["mode"], "exact")
        self.assertEqual(expression["expression"]["operator"], "multiply")
        self.assertEqual([row["value"] for row in expression["expression"]["operands"]], [2, 3])

    def test_numeric_calls_preserve_parameters_and_compile_ascension_select(self):
        ascension = "MegaCrit.Sts2.Core.Helpers.AscensionHelper::GetValueIfAscension sig:00030811a8980808"
        _, calls = self.flow([
            ("ldc.i4.s", 9), ("ldc.i4.4", None), ("ldc.i4.2", None),
            ("call", ascension), ("call", "X::Sink sig:00010108"), ("ret", None),
        ])
        expression = value_expression(calls[4].arguments[0], field_name="amount", instruction_index=4)
        self.assertEqual(expression, {
            "kind": "ascensionSelect", "threshold": 9, "valueType": "integer",
            "atOrAbove": {"kind": "constant", "value": 4, "valueType": "integer"},
            "below": {"kind": "constant", "value": 2, "valueType": "integer"},
        })

        _, calls = self.flow([
            ("ldc.r4", 2.5), ("call", "Godot.Mathf::Log sig:00010c0c"),
            ("call", "X::Sink sig:0001010c"), ("ret", None),
        ])
        expression = value_expression(calls[2].arguments[0], field_name="scale", instruction_index=2)
        self.assertEqual(expression["arguments"], [
            {"kind": "constant", "value": "2.5", "valueType": "decimal"},
        ])
        self.assertEqual(validate_expression(expression), "decimal")
        with self.assertRaisesRegex(SourceExtractionError, "required by parameterized method signature"):
            validate_expression({
                "kind": "reference", "reference": "Godot.Mathf::Log sig:00010c0c",
                "valueType": "decimal",
            })
        with self.assertRaisesRegex(SourceExtractionError, "exactly 1 expressions"):
            validate_expression({**expression, "arguments": []})
        with self.assertRaisesRegex(SourceExtractionError, "must be decimal"):
            validate_expression({**expression, "arguments": [
                {"kind": "constant", "value": 2, "valueType": "integer"},
            ]})

    def test_numeric_call_with_unprojectable_parameter_fails_closed(self):
        _, calls = self.flow([
            ("ldarg.0", None), ("call", "X::Numeric sig:00010808"),
            ("call", "X::Sink sig:00010108"), ("ret", None),
        ])
        with self.assertRaisesRegex(SourceExtractionError, "unresolved amount expression"):
            value_expression(calls[2].arguments[0], field_name="amount", instruction_index=2)

    def test_equal_join_resolves_but_nonunique_join_fails_closed(self):
        def branch(right):
            rows = [
                self.ins("ldc.i4.1", None, 0), self.ins("brtrue.s", 4, 1),
                self.ins("ldc.i4.2", None, 2), self.ins("br.s", 5, 3),
                self.ins(f"ldc.i4.{right}", None, 4),
                self.ins("call", "X::Sink sig:00010108", 5), self.ins("ret", None, 6),
            ]
            flow = CilDataFlow(rows); return flow.run()[5].arguments[0]
        equal = value_expression(branch(2), field_name="joined amount", instruction_index=5)
        self.assertEqual(equal["value"], 2)
        with self.assertRaisesRegex(SourceExtractionError, "non-unique joined amount"):
            value_expression(branch(3), field_name="joined amount", instruction_index=5)

    def test_unknown_signature_opcode_type_and_stack_fail_closed(self):
        with self.assertRaisesRegex(SourceExtractionError, "no required metadata signature"):
            self.flow([("call", "X::NoSignature"), ("ret", None)])
        with self.assertRaisesRegex(SourceExtractionError, "unknown stack-affecting opcode"):
            self.flow([("localloc", None), ("ret", None)])
        with self.assertRaisesRegex(SourceExtractionError, "stack underflow"):
            self.flow([("call", "X::Sink sig:00010108"), ("ret", None)])
        _, calls = self.flow([("ldarg.0", None), ("call", "X::Sink sig:00010108"), ("ret", None)])
        with self.assertRaisesRegex(SourceExtractionError, "unresolved amount expression"):
            value_expression(calls[1].arguments[0], field_name="amount", instruction_index=1)

    def test_source_field_requires_supplied_context_and_trailing_enum_is_distinct(self):
        source = {"kind": "sourceField", "symbol": "X::counter", "valueType": "integer"}
        self.assertEqual(validate_expression(source), "integer")
        with self.assertRaisesRegex(SourceExtractionError, "missing state input"):
            evaluate_expression(source, {})
        self.assertEqual(evaluate_expression(source, {"field:X::counter": 4}), 4)
        _, calls = self.flow([
            ("ldc.i4.7", None), ("ldc.i4.8", None), ("ldnull", None), ("ldc.i4.0", None),
            ("call", "X::Gain sig:00040108081c02"), ("ret", None),
        ])
        self.assertEqual(calls[4].arguments[0].data, 7)
        self.assertEqual(calls[4].arguments[1].data, 8)

    def test_intent_constructor_uses_signature_stack_and_preserves_func_delegate(self):
        target = "X::<GenerateMoveStateMachine>b__0 sig:200008"
        intent_ctor = "X.Intents.MultiAttackIntent::.ctor sig:20020108151281bd0108"
        rows = [
            self.ins("ldc.i4.1", None, 0),
            self.ins("newarr", "X.Intents.AbstractIntent", 1),
            self.ins("dup", None, 2),
            self.ins("ldc.i4.0", None, 3),  # array index, never a ctor argument
            self.ins("ldarg.0", None, 4),
            self.ins("call", "X::get_Damage sig:200008", 5),
            self.ins("ldarg.0", None, 6),
            self.ins("ldftn", target, 7),
            self.ins("newobj", "<TypeSpec:FuncInt>::.ctor sig:2002011c18", 8),
            self.ins("newobj", intent_ctor, 9),
            self.ins("stelem.ref", None, 10),
            self.ins("ret", None, 11),
        ]

        def method_record(symbol, instructions):
            return {
                "assemblySha256": "a" * 64,
                "cilInstructionsSha256": "b" * 64,
                "diagnosticMetadataToken": "0x06000001",
                "instructions": instructions,
                "metadataSignature": symbol.split(" sig:", 1)[1],
                "methodBodySha256": "c" * 64,
                "normalizedInstructionsSha256": "d" * 64,
                "symbolSignature": symbol,
            }

        target_rows = [
            self.ins("ldarg.0", None, 0),
            self.ins("call", "X::get_Count sig:200008", 1),
            self.ins("ret", None, 2),
        ]
        target_record = method_record(target, target_rows)

        class FakeAssembly:
            @staticmethod
            def find_methods(owner, name):
                return [1] if (owner, name) == ("X", "<GenerateMoveStateMachine>b__0") else []

            @staticmethod
            def method_symbol(index):
                return target

            @staticmethod
            def method_record(index, assembly_sha256):
                return target_record

        record = method_record("X::GenerateMoveStateMachine sig:200001", rows)
        calls = CilDataFlow(rows).run()
        intents = _intent_records(
            rows, record, invocations=calls, assembly=FakeAssembly(), assembly_sha256="a" * 64
        )
        self.assertEqual(len(intents), 1)
        self.assertEqual(intents[0]["constructorSymbolSignature"], intent_ctor)
        damage, count = intents[0]["arguments"]
        self.assertEqual(damage["reference"], "X::get_Damage sig:200008")
        self.assertEqual(count["kind"], "sourceDelegate")
        self.assertEqual(count["binding"], {"argumentIndex": 0, "kind": "methodArgument"})
        self.assertEqual(count["targetMethod"]["symbolSignature"], target)
        self.assertEqual(count["resultExpression"]["reference"], "X::get_Count sig:200008")
        self.assertNotIn({"kind": "constant", "value": 0, "valueType": "integer"}, intents[0]["arguments"])

        malformed = [dict(row) for row in rows]
        malformed[7] = self.ins("ldnull", None, 7)
        with self.assertRaisesRegex(SourceExtractionError, "delegate target"):
            _intent_records(
                malformed, method_record("X::GenerateMoveStateMachine sig:200001", malformed),
                invocations=CilDataFlow(malformed).run(), assembly=FakeAssembly(),
                assembly_sha256="a" * 64,
            )

    def test_required_attack_target_evidence_cannot_be_omitted(self):
        operation = {"kind": "attack", "operationId": "X/op/0", "provenance": {},
                     "sinkSymbolSignature": "X::Attack sig:0001",
                     "value": {"kind": "constant", "value": "1", "valueType": "decimal"}}
        with self.assertRaisesRegex(SourceExtractionError, "missing fields"):
            validate_operation(operation)



class InitialPowerApplyContractTests(unittest.TestCase):
    GENERIC = (
        "MegaCrit.Sts2.Core.Commands.PowerCmd::Apply "
        "sig:10010615128221011e0012a64c12a7e411844912a7e41288b802 "
        "generic:MegaCrit.Sts2.Core.Models.Powers.ArtifactPower"
    )
    CUSTOM = "MegaCrit.Sts2.Core.Commands.PowerCmd::Apply sig:000712812112a64c1288f412a7e411844912a7e41288b802"

    @staticmethod
    def value(kind, data=None, operands=(), cil="class", origins=frozenset({0})):
        return SymbolicValue(kind, CilType(cil), data, tuple(operands), origins)

    def setUp(self):
        self.record = {"instructions": [{"opcode": "nop", "operand": None} for _ in range(20)]}
        model = self.value("field", "Synthetic::<>4__this")
        self.target = self.value(
            "call", "MegaCrit.Sts2.Core.Models.MonsterModel::get_Creature sig:200012a7e4", (model,)
        )
        integer = self.value("constant", 3, cil="i4")
        self.amount = self.value("new", "System.Decimal::.ctor sig:20010108", (integer,), cil="valuetype")
        self.context = self.value("new", "SyntheticContext::.ctor sig:200001")
        self.null = self.value("null")
        self.false = self.value("constant", 0, cil="i4")

    def invocation(self, symbol, arguments):
        return Invocation(10, symbol, decode_method_signature(symbol), tuple(arguments), None, None)

    def test_generic_and_custom_overloads_preserve_exact_model_target_and_amount_positions(self):
        generic = self.invocation(self.GENERIC, [self.context, self.target, self.amount, self.target, self.null, self.false])
        model, target, amount, _ = _power_apply(generic, self.record)
        self.assertEqual((model, target), ("POWER.ARTIFACT_POWER", "sourceMonster"))
        self.assertEqual(amount["expression"]["value"], 3)

        power = self.value(
            "call",
            "MegaCrit.Sts2.Core.Models.ModelDb::Power sig:1001001e00 generic:MegaCrit.Sts2.Core.Models.Powers.WitheringPresencePower",
        )
        custom = self.invocation(self.CUSTOM, [self.context, power, self.target, self.amount, self.target, self.null, self.false])
        model, target, amount, _ = _power_apply(custom, self.record)
        self.assertEqual((model, target, amount["expression"]["value"]),
                         ("POWER.WITHERING_PRESENCE_POWER", "sourceMonster", 3))

    def conditional_case(self):
        getter = "MegaCrit.Sts2.Core.Combat.ICombatState::get_CurrentSide sig:200011aa6c"
        instructions = [
            {"opcode": "callvirt", "operand": getter},
            {"opcode": "ldc.i4.2", "operand": None},
            {"opcode": "beq.s", "operand": 5},
            {"opcode": "ldc.i4.1", "operand": None},
            {"opcode": "br.s", "operand": 6},
            {"opcode": "ldc.i4.2", "operand": None},
            {"opcode": "nop", "operand": None},
            {"opcode": "nop", "operand": None},
            {"opcode": "nop", "operand": None},
            {"opcode": "nop", "operand": None},
            {"opcode": "call", "operand": self.GENERIC},
        ]
        one = self.value("constant", 1, cil="i4", origins=frozenset({3}))
        two = self.value("constant", 2, cil="i4", origins=frozenset({5}))
        joined = self.value("join", "stack[0] at IL_0006", (one, two), cil="i4", origins=frozenset({3, 5}))
        amount = self.value("convert", "conv.r4", (joined,), cil="r4", origins=frozenset({3, 5, 6}))
        invocation = self.invocation(
            self.GENERIC,
            [self.context, self.target, amount, self.target, self.null, self.false],
        )
        return invocation, {"instructions": instructions}

    @staticmethod
    def branch_literal(expression):
        while expression["kind"] == "convert":
            expression = expression["expression"]
        return expression["value"]

    def test_current_side_join_extracts_exact_comparison_and_cfg_arm_mapping(self):
        invocation, record = self.conditional_case()
        model, target, amount, origins = _power_apply(
            invocation, record, current_side_domain={"minimum": 0, "maximum": 2}
        )
        self.assertEqual((model, target), ("POWER.ARTIFACT_POWER", "sourceMonster"))
        self.assertEqual(amount["condition"], {
            "kind": "compare",
            "operator": "equal",
            "left": {
                "kind": "stateVariable",
                "name": "combat.currentSide",
                "valueType": "integer",
                "domain": {"minimum": 0, "maximum": 2},
            },
            "right": {"kind": "constant", "value": 2, "valueType": "integer"},
            "valueType": "boolean",
        })
        self.assertEqual(self.branch_literal(amount["whenTrue"]), 2)
        self.assertEqual(self.branch_literal(amount["whenFalse"]), 1)
        self.assertTrue({0, 1, 2, 3, 4, 5, 6, 10}.issubset(origins))

    def test_current_side_join_requires_source_derived_enum_domain(self):
        invocation, record = self.conditional_case()
        with self.assertRaisesRegex(SourceExtractionError, "lacks a derived CurrentSide domain"):
            _power_apply(invocation, record)

    def test_current_side_join_reads_changed_compare_instead_of_inventing_one(self):
        invocation, record = self.conditional_case()
        record["instructions"][1]["opcode"] = "ldc.i4.7"
        _, _, amount, _ = _power_apply(
            invocation, record, current_side_domain={"minimum": 0, "maximum": 2}
        )
        self.assertEqual(amount["condition"]["right"]["value"], 7)
        self.assertEqual(self.branch_literal(amount["whenTrue"]), 2)
        self.assertEqual(self.branch_literal(amount["whenFalse"]), 1)

    def test_current_side_join_rejects_unproved_predicate_or_arm_mapping(self):
        mutations = (
            (lambda record: record["instructions"][0].__setitem__("operand", "Other::get_CurrentSide sig:200008"), "one exact CurrentSide comparison"),
            (lambda record: record["instructions"][2].__setitem__("opcode", "bgt.s"), "one exact CurrentSide comparison"),
            (lambda record: record["instructions"][2].__setitem__("operand", 99), "branch target"),
        )
        for mutate, pattern in mutations:
            invocation, record = self.conditional_case()
            mutate(record)
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(SourceExtractionError, pattern):
                    _power_apply(
                invocation, record, current_side_domain={"minimum": 0, "maximum": 2}
            )

        invocation, record = self.conditional_case()
        joined = invocation.arguments[2].operands[0]
        ambiguous_join = self.value(
            "join", joined.data, (
                self.value("constant", 1, cil="i4", origins=frozenset({3, 5})),
                self.value("constant", 2, cil="i4", origins=frozenset({3, 5})),
            ), cil="i4", origins=frozenset({3, 5}),
        )
        amount = self.value(
            "convert", "conv.r4", (ambiguous_join,), cil="r4", origins=frozenset({3, 5, 6})
        )
        args = list(invocation.arguments); args[2] = amount
        invocation = self.invocation(self.GENERIC, args)
        with self.assertRaisesRegex(SourceExtractionError, "one exact CurrentSide comparison"):
            _power_apply(
                        invocation, record, current_side_domain={"minimum": 0, "maximum": 2}
                    )

    def test_helper_cycle_or_repeated_traversal_fails_closed(self):
        seen = set()
        _claim_helper(seen, 7, "Monster::Sleep sig:2000128121")
        with self.assertRaisesRegex(SourceExtractionError, "helper cycle/repeated helper"):
            _claim_helper(seen, 7, "Monster::Sleep sig:2000128121")

    def test_unknown_overload_changed_argument_order_and_unresolved_target_fail(self):
        unknown_symbol = "MegaCrit.Sts2.Core.Commands.PowerCmd::Apply sig:0002010808"
        with self.assertRaisesRegex(SourceExtractionError, "unknown PowerCmd.Apply overload"):
            _power_apply(self.invocation(unknown_symbol, [self.false, self.false]), self.record)
        changed = self.invocation(self.GENERIC, [self.context, self.amount, self.target, self.target, self.null, self.false])
        with self.assertRaisesRegex(SourceExtractionError, "recipient|unresolved"):
            _power_apply(changed, self.record)
        unresolved = self.value("unresolved", "missing target join")
        broken = self.invocation(self.GENERIC, [self.context, unresolved, self.amount, self.target, self.null, self.false])
        with self.assertRaisesRegex(SourceExtractionError, "missing target join"):
            _power_apply(broken, self.record)

class PlacementExtractionTests(unittest.TestCase):
    def test_literal_registry_count_order_and_unknown_structure_fail_closed(self):
        record = {
            "symbolSignature": "Game.Act::GenerateAllEncounters sig:x",
            "instructions": [
                {"opcode": "ldc.i4.2", "operand": None},
                {"opcode": "newarr", "operand": "Game.Encounter"},
                {"opcode": "call", "operand": "Game.Db::Encounter sig:x generic:Game.Encounter.A"},
                {"opcode": "call", "operand": "Game.Db::Encounter sig:x generic:Game.Encounter.B"},
            ],
        }
        self.assertEqual(
            decode_factory_collection(record, factory="Game.Db::Encounter ", element_type="Game.Encounter"),
            ["Game.Encounter.A", "Game.Encounter.B"],
        )
        broken = json.loads(json.dumps(record))
        broken["instructions"][0]["opcode"] = "ldc.i4.1"
        with self.assertRaisesRegex(SourceExtractionError, "cardinality mismatch"):
            decode_factory_collection(broken, factory="Game.Db::Encounter ", element_type="Game.Encounter")
        ambiguous = json.loads(json.dumps(record))
        ambiguous["instructions"][3]["operand"] += " trailing"
        with self.assertRaisesRegex(SourceExtractionError, "ambiguous generic"):
            decode_factory_collection(ambiguous, factory="Game.Db::Encounter ", element_type="Game.Encounter")

    @staticmethod
    def placement_fixture():
        return {
            "acts": [
                {"canonicalId": "ACT.A"}, {"canonicalId": "ACT.B"},
            ],
            "pools": [
                {
                    "actId": "ACT.A", "canonicalMembers": [{"weight": {"kind": "uniform"}}],
                    "poolId": "POOL.A", "selection": {"kind": "uniformSingle"},
                },
                {
                    "actId": "ACT.B", "canonicalMembers": [{"weight": {"kind": "none"}}],
                    "poolId": "POOL.B", "selection": {"kind": "shuffleThenCyclicEligible"},
                },
            ],
            "encounters": [{
                "canonicalEncounter": "ENCOUNTER.X", "classification": "poolMember",
                "memberships": [
                    {"actId": "ACT.A", "poolId": "POOL.A", "conditions": []},
                    {
                        "actId": "ACT.B", "poolId": "POOL.B",
                        "conditions": [{
                            "kind": "decodedSourcePredicate", "provenance": {},
                            "condition": {"kind": "always"},
                        }],
                    },
                ],
            }],
            "eventLinkage": [],
            "sourceDenominators": {
                "acts": 2, "currentEncounterMemberships": 2,
                "currentEncounterPlacements": 1, "eventEncounterLinks": 0,
                "poolRegistryMembers": 2, "pools": 2,
            },
        }

    def test_multiple_memberships_preserved_and_unknown_nodes_rejected(self):
        fixture = self.placement_fixture()
        validate_placement(fixture)
        broken = json.loads(json.dumps(fixture))
        broken["pools"][0]["selection"]["kind"] = "suffixInferredPool"
        with self.assertRaisesRegex(SourceExtractionError, "unknown placement selection"):
            validate_placement(broken)
        broken = json.loads(json.dumps(fixture))
        broken["encounters"][0]["memberships"][1]["conditions"][0]["condition"]["kind"] = "fuzzyCondition"
        with self.assertRaisesRegex(SourceExtractionError, "unknown placement condition"):
            validate_placement(broken)
        broken = json.loads(json.dumps(fixture))
        broken["pools"][0]["canonicalMembers"][0]["weight"]["kind"] = "guessed"
        with self.assertRaisesRegex(SourceExtractionError, "unknown placement weight"):
            validate_placement(broken)


class ObservationIdentityTests(unittest.TestCase):
    @staticmethod
    def fixture():
        return {
            "aliases": [],
            "entries": [
                {"observedId": "MONSTER.EGG", "canonicalMonster": "MONSTER.EGG", "identityKind": "model", "sourceType": "Game.Monsters.Egg"},
                {"observedId": "MONSTER.FRONT", "canonicalMonster": "MONSTER.FRONT", "identityKind": "model", "sourceType": "Game.Monsters.Front"},
            ],
            "matchingPolicy": {
                "caseSensitive": True, "fuzzyMatching": False, "prefixStripping": False,
                "wirePrefixes": [{"category": "monsterModel", "prefix": "MONSTER.", "source": "ModelId.Category"}],
            },
            "observationContracts": [
                {"contractId": "currentRunSave.monsterIds", "identityKind": "model", "wireForm": "MONSTER.<ModelId.Entry>"},
                {"contractId": "currentRunSave.modelIdRead", "identityKind": "model", "wireForm": "<ModelId.Category>.<ModelId.Entry>"},
                {"contractId": "gameResources.monsterVisualsPath", "identityKind": "resourceRepresentationOfModel", "wireForm": "resource"},
                {"contractId": "combatLog.encounterStart", "identityKind": "encounterEntry", "wireForm": "entry"},
                {"contractId": "combatLog.encounterWin", "identityKind": "encounterModel", "wireForm": "model"},
            ],
            "resourceRepresentations": [
                {"canonicalMonster": "MONSTER.EGG", "identityKind": "resourceRepresentationOfModel", "resourceId": "res://scenes/creature_visuals/egg.tscn", "transformation": {"caseTransform": "ToLowerInvariant", "input": "ModelId.Entry", "pathPrefix": "res://scenes/creature_visuals/", "pathSuffix": ".tscn"}},
                {"canonicalMonster": "MONSTER.FRONT", "identityKind": "resourceRepresentationOfModel", "resourceId": "res://scenes/creature_visuals/front.tscn", "transformation": {"caseTransform": "ToLowerInvariant", "input": "ModelId.Entry", "pathPrefix": "res://scenes/creature_visuals/", "pathSuffix": ".tscn"}},
            ],
            "sourceConclusions": [],
            "sourceDenominators": {
                "currentReachableModels": 2, "observableIds": 2, "resourceRepresentations": 2,
                "sourceDeclaredCurrentAliases": 0, "stateObservationContracts": 1,
            },
            "stateObservationContracts": [{
                "canonicalMonster": "MONSTER.EGG", "identityKind": "stateOfModel", "stateId": "MONSTER.EGG#HATCHED",
                "observation": {
                    "distinguishability": "notDistinguishableFromModelIdAlone",
                    "emittedModelId": "MONSTER.EGG", "separateStateIdEmitted": False,
                },
            }],
        }

    def test_exact_only_lookup_rejects_prefix_case_and_lookalike_fallback(self):
        fixture = self.fixture()
        validate_observation_identities(fixture, reachable_models={"MONSTER.EGG", "MONSTER.FRONT"})
        self.assertEqual(resolve_observed_identity(fixture, "MONSTER.FRONT")["canonicalMonster"], "MONSTER.FRONT")
        for lookalike in ("FRONT", "monster.front", "MONSTER_FRONT", "MONSTER.FRONT ", "MONSTER.FRONT_EXTRA", "res://scenes/creature_visuals/front.tscn"):
            self.assertIsNone(resolve_observed_identity(fixture, lookalike), lookalike)

    def test_alias_collision_missing_target_and_normalization_policy_fail(self):
        fixture = self.fixture()
        broken = json.loads(json.dumps(fixture))
        broken["entries"][1]["observedId"] = "MONSTER.EGG"
        with self.assertRaisesRegex(SourceExtractionError, "collision"):
            validate_observation_identities(broken, reachable_models={"MONSTER.EGG", "MONSTER.FRONT"})
        broken = json.loads(json.dumps(fixture))
        broken["stateObservationContracts"][0]["canonicalMonster"] = "MONSTER.MISSING"
        with self.assertRaisesRegex(SourceExtractionError, "missing target"):
            validate_observation_identities(broken, reachable_models={"MONSTER.EGG", "MONSTER.FRONT"})
        broken = json.loads(json.dumps(fixture))
        broken["matchingPolicy"]["fuzzyMatching"] = True
        with self.assertRaisesRegex(SourceExtractionError, "normalization"):
            validate_observation_identities(broken, reachable_models={"MONSTER.EGG", "MONSTER.FRONT"})
        broken = json.loads(json.dumps(fixture))
        broken["aliases"] = [{"observedId": "MONSTER.EG", "target": "MONSTER.EGG"}]
        with self.assertRaisesRegex(SourceExtractionError, "no source-declared aliases"):
            validate_observation_identities(broken, reachable_models={"MONSTER.EGG", "MONSTER.FRONT"})


class BehaviorInheritanceTests(unittest.TestCase):
    def test_behavior_owner_identity_requires_exact_reachable_descendants(self):
        class Assembly:
            bases = {
                "Game.Monsters.Front": "Game.Monsters.SpecialSegment",
                "Game.Monsters.SpecialSegment": "Game.Monsters.SharedSegment",
                "Game.Monsters.SharedSegmentLookalike": "System.Object",
            }

            def derives_from(self, source, ancestor):
                seen = set()
                while source in self.bases:
                    if source in seen:
                        raise SourceExtractionError("cycle")
                    seen.add(source)
                    source = self.bases[source]
                    if source == ancestor:
                        return True
                return False

        source_to_model = {
            "Game.Monsters.Front": "MONSTER.FRONT",
            "Game.Monsters.SharedSegmentLookalike": "MONSTER.LOOKALIKE",
        }
        self.assertEqual(
            _canonical_for_type(
                "Game.Monsters.SharedSegment", source_to_model, Assembly(), {"MONSTER.FRONT", "MONSTER.LOOKALIKE"}
            ),
            "MONSTER.SHARED_SEGMENT",
        )
        with self.assertRaisesRegex(SourceExtractionError, "no canonical model or reachable concrete descendants"):
            _canonical_for_type(
                "Game.Monsters.Shared", source_to_model, Assembly(), {"MONSTER.FRONT", "MONSTER.LOOKALIKE"}
            )

    def models(self):
        return [
            {"sourceType": "Game.Monsters.Front", "canonicalId": "FRONT"},
            {"sourceType": "Game.Monsters.Middle", "canonicalId": "MIDDLE"},
            {"sourceType": "Game.Monsters.LookalikeSegment", "canonicalId": "LOOKALIKE"},
        ]

    def test_multi_level_exact_inheritance_and_lookalike_rejection(self):
        relations = resolve_behavior_applicability(
            base_by_type={
                "Game.Monsters.Front": "Game.Monsters.SpecialSegment",
                "Game.Monsters.SpecialSegment": "Game.Monsters.SharedSegment",
                "Game.Monsters.Middle": "Game.Monsters.SharedSegment",
                "Game.Monsters.SharedSegment": "System.Object",
                "Game.Monsters.LookalikeSegment": "System.Object",
            },
            behavior_owner_types=["Game.Monsters.SharedSegment"],
            concrete_models=self.models(),
            reachable_models={"MONSTER.FRONT", "MONSTER.MIDDLE", "MONSTER.LOOKALIKE"},
            assembly_sha256="a" * 64,
        )
        self.assertEqual(
            [row["canonicalMonster"] for row in relations[0]["applicableConcreteModels"]],
            ["MONSTER.FRONT", "MONSTER.MIDDLE"],
        )
        self.assertEqual(
            relations[0]["applicableConcreteModels"][0]["inheritancePath"],
            ["Game.Monsters.Front", "Game.Monsters.SpecialSegment", "Game.Monsters.SharedSegment"],
        )

    def test_attach_is_one_to_many_for_every_graph_and_registration(self):
        relation = resolve_behavior_applicability(
            base_by_type={
                "Game.Monsters.Front": "Game.Monsters.SharedSegment",
                "Game.Monsters.Middle": "Game.Monsters.SharedSegment",
                "Game.Monsters.SharedSegment": "System.Object",
            },
            behavior_owner_types=["Game.Monsters.SharedSegment"],
            concrete_models=self.models()[:2],
            reachable_models={"MONSTER.FRONT", "MONSTER.MIDDLE"},
            assembly_sha256="b" * 64,
        )
        behavior = {
            "graphs": [{"sourceType": "Game.Monsters.SharedSegment"}],
            "registrations": [{"sourceType": "Game.Monsters.SharedSegment"}],
        }
        attach_behavior_applicability(behavior, relation)
        expected = ["MONSTER.FRONT", "MONSTER.MIDDLE"]
        self.assertEqual(behavior["graphs"][0]["applicableConcreteModels"], expected)
        self.assertEqual(behavior["registrations"][0]["applicableConcreteModels"], expected)

    def test_cycles_missing_bases_duplicates_and_unresolved_owners_fail(self):
        kwargs = dict(
            behavior_owner_types=["Game.Monsters.SharedSegment"],
            concrete_models=self.models()[:1],
            reachable_models={"MONSTER.FRONT"},
            assembly_sha256="c" * 64,
        )
        with self.assertRaisesRegex(SourceExtractionError, "cycle"):
            resolve_behavior_applicability(
                base_by_type={
                    "Game.Monsters.Front": "Game.Monsters.SharedSegment",
                    "Game.Monsters.SharedSegment": "Game.Monsters.Front",
                }, **kwargs
            )
        with self.assertRaisesRegex(SourceExtractionError, "unresolved base"):
            resolve_behavior_applicability(
                base_by_type={"Game.Monsters.Front": "Missing.Base"}, **kwargs
            )
        with self.assertRaisesRegex(SourceExtractionError, "no proven"):
            resolve_behavior_applicability(
                base_by_type={
                    "Game.Monsters.Front": "System.Object",
                    "Game.Monsters.SharedSegment": "System.Object",
                }, **kwargs
            )
        with self.assertRaisesRegex(SourceExtractionError, "duplicate behavior owner"):
            resolve_behavior_applicability(
                base_by_type={
                    "Game.Monsters.Front": "Game.Monsters.SharedSegment",
                    "Game.Monsters.SharedSegment": "System.Object",
                }, behavior_owner_types=["Game.Monsters.SharedSegment"] * 2,
                concrete_models=self.models()[:1], reachable_models={"MONSTER.FRONT"},
                assembly_sha256="d" * 64,
            )


class ClosedWorldInvocationTests(unittest.TestCase):
    @staticmethod
    def ins(opcode, operand, offset):
        return {"offsetDiagnostic": offset, "opcode": opcode, "operand": operand}

    @classmethod
    def invocation(cls, rows, index):
        return CilDataFlow(rows).run()[index]

    @staticmethod
    def record(symbol, rows):
        return {
            "assemblySha256": "a" * 64,
            "cilInstructionsSha256": "b" * 64,
            "diagnosticMetadataToken": "0x06000001",
            "instructions": rows,
            "metadataSignature": symbol.split(" sig:", 1)[1],
            "methodBodySha256": "c" * 64,
            "normalizedInstructionsSha256": "d" * 64,
            "symbolSignature": symbol,
        }

    class EmptyAssembly:
        md = SimpleNamespace(MethodDef=SimpleNamespace(rows=[]), InterfaceImpl=SimpleNamespace(rows=[]))
        type_names = {}

        @staticmethod
        def find_methods(owner, member): return []

        @staticmethod
        def derives_from(owner, ancestor): return False

    def test_unknown_gameplay_and_framework_calls_fail_with_stable_evidence(self):
        unknown_rows = [self.ins("call", "MegaCrit.Sts2.Core.Commands.NewGameplayCmd::DoThing sig:000001", 0),
                        self.ins("ret", None, 1)]
        invocation = self.invocation(unknown_rows, 0)
        record = self.record("X::MoveNext sig:200001", unknown_rows)
        messages = []
        for _ in range(2):
            audit = ClosedWorldInvocationAudit(self.EmptyAssembly(), "a" * 64, {})
            with self.assertRaises(SourceExtractionError) as caught:
                audit.classify(invocation, record, "MONSTER.X#MOVE")
            messages.append(str(caught.exception))
        self.assertEqual(messages[0], messages[1])
        self.assertRegex(messages[0], r"^UNRESOLVED\.INVOCATION\.[0-9a-f]{64}:")
        self.assertIn("unknown command/effect API", messages[0])

        godot_rows = [self.ins("ldarg.0", None, 0),
                      self.ins("callvirt", "Godot.Node::UnknownGameplayishCall sig:200001", 1),
                      self.ins("ret", None, 2)]
        godot_call = self.invocation(godot_rows, 1)
        with self.assertRaisesRegex(SourceExtractionError, "unclassified invocation declaration"):
            ClosedWorldInvocationAudit(self.EmptyAssembly(), "a" * 64, {}).classify(
                godot_call, self.record("X::MoveNext sig:200001", godot_rows), "MONSTER.X#MOVE"
            )

    def test_narrow_presentation_call_is_counted_not_ignored(self):
        rows = [self.ins("ldstr", "string:sfx", 0), self.ins("ldc.r4", 0.5, 1),
                self.ins("call", "MegaCrit.Sts2.Core.Commands.SfxCmd::Play sig:0002010e0c", 2),
                self.ins("ret", None, 3)]
        audit = ClosedWorldInvocationAudit(self.EmptyAssembly(), "a" * 64, {})
        decision = audit.classify(self.invocation(rows, 2), self.record("X::MoveNext sig:200001", rows), "MONSTER.X#MOVE")
        self.assertEqual(decision["classification"], "provenNonGameplayPlumbing")
        self.assertEqual(decision["role"], "presentation")
        self.assertEqual(audit.summary()["denominator"], 1)
        self.assertEqual(audit.summary()["unresolved"], 0)

    def helper_assembly(self, nested_symbol):
        owner = "MegaCrit.Sts2.Core.Models.Monsters.FixtureMonster"
        helper_symbol = owner + "::Helper sig:200001"
        if "Kill" in nested_symbol:
            helper_rows = [self.ins("ldnull", None, 0), self.ins("ldc.i4.0", None, 1),
                           self.ins("call", nested_symbol, 2), self.ins("pop", None, 3), self.ins("ret", None, 4)]
        else:
            helper_rows = [self.ins("call", nested_symbol, 0), self.ins("ret", None, 1)]
        helper_record = self.record(helper_symbol, helper_rows)
        flags = SimpleNamespace(mdSpecialName=False, mdAbstract=False)

        class FakeAssembly(self.EmptyAssembly):
            md = SimpleNamespace(MethodDef=SimpleNamespace(rows=[SimpleNamespace(Flags=flags)]),
                                 InterfaceImpl=SimpleNamespace(rows=[]))
            type_names = {1: owner}

            @staticmethod
            def find_methods(candidate_owner, member):
                return [1] if (candidate_owner, member) == (owner, "Helper") else []

            @staticmethod
            def method_symbol(index): return helper_symbol

            @staticmethod
            def method_record(index, assembly_sha256): return helper_record

        outer_rows = [self.ins("ldarg.0", None, 0), self.ins("call", helper_symbol, 1), self.ins("ret", None, 2)]
        return FakeAssembly(), outer_rows

    def test_helper_effects_are_traversed_and_unknown_nested_commands_fail(self):
        kill = "MegaCrit.Sts2.Core.Commands.CreatureCmd::Kill sig:000212812112a7e402"
        assembly, rows = self.helper_assembly(kill)
        audit = ClosedWorldInvocationAudit(assembly, "a" * 64, {})
        decision = audit.classify(self.invocation(rows, 1), self.record("X::MoveNext sig:200001", rows), "MONSTER.X#MOVE")
        self.assertEqual(decision["classification"], "traversedGameplayHelper")
        effects = decision["evidence"]["gameplayEffects"]
        self.assertEqual([(row["kind"], row["sinkSymbolSignature"]) for row in effects], [("kill", kill)])
        self.assertEqual(decision["evidence"]["nestedInvocationSites"], 1)
        helper_summary = audit.summary()
        self.assertEqual((helper_summary["directDenominator"], helper_summary["helperDenominator"]), (1, 1))

        unknown = "MegaCrit.Sts2.Core.Commands.NewGameplayCmd::HiddenEffect sig:000001"
        assembly, rows = self.helper_assembly(unknown)
        with self.assertRaisesRegex(SourceExtractionError, r"UNRESOLVED\.INVOCATION\.[0-9a-f]{64}.*unknown command/effect API"):
            ClosedWorldInvocationAudit(assembly, "a" * 64, {}).classify(
                self.invocation(rows, 1), self.record("X::MoveNext sig:200001", rows), "MONSTER.X#MOVE"
            )


if __name__ == "__main__":
    unittest.main()
