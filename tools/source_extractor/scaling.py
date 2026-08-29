"""Raw-derived HP multiplayer scaling expression and provenance."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from .ast import evaluate_expression, validate_expression
from .canonical import witness_sha256
from .errors import SourceExtractionError
from .metadata import AssemblyMetadata


def _state(name: str, value_type: str, domain: Any) -> dict[str, Any]:
    return {"domain": domain, "kind": "stateVariable", "name": name, "valueType": value_type}


def _constant(value: int | str, value_type: str) -> dict[str, Any]:
    return {"kind": "constant", "value": value, "valueType": value_type}


def _method_provenance(record: dict[str, Any], witness: str) -> dict[str, Any]:
    return {
        "assemblySha256": record["assemblySha256"],
        "cilInstructionsSha256": record["cilInstructionsSha256"],
        "diagnosticMetadataToken": record["diagnosticMetadataToken"],
        "metadataSignature": record["metadataSignature"],
        "methodBodySha256": record["methodBodySha256"],
        "normalizedInstructionsSha256": record["normalizedInstructionsSha256"],
        "normalizedSemanticWitness": witness,
        "normalizedSemanticWitnessSha256": witness_sha256(witness),
        "symbolSignature": record["symbolSignature"],
    }


def extract_hp_multiplayer_scaling(dll_path: Path, assembly_sha256: str, *, assembly: AssemblyMetadata | None = None) -> dict[str, Any]:
    owns_assembly = assembly is None
    if assembly is None:
        assembly = AssemblyMetadata(dll_path)
    try:
        scale_owner = "MegaCrit.Sts2.Core.Entities.Creatures.Creature"
        factor_owner = "MegaCrit.Sts2.Core.Models.Singleton.MultiplayerScalingModel"
        scale_matches = assembly.find_methods(scale_owner, "ScaleHpForMultiplayer")
        factor_matches = assembly.find_methods(factor_owner, "GetMultiplayerScaling")
        if len(scale_matches) != 1 or len(factor_matches) != 1:
            raise SourceExtractionError("HP multiplayer methods are unresolved")
        scale = assembly.method_record(scale_matches[0], assembly_sha256)
        factor = assembly.method_record(factor_matches[0], assembly_sha256)
        scale_operands = [str(item["operand"]) for item in scale["instructions"]]
        for needle in ("Decimal::op_Implicit", "Decimal::op_Multiply", "GetMultiplayerScaling"):
            if not any(needle in item for item in scale_operands):
                raise SourceExtractionError(f"HP scaling operation {needle} is unresolved")
        factor_operands = [str(item["operand"]) for item in factor["instructions"]]
        if not any("EncounterModel::get_RoomType" in item for item in factor_operands):
            raise SourceExtractionError("HP boss-context branch is unresolved")
        decimal_parts = [
            item["operand"]
            for item in factor["instructions"]
            if item["opcode"] in {"ldc.i4", "ldc.i4.s"} and item["operand"] in {11, 12, 13}
        ]
        if decimal_parts != [11, 12, 13, 12]:
            raise SourceExtractionError(f"HP scaling factor constants drift: {decimal_parts!r}")

        base = _state("baseHp", "decimal", {"minimum": "0"})
        players = _state("playerCount", "integer", {"minimum": 1})
        act = _state("actIndex", "integer", {"maximum": 2, "minimum": 0})
        boss = _state("bossRoom", "boolean", [False, True])
        factor_expression = {
            "actIndex": act,
            "boss": boss,
            "factors": {
                "act1": "1.1",
                "act2": "1.2",
                "act3Boss": "1.3",
                "act3NonBoss": "1.2",
            },
            "kind": "actRoomFactor",
            "valueType": "decimal",
        }
        player_decimal = {
            "expression": players,
            "fromType": "integer",
            "kind": "convert",
            "mode": "exact",
            "toType": "decimal",
            "valueType": "decimal",
        }
        expression = {
            "condition": {
                "kind": "compare",
                "left": players,
                "operator": "lessOrEqual",
                "right": _constant(1, "integer"),
                "valueType": "boolean",
            },
            "kind": "conditional",
            "valueType": "decimal",
            "whenFalse": {
                "kind": "arithmetic",
                "operands": [base, player_decimal, factor_expression],
                "operator": "multiply",
                "valueType": "decimal",
            },
            "whenTrue": base,
        }
        validate_expression(expression, expected_type="decimal")
        fixtures = [
            ({"actIndex": 0, "baseHp": "100", "bossRoom": False, "playerCount": 1}, "100"),
            ({"actIndex": 0, "baseHp": "100", "bossRoom": False, "playerCount": 2}, "220.0"),
            ({"actIndex": 1, "baseHp": "100", "bossRoom": False, "playerCount": 2}, "240.0"),
            ({"actIndex": 2, "baseHp": "100", "bossRoom": False, "playerCount": 2}, "240.0"),
            ({"actIndex": 2, "baseHp": "100", "bossRoom": True, "playerCount": 2}, "260.0"),
        ]
        evaluated = []
        for state, expected in fixtures:
            value = evaluate_expression(expression, state)
            if value != Decimal(expected):
                raise SourceExtractionError(f"HP scaling regression failed: {state!r} -> {value}, expected {expected}")
            evaluated.append({"inputs": state, "result": str(value)})
        return {
            "expression": expression,
            "numericSemantics": {
                "factorType": "System.Decimal",
                "outputType": "System.Decimal",
                "playerCountConversion": "System.Decimal.op_Implicit(System.Int32)",
                "rounding": "none",
                "sourceHpType": "System.Decimal",
                "truncation": "none",
            },
            "provenance": {
                "factorSelection": _method_provenance(factor, "act 0 => 1.1; act 1 => 1.2; act 2 boss RoomType 3 => 1.3 else 1.2; other acts throw"),
                "scaling": _method_provenance(scale, "if playerCount <= 1 return source HP; else Decimal multiply source HP * playerCount * factor"),
            },
            "regressionWitnesses": evaluated,
            "ruleId": "hpMultiplayerScaling.v0.111.0",
        }
    finally:
        if owns_assembly:
            assembly.close()
