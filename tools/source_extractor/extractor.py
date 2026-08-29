"""Build the deterministic v0.111.0 normalized source-world artifact."""

from __future__ import annotations

import hashlib
from typing import Any

from . import EXTRACTOR_VERSION, SCHEMA_VERSION
from .canonical import canonical_json_bytes, strict_json_bytes, witness_sha256
from .encounters import extract_rosters
from .errors import SourceExtractionError
from .input_gate import VerifiedInputs
from .localization import require_localized_text
from .metadata import AssemblyMetadata, extract_encounter_census
from .names import join_monster_names
from .pck import read_selected
from .scaling import extract_hp_multiplayer_scaling
from .states import extract_state_facts
from .world import extract_monster_world

_ENCOUNTER_LOCALIZATION = "localization/eng/encounters.json"
_DLL_PATH = "data_sts2_linuxbsd_x86_64/sts2.dll"
_PCK_PATH = "SlayTheSpire2.pck"


def complete(numerator: int, denominator: int) -> dict[str, Any]:
    if numerator != denominator:
        raise SourceExtractionError(f"cannot mark partial coverage complete: {numerator}/{denominator}")
    return {"denominator": denominator, "numerator": numerator, "status": "complete", "unresolved": 0}


def not_extracted() -> dict[str, str]:
    return {"status": "notExtracted"}


