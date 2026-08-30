"""Closed enemy-production discovery, producer semantics, and Add contract.

The E2d1a census is retained as an independently checkable discovery layer.
E2d1b closes the seven reachable producer triggers without executing game code:
pools, availability, slots, cardinality, cap/repeat state, producer-local
post-Add ordering, runtime contracts, and explicit E2a/E2b/E2d2 boundaries.
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
                              "producerSemantics": "sourceCompleteE2d1b"}
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
            "lifecycle": "pendingE2d2", "producerSemantics": "sourceCompleteE2d1b",
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
        "semanticBoundaries": {"coreSlotValidation": "absent", "emptyOrNoSlot": "producerOwnedSourceCompleteE2d1b"},
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



def _record_for_symbol(assembly: Any, assembly_sha256: str, symbol: str) -> dict[str, Any]:
    matches = [index for index, row in enumerate(assembly.md.MethodDef.rows, 1)
               if row.Rva and assembly.method_symbol(index) == symbol]
    if len(matches) != 1:
        raise SourceExtractionError(f"production method symbol denominator {symbol} = {len(matches)}")
    return assembly.method_record(matches[0], assembly_sha256)


def _proof(record: Mapping[str, Any], semantic: Any, *fragments: str) -> dict[str, Any]:
    """Bind a normalized semantic witness to a bounded instruction slice."""
    indexes: set[int] = set()
    for fragment in fragments:
        matches = [index for index, item in enumerate(record["instructions"])
                   if fragment in str(item.get("operand", ""))]
        if not matches:
            raise SourceExtractionError(
                f"production proof missing {fragment} in {record['symbolSignature']}"
            )
        for index in matches:
            indexes.update(range(max(0, index - 2), min(len(record["instructions"]), index + 3)))
    if not indexes:
        indexes = set(range(len(record["instructions"])))
    normalized = [{"opcode": record["instructions"][index]["opcode"],
                   "operand": record["instructions"][index].get("operand")}
                  for index in sorted(indexes)]
    result = _method(record)
    result["normalizedSliceSha256"] = witness_sha256(normalized)
    result["semanticWitnessSha256"] = witness_sha256(semantic)
    return result


def _symbols(record: Mapping[str, Any]) -> list[str]:
    return [str(item.get("operand", "")) for item in record["instructions"]]


def _owner_records_containing(assembly: Any, assembly_sha256: str, owner: str,
                              fragment: str) -> list[dict[str, Any]]:
    result = []
    for index, row in enumerate(assembly.md.MethodDef.rows, 1):
        method_owner = assembly.type_names.get(assembly.method_owner.get(index), "")
        if not row.Rva or not (method_owner == owner or method_owner.startswith(owner + "+")):
            continue
        record = assembly.method_record(index, assembly_sha256)
        if any(fragment in str(item.get("operand", "")) for item in record["instructions"]):
            result.append(record)
    result.sort(key=lambda row: row["symbolSignature"])
    return result


def _contract(contract_id: str, *, methods: list[Mapping[str, Any]], **fields: Any) -> dict[str, Any]:
    if not methods:
        raise SourceExtractionError(f"runtime production contract has no source methods: {contract_id}")
    semantic = {"contractId": contract_id, **fields}
    return {"contractId": contract_id, **fields,
            "provenance": [_proof(record, semantic) for record in methods]}


def _require_order(record: Mapping[str, Any], fragments: list[str], label: str) -> list[int]:
    positions: list[int] = []
    cursor = -1
    for fragment in fragments:
        found = next((index for index, item in enumerate(record["instructions"])
                      if index > cursor and fragment in str(item.get("operand", ""))), None)
        if found is None:
            raise SourceExtractionError(f"{label} order missing {fragment}")
        positions.append(found)
        cursor = found
    return positions


def _fixed_slots(record: Mapping[str, Any]) -> list[str]:
    instructions = record["instructions"]
    if len(instructions) < 8 or instructions[1].get("opcode") != "newarr" or instructions[1].get("operand") != "System.String":
        raise SourceExtractionError(f"production encounter slots are not a fixed string array: {record['symbolSignature']}")
    first = instructions[0]["opcode"]
    if first == "ldc.i4":
        count = instructions[0].get("operand")
    elif first.startswith("ldc.i4.") and first.rsplit(".", 1)[1].isdigit():
        count = int(first.rsplit(".", 1)[1])
    else:
        raise SourceExtractionError(f"production slot count is not exact: {record['symbolSignature']}")
    names = [str(item["operand"])[7:] for item in instructions
             if item["opcode"] == "ldstr" and str(item.get("operand", "")).startswith("string:")]
    if type(count) is not int or count != len(names) or len(set(names)) != count:
        raise SourceExtractionError(f"production fixed slot denominator drift: {record['symbolSignature']}")
    expected_length = 2 + 4 * count + 2
    if len(instructions) != expected_length or instructions[-1]["opcode"] != "ret":
        raise SourceExtractionError(f"production slot array construction changed: {record['symbolSignature']}")
    for index, name in enumerate(names):
        start = 2 + 4 * index
        group = instructions[start:start + 4]
        if ([item["opcode"] for item in group] != ["dup", f"ldc.i4.{index}", "ldstr", "stelem.ref"]
                or group[2].get("operand") != "string:" + name):
            raise SourceExtractionError(f"production slot array order changed: {record['symbolSignature']}")
    return names


def _graph_repeat(graph: Mapping[str, Any], move_id: str) -> dict[str, Any]:
    state_id = move_id.split("#", 1)[1]
    node = graph["graphId"] + "/" + state_id
    edges = graph["edges"]
    incoming = [row for row in edges if row["to"] == node and row["kind"] == "randomBranch"]
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adjacency[edge["from"]].append(edge["to"])
    pending = list(adjacency.get(node, [])); seen: set[str] = set(); cyclic = False
    while pending:
        current = pending.pop()
        if current == node:
            cyclic = True
            break
        if current in seen:
            continue
        seen.add(current); pending.extend(adjacency.get(current, []))
    if incoming:
        if len(incoming) != 1:
            raise SourceExtractionError(f"production move random-branch join is ambiguous: {move_id}")
        edge = incoming[0]
        repeat = dict(edge["repeat"])
        if repeat["enumName"] == "UseOnlyOnce":
            classification = "graphPerBodyUseOnlyOnce"
        elif repeat["enumName"] == "CanRepeatForever" and cyclic:
            classification = "graphRepeatWhileAvailable"
        elif cyclic:
            classification = "graphRepeatPolicyBounded"
        else:
            classification = "graphSingleReachableBranch"
        return {"branchSourceOrder": edge["sourceOrder"], "classification": classification,
                "cooldown": edge["cooldown"], "graphCycle": cyclic, "repeat": repeat}
    return {"classification": "graphCycleRepeat" if cyclic else "graphLifetimeOnce",
            "graphCycle": cyclic}


def _slot_strategy(assembly: Any, assembly_sha256: str, root_record: Mapping[str, Any],
                   direct_site: Mapping[str, Any], encounter: Mapping[str, Any]) -> dict[str, Any]:
    symbols = _symbols(root_record)
    add_index = next((index for index, symbol in enumerate(symbols) if symbol.startswith(_ADD)), None)
    if add_index is None:
        raise SourceExtractionError(f"production direct Add disappeared: {root_record['symbolSignature']}")
    if any("EncounterModel::GetNextSlot" in symbol for symbol in symbols[:add_index]):
        kind = "firstFreeDeclaredSlot"
    elif any("Enumerable::LastOrDefault" in symbol for symbol in symbols[:add_index]):
        kind = "lastFreeDeclaredSlot"
    else:
        strings = [symbol[7:] for symbol in symbols[:add_index] if symbol.startswith("string:")]
        if not strings:
            raise SourceExtractionError(f"production fixed slot is unresolved: {root_record['symbolSignature']}")
        kind = "fixedName"
    encounter_owner = encounter["sourceType"]
    slots_record = _one_method(assembly, assembly_sha256, encounter_owner, "get_Slots")
    slots = _fixed_slots(slots_record)
    if kind == "fixedName":
        fixed = [symbol[7:] for symbol in symbols[max(0, add_index - 8):add_index]
                 if symbol.startswith("string:")]
        if len(fixed) != 1 or fixed[0] not in slots:
            raise SourceExtractionError(f"production fixed slot/encounter join changed: {root_record['symbolSignature']}")
        value: str | None = fixed[0]
        empty = "passFixedNameWithoutOccupancyCheck"
    else:
        value = None
        has_empty_guard = any("String::IsNullOrEmpty" in symbol for symbol in symbols[:add_index])
        if kind == "lastFreeDeclaredSlot" and not has_empty_guard:
            # Ovicopter uses a direct null/false branch instead of IsNullOrEmpty.
            has_empty_guard = any(item["opcode"].startswith("brfalse")
                                  for item in root_record["instructions"][:add_index])
        empty = "skipAttempt" if has_empty_guard else "passEmptyStringToCoreAdd"
    semantic = {"encounter": "ENCOUNTER." + encounter["canonicalId"], "empty": empty,
                "kind": kind, "slots": slots, "value": value}
    fragments = ["CreatureCmd::Add", "EncounterModel::get_Slots" if kind == "lastFreeDeclaredSlot"
                 else "EncounterModel::GetNextSlot" if kind == "firstFreeDeclaredSlot" else "string:" + str(value)]
    return {
        "canonicalEncounter": "ENCOUNTER." + encounter["canonicalId"],
        "emptyResult": "notApplicableFixedName" if kind == "fixedName" else "emptyStringOrNull", "fixedName": value, "kind": kind,
        "noSlotBehavior": empty, "orderedEncounterSlots": slots,
        "provenance": {
            "selection": _proof(root_record, semantic, *fragments),
            "slots": _proof(slots_record, slots),
        },
        "slotStrategyId": "SLOT_STRATEGY." + direct_site["apiSiteRef"].split(".", 1)[1],
        "validation": "producerOwned; core Add performs none",
    }


def _static_model_pools(record: Mapping[str, Any], source_to_model: Mapping[str, str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    pending: list[str] = []
    for item in record["instructions"]:
        operand = str(item.get("operand", ""))
        if item["opcode"] == "call" and "ModelDb::Monster" in operand and " generic:" in operand:
            source_type = operand.split(" generic:", 1)[1]
            if source_type not in source_to_model:
                raise SourceExtractionError(f"unknown production pool model {source_type}")
            pending.append(source_to_model[source_type])
        elif item["opcode"] == "stsfld" and pending:
            if operand in result:
                raise SourceExtractionError(f"duplicate production static pool field {operand}")
            result[operand] = pending; pending = []
    if pending or len(result) != 2 or sorted(len(value) for value in result.values()) != [2, 2]:
        raise SourceExtractionError("production static pool construction denominator drift")
    return result


def _producer_semantics(assembly: Any, assembly_sha256: str, behavior: Mapping[str, Any],
                        roots: list[dict[str, Any]], helpers: list[dict[str, Any]],
                        direct_sites: list[dict[str, Any]], applicability: list[dict[str, Any]],
                        encounters: list[Mapping[str, Any]], source_to_model: Mapping[str, str],
                        initial_state: Mapping[str, Any]) -> dict[str, Any]:
    graphs = {row["graphId"]: row for row in behavior["graphs"]}
    encounter_by_id = {"ENCOUNTER." + row["canonicalId"]: row for row in encounters}
    applicability_by_owner = {row["ownerModel"]: row for row in applicability}
    root_by_id = {row["moveId"]: row for row in roots}
    site_by_root: dict[str, dict[str, Any]] = {}
    for site in direct_sites:
        for root_ref in site["rootRefs"]:
            if root_ref in site_by_root:
                raise SourceExtractionError(f"production root has multiple direct sinks: {root_ref}")
            site_by_root[root_ref] = site
    if set(site_by_root) != set(root_by_id):
        raise SourceExtractionError("production root/direct sink closure changed")

    # Source-built pools: two ordered Fabricator lists and five exact generic candidates.
    static_record = next((_one_method(assembly, assembly_sha256, root["ownerSourceType"], ".cctor")
                          for root in roots if root["sinkReachability"] == "transitiveHelperClosure"), None)
    if static_record is None:
        raise SourceExtractionError("production dynamic pool constructor is absent")
    static_fields = _static_model_pools(static_record, source_to_model)
    dynamic_owner = next(root["ownerModel"] for root in roots if root["sinkReachability"] == "transitiveHelperClosure")
    dynamic_encounter = encounter_by_id[applicability_by_owner[dynamic_owner]["canonicalEncounter"]]
    declared_pools = dynamic_encounter["productionPools"]
    pools: list[dict[str, Any]] = []
    field_to_pool: dict[str, str] = {}
    for field, members in sorted(static_fields.items()):
        matches = [row for row in declared_pools if row["members"] == members]
        if len(matches) != 1:
            raise SourceExtractionError(f"production dynamic pool membership join ambiguous: {field}")
        pool_id = "PRODUCTION_POOL." + dynamic_owner + "." + matches[0]["poolId"].upper()
        field_to_pool[field] = pool_id
        semantic = {"field": field, "members": members, "poolId": pool_id}
        pools.append({
            "candidateModels": members, "emptySelection": "NextItemReturnsNullThenToMutableFaults",
            "filter": {"comparison": "canonicalModelReferenceIdentity", "excludeRuntimeStateRef": "RUNTIME.PRODUCTION.FABRICATOR_LAST_SPAWNED",
                       "kind": "excludeImmediatePreviousReference"},
            "poolId": pool_id,
            "provenance": _proof(static_record, semantic, field),
            "replacementPolicy": "reusablePoolWithImmediateSameReferenceExclusion",
            "selection": {"algorithm": "uniformNextIntZeroInclusiveCountExclusive", "kind": "runtimeRng",
                          "rngStateRef": "RUNTIME.PRODUCTION.MONSTER_AI_RNG"},
        })
    fixed_pool_by_root: dict[str, str] = {}
    for root in roots:
        site = site_by_root[root["moveId"]]
        if root["sinkReachability"] != "direct":
            continue
        models = site["candidateMembership"]["canonicalModels"]
        if len(models) != 1:
            raise SourceExtractionError(f"fixed production pool is not singleton: {root['moveId']}")
        pool_id = "PRODUCTION_POOL." + root["moveId"].replace("#", ".")
        fixed_pool_by_root[root["moveId"]] = pool_id
        record = _record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
        semantic = {"model": models[0], "poolId": pool_id, "selection": "fixedReusable"}
        pools.append({
            "candidateModels": models, "emptySelection": "impossibleForSourceFixedCandidate",
            "filter": {"kind": "none"}, "poolId": pool_id,
            "provenance": _proof(record, semantic, "CreatureCmd::Add"),
            "replacementPolicy": "reusableFixedCandidate",
            "selection": {"kind": "fixedCanonicalModel"},
        })
    pools.sort(key=lambda row: row["poolId"])
    if len(pools) != 7 or sum(len(row["candidateModels"]) for row in pools) != 9 or len({model for row in pools for model in row["candidateModels"]}) != 9:
        raise SourceExtractionError("production pool/candidate denominator drift")

    # Wrapper methods bind each dynamic attempt to one source-built pool field.
    wrapper_pool: dict[str, str] = {}
    root_helper_edges = [row for row in helpers if row["callSiteId"].startswith("MONSTER.")]
    shared_body_symbols: set[str] = set()
    for edge in root_helper_edges:
        wrapper_symbol = edge["calleeSymbolSignature"]
        wrapper_name = wrapper_symbol.split("::", 1)[1].split(" sig:", 1)[0]
        traversed = [row["symbolSignature"] for row in edge["traversedMethods"]]
        wrapper_states = [symbol for symbol in traversed if "+<" + wrapper_name + ">" in symbol]
        shared_states = [symbol for symbol in traversed if any(
            effect["kind"] == "summon" and effect["sourceMethod"] == symbol
            for effect in edge["gameplayEffects"]
        )]
        if len(wrapper_states) != 1 or len(shared_states) != 1:
            raise SourceExtractionError(f"production wrapper/shared-helper traversal changed: {wrapper_symbol}")
        state = _record_for_symbol(assembly, assembly_sha256, wrapper_states[0])
        fields = [operand for operand in _symbols(state) if operand in static_fields]
        if len(fields) != 1:
            raise SourceExtractionError(f"production wrapper pool field join changed: {wrapper_symbol}")
        previous = wrapper_pool.setdefault(wrapper_symbol, field_to_pool[fields[0]])
        if previous != field_to_pool[fields[0]]:
            raise SourceExtractionError(f"production wrapper maps to multiple pools: {wrapper_symbol}")
        shared_body_symbols.update(shared_states)
    if len(wrapper_pool) != 2 or len(shared_body_symbols) != 1:
        raise SourceExtractionError("production dynamic pool wrapper/shared-body denominator drift")
    dynamic_body_record = _record_for_symbol(assembly, assembly_sha256, next(iter(shared_body_symbols)))
    filter_symbols = [symbol for symbol in _symbols(dynamic_body_record) if "::<SpawnBot>b__" in symbol]
    if len(set(filter_symbols)) != 1:
        raise SourceExtractionError("production immediate-previous filter delegate changed")
    filter_record = _record_for_symbol(assembly, assembly_sha256, next(iter(filter_symbols)))
    rng_ids = assembly.find_methods("MegaCrit.Sts2.Core.Random.Rng", "NextItem")
    if len(rng_ids) != 1:
        raise SourceExtractionError("production NextItem RNG method denominator changed")
    rng_record = assembly.method_record(rng_ids[0], assembly_sha256)
    filter_ops = [(item["opcode"], item.get("operand")) for item in filter_record["instructions"]]
    if ([item[0] for item in filter_ops] != ["ldarg.1", "ldarg.0", "ldfld", "ceq", "ldc.i4.0", "ceq", "ret"]
            or "::_lastSpawned" not in str(filter_ops[2][1])):
        raise SourceExtractionError("production immediate-previous filter is not exact reference inequality")
    rng_order = _require_order(rng_record, ["Enumerable::Count", "Rng::NextInt", "Enumerable::ElementAt"], "production uniform NextItem")
    if (not any(item["opcode"].startswith("brtrue") for item in rng_record["instructions"][rng_order[0]:rng_order[1]])
            or not any(item["opcode"] == "initobj" for item in rng_record["instructions"][rng_order[0]:rng_order[1]])):
        raise SourceExtractionError("production empty NextItem/default/no-draw branch changed")
    _require_order(dynamic_body_record, ["Enumerable::Where", "Enumerable::ToList", "Rng::NextItem", "::_lastSpawned", "MonsterModel::ToMutable", "EncounterModel::GetNextSlot", "CreatureCmd::Add", "::GetResult", "PowerCmd::Apply"], "dynamic production selection/Add/Minion")
    for pool in pools:
        if pool["selection"]["kind"] != "runtimeRng":
            continue
        semantic = {"filter": pool["filter"], "selection": pool["selection"], "emptySelection": pool["emptySelection"]}
        pool["selectionProvenance"] = {
            "filter": _proof(filter_record, semantic, "::_lastSpawned"),
            "selectionAndWriteBeforeAdd": _proof(dynamic_body_record, semantic, "Enumerable::Where", "Rng::NextItem", "::_lastSpawned", "CreatureCmd::Add"),
            "uniformRng": _proof(rng_record, semantic, "Rng::NextInt"),
        }

    slots: list[dict[str, Any]] = []
    slot_by_site: dict[str, dict[str, Any]] = {}
    for site in direct_sites:
        root = root_by_id[site["rootRefs"][0]]
        record = (_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
                  if root["sinkReachability"] == "direct" else dynamic_body_record)
        encounter = encounter_by_id[applicability_by_owner[root["ownerModel"]]["canonicalEncounter"]]
        strategy = _slot_strategy(assembly, assembly_sha256, record, site, encounter)
        slots.append(strategy); slot_by_site[site["apiSiteRef"]] = strategy
    slots.sort(key=lambda row: row["slotStrategyId"])
    if len(slots) != 6 or {row["kind"] for row in slots} != {"firstFreeDeclaredSlot", "lastFreeDeclaredSlot", "fixedName"}:
        raise SourceExtractionError("production slot strategy denominator drift")

    initial_by_model = {row["ownerModel"]: row for row in initial_state["initialStateOwners"]}
    producers: list[dict[str, Any]] = []
    post_add: list[dict[str, Any]] = []
    for root in roots:
        move_id = root["moveId"]
        record = _record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
        symbols = _symbols(record)
        site = site_by_root[move_id]
        graph = graphs[root["graphId"]]
        encounter_id = applicability_by_owner[root["ownerModel"]]["canonicalEncounter"]
        producer_id = "PRODUCTION." + move_id.replace("#", ".")
        repeat = _graph_repeat(graph, move_id)
        attempts: list[dict[str, Any]] = []
        semantic_kind: str
        if root["sinkReachability"] == "transitiveHelperClosure":
            semantic_kind = "orderedHelperBatch"
            outgoing = [row for row in helpers if row["callerSymbolSignature"] == record["symbolSignature"]]
            if not outgoing:
                raise SourceExtractionError(f"production helper attempts missing: {move_id}")
            for order, edge in enumerate(sorted(outgoing, key=lambda row: row["sourceOrder"])):
                if edge["calleeSymbolSignature"] not in wrapper_pool:
                    raise SourceExtractionError(f"production helper pool unresolved: {edge['calleeSymbolSignature']}")
                attempts.append({
                    "addApiSiteRef": site["apiSiteRef"], "attemptId": f"{producer_id}/attempt/{order}",
                    "awaitedResult": "exactCreatedCreatureBody", "bodyAddAttempts": {"maximum": 1, "minimum": 0},
                    "emptyPoolBehavior": "nullThenToMutableFault", "noSlotBehavior": slot_by_site[site["apiSiteRef"]]["noSlotBehavior"],
                    "order": order, "poolRef": wrapper_pool[edge["calleeSymbolSignature"]],
                    "postAddEffectRefs": ["POST_ADD.PRODUCTION.MINION.FABRICATOR"],
                    "slotStrategyRef": slot_by_site[site["apiSiteRef"]]["slotStrategyId"],
                    "triggerHelperCallSiteRef": edge["callSiteId"],
                })
            availability = {"expression": {"kind": "comparison", "left": {"kind": "count", "collection": "aliveSameSideCreaturesIncludingOwner"},
                                                   "operator": "lessThan", "right": {"kind": "constant", "value": 4, "valueType": "integer"},
                                                   "valueType": "boolean"},
                            "method": _proof(_one_method(assembly, assembly_sha256, root["ownerSourceType"], "get_CanFabricate"),
                                             "alive same-side creature count < 4", "GetTeammatesOf", "Enumerable::Count"),
                            "runtimeInputRefs": ["RUNTIME.PRODUCTION.SAME_SIDE_CREATURES", "RUNTIME.PRODUCTION.CREATURE_IS_ALIVE"]}
            concurrent = {"classification": "predicateBounded", "preActivationAliveSameSideMaximum": 3,
                          "possiblePostActivationAliveSameSideMaximum": 5}
            lifetime = {"classification": "sourceProvenNoLifetimeCapInClosedGraph", "poolDepletion": False}
        else:
            pool_ref = fixed_pool_by_root[move_id]
            strategy = slot_by_site[site["apiSiteRef"]]
            attempts = [{
                "addApiSiteRef": site["apiSiteRef"], "attemptId": f"{producer_id}/attempt/0",
                "awaitedResult": "exactCreatedCreatureBody", "emptyPoolBehavior": "notApplicableFixedCandidate",
                "noSlotBehavior": strategy["noSlotBehavior"], "order": 0, "poolRef": pool_ref,
                "postAddEffectRefs": [], "slotStrategyRef": strategy["slotStrategyId"],
            }]
            if any("get_BloatAmount" in symbol for symbol in symbols):
                semantic_kind = "runtimeCardinalityRepeating"
                attempts[0]["bodyAddAttempts"] = {"kind": "runtimeStateValue", "runtimeStateRef": "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT"}
                availability = {"expression": {"kind": "graphReachable"}, "runtimeInputRefs": ["RUNTIME.PRODUCTION.ENCOUNTER", "RUNTIME.PRODUCTION.CURRENT_ENEMIES"]}
                concurrent = {"classification": "slotMediatedNoExplicitNumericCap"}
                lifetime = {"classification": "sourceProvenNoLifetimeCapInClosedGraph", "poolDepletion": False}
            elif any("PowerCmd::Apply" in symbol and "MinionPower" in symbol for symbol in symbols):
                semantic_kind = "fixedThreeAttemptBatch"
                if not any(item["opcode"] == "ldc.i4.3" for item in record["instructions"]):
                    raise SourceExtractionError("production fixed batch cardinality is no longer three")
                attempts[0]["bodyAddAttempts"] = {"maximum": 3, "minimum": 0, "sourceLoopIterations": 3}
                attempts[0]["postAddEffectRefs"] = ["POST_ADD.PRODUCTION.MINION.OVICOPTER"]
                can_lay = {"kind": "comparison", "left": {"kind": "count", "collection": "aliveSameSideCreaturesIncludingOwner"},
                           "operator": "lessThanOrEqual", "right": {"kind": "constant", "value": 3, "valueType": "integer"},
                           "valueType": "boolean"}
                availability = {"expression": {"kind": "pathQualified", "paths": [
                                    {"condition": {"kind": "unconditionalGraphInitial"}, "path": "initial"},
                                    {"condition": can_lay, "path": "repeatAfterTenderizer"}]},
                                "method": _proof(_one_method(assembly, assembly_sha256, root["ownerSourceType"], "get_CanLay"),
                                                 "initial unconditional; repeat alive same-side count <= 3", "GetTeammatesOf", "Enumerable::Count"),
                                "runtimeInputRefs": ["RUNTIME.PRODUCTION.SAME_SIDE_CREATURES", "RUNTIME.PRODUCTION.CREATURE_IS_ALIVE"]}
                concurrent = {"classification": "predicateAndSlotsMediated", "preActivationAliveSameSideMaximum": 3,
                              "sourceLoopAttempts": 3}
                lifetime = {"classification": "sourceProvenNoLifetimeCapInClosedGraph", "poolDepletion": False,
                            "hatchDependencyRef": "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH"}
            elif any("set_HasSummoned" in symbol for symbol in symbols):
                semantic_kind = "fixedGraphOnceWithStatePostAdd"
                attempts[0]["bodyAddAttempts"] = {"maximum": 1, "minimum": 0}
                attempts[0]["postAddEffectRefs"] = ["POST_ADD.PRODUCTION.OBSCURA_HAS_SUMMONED"]
                availability = {"expression": {"kind": "graphLifetimeOnce"}, "runtimeInputRefs": ["RUNTIME.PRODUCTION.COMBAT_IS_LIVE"]}
                concurrent = {"classification": "fixedSlotNoOccupancyGuard"}
                lifetime = {"classification": "graphLifetimeOnce"}
            elif assembly.find_methods(root["ownerSourceType"], "CanSummon"):
                semantic_kind = "groupCounterBounded"
                attempts[0]["bodyAddAttempts"] = {"maximum": 1, "minimum": 0}
                attempts[0]["postAddEffectRefs"] = ["POST_ADD.PRODUCTION.RAT_GROUP_COUNTER_SYNC"]
                can = _one_method(assembly, assembly_sha256, root["ownerSourceType"], "CanSummon")
                availability = {"evaluationOrder": ["turnsAtOrBelowZero", "groupCallCountBelowThree", "encounterAndFirstFreeSlot",
                                                     "noOtherTeammatePlansCallForBackup"],
                                "expression": {"conditions": [
                                    {"left": "RUNTIME.PRODUCTION.RAT_TURNS_UNTIL_SUMMONABLE", "operator": "lessThanOrEqual", "right": 0},
                                    {"left": "RUNTIME.PRODUCTION.RAT_CALL_FOR_BACKUP_COUNT", "operator": "lessThan", "right": 3},
                                    {"kind": "nonEmptyFirstFreeSlot"}, {"kind": "noOtherTeammateNextMove", "moveId": move_id}],
                                    "kind": "all", "valueType": "boolean"},
                                "method": _proof(can, "ordered four-clause Rat summon availability", "get_TurnsUntilSummonable", "get_CallForBackupCount", "GetNextSlot", "get_NextMove"),
                                "runtimeInputRefs": ["RUNTIME.PRODUCTION.RAT_TURNS_UNTIL_SUMMONABLE", "RUNTIME.PRODUCTION.RAT_CALL_FOR_BACKUP_COUNT",
                                                     "RUNTIME.PRODUCTION.ENCOUNTER", "RUNTIME.PRODUCTION.CURRENT_ENEMIES", "RUNTIME.PRODUCTION.MONSTER_NEXT_MOVE_ID"]}
                concurrent = {"classification": "slotAndTeammatePlanMediated"}
                lifetime = {"classification": "groupCounterBounded", "completedCallPathMaximum": 3,
                            "normallyAddedBodyMaximum": 3, "scope": "allCurrentTwoTailedRats"}
            else:
                semantic_kind = "fixedGraphOnce"
                attempts[0]["bodyAddAttempts"] = {"maximum": 1, "minimum": 0}
                availability = {"expression": {"kind": "graphLifetimeOnce"}, "runtimeInputRefs": ["RUNTIME.PRODUCTION.COMBAT_IS_LIVE"]}
                concurrent = {"classification": "fixedSlotNoOccupancyGuard"}
                lifetime = {"classification": "graphLifetimeOnce"}
        candidate_models = sorted({model for attempt in attempts for pool in pools if pool["poolId"] == attempt["poolRef"] for model in pool["candidateModels"]})
        initial_refs = sorted({ref for model in candidate_models for ref in initial_by_model[model]["factRefs"]})
        if semantic_kind == "runtimeCardinalityRepeating":
            activation_cardinality = {"bodyAddAttempts": {"kind": "runtimeStateValue", "runtimeStateRef": "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT"},
                                      "normallyAddedBodies": {"minimum": 0, "maximumRef": "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT"}}
        elif semantic_kind == "fixedThreeAttemptBatch":
            activation_cardinality = {"bodyAddAttempts": {"exact": 3}, "normallyAddedBodies": {"maximum": 3, "minimum": 0}}
        else:
            maximum = len(attempts)
            activation_cardinality = {"bodyAddAttempts": {"maximum": maximum, "minimum": 0},
                                      "normallyAddedBodies": {"maximum": maximum, "minimum": 0},
                                      "orderedTriggerCalls": maximum}
        producer_semantic = {"attempts": attempts, "availability": availability["expression"], "moveId": move_id,
                             "repeat": repeat, "semanticKind": semantic_kind}
        producers.append({
            "activationCardinality": activation_cardinality,
            "applicableConcreteModels": root["applicableConcreteModels"], "attempts": attempts,
            "availability": availability, "canonicalEncounter": encounter_id,
            "concurrentPolicy": concurrent,
            "dependencies": {"e2aInitialStateFactRefs": initial_refs, "e2bHpAssignmentRef": "hpPipeline.assignment",
                             "e2d2LifecycleRefs": ["DEPENDENCY.PRODUCTION.CURRENT_ENEMY_LIFECYCLE", "DEPENDENCY.PRODUCTION.AFTER_CREATURE_ADDED_LISTENERS"]},
            "graphRef": root["graphId"], "lifetimePolicy": lifetime, "moveRef": move_id,
            "ownerModel": root["ownerModel"], "producerId": producer_id,
            "provenance": _proof(record, producer_semantic, *("CreatureCmd::Add",) if root["sinkReachability"] == "direct" else ("Spawn",)),
            "repeatPolicy": repeat, "semanticKind": semantic_kind, "triggerKind": "monsterMove",
        })
    producers.sort(key=lambda row: row["producerId"])
    if len(producers) != 7 or {len(row["attempts"]) for row in producers} != {1, 2}:
        raise SourceExtractionError("production producer/attempt denominator drift")

    # Four exact source sites execute only after a normal Add-task return.
    fabricator_body = dynamic_body_record
    ovicopter = next(_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
                      for root in roots if any("MinionPower" in symbol for symbol in _symbols(_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"]))))
    obscura = next(_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
                    for root in roots if any("set_HasSummoned" in symbol for symbol in _symbols(_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"]))))
    rat = next(_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
               for root in roots if assembly.find_methods(root["ownerSourceType"], "CanSummon"))
    rat_setter_symbols = [symbol for symbol in _symbols(rat) if "::<CallForBackup>b__" in symbol]
    rat_setter_symbols = [symbol for symbol in rat_setter_symbols
                          if any("set_CallForBackupCount" in value for value in _symbols(
                              _record_for_symbol(assembly, assembly_sha256, symbol)))]
    if len(set(rat_setter_symbols)) != 1:
        raise SourceExtractionError("Rat post-Add counter setter closure changed")
    rat_setter = _record_for_symbol(assembly, assembly_sha256, next(iter(rat_setter_symbols)))
    _require_order(rat, ["CreatureCmd::Add", "::GetResult", "get_Enemies", "Enumerable::Select",
                         "Enumerable::OfType", "Enumerable::ToList", "Enumerable::Max",
                         "<CallForBackup>b__3", "::ForEach"], "Rat Add/group-counter synchronization")
    rat_increment_symbols = [symbol for symbol in _symbols(rat) if "::<CallForBackup>b__" in symbol]
    rat_increment_records = [_record_for_symbol(assembly, assembly_sha256, symbol)
                             for symbol in set(rat_increment_symbols)]
    rat_increment_records = [record for record in rat_increment_records
                             if any("get_CallForBackupCount" in value for value in _symbols(record))]
    if len(rat_increment_records) != 1:
        raise SourceExtractionError("Rat old-plus-one counter projection changed")
    increment_ops = [item["opcode"] for item in rat_increment_records[0]["instructions"]]
    if increment_ops != ["ldarg.1", "callvirt", "ldc.i4.1", "add", "ret"]:
        raise SourceExtractionError("Rat counter update is not exact old-plus-one")
    effect_specs = [
        ("POST_ADD.PRODUCTION.MINION.FABRICATOR", fabricator_body, "applyPower", "POWER.MINION_POWER", "PowerCmd::Apply", None),
        ("POST_ADD.PRODUCTION.MINION.OVICOPTER", ovicopter, "applyPower", "POWER.MINION_POWER", "PowerCmd::Apply", None),
        ("POST_ADD.PRODUCTION.OBSCURA_HAS_SUMMONED", obscura, "stateWrite", "RUNTIME.PRODUCTION.OBSCURA_HAS_SUMMONED", "set_HasSummoned", None),
        ("POST_ADD.PRODUCTION.RAT_GROUP_COUNTER_SYNC", rat, "groupStateWrite", "RUNTIME.PRODUCTION.RAT_CALL_FOR_BACKUP_COUNT", "<CallForBackup>b__3", rat_setter),
    ]
    for effect_id, record, kind, target, sink, support in effect_specs:
        order = _require_order(record, ["CreatureCmd::Add", "::GetResult", sink], effect_id)
        semantic = {"effectId": effect_id, "kind": kind, "order": "afterNormalAddTaskReturn", "target": target}
        effect = {"effectId": effect_id, "kind": kind, "ordering": "afterNormalAddTaskReturn",
                  "provenance": _proof(record, semantic, "CreatureCmd::Add", "::GetResult", sink), "targetRef": target,
                  "validatedOrderInstructionIndices": order}
        if support is not None:
            effect["supportProvenance"] = [_proof(support, semantic, "set_CallForBackupCount")]
        post_add.append(effect)
    post_add.sort(key=lambda row: row["effectId"])

    # Producer-specific state contracts. Shared collection/query contracts remain
    # dynamic and are intentionally not treated as observed values. Method sets
    # are discovered from the exact owner/nested-owner closure, not a display list.
    producer_records = [_record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"])
                        for root in roots]
    live_records = [record for record in producer_records if any("IsLiveCombat" in value for value in _symbols(record))]
    encounter_records = [record for record in producer_records if any("get_Encounter" in value for value in _symbols(record))]
    enemies_records = [record for record in producer_records if any("get_Enemies" in value for value in _symbols(record))]
    availability_records = []
    for root in roots:
        for name in ("get_CanFabricate", "get_CanLay", "CanSummon"):
            ids = assembly.find_methods(root["ownerSourceType"], name)
            if len(ids) > 1:
                raise SourceExtractionError(f"production availability method denominator changed: {root['ownerSourceType']}::{name}")
            if ids:
                availability_records.append(assembly.method_record(ids[0], assembly_sha256))
    availability_records = sorted({row["symbolSignature"]: row for row in availability_records}.values(), key=lambda row: row["symbolSignature"])
    next_move_records = [row for row in availability_records if any("get_NextMove" in value for value in _symbols(row))]
    dynamic_owner_source = next(root["ownerSourceType"] for root in roots if root["ownerModel"] == dynamic_owner)
    last_spawned_records = _owner_records_containing(assembly, assembly_sha256, dynamic_owner_source, "::_lastSpawned")
    if len(last_spawned_records) != 2:
        raise SourceExtractionError("production immediate-previous reference read/write closure changed")
    rat_owner = next(root["ownerSourceType"] for root in roots if assembly.find_methods(root["ownerSourceType"], "CanSummon"))
    rat_turn_records = _owner_records_containing(assembly, assembly_sha256, rat_owner, "::_turnsUntilSummonable")
    rat_turn_update_records = _owner_records_containing(assembly, assembly_sha256, rat_owner, "::set_TurnsUntilSummonable")
    if len(rat_turn_records) != 3 or len(rat_turn_update_records) != 3:
        raise SourceExtractionError("Rat summon-turn default/getter/update closure changed")
    for record in rat_turn_update_records:
        _require_order(record, ["get_TurnsUntilSummonable", "set_TurnsUntilSummonable"], "Rat summon-turn decrement")
        setter_index = next(index for index, value in enumerate(_symbols(record)) if "set_TurnsUntilSummonable" in value)
        if not any(item["opcode"] == "sub" for item in record["instructions"][:setter_index]):
            raise SourceExtractionError("Rat summon-turn update is not subtraction before move effect")
    rat_count_records = _owner_records_containing(assembly, assembly_sha256, rat_owner, "::_callForBackupCount")
    rat_count_update_records = _owner_records_containing(assembly, assembly_sha256, rat_owner, "::set_CallForBackupCount")
    if len(rat_count_records) != 2 or len(rat_count_update_records) != 1:
        raise SourceExtractionError("Rat group-call counter getter/update closure changed")
    living_owner = next(root["ownerSourceType"] for root in roots
                        if any("get_BloatAmount" in value for value in _symbols(
                            _record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"]))))
    living_records = _owner_records_containing(assembly, assembly_sha256, living_owner, "::_bloatAmount")
    if len(living_records) != 3:
        raise SourceExtractionError("Living Fog BloatAmount field closure changed")
    if _owner_records_containing(assembly, assembly_sha256, living_owner, "::set_BloatAmount"):
        raise SourceExtractionError("Living Fog BloatAmount gained a reachable setter call")
    obscura_owner = next(root["ownerSourceType"] for root in roots
                         if any("set_HasSummoned" in value for value in _symbols(
                             _record_for_symbol(assembly, assembly_sha256, root["rootMethod"]["symbolSignature"]))))
    obscura_records = (_owner_records_containing(assembly, assembly_sha256, obscura_owner, "::_hasSummoned")
                        + _owner_records_containing(assembly, assembly_sha256, obscura_owner, "::set_HasSummoned"))
    obscura_records = sorted({row["symbolSignature"]: row for row in obscura_records}.values(), key=lambda row: row["symbolSignature"])
    if len(obscura_records) != 3:
        raise SourceExtractionError("Obscura HasSummoned field closure changed")

    unavailable = "unavailableNoCurrentAdapter"
    runtime_contracts = [
        _contract("RUNTIME.PRODUCTION.COMBAT_IS_LIVE", methods=live_records, default="runtime", domain="boolean", observationAvailability=unavailable, update="combatLifecycle"),
        _contract("RUNTIME.PRODUCTION.ENCOUNTER", methods=encounter_records, default="runtimeNullable", domain="nullableCanonicalEncounter", observationAvailability=unavailable, update="combatLifecycle"),
        _contract("RUNTIME.PRODUCTION.CURRENT_ENEMIES", methods=enemies_records, default="runtime", domain="orderedCreatureBodyCollection", observationAvailability=unavailable, update="E2d2LifecycleOwned"),
        _contract("RUNTIME.PRODUCTION.SAME_SIDE_CREATURES", methods=availability_records, default="runtime", domain="orderedCreatureBodyCollectionIncludingSource", observationAvailability=unavailable, update="combatLifecycle"),
        _contract("RUNTIME.PRODUCTION.CREATURE_IS_ALIVE", methods=availability_records, default="runtime", domain="booleanPerBody", observationAvailability=unavailable, update="E2d2LifecycleOwned"),
        _contract("RUNTIME.PRODUCTION.MONSTER_NEXT_MOVE_ID", methods=next_move_records, default="runtimeNullable", domain="nullableCanonicalMoveIdPerBody", observationAvailability=unavailable, update="moveSelection"),
        _contract("RUNTIME.PRODUCTION.MONSTER_AI_RNG", methods=[dynamic_body_record, rng_record], default="runSeededRuntimeState", domain="deterministicRngStream", observationAvailability=unavailable, update="NextItemConsumesNextIntOnlyWhenNonempty"),
        _contract("RUNTIME.PRODUCTION.FABRICATOR_LAST_SPAWNED", methods=[_one_method(assembly, assembly_sha256, dynamic_owner_source, ".ctor")] + last_spawned_records, default=None, domain="nullableCanonicalMonsterModelReference", observationAvailability=unavailable, reset="noneFound", update="chosenReferenceBeforeAdd"),
        _contract("RUNTIME.PRODUCTION.RAT_TURNS_UNTIL_SUMMONABLE", methods=rat_turn_records + rat_turn_update_records, default=2, domain="Int32NoFloor", observationAvailability=unavailable, reset="noneFound", update="subtractOneBeforeEachOfThreeNonCallMoveEffects"),
        _contract("RUNTIME.PRODUCTION.RAT_CALL_FOR_BACKUP_COUNT", methods=[_one_method(assembly, assembly_sha256, rat_owner, ".ctor")] + rat_count_records + rat_count_update_records + [rat], default=0, domain="Int32; reachable production range 0..3", observationAvailability=unavailable, reset="noneFound", update="afterNormalAddReturn set every current Rat to Max(oldPlusOne)"),
        _contract("RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT", methods=living_records, default=1, domain="Int32", observationAvailability=unavailable, reset="noneFound", update="noReachableWriteAfterConstruction"),
        _contract("RUNTIME.PRODUCTION.OBSCURA_HAS_SUMMONED", methods=[_one_method(assembly, assembly_sha256, obscura_owner, ".ctor")] + obscura_records, default=False, domain="boolean", observationAvailability=unavailable, reset="noneFound", update="trueAfterNormalAddReturn"),
    ]
    if len(runtime_contracts) != 12:
        raise AssertionError("production runtime contract construction drift")

    dependencies = [
        {"affectedProducerRefs": [row["producerId"] for row in producers], "dependencyId": "DEPENDENCY.PRODUCTION.CURRENT_ENEMY_LIFECYCLE", "kind": "deathRemovalSlotAvailability", "sourceRefs": ["production.runtimeStateContracts.CURRENT_ENEMIES", "production.slotStrategies"], "status": "pendingE2d2"},
        {"affectedProducerRefs": [row["producerId"] for row in producers], "dependencyId": "DEPENDENCY.PRODUCTION.AFTER_CREATURE_ADDED_LISTENERS", "kind": "awaitedHookListenerEffects", "sourceRefs": ["production.coreAddContract.hookBoundary.afterCreatureAddedToCombat"], "status": "pendingE2d2"},
        {"affectedProducerRefs": [row["producerId"] for row in producers if row["lifetimePolicy"].get("hatchDependencyRef") == "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH"], "dependencyId": "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH", "kind": "sameBodyHatchStateTransitionNotAdd", "sourceRefs": ["initialState", "behavior.MONSTER.TOUGH_EGG#HATCH_MOVE"], "status": "pendingE2d2"},
        {"affectedProducerRefs": [], "dependencyId": "DEPENDENCY.PRODUCTION.DEATH_POWER_ADD_SITES", "kind": "fourExplicitOutOfDomainAddSites", "sourceRefs": ["production.addApiCensus.outOfScopeDeathPower"], "status": "pendingE2d2"},
    ]
    if len(dependencies[2]["affectedProducerRefs"]) != 1:
        raise SourceExtractionError("Tough Egg production dependency join changed")

    source_denominators = {
        "candidateEntries": sum(len(row["candidateModels"]) for row in pools),
        "candidateRngSelections": sum(row["selection"]["kind"] == "runtimeRng" for row in pools),
        "dependencyRefs": len(dependencies), "pools": len(pools), "postAddEffects": len(post_add),
        "producers": len(producers), "runtimeStateContracts": len(runtime_contracts), "slotStrategies": len(slots),
    }
    expected = {"candidateEntries": 9, "candidateRngSelections": 2, "dependencyRefs": 4, "pools": 7,
                "postAddEffects": 4, "producers": 7, "runtimeStateContracts": 12, "slotStrategies": 6}
    # One algorithmic RNG site is shared by the two source pool records.
    source_denominators["candidateRngSelections"] = len({row["selectionProvenance"]["selectionAndWriteBeforeAdd"]["symbolSignature"]
                                                            for row in pools if row["selection"]["kind"] == "runtimeRng"})
    expected["candidateRngSelections"] = 1
    if source_denominators != expected:
        raise SourceExtractionError(f"production semantic denominator drift: {source_denominators!r}")
    return {"dependencies": dependencies, "pools": pools, "postAddEffects": post_add,
            "producers": producers, "runtimeStateContracts": runtime_contracts,
            "slotStrategies": slots, "sourceDenominators": source_denominators,
            "status": "sourceComplete"}

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
    producer_semantics = _producer_semantics(
        assembly, assembly_sha256, behavior, roots, helpers, semantics, applicability,
        all_encounters, source_to_model, initial_state,
    )
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
        "producerRoots": roots, "productionSemantics": producer_semantics, "summary": summary,
    }
