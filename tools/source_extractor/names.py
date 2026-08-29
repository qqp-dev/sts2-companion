"""Shipped English monster/state name joins with assembly-proven exceptions."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .canonical import strict_json_bytes, witness_sha256
from .errors import SourceExtractionError
from .localization import require_localized_text
from .metadata import AssemblyMetadata
from .pck import read_selected
from .world import arithmetic, const, state_integer

LOCALIZATION_PATH = "localization/eng/monsters.json"


def _method_provenance(record: dict[str, Any], witness: Any) -> dict[str, Any]:
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


def _assert_operands(record: dict[str, Any], required: list[str]) -> None:
    operands = [str(item["operand"]) for item in record["instructions"]]
    for needle in required:
        if not any(needle in item for item in operands):
            raise SourceExtractionError(f"required title behavior {needle!r} absent from {record['symbolSignature']}")


def join_monster_names(
    records: list[dict[str, Any]],
    reachable_models: set[str],
    dll_path: Path,
    assembly_sha256: str,
    pck_path: Path,
    pck_sha256: str,
    *,
    assembly: AssemblyMetadata | None = None,
) -> dict[str, Any]:
    data, entry, info = read_selected(pck_path, LOCALIZATION_PATH)
    localization = strict_json_bytes(data, f"SlayTheSpire2.pck:{LOCALIZATION_PATH}")
    if not isinstance(localization, dict):
        raise SourceExtractionError("monster localization top level must be an object")
    blob_sha256 = hashlib.sha256(data).hexdigest()

    owns_assembly = assembly is None
    if assembly is None:
        assembly = AssemblyMetadata(dll_path)
    try:
        methods: dict[str, dict[str, Any]] = {}
        owners = {
            "default": "MegaCrit.Sts2.Core.Models.MonsterModel",
            "toughEgg": "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg",
            "testSubject": "MegaCrit.Sts2.Core.Models.Monsters.TestSubject",
            "decimillipede": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment",
        }
        for key, owner in owners.items():
            matches = assembly.find_methods(owner, "get_Title")
            if len(matches) != 1:
                raise SourceExtractionError(f"required title getter {owner} matched {len(matches)}")
            methods[key] = assembly.method_record(matches[0], assembly_sha256)
        _assert_operands(methods["default"], ["AbstractModel::get_Id", "ModelId::get_Entry", "string:.name"])
        _assert_operands(methods["toughEgg"], ["ToughEgg::_hatched", "string:HATCHLING.name"])
        _assert_operands(methods["testSubject"], ["ProgressState::get_TestSubjectKills", "LocString::Add"])
        if not any(item["opcode"] == "ldc.i4.8" for item in methods["testSubject"]["instructions"]):
            raise SourceExtractionError("Test Subject title offset 8 is unresolved")
        _assert_operands(methods["decimillipede"], ["string:DECIMILLIPEDE_SEGMENT.name"])

        method_witnesses = {
            "default": _method_provenance(methods["default"], "localization key = canonical ModelId.Entry + '.name'"),
            "toughEgg": _method_provenance(methods["toughEgg"], "if ToughEgg._hatched then HATCHLING.name else canonical entry .name"),
            "testSubject": _method_provenance(methods["testSubject"], "Count = ProgressState.TestSubjectKills + 8; substitute Count in canonical title"),
            "decimillipede": _method_provenance(methods["decimillipede"], "all DecimillipedeSegment concrete subclasses use DECIMILLIPEDE_SEGMENT.name"),
        }

        joined = 0
        for record in records:
            model_ref = "MONSTER." + record["canonicalId"]
            if model_ref not in reachable_models:
                continue
            canonical_id = record["canonicalId"]
            if canonical_id.startswith("DECIMILLIPEDE_SEGMENT_"):
                key = "DECIMILLIPEDE_SEGMENT.name"
                method_key = "decimillipede"
            else:
                key = canonical_id + ".name"
                method_key = "default"
            value = require_localized_text(localization, key)
            name: dict[str, Any] = {"kind": "localizedText", "text": value}
            if canonical_id == "TEST_SUBJECT":
                if "{Count}" not in value:
                    raise SourceExtractionError("Test Subject shipped title is not the expected Count template")
                name = {
                    "inputs": {
                        "Count": arithmetic("add", state_integer("testSubjectKills", 0), const(8))
                    },
                    "kind": "localizedTemplate",
                    "template": value,
                }
                method_key = "testSubject"
            localization_provenance = {
                "authority": "rawSource",
                "entryMd5": entry.md5,
                "entrySha256": blob_sha256,
                "keyValueWitnessSha256": witness_sha256([key, value]),
                "localizationKey": key,
                "pckPath": LOCALIZATION_PATH,
                "pckSha256": pck_sha256,
            }
            record["name"] = name
            record["provenance"]["name"] = {
                "assemblyBehavior": method_witnesses[method_key],
                "localization": localization_provenance,
            }
            joined += 1

        hatchling_key = "HATCHLING.name"
        hatchling = require_localized_text(localization, hatchling_key)
        if joined != 108:
            raise SourceExtractionError(f"reachable monster name join drift: got {joined}, expected 108")
        return {
            "hatchlingName": {
                "kind": "localizedText",
                "provenance": {
                    "assemblyBehavior": method_witnesses["toughEgg"],
                    "localization": {
                        "authority": "rawSource",
                        "entryMd5": entry.md5,
                        "entrySha256": blob_sha256,
                        "keyValueWitnessSha256": witness_sha256([hatchling_key, hatchling]),
                        "localizationKey": hatchling_key,
                        "pckPath": LOCALIZATION_PATH,
                        "pckSha256": pck_sha256,
                    },
                },
                "text": hatchling,
            },
            "joinedCount": joined,
            "localizationBlob": {
                "entryFlags": entry.flags,
                "entryMd5": entry.md5,
                "entrySha256": blob_sha256,
                "pckDirectoryOffset": info.directory_offset,
                "pckFileCount": info.file_count,
                "pckFormat": info.format,
                "pckGodotVersion": list(info.godot_version),
                "pckPath": LOCALIZATION_PATH,
                "pckSha256": pck_sha256,
            },
            "titleRules": method_witnesses,
        }
    finally:
        if owns_assembly:
            assembly.close()
