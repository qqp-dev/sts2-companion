"""Pure builder for the compact E1 encounter projection."""

from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
from typing import Any

from source_extractor.canonical import atomic_write, canonical_json_bytes, strict_json_bytes, witness_sha256
from source_extractor.errors import SourceExtractionError
from .contract import (
    AUTHORITY, EMBEDDED_SOURCE_INPUTS, GAME, GENERATOR_NAME, GENERATOR_VERSION,
    LEGACY_ARTIFACT, PROJECTION_INPUTS, SCHEMA_VERSION, SOURCE_ARTIFACT,
    SOURCE_EXTRACTOR_VERSION, SOURCE_SCHEMA_VERSION, coverage_rows,
)


def _without_provenance(value: Any) -> Any:
    """Copy source semantics while replacing bulky proof with fact-level refs."""
    if isinstance(value, list):
        return [_without_provenance(item) for item in value]
    if isinstance(value, dict):
        return {key: _without_provenance(item) for key, item in value.items() if key not in {"provenance", "targetProvenance"}}
    return value


def _compact_intents(intents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = _without_provenance(intents)
    for intent in result:
        for argument in intent["arguments"]:
            if argument.get("kind") == "sourceDelegate":
                method = argument["targetMethod"]
                argument["targetMethod"] = {
                    "methodBodySha256": method["methodBodySha256"],
                    "normalizedSliceSha256": method["normalizedSliceSha256"],
                    "symbolSignature": method["symbolSignature"],
                }
    return result


def _pointer_token(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


class _Facts:
    def __init__(self, source: dict[str, Any], legacy: dict[str, Any]):
        self.source = source
        self.legacy = legacy
        self.evidence: list[dict[str, Any]] = []
        self.fact_references: list[dict[str, Any]] = []
        self._evidence_ids: set[str] = set()
        self._fact_ids: set[str] = set()

    @staticmethod
    def _resolve(document: Any, pointer: str) -> Any:
        value = document
        if pointer:
            for raw in pointer.split("/")[1:]:
                token = raw.replace("~1", "/").replace("~0", "~")
                value = value[int(token)] if isinstance(value, list) else value[token]
        return value

    def add(self, fact_id: str, lane: str, evidence_id: str, artifact: str, pointers: list[str]) -> None:
        if fact_id in self._fact_ids:
            raise SourceExtractionError(f"duplicate projected fact id {fact_id!r}")
        self._fact_ids.add(fact_id)
        if evidence_id not in self._evidence_ids:
            document = self.source if artifact == "INPUT.SOURCE" else self.legacy
            rows = [{"jsonPointer": p, "valueSha256": witness_sha256(self._resolve(document, p))} for p in pointers]
            self.evidence.append({"artifactInput": artifact, "evidenceId": evidence_id, "lane": lane, "pointers": rows})
            self._evidence_ids.add(evidence_id)
        self.fact_references.append({"evidenceRefs": [evidence_id], "factId": fact_id, "lane": lane})


def _source_encounters(source: dict[str, Any], facts: _Facts) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"event": [], "ordinary": []}
    for kind in ("ordinary", "event"):
        for index, row in enumerate(source["encounters"][kind]):
            fact_id = f"SOURCE.ENCOUNTER.{row['canonicalId']}"
            facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/encounters/{kind}/{index}"])
            result[kind].append({
                "canonicalId": row["canonicalId"], "factId": fact_id,
                "initialRoster": _without_provenance(row["initialRoster"]), "kind": row["kind"],
                "nonRosterInitializationRng": row["nonRosterInitializationRng"],
                "possibleMonsters": deepcopy(row["possibleMonsters"]),
                "producedMonsters": deepcopy(row["producedMonsters"]),
                "productionPools": _without_provenance(row["productionPools"]),
                "sourceType": row["sourceType"], "title": row["title"],
            })
    return result


def _source_monsters(source: dict[str, Any], facts: _Facts) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(source["monsters"]):
        if row["reachability"]["classification"] not in {"ordinaryReachable", "eventOnly"}:
            continue
        canonical_model = f"MONSTER.{row['canonicalId']}"
        fact_id = f"SOURCE.{canonical_model}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/monsters/{index}"])
        result.append({
            "canonicalId": row["canonicalId"], "canonicalModel": canonical_model,
            "factId": fact_id, "initialHp": _without_provenance(row["initialHp"]),
            "name": _without_provenance(row["name"]),
            "reachability": row["reachability"]["classification"], "sourceType": row["sourceType"],
        })
    return result


