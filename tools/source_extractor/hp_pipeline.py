"""Source-derived monster HP selection, Decimal arithmetic, assignment, and wire chain.

This E2b slice is deliberately separate from :mod:`scaling`: the arithmetic
helper returns Decimal with no rounding, while this module proves the later
explicit Decimal-to-Int32 assignment conversion and integer storage.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .ast import evaluate_expression, validate_expression
from .canonical import witness_sha256
from .errors import SourceExtractionError
if TYPE_CHECKING:
    from .metadata import AssemblyMetadata

_HP_CREATURE = "MegaCrit.Sts2.Core.Entities.Creatures.Creature"
_HP_COMBAT_STATE = "MegaCrit.Sts2.Core.Combat.CombatState"
_HP_COMMAND = "MegaCrit.Sts2.Core.Commands.CreatureCmd"
_HP_NET_STATE = "MegaCrit.Sts2.Core.Entities.Multiplayer.NetFullCombatState"
_HP_NET_CREATURE = _HP_NET_STATE + "+CreatureState"
_HP_TARGET_MEMBERS = {
    "ScaleHpForMultiplayer", "ScaleMonsterHpForMultiplayer", "SetCurrentHpInternal",
    "SetMaxHpInternal", "SetUniqueMonsterHpValue",
}
_HP_COMMAND_MEMBERS = {"GainMaxHp", "LoseMaxHp", "SetCurrentHp", "SetMaxAndCurrentHp", "SetMaxHp"}


def _one(assembly: AssemblyMetadata, owner: str, name: str, assembly_sha256: str) -> tuple[int, dict[str, Any]]:
    matches = assembly.find_methods(owner, name)
    if len(matches) != 1:
        raise SourceExtractionError(f"HP pipeline method {owner}::{name} matched {len(matches)}")
    return matches[0], assembly.method_record(matches[0], assembly_sha256)


def _require_order(record: dict[str, Any], fragments: tuple[str, ...], *, label: str) -> list[int]:
    """Resolve one ordered CIL semantic chain; absent/out-of-order fails."""
    positions: list[int] = []
    start = 0
    instructions = record["instructions"]
    for fragment in fragments:
        matches = [
            index for index in range(start, len(instructions))
            if fragment in str(instructions[index]["operand"])
        ]
        if not matches:
            raise SourceExtractionError(
                f"HP pipeline {label} missing or reordered {fragment} in {record['symbolSignature']}"
            )
        position = matches[0]
        positions.append(position)
        start = position + 1
    return positions


def _require_exact_opcodes(record: dict[str, Any], expected: tuple[tuple[str, Any], ...], *, label: str) -> None:
    actual = tuple((item["opcode"], item["operand"]) for item in record["instructions"])
    cursor = 0
    for required in expected:
        try:
            cursor = actual.index(required, cursor) + 1
        except ValueError as exc:
            raise SourceExtractionError(
                f"HP pipeline {label} missing or reordered opcode {required!r} in {record['symbolSignature']}"
            ) from exc


def _provenance(record: dict[str, Any], semantic: Any) -> dict[str, Any]:
    normalized = [{"opcode": row["opcode"], "operand": row["operand"]} for row in record["instructions"]]
    return {
        key: record[key]
        for key in (
            "assemblySha256", "cilInstructionsSha256", "diagnosticMetadataToken", "metadataSignature",
            "methodBodySha256", "normalizedInstructionsSha256", "symbolSignature",
        )
    } | {
        "normalizedSliceSha256": witness_sha256(normalized),
        "semanticWitnessSha256": witness_sha256(semantic),
    }


def _raw_instructions(assembly: AssemblyMetadata, row_index: int) -> list[dict[str, Any]]:
    """Resolve every body for call census without JSON-normalizing unrelated floats."""
    result: list[dict[str, Any]] = []
    for instruction in assembly.method_body(row_index).instructions:
        operand = instruction.operand
        if hasattr(operand, "value"):
            operand = assembly.resolve_token(operand)
        elif isinstance(operand, (list, tuple)) and all(type(item) is int for item in operand):
            operand = list(operand)
        elif operand is not None and not isinstance(operand, (str, int, float, bytes)):
            operand = str(operand)
        result.append({"opcode": instruction.mnemonic, "operand": operand})
    return result


def _target_member(symbol: str, owner: str, members: set[str]) -> str | None:
    prefix = owner + "::"
    if not symbol.startswith(prefix):
        return None
    member = symbol[len(prefix):].split(" sig:", 1)[0]
    return member if member in members else None


def _method_code_bytes(assembly: AssemblyMetadata, row_index: int) -> bytes:
    """Compatibility delegate to the shared validated metadata code reader."""
    return assembly.method_code_bytes(row_index)


def _call_census(
    assembly: AssemblyMetadata,
    exact_targets: dict[str, tuple[int, str]],
    exact_commands: dict[str, tuple[int, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Scan every CIL region, then fully decode every token candidate body."""
    token_bytes = {
        (0x06000000 | row_index).to_bytes(4, "little")
        for row_index, _symbol in list(exact_targets.values()) + list(exact_commands.values())
    }
    candidate_indexes: list[int] = []
    for row_index, row in enumerate(assembly.md.MethodDef.rows, 1):
        if row.Rva and any(token in _method_code_bytes(assembly, row_index) for token in token_bytes):
            candidate_indexes.append(row_index)

    target_symbols = {member: symbol for member, (_index, symbol) in exact_targets.items()}
    command_symbols = {member: symbol for member, (_index, symbol) in exact_commands.items()}
    target_sites: list[dict[str, Any]] = []
    command_sites: list[dict[str, Any]] = []
    for row_index in candidate_indexes:
        caller_symbol = assembly.method_symbol(row_index)
        for instruction_index, instruction in enumerate(_raw_instructions(assembly, row_index)):
            if instruction["opcode"] not in {"call", "callvirt", "newobj"}:
                continue
            symbol = str(instruction["operand"])
            member = _target_member(symbol, _HP_CREATURE, _HP_TARGET_MEMBERS)
            if member is not None:
                if symbol != target_symbols[member]:
                    raise SourceExtractionError(f"unknown HP target overload at {caller_symbol}: {symbol}")
                target_sites.append({
                    "caller": caller_symbol, "instructionIndex": instruction_index,
                    "opcode": instruction["opcode"], "target": symbol, "targetMember": member,
                })
            member = _target_member(symbol, _HP_COMMAND, _HP_COMMAND_MEMBERS)
            if member is not None:
                if symbol != command_symbols[member]:
                    raise SourceExtractionError(f"unknown HP command overload at {caller_symbol}: {symbol}")
                command_sites.append({
                    "caller": caller_symbol, "instructionIndex": instruction_index,
                    "opcode": instruction["opcode"], "target": symbol, "targetMember": member,
                })
    target_sites.sort(key=lambda row: (row["caller"], row["instructionIndex"], row["target"]))
    command_sites.sort(key=lambda row: (row["caller"], row["instructionIndex"], row["target"]))
    return target_sites, command_sites