def _encounter_records(
    verified: VerifiedInputs,
    census: dict[str, Any],
    rosters: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    dll = verified.by_relative_path(_DLL_PATH)
    pck = verified.by_relative_path(_PCK_PATH)
    data, entry, info = read_selected(pck.path, _ENCOUNTER_LOCALIZATION)
    localization = strict_json_bytes(data, f"{_PCK_PATH}:{_ENCOUNTER_LOCALIZATION}")
    if not isinstance(localization, dict):
        raise SourceExtractionError("encounter localization top level must be an object")
    blob_sha256 = hashlib.sha256(data).hexdigest()
    roster_by_id = {
        item["canonicalId"]: item
        for kind in ("ordinary", "event")
        for item in rosters[kind]
    }
    encounters: dict[str, list[dict[str, Any]]] = {"event": [], "ordinary": []}
    for kind in ("ordinary", "event"):
        for source in census[kind]:
            canonical_id = source["canonicalId"]
            key = canonical_id + ".title"
            title = require_localized_text(localization, key)
            identity_witness = {
                "category": source["assemblyCategory"],
                "entry": canonical_id,
                "sourceType": source["sourceType"],
            }
            roster = roster_by_id.pop(canonical_id, None)
            if roster is None:
                raise SourceExtractionError(f"missing roster join for {canonical_id}")
            encounters[kind].append({
                "assemblyCategory": source["assemblyCategory"],
                "canonicalId": canonical_id,
                "initialRoster": roster["initialRoster"],
                "kind": kind,
                "nonRosterInitializationRng": roster["nonRosterInitializationRng"],
                "possibleMonsters": roster["possibleMonsters"],
                "possibleMonstersProvenance": roster["possibleMonstersProvenance"],
                "producedMonsters": roster["producedMonsters"],
                "producedMonstersProvenance": roster["producedMonstersProvenance"],
                "productionPools": roster["productionPools"],
                "provenance": {
                    "identity": {
                        "assemblySha256": dll.sha256,
                        "authority": "rawSource",
                        "diagnosticMetadataToken": source["diagnosticMetadataToken"],
                        "modelIdRule": "modelDb.typeToId.v0.111.0",
                        "semanticWitness": identity_witness,
                        "semanticWitnessSha256": witness_sha256(identity_witness),
                        "sourceType": source["sourceType"],
                    },
                    "title": {
                        "authority": "rawSource",
                        "entryMd5": entry.md5,
                        "entrySha256": blob_sha256,
                        "keyValueWitnessSha256": witness_sha256([key, title]),
                        "localizationKey": key,
                        "pckPath": _ENCOUNTER_LOCALIZATION,
                        "pckSha256": pck.sha256,
                    },
                },
                "rosterMethod": roster["rosterMethod"],
                "sourceType": source["sourceType"],
                "title": title,
            })
    if roster_by_id:
        raise SourceExtractionError(f"orphan roster records: {sorted(roster_by_id)!r}")
    return encounters, {
        "entryFlags": entry.flags,
        "entryMd5": entry.md5,
        "entrySha256": blob_sha256,
        "pckDirectoryOffset": info.directory_offset,
        "pckFileCount": info.file_count,
        "pckFormat": info.format,
        "pckGodotVersion": list(info.godot_version),
        "pckPath": _ENCOUNTER_LOCALIZATION,
        "pckSha256": pck.sha256,
    }


def build_artifact(verified: VerifiedInputs) -> bytes:
    dll = verified.by_relative_path(_DLL_PATH)
    pck = verified.by_relative_path(_PCK_PATH)
    assembly = AssemblyMetadata(dll.path)
    try:
        census = extract_encounter_census(dll.path, dll.sha256, assembly=assembly)
        world = extract_monster_world(dll.path, dll.sha256, assembly=assembly)
        known_models = {"MONSTER." + item["canonicalId"] for item in world["concrete"]}
        rosters = extract_rosters(dll.path, dll.sha256, census, known_models, assembly=assembly)
        name_data = join_monster_names(
            world["concrete"], set(rosters["reachableModels"]), dll.path, dll.sha256,
            pck.path, pck.sha256, assembly=assembly
        )
        state_facts = extract_state_facts(dll.path, dll.sha256, assembly=assembly)
        hp_scaling = extract_hp_multiplayer_scaling(dll.path, dll.sha256, assembly=assembly)
    finally:
        assembly.close()
    reachable = set(rosters["reachableModels"])
    ordinary_reachable = set(rosters["ordinaryReachableModels"])
    event_only = set(rosters["eventOnlyModels"])

    excluded: list[dict[str, str]] = []
    expected_other = world["otherClassifications"]
    for record in world["concrete"]:
        model_ref = "MONSTER." + record["canonicalId"]
        record["provenance"]["identity"]["authority"] = "rawSource"
        if model_ref in ordinary_reachable:
            record["reachability"] = {"classification": "ordinaryReachable"}
        elif model_ref in event_only:
            record["reachability"] = {"classification": "eventOnly"}
        else:
            if record["canonicalId"] == "DEPRECATED_MONSTER":
                classification = "deprecatedPlaceholder"
            else:
                classification = expected_other.get(record["canonicalId"])
            if classification is None:
                raise SourceExtractionError(f"unclassified concrete monster {record['canonicalId']}")
            record["reachability"] = {"classification": classification}
            excluded.append({
                "canonicalId": record["canonicalId"],
                "classification": classification,
                "sourceType": record["sourceType"],
            })
    if len(excluded) != 12:
        raise SourceExtractionError(f"excluded concrete monster count drift: got {len(excluded)}")

    encounters, encounter_blob = _encounter_records(verified, census, rosters)
    total_encounters = len(encounters["ordinary"]) + len(encounters["event"])

    artifact: dict[str, Any] = {
        "astGrammar": {
            "expressionKinds": ["actRoomFactor", "arithmetic", "ascensionSelect", "compare", "conditional", "constant", "convert", "range", "stateVariable"],
            "numericTypes": ["decimal", "integer", "integerRange"],
            "rosterKinds": ["filteredChoice", "fixed", "permutation", "repeat", "sequence", "uniformChoice", "weightedChoice"],
            "rules": "docs/source-world-model.md#normalized-ast-grammar",
        },
        "authority": {
            "artifactTier": "rawSource",
            "fallbackPolicy": {
                "allowedFutureKinds": ["community", "empirical"],
                "conflictsMustBeExplicit": True,
                "requiredFutureFields": ["kind", "url", "pageRevisionOrRetrievalDate", "claimedGameVersion", "confidence", "status"],
                "silentMerge": False,
            },
        },
        "coverage": {
            "encounterIdentities": complete(total_encounters, 89),
            "encounterPossibleMembership": complete(total_encounters, 89),
            "encounterProductionMembership": complete(total_encounters, 89),
            "encounterRosters": complete(total_encounters, 89),
            "encounterTitlesEnglish": complete(total_encounters, 89),
            "hpInitialConcreteCensus": complete(len(world["hpGetterCensus"]), 120),
            "hpInitialCurrentReachable": complete(len(reachable), 108),
            "hpMultiplayerScaling": complete(1, 1),
            "hpSpecialStateFormulas": complete(4, 4),
            "monsterIdentitiesCurrentReachable": complete(len(reachable), 108),
            "monsterNamesEnglishCurrentReachable": complete(name_data["joinedCount"], 108),
            "monsterNamespaceCensus": complete(121, 121),
            "blockMultiplayerScaling": not_extracted(),
            "moveIntents": not_extracted(),
            "moveMultiplayerScaling": not_extracted(),
            "moveOperations": not_extracted(),
            "moveRegistrationsAndTitles": not_extracted(),
            "moveSelectionGraphs": not_extracted(),
            "patterns": not_extracted(),
            "powerMultiplayerScaling": not_extracted(),
            "powers": not_extracted(),
        },
        "encounterCensus": {
            "abstractTypes": census["abstractTypes"],
            "counts": {
                "abstract": len(census["abstractTypes"]),
                "currentEvent": len(encounters["event"]),
                "currentOrdinary": len(encounters["ordinary"]),
                "currentTotal": total_encounters,
                "deprecatedPlaceholder": len(census["deprecatedPlaceholderTypes"]),
            },
            "deprecatedPlaceholderTypes": census["deprecatedPlaceholderTypes"],
        },
        "encounters": encounters,
        "extractorVersion": EXTRACTOR_VERSION,
        "game": {
            "branch": verified.release["branch"],
            "commit": verified.release["commit"],
            "mainAssemblyHash": verified.release["main_assembly_hash"],
            "version": verified.release["version"],
        },
        "inputs": [
            {"path": item.relative_path, "sha256": item.sha256, "size": item.size}
            for item in sorted(verified.files, key=lambda value: value.relative_path)
        ],
        "monsterCensus": {
            "abstractTypes": world["abstractTypes"],
            "counts": {
                "abstract": 1,
                "concrete": len(world["concrete"]),
                "eventOnlyReachable": len(event_only),
                "excludedConcrete": len(excluded),
                "namespaceTotal": len(world["concrete"]) + len(world["abstractTypes"]),
                "ordinaryReachable": len(ordinary_reachable),
                "totalReachable": len(reachable),
            },
            "excludedConcrete": sorted(excluded, key=lambda item: item["canonicalId"]),
            "hpGetterCensus": world["hpGetterCensus"],
        },
        "monsters": world["concrete"],
        "multiplayerScaling": {"hp": hp_scaling},
        "provenance": {
            "assemblyRules": {"modelDb.typeToId.v0.111.0": census["modelIdRule"]},
            "localizationBlobs": {
                "encountersEnglish": encounter_blob,
                "monstersEnglish": name_data["localizationBlob"],
            },
            "titleRules": name_data["titleRules"],
            "witnessCanonicalization": "SHA-256 of UTF-8 RFC 8259 JSON with object keys sorted, no insignificant whitespace, and non-ASCII preserved",
        },
        "reachability": {
            "eventOnlyModels": rosters["eventOnlyModels"],
            "eventReachableModels": rosters["eventReachableModels"],
            "ordinaryReachableModels": rosters["ordinaryReachableModels"],
            "reachableModels": rosters["reachableModels"],
        },
        "runtimeReady": False,
        "safety": {
            "assemblyExecution": False,
            "cilExecution": False,
            "godotInitialization": False,
            "mode": "metadataAndBoundedCilAnalysis",
            "pckAccess": "readOnlySelective",
            "reflectionLoading": False,
        },
        "schemaVersion": SCHEMA_VERSION,
        "states": {
            **state_facts,
            "hatchlingName": name_data["hatchlingName"],
        },
        "status": "incomplete",
    }
    return canonical_json_bytes(artifact)