def _source_states(source: dict[str, Any], monsters: list[dict[str, Any]], facts: _Facts) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_model = {row["canonicalModel"]: row for row in monsters}
    source_monster_index = {f"MONSTER.{row['canonicalId']}": index for index, row in enumerate(source["monsters"])}
    result = []
    for index, identity in enumerate(source["states"]["stateIdentities"]):
        fact_id = f"SOURCE.STATE.{identity['stateId'].replace('#', '.')}"
        name_pointer = (
            "/states/hatchlingName"
            if identity["displayNameKey"] == "HATCHLING.name"
            else f"/monsters/{source_monster_index[identity['canonicalModel']]}/name"
        )
        facts.add(
            fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
            [f"/states/stateIdentities/{index}", name_pointer],
        )
        display_name = _without_provenance(source["states"]["hatchlingName"]) if identity["displayNameKey"] == "HATCHLING.name" else deepcopy(by_model[identity["canonicalModel"]]["name"])
        result.append({**deepcopy(identity), "displayName": display_name, "factId": fact_id})
    rules = {key: _without_provenance(value) for key, value in source["states"].items() if key not in {"stateIdentities", "hatchlingName"}}
    fact_id = "SOURCE.STATE_RULES"
    facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", ["/states"])
    return result, {"factId": fact_id, "rules": rules}


def _source_models(source: dict[str, Any], facts: _Facts) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"cards": [], "powers": []}
    for family in ("cards", "powers"):
        for index, row in enumerate(source[family]):
            fact_id = f"SOURCE.{row['canonicalId']}"
            facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/{family}/{index}"])
            result[family].append({"canonicalId": row["canonicalId"], "englishTitle": row["englishTitle"], "factId": fact_id})
    return result


def _source_moves(source: dict[str, Any], monster_models: set[str], facts: _Facts) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    registrations = source["behavior"]["registrations"]
    applicability = {
        row["behaviorOwnerSourceType"]: row
        for row in source["behavior"]["applicability"]
    }
    moves = []
    owner_source_types: dict[str, str] = {}
    owner_first_index: dict[str, int] = {}
    for index, row in enumerate(registrations):
        owner_source_types.setdefault(row["canonicalMonster"], row["sourceType"])
        owner_first_index.setdefault(row["canonicalMonster"], index)
        fact_id = f"SOURCE.MOVE.{row['canonicalId'].replace('#', '.')}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/behavior/registrations/{index}"])
        moves.append({
            "action": {"executionKind": row["execution"]["kind"], "symbolSignature": row["action"]["symbolSignature"]},
            "applicableConcreteModels": deepcopy(row["applicableConcreteModels"]),
            "canonicalId": row["canonicalId"], "canonicalMonster": row["canonicalMonster"],
            "factId": fact_id, "graphId": row["graphId"],
            "intents": _compact_intents(row["intents"]), "operations": _without_provenance(row["operations"]),
            "ordinal": row["registration"]["ordinal"],
            "ownerRef": f"SOURCE.BEHAVIOR_OWNER.{row['canonicalMonster']}",
            "sourceType": row["sourceType"], "stateId": row["stateId"], "title": _without_provenance(row["title"]),
        })
    owners = []
    applicability_index = {
        row["behaviorOwnerSourceType"]: index
        for index, row in enumerate(source["behavior"]["applicability"])
    }
    for canonical_monster in sorted(owner_source_types):
        fact_id = f"SOURCE.BEHAVIOR_OWNER.{canonical_monster}"
        source_type = owner_source_types[canonical_monster]
        index = owner_first_index[canonical_monster]
        app_index = applicability_index.get(source_type)
        relation = applicability.get(source_type)
        if app_index is None or relation is None:
            raise SourceExtractionError(f"behavior owner lacks source applicability: {source_type}")
        facts.add(
            fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
            [f"/behavior/registrations/{index}", f"/behavior/applicability/{app_index}"],
        )
        concrete = canonical_monster in monster_models
        applicable_models = [row["canonicalMonster"] for row in relation["applicableConcreteModels"]]
        owner = {
            "applicableConcreteModels": applicable_models,
            "applicabilityKind": "directModel" if concrete and applicable_models == [canonical_monster] else "inheritedBehavior",
            "canonicalMonster": canonical_monster, "classification": "concreteModel" if concrete else "abstractBehavior",
            "factId": fact_id, "sourceType": source_type,
        }
        if concrete:
            owner["modelRef"] = f"SOURCE.{canonical_monster}"
        owners.append(owner)
    return moves, owners


