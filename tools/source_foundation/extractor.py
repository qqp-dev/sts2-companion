"""Build the deterministic v0.111.0 identity/title foundation artifact."""

from __future__ import annotations

import hashlib
from typing import Any

from . import EXTRACTOR_VERSION, SCHEMA_VERSION
from .canonical import canonical_json_bytes, strict_json_bytes, witness_sha256
from .errors import FoundationError
from .input_gate import VerifiedInputs
from .metadata import extract_encounter_census
from .pck import read_selected

_LOCALIZATION_PATH = "localization/eng/encounters.json"
_DLL_PATH = "data_sts2_linuxbsd_x86_64/sts2.dll"
_PCK_PATH = "SlayTheSpire2.pck"


def _status(status: str) -> dict[str, str]:
    return {"status": status}


def build_artifact(verified: VerifiedInputs) -> bytes:
    dll = verified.by_relative_path(_DLL_PATH)
    pck = verified.by_relative_path(_PCK_PATH)
    census = extract_encounter_census(dll.path, dll.sha256)

    localization_bytes, entry, pck_info = read_selected(pck.path, _LOCALIZATION_PATH)
    localization = strict_json_bytes(
        localization_bytes, f"{_PCK_PATH}:{_LOCALIZATION_PATH}"
    )
    if not isinstance(localization, dict):
        raise FoundationError("encounter localization top level must be an object")
    entry_sha256 = hashlib.sha256(localization_bytes).hexdigest()

    encounters: dict[str, list[dict[str, Any]]] = {"event": [], "ordinary": []}
    for kind in ("ordinary", "event"):
        for source in census[kind]:
            canonical_id = source["canonicalId"]
            localization_key = canonical_id + ".title"
            if localization_key not in localization:
                raise FoundationError(
                    f"missing shipped English encounter title: {localization_key}"
                )
            title = localization[localization_key]
            if not isinstance(title, str) or not title:
                raise FoundationError(
                    f"invalid shipped English encounter title: {localization_key}"
                )
            identity_witness = {
                "category": source["assemblyCategory"],
                "entry": canonical_id,
                "sourceType": source["sourceType"],
            }
            encounters[kind].append(
                {
                    "assemblyCategory": source["assemblyCategory"],
                    "canonicalId": canonical_id,
                    "kind": kind,
                    "provenance": {
                        "identity": {
                            "assemblySha256": dll.sha256,
                            "diagnosticMetadataToken": source[
                                "diagnosticMetadataToken"
                            ],
                            "modelIdRule": "modelDb.typeToId.v0.111.0",
                            "semanticWitness": identity_witness,
                            "semanticWitnessSha256": witness_sha256(identity_witness),
                            "sourceType": source["sourceType"],
                        },
                        "title": {
                            "entryMd5": entry.md5,
                            "entrySha256": entry_sha256,
                            "keyValueWitnessSha256": witness_sha256(
                                [localization_key, title]
                            ),
                            "localizationKey": localization_key,
                            "pckPath": _LOCALIZATION_PATH,
                            "pckSha256": pck.sha256,
                        },
                    },
                    "sourceType": source["sourceType"],
                    "title": title,
                }
            )

    ordinary_count = len(encounters["ordinary"])
    event_count = len(encounters["event"])
    total_count = ordinary_count + event_count
    if (ordinary_count, event_count, total_count) != (81, 8, 89):
        raise FoundationError(
            "post-join encounter count drift: "
            f"ordinary={ordinary_count}, event={event_count}, total={total_count}"
        )

    artifact: dict[str, Any] = {
        "coverage": {
            "encounterIdentities": {"count": total_count, "status": "complete"},
            "encounterTitlesEnglish": {"count": total_count, "status": "complete"},
            "hp": _status("notExtracted"),
            "monsterIdentities": _status("notExtracted"),
            "moves": _status("notExtracted"),
            "multiplayerScaling": _status("notExtracted"),
            "patterns": _status("notExtracted"),
            "powers": _status("notExtracted"),
            "rostersAndPools": _status("notExtracted"),
            "stateFormulas": _status("notExtracted"),
        },
        "encounterCensus": {
            "abstractTypes": census["abstractTypes"],
            "counts": {
                "abstract": len(census["abstractTypes"]),
                "currentEvent": event_count,
                "currentOrdinary": ordinary_count,
                "currentTotal": total_count,
                "deprecatedPlaceholder": len(
                    census["deprecatedPlaceholderTypes"]
                ),
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
            {
                "path": item.relative_path,
                "sha256": item.sha256,
                "size": item.size,
            }
            for item in sorted(verified.files, key=lambda value: value.relative_path)
        ],
        "provenance": {
            "assemblyRules": {
                "modelDb.typeToId.v0.111.0": census["modelIdRule"]
            },
            "localizationBlob": {
                "entryFlags": entry.flags,
                "entryMd5": entry.md5,
                "entrySha256": entry_sha256,
                "pckDirectoryOffset": pck_info.directory_offset,
                "pckFileCount": pck_info.file_count,
                "pckFormat": pck_info.format,
                "pckGodotVersion": list(pck_info.godot_version),
                "pckPath": _LOCALIZATION_PATH,
                "pckSha256": pck.sha256,
            },
            "witnessCanonicalization": (
                "SHA-256 of UTF-8 RFC 8259 JSON with object keys sorted, "
                "no insignificant whitespace, and non-ASCII preserved"
            ),
        },
        "runtimeReady": False,
        "safety": {
            "assemblyExecution": False,
            "cilExecution": False,
            "godotInitialization": False,
            "mode": "metadataOnly",
            "pckAccess": "readOnlySelective",
            "reflectionLoading": False,
        },
        "schemaVersion": SCHEMA_VERSION,
        "status": "incomplete",
    }
    return canonical_json_bytes(artifact)