def _field(assembly: AssemblyMetadata, owner: str, name: str) -> dict[str, Any]:
    matches = []
    for index, row in enumerate(assembly.md.Field.rows, 1):
        if assembly.type_names.get(assembly.field_owner.get(index)) == owner and str(row.Name) == name:
            matches.append((index, row))
    if len(matches) != 1:
        raise SourceExtractionError(f"HP storage field {owner}::{name} matched {len(matches)}")
    index, row = matches[0]
    signature = row.Signature.value.hex()
    if signature != "0608":  # FIELD + ELEMENT_TYPE_I4
        raise SourceExtractionError(f"HP storage field {owner}::{name} is not CLI Int32: {signature}")
    return {"cliType": "Int32", "metadataSignature": signature, "symbol": assembly.field_symbol(index)}


def _enum_literal(assembly: AssemblyMetadata, owner: str, name: str) -> int:
    matches = []
    for index, row in enumerate(assembly.md.Field.rows, 1):
        if assembly.type_names.get(assembly.field_owner.get(index)) == owner and str(row.Name) == name:
            matches.append(row)
    if len(matches) != 1:
        raise SourceExtractionError(f"HP applicability enum {owner}::{name} matched {len(matches)}")
    values = [
        constant.Value.value for constant in assembly.md.Constant.rows
        if getattr(constant.Parent, "row", None) is matches[0]
    ]
    if len(values) != 1 or len(values[0]) != 4:
        raise SourceExtractionError(f"HP applicability enum {owner}::{name} has unresolved Int32 constant")
    return int.from_bytes(values[0], "little", signed=True)


