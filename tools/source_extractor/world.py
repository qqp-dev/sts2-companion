"""Monster census and bounded source HP-expression extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .ast import evaluate_expression, validate_expression
from .canonical import witness_sha256
from .errors import SourceExtractionError
from .metadata import AssemblyMetadata, _slugify_ascii_type_name

MONSTER_NAMESPACE = "MegaCrit.Sts2.Core.Models.Monsters"
MONSTER_BASE = "MegaCrit.Sts2.Core.Models.MonsterModel"
ABSTRACT_SEGMENT = MONSTER_NAMESPACE + ".DecimillipedeSegment"
EXPECTED_TYPES = 121
EXPECTED_CONCRETE = 120

OTHER_NON_ENCOUNTER = {
    "BIG_DUMMY": "helperOrTest",
    "BYRDPIP": "helperOrObsolete",
    "MULTI_ATTACK_MOVE_MONSTER": "helperOrTest",
    "ONE_HP_MONSTER": "helperOrTest",
    "OSTY": "helperOrObsolete",
    "PAELS_LEGION": "helperOrObsolete",
    "SINGLE_ATTACK_MOVE_MONSTER": "helperOrTest",
    "TEN_HP_MONSTER": "helperOrTest",
    "THE_ADVERSARY_MK_ONE": "obsolete",
    "THE_ADVERSARY_MK_THREE": "obsolete",
    "THE_ADVERSARY_MK_TWO": "obsolete",
}


def const(value: int) -> dict[str, Any]:
    return {"kind": "constant", "value": value, "valueType": "integer"}


def state_integer(name: str, minimum: int, maximum: int | None = None) -> dict[str, Any]:
    domain: dict[str, int] = {"minimum": minimum}
    if maximum is not None:
        domain["maximum"] = maximum
    return {"domain": domain, "kind": "stateVariable", "name": name, "valueType": "integer"}


def arithmetic(operator: str, *operands: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "arithmetic", "operands": list(operands), "operator": operator, "valueType": "integer"}


def _ldc(instruction: dict[str, Any]) -> int | None:
    opcode = instruction["opcode"]
    if opcode in {"ldc.i4", "ldc.i4.s"}:
        value = instruction["operand"]
        if type(value) is not int:
            raise SourceExtractionError(f"non-integer {opcode} operand")
        return value
    values = {
        "ldc.i4.m1": -1,
        "ldc.i4.0": 0,
        "ldc.i4.1": 1,
        "ldc.i4.2": 2,
        "ldc.i4.3": 3,
        "ldc.i4.4": 4,
        "ldc.i4.5": 5,
        "ldc.i4.6": 6,
        "ldc.i4.7": 7,
        "ldc.i4.8": 8,
    }
    return values.get(opcode)


def _method_fact(record: dict[str, Any], expression: Any) -> dict[str, Any]:
    return {
        "assemblySha256": record["assemblySha256"],
        "cilInstructionsSha256": record["cilInstructionsSha256"],
        "diagnosticMetadataToken": record["diagnosticMetadataToken"],
        "metadataSignature": record["metadataSignature"],
        "methodBodySha256": record["methodBodySha256"],
        "normalizedExpression": expression,
        "normalizedExpressionSha256": witness_sha256(expression),
        "normalizedInstructionsSha256": record["normalizedInstructionsSha256"],
        "symbolSignature": record["symbolSignature"],
    }


class HpExtractor:
    """Strict stack evaluator for the reviewed v0.111.0 HP getter domain."""

    ASCENSION = "MegaCrit.Sts2.Core.Helpers.AscensionHelper::GetValueIfAscension sig:00030811a8980808"
    MIN_VIRTUAL = "MegaCrit.Sts2.Core.Models.MonsterModel::get_MinInitialHp sig:200008"

    def __init__(self, assembly: AssemblyMetadata, assembly_sha256: str):
        self.assembly = assembly
        self.assembly_sha256 = assembly_sha256
        self._cache: dict[tuple[str, str], tuple[dict[str, Any], dict[str, Any]]] = {}
        self._active: set[tuple[str, str]] = set()

    def effective_method(self, source_type: str, method_name: str) -> int:
        current = source_type
        seen: set[str] = set()
        for _ in range(32):
            if current in seen:
                raise SourceExtractionError(f"HP method inheritance cycle at {current}")
            seen.add(current)
            matches = self.assembly.find_methods(current, method_name)
            if len(matches) > 1:
                raise SourceExtractionError(f"ambiguous HP getter {current}::{method_name}")
            if matches:
                return matches[0]
            current = self.assembly.base_by_type.get(current, "")
            if not current:
                break
        raise SourceExtractionError(f"missing effective HP getter {source_type}::{method_name}")

    def named_method(self, owner: str, method_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        key = (owner, method_name)
        if key in self._cache:
            return self._cache[key]
        matches = self.assembly.find_methods(owner, method_name)
        if len(matches) != 1:
            raise SourceExtractionError(f"required HP helper {owner}::{method_name} matched {len(matches)} methods")
        return self._evaluate(key, matches[0], owner)

    def effective(self, source_type: str, method_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
        key = (source_type, method_name)
        if key in self._cache:
            return self._cache[key]
        return self._evaluate(key, self.effective_method(source_type, method_name), source_type)

    def _evaluate(self, key: tuple[str, str], method_index: int, source_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if key in self._active:
            raise SourceExtractionError(f"cycle while evaluating HP getter {key[0]}::{key[1]}")
        if len(self._active) >= 16:
            raise SourceExtractionError("HP evaluator recursion depth exceeded")
        self._active.add(key)
        try:
            record = self.assembly.method_record(method_index, self.assembly_sha256)
            stack: list[Any] = []
            returned: dict[str, Any] | None = None
            for instruction in record["instructions"]:
                opcode, operand = instruction["opcode"], instruction["operand"]
                value = _ldc(instruction)
                if value is not None:
                    stack.append(const(value))
                elif opcode == "ldarg.0":
                    stack.append(("self", source_type))
                elif opcode in {"add", "sub", "mul"}:
                    if len(stack) < 2:
                        raise SourceExtractionError(f"HP stack underflow in {record['symbolSignature']}")
                    right, left = stack.pop(), stack.pop()
                    if not isinstance(left, dict) or not isinstance(right, dict):
                        raise SourceExtractionError(f"nonnumeric HP arithmetic in {record['symbolSignature']}")
                    stack.append(arithmetic({"add": "add", "sub": "subtract", "mul": "multiply"}[opcode], left, right))
                elif opcode in {"call", "callvirt"}:
                    if operand == self.ASCENSION:
                        if len(stack) < 3:
                            raise SourceExtractionError(f"ascension stack underflow in {record['symbolSignature']}")
                        below, at_or_above, threshold = stack.pop(), stack.pop(), stack.pop()
                        if threshold.get("kind") != "constant" or type(threshold.get("value")) is not int:
                            raise SourceExtractionError(f"dynamic ascension threshold in {record['symbolSignature']}")
                        stack.append({
                            "atOrAbove": at_or_above,
                            "below": below,
                            "kind": "ascensionSelect",
                            "threshold": threshold["value"],
                            "valueType": "integer",
                        })
                    elif operand == self.MIN_VIRTUAL:
                        if not stack or stack.pop() != ("self", source_type):
                            raise SourceExtractionError(f"unsupported virtual min receiver in {record['symbolSignature']}")
                        expression, _ = self.effective(source_type, "get_MinInitialHp")
                        stack.append(expression)
                    elif operand == "MegaCrit.Sts2.Core.Models.Monsters.Axebot::get_RespawnMaxHpBonus sig:200008":
                        if not stack or stack.pop() != ("self", source_type):
                            raise SourceExtractionError("unsupported Axebot bonus receiver")
                        helper, _ = self.named_method(MONSTER_NAMESPACE + ".Axebot", "get_RespawnMaxHpBonus")
                        stack.append(helper)
                    elif operand == "MegaCrit.Sts2.Core.Models.Monsters.Axebot::get_RespawnCount sig:200008":
                        if not stack or stack.pop()[0] != "self":
                            raise SourceExtractionError("unsupported Axebot respawn receiver")
                        stack.append(state_integer("axebotRespawnCount", 0, 2))
                    elif operand == "MegaCrit.Sts2.Core.Models.Monsters.TestSubject::get_FirstFormHp sig:200008":
                        if not stack or stack.pop()[0] != "self":
                            raise SourceExtractionError("unsupported Test Subject HP receiver")
                        helper, _ = self.named_method(MONSTER_NAMESPACE + ".TestSubject", "get_FirstFormHp")
                        stack.append(helper)
                    else:
                        raise SourceExtractionError(f"unknown call on required HP slice: {operand} in {record['symbolSignature']}")
                elif opcode == "ret":
                    if len(stack) != 1 or not isinstance(stack[0], dict):
                        raise SourceExtractionError(f"invalid HP return stack in {record['symbolSignature']}")
                    returned = stack.pop()
                else:
                    raise SourceExtractionError(f"unknown opcode on required HP slice: {opcode} in {record['symbolSignature']}")
            if returned is None:
                raise SourceExtractionError(f"HP getter has no return: {record['symbolSignature']}")
            validate_expression(returned, expected_type="integer")
            result = (returned, _method_fact(record, returned))
            self._cache[key] = result
            return result
        finally:
            self._active.remove(key)


def _evaluate_a8(expression: dict[str, Any]) -> int:
    value = evaluate_expression(expression, {"ascension": 8, "axebotRespawnCount": 0})
    if type(value) is not int:
        raise SourceExtractionError("A8 HP expression did not evaluate to integer")
    return value


def extract_monster_world(dll_path: Path, assembly_sha256: str, *, assembly: AssemblyMetadata | None = None) -> dict[str, Any]:
    owns_assembly = assembly is None
    if assembly is None:
        assembly = AssemblyMetadata(Path(dll_path))
    try:
        types: list[tuple[int, Any, str]] = [
            (index, row, assembly.type_names[index])
            for index, row in enumerate(assembly.md.TypeDef.rows, 1)
            if str(row.TypeNamespace) == MONSTER_NAMESPACE
        ]
        if len(types) != EXPECTED_TYPES:
            raise SourceExtractionError(f"monster namespace type count drift: got {len(types)}, expected {EXPECTED_TYPES}")
        abstracts = [name for _, row, name in types if bool(row.Flags.tdAbstract)]
        if abstracts != [ABSTRACT_SEGMENT]:
            raise SourceExtractionError(f"abstract monster census drift: {abstracts!r}")
        concrete = [(index, row, name) for index, row, name in types if not bool(row.Flags.tdAbstract)]
        if len(concrete) != EXPECTED_CONCRETE:
            raise SourceExtractionError(f"concrete monster count drift: got {len(concrete)}")

        hp = HpExtractor(assembly, assembly_sha256)
        records: list[dict[str, Any]] = []
        getter_fixture: list[dict[str, Any]] = []
        ids: set[str] = set()
        for index, row, source_type in concrete:
            if not assembly.derives_from(source_type, MONSTER_BASE):
                raise SourceExtractionError(f"non-MonsterModel in exact monster namespace: {source_type}")
            category_type = assembly.category_type(source_type)
            if category_type != MONSTER_BASE:
                raise SourceExtractionError(f"unexpected monster ModelDb category for {source_type}: {category_type}")
            canonical_id = _slugify_ascii_type_name(str(row.TypeName))
            if canonical_id in ids:
                raise SourceExtractionError(f"duplicate canonical monster ID {canonical_id}")
            ids.add(canonical_id)
            minimum, minimum_provenance = hp.effective(source_type, "get_MinInitialHp")
            maximum, maximum_provenance = hp.effective(source_type, "get_MaxInitialHp")
            a8_minimum, a8_maximum = _evaluate_a8(minimum), _evaluate_a8(maximum)
            if a8_minimum > a8_maximum:
                raise SourceExtractionError(f"inverted A8 HP range for {canonical_id}")
            identity_witness = {"category": "MONSTER", "entry": canonical_id, "sourceType": source_type}
            range_expression = {"kind": "range", "maximum": maximum, "minimum": minimum, "valueType": "integerRange"}
            validate_expression(range_expression, expected_type="integerRange")
            record = {
                "assemblyCategory": "MONSTER",
                "canonicalId": canonical_id,
                "initialHp": {
                    "a8SinglePlayer": {"maximum": a8_maximum, "minimum": a8_minimum},
                    "expression": range_expression,
                    "provenance": {"maximum": maximum_provenance, "minimum": minimum_provenance},
                },
                "provenance": {
                    "identity": {
                        "assemblySha256": assembly_sha256,
                        "diagnosticMetadataToken": f"0x{0x02000000 | index:08x}",
                        "modelIdRule": "modelDb.typeToId.v0.111.0",
                        "semanticWitness": identity_witness,
                        "semanticWitnessSha256": witness_sha256(identity_witness),
                        "sourceType": source_type,
                    }
                },
                "sourceType": source_type,
            }
            records.append(record)
            getter_fixture.append({
                "a8SinglePlayer": {"maximum": a8_maximum, "minimum": a8_minimum},
                "canonicalId": canonical_id,
                "maximumGetter": maximum_provenance["symbolSignature"],
                "minimumGetter": minimum_provenance["symbolSignature"],
            })

        records.sort(key=lambda item: item["canonicalId"])
        getter_fixture.sort(key=lambda item: item["canonicalId"])
        return {
            "abstractTypes": abstracts,
            "concrete": records,
            "hpGetterCensus": getter_fixture,
            "otherClassifications": dict(sorted(OTHER_NON_ENCOUNTER.items())),
        }
    finally:
        if owns_assembly:
            assembly.close()