def _source_graphs(source: dict[str, Any], facts: _Facts) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(source["behavior"]["graphs"]):
        fact_id = f"SOURCE.{row['graphId']}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/behavior/graphs/{index}"])
        result.append({**_without_provenance(row), "factId": fact_id})
    return result



def _source_placement(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    placement = source["placement"]
    result: dict[str, Any] = {"sourceDenominators": deepcopy(placement["sourceDenominators"])}
    for family, prefix in (("acts", "SOURCE.ACT"), ("pools", "SOURCE.POOL"), ("encounters", "SOURCE.PLACEMENT"), ("eventLinkage", "SOURCE.EVENT_LINK")):
        rows = []
        for index, row in enumerate(placement[family]):
            if family == "acts":
                suffix = row["canonicalId"].removeprefix("ACT.")
            elif family == "pools":
                suffix = row["poolId"].removeprefix("POOL.")
            else:
                suffix = row["canonicalEncounter"].removeprefix("ENCOUNTER.")
            fact_id = f"{prefix}.{suffix}"
            facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/placement/{family}/{index}"])
            rows.append({**_without_provenance(row), "factId": fact_id})
        result[family] = rows
    return result


def _source_observation_identities(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    identities = source["observationIdentities"]
    entries = []
    for index, row in enumerate(identities["entries"]):
        fact_id = f"SOURCE.OBSERVED_IDENTITY.{row['canonicalMonster']}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/observationIdentities/entries/{index}"])
        entries.append({**_without_provenance(row), "factId": fact_id})
    resource_representations = []
    for index, row in enumerate(identities["resourceRepresentations"]):
        fact_id = f"SOURCE.OBSERVED_RESOURCE.{row['canonicalMonster']}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/observationIdentities/resourceRepresentations/{index}"])
        resource_representations.append({**_without_provenance(row), "factId": fact_id})
    state_contracts = []
    for index, row in enumerate(identities["stateObservationContracts"]):
        fact_id = f"SOURCE.OBSERVED_STATE.{row['stateId'].replace('#', '.')}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/observationIdentities/stateObservationContracts/{index}"])
        state_contracts.append({**deepcopy(row), "factId": fact_id})
    policy_fact = "SOURCE.OBSERVATION_IDENTITY_POLICY"
    facts.add(policy_fact, "source", f"EVIDENCE.{policy_fact}", "INPUT.SOURCE", ["/observationIdentities/matchingPolicy", "/observationIdentities/observationContracts", "/observationIdentities/sourceConclusions"])
    return {
        "aliases": deepcopy(identities["aliases"]), "entries": entries,
        "matchingPolicy": deepcopy(identities["matchingPolicy"]),
        "observationContracts": _without_provenance(identities["observationContracts"]),
        "policyFactId": policy_fact, "resourceRepresentations": resource_representations,
        "sourceConclusions": deepcopy(identities["sourceConclusions"]),
        "sourceDenominators": deepcopy(identities["sourceDenominators"]),
        "stateObservationContracts": state_contracts,
    }

def _source_scaling(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    result = {}
    for key in ("hp", "block", "ordinaryMonsterAttack", "power"):
        fact_id = f"SOURCE.SCALING.{key.upper()}"
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [f"/multiplayerScaling/{key}"])
        result[key] = {"factId": fact_id, "rule": _without_provenance(source["multiplayerScaling"][key])}
    return result

def _legacy_body(row: dict[str, Any], fact_id: str) -> dict[str, Any]:
    allowed = {
        "count", "displayName", "hpA8", "monsterId", "moves", "pack", "patchChecked",
        "pattern", "role", "sourceFlags", "sourcePage", "startsWithA9", "type",
    }
    return {
        "annotations": {key: deepcopy(row[key]) for key in sorted(row) if key in allowed},
        "factId": fact_id,
        "provenanceStatus": {"classification": "incompleteKnownUnknown", "missingPerFactFields": ["confidence", "status"]},
    }