def _distribution(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        value = str(row[key])
        result[value] = result.get(value, 0) + 1
    return dict(sorted(result.items()))


def _nested_move_next(assembly: AssemblyMetadata, prefix: str, assembly_sha256: str) -> dict[str, Any]:
    types = [index for index, name in assembly.type_names.items() if name.startswith(prefix)]
    matches: list[int] = []
    for type_index in types:
        for method in assembly.md.TypeDef.rows[type_index - 1].MethodList:
            if str(method.row.Name) == "MoveNext":
                matches.append(method.row_index)
    if len(matches) != 1:
        raise SourceExtractionError(f"HP pipeline state machine {prefix} matched {len(matches)} MoveNext methods")
    return assembly.method_record(matches[0], assembly_sha256)


def _assignment_expression() -> dict[str, Any]:
    return {
        "expression": {
            "domain": {"minimum": "0"}, "kind": "stateVariable",
            "name": "assignedHpDecimal", "valueType": "decimal",
        },
        "fromType": "decimal", "kind": "convert", "mode": "truncateTowardZero",
        "toType": "integer", "valueType": "integer",
    }


def _semantic_leaf_count(value: Any) -> int:
    if isinstance(value, dict):
        return sum(_semantic_leaf_count(child) for child in value.values())
    if isinstance(value, list):
        return sum(_semantic_leaf_count(child) for child in value)
    return 1


def validate_hp_pipeline(pipeline: Any, *, path: str = "hpPipeline") -> None:
    """Validate E2b semantics independently of extraction provenance bulk."""
    if not isinstance(pipeline, dict):
        raise SourceExtractionError(f"{path} must be an object")
    required = {
        "applicability", "assignment", "baseSelection", "callCensus", "commandWrappers", "networkStorage",
        "provenance", "regressionWitnesses", "ruleId", "sourceDenominators", "specialCallPaths", "storage",
    }
    if set(pipeline) != required:
        raise SourceExtractionError(f"{path} fields mismatch: {sorted(set(pipeline) ^ required)!r}")
    if pipeline["ruleId"] != "monsterHpAssignmentPipeline.v0.111.0":
        raise SourceExtractionError(f"{path}.ruleId drift")

    expected_base = {
        "candidateDomain": "inclusiveIntegers",
        "fallback": "fullInclusiveRangeWhenEveryCandidateMatchesATeammateMaxHp",
        "initialConstructorWrites": ["maxHp=maxInitialHp", "currentHp=maxInitialHp"],
        "invalidRange": "InvalidOperationExceptionWhenMinInitialHpGreaterThanMaxInitialHp",
        "rangeConstruction": "Enumerable.Range(minInitialHp,maxInitialHp+1-minInitialHp)",
        "rng": "RunRngSet.Niche",
        "selection": "Rng.NextItem(remainingCandidates)ElseRng.NextInt(minInclusive,maxExclusive)",
        "teammateAvoidance": "removeExistingTeammateMaxHpValuesWhenPossible",
        "writeOrder": ["maxHp", "currentHp", "monsterMaxHpBeforeModification"],
    }
    if pipeline["baseSelection"] != expected_base:
        raise SourceExtractionError(f"{path}.baseSelection incomplete unique-selection branch")

    if pipeline["applicability"] != {
        "normalCreation": "CombatSide.Enemy", "normalCreationEnumValue": 2,
        "normalOrder": ["SetUniqueMonsterHpValue", "ScaleMonsterHpForMultiplayer"],
        "onePlayer": "ScaleMonsterHpForMultiplayerReturnsWithoutSetterWrites",
        "specialPathsJoinAssignment": True,
    }:
        raise SourceExtractionError(f"{path}.applicability missing one-player branch or assignment join")

    assignment = pipeline["assignment"]
    if set(assignment) != {"conversion", "current", "max", "numericContract"}:
        raise SourceExtractionError(f"{path}.assignment fields mismatch")
    validate_expression(assignment["conversion"], path=path + ".assignment.conversion", expected_type="integer")
    if assignment["conversion"] != _assignment_expression():
        raise SourceExtractionError(f"{path}.assignment conversion operator or order changed")
    if assignment["numericContract"] != {
        "arithmeticRounding": "none", "assignmentConversion": "truncateTowardZero",
        "checkedOverflow": "Decimal.op_Explicit throws OverflowException outside Int32",
        "nonNegativeEquivalence": "floor", "negativeEquivalenceClaimed": False,
        "operator": "System.Decimal.op_Explicit(System.Decimal)->System.Int32",
    }:
        raise SourceExtractionError(f"{path}.assignment numeric conversion contract drift")
    if assignment["max"] != {
        "cap": 999999999, "capOrder": "afterDecimalToInt32Conversion",
        "currentInteraction": "storeMaxThenStoreMin(previousCurrent,newMax)",
        "negativeInput": "ArgumentExceptionBeforeConversion", "storageType": "Int32",
    }:
        raise SourceExtractionError(f"{path}.assignment max cap/guard/order drift")
    if assignment["current"] != {
        "clamp": "DecimalMin(requestedCurrent,Decimal(maxHp))BeforeConversion",
        "lowerClamp": "none", "storageType": "Int32",
    }:
        raise SourceExtractionError(f"{path}.assignment current clamp/order drift")

    expected_wrappers = [
        {"command": "GainMaxHp", "joins": ["SetMaxHp"]},
        {"command": "LoseMaxHp", "joins": ["SetMaxHp"]},
        {"command": "SetCurrentHp", "joins": ["SetCurrentHpInternal"]},
        {"command": "SetMaxAndCurrentHp", "joins": ["SetMaxHp", "SetCurrentHp"]},
        {"command": "SetMaxHp", "joins": ["SetMaxHpInternal"]},
    ]
    if pipeline["commandWrappers"] != expected_wrappers:
        raise SourceExtractionError(f"{path}.commandWrappers unknown setter overload or wrong current/max assignment order")
    special = pipeline["specialCallPaths"]
    if [row.get("pathId") for row in special] != ["DECIMILLIPEDE", "TEST_SUBJECT", "TOUGH_EGG"]:
        raise SourceExtractionError(f"{path}.specialCallPaths unjoined special caller")
    expected_joins = {
        "DECIMILLIPEDE": ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"],
        "TEST_SUBJECT": ["ScaleHpForMultiplayer", "SetMaxHp", "Heal", "HealInternal", "SetCurrentHpInternal"],
        "TOUGH_EGG": ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"],
    }
    for row in special:
        if row.get("joins") != expected_joins[row["pathId"]]:
            raise SourceExtractionError(f"{path}.specialCallPaths unjoined special caller {row['pathId']}")

    expected_storage = {
        "currentHp": {"cliType": "Int32", "metadataSignature": "0608", "symbol": _HP_CREATURE + "::_currentHp"},
        "maxHp": {"cliType": "Int32", "metadataSignature": "0608", "symbol": _HP_CREATURE + "::_maxHp"},
    }
    if pipeline["storage"] != expected_storage:
        raise SourceExtractionError(f"{path}.storage current/max must be Int32")
    expected_network = {
        "captureOrder": ["currentHp", "maxHp"], "deserializationOrder": ["currentHp", "maxHp"],
        "fields": {
            "currentHp": {"cliType": "Int32", "metadataSignature": "0608", "symbol": _HP_NET_CREATURE + "::currentHp"},
            "maxHp": {"cliType": "Int32", "metadataSignature": "0608", "symbol": _HP_NET_CREATURE + "::maxHp"},
        },
        "serializationOrder": ["currentHp:Int32/32", "maxHp:Int32/32"], "wireBits": 32,
        "wireReader": "PacketReader.ReadInt", "wireWriter": "PacketWriter.WriteInt",
    }
    if pipeline["networkStorage"] != expected_network:
        raise SourceExtractionError(f"{path}.networkStorage current/max wire fields must be Int32/32")

    census = pipeline["callCensus"]
    if set(census) != {"commandSites", "commandTargetDistribution", "targetSites", "targetDistribution"}:
        raise SourceExtractionError(f"{path}.callCensus fields mismatch")
    if len(census["targetSites"]) != 19 or census["targetDistribution"] != {
        "ScaleHpForMultiplayer": 8, "ScaleMonsterHpForMultiplayer": 1, "SetCurrentHpInternal": 6,
        "SetMaxHpInternal": 3, "SetUniqueMonsterHpValue": 1,
    }:
        raise SourceExtractionError(f"{path}.callCensus required HP target call closure drift")
    if len(census["commandSites"]) != 44 or census["commandTargetDistribution"] != {
        "GainMaxHp": 22, "LoseMaxHp": 10, "SetCurrentHp": 3, "SetMaxAndCurrentHp": 4, "SetMaxHp": 5,
    }:
        raise SourceExtractionError(f"{path}.callCensus command caller closure drift")

    semantic_scope = {
        "applicability": pipeline["applicability"], "assignment": pipeline["assignment"],
        "baseSelection": pipeline["baseSelection"], "commandWrappers": pipeline["commandWrappers"],
        "networkStorage": pipeline["networkStorage"], "specialCallPaths": pipeline["specialCallPaths"],
        "storage": pipeline["storage"],
    }
    expected_denominators = {
        "baseSelectionChainMethods": 4,
        "capClampPreconditionSemanticFields": _semantic_leaf_count({
            "current": pipeline["assignment"]["current"], "max": pipeline["assignment"]["max"],
        }),
        "commandAndSpecialCallerApplicability": len(census["commandSites"]) + len(expected_wrappers) + len(special),
        "completePipelineSemanticFields": _semantic_leaf_count(semantic_scope),
        "multiplayerWrapperHelperCallSites": census["targetDistribution"]["ScaleHpForMultiplayer"] + census["targetDistribution"]["ScaleMonsterHpForMultiplayer"],
        "setterMethodsAndDirectCallSites": 2 + census["targetDistribution"]["SetMaxHpInternal"] + census["targetDistribution"]["SetCurrentHpInternal"],
        "storageAndNetworkSerializationJoins": 10,
    }
    if pipeline["sourceDenominators"] != expected_denominators:
        raise SourceExtractionError(f"{path}.sourceDenominators drift")

    expected_witnesses = [
        {"case": "fractionalAct1TwoPlayer", "decimalProduct": "101.2", "inputs": {"actIndex": 0, "baseHp": 46, "bossRoom": False, "playerCount": 2}, "storedHp": 101},
        {"case": "exactIntegerProduct", "decimalProduct": "110.0", "inputs": {"actIndex": 0, "baseHp": 50, "bossRoom": False, "playerCount": 2}, "storedHp": 110},
        {"case": "act3Boss", "decimalProduct": "119.6", "inputs": {"actIndex": 2, "baseHp": 46, "bossRoom": True, "playerCount": 2}, "storedHp": 119},
        {"case": "onePlayerBypass", "decimalProduct": "46", "inputs": {"actIndex": 0, "baseHp": 46, "bossRoom": False, "playerCount": 1}, "storedHp": 46},
        {"case": "inclusiveBaseRange", "inputs": {"maximum": 52, "minimum": 46}, "selectionDomain": [46, 47, 48, 49, 50, 51, 52]},
        {"case": "teammateAvoidance", "inputs": {"maximum": 48, "minimum": 46, "teammateMaxHp": [46, 48]}, "selectionDomain": [47]},
        {"case": "teammateFallback", "inputs": {"maximum": 46, "minimum": 46, "teammateMaxHp": [46]}, "selectionDomain": [46]},
        {"case": "capExact", "requestedDecimal": "999999999", "storedHp": 999999999},
        {"case": "capAbove", "requestedDecimal": "1000000000", "storedHp": 999999999},
        {"case": "negativeMaxRejected", "requestedDecimal": "-1", "result": "ArgumentExceptionBeforeConversion"},
        {"case": "currentClamp", "maximumHp": 101, "requestedDecimal": "120.9", "storedHp": 101},
        {"case": "currentFractionalConversion", "maximumHp": 101, "requestedDecimal": "100.9", "storedHp": 100},
        {"case": "checkedOverflowBeforeCap", "requestedDecimal": "2147483648", "result": "OverflowExceptionBeforeCap"},
    ]
    if pipeline["regressionWitnesses"] != expected_witnesses:
        raise SourceExtractionError(f"{path}.regressionWitnesses assignment semantics drift")

    provenance = pipeline["provenance"]
    expected_provenance = {
        "baseConstructor", "commandStateMachines", "createCreature", "networkCapture", "networkDeserialize",
        "networkSerialize", "scaleHelper", "scaleWrapper", "setCurrent", "setMax", "setUnique",
        "specialCallPaths", "testSubjectHealCommand", "testSubjectHealInternal", "uniqueTeammateProjection",
    }
    if not isinstance(provenance, dict) or set(provenance) != expected_provenance:
        raise SourceExtractionError(f"{path}.provenance closure incomplete")
    for name, value in provenance.items():
        records = value if isinstance(value, list) else [value]
        if not records:
            raise SourceExtractionError(f"{path}.provenance.{name} empty")
        for record in records:
            for key in ("assemblySha256", "methodBodySha256", "normalizedInstructionsSha256", "semanticWitnessSha256", "symbolSignature"):
                if not isinstance(record.get(key), str) or not record[key]:
                    raise SourceExtractionError(f"{path}.provenance.{name}.{key} missing")


def extract_hp_pipeline(assembly: AssemblyMetadata, assembly_sha256: str) -> dict[str, Any]:
    # Metadata/CIL dependencies remain extractor-only; projection validation imports
    # this module for the pure semantic validator without importing dnfile/dncil.
    from .scaling import extract_hp_multiplayer_scaling

    records: dict[str, dict[str, Any]] = {}
    for key, owner, name in (
        ("createCreature", _HP_COMBAT_STATE, "CreateCreature"),
        ("setUnique", _HP_CREATURE, "SetUniqueMonsterHpValue"),
        ("scaleWrapper", _HP_CREATURE, "ScaleMonsterHpForMultiplayer"),
        ("scaleHelper", _HP_CREATURE, "ScaleHpForMultiplayer"),
        ("setMax", _HP_CREATURE, "SetMaxHpInternal"),
        ("setCurrent", _HP_CREATURE, "SetCurrentHpInternal"),
        ("networkCapture", _HP_NET_STATE, "FromRun"),
        ("networkSerialize", _HP_NET_CREATURE, "Serialize"),
        ("networkDeserialize", _HP_NET_CREATURE, "Deserialize"),
    ):
        _, records[key] = _one(assembly, owner, name, assembly_sha256)
    constructors = [
        index for index in assembly.find_methods(_HP_CREATURE, ".ctor")
        if assembly.md.MethodDef.rows[index - 1].Signature.value.hex() == "2003011288e411aa6c0e"
    ]
    if len(constructors) != 1:
        raise SourceExtractionError(f"HP pipeline monster constructor matched {len(constructors)}")
    records["baseConstructor"] = assembly.method_record(constructors[0], assembly_sha256)
    _, unique_projection = _one(
        assembly, _HP_CREATURE + "+<>c", "<SetUniqueMonsterHpValue>b__107_0", assembly_sha256
    )

    command_targets: dict[str, tuple[int, str]] = {}
    for member in sorted(_HP_COMMAND_MEMBERS):
        index, record = _one(assembly, _HP_COMMAND, member, assembly_sha256)
        command_targets[member] = (index, record["symbolSignature"])
    command_moves = {
        member: _nested_move_next(assembly, _HP_COMMAND + "+<" + member + ">d__", assembly_sha256)
        for member in sorted(_HP_COMMAND_MEMBERS)
    }
    _, test_subject_heal_internal = _one(assembly, _HP_CREATURE, "HealInternal", assembly_sha256)
    test_subject_heal_command = _nested_move_next(assembly, _HP_COMMAND + "+<Heal>d__", assembly_sha256)
    _require_order(test_subject_heal_command, ("::HealInternal sig:",), label="Test Subject Heal command join")
    _require_order(test_subject_heal_internal, ("get_CurrentHp", "Decimal::op_Addition", "SetCurrentHpInternal"), label="Test Subject current assignment join")
    record_key = {
        "ScaleHpForMultiplayer": "scaleHelper", "ScaleMonsterHpForMultiplayer": "scaleWrapper",
        "SetCurrentHpInternal": "setCurrent", "SetMaxHpInternal": "setMax",
        "SetUniqueMonsterHpValue": "setUnique",
    }
    target_methods = {
        member: (
            assembly.find_methods(_HP_CREATURE, member)[0],
            records[record_key[member]]["symbolSignature"],
        )
        for member in sorted(_HP_TARGET_MEMBERS)
    }
    target_sites, command_sites = _call_census(assembly, target_methods, command_targets)
    target_distribution = _distribution(target_sites, "targetMember")
    command_distribution = _distribution(command_sites, "targetMember")
    # The denominators above are discovered before these exact-version regression pins.
    if target_distribution != {
        "ScaleHpForMultiplayer": 8, "ScaleMonsterHpForMultiplayer": 1, "SetCurrentHpInternal": 6,
        "SetMaxHpInternal": 3, "SetUniqueMonsterHpValue": 1,
    }:
        raise SourceExtractionError(f"HP target call-site distribution drift after census: {target_distribution!r}")
    if command_distribution != {
        "GainMaxHp": 22, "LoseMaxHp": 10, "SetCurrentHp": 3, "SetMaxAndCurrentHp": 4, "SetMaxHp": 5,
    }:
        raise SourceExtractionError(f"HP command call-site distribution drift after census: {command_distribution!r}")

    _require_order(records["baseConstructor"], (
        "get_MinInitialHp", "get_MaxInitialHp", "InvalidOperationException::.ctor", "::_maxHp", "::_currentHp",
    ), label="constructor min/max validation and writes")
    _require_order(records["createCreature"], (
        "Creature::.ctor", "SetUniqueMonsterHpValue", "ScaleMonsterHpForMultiplayer",
    ), label="normal creation order")
    _require_order(records["setUnique"], (
        "get_MinInitialHp", "get_MaxInitialHp", "Enumerable::Range", "Enumerable::Except",
        "Enumerable::Select", "ExceptWith", "get_Count", "Rng::NextItem", "Rng::NextInt",
        "::_maxHp", "::_currentHp", "set_MonsterMaxHpBeforeModification",
    ), label="inclusive unique/fallback selection")
    _require_order(unique_projection, ("get_MaxHp",), label="teammate max-HP projection")
    enemy_value = _enum_literal(assembly, "MegaCrit.Sts2.Core.Combat.CombatSide", "Enemy")
    if enemy_value != 2:
        raise SourceExtractionError(f"CombatSide.Enemy value drift: {enemy_value}")
    if not any(row["opcode"] == "ldc.i4.2" for row in records["createCreature"]["instructions"]):
        raise SourceExtractionError("normal HP assignment CombatSide.Enemy branch is absent")

    _require_exact_opcodes(records["scaleWrapper"], (
        ("ldarg.2", None), ("ldc.i4.1", None), ("bne.un.s", 6),
    ), label="one-player wrapper bypass")
    _require_order(records["scaleWrapper"], (
        "get_MaxHp", "Decimal::op_Implicit", "ScaleHpForMultiplayer", "SetMaxHpInternal",
        "get_MaxHp", "Decimal::op_Implicit", "SetCurrentHpInternal",
    ), label="multiplayer assignment order")
    _require_order(records["scaleHelper"], (
        "Decimal::op_Implicit", "Decimal::op_Multiply", "GetMultiplayerScaling", "Decimal::op_Multiply",
    ), label="Decimal multiply order")
    _require_order(records["setMax"], (
        "Decimal::Zero", "Decimal::op_LessThan", "ArgumentException::.ctor", "Decimal::op_Explicit",
        "Math::Min", "set_MaxHp", "get_CurrentHp", "get_MaxHp", "Math::Min", "set_CurrentHp",
    ), label="max guard conversion cap storage order")
    if not any(row["opcode"] == "ldc.i4" and row["operand"] == 999999999 for row in records["setMax"]["instructions"]):
        raise SourceExtractionError("HP max cap 999999999 absent")
    _require_order(records["setCurrent"], (
        "get_MaxHp", "Decimal::op_Implicit", "Math::Min", "Decimal::op_Explicit", "set_CurrentHp",
    ), label="current clamp conversion storage order")

    wrapper_joins = {
        "GainMaxHp": ["SetMaxHp"], "LoseMaxHp": ["SetMaxHp"],
        "SetCurrentHp": ["SetCurrentHpInternal"],
        "SetMaxAndCurrentHp": ["SetMaxHp", "SetCurrentHp"], "SetMaxHp": ["SetMaxHpInternal"],
    }
    for member, joins in wrapper_joins.items():
        _require_order(
            command_moves[member], tuple("::" + join + " sig:" for join in joins),
            label=f"command wrapper {member}",
        )

    special_specs = [
        ("DECIMILLIPEDE", "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment+<AfterAddedToRoom>d__46", ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"], ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"]),
        ("TEST_SUBJECT", "MegaCrit.Sts2.Core.Models.Monsters.TestSubject+<Revive>d__81", ["ScaleHpForMultiplayer", "SetMaxHp", "Heal"], ["ScaleHpForMultiplayer", "SetMaxHp", "Heal", "HealInternal", "SetCurrentHpInternal"]),
        ("TOUGH_EGG", "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg+<Hatch>d__36", ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"], ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"]),
    ]
    special_rows = []
    special_records = []
    for path_id, owner, direct_joins, complete_joins in special_specs:
        record = _nested_move_next(assembly, owner, assembly_sha256)
        _require_order(record, tuple("::" + join + " sig:" for join in direct_joins), label=f"special HP path {path_id}")
        special_rows.append({"joins": complete_joins, "pathId": path_id})
        special_records.append(_provenance(record, {"joins": complete_joins, "pathId": path_id}))

    current_field = _field(assembly, _HP_CREATURE, "_currentHp")
    max_field = _field(assembly, _HP_CREATURE, "_maxHp")
    net_current = _field(assembly, _HP_NET_CREATURE, "currentHp")
    net_max = _field(assembly, _HP_NET_CREATURE, "maxHp")
    _require_order(records["networkCapture"], (
        "get_CurrentHp", "CreatureState::currentHp", "get_MaxHp", "CreatureState::maxHp",
    ), label="network capture order")
    _require_exact_opcodes(records["networkSerialize"], (
        ("ldfld", net_current["symbol"]), ("ldc.i4.s", 32),
        ("callvirt", "MegaCrit.Sts2.Core.Multiplayer.Serialization.PacketWriter::WriteInt sig:2002010808"),
        ("ldfld", net_max["symbol"]), ("ldc.i4.s", 32),
        ("callvirt", "MegaCrit.Sts2.Core.Multiplayer.Serialization.PacketWriter::WriteInt sig:2002010808"),
    ), label="Int32 wire serialization")
    _require_exact_opcodes(records["networkDeserialize"], (
        ("ldc.i4.s", 32),
        ("callvirt", "MegaCrit.Sts2.Core.Multiplayer.Serialization.PacketReader::ReadInt sig:20010808"),
        ("stfld", net_current["symbol"]), ("ldc.i4.s", 32),
        ("callvirt", "MegaCrit.Sts2.Core.Multiplayer.Serialization.PacketReader::ReadInt sig:20010808"),
        ("stfld", net_max["symbol"]),
    ), label="Int32 wire deserialization")

    helper_expression = extract_hp_multiplayer_scaling(
        Path("."), assembly_sha256, assembly=assembly
    )["expression"]
    fixture_inputs = [
        ("fractionalAct1TwoPlayer", 46, 2, 0, False),
        ("exactIntegerProduct", 50, 2, 0, False),
        ("act3Boss", 46, 2, 2, True),
        ("onePlayerBypass", 46, 1, 0, False),
    ]
    witnesses = []
    for case, base_hp, players, act_index, boss_room in fixture_inputs:
        inputs = {"actIndex": act_index, "baseHp": str(base_hp), "bossRoom": boss_room, "playerCount": players}
        product = evaluate_expression(helper_expression, inputs)
        witnesses.append({
            "case": case, "decimalProduct": str(product),
            "inputs": {"actIndex": act_index, "baseHp": base_hp, "bossRoom": boss_room, "playerCount": players},
            "storedHp": min(int(product), 999999999),
        })
    inclusive = list(range(46, 52 + 1))
    avoided = [candidate for candidate in range(46, 48 + 1) if candidate not in {46, 48}]
    exhausted = [candidate for candidate in range(46, 46 + 1) if candidate not in {46}]
    witnesses.extend([
        {"case": "inclusiveBaseRange", "inputs": {"maximum": 52, "minimum": 46}, "selectionDomain": inclusive},
        {"case": "teammateAvoidance", "inputs": {"maximum": 48, "minimum": 46, "teammateMaxHp": [46, 48]}, "selectionDomain": avoided},
        {"case": "teammateFallback", "inputs": {"maximum": 46, "minimum": 46, "teammateMaxHp": [46]}, "selectionDomain": exhausted or [46]},
        {"case": "capExact", "requestedDecimal": "999999999", "storedHp": min(int("999999999"), 999999999)},
        {"case": "capAbove", "requestedDecimal": "1000000000", "storedHp": min(int("1000000000"), 999999999)},
        {"case": "negativeMaxRejected", "requestedDecimal": "-1", "result": "ArgumentExceptionBeforeConversion"},
        {"case": "currentClamp", "maximumHp": 101, "requestedDecimal": "120.9", "storedHp": int(min(Decimal("120.9"), Decimal(101)))},
        {"case": "currentFractionalConversion", "maximumHp": 101, "requestedDecimal": "100.9", "storedHp": int(min(Decimal("100.9"), Decimal(101)))},
        {"case": "checkedOverflowBeforeCap", "requestedDecimal": "2147483648", "result": "OverflowExceptionBeforeCap"},
    ])

    provenance = {key: _provenance(record, key) for key, record in records.items()}
    provenance["uniqueTeammateProjection"] = _provenance(unique_projection, "teammate max HP projection")
    provenance["testSubjectHealCommand"] = _provenance(test_subject_heal_command, "Heal command to HealInternal")
    provenance["testSubjectHealInternal"] = _provenance(test_subject_heal_internal, "HealInternal to SetCurrentHpInternal")
    provenance["commandStateMachines"] = [
        _provenance(command_moves[key], {"command": key, "joins": wrapper_joins[key]})
        for key in sorted(command_moves)
    ]
    provenance["specialCallPaths"] = special_records
    applicability = {
        "normalCreation": "CombatSide.Enemy", "normalCreationEnumValue": enemy_value,
        "normalOrder": ["SetUniqueMonsterHpValue", "ScaleMonsterHpForMultiplayer"],
        "onePlayer": "ScaleMonsterHpForMultiplayerReturnsWithoutSetterWrites",
        "specialPathsJoinAssignment": True,
    }
    assignment = {
        "conversion": _assignment_expression(),
        "current": {
            "clamp": "DecimalMin(requestedCurrent,Decimal(maxHp))BeforeConversion",
            "lowerClamp": "none", "storageType": "Int32",
        },
        "max": {
            "cap": 999999999, "capOrder": "afterDecimalToInt32Conversion",
            "currentInteraction": "storeMaxThenStoreMin(previousCurrent,newMax)",
            "negativeInput": "ArgumentExceptionBeforeConversion", "storageType": "Int32",
        },
        "numericContract": {
            "arithmeticRounding": "none", "assignmentConversion": "truncateTowardZero",
            "checkedOverflow": "Decimal.op_Explicit throws OverflowException outside Int32",
            "negativeEquivalenceClaimed": False, "nonNegativeEquivalence": "floor",
            "operator": "System.Decimal.op_Explicit(System.Decimal)->System.Int32",
        },
    }
    base_selection = {
        "candidateDomain": "inclusiveIntegers",
        "fallback": "fullInclusiveRangeWhenEveryCandidateMatchesATeammateMaxHp",
        "initialConstructorWrites": ["maxHp=maxInitialHp", "currentHp=maxInitialHp"],
        "invalidRange": "InvalidOperationExceptionWhenMinInitialHpGreaterThanMaxInitialHp",
        "rangeConstruction": "Enumerable.Range(minInitialHp,maxInitialHp+1-minInitialHp)",
        "rng": "RunRngSet.Niche",
        "selection": "Rng.NextItem(remainingCandidates)ElseRng.NextInt(minInclusive,maxExclusive)",
        "teammateAvoidance": "removeExistingTeammateMaxHpValuesWhenPossible",
        "writeOrder": ["maxHp", "currentHp", "monsterMaxHpBeforeModification"],
    }
    command_wrappers = [{"command": key, "joins": wrapper_joins[key]} for key in sorted(wrapper_joins)]
    network_storage = {
        "captureOrder": ["currentHp", "maxHp"], "deserializationOrder": ["currentHp", "maxHp"],
        "fields": {"currentHp": net_current, "maxHp": net_max},
        "serializationOrder": ["currentHp:Int32/32", "maxHp:Int32/32"], "wireBits": 32,
        "wireReader": "PacketReader.ReadInt", "wireWriter": "PacketWriter.WriteInt",
    }
    storage = {"currentHp": current_field, "maxHp": max_field}
    semantic_scope = {
        "applicability": applicability, "assignment": assignment, "baseSelection": base_selection,
        "commandWrappers": command_wrappers, "networkStorage": network_storage,
        "specialCallPaths": special_rows, "storage": storage,
    }
    source_denominators = {
        "baseSelectionChainMethods": 4,
        "capClampPreconditionSemanticFields": _semantic_leaf_count({"current": assignment["current"], "max": assignment["max"]}),
        "commandAndSpecialCallerApplicability": len(command_sites) + len(command_wrappers) + len(special_rows),
        "completePipelineSemanticFields": _semantic_leaf_count(semantic_scope),
        "multiplayerWrapperHelperCallSites": target_distribution["ScaleHpForMultiplayer"] + target_distribution["ScaleMonsterHpForMultiplayer"],
        "setterMethodsAndDirectCallSites": 2 + target_distribution["SetMaxHpInternal"] + target_distribution["SetCurrentHpInternal"],
        "storageAndNetworkSerializationJoins": 10,
    }
    pipeline = {
        "applicability": applicability,
        "assignment": assignment,
        "baseSelection": base_selection,
        "callCensus": {
            "commandSites": command_sites, "commandTargetDistribution": command_distribution,
            "targetDistribution": target_distribution, "targetSites": target_sites,
        },
        "commandWrappers": command_wrappers,
        "networkStorage": network_storage,
        "provenance": provenance,
        "regressionWitnesses": witnesses,
        "ruleId": "monsterHpAssignmentPipeline.v0.111.0",
        "sourceDenominators": source_denominators,
        "specialCallPaths": special_rows,
        "storage": storage,
    }
    validate_hp_pipeline(pipeline)
    return pipeline
