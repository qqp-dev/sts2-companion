"""Exact current-save/log monster identity observation contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .canonical import witness_sha256
from .errors import SourceExtractionError


def _method(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "assemblySha256", "cilInstructionsSha256", "metadataSignature",
            "methodBodySha256", "normalizedInstructionsSha256", "symbolSignature",
        )
    }


def _one(assembly: Any, owner: str, name: str, assembly_sha256: str) -> dict[str, Any]:
    matches = assembly.find_methods(owner, name)
    if len(matches) != 1:
        raise SourceExtractionError(f"ambiguous identity contract method {owner}::{name}")
    return assembly.method_record(matches[0], assembly_sha256)


def _require_order(record: Mapping[str, Any], fragments: Sequence[str]) -> None:
    operands = [str(row.get("operand") or "") for row in record["instructions"]]
    cursor = -1
    for fragment in fragments:
        matches = [index for index, operand in enumerate(operands) if index > cursor and fragment in operand]
        if not matches:
            raise SourceExtractionError(
                f"identity contract operation {fragment!r} missing from {record['symbolSignature']}"
            )
        cursor = matches[0]


def extract_observation_identities(
    assembly: Any,
    assembly_sha256: str,
    monsters: Sequence[Mapping[str, Any]],
    reachable_models: set[str],
    state_facts: Mapping[str, Any],
) -> dict[str, Any]:
    """Enumerate the complete exact current monster-ID wire domain.

    Current save output is not an alias protocol: it obtains the canonical
    MonsterModel.Id and serializes ModelId.ToString. Dynamic monster states do
    not replace that ID. This function therefore emits one unique direct entry
    per reachable model and a separate non-decodable state observation contract.
    """
    by_model: dict[str, Mapping[str, Any]] = {}
    for row in monsters:
        canonical = row.get("canonicalId")
        source_type = row.get("sourceType")
        if not isinstance(canonical, str) or not isinstance(source_type, str):
            raise SourceExtractionError("monster identity record is incomplete")
        model = "MONSTER." + canonical.removeprefix("MONSTER.")
        if model in by_model:
            raise SourceExtractionError(f"duplicate monster identity {model}")
        by_model[model] = row
    if set(reachable_models) - set(by_model):
        raise SourceExtractionError("reachable monster identity domain is not referentially complete")

    to_string = _one(assembly, "MegaCrit.Sts2.Core.Models.ModelId", "ToString", assembly_sha256)
    _require_order(to_string, ("ModelId::get_Category", "string:.", "ModelId::get_Entry", "System.String::Concat"))
    deserialize = _one(assembly, "MegaCrit.Sts2.Core.Models.ModelId", "Deserialize", assembly_sha256)
    _require_order(deserialize, ("System.String::Split", "ModelId::.ctor"))
    converter_write = _one(
        assembly, "MegaCrit.Sts2.Core.Saves.Runs.ModelIdRunSaveConverter", "Write", assembly_sha256
    )
    _require_order(converter_write, ("System.Object::ToString", "Utf8JsonWriter::WriteStringValue"))
    converter_read = _one(
        assembly, "MegaCrit.Sts2.Core.Saves.Runs.ModelIdRunSaveConverter", "Read", assembly_sha256
    )
    _require_order(converter_read, ("Utf8JsonReader::GetString", "ModelId::Deserialize"))
    initial_save = _one(
        assembly, "MegaCrit.Sts2.Core.Rooms.CombatRoom+<StartCombat>d__46", "MoveNext", assembly_sha256
    )
    _require_order(
        initial_save,
        ("EncounterModel::get_MonstersWithSlots", "::Item1", "MapPointRoomHistoryEntry::get_MonsterIds", "AbstractModel::get_Id", "::Add"),
    )
    summoned_save = _one(
        assembly, "MegaCrit.Sts2.Core.Commands.CreatureCmd+<Add>d__2", "MoveNext", assembly_sha256
    )
    _require_order(
        summoned_save,
        ("MapPointRoomHistoryEntry::get_MonsterIds", "Creature::get_Monster", "AbstractModel::get_Id", "::Add"),
    )
    start_log = _one(
        assembly, "MegaCrit.Sts2.Core.Nodes.Rooms.NCombatRoom", "_Ready", assembly_sha256
    )
    _require_order(
        start_log,
        ("string:Creating NCombatRoom with mode=", "Encounter", "AbstractModel::get_Id", "ModelId::get_Entry", "Log::Info"),
    )
    win_log = _one(
        assembly, "MegaCrit.Sts2.Core.Saves.EncounterStats", "IncrementWin", assembly_sha256
    )
    _require_order(win_log, ("string: has won against encounter ", "EncounterStats::get_Id", "Log::Info"))
    visuals_path = _one(
        assembly, "MegaCrit.Sts2.Core.Models.MonsterModel", "get_VisualsPath", assembly_sha256
    )
    _require_order(visuals_path, ("string:creature_visuals/", "AbstractModel::get_Id", "ModelId::get_Entry", "String::ToLowerInvariant", "SceneHelper::GetScenePath"))
    scene_path = _one(
        assembly, "MegaCrit.Sts2.Core.Helpers.SceneHelper", "GetScenePath", assembly_sha256
    )
    _require_order(scene_path, ("string:res://scenes/", "string:.tscn", "System.String::Concat"))

    entries = []
    for observed_id in sorted(reachable_models):
        row = by_model[observed_id]
        entries.append({
            "canonicalMonster": observed_id,
            "identityKind": "model",
            "observedId": observed_id,
            "sourceType": row["sourceType"],
            "provenance": row["provenance"]["identity"],
        })

    resource_representations = []
    for model in sorted(reachable_models):
        entry = model.split(".", 1)[1]
        if not entry.isascii():
            raise SourceExtractionError(f"resource path entry is outside proved ASCII domain: {entry!r}")
        resource_representations.append({
            "canonicalMonster": model,
            "identityKind": "resourceRepresentationOfModel",
            "resourceId": f"res://scenes/creature_visuals/{entry.lower()}.tscn",
            "transformation": {
                "caseTransform": "ToLowerInvariant", "input": "ModelId.Entry",
                "pathPrefix": "res://scenes/creature_visuals/", "pathSuffix": ".tscn",
            },
            "provenance": {"methods": [_method(visuals_path), _method(scene_path)]},
        })

    raw_states = state_facts.get("stateIdentities")
    if not isinstance(raw_states, list):
        raise SourceExtractionError("state identity census missing from source facts")
    state_contracts = []
    state_ids: set[str] = set()
    for row in raw_states:
        state_id = row.get("stateId")
        model = row.get("canonicalModel")
        if not isinstance(state_id, str) or not isinstance(model, str):
            raise SourceExtractionError("malformed source state identity")
        if state_id in state_ids:
            raise SourceExtractionError(f"duplicate state identity {state_id}")
        if model not in reachable_models:
            raise SourceExtractionError(f"state identity targets non-reachable model {model}")
        state_ids.add(state_id)
        state_contracts.append({
            "canonicalMonster": model,
            "identityKind": "stateOfModel",
            "observation": {
                "distinguishability": "notDistinguishableFromModelIdAlone",
                "emittedModelId": model,
                "separateStateIdEmitted": False,
            },
            "stateId": state_id,
        })

    result = {
        "aliases": [],
        "entries": entries,
        "matchingPolicy": {
            "caseSensitive": True, "fuzzyMatching": False, "prefixStripping": False,
            "wirePrefixes": [{"category": "monsterModel", "prefix": "MONSTER.", "source": "ModelId.Category"}],
        },
        "observationContracts": [
            {
                "contractId": "currentRunSave.monsterIds",
                "identityKind": "model",
                "provenance": {
                    "collectionMethods": [_method(initial_save), _method(summoned_save)],
                    "modelIdMethods": [_method(to_string), _method(converter_write)],
                },
                "wireForm": "MONSTER.<ModelId.Entry>",
            },
            {
                "contractId": "currentRunSave.modelIdRead",
                "identityKind": "model",
                "provenance": {"methods": [_method(converter_read), _method(deserialize)]},
                "wireForm": "<ModelId.Category>.<ModelId.Entry>",
            },
            {
                "contractId": "gameResources.monsterVisualsPath",
                "identityKind": "resourceRepresentationOfModel",
                "provenance": {"methods": [_method(visuals_path), _method(scene_path)]},
                "wireForm": "res://scenes/creature_visuals/<ModelId.Entry.ToLowerInvariant()>.tscn",
            },
            {
                "contractId": "combatLog.encounterStart",
                "identityKind": "encounterEntry",
                "provenance": {"methods": [_method(start_log)]},
                "wireForm": "<Encounter.ModelId.Entry>",
            },
            {
                "contractId": "combatLog.encounterWin",
                "identityKind": "encounterModel",
                "provenance": {"methods": [_method(win_log), _method(to_string)]},
                "wireForm": "ENCOUNTER.<ModelId.Entry>",
            },
        ],
        "resourceRepresentations": resource_representations,
        "sourceConclusions": [
            {
                "code": "CURRENT_MONSTER_WIRE_IDS_ARE_CANONICAL_MODEL_IDS",
                "conclusion": "Current save monster_ids are canonical MonsterModel.Id values; no state or presentation alias is emitted.",
                "evidenceWitnessSha256": witness_sha256([
                    _method(initial_save), _method(summoned_save), _method(to_string), _method(converter_write)
                ]),
            },
            {
                "code": "STATE_NOT_IDENTIFIABLE_FROM_MODEL_ID_ALONE",
                "conclusion": "A canonical monster ModelId does not independently identify a dynamic hatch, phase, or behavior state.",
                "evidenceWitnessSha256": witness_sha256(state_contracts),
            },
        ],
        "sourceDenominators": {
            "currentReachableModels": len(reachable_models),
            "observableIds": len(entries),
            "resourceRepresentations": len(resource_representations),
            "sourceDeclaredCurrentAliases": 0,
            "stateObservationContracts": len(state_contracts),
        },
        "stateObservationContracts": sorted(state_contracts, key=lambda row: row["stateId"]),
    }
    validate_observation_identities(result, reachable_models=reachable_models)
    return result


def resolve_observed_identity(value: Mapping[str, Any], observed_id: str) -> dict[str, Any] | None:
    """Resolve by exact equality only; intentionally has no normalization path."""
    matches = [row for row in value.get("entries", []) if row.get("observedId") == observed_id]
    if len(matches) > 1:
        raise SourceExtractionError(f"ambiguous observed identity {observed_id!r}")
    return matches[0] if matches else None


def validate_observation_identities(value: Any, *, reachable_models: set[str]) -> None:
    required = {
        "aliases", "entries", "matchingPolicy", "observationContracts", "sourceConclusions",
        "resourceRepresentations", "sourceDenominators", "stateObservationContracts",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise SourceExtractionError("malformed observation identity root")
    entries = value["entries"]
    if not isinstance(entries, list):
        raise SourceExtractionError("observation identity entries must be a list")
    observed = [row.get("observedId") for row in entries]
    targets = [row.get("canonicalMonster") for row in entries]
    for row in entries:
        if set(row) not in (
            {"canonicalMonster", "identityKind", "observedId", "sourceType", "provenance"},
            {"canonicalMonster", "identityKind", "observedId", "sourceType"},
        ):
            raise SourceExtractionError("malformed observable identity fields")
        if not isinstance(row.get("sourceType"), str) or not row["sourceType"]:
            raise SourceExtractionError("observable identity lacks exact source type")
    if len(set(observed)) != len(observed) or None in observed:
        raise SourceExtractionError("observable identity collision")
    if set(targets) != set(reachable_models) or any(row.get("identityKind") != "model" for row in entries):
        raise SourceExtractionError("observable identity domain is not exactly the reachable model domain")
    if any(row.get("observedId") != row.get("canonicalMonster") for row in entries):
        raise SourceExtractionError("noncanonical current observable alias found")
    resources = value["resourceRepresentations"]
    resource_ids = [row.get("resourceId") for row in resources]
    resource_targets = [row.get("canonicalMonster") for row in resources]
    if len(resources) != len(reachable_models) or len(set(resource_ids)) != len(resource_ids) or set(resource_targets) != set(reachable_models):
        raise SourceExtractionError("resource observation representations are not unique and referentially complete")
    for row in resources:
        if set(row) not in (
            {"canonicalMonster", "identityKind", "provenance", "resourceId", "transformation"},
            {"canonicalMonster", "identityKind", "resourceId", "transformation"},
        ):
            raise SourceExtractionError("malformed resource representation fields")
        model = row["canonicalMonster"]
        entry = model.split(".", 1)[1]
        expected = f"res://scenes/creature_visuals/{entry.lower()}.tscn"
        expected_transformation = {
            "caseTransform": "ToLowerInvariant", "input": "ModelId.Entry",
            "pathPrefix": "res://scenes/creature_visuals/", "pathSuffix": ".tscn",
        }
        if row.get("identityKind") != "resourceRepresentationOfModel" or row.get("resourceId") != expected or row.get("transformation") != expected_transformation:
            raise SourceExtractionError("resource identity representation differs from exact source transformation")
    aliases = value["aliases"]
    if aliases != []:
        # Future schemas may add aliases only with a separate, fully validated
        # source target/provenance contract. Schema 5 has no such declarations.
        raise SourceExtractionError("current wire contract has no source-declared aliases")
    policy = value["matchingPolicy"]
    if set(policy) != {"caseSensitive", "fuzzyMatching", "prefixStripping", "wirePrefixes"}:
        raise SourceExtractionError("malformed identity matching policy")
    if policy.get("caseSensitive") is not True or policy.get("fuzzyMatching") is not False or policy.get("prefixStripping") is not False:
        raise SourceExtractionError("identity matching policy permits normalization or fuzzy fallback")
    if policy["wirePrefixes"] != [{"category": "monsterModel", "prefix": "MONSTER.", "source": "ModelId.Category"}]:
        raise SourceExtractionError("unproved identity wire prefix")
    contracts = value["observationContracts"]
    if not isinstance(contracts, list):
        raise SourceExtractionError("observation contracts must be a list")
    expected_contracts = {
        "currentRunSave.monsterIds", "currentRunSave.modelIdRead",
        "gameResources.monsterVisualsPath", "combatLog.encounterStart", "combatLog.encounterWin",
    }
    contract_ids = {row.get("contractId") for row in contracts}
    if contract_ids != expected_contracts or len(contracts) != len(expected_contracts):
        raise SourceExtractionError("observation contract denominator or identity mismatch")
    for row in contracts:
        if set(row) not in (
            {"contractId", "identityKind", "provenance", "wireForm"},
            {"contractId", "identityKind", "wireForm"},
        ) or not isinstance(row.get("wireForm"), str) or not row["wireForm"]:
            raise SourceExtractionError("malformed observation contract fields")
    states = value["stateObservationContracts"]
    state_ids = [row.get("stateId") for row in states]
    if len(set(state_ids)) != len(state_ids) or None in state_ids:
        raise SourceExtractionError("state observation identity collision")
    for row in states:
        if set(row) != {"canonicalMonster", "identityKind", "observation", "stateId"}:
            raise SourceExtractionError("malformed state observation fields")
        if row.get("canonicalMonster") not in reachable_models or row.get("identityKind") != "stateOfModel":
            raise SourceExtractionError("state observation has a missing target")
        observation = row.get("observation")
        if observation != {
            "distinguishability": "notDistinguishableFromModelIdAlone",
            "emittedModelId": row["canonicalMonster"],
            "separateStateIdEmitted": False,
        }:
            raise SourceExtractionError("state observation contract invents a wire state alias")
    denominators = value["sourceDenominators"]
    if denominators != {
        "currentReachableModels": len(reachable_models),
        "observableIds": len(entries),
        "resourceRepresentations": len(resources),
        "sourceDeclaredCurrentAliases": 0,
        "stateObservationContracts": len(states),
    }:
        raise SourceExtractionError("observation identity denominator accounting mismatch")