def _legacy_annotations(legacy: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    current = []
    archive = []
    for encounter_id, row in legacy["encounters"].items():
        encounter_fact = f"LEGACY.ENCOUNTER.{encounter_id}"
        ep = f"/encounters/{_pointer_token(encounter_id)}"
        facts.add(encounter_fact, "legacy", f"EVIDENCE.{encounter_fact}", "INPUT.LEGACY", [ep, "/meta/targetBranch", "/meta/targetVersion"])
        bodies = []
        for index, body in enumerate(row["lineup"]):
            body_fact = f"LEGACY.BODY.{encounter_id}.{index}"
            facts.add(body_fact, "legacy", f"EVIDENCE.{body_fact}", "INPUT.LEGACY", [f"{ep}/lineup/{index}"])
            bodies.append(_legacy_body(body, body_fact))
        projected = {
            "annotations": {
                "act": row["act"], "displayName": row["name"], "roomClass": row["kind"],
                "rules": deepcopy(row["rules"]), "timing": deepcopy(row["timing"]),
            },
            "factId": encounter_fact, "legacyEncounterId": encounter_id, "presentationBodies": bodies,
            "provenanceStatus": {
                "classification": "incompleteKnownUnknown",
                "claimedTarget": {"branch": legacy["meta"]["targetBranch"], "version": legacy["meta"]["targetVersion"]},
                "missingPerFactFields": ["confidence", "status"],
            },
        }
        if encounter_id == "DOORMAKER_BOSS":
            projected["archiveReason"] = "absentFromCurrentSourceEncounterCensus"
            archive.append(projected)
        else:
            projected["canonicalEncounterRef"] = f"SOURCE.ENCOUNTER.{encounter_id}"
            projected["joinBasis"] = "exactCanonicalEncounterId"
            current.append(projected)
    return {
        "archive": archive, "current": current, "moveTitleFallbackCandidates": [],
        "provenanceContract": {
            "authority": "legacyCommunityAnnotation", "globalSourceDescription": legacy["meta"]["source"],
            "perFactProvenance": "incompleteKnownUnknown", "requiredButAbsent": ["confidence", "status"],
        },
    }


def _range_from_source(monster: dict[str, Any]) -> list[int]:
    row = monster["initialHp"]["a8SinglePlayer"]
    return [row["minimum"]] if row["minimum"] == row["maximum"] else [row["minimum"], row["maximum"]]


def _comparisons_and_conflicts(source_facts: dict[str, Any], legacy_annotations: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    encounters = {row["canonicalId"]: row for row in source_facts["encounters"]["ordinary"]}
    monsters = {row["canonicalId"]: row for row in source_facts["monsters"]}
    placements = {row["canonicalEncounter"].removeprefix("ENCOUNTER."): row for row in source_facts["placement"]["encounters"]}
    observed_ids = {row["observedId"]: row for row in source_facts["observationIdentities"]["entries"]}
    identity_policy_fact = source_facts["observationIdentities"]["policyFactId"]
    comparisons: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    def compare(comparison_id: str, family: str, left_fact: str, left_value: Any, right_fact: str, right_value: Any, *, comparable: bool = True, reason: str | None = None) -> None:
        status = "notStaticallyComparable" if not comparable else ("agrees" if left_value == right_value else "conflict")
        row = {
            "comparisonId": comparison_id, "family": family,
            "left": {"factId": left_fact, "lane": "source", "value": deepcopy(left_value)},
            "right": {"factId": right_fact, "lane": "legacy", "value": deepcopy(right_value)}, "status": status,
        }
        if reason is not None:
            row["reasonCode"] = reason
        comparisons.append(row)
        if status == "conflict":
            conflicts.append({
                "conflictId": f"CONFLICT.{comparison_id}", "family": family, "left": deepcopy(row["left"]),
                "resolution": "unresolved", "right": deepcopy(row["right"]),
            })

    for legacy_encounter in legacy_annotations["current"]:
        encounter_id = legacy_encounter["legacyEncounterId"]
        source_encounter = encounters[encounter_id]
        placement = placements[encounter_id]
        source_act_ids = sorted({row["actId"] for row in placement["memberships"]})
        compare(
            f"ACT_PLACEMENT.{encounter_id}", "encounterActPlacement", placement["factId"],
            {"actIds": source_act_ids, "classification": placement["classification"]},
            legacy_encounter["factId"], {"legacyActAnnotation": legacy_encounter["annotations"]["act"]},
            comparable=False, reason="DISTINCT_SOURCE_AND_LEGACY_ACT_VOCABULARIES",
        )
        source_room_classes = sorted({row["roomClass"] for row in placement["memberships"]})
        legacy_room = legacy_encounter["annotations"]["roomClass"]
        room_comparable = len(source_room_classes) == 1 and source_room_classes[0] in {"elite", "boss"}
        compare(
            f"ROOM_PLACEMENT.{encounter_id}", "encounterRoomClass", placement["factId"],
            source_room_classes[0] if room_comparable else {"roomClasses": source_room_classes, "classification": placement["classification"]},
            legacy_encounter["factId"], legacy_room,
            comparable=room_comparable, reason=None if room_comparable else "DISTINCT_SOURCE_AND_LEGACY_ROOM_VOCABULARIES",
        )
        compare(
            f"ENCOUNTER_TITLE.{encounter_id}", "encounterTitle", source_encounter["factId"], source_encounter["title"],
            legacy_encounter["factId"], legacy_encounter["annotations"]["displayName"],
        )
        for index, body in enumerate(legacy_encounter["presentationBodies"]):
            annotation = body["annotations"]
            queried_observed_id = f"MONSTER.{annotation['monsterId']}"
            observed = observed_ids.get(queried_observed_id)
            compare(
                f"OBSERVED_IDENTITY.{encounter_id}.{index}", "observedMonsterIdentity",
                observed["factId"] if observed is not None else identity_policy_fact,
                queried_observed_id if observed is not None else {"exactSourceMatch": None, "queriedObservedId": queried_observed_id},
                body["factId"], queried_observed_id,
                comparable=observed is not None, reason=None if observed is not None else "NO_EXACT_SOURCE_OBSERVATION_ID",
            )
            monster = monsters.get(annotation["monsterId"])
            if monster is None:
                continue
            name = monster["name"]
            if name["kind"] == "localizedText":
                compare(
                    f"MONSTER_TITLE.{encounter_id}.{index}", "monsterTitle", monster["factId"], name["text"],
                    body["factId"], annotation["displayName"],
                )
            else:
                compare(
                    f"MONSTER_TITLE.{encounter_id}.{index}", "monsterTitle", monster["factId"], name,
                    body["factId"], annotation["displayName"], comparable=False,
                    reason="DYNAMIC_SOURCE_TITLE_REQUIRES_RUNTIME_STATE",
                )
            compare(
                f"HP_A8.{encounter_id}.{index}", "initialHpA8SinglePlayer", monster["factId"], _range_from_source(monster),
                body["factId"], annotation["hpA8"],
            )
    return comparisons, conflicts


def _fallback_candidates(source_facts: dict[str, Any], legacy_annotations: dict[str, Any]) -> list[dict[str, Any]]:
    by_monster: dict[str, list[dict[str, Any]]] = {}
    for encounter in legacy_annotations["current"] + legacy_annotations["archive"]:
        for body in encounter["presentationBodies"]:
            monster = body["annotations"]["monsterId"]
            for index, move in enumerate(body["annotations"]["moves"]):
                by_monster.setdefault(f"MONSTER.{monster}", []).append({
                    "legacyBodyFactId": body["factId"], "legacyMoveIndex": index, "title": move["name"],
                })
    result = []
    for move in source_facts["moves"]:
        if move["title"]["classification"] != "missingLocalization":
            continue
        result.append({
            "basis": "sameExactCanonicalMonsterIdOnly",
            "candidateId": f"FALLBACK_CANDIDATES.{move['canonicalId'].replace('#', '.')}",
            "candidates": deepcopy(by_monster.get(move["canonicalMonster"], [])),
            "sourceMoveFactId": move["factId"], "status": "unjoinedCandidateSet",
        })
    return result

def _known_unknowns(source_facts: dict[str, Any], legacy_annotations: dict[str, Any]) -> list[dict[str, Any]]:
    encounter_facts = [row["factId"] for kind in ("ordinary", "event") for row in source_facts["encounters"][kind]]
    event_facts = [row["factId"] for row in source_facts["encounters"]["event"]]
    monster_facts = [row["factId"] for row in source_facts["monsters"]]
    rows = [
        {
            "affectedFactIds": monster_facts,
            "detail": "Complete starts-with powers and initial model state coverage is an E2 prerequisite.",
            "reasonCode": "INITIAL_STATE_COVERAGE_ABSENT", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.INITIAL_STATES",
        },
        {
            "affectedFactIds": event_facts,
            "detail": "Event encounter identities and rosters are present, but event-model behavior coverage is an E2 prerequisite.",
            "reasonCode": "EVENT_BEHAVIOR_COVERAGE_ABSENT", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.EVENT_BEHAVIOR",
        },
        {
            "affectedFactIds": [source_facts["scaling"]["hp"]["factId"]],
            "detail": "Source HP scaling declares no rounding/truncation. The audited stable consumer floors 2P values, but runtime source is outside E1's two-input evidence boundary; no precedence is selected.",
            "reasonCode": "SOURCE_VS_STABLE_HP_ROUNDING_CONFLICT", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.HP_ROUNDING_CONFLICT",
        },
        {
            "affectedFactIds": [row["factId"] for row in legacy_annotations["current"] + legacy_annotations["archive"]],
            "detail": "Legacy records lack the per-fact confidence and status fields required by the future community provenance contract.",
            "reasonCode": "LEGACY_PER_FACT_PROVENANCE_INCOMPLETE", "scope": "legacyAnnotations", "status": "unresolved",
            "unknownId": "UNKNOWN.LEGACY_PROVENANCE",
        },
        {
            "affectedFactIds": [],
            "detail": "Complete acts/rooms/events/map rules beyond bounded encounter placement, items, powers/statuses/enchantments, characters/aspects/pools/unlocks, and global combat/lifecycle families remain outside E1.",
            "reasonCode": "BROADER_WORLD_MODEL_FAMILIES_ABSENT", "scope": "worldModel", "status": "unresolved",
            "unknownId": "UNKNOWN.BROADER_WORLD_MODEL",
        },
    ]
    candidates = {row["sourceMoveFactId"]: row for row in legacy_annotations["moveTitleFallbackCandidates"]}
    for move in source_facts["moves"]:
        if move["title"]["classification"] != "missingLocalization":
            continue
        candidate = candidates[move["factId"]]
        rows.append({
            "affectedFactIds": [move["factId"]] + [row["legacyBodyFactId"] for row in candidate["candidates"]],
            "detail": "Source move localization is missing/internal. Same-monster legacy move names are unjoined candidates, never selected fallbacks.",
            "reasonCode": "SOURCE_MOVE_TITLE_MISSING_OR_INTERNAL", "scope": "projectedMoves", "status": "unresolved",
            "unknownId": f"UNKNOWN.MOVE_TITLE.{move['canonicalId'].replace('#', '.')}",
        })
    return rows


def _readiness(known_unknowns: list[dict[str, Any]]) -> dict[str, Any]:
    by_scope: dict[str, list[str]] = {}
    for row in known_unknowns:
        by_scope.setdefault(row["scope"], []).append(row["unknownId"])
    return {
        "global": {"ready": False, "reasonRefs": sorted(by_scope.get("worldModel", [])), "status": "incomplete"},
        "root": {"ready": False, "reasonRefs": sorted(row["unknownId"] for row in known_unknowns), "status": "incomplete"},
        "runtimeScopes": {
            "encounterCompanion": {
                "ready": False, "reasonRefs": sorted(by_scope.get("encounterCompanion", [])), "status": "incomplete",
            },
            "encounterProjection": {
                "ready": True, "requiredCoverageFamilies": [row["family"] for row in coverage_rows()],
                "requiredJoins": [
                    "encounterToMonster", "stateToModel", "registrationToBehaviorOwner", "graphTopology",
                    "operationModel", "legacyToCanonical", "factToEvidence", "encounterPlacement",
                    "eventEncounterLinkage", "observationIdentity", "behaviorApplicability",
                ],
                "status": "complete",
            },
        },
    }


def build_payload(source: dict[str, Any], legacy: dict[str, Any]) -> dict[str, Any]:
    facts = _Facts(source, legacy)
    encounters = _source_encounters(source, facts)
    monsters = _source_monsters(source, facts)
    states, state_rules = _source_states(source, monsters, facts)
    models = _source_models(source, facts)
    moves, owners = _source_moves(source, {row["canonicalModel"] for row in monsters}, facts)
    source_facts = {
        "behaviorOwners": owners, "encounters": encounters, "graphs": _source_graphs(source, facts),
        "models": models, "monsters": monsters, "moves": moves,
        "observationIdentities": _source_observation_identities(source, facts),
        "placement": _source_placement(source, facts), "scaling": _source_scaling(source, facts),
        "stateRules": state_rules, "states": states,
    }
    legacy_annotations = _legacy_annotations(legacy, facts)
    legacy_annotations["moveTitleFallbackCandidates"] = _fallback_candidates(source_facts, legacy_annotations)
    comparisons, conflicts = _comparisons_and_conflicts(source_facts, legacy_annotations)
    unknowns = _known_unknowns(source_facts, legacy_annotations)
    return {
        "conflicts": conflicts, "evidence": sorted(facts.evidence, key=lambda row: row["evidenceId"]),
        "factReferences": sorted(facts.fact_references, key=lambda row: row["factId"]), "knownUnknowns": unknowns,
        "laneComparisons": comparisons, "legacyAnnotations": legacy_annotations, "readiness": _readiness(unknowns),
        "sourceFacts": source_facts,
    }


def _verify_input_bytes(data: bytes, expected: dict[str, Any], label: str) -> None:
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != expected["size"]:
        raise SourceExtractionError(f"{label} input size mismatch: expected {expected['size']}, got {len(data)}")
    if digest != expected["sha256"]:
        raise SourceExtractionError(f"{label} input SHA-256 mismatch: expected {expected['sha256']}, got {digest}")


def build_artifact(source_bytes: bytes, legacy_bytes: bytes) -> bytes:
    """Build and fully validate canonical bytes from exactly two checked inputs."""
    _verify_input_bytes(source_bytes, SOURCE_ARTIFACT, "source")
    _verify_input_bytes(legacy_bytes, LEGACY_ARTIFACT, "legacy")
    source = strict_json_bytes(source_bytes, SOURCE_ARTIFACT["path"])
    legacy = strict_json_bytes(legacy_bytes, LEGACY_ARTIFACT["path"])
    payload = build_payload(source, legacy)
    artifact = {
        "authority": deepcopy(AUTHORITY),
        "metadata": {
            "embeddedSourceInputManifest": deepcopy(EMBEDDED_SOURCE_INPUTS),
            "embeddedSourceInputManifestSha256": witness_sha256(EMBEDDED_SOURCE_INPUTS),
            "game": deepcopy(GAME), "generator": {"name": GENERATOR_NAME, "version": GENERATOR_VERSION},
            "payloadSha256": witness_sha256(payload), "projectionInputs": deepcopy(PROJECTION_INPUTS),
            "requiredCoverage": coverage_rows(), "sourceExtractorVersion": SOURCE_EXTRACTOR_VERSION,
            "sourceSchemaVersion": SOURCE_SCHEMA_VERSION,
        },
        "payload": payload, "schemaVersion": SCHEMA_VERSION,
    }
    from .validator import validate_artifact
    validate_artifact(artifact, source=source, legacy=legacy)
    return canonical_json_bytes(artifact)


def regenerate(source_path: Path, legacy_path: Path, output: Path, *, check: bool = False) -> bytes:
    """Build before touching output; in check mode require exact existing bytes."""
    try:
        source_bytes = Path(source_path).read_bytes()
        legacy_bytes = Path(legacy_path).read_bytes()
    except OSError as exc:
        raise SourceExtractionError(f"cannot read projection input: {exc}") from exc
    generated = build_artifact(source_bytes, legacy_bytes)
    if check:
        try:
            existing = Path(output).read_bytes()
        except OSError as exc:
            raise SourceExtractionError(f"cannot read checked projection {output}: {exc}") from exc
        if existing != generated:
            raise SourceExtractionError(f"checked projection differs: regenerate {output} without --check")
    else:
        atomic_write(Path(output), generated)
    return generated
