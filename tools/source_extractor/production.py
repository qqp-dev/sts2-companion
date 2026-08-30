"""Closed enemy-production discovery and core CreatureCmd.Add contract.

This E2d1a component deliberately stops before producer pool/cap/repetition
semantics.  It discovers roots and direct API sinks from metadata/CIL, reuses
the behavior invocation closure, classifies every assembly Add/Summon call,
and proves the shared Add lifecycle boundary without executing game code.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from .canonical import witness_sha256
from .errors import SourceExtractionError

_ADD = "MegaCrit.Sts2.Core.Commands.CreatureCmd::Add"
_OSTY = "MegaCrit.Sts2.Core.Commands.OstyCmd::Summon"
_CREATURE_CMD = "MegaCrit.Sts2.Core.Commands.CreatureCmd"
_MONSTER_NS = "MegaCrit.Sts2.Core.Models.Monsters."


def _method(record: Mapping[str, Any], *, slice_: bool = False) -> dict[str, Any]:
    keys = ["assemblySha256", "cilInstructionsSha256", "diagnosticMetadataToken",
            "metadataSignature", "methodBodySha256", "normalizedInstructionsSha256",
            "symbolSignature"]
    if slice_:
        keys.append("normalizedSliceSha256")
    result = {key: record[key] for key in keys if key in record}
    if slice_ and "normalizedSliceSha256" not in result:
        result["normalizedSliceSha256"] = record["normalizedInstructionsSha256"]
    return result


def _owner(symbol: str) -> str:
    return symbol.split("::", 1)[0]


def _ordered(record: Mapping[str, Any], fragments: list[str]) -> list[int]:
    result = []
    cursor = -1
    for fragment in fragments:
        position = next((index for index, item in enumerate(record["instructions"])
                         if index > cursor and isinstance(item.get("operand"), str)
                         and fragment in item["operand"]), None)
        if position is None:
            raise SourceExtractionError(
                f"core Add order missing {fragment} in {record['symbolSignature']}"
            )
        result.append(position); cursor = position
    return result


def _one_method(assembly: Any, assembly_sha256: str, owner: str, name: str) -> dict[str, Any]:
    matches = assembly.find_methods(owner, name)
    if len(matches) != 1:
        raise SourceExtractionError(f"core method denominator {owner}::{name} = {len(matches)}")
    return assembly.method_record(matches[0], assembly_sha256)


def _all_api_sites(assembly: Any, assembly_sha256: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    # Scan raw bodies first so unrelated non-JSON numeric operands cannot hide a
    # call. Only matched callers are normalized into full provenance records.
    matches: list[tuple[int, int, str, str]] = []
    for method_index, row in enumerate(assembly.md.MethodDef.rows, 1):
        if not row.Rva:
            continue
        body = assembly.method_body(method_index)
        for source_order, instruction in enumerate(body.instructions):
            if instruction.mnemonic not in {"call", "callvirt"}:
                continue
            operand = instruction.operand
            if not hasattr(operand, "value"):
                raise SourceExtractionError(
                    f"unresolved call token in {assembly.method_symbol(method_index)}@{source_order}"
                )
            symbol = assembly.resolve_token(operand)
            family = "creatureAdd" if symbol.startswith(_ADD) else "ostySummon" if symbol.startswith(_OSTY) else None
            if family is not None:
                matches.append((method_index, source_order, symbol, family))
    records = {index: assembly.method_record(index, assembly_sha256) for index, _, _, _ in matches}
    add: list[dict[str, Any]] = []
    osty: list[dict[str, Any]] = []
    for method_index, source_order, symbol, family in matches:
        record = records[method_index]
        site = {"caller": _method(record), "family": family,
                "sinkSymbolSignature": symbol, "sourceOrder": source_order}
        site["siteId"] = ("CREATURE_ADD_SITE." if family == "creatureAdd" else "OSTY_SUMMON_SITE.") + witness_sha256([
            record["symbolSignature"], source_order, symbol,
        ])
        (add if family == "creatureAdd" else osty).append(site)
    add.sort(key=lambda row: (row["caller"]["symbolSignature"], row["sourceOrder"], row["sinkSymbolSignature"]))
    osty.sort(key=lambda row: (row["caller"]["symbolSignature"], row["sourceOrder"], row["sinkSymbolSignature"]))
    if len(add) != 14 or len(osty) != 17:
        raise SourceExtractionError(f"Add/Osty assembly census drift {len(add)}/14, {len(osty)}/17")
    return add, osty


def _root_method(registration: Mapping[str, Any]) -> str:
    execution = registration["execution"]
    if execution["kind"] != "asyncStateMachine":
        raise SourceExtractionError(f"production root is not async: {registration['canonicalId']}")
    return execution["moveNext"]["symbolSignature"]


def _discover_roots(behavior: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], set[tuple[str, int]]]:
    registrations = {row["canonicalId"]: row for row in behavior["registrations"]}
    decisions = behavior["invocationCensus"]["decisions"]
    roots_by_id: dict[str, dict[str, Any]] = {}
    included_keys: set[tuple[str, int]] = set()
    for decision in decisions:
        invocation_id = decision["invocationId"]
        if not invocation_id.startswith("MONSTER."):
            continue
        move_id = invocation_id.split("/invocation/", 1)[0]
        if move_id not in registrations:
            continue
        direct = decision["classification"] == "normalizedGameplayOperation" and decision.get("normalizedKind") == "summon"
        helper = (decision["classification"] == "traversedGameplayHelper"
                  and any(effect.get("kind") == "summon"
                          for effect in decision.get("evidence", {}).get("gameplayEffects", [])))
        if not (direct or helper):
            continue
        registration = registrations[move_id]
        existing = roots_by_id.get(move_id)
        if existing is None:
            roots_by_id[move_id] = {
                "applicableConcreteModels": registration["applicableConcreteModels"],
                "discoveryDecisionRefs": [invocation_id],
                "graphId": registration["graphId"], "moveId": move_id,
                "ownerModel": registration["canonicalMonster"],
                "ownerSourceType": registration["sourceType"],
                "rootMethod": _method(registration["execution"]["moveNext"]),
                "sinkReachability": "direct" if direct else "transitiveHelperClosure",
            }
        else:
            if existing["sinkReachability"] != ("direct" if direct else "transitiveHelperClosure"):
                raise SourceExtractionError(f"production root has mixed direct/helper evidence: {move_id}")
            existing["discoveryDecisionRefs"].append(invocation_id)
        if direct:
            included_keys.add((_root_method(registration), decision["sourceOrder"]))
    # Helper direct Add decisions carry their source method explicitly.
    for decision in decisions:
        if (decision["classification"] == "normalizedGameplayOperation"
                and decision.get("normalizedKind") == "summon"
                and decision["invocationId"].startswith("HELPER.")):
            included_keys.add((decision["sourceMethod"], decision["sourceOrder"]))
    roots = sorted(roots_by_id.values(), key=lambda row: row["moveId"])
    for root in roots:
        refs = sorted(set(root["discoveryDecisionRefs"]))
        if len(refs) != len(root["discoveryDecisionRefs"]):
            raise SourceExtractionError(f"duplicate production evidence ref: {root['moveId']}")
        root["discoveryDecisionRefs"] = refs
    helpers = []
    for decision in decisions:
        evidence = decision.get("evidence", {})
        if (decision["classification"] != "traversedGameplayHelper"
                or not any(effect.get("kind") == "summon" for effect in evidence.get("gameplayEffects", []))):
            continue
        # Keep only edges reachable from a discovered root or another helper.
        if not (decision["invocationId"].startswith("MONSTER.")
                or decision["invocationId"].startswith("HELPER.")):
            continue
        helpers.append({
            "callSiteId": decision["invocationId"],
            "calleeSymbolSignature": evidence["symbolSignature"],
            "callerSymbolSignature": decision.get("sourceMethod") or _root_method(registrations[decision["invocationId"].split("/invocation/", 1)[0]]),
            "gameplayEffects": evidence["gameplayEffects"],
            "sourceOrder": decision["sourceOrder"],
            "traversedMethods": evidence["traversedMethods"],
        })
    helpers.sort(key=lambda row: row["callSiteId"])
    if (len(roots), len({row["ownerModel"] for row in roots}), len(helpers),
            len({row["calleeSymbolSignature"] for row in helpers})) != (7, 6, 5, 3):
        raise SourceExtractionError("production root/helper closure denominator drift")
    return roots, helpers, included_keys


def _classify_add_sites(sites: list[dict[str, Any]], included: set[tuple[str, int]]) -> None:
    for site in sites:
        caller = site["caller"]["symbolSignature"]
        key = (caller, site["sourceOrder"])
        owner = _owner(caller)
        if key in included:
            classification, reason = "currentEnemyEncounterProduction", "reachableFromCurrentBehaviorRoot"
        elif owner.startswith(_CREATURE_CMD + "+<Add>d__"):
            classification, reason = "coreAddForwarding", "sharedCreatureAddImplementation"
        elif owner.startswith("MegaCrit.Sts2.Core.Commands.PlayerCmd+<AddPet>"):
            classification, reason = "outOfScopePlayerPet", "playerCommandNotEnemyEncounterProduction"
        elif ".Models.Monsters.Mocks." in owner:
            classification, reason = "outOfScopeMock", "mockMonsterNotCurrentReachableBehavior"
        elif owner.startswith("MegaCrit.Sts2.Core.Models.Powers.") and "+<AfterDeath>" in owner:
            classification, reason = "outOfScopeDeathPower", "deathLifecyclePendingE2d2"
        else:
            raise SourceExtractionError(f"unclassified CreatureCmd.Add call site: {caller}@{site['sourceOrder']}")
        site["classification"] = classification
        site["reason"] = reason


def _classify_osty_sites(sites: list[dict[str, Any]]) -> None:
    for site in sites:
        owner = _owner(site["caller"]["symbolSignature"])
        if ".Mocks." in owner:
            site["classification"] = "outOfScopeMockOstySummon"
            site["reason"] = "mockPlayerSummon"
        elif owner.startswith(("MegaCrit.Sts2.Core.Models.Cards.", "MegaCrit.Sts2.Core.Models.Potions.",
                               "MegaCrit.Sts2.Core.Models.Powers.", "MegaCrit.Sts2.Core.Models.Relics.")):
            site["classification"] = "separateOstySummonApi"
            site["reason"] = "playerOstyLifecycleNotCreatureAddEnemyProduction"
        else:
            raise SourceExtractionError(f"unclassified OstyCmd.Summon call site: {owner}")


def _generic_model(symbol: str, source_to_model: Mapping[str, str]) -> str | None:
    marker = " generic:"
    if marker not in symbol:
        return None
    source_type = symbol.split(marker, 1)[1]
    model = source_to_model.get(source_type)
    if model is None:
        raise SourceExtractionError(f"unknown generic Add monster type {source_type}")
    return model


def _site_semantics(assembly: Any, assembly_sha256: str, sites: list[dict[str, Any]], roots: list[dict[str, Any]],
                    helpers: list[dict[str, Any]], behavior: Mapping[str, Any],
                    encounters: list[Mapping[str, Any]], source_to_model: Mapping[str, str]) -> list[dict[str, Any]]:
    root_by_method = {row["rootMethod"]["symbolSignature"]: row for row in roots}
    direct_ops = {}
    for registration in behavior["registrations"]:
        method = registration["execution"].get("moveNext", {}).get("symbolSignature")
        for operation in registration["operations"]:
            if operation["kind"] == "summon":
                direct_ops[(method, operation["sourceOrder"])] = operation
    helper_root_ids = [row["moveId"] for row in roots if row["sinkReachability"] == "transitiveHelperClosure"]
    result = []
    for site in sites:
        if site["classification"] != "currentEnemyEncounterProduction":
            continue
        caller = site["caller"]["symbolSignature"]
        root = root_by_method.get(caller)
        operation = direct_ops.get((caller, site["sourceOrder"]))
        if root is not None and operation is None:
            raise SourceExtractionError(f"direct Add operation join missing: {caller}@{site['sourceOrder']}")
        if root is not None:
            root_ids = [root["moveId"]]
            canonical_model = _generic_model(site["sinkSymbolSignature"], source_to_model)
            model_argument: dict[str, Any] = {"canonicalModel": canonical_model, "kind": "genericCanonicalModel"}
            candidate_membership = {"canonicalModels": [canonical_model], "classification": "exactGenericType"}
            target = operation["target"]
            slot = operation["selection"]["slot"]
        else:
            if not caller.startswith("MegaCrit.Sts2.Core.Models.Monsters.Fabricator+<SpawnBot>"):
                raise SourceExtractionError(f"unknown shared production sink {caller}")
            owner = _owner(caller)
            record = _one_method(assembly, assembly_sha256, owner, "MoveNext")
            positions = _ordered(record, ["MonsterModel::ToMutable", "MonsterModel::get_CombatState", "ICombatState::get_Encounter", "MonsterModel::get_CombatState", "EncounterModel::GetNextSlot", "CreatureCmd::Add", "::GetResult"])
            if not any(index < positions[5] and item["opcode"] == "ldc.i4.2" for index, item in enumerate(record["instructions"])):
                raise SourceExtractionError("Fabricator Add side argument is not exact Enemy enum 2")
            root_ids = sorted(helper_root_ids)
            model_argument = {"kind": "runtimeCanonicalMonsterModel",
                              "source": "closedTraversedHelperOptionSelection",
                              "producerSemantics": "pendingE2d1b"}
            fabricator_encounters = [row for row in encounters if "MONSTER.FABRICATOR" in row["possibleMonsters"]]
            if len(fabricator_encounters) != 1 or len(fabricator_encounters[0]["producedMonsters"]) != 4:
                raise SourceExtractionError("Fabricator existing produced-membership join is ambiguous")
            candidate_membership = {
                "canonicalEncounter": "ENCOUNTER." + fabricator_encounters[0]["canonicalId"],
                "canonicalModels": fabricator_encounters[0]["producedMonsters"],
                "classification": "existingEncounterProducedMembershipNotPoolSemantics",
            }
            target = "sourceMonsterCombatState"
            slot = "nextOpenCombatSlot"
        if model_argument.get("canonicalModel") is None and model_argument["kind"] == "genericCanonicalModel":
            raise SourceExtractionError(f"generic Add candidate unresolved: {caller}")
        result.append({
            "apiSiteRef": site["siteId"], "awaitedResult": "exactCreatedCreatureBody",
            "candidateMembership": candidate_membership, "modelArgument": model_argument, "rootRefs": root_ids,
            "side": {"enumName": "Enemy", "enumValue": 2},
            "slotArgument": slot, "targetCombat": target,
        })
    result.sort(key=lambda row: row["apiSiteRef"])
    if len(result) != 6 or sum(len(row["rootRefs"]) for row in result) != 7:
        raise SourceExtractionError("production direct-site/root join denominator drift")
    return result


def _core_add_contract(assembly: Any, assembly_sha256: str,
                       initial_state: Mapping[str, Any], hp_pipeline: Mapping[str, Any],
                       candidate_models: set[str]) -> dict[str, Any]:
    overload_ids = assembly.find_methods(_CREATURE_CMD, "Add")
    if len(overload_ids) != 3:
        raise SourceExtractionError(f"CreatureCmd.Add overload denominator {len(overload_ids)}/3")
    overloads = []
    for index in overload_ids:
        record = assembly.method_record(index, assembly_sha256)
        row = assembly.md.MethodDef.rows[index - 1]
        params = [str(item.row.Name) for item in row.ParamList if item.row.Sequence]
        if params not in (["combatState", "slotName"], ["monster", "combatState", "side", "slotName"], ["creature"]):
            raise SourceExtractionError(f"unknown CreatureCmd.Add overload parameters {params!r}")
        overloads.append({"method": _method(record), "parameters": params})
    machines = {}
    for owner, key in [
        (_CREATURE_CMD + "+<Add>d__0`1", "genericModel"),
        (_CREATURE_CMD + "+<Add>d__1", "explicitModel"),
        (_CREATURE_CMD + "+<Add>d__2", "existingBody"),
    ]:
        machines[key] = _one_method(assembly, assembly_sha256, owner, "MoveNext")
    _ordered(machines["genericModel"], ["ModelDb::Monster", "MonsterModel::ToMutable", "ICombatState::CreateCreature",
                                         "CreatureCmd::Add", "TaskAwaiter::GetResult", "::SetResult"])
    _ordered(machines["explicitModel"], ["AbstractModel::AssertMutable", "ICombatState::CreateCreature",
                                          "CreatureCmd::Add", "TaskAwaiter::GetResult", "::SetResult"])
    body = machines["existingBody"]
    order = _ordered(body, [
        "CombatManager::get_IsInProgress", "Creature::get_CombatState", "ICombatState::IsLiveCombat",
        "ICombatState::AddCreature", "CombatManager::AddCreature", "NCombatRoom::AddCreature",
        "CombatManager::AfterCreatureAdded", "TaskAwaiter::GetResult", "Creature::PrepareForNextTurn",
        "MapPointRoomHistoryEntry::get_MonsterIds", "::Contains", "MapPointRoomHistoryEntry::get_MonsterIds",
        "::Add", "Hook::AfterCreatureAddedToCombat", "TaskAwaiter::GetResult", "::SetResult",
    ])
    if any(isinstance(item.get("operand"), str) and ("AfterSummon" in item["operand"] or "GetNextSlot" in item["operand"])
           for record in machines.values() for item in record["instructions"]):
        raise SourceExtractionError("core Add acquired AfterSummon or slot validation")
    create = _one_method(assembly, assembly_sha256, "MegaCrit.Sts2.Core.Combat.CombatState", "CreateCreature")
    _ordered(create, ["Creature::.ctor", "EncounterModel::OnCreatureSpawned"])
    spawned = _one_method(assembly, assembly_sha256, "MegaCrit.Sts2.Core.Models.EncounterModel", "OnCreatureSpawned")
    _ordered(spawned, ["Creature::get_Side", "Creature::get_Monster", "MonsterModel::get_CanonicalInstance",
                       "::_spawnedEnemies", "::Contains", "::_spawnedEnemies", "::Add"])
    add_creature = _one_method(assembly, assembly_sha256, "MegaCrit.Sts2.Core.Combat.CombatState", "AddCreature")
    _ordered(add_creature, ["Creature::get_CombatState", "Creature::get_Side", "CombatState::ContainsCreature", "::Add"])
    initial_stages = [row["stage"] for row in initial_state["initializationChain"]]
    required_initial = {"creatureCreation", "encounterSpawnRegistration", "creatureAdded",
                        "modelAdditionHookDispatch", "effectiveMonsterAdditionHook"}
    if not required_initial <= set(initial_stages):
        raise SourceExtractionError("core Add to E2a initialization-chain join is incomplete")
    if not hp_pipeline.get("sourceDenominators"):
        raise SourceExtractionError("core Add to E2b HP pipeline dependency is absent")
    initial_by_model = {row["ownerModel"]: row for row in initial_state["initialStateOwners"]}
    if not candidate_models or not candidate_models <= set(initial_by_model):
        raise SourceExtractionError("produced candidate to E2a owner join is incomplete")
    initial_fact_refs = sorted({ref for model in candidate_models for ref in initial_by_model[model]["factRefs"]})
    no_gameplay_fact_models = sorted(model for model in candidate_models if not initial_by_model[model]["factRefs"])
    if len(candidate_models) != 9 or len(initial_fact_refs) != 7 or len(no_gameplay_fact_models) != 4:
        raise SourceExtractionError("produced candidate E2a fact/no-op denominator drift")
    return {
        "callOrder": [
            "createBody", "encounterOnCreatureSpawned", "coreLiveCheck", "combatBodyListInsertion",
            "combatManagerNodeInsertion", "roomNodeInsertion", "awaitInitialStateDispatch",
            "prepareForNextTurn", "uniqueRoomMonsterIdHistory", "awaitAfterCreatureAddedToCombat", "returnCreatedBody",
        ],
        "dependencies": {
            "hpAssignmentComponentRef": "hpPipeline.assignment",
            "initialStateComponentRef": "initialState",
            "initialStateFactRefs": initial_fact_refs,
            "initialStateNoGameplayFactModels": no_gameplay_fact_models,
            "initialStateOwnerModels": sorted(candidate_models),
            "lifecycle": "pendingE2d2", "producerSemantics": "pendingE2d1b",
        },
        "failureSemantics": {
            "cancellationToken": "absent", "duplicateBody": "InvalidOperationException",
            "differentCombat": "InvalidOperationException", "exceptionPropagation": "asyncSetException",
            "noCombatState": "InvalidOperationException", "notInProgress": "InvalidOperationException",
            "nonLiveCombat": "returnWithoutInsertion", "rollback": "absent",
        },
        "history": {
            "encounterSpawnedEnemies": "unique canonical MonsterModel membership for enemy-side reward/progress history",
            "roomMonsterIds": "unique canonical model ID membership when room history exists",
            "not": ["bodyCount", "productionCap", "poolDepletion"],
        },
        "hookBoundary": {"afterCreatureAddedToCombat": "awaited", "afterSummon": "absentSeparateOstyApi"},
        "methods": {
            "addCreature": _method(add_creature, slice_=True), "createCreature": _method(create, slice_=True),
            "genericModel": _method(machines["genericModel"], slice_=True),
            "explicitModel": _method(machines["explicitModel"], slice_=True),
            "existingBody": _method(body, slice_=True), "spawnHistory": _method(spawned, slice_=True),
        },
        "overloads": sorted(overloads, key=lambda row: row["method"]["symbolSignature"]),
        "resultIdentity": "generic and explicit-model wrappers return the exact body created before awaiting core Add",
        "semanticBoundaries": {"coreSlotValidation": "absent", "emptyOrNoSlot": "producerOwnedPendingE2d1b"},
        "validatedOrderInstructionIndices": order,
    }


def _osty_summon_contract(assembly: Any, assembly_sha256: str) -> dict[str, Any]:
    wrapper = _one_method(assembly, assembly_sha256, "MegaCrit.Sts2.Core.Commands.OstyCmd", "Summon")
    body = _one_method(assembly, assembly_sha256, "MegaCrit.Sts2.Core.Commands.OstyCmd+<Summon>d__0", "MoveNext")
    _ordered(body, ["PlayerCmd::AddPet", "CombatHistory::Summoned", "Hook::AfterSummon", "TaskAwaiter::GetResult", "::SetResult"])
    if not any(isinstance(item.get("operand"), str) and "Hook::AfterSummon" in item["operand"] for item in body["instructions"]):
        raise SourceExtractionError("Osty summon AfterSummon boundary is absent")
    return {
        "afterSummon": "awaitedAfterOstyAddOrReviveHistory",
        "classification": "separateFromCreatureCmdAddEnemyProduction",
        "methods": {"summon": _method(wrapper, slice_=True), "stateMachine": _method(body, slice_=True)},
    }


def extract_production(assembly: Any, assembly_sha256: str, behavior: Mapping[str, Any],
                       monsters: list[Mapping[str, Any]], encounters: Mapping[str, list[Mapping[str, Any]]],
                       initial_state: Mapping[str, Any], hp_pipeline: Mapping[str, Any]) -> dict[str, Any]:
    roots, helpers, included = _discover_roots(behavior)
    add_sites, osty_sites = _all_api_sites(assembly, assembly_sha256)
    _classify_add_sites(add_sites, included); _classify_osty_sites(osty_sites)
    included_sites = [row for row in add_sites if row["classification"] == "currentEnemyEncounterProduction"]
    if len(included_sites) != 6:
        raise SourceExtractionError(f"current enemy Add sink denominator {len(included_sites)}/6")
    source_to_model = {row["sourceType"]: "MONSTER." + row["canonicalId"] for row in monsters}
    all_encounters = encounters["ordinary"] + encounters["event"]
    applicability = []
    for owner_model in sorted({row["ownerModel"] for row in roots}):
        matches = [row for row in all_encounters if owner_model in row["possibleMonsters"]]
        if len(matches) != 1:
            raise SourceExtractionError(f"producer encounter applicability denominator {owner_model}={len(matches)}")
        applicability.append({"canonicalEncounter": "ENCOUNTER." + matches[0]["canonicalId"],
                              "ownerModel": owner_model, "sourceType": matches[0]["sourceType"]})
    semantics = _site_semantics(assembly, assembly_sha256, add_sites, roots, helpers, behavior, all_encounters, source_to_model)
    candidate_models = {model for site in semantics for model in site["candidateMembership"]["canonicalModels"]}
    classifications = defaultdict(int)
    for row in add_sites: classifications[row["classification"]] += 1
    summary = {
        "addAssemblySites": len(add_sites), "currentDirectSites": len(included_sites),
        "helperCallEdges": len(helpers), "helperMethods": len({row["calleeSymbolSignature"] for row in helpers}),
        "ostyAssemblySites": len(osty_sites), "ownerEncounterApplicability": len(applicability),
        "producerOwners": len({row["ownerModel"] for row in roots}), "producerRoots": len(roots),
        "siteClassifications": dict(sorted(classifications.items())),
    }
    return {
        "addApiCensus": add_sites, "applicability": applicability,
        "coreAddContract": _core_add_contract(assembly, assembly_sha256, initial_state, hp_pipeline, candidate_models),
        "directSites": semantics, "helperCallSites": helpers, "ostySummonCensus": osty_sites,
        "ostySummonContract": _osty_summon_contract(assembly, assembly_sha256),
        "producerRoots": roots, "productionSemantics": {"status": "pendingE2d1b"}, "summary": summary,
    }
