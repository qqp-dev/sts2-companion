"""Pure builder for the compact E2 lifecycle encounter projection."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from source_extractor.canonical import atomic_write, canonical_json_bytes, strict_json_bytes, witness_sha256
from source_extractor.errors import SourceExtractionError
from .contract import (
    AUTHORITY, EMBEDDED_SOURCE_INPUTS, GAME, GENERATOR_NAME, GENERATOR_VERSION,
    LEGACY_ARTIFACT, PROJECTION_INPUTS, SCHEMA_VERSION, SOURCE_ARTIFACT,
    SOURCE_EXTRACTOR_VERSION, SOURCE_SCHEMA_VERSION, INTENT_FORMAT_KEYS, INTENT_LOCALIZATION_CONTRACT,
    INTENT_PAIR_STEMS, LOCALIZATION_CATALOG_SHA256, POWER_LOCALIZATION_CONTRACT, coverage_rows,
)


def _without_provenance(value: Any) -> Any:
    """Copy source semantics while replacing bulky proof with fact-level refs."""
    if isinstance(value, list):
        return [_without_provenance(item) for item in value]
    if isinstance(value, dict):
        return {key: _without_provenance(item) for key, item in value.items() if key not in {"provenance", "targetProvenance"}}
    return value


def _compact_lifecycle_value(value: Any) -> Any:
    """Keep lifecycle mechanics/conditions while replacing all CIL proof with refs."""
    if isinstance(value, list):
        return [_compact_lifecycle_value(item) for item in value]
    if isinstance(value, dict):
        if "logicalMethod" in value and "physicalBody" in value:
            return {
                "logicalSymbolSignature": value["logicalMethod"]["symbolSignature"],
                "physicalSymbolSignature": value["physicalBody"]["symbolSignature"],
            }
        if "methodBodySha256" in value and "symbolSignature" in value:
            return {"symbolSignature": value["symbolSignature"]}
        return {key: _compact_lifecycle_value(item) for key, item in value.items()
                if key not in {"provenance", "targetProvenance", "instructionOrigins",
                               "instructionIndex", "normalizedSliceSha256", "semanticWitnessSha256"}}
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
            projected = {"canonicalId": row["canonicalId"], "englishTitle": row["englishTitle"], "factId": fact_id}
            if family == "powers":
                smart = row["smartDescription"]
                projected.update({
                    "titleLocalization": deepcopy(row["provenance"]),
                    "smartDescription": {
                        "classification": smart["classification"], "key": smart["key"],
                        # Null is authoritative, explicit absence; it is never filled from wiki prose.
                        "template": smart.get("template"),
                    },
                })
            result[family].append(projected)
    return result


def _source_intent_localization(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    raw = source["intentLocalization"]
    root_fact = "SOURCE.INTENT_LOCALIZATION.CATALOG"
    facts.add(root_fact, "source", f"EVIDENCE.{root_fact}", "INPUT.SOURCE", ["/intentLocalization"])
    entries = []
    for key, value in raw["entries"].items():
        fact_id = "SOURCE.INTENT_LOCALIZATION." + key.upper()
        pointer = "/intentLocalization/entries/" + _pointer_token(key)
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", [pointer, "/intentLocalization/provenance"])
        entry_kind = "format" if key.startswith("FORMAT_") else "description" if key.endswith(".description") else "title"
        entries.append({
            "catalogFactRef": root_fact, "entryKind": entry_kind, "factId": fact_id,
            "key": key, "provenanceFactRef": root_fact, "value": value,
        })
    pairs = [{
        "descriptionKey": stem + ".description", "pairId": "INTENT_PAIR." + stem,
        "titleKey": stem + ".title",
    } for stem in INTENT_PAIR_STEMS]
    return {
        "entries": entries, "factId": root_fact, "formatKeys": deepcopy(INTENT_FORMAT_KEYS),
        "pairs": pairs, "provenance": deepcopy(raw["provenance"]),
    }


def _intent_localization_ref(intent: dict[str, Any]) -> dict[str, Any]:
    kind = intent["kind"]
    pair_stem = {
        "attack": "ATTACK", "block": "DEFEND", "buff": "BUFF", "cardDebuff": "CARD_DEBUFF",
        "deathBlow": "DEATH_BLOW", "escape": "ESCAPE", "heal": "HEAL", "hidden": "UNKNOWN",
        "sleep": "SLEEP", "status": "STATUS", "stun": "STUN", "summon": "SUMMON",
    }.get(kind)
    selector = {"kind": "intentKind", "value": kind}
    if kind == "debuff":
        argument = intent["arguments"][0] if len(intent["arguments"]) == 1 else None
        strong = argument is not None and argument.get("kind") == "constant" and argument.get("valueType") == "boolean" and argument.get("value") is True
        normal = argument is not None and argument.get("kind") == "constant" and argument.get("valueType") == "boolean" and argument.get("value") is False
        if not (strong or normal):
            return {"kind": kind, "status": "knownUnsupported", "reason": "unresolvedDebuffStrengthArgument"}
        pair_stem = "DEBUFF_STRONG" if strong else "DEBUFF"
        selector = {"argumentIndex": 0, "kind": "booleanArgument", "value": strong}
    if pair_stem is None:
        return {"kind": kind, "status": "knownUnsupported", "reason": "noCheckedLocalizationPair"}
    if intent["intentClass"] == "MultiAttackIntent":
        format_key = "FORMAT_DAMAGE_MULTI"
    elif kind in {"attack", "deathBlow"}:
        format_key = "FORMAT_DAMAGE_SINGLE"
    elif kind == "status":
        format_key = "FORMAT_STATUS_CARD_COUNT"
    else:
        format_key = "FORMAT_EMPTY"
    return {
        "descriptionKey": pair_stem + ".description", "formatKey": format_key, "kind": kind,
        "pairId": "INTENT_PAIR." + pair_stem, "selector": selector, "status": "supported",
        "titleKey": pair_stem + ".title",
    }


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
            "intents": [
                {**compact_intent, "localizationRef": _intent_localization_ref(raw_intent)}
                for raw_intent, compact_intent in zip(row["intents"], _compact_intents(row["intents"]), strict=True)
            ], "operations": _without_provenance(row["operations"]),
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
            "applicabilityKind": (
                "directModel" if concrete and applicable_models == [canonical_monster]
                else "directModelWithInheritedApplicability" if concrete and canonical_monster in applicable_models
                else "inheritedBehavior"
            ),
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
        compact = _without_provenance(row)
        for edge in compact["edges"]:
            weight = edge.get("weight", {})
            if weight.get("kind") == "delegate":
                weight["targetMethod"] = _compact_method(weight["targetMethod"])
        result.append({**compact, "factId": fact_id})
    return result



def _compact_method(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value[key] for key in ("methodBodySha256", "normalizedSliceSha256", "symbolSignature") if key in value}


def _source_random_selection(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    raw = source["behavior"]["randomSelectionContract"]
    fact_id = "SOURCE.RANDOM_SELECTION.CONTRACT"
    facts.add(fact_id, "source", "EVIDENCE." + fact_id, "INPUT.SOURCE", ["/behavior/randomSelectionContract"])
    return {
        "algorithm": deepcopy(raw["algorithm"]), "enumValues": deepcopy(raw["enum"]["values"]),
        "factId": fact_id,
        "methods": {key: _compact_method(value) for key, value in raw["methods"].items()},
        "overloads": [{"method": _compact_method(row["method"]), "parameters": deepcopy(row["parameters"])}
                      for row in raw["overloads"]],
        "summary": deepcopy(raw["summary"]),
    }


def _source_production(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    raw = source["production"]
    fact_id = "SOURCE.PRODUCTION.DISCOVERY_CORE_ADD"
    facts.add(fact_id, "source", "EVIDENCE." + fact_id, "INPUT.SOURCE", ["/production"])
    def site(row: dict[str, Any]) -> dict[str, Any]:
        return {key: deepcopy(row[key]) for key in (
            "siteId", "classification", "reason", "family", "sinkSymbolSignature", "sourceOrder"
        )} | {"callerSymbolSignature": row["caller"]["symbolSignature"]}
    core = deepcopy(raw["coreAddContract"])
    core.pop("validatedOrderInstructionIndices", None)
    core["methods"] = {key: _compact_method(value) for key, value in raw["coreAddContract"]["methods"].items()}
    core["overloads"] = [{"method": _compact_method(row["method"]), "parameters": deepcopy(row["parameters"])}
                         for row in raw["coreAddContract"]["overloads"]]
    roots = []
    for row in raw["producerRoots"]:
        compact = {key: deepcopy(row[key]) for key in row if key != "rootMethod"}
        compact["rootMethod"] = _compact_method(row["rootMethod"])
        roots.append(compact)
    helpers = [{key: deepcopy(row[key]) for key in (
        "callSiteId", "calleeSymbolSignature", "callerSymbolSignature", "sourceOrder"
    )} for row in raw["helperCallSites"]]
    osty_contract = deepcopy(raw["ostySummonContract"])
    osty_contract["methods"] = {key: _compact_method(value) for key, value in raw["ostySummonContract"]["methods"].items()}
    raw_semantics = raw["productionSemantics"]
    semantics = {"sourceDenominators": deepcopy(raw_semantics["sourceDenominators"]),
                 "status": raw_semantics["status"]}
    semantics["producers"] = []
    for index, row in enumerate(raw_semantics["producers"]):
        compact = deepcopy(row)
        compact["provenance"] = _compact_method(row["provenance"])
        if "method" in compact["availability"]:
            compact["availability"]["method"] = _compact_method(row["availability"]["method"])
        compact["dependencies"]["e2aInitialStateFactRefs"] = ["SOURCE." + ref for ref in row["dependencies"]["e2aInitialStateFactRefs"]]
        compact["dependencies"]["e2bHpAssignmentRef"] = "SOURCE.HP_ASSIGNMENT_PIPELINE"
        compact["dependencies"]["e2d2LifecycleRefs"] = ["SOURCE." + ref for ref in row["dependencies"]["e2d2LifecycleRefs"]]
        compact["factId"] = "SOURCE." + row["producerId"]
        facts.add(compact["factId"], "source", "EVIDENCE." + compact["factId"], "INPUT.SOURCE",
                  [f"/production/productionSemantics/producers/{index}"])
        semantics["producers"].append(compact)
    semantics["pools"] = []
    for index, row in enumerate(raw_semantics["pools"]):
        compact = deepcopy(row); compact["provenance"] = _compact_method(row["provenance"])
        if "selectionProvenance" in row:
            compact["selectionProvenance"] = {key: _compact_method(value) for key, value in row["selectionProvenance"].items()}
        compact["factId"] = "SOURCE." + row["poolId"]
        facts.add(compact["factId"], "source", "EVIDENCE." + compact["factId"], "INPUT.SOURCE",
                  [f"/production/productionSemantics/pools/{index}"])
        semantics["pools"].append(compact)
    semantics["slotStrategies"] = []
    for index, row in enumerate(raw_semantics["slotStrategies"]):
        compact = deepcopy(row)
        compact["provenance"] = {key: _compact_method(value) for key, value in row["provenance"].items()}
        compact["factId"] = "SOURCE." + row["slotStrategyId"]
        facts.add(compact["factId"], "source", "EVIDENCE." + compact["factId"], "INPUT.SOURCE",
                  [f"/production/productionSemantics/slotStrategies/{index}"])
        semantics["slotStrategies"].append(compact)
    semantics["postAddEffects"] = []
    for index, row in enumerate(raw_semantics["postAddEffects"]):
        compact = deepcopy(row); compact.pop("validatedOrderInstructionIndices", None)
        compact["provenance"] = _compact_method(row["provenance"])
        if "supportProvenance" in row:
            compact["supportProvenance"] = [_compact_method(value) for value in row["supportProvenance"]]
        compact["factId"] = "SOURCE." + row["effectId"]
        facts.add(compact["factId"], "source", "EVIDENCE." + compact["factId"], "INPUT.SOURCE",
                  [f"/production/productionSemantics/postAddEffects/{index}"])
        semantics["postAddEffects"].append(compact)
    semantics["runtimeStateContracts"] = []
    for index, row in enumerate(raw_semantics["runtimeStateContracts"]):
        compact = deepcopy(row)
        compact["provenance"] = [_compact_method(value) for value in row["provenance"]]
        compact["factId"] = "SOURCE." + row["contractId"]
        facts.add(compact["factId"], "source", "EVIDENCE." + compact["factId"], "INPUT.SOURCE",
                  [f"/production/productionSemantics/runtimeStateContracts/{index}"])
        semantics["runtimeStateContracts"].append(compact)
    semantics["dependencies"] = []
    for index, row in enumerate(raw_semantics["dependencies"]):
        compact = deepcopy(row); compact["factId"] = "SOURCE." + row["dependencyId"]
        facts.add(compact["factId"], "source", "EVIDENCE." + compact["factId"], "INPUT.SOURCE",
                  [f"/production/productionSemantics/dependencies/{index}"])
        semantics["dependencies"].append(compact)
    return {
        "addApiCensus": [site(row) for row in raw["addApiCensus"]],
        "applicability": deepcopy(raw["applicability"]), "coreAddContract": core,
        "directSites": deepcopy(raw["directSites"]), "factId": fact_id,
        "helperCallSites": helpers, "ostySummonCensus": [site(row) for row in raw["ostySummonCensus"]],
        "ostySummonContract": osty_contract,
        "producerRoots": roots, "productionSemantics": semantics,
        "summary": deepcopy(raw["summary"]),
    }


def _source_lifecycle(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    lifecycle=source["lifecycle"]
    fact_id="SOURCE.LIFECYCLE.CORE.E2D2A"
    facts.add(fact_id,"source","EVIDENCE."+fact_id,"INPUT.SOURCE",["/lifecycle"])
    def method_ref(row: dict[str, Any]) -> dict[str, Any]:
        return {"parameters":[item["name"] for item in row["parameters"]],
                "physicalSymbolSignature":row["physicalBody"]["symbolSignature"],
                "symbolSignature":row["method"]["symbolSignature"]}
    dependencies=[]
    for index,row in enumerate(lifecycle["dependencies"]):
        dep_fact_id="SOURCE."+row["dependencyId"]
        facts.add(dep_fact_id,"source","EVIDENCE."+dep_fact_id,"INPUT.SOURCE",[f"/lifecycle/dependencies/{index}"])
        dependencies.append({"factId":dep_fact_id,**deepcopy(row)})
    method_refs={
        "commands":[method_ref(row) for row in lifecycle["api"]["commandDeclarations"]],
        "dispatch":[method_ref(row) for row in lifecycle["dispatchMethods"]],
        "listenerRegistries":[method_ref(row) for row in lifecycle["listenerRegistryMethods"]],
        "removal":[method_ref(row) for row in lifecycle["removalMethods"]],
        "termination":[method_ref(row) for row in lifecycle["combatTerminationMethods"]],
        "actionExecutor":lifecycle["actionExecutorMethod"]["symbolSignature"],
    }
    boundaries=[{"boundaryId":row["boundaryId"],"classification":row["classification"],
                 "effectStatus":row["effectStatus"],"sourceType":row["sourceType"],
                 "symbolSignature":row["method"]["symbolSignature"]} for row in lifecycle["runtimeBoundaries"]]
    return {
        "api":{"commandDeclarations":method_refs["commands"]},
        "combatTermination":deepcopy(lifecycle["combatTermination"]),
        "componentId":lifecycle["componentId"],"core":deepcopy(lifecycle["core"]),
        "dependencies":dependencies,"digests":deepcopy(lifecycle["digests"]),
        "dispatch":deepcopy(lifecycle["dispatch"]),"factId":fact_id,
        "listenerRegistry":deepcopy(lifecycle["listenerRegistry"]),"methodRefs":method_refs,
        "removal":deepcopy(lifecycle["removal"]),
        "runtimeBoundaries":boundaries,"runtimeStateContracts":deepcopy(lifecycle["runtimeStateContracts"]),
        "sourceDenominators":deepcopy(lifecycle["sourceDenominators"]),"status":lifecycle["status"],
        "listenerCensus":deepcopy(lifecycle["listenerCensus"]),
        "mechanics":{
            "cleanup":[{"cleanupId":row["cleanupId"],"classification":row["classification"],
                         "ownerModel":row["ownerModel"],"survivorGameplayEffects":row["survivorGameplayEffects"]}
                        for row in lifecycle["cleanup"]],
            "deathProduction":_compact_lifecycle_value(lifecycle["deathProduction"]),
            "doom":_compact_lifecycle_value(lifecycle["doom"]),
            "eventCombat":_compact_lifecycle_value(lifecycle["eventCombat"]),
            "phaseSystems":_compact_lifecycle_value(lifecycle["phaseSystems"]),
            "powerRetentionPolicies":deepcopy(lifecycle["powerRetentionPolicies"]),
            "relationships":_compact_lifecycle_value(lifecycle["relationships"]),
            "runTermination":_compact_lifecycle_value(lifecycle["runTermination"]),
            "subscriptions":_compact_lifecycle_value(lifecycle["subscriptions"]),
        },
        "semanticPipelineAudit":deepcopy(lifecycle["semanticPipelineAudit"]),
        "closeoutDigests":deepcopy(lifecycle["closeoutDigests"]),
    }


def _source_event_turn_behavior(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    behavior = source["behavior"]
    dependency_fact_ids: dict[str, str] = {}
    dependencies = []
    for index, row in enumerate(behavior["eventDependencies"]):
        fact_id = "SOURCE." + row["dependencyId"]
        dependency_fact_ids[row["dependencyId"]] = fact_id
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
                  [f"/behavior/eventDependencies/{index}"])
        compact = {
            "dependencyId": row["dependencyId"], "factId": fact_id,
            "kind": row["kind"], "sourceRootSymbols": [root["symbolSignature"] for root in row["sourceRoots"]],
            "sourceType": row["sourceType"], "status": row["status"],
            "initialStateFactRefs": ["SOURCE." + ref for ref in row.get("initialStateFactRefs", [])],
        }
        if "resolvedComponentRef" in row:
            compact["resolvedComponentRef"] = row["resolvedComponentRef"]
        dependencies.append(compact)

    encounters = []
    for index, row in enumerate(behavior["eventTurnMachines"]):
        encounter_id = row["canonicalEncounter"]
        fact_id = "SOURCE.EVENT_TURN." + encounter_id
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
                  [f"/behavior/eventTurnMachines/{index}"])
        encounters.append({
            "applicability": row["applicability"],
            "behaviorClassification": row["behaviorClassification"],
            "behaviorOwner": row["behaviorOwner"],
            "behaviorOwnerRef": "SOURCE.BEHAVIOR_OWNER." + row["behaviorOwner"],
            "behaviorOwnerSourceType": row["behaviorOwnerSourceType"],
            "canonicalEncounter": encounter_id, "canonicalEvent": row["canonicalEvent"],
            "canonicalModel": row["canonicalModel"],
            "dependencyRefs": [dependency_fact_ids[ref] for ref in row["dependencyRefs"]],
            "encounterRef": "SOURCE.ENCOUNTER." + encounter_id,
            "eventLinkRef": "SOURCE.EVENT_LINK." + encounter_id,
            "eventSourceType": row["eventSourceType"], "factId": fact_id,
            "graphId": row["graphId"], "graphRef": "SOURCE." + row["graphId"],
            "initialStateFactRefs": ["SOURCE." + ref for ref in row["initialStateFactRefs"]],
            "modelRef": "SOURCE." + row["canonicalModel"],
            "registrationRefs": ["SOURCE.MOVE." + ref.replace("#", ".") for ref in row["registrationIds"]],
            "titles": _without_provenance(row["titles"]),
        })
    return {
        "dependencies": dependencies, "encounters": encounters,
        "invocationSummary": deepcopy(behavior["eventTurnInvocationCensus"]["summary"]),
        "sourceDenominators": deepcopy(behavior["eventTurnSummary"]),
    }


def _source_event_scripts(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    """Project compact E2c2 semantics; omit method/call proof bulk."""
    raw=source["eventScripts"]
    result={}
    specs=(
        ("owners","SOURCE.EVENT_SCRIPT_OWNER",lambda r:r["canonicalEvent"].removeprefix("EVENT.")),
        ("options","SOURCE.EVENT_SCRIPT_OPTION",lambda r:r["optionId"].removeprefix("EVENT_OPTION.").replace("/",".")),
        ("transitions","SOURCE.EVENT_SCRIPT_TRANSITION",lambda r:r["transitionId"].removeprefix("EVENT_TRANSITION.").replace("/",".")),
        ("stateContracts","SOURCE.EVENT_SCRIPT_CONTRACT",lambda r:(r["eventId"].removeprefix("EVENT.")+"."+r["name"].replace(".","_"))),
        ("effects","SOURCE.EVENT_SCRIPT_EFFECT",lambda r:r["effectId"].removeprefix("EVENT_EFFECT.").replace("/",".")),
        ("nodes","SOURCE.EVENT_SCRIPT_NODE",lambda r:r["nodeId"].removeprefix("EVENT_NODE.").replace("/",".")),
        ("edges","SOURCE.EVENT_SCRIPT_EDGE",lambda r:r["edgeId"].removeprefix("EVENT_EDGE.").replace("/",".")),
        ("displayScaling","SOURCE.EVENT_SCRIPT_DISPLAY",lambda r:r["destination"].replace("event.dynamicVars.","").replace(".baseValue","")),
        ("dependencies","SOURCE.EVENT_SCRIPT_DEPENDENCY",lambda r:r["dependencyId"].replace("/",".")),
        ("outcomes","SOURCE.EVENT_SCRIPT_OUTCOME",lambda r:r["outcomeId"].removeprefix("EVENT_OUTCOME.").replace("/",".")),
    )
    for family,prefix,suffix in specs:
        rows=[]
        for index,row in enumerate(raw[family]):
            fact_id=prefix+"."+suffix(row)
            facts.add(fact_id,"source",f"EVIDENCE.{fact_id}","INPUT.SOURCE",[f"/eventScripts/{family}/{index}"])
            compact=_without_provenance(row)
            if family=="owners":
                compact["e1EncounterLinkRefs"]=[x.replace("SOURCE.EVENT_LINK.ENCOUNTER.","SOURCE.EVENT_LINK.") for x in compact["e1EncounterLinkRefs"]]
            elif family=="transitions":
                compact["e1EventLinkRef"]=compact["e1EventLinkRef"].replace("SOURCE.EVENT_LINK.ENCOUNTER.","SOURCE.EVENT_LINK.")
            # Proof methods remain represented by exact identity only; full
            # hashes and CIL call sites stay in raw source data.
            for key in ("method","constructionMethod","callbackMethod","resumeMethod","resumeBody"):
                if isinstance(compact.get(key),dict):
                    m=compact[key]; compact[key]={"methodBodySha256":m["methodBodySha256"],"symbolSignature":m["symbolSignature"]}
            availability=compact.get("availability")
            if isinstance(availability,dict) and isinstance(availability.get("method"),dict):
                m=availability["method"];availability["method"]={"methodBodySha256":m["methodBodySha256"],"symbolSignature":m["symbolSignature"]}
            compact["factId"]=fact_id;rows.append(compact)
        result[family]=rows
    dispatch_id="SOURCE.EVENT_SCRIPT.FOUL_POTION_DISPATCH"
    facts.add(dispatch_id,"source",f"EVIDENCE.{dispatch_id}","INPUT.SOURCE",["/eventScripts/foulPotionDispatch"])
    result["foulPotionDispatch"]={"classification":raw["foulPotionDispatch"]["classification"],"factId":dispatch_id,
                                    "taskJoin":raw["foulPotionDispatch"]["taskJoin"]}
    result["framework"]={"methodCount":raw["sourceDenominators"]["frameworkMethods"],
                          "roles":sorted({x["edgeRole"] for x in raw["frameworkMethods"]})}
    result["invocationSummary"]=deepcopy(raw["invocationCensus"]["summary"])
    result["sourceDenominators"]=deepcopy(raw["sourceDenominators"])

    # Architect is an independent source-closed component. Keep structural
    # localization/control facts and omit its 96 method/715 call proof bulk.
    architect=deepcopy(raw["architect"])
    architect.pop("methods");architect.pop("invocationCensus")
    def compact_methods(value):
        if isinstance(value,dict):
            if "symbolSignature" in value and "methodBodySha256" in value and "metadataSignature" in value:
                return {"methodBodySha256":value["methodBodySha256"],"symbolSignature":value["symbolSignature"]}
            return {key:compact_methods(child) for key,child in value.items()}
        if isinstance(value,list):return [compact_methods(child) for child in value]
        return value
    architect=compact_methods(architect)
    def architect_fact(fact_id,pointer):
        facts.add(fact_id,"source",f"EVIDENCE.{fact_id}","INPUT.SOURCE",[pointer]);return fact_id
    for family in ("applicability","placement","localization","presentation","roomEntry","terminal","visualOnlyCombat"):
        fact_id=architect_fact("SOURCE.ARCHITECT."+family.upper(),f"/eventScripts/architect/{family}")
        architect[family]["factId"]=fact_id
    selection=architect["dialogue"]["selection"]
    selection["factId"]=architect_fact("SOURCE.ARCHITECT.DIALOGUE_SELECTION","/eventScripts/architect/dialogue/selection")
    for ti,template in enumerate(architect["dialogue"]["templates"]):
        suffix=template["templateId"].removeprefix("ARCHITECT_DIALOGUE.")
        template["factId"]=architect_fact("SOURCE.ARCHITECT.TEMPLATE."+suffix,f"/eventScripts/architect/dialogue/templates/{ti}")
        for li,line in enumerate(template["lines"]):
            line["factId"]=architect_fact("SOURCE.ARCHITECT.LINE."+suffix+f".{li}",f"/eventScripts/architect/dialogue/templates/{ti}/lines/{li}")
    for family,prefix,id_key in (("dependencies","SOURCE.ARCHITECT.DEPENDENCY","dependencyId"),
                                 ("runtimeContracts","SOURCE.ARCHITECT.CONTRACT","name"),
                                 ("semanticEffects","SOURCE.ARCHITECT.EFFECT","effectId")):
        for index,row in enumerate(architect[family]):
            suffix=row[id_key].replace("/",".")
            row["factId"]=architect_fact(prefix+"."+suffix,f"/eventScripts/architect/{family}/{index}")
    for index,row in enumerate(architect["initialState"]["options"]):
        suffix=row["optionId"].removeprefix("EVENT_OPTION.").replace("/",".")
        row["factId"]=architect_fact("SOURCE.ARCHITECT.OPTION."+suffix,f"/eventScripts/architect/initialState/options/{index}")
    for family,prefix in (("nodes","SOURCE.ARCHITECT.NODE"),("edges","SOURCE.ARCHITECT.EDGE")):
        for index,row in enumerate(architect["lineControl"][family]):
            source_id=row["nodeId"] if family=="nodes" else row["edgeId"]
            row["factId"]=architect_fact(prefix+"."+source_id.replace("/","."),f"/eventScripts/architect/lineControl/{family}/{index}")
    architect["initialState"]["factId"]=architect_fact("SOURCE.ARCHITECT.INITIAL_STATE","/eventScripts/architect/initialState")
    architect["lineControl"]["factId"]=architect_fact("SOURCE.ARCHITECT.LINE_CONTROL","/eventScripts/architect/lineControl")
    architect["applicability"]["e1EventLinkRef"]=architect["applicability"]["e1EventLinkRef"].replace("SOURCE.EVENT_LINK.ENCOUNTER.","SOURCE.EVENT_LINK.")
    result["architect"]=architect
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


def _source_hp_pipeline(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    """Project semantics and refs, never the 63-site census or CIL proof bulk."""
    fact_id = "SOURCE.HP_ASSIGNMENT_PIPELINE"
    facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE", ["/hpPipeline"])
    compact = deepcopy(source["hpPipeline"])
    compact.pop("callCensus")
    compact.pop("provenance")
    compact["factId"] = fact_id
    return compact


def _source_initial_state(source: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    initial = source["initialState"]
    projected_facts = []
    fact_id_map: dict[str, str] = {}
    for index, row in enumerate(initial["initialStateFacts"]):
        fact_id = "SOURCE." + row["factId"]
        fact_id_map[row["factId"]] = fact_id
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
                  [f"/initialState/initialStateFacts/{index}"])
        compact = _without_provenance(row)
        compact["factId"] = fact_id
        projected_facts.append(compact)

    owners = []
    for index, row in enumerate(initial["initialStateOwners"]):
        fact_id = "SOURCE.INITIAL_OWNER." + row["ownerModel"]
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
                  [f"/initialState/initialStateOwners/{index}"])
        owners.append({
            "applicableModels": deepcopy(row["applicableModels"]),
            "classification": row["classification"], "effectiveHook": row["effectiveHook"],
            "factId": fact_id, "factRefs": [fact_id_map[ref] for ref in row["factRefs"]],
            "inheritancePath": deepcopy(row["inheritancePath"]), "ownerModel": row["ownerModel"],
            "sourceType": row["sourceType"],
        })

    contracts = []
    for index, row in enumerate(initial["runtimeStateContracts"]):
        fact_id = "SOURCE." + row["contractId"]
        facts.add(fact_id, "source", f"EVIDENCE.{fact_id}", "INPUT.SOURCE",
                  [f"/initialState/runtimeStateContracts/{index}"])
        compact = deepcopy(row); compact["factId"] = fact_id
        for site in compact["updateSites"]:
            if "factRef" in site: site["factRef"] = fact_id_map[site["factRef"]]
        contracts.append(compact)

    power_hooks = []
    for row in initial["powerHookClosure"]:
        power_hooks.append({
            "canonicalPower": row["canonicalPower"], "sourceType": row["sourceType"],
            "hooks": [{
                "classification": hook["classification"], "effectiveMethod": hook["effectiveMethod"],
                "effectFactRefs": [fact_id_map[ref] for ref in hook["effectFactRefs"]],
                "hook": hook["hook"], "inheritancePath": deepcopy(hook["inheritancePath"]),
            } for hook in row["hooks"]],
        })

    return {
        "externalHookBoundary": [{
            "family": row["family"], "registryClassification": row["registryClassification"],
            "declarations": [{"classification": item["classification"], "sourceType": item["sourceType"],
                              "symbolSignature": item["method"]["symbolSignature"]}
                             for item in row["declarations"]],
        } for row in initial["externalHookBoundary"]],
        "facts": projected_facts,
        "legacyComparisonFacts": [],
        "owners": owners,
        "powerHookClosure": power_hooks,
        "runtimeStateContracts": contracts,
        "sourceDenominators": deepcopy(initial["sourceDenominators"]),
        "stageOrdering": [{"stage": row["stage"], "symbolSignature": row["method"]["symbolSignature"]}
                          for row in initial["initializationChain"]],
        "summary": deepcopy(initial["summary"]),
    }


def _legacy_power_tokens(value: str) -> list[dict[str, Any]]:
    if not isinstance(value, str) or not value.strip():
        raise SourceExtractionError("legacy startsWithA9 must be a nonempty string")
    result = []
    for raw in re.split(r"[;,]", value):
        token = raw.strip()
        if not token: raise SourceExtractionError(f"empty legacy initial-state token in {value!r}")
        match = re.fullmatch(r"(.+?)\s+(-?\d+)", token)
        result.append({"amount": int(match.group(2)), "title": match.group(1)} if match else {"title": token})
    return result


def _constant_amount(expression: dict[str, Any]) -> int | str | None:
    value = expression
    while value.get("kind") == "convert": value = value["expression"]
    if value.get("kind") != "constant": return None
    raw = value.get("value")
    if type(raw) is int: return raw
    if isinstance(raw, str):
        try:
            integer = int(raw)
        except ValueError:
            return None
        return integer if str(integer) == raw else raw
    return None


def _selection_models(node: dict[str, Any]) -> list[str]:
    kind = node["kind"]
    if kind in {"model", "fixed"}: return [node["model"]]
    result = []
    for key in ("children", "choices"):
        for child in node.get(key, []): result.extend(_selection_models(child))
    if "child" in node: result.extend(_selection_models(node["child"]))
    return result


def _initial_legacy_comparisons(
    source: dict[str, Any], source_facts: dict[str, Any], legacy_annotations: dict[str, Any], facts: _Facts,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    initial = source_facts["initialState"]
    initial_by_owner: dict[str, list[dict[str, Any]]] = {}
    source_index_by_fact = {"SOURCE." + row["factId"]: index for index, row in enumerate(source["initialState"]["initialStateFacts"])}
    for row in initial["facts"]: initial_by_owner.setdefault(row["ownerModel"], []).append(row)
    initial_fact_by_id = {row["factId"]: row for row in initial["facts"]}
    power_hook_by_model = {row["canonicalPower"]: row for row in initial["powerHookClosure"]}
    def with_immediate_power_hooks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result = list(rows); seen = {row["factId"] for row in result}
        for applied in [row for row in rows if row["effect"]["kind"] == "applyPower"]:
            closure = power_hook_by_model.get(applied["effect"]["model"])
            if closure is None: continue
            for hook in closure["hooks"]:
                for ref in hook["effectFactRefs"]:
                    if ref not in seen:
                        result.append(initial_fact_by_id[ref]); seen.add(ref)
        return result
    power_titles = {row["canonicalId"]: row["englishTitle"] for row in source_facts["models"]["powers"]}
    source_power_index = {row["canonicalId"]: index for index, row in enumerate(source["powers"])}
    observed_entries = source_facts["observationIdentities"]["entries"]
    observed = {row["observedId"] for row in observed_entries}
    observed_index = {row["observedId"]: index for index, row in enumerate(source["observationIdentities"]["entries"])}
    state_by_legacy = {
        "MONSTER.HATCHLING": next(row for row in source_facts["states"] if row["stateId"] == "MONSTER.TOUGH_EGG#HATCHED"),
        "MONSTER.TEST_SUBJECT_PHASE_2": next(row for row in source_facts["states"] if row["stateId"] == "MONSTER.TEST_SUBJECT#PHASE_2"),
        "MONSTER.TEST_SUBJECT_PHASE_3": next(row for row in source_facts["states"] if row["stateId"] == "MONSTER.TEST_SUBJECT#PHASE_3"),
    }
    encounters = {row["canonicalId"]: row for kind in ("ordinary", "event") for row in source_facts["encounters"][kind]}
    comparisons=[]; conflicts=[]
    for legacy_encounter in legacy_annotations["current"]:
        encounter_id = legacy_encounter["legacyEncounterId"]
        for body_index, body in enumerate(legacy_encounter["presentationBodies"]):
            annotation = body["annotations"].get("startsWithA9")
            if not annotation: continue
            queried = "MONSTER." + body["annotations"]["monsterId"]
            right_value = {"claimedTokens": _legacy_power_tokens(annotation), "queriedObservedId": queried}
            source_refs: list[str] = []; pointers: list[str] = []
            reason: str | None = None
            if queried in state_by_legacy:
                state = state_by_legacy[queried]
                source_refs=[state["factId"]]
                left_value={"canonicalModel":state["canonicalModel"],"stateId":state["stateId"]}
                status="stateNotModel"; reason="LEGACY_INITIAL_ANNOTATION_DESCRIBES_STATE_NOT_MODEL"
                pointers=[f"/states/stateIdentities/{next(i for i,x in enumerate(source['states']['stateIdentities']) if x['stateId']==state['stateId'])}"]
            elif queried not in observed:
                roster_models=_selection_models(encounters[encounter_id]["initialRoster"]["selection"])
                candidate=roster_models[body_index] if body_index < len(roster_models) else None
                candidate_facts=initial_by_owner.get(candidate or "", [])
                source_refs=[row["factId"] for row in candidate_facts]
                pointers=[f"/initialState/initialStateFacts/{source_index_by_fact[row['factId']]}" for row in candidate_facts]
                pointers.append("/observationIdentities/matchingPolicy")
                if candidate in observed_index: pointers.append(f"/observationIdentities/entries/{observed_index[candidate]}")
                left_value={"candidateCanonicalModel":candidate,"identityJoin":"none"}
                status="unmatchedLegacyIdentity"; reason="LEGACY_SHORTCUT_IS_NOT_SOURCE_ALIAS"
            else:
                candidate_facts=[row for row in initial_by_owner.get(queried, [])
                                 if row.get("encounterApplicability") in {None,"ENCOUNTER."+encounter_id}]
                candidate_facts=with_immediate_power_hooks(candidate_facts)
                source_refs=[row["factId"] for row in candidate_facts]
                pointers=[f"/initialState/initialStateFacts/{source_index_by_fact[row['factId']]}" for row in candidate_facts]
                pointers.append(f"/observationIdentities/entries/{observed_index[queried]}")
                applies=[row for row in candidate_facts if row["effect"]["kind"]=="applyPower"]
                by_title={power_titles.get(row["effect"]["model"]):row for row in applies}
                claims=right_value["claimedTokens"]; normalized=[]; dynamic=False; missing=False
                for claim in claims:
                    match=by_title.get(claim["title"])
                    if match is None: missing=True;continue
                    item={"title":claim["title"]}
                    if "amount" in claim:
                        amount=_constant_amount(match["baseValue"]["expression"])
                        if amount is None: dynamic=True
                        elif amount != claim["amount"]:
                            item["amount"]=amount
                        else: item["amount"]=claim["amount"]
                    normalized.append(item)
                    model=match["effect"]["model"]
                    if model in source_power_index: pointers.append(f"/powers/{source_power_index[model]}")
                extras=[row for row in candidate_facts if row["effect"]["kind"]!="applyPower" or power_titles.get(row["effect"].get("model")) not in {x["title"] for x in claims}]
                if queried=="MONSTER.TOUGH_EGG":
                    status="dynamicNotComparable";reason="SOURCE_INITIAL_STATE_IS_TRIGGER_AND_CURRENT_SIDE_DEPENDENT"
                elif missing:
                    status="partialNonEquivalent";reason="LEGACY_INITIAL_TEXT_HAS_NO_EXACT_SOURCE_POWER_TITLE_MATCH"
                elif dynamic:
                    status="dynamicNotComparable";reason="SOURCE_POWER_AMOUNT_REMAINS_RUNTIME_EXPRESSION"
                elif any(item.get("amount") != claim.get("amount") for item,claim in zip(normalized,claims)):
                    status="conflict";reason=None
                elif extras:
                    status="sourceSuperset";reason="SOURCE_INITIAL_STATE_HAS_ADDITIONAL_ORDERED_GAMEPLAY_EFFECTS"
                else:
                    status="agrees";reason=None
                semantic={"claimedTokens":normalized,"queriedObservedId":queried}
                left_value=right_value if status=="agrees" else {**semantic,"additionalSourceFactRefs":[x["factId"] for x in extras]}
                if not pointers: pointers=["/initialState/sourceDenominators"]
            comparison_fact="SOURCE.INITIAL_LEGACY_COMPARISON."+body["factId"].removeprefix("LEGACY.BODY.")
            facts.add(comparison_fact,"source",f"EVIDENCE.{comparison_fact}","INPUT.SOURCE",sorted(set(pointers)))
            initial["legacyComparisonFacts"].append({"factId":comparison_fact,"legacyFactRef":body["factId"],
                                                     "sourceFactRefs":source_refs,"status":status})
            comparison={"comparisonId":"COMPARE.INITIAL."+body["factId"].removeprefix("LEGACY.BODY."),
                        "family":"initialStateLegacyAnnotation",
                        "left":{"factId":comparison_fact,"lane":"source","value":left_value},
                        "right":{"factId":body["factId"],"lane":"legacy","value":right_value},"status":status}
            if reason is not None: comparison["reasonCode"]=reason
            comparisons.append(comparison)
            if status=="conflict":
                conflicts.append({"conflictId":"CONFLICT."+comparison["comparisonId"],"family":comparison["family"],
                                  "left":deepcopy(comparison["left"]),"right":deepcopy(comparison["right"]),"resolution":"unresolved"})
    if len(comparisons)!=57: raise SourceExtractionError(f"initial-state legacy comparison coverage incomplete: {len(comparisons)}/57")
    return comparisons,conflicts

def _legacy_body(row: dict[str, Any], fact_id: str) -> dict[str, Any]:
    allowed = {
        "count", "displayName", "hpA8", "hpBelowA8", "monsterId", "moves", "pack", "patchChecked",
        "pattern", "retainedProvenance", "role", "sourceFlags", "sourcePage", "startsWithA9", "type",
        "typedConflicts",
    }
    return {
        "annotations": {key: deepcopy(row[key]) for key in sorted(row) if key in allowed},
        "factId": fact_id,
        "provenanceStatus": {"classification": "incompleteKnownUnknown", "missingPerFactFields": ["confidence", "status"]},
    }


def _legacy_annotations(legacy: dict[str, Any], facts: _Facts) -> dict[str, Any]:
    if "DOORMAKER_BOSS" in legacy.get("encounters", {}):
        raise SourceExtractionError("Doormaker leaked into current retained encounters")
    if "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER" in legacy.get("encounters", {}):
        raise SourceExtractionError("Mysterious Knight leaked into current retained encounters")
    archive_encounters = ((legacy.get("archive") or {}).get("encounters")) or {}
    if set(archive_encounters) != {"DOORMAKER_BOSS"}:
        raise SourceExtractionError("retained archive must contain exactly DOORMAKER_BOSS")
    references = legacy.get("retainedReferences") or {}
    if set(references) != {"MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"}:
        raise SourceExtractionError("retained references must contain exactly MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER")
    if references["MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"].get("notACurrentSelector") is not True:
        raise SourceExtractionError("Mysterious Knight retained reference must not be a current selector")

    def project(encounter_id: str, row: dict[str, Any], pointer_prefix: str) -> dict[str, Any]:
        encounter_fact = f"LEGACY.ENCOUNTER.{encounter_id}"
        ep = f"{pointer_prefix}/{_pointer_token(encounter_id)}"
        facts.add(encounter_fact, "legacy", f"EVIDENCE.{encounter_fact}", "INPUT.LEGACY", [ep, "/meta/targetBranch", "/meta/targetVersion"])
        bodies = []
        for index, body in enumerate(row["lineup"]):
            body_fact = f"LEGACY.BODY.{encounter_id}.{index}"
            facts.add(body_fact, "legacy", f"EVIDENCE.{body_fact}", "INPUT.LEGACY", [f"{ep}/lineup/{index}"])
            bodies.append(_legacy_body(body, body_fact))
        return {
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

    current = []
    for encounter_id, row in legacy["encounters"].items():
        projected = project(encounter_id, row, "/encounters")
        projected["canonicalEncounterRef"] = f"SOURCE.ENCOUNTER.{encounter_id}"
        projected["joinBasis"] = "exactCanonicalEncounterId"
        current.append(projected)
    archive = []
    for encounter_id, row in archive_encounters.items():
        projected = project(encounter_id, row, "/archive/encounters")
        projected["archiveReason"] = "absentFromCurrentSourceEncounterCensus"
        archive.append(projected)
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
    rows = [
        {
            "affectedFactIds": [row["factId"] for row in source_facts["initialState"]["facts"]]
                               + [row["factId"] for row in source_facts["production"]["productionSemantics"]["dependencies"]]
                               + [source_facts["production"]["factId"], source_facts["lifecycle"]["factId"]]
                               + [row["factId"] for row in source_facts["lifecycle"]["dependencies"]],
            "detail": "Core kill/escape/removal, generic dispatch/listener registry, and centralized pending-loss/victory mechanics are source-complete E2d2a; concrete listener effects/phases/relationships/death-Add, event reward/parent routing, and run termination remain E2d2b/c/d.",
            "reasonCode": "LIFECYCLE_COVERAGE_REMAINING", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.LIFECYCLE_COVERAGE",
        },
        {
            "affectedFactIds": [row["factId"] for row in source_facts["initialState"]["runtimeStateContracts"]]
                               + [row["factId"] for row in source_facts["production"]["productionSemantics"]["runtimeStateContracts"]]
                               + [row["factId"] for row in source_facts["eventScripts"]["architect"]["runtimeContracts"]]
                               + [row["factId"] for row in source_facts["eventScripts"]["architect"]["dependencies"] if row["kind"] == "formula"],
            "detail": "Initial, production, and Architect runtime inputs are preserved, but live observation adapters, actual RNG outcomes, and companion-wide getter/delegate formula inlining, including ScoreUtility.CalculateScore, remain incomplete.",
            "reasonCode": "FORMULA_RUNTIME_CONTRACT_COVERAGE_INCOMPLETE", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.FORMULA_RUNTIME_CONTRACTS",
        },
        {
            "affectedFactIds": [row["factId"] for row in source_facts["eventTurnBehavior"]["encounters"]]
                               + [row["factId"] for row in source_facts["eventTurnBehavior"]["dependencies"]]
                               + [row["factId"] for row in source_facts["eventScripts"]["owners"]]
                               + [row["factId"] for row in source_facts["eventScripts"]["outcomes"]]
                               + [source_facts["eventScripts"]["architect"][name]["factId"] for name in ("applicability", "terminal", "visualOnlyCombat")],
            "detail": "All eight event turn machines, seven linked non-Architect scripts, and the Architect terminal dialogue script are source-complete; referenced event lifecycle/result and formula producers keep aggregate event behavior unresolved.",
            "reasonCode": "EVENT_BEHAVIOR_AGGREGATE_INCOMPLETE", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.EVENT_BEHAVIOR",
        },
        {
            "affectedFactIds": [row["factId"] for row in source_facts["eventScripts"]["dependencies"] if row["kind"] == "lifecycle"]
                               + [row["factId"] for row in source_facts["eventScripts"]["architect"]["dependencies"] if row["kind"] == "lifecycle"]
                               + [row["factId"] for row in source_facts["eventTurnBehavior"]["dependencies"] if row["kind"] == "eventLifecycleTimeoutResultSemantics"],
            "detail": "Scripts are complete, while Battle timeout/escape/common event terminal results and Architect OnEnded(true), forced-kill, and run-end ordering remain exact E2d2 lifecycle dependencies.",
            "reasonCode": "EVENT_LIFECYCLE_TIMEOUT_RESULT_UNEXTRACTED", "scope": "encounterCompanion", "status": "unresolved",
            "unknownId": "UNKNOWN.EVENT_LIFECYCLE",
        },
        {
            "affectedFactIds": [row["factId"] for row in legacy_annotations["current"] + legacy_annotations["archive"]],
            "detail": "Legacy records lack the per-fact confidence and status fields required by the future community provenance contract.",
            "reasonCode": "LEGACY_PER_FACT_PROVENANCE_INCOMPLETE", "scope": "legacyAnnotations", "status": "unresolved",
            "unknownId": "UNKNOWN.LEGACY_PROVENANCE",
        },
        {
            "affectedFactIds": [],
            "detail": "Complete acts/rooms/events/map rules beyond bounded encounter placement, items, powers/statuses/enchantments, characters/aspects/pools/unlocks, and global combat/lifecycle families remain outside E2a.",
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
    resolved_lifecycle_unknowns = {
        "UNKNOWN.LIFECYCLE_COVERAGE", "UNKNOWN.EVENT_LIFECYCLE", "UNKNOWN.EVENT_BEHAVIOR",
    }
    return [row for row in rows if row["unknownId"] not in resolved_lifecycle_unknowns]


def _resolved_audits(source_facts: dict[str, Any]) -> list[dict[str, Any]]:
    helper = source_facts["scaling"]["hp"]
    pipeline = source_facts["hpPipeline"]
    event_turn = source_facts["eventTurnBehavior"]
    production = source_facts["production"]["productionSemantics"]
    return [{
        "auditId": "AUDIT.RESOLVED.PRODUCTION_SEMANTICS",
        "boundary": "Seven producer triggers and their death/removal, Tough Egg hatch, AfterCreatureAdded listener, and death-Power Add lifecycle refs are source-complete and joined by refs rather than copied.",
        "classificationFactRefs": [row["factId"] for family in ("producers", "pools", "slotStrategies", "postAddEffects", "runtimeStateContracts") for row in production[family]],
        "dependencyFactRefs": [row["factId"] for row in production["dependencies"]],
        "family": "enemyBodyProduction", "historicalStatus": "sourceComplete",
        "sourceDenominators": deepcopy(production["sourceDenominators"]),
    }, {
        "auditId": "AUDIT.RESOLVED.EVENT_TURN_MACHINES",
        "boundary": "Architect scripting and lifecycle timeout/result refs are separately source-complete; formula boundaries remain independent.",
        "classificationFactRefs": [row["factId"] for row in event_turn["encounters"]],
        "dependencyFactRefs": [row["factId"] for row in event_turn["dependencies"]],
        "family": "eventTurnMachines", "historicalStatus": "sourceComplete",
        "sourceDenominators": deepcopy(event_turn["sourceDenominators"]),
    }, {
        "auditId": "AUDIT.RESOLVED.LINKED_EVENT_SCRIPTS",
        "boundary": "The non-Architect scripts, Architect component, and lifecycle producers/results are separately source-complete; formula dependencies remain explicit.",
        "classificationFactRefs": [row["factId"] for row in source_facts["eventScripts"]["owners"]],
        "dependencyFactRefs": [row["factId"] for row in source_facts["eventScripts"]["dependencies"]],
        "family": "linkedEventStartOptionTransitionResume", "historicalStatus": "sourceComplete",
        "sourceDenominators": deepcopy(source_facts["eventScripts"]["sourceDenominators"]),
    }, {
        "auditId": "AUDIT.RESOLVED.ARCHITECT_SCRIPT",
        "boundary": "Dialogue/control/presentation/terminal calls and RunManager OnEnded/forced-kill ordering are source-complete; score formula values remain a dependency.",
        "classificationFactRefs": [source_facts["eventScripts"]["architect"][name]["factId"] for name in ("applicability", "placement", "localization", "initialState", "lineControl", "presentation", "roomEntry", "terminal", "visualOnlyCombat")]
                                  + [row["factId"] for row in source_facts["eventScripts"]["architect"]["dialogue"]["templates"]],
        "dependencyFactRefs": [row["factId"] for row in source_facts["eventScripts"]["architect"]["dependencies"]],
        "family": "architectTerminalScript", "historicalStatus": "sourceComplete",
        "sourceDenominators": deepcopy(source_facts["eventScripts"]["architect"]["sourceDenominators"]),
    }, {
        "auditId": "AUDIT.RESOLVED.CORE_LIFECYCLE",
        "boundary": "Core and aggregate listener/phase/relationship/death-Add/event/run lifecycle are source-complete; formula runtime contracts remain outside this audit.",
        "classificationFactRefs": [source_facts["lifecycle"]["factId"]],
        "dependencyFactRefs": [row["factId"] for row in source_facts["lifecycle"]["dependencies"]],
        "family": "coreLifecycle", "historicalStatus": "sourceComplete",
        "sourceDenominators": deepcopy(source_facts["lifecycle"]["sourceDenominators"]),
    }, {
        "auditId": "AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING",
        "family": "hpAssignmentRounding",
        "historicalStatus": "resolved",
        "lanes": [
            {
                "factId": helper["factId"], "lane": "rawSourceHelper",
                "statement": {"arithmeticRounding": helper["rule"]["numericSemantics"]["rounding"], "outputType": helper["rule"]["numericSemantics"]["outputType"]},
            },
            {
                "factId": pipeline["factId"], "lane": "rawSourceAssignment",
                "statement": {
                    "assignmentConversion": pipeline["assignment"]["numericContract"]["assignmentConversion"],
                    "nonNegativeEquivalence": pipeline["assignment"]["numericContract"]["nonNegativeEquivalence"],
                    "storageType": pipeline["assignment"]["max"]["storageType"],
                },
            },
            {
                "implementationPath": "src/book.mjs::scaleRange", "lane": "stableLegacyConsumer",
                "statement": {"conversion": "Math.floor", "domain": "displayedNonNegativeHp"},
            },
        ],
        "resolution": {
            "classification": "agreementForNonNegativeFinalAssignedHp",
            "detail": "The helper performs no rounding; downstream assignment truncates toward zero, which equals floor only for source-proven non-negative HP. The stable legacy consumer floors displayed non-negative HP.",
            "negativeValuesGeneralized": False,
            "precedenceSelected": False,
        },
    }]


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
                    "initialStateOwnerApplicability", "initialStateFactRuntimeContract", "initialPowerHookClosure",
                    "initialStateLegacyComparisons", "hpArithmeticAssignmentStorage",
                    "eventTurnClassificationDependencies", "eventScriptOwnerEncounterLink",
                    "eventScriptOptionDelegate", "eventScriptTransitionArguments", "eventScriptOutcomeDependency",
                    "architectOwnerPlacementApplicability", "architectLocalizationStructure",
                    "architectDialogueLineGraph", "architectOptionDelegates", "architectVisualOnlyLayout",
                    "architectPresentationGameplayBoundary", "architectTerminalOrder", "architectDependencyRefs",
                    "randomBranchRepeatWeight", "randomSelectionRuntime", "productionDiscovery", "coreAddDependencies",
                    "productionProducerPool", "productionAvailabilityCapRepeat", "productionSlotFailure",
                    "productionRuntimeState", "productionPostAddOrder", "productionLifecycleDependencies",
                    "coreLifecycleApiDispatchRegistryRemovalTermination",
                    "reachableListenerPhaseRelationshipDeathAddEventRunClosure",
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
        "behaviorOwners": owners, "encounters": encounters,
        "eventTurnBehavior": _source_event_turn_behavior(source, facts),
        "eventScripts": _source_event_scripts(source, facts),
        "graphs": _source_graphs(source, facts), "models": models, "monsters": monsters, "moves": moves,
        "randomSelection": _source_random_selection(source, facts),
        "production": _source_production(source, facts),
        "lifecycle": _source_lifecycle(source, facts),
        "observationIdentities": _source_observation_identities(source, facts),
        "placement": _source_placement(source, facts), "scaling": _source_scaling(source, facts),
        "hpPipeline": _source_hp_pipeline(source, facts),
        "stateRules": state_rules, "states": states,
        "initialState": _source_initial_state(source, facts),
        "intentLocalization": _source_intent_localization(source, facts),
    }
    legacy_annotations = _legacy_annotations(legacy, facts)
    legacy_annotations["moveTitleFallbackCandidates"] = _fallback_candidates(source_facts, legacy_annotations)
    comparisons, conflicts = _comparisons_and_conflicts(source_facts, legacy_annotations)
    initial_comparisons, initial_conflicts = _initial_legacy_comparisons(source, source_facts, legacy_annotations, facts)
    comparisons.extend(initial_comparisons); conflicts.extend(initial_conflicts)
    comparisons.sort(key=lambda row: row["comparisonId"]); conflicts.sort(key=lambda row: row["conflictId"])
    unknowns = _known_unknowns(source_facts, legacy_annotations)
    return {
        "conflicts": conflicts, "evidence": sorted(facts.evidence, key=lambda row: row["evidenceId"]),
        "factReferences": sorted(facts.fact_references, key=lambda row: row["factId"]), "knownUnknowns": unknowns,
        "laneComparisons": comparisons, "legacyAnnotations": legacy_annotations, "readiness": _readiness(unknowns),
        "resolvedAudits": _resolved_audits(source_facts),
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
            "localizationProjectionContract": {
                "catalogSha256": LOCALIZATION_CATALOG_SHA256,
                "intent": deepcopy(INTENT_LOCALIZATION_CONTRACT), "power": deepcopy(POWER_LOCALIZATION_CONTRACT),
            },
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
