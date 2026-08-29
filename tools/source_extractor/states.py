"""Required monster display/HP-state facts and narrow mutation witnesses."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .ast import evaluate_expression, validate_expression
from .canonical import witness_sha256
from .errors import SourceExtractionError
from .metadata import AssemblyMetadata
from .world import HpExtractor, MONSTER_NAMESPACE, const


def _compact(record: dict[str, Any], witness: Any) -> dict[str, Any]:
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


def _method(assembly: AssemblyMetadata, owner: str, name: str, sha: str) -> dict[str, Any]:
    matches = assembly.find_methods(owner, name)
    if len(matches) != 1:
        raise SourceExtractionError(f"required state method {owner}::{name} matched {len(matches)}")
    return assembly.method_record(matches[0], sha)


def _contains(record: dict[str, Any], *needles: str) -> None:
    values = [str(item["operand"]) for item in record["instructions"]]
    for needle in needles:
        if not any(needle in item for item in values):
            raise SourceExtractionError(f"state witness {needle!r} absent from {record['symbolSignature']}")


def _a8(expression: dict[str, Any]) -> int:
    result = evaluate_expression(expression, {"ascension": 8, "axebotRespawnCount": 0})
    if type(result) is not int: raise SourceExtractionError("state HP expression is not integer")
    return result


def extract_state_facts(dll_path: Path, assembly_sha256: str, *, assembly: AssemblyMetadata | None = None) -> dict[str, Any]:
    owns_assembly = assembly is None
    if assembly is None:
        assembly = AssemblyMetadata(dll_path)
    try:
        hp = HpExtractor(assembly, assembly_sha256)
        tough_min, tough_min_prov = hp.named_method(MONSTER_NAMESPACE + ".ToughEgg", "get_HatchlingMinHp")
        tough_max, tough_max_prov = hp.named_method(MONSTER_NAMESPACE + ".ToughEgg", "get_HatchlingMaxHp")
        tough_range = {"kind": "range", "maximum": tough_max, "minimum": tough_min, "valueType": "integerRange"}
        validate_expression(tough_range, expected_type="integerRange")
        hatch = _method(assembly, MONSTER_NAMESPACE + ".ToughEgg+<Hatch>d__36", "MoveNext", assembly_sha256)
        _contains(hatch, "get_HatchlingMinHp", "get_HatchlingMaxHp", "ScaleHpForMultiplayer", "SetMaxAndCurrentHp")

        phases: list[dict[str, Any]] = []
        for phase, getter in ((1, "get_FirstFormHp"), (2, "get_SecondFormHp"), (3, "get_ThirdFormHp")):
            expression, provenance = hp.named_method(MONSTER_NAMESPACE + ".TestSubject", getter)
            phases.append({
                "a8SinglePlayer": _a8(expression),
                "expression": expression,
                "phase": phase,
                "provenance": provenance,
            })
        respawn = _method(assembly, MONSTER_NAMESPACE + ".TestSubject+<RespawnMove>d__74", "MoveNext", assembly_sha256)
        _contains(respawn, "set_Respawns", "get_SecondFormHp", "get_ThirdFormHp", "TestSubject::Revive")
        revive = _method(assembly, MONSTER_NAMESPACE + ".TestSubject+<Revive>d__81", "MoveNext", assembly_sha256)
        _contains(revive, "ScaleHpForMultiplayer", "CreatureCmd::SetMaxHp", "CreatureCmd::Heal")

        bonus, bonus_provenance = hp.named_method(MONSTER_NAMESPACE + ".Axebot", "get_RespawnMaxHpBonus")
        ax_min, ax_min_prov = hp.effective(MONSTER_NAMESPACE + ".Axebot", "get_MinInitialHp")
        ax_max, ax_max_prov = hp.effective(MONSTER_NAMESPACE + ".Axebot", "get_MaxInitialHp")

        deci_owner = MONSTER_NAMESPACE + ".DecimillipedeSegment+<AfterAddedToRoom>d__46"
        deci_apply = _method(assembly, deci_owner, "MoveNext", assembly_sha256)
        _contains(deci_apply, "PowerCmd::Apply", "ReattachPower")
        if not any(item["opcode"] == "ldc.i4.s" and item["operand"] == 25 for item in deci_apply["instructions"]):
            raise SourceExtractionError("Decimillipede Reattach amount 25 is unresolved")
        deci_use = _method(assembly, "MegaCrit.Sts2.Core.Models.Powers.ReattachPower+<DoReattach>d__10", "MoveNext", assembly_sha256)
        _contains(deci_use, "PowerModel::get_Amount", "CreatureCmd::Heal")
        amount = {"kind": "constant", "value": "25", "valueType": "decimal"}
        validate_expression(amount, expected_type="decimal")

        return {
            "axebotRespawn": {
                "bonusExpression": bonus,
                "maximumHpExpression": {"kind": "range", "maximum": ax_max, "minimum": ax_min, "valueType": "integerRange"},
                "preMultiplayerScaling": True,
                "provenance": {"bonus": bonus_provenance, "maximum": ax_max_prov, "minimum": ax_min_prov},
                "stateInput": {"domain": {"maximum": 2, "minimum": 0}, "kind": "stateVariable", "name": "axebotRespawnCount", "valueType": "integer"},
            },
            "decimillipedeReattach": {
                "amountExpression": amount,
                "operation": "healCurrentHp",
                "provenance": {
                    "amountApplication": _compact(deci_apply, "apply ReattachPower with Decimal amount 25 during segment room initialization"),
                    "amountUse": _compact(deci_use, "ReattachPower.Amount is converted to Decimal and passed to CreatureCmd.Heal"),
                },
            },
            "stateIdentities": [
                {"canonicalModel": "MONSTER.TOUGH_EGG", "displayNameKey": "TOUGH_EGG.name", "hpState": "initial", "stateId": "MONSTER.TOUGH_EGG#UNHATCHED"},
                {"canonicalModel": "MONSTER.TOUGH_EGG", "displayNameKey": "HATCHLING.name", "hpState": "hatched", "stateId": "MONSTER.TOUGH_EGG#HATCHED"},
                *[
                    {"canonicalModel": "MONSTER.TEST_SUBJECT", "displayNameKey": "TEST_SUBJECT.name", "hpState": f"phase{phase}", "stateId": f"MONSTER.TEST_SUBJECT#PHASE_{phase}"}
                    for phase in (1, 2, 3)
                ],
                *[
                    {"canonicalModel": f"MONSTER.DECIMILLIPEDE_SEGMENT_{part}", "displayNameKey": "DECIMILLIPEDE_SEGMENT.name", "hpState": "initial", "stateId": f"MONSTER.DECIMILLIPEDE_SEGMENT_{part}#BODY"}
                    for part in ("BACK", "FRONT", "MIDDLE")
                ],
            ],
            "testSubjectPhases": {
                "phaseInput": {"domain": {"maximum": 3, "minimum": 1}, "kind": "stateVariable", "name": "testSubjectPhase", "valueType": "integer"},
                "phases": phases,
                "postSelectionScaling": "hpMultiplayerScaling.v0.111.0",
                "provenance": {
                    "phaseSelection": _compact(respawn, "increment Respawns; 1 selects SecondFormHp, 2 selects ThirdFormHp; pass selected HP to Revive"),
                    "reviveMutation": _compact(revive, "scale selected base HP, set MaxHp, then heal to scaled HP"),
                },
            },
            "toughEggHatch": {
                "a8SinglePlayer": {"maximum": _a8(tough_max), "minimum": _a8(tough_min)},
                "expression": tough_range,
                "postSelectionScaling": "hpMultiplayerScaling.v0.111.0",
                "provenance": {
                    "maximum": tough_max_prov,
                    "minimum": tough_min_prov,
                    "mutation": _compact(hatch, "inclusive RNG range HatchlingMinHp..HatchlingMaxHp, then multiplayer scale and SetMaxAndCurrentHp"),
                },
            },
        }
    finally:
        if owns_assembly:
            assembly.close()
