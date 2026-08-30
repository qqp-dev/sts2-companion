"""Fail-closed E2d2a core lifecycle extraction from pinned CLI metadata/CIL.

This slice closes shared kill/escape/removal/dispatch/combat-ending mechanics.
Concrete listener effects, event terminal routing, and run termination remain
explicit later-wave dependencies.  The module never loads or executes the game.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Iterable, Mapping

from .behavior import _async_map
from .canonical import witness_sha256
from .cil_eval import CilDataFlow, SymbolicValue, decode_method_signature
from .errors import SourceExtractionError
if TYPE_CHECKING:
    from .metadata import AssemblyMetadata

_CREATURE_CMD = "MegaCrit.Sts2.Core.Commands.CreatureCmd"
_HOOK = "MegaCrit.Sts2.Core.Hooks.Hook"
_COMBAT_MANAGER = "MegaCrit.Sts2.Core.Combat.CombatManager"
_COMBAT_STATE = "MegaCrit.Sts2.Core.Combat.CombatState"
_RUN_STATE = "MegaCrit.Sts2.Core.Runs.RunState"
_ACTION_EXECUTOR = "MegaCrit.Sts2.Core.GameActions.ActionExecutor"

# Exact method-body recognizers for the pinned assembly.  These are version
# assertions, not generated IDs and not a substitute for normalized semantics.
_BODY_PINS = {
    f"{_CREATURE_CMD}::Kill sig:000212812112a7e402": "f339fc8da6d8b0f45a8a8f09a45c9e32b241bfc5de52900a6569a2f000429742",
    f"{_CREATURE_CMD}::Kill sig:00021281211512832d0112a7e402": "b74f19980a78bbd6b0bddb51c85df1b3a4eac54dc483138f30fc53ac28e9ddf4",
    f"{_CREATURE_CMD}::KillWithoutCheckingWinCondition sig:000312812112a7e40208": "69e88b4656b63055b5a4813554aa6dba6fc9b703d33e64f7775755d2bb463570",
    f"{_CREATURE_CMD}::Escape sig:000212812112a7e402": "20335c8a5a91ca41132e6b0fe506cdeb7f312e93a318448f60110e3c122a5163",
    f"{_CREATURE_CMD}+<Kill>d__13::MoveNext sig:200001": "3233e3397e7768a1c75e355b0f41c471451260a228ebca08d598bfcd8e090b6c",
    f"{_CREATURE_CMD}+<Kill>d__14::MoveNext sig:200001": "a84a440263d6ac641ce83ef96e790232c8d174c8b3da0b978e1d755bbfb4bc00",
    f"{_CREATURE_CMD}+<KillWithoutCheckingWinCondition>d__15::MoveNext sig:200001": "d41c058456089e077291bed61b8de31b1b706b94955fc990afab4bf67a62f008",
    f"{_HOOK}::BeforeDeath sig:000312812112841c12aa8812a7e4": "904c5b4a46e99ee922dcb5263dbe649d360995ae5ddb02a0b33535229f277dcc",
    f"{_HOOK}::AfterDeath sig:000512812112841c12aa8812a7e4020c": "34b7d7ac55454fe17c81a2aaf7fe73007592f42d4cb38855318ee0af9becac7b",
    f"{_HOOK}::AfterPreventingDeath sig:000412812112841c12aa8812889c12a7e4": "92c012931a7d991e1273d0e1cccaf51a053837718afe3251ad457663f97dbe44",
    f"{_HOOK}::ShouldCreatureBeRemovedFromCombatAfterDeath sig:00020212aa8812a7e4": "327230a82d573a57728546f6a7a3aceb8a89baa2bc75ffd70469fcd5f028833b",
    f"{_HOOK}::ShouldDie sig:00040212841c12aa8812a7e41012889c": "0a7fb87d8d34978705e29d1980204dda788c2f665995106b5580fe50eba67609",
    f"{_HOOK}::ShouldStopCombatFromEnding sig:00010212aa88": "a5e16a6450a590dc432212b7ccf721f4c6b3d8c272e96f5a866c4cabef4485b1",
    f"{_HOOK}+<BeforeDeath>d__27::MoveNext sig:200001": "738c7aafdae99674cad0f671f898b140960d67c22d1de7e607d43093a2c80f1d",
    f"{_HOOK}+<AfterDeath>d__28::MoveNext sig:200001": "fb8398652bf5c6cd5721bcee492f01b3ed24537de7b547df833e9c70b6c00bdc",
    f"{_HOOK}+<AfterPreventingDeath>d__66::MoveNext sig:200001": "229dc877eafbebc8f7a4742aceec26057486f2bcd2fe78fdbb98a99794e45edd",
    f"{_HOOK}::IterateCombatHookListeners sig:0001151281f50112889c12aa88": "5daa6b92458fbb95bf9968df830ba9e4ec8e743c813fd15842b7fdb2b9491897",
    f"{_HOOK}+<IterateCombatHookListeners>d__0::MoveNext sig:200002": "b6a0de09845b37fe91cc07818522d0924fd1caf76df76b0a5d1ef50d5f993def",
    f"{_COMBAT_STATE}::IterateHookListeners sig:2000151281f50112889c": "abe5890ad6527ba2c4583ea3d49e8d8150d78bbe5e747134e12c1690dfc84b85",
    f"{_COMBAT_STATE}+<IterateHookListeners>d__69::MoveNext sig:200002": "ce4169f167efc181a906d3e114acabfc5db77390181a3d6e5ab6ca1b364fd5fc",
    f"{_RUN_STATE}::IterateHookListeners sig:2001151281f50112889c12aa88": "8ca101a568cc58d8195c8f2a6ed61687a74e826aa6b928b68a50bf0591769dc1",
    f"{_RUN_STATE}+<IterateHookListeners>d__118::MoveNext sig:200002": "da4db0df36741af834a3ec69d270b78f4c5bdc6e18daf932f1a07b7084313c36",
    f"{_COMBAT_MANAGER}::RemoveCreature sig:20010112a7e4": "b7a571d5be7491959083e4520d9eeb90e76e3921722ad0efea62c596e9ab975f",
    f"{_COMBAT_STATE}::CreatureEscaped sig:20010112a7e4": "c6eade38809ed832280d0a5212d06d30fd3eed7abe5e21dd42c78f132fab4dff",
    f"{_COMBAT_STATE}::RemoveCreature sig:20020112a7e402": "e3e4126afbe5d26dbc259adc838d4e43bc2a5646542edc31da221712fdfcea6f",
    f"{_COMBAT_MANAGER}::IsCombatEnding sig:20010212aa84": "ac864d795c65b312843d2f13a23b54b5c1a1a2c24e041c46f0375e9f04c943bc",
    f"{_COMBAT_MANAGER}::LoseCombat sig:200001": "32f7490ddb344cb42c8c10b71780a5d9050967b2232c157b5ace7591fb209a35",
    f"{_COMBAT_MANAGER}::ProcessPendingLoss sig:20010112aa84": "1b3b30a9c4adf57685b2b5928abdd93259a47461448cbe65516b4b535a77e95e",
    f"{_COMBAT_MANAGER}::EndCombatInternal sig:2000128121": "a27b1e71023080da6b2863cfdd97b89814923e1d805d5a0adb180545c3f2d7bb",
    f"{_COMBAT_MANAGER}::EndCombatInternal sig:200112812112aa84": "f66302b4aa8fedc75f825108831f5e370df5f85fd3e4a0919347bd4e3ab063c5",
    f"{_COMBAT_MANAGER}::CheckWinCondition sig:2000151282210102": "874acf571535f4cb7170b9e32240c0eb251cd6cabe12a4aeb4aaf0627d1cecaa",
    f"{_COMBAT_MANAGER}::CheckWinCondition sig:200115128221010212aa84": "3ed429c3b008c80103a8adaaec71ccd445ba4c2d5bf122fe327eee63284d3c66",
    f"{_COMBAT_MANAGER}+<EndCombatInternal>d__121::MoveNext sig:200001": "da6e55a3307d53930ccd474340bc348b25af62cdfe380dc758631ffd6f0bbfc8",
    f"{_COMBAT_MANAGER}+<EndCombatInternal>d__122::MoveNext sig:200001": "8e252bb938763b7f9a089ed30b4d1cf0ec5d49e931c97210f186b2c041386a60",
    f"{_COMBAT_MANAGER}+<CheckWinCondition>d__124::MoveNext sig:200001": "c723fa952206466a0fbd94e9befd7a6b1e9397378be3cb9d679e760f634d2f65",
    f"{_COMBAT_MANAGER}+<CheckWinCondition>d__125::MoveNext sig:200001": "1e43ce71c1b26ba10fc3fbca75d22242da8c4db928ae7533d1a823a003c1201e",
    f"{_ACTION_EXECUTOR}+<ExecuteActions>d__28::MoveNext sig:200001": "fca2582a392be490a4851a07008b071e0a42245e15a85fdc4eaed79495b56856",
}

_DECLARATIONS = (
    (_CREATURE_CMD, "Kill", "000212812112a7e402", ("creature", "force")),
    (_CREATURE_CMD, "Kill", "00021281211512832d0112a7e402", ("creatures", "force")),
    (_CREATURE_CMD, "KillWithoutCheckingWinCondition", "000312812112a7e40208", ("creature", "force", "recursion")),
    (_CREATURE_CMD, "Escape", "000212812112a7e402", ("creature", "removeCreatureNode")),
)
_DISPATCH = (
    (_HOOK, "BeforeDeath", "000312812112841c12aa8812a7e4", ("runState", "combatState", "creature")),
    (_HOOK, "AfterDeath", "000512812112841c12aa8812a7e4020c", ("runState", "combatState", "creature", "wasRemovalPrevented", "deathAnimLength")),
    (_HOOK, "AfterPreventingDeath", "000412812112841c12aa8812889c12a7e4", ("runState", "combatState", "preventer", "creature")),
    (_HOOK, "ShouldCreatureBeRemovedFromCombatAfterDeath", "00020212aa8812a7e4", ("combatState", "creature")),
    (_HOOK, "ShouldDie", "00040212841c12aa8812a7e41012889c", ("runState", "combatState", "creature", "preventer")),
    (_HOOK, "ShouldStopCombatFromEnding", "00010212aa88", ("combatState",)),
)
_TERMINATION = (
    (_COMBAT_MANAGER, "CheckWinCondition", "2000151282210102", ()),
    (_COMBAT_MANAGER, "CheckWinCondition", "200115128221010212aa84", ("turnState",)),
    (_COMBAT_MANAGER, "EndCombatInternal", "2000128121", ()),
    (_COMBAT_MANAGER, "EndCombatInternal", "200112812112aa84", ("turnState",)),
    (_COMBAT_MANAGER, "IsCombatEnding", "20010212aa84", ("turnState",)),
    (_COMBAT_MANAGER, "LoseCombat", "200001", ()),
    (_COMBAT_MANAGER, "ProcessPendingLoss", "20010112aa84", ("turnState",)),
)


def _proof(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in (
        "assemblySha256", "cilInstructionsSha256", "diagnosticMetadataToken", "metadataSignature",
        "methodBodySha256", "normalizedInstructionsSha256", "symbolSignature",
    )}


def _exact_method(assembly: AssemblyMetadata, assembly_sha256: str, owner: str, name: str,
                  signature: str, parameters: Iterable[str] | None = None) -> tuple[int, dict[str, Any]]:
    rows = [index for index in assembly.find_methods(owner, name)
            if assembly.md.MethodDef.rows[index - 1].Signature.value.hex() == signature]
    if len(rows) != 1:
        raise SourceExtractionError(f"required lifecycle declaration is not unique: {owner}::{name} sig:{signature} ({len(rows)})")
    index = rows[0]; row = assembly.md.MethodDef.rows[index - 1]
    actual_parameters = tuple(str(item.row.Name) for item in row.ParamList)
    if parameters is not None and actual_parameters != tuple(parameters):
        raise SourceExtractionError(f"lifecycle parameter metadata drift at {owner}::{name}: {actual_parameters!r}")
    record = assembly.method_record(index, assembly_sha256)
    expected = _BODY_PINS.get(record["symbolSignature"])
    if expected is None or record["methodBodySha256"] != expected:
        raise SourceExtractionError(f"unrecognized lifecycle CIL body: {record['symbolSignature']}")
    return index, record


def _physical_record(assembly: AssemblyMetadata, assembly_sha256: str, logical_index: int,
                     async_map: Mapping[int, int]) -> dict[str, Any]:
    physical_index = async_map.get(logical_index)
    if physical_index is None:
        raise SourceExtractionError(f"missing lifecycle async state machine: {assembly.method_symbol(logical_index)}")
    record = assembly.method_record(physical_index, assembly_sha256)
    if _BODY_PINS.get(record["symbolSignature"]) != record["methodBodySha256"]:
        raise SourceExtractionError(f"unrecognized lifecycle physical CIL body: {record['symbolSignature']}")
    return record


def _method_contract(assembly: AssemblyMetadata, assembly_sha256: str, spec: tuple[str, str, str, tuple[str, ...]],
                     async_map: Mapping[int, int], *, async_required: bool = False) -> tuple[int, dict[str, Any]]:
    index, record = _exact_method(assembly, assembly_sha256, *spec)
    result = {"method": _proof(record), "parameters": [
        {"name": name, "position": position, "sourceMetadata": True}
        for position, name in enumerate(spec[3])
    ]}
    if async_required:
        result["physicalBody"] = _proof(_physical_record(assembly, assembly_sha256, index, async_map))
    else:
        result["physicalBody"] = _proof(record)
    return index, result


def _classify_command_caller(symbol: str) -> str:
    rules = (
        ("MegaCrit.Sts2.Core.Commands.CreatureCmd+", "coreLifecycleInternal"),
        ("MegaCrit.Sts2.Core.Models.Monsters.", "monsterLifecycle"),
        ("MegaCrit.Sts2.Core.Models.Powers.", "powerLifecycle"),
        ("MegaCrit.Sts2.Core.Models.Cards.", "playerCardLifecycle"),
        ("MegaCrit.Sts2.Core.Models.Events.", "eventLifecycle"),
        ("MegaCrit.Sts2.Core.Runs.", "runLifecycle"),
        ("MegaCrit.Sts2.Core.DevConsole.", "developerCommand"),
        ("MegaCrit.Sts2.Core.AutoSlay.", "automation"),
    )
    for prefix, value in rules:
        if symbol.startswith(prefix):
            return value
    raise SourceExtractionError(f"unknown lifecycle command caller: {symbol}")


def _symbolic_contract(value: SymbolicValue, parameter: str, position: int) -> dict[str, Any]:
    def witness(item: SymbolicValue, depth: int = 0) -> Any:
        if depth > 64: raise SourceExtractionError("lifecycle argument witness depth exceeded")
        return {"data": item.data, "kind": item.kind, "operands": [witness(x, depth + 1) for x in item.operands],
                "origins": sorted(item.origins)}
    raw = witness(value)
    base = {"parameter": parameter, "position": position, "valueWitnessSha256": witness_sha256(raw)}
    if parameter in {"force", "removeCreatureNode"}:
        if value.kind == "constant" and type(value.data) is int and value.data in {0, 1}:
            return {**base, "kind": "constant", "value": bool(value.data), "valueType": "boolean"}
        if value.kind == "field" and isinstance(value.data, str) and value.data.rsplit("::", 1)[-1] in {"force", "removeCreatureNode"}:
            return {**base, "kind": "runtimeParameter", "sourceSymbol": value.data, "valueType": "boolean"}
        raise SourceExtractionError(f"unresolved lifecycle Boolean argument {parameter}: {value.kind} {value.data}")
    if parameter == "recursion":
        if value.kind == "constant" and type(value.data) is int:
            return {**base, "kind": "constant", "value": value.data, "valueType": "integer"}
        return {**base, "kind": "runtimeValue", "sourceKind": value.kind,
                "sourceSymbol": value.data if isinstance(value.data, str) else None, "valueType": "integer"}
    return {**base, "kind": "runtimeValue", "sourceKind": value.kind,
            "sourceSymbol": value.data if isinstance(value.data, str) else None, "valueType": "sourceTyped"}


def _candidate_methods(assembly: AssemblyMetadata, target_indexes: Iterable[int]) -> list[int]:
    tokens = [(0x06000000 | index).to_bytes(4, "little") for index in target_indexes]
    result=[]
    for index, row in enumerate(assembly.md.MethodDef.rows, 1):
        if row.Rva and any(token in assembly.method_code_bytes(index) for token in tokens):
            result.append(index)
    return result


def _command_call_sites(assembly: AssemblyMetadata, assembly_sha256: str,
                        declarations: list[tuple[int, dict[str, Any]]],
                        current_move_sites: set[tuple[str, int]]) -> list[dict[str, Any]]:
    target_parameters = {row[1]["method"]["symbolSignature"]: [item["name"] for item in row[1]["parameters"]]
                         for row in declarations}
    sites=[]
    for caller_index in _candidate_methods(assembly, [row[0] for row in declarations]):
        record=assembly.method_record(caller_index, assembly_sha256)
        flow=CilDataFlow(record["instructions"])
        large_method=len(record["instructions"]) > 1024
        invocations={} if large_method else flow.run()
        raw_sites=[(index,item) for index,item in enumerate(record["instructions"])
                   if item["opcode"] in {"call","callvirt"} and item["operand"] in target_parameters]
        for instruction_index, instruction in raw_sites:
            parameters=target_parameters[instruction["operand"]]
            if large_method:
                if parameters[-1] not in {"force","removeCreatureNode"}:
                    raise SourceExtractionError(f"unsupported large lifecycle call shape at {record['symbolSignature']}:{instruction_index}")
                boolean=flow.trailing_boolean_argument(instruction_index)
                arguments=[]
                for position,parameter in enumerate(parameters[:-1]):
                    witness={"caller":record["symbolSignature"],"instructionIndex":instruction_index,
                             "parameter":parameter,"position":position,"targetSignature":instruction["operand"]}
                    arguments.append({"kind":"runtimeValue","parameter":parameter,"position":position,
                                      "sourceKind":"boundedCilInvocationArgument","sourceSymbol":None,
                                      "valueType":"sourceTyped","valueWitnessSha256":witness_sha256(witness)})
                arguments.append(_symbolic_contract(boolean,parameters[-1],len(parameters)-1))
            else:
                invocation=invocations.get(instruction_index)
                if invocation is None or invocation.symbol!=instruction["operand"] or len(invocation.arguments)!=len(parameters):
                    raise SourceExtractionError(f"lifecycle command stack arity drift at {record['symbolSignature']}:{instruction_index}")
                arguments=[_symbolic_contract(value, parameter, position)
                           for position, (parameter, value) in enumerate(zip(parameters, invocation.arguments, strict=True))]
            semantic={"arguments": arguments, "caller": record["symbolSignature"], "instructionIndex": instruction_index,
                      "target": instruction["operand"]}
            classification=("currentEncounterMove" if (record["symbolSignature"],instruction_index) in current_move_sites
                            else _classify_command_caller(record["symbolSignature"]))
            sites.append({**semantic, "callSiteId": f"LIFECYCLE.CALL.{len(sites):03d}",
                          "classification": classification,
                          "opcode": record["instructions"][instruction_index]["opcode"],
                          "provenance": {**_proof(record), "semanticWitnessSha256": witness_sha256(semantic)}})
    sites.sort(key=lambda row: (row["caller"], row["instructionIndex"], row["target"]))
    for index, row in enumerate(sites): row["callSiteId"] = f"LIFECYCLE.CALL.{index:03d}"
    counts=Counter(row["target"].split("::",1)[1].split(" sig:",1)[0] for row in sites)
    if counts != {"Kill": 19, "KillWithoutCheckingWinCondition": 2, "Escape": 3}:
        raise SourceExtractionError(f"lifecycle command call-site denominator drift: {dict(counts)}")
    encounter=[row for row in sites if row["classification"] == "currentEncounterMove"]
    if len(encounter) != 2:
        raise SourceExtractionError("current encounter Kill operation/call-site join drift")
    for row in encounter:
        force=next((item for item in row["arguments"] if item["parameter"] == "force"), None)
        if force is None or force.get("kind") != "constant" or force.get("value") is not False:
            raise SourceExtractionError("current encounter Kill operations must use ordinary force:false death")
    return sites


def _classify_check_caller(symbol: str) -> str:
    if symbol.startswith(f"{_COMBAT_MANAGER}+"):
        return "turnBoundaryOrCoreDelegation"
    if symbol.startswith(f"{_ACTION_EXECUTOR}+"):
        return "actionExecutor"
    if symbol.startswith("MegaCrit.Sts2.Core.DevConsole."):
        return "developerCommand"
    if symbol.startswith("MegaCrit.Sts2.Core.AutoSlay."):
        return "automation"
    raise SourceExtractionError(f"unknown centralized win-check caller: {symbol}")


def _check_call_sites(assembly: AssemblyMetadata, assembly_sha256: str,
                      check_indexes: list[int]) -> list[dict[str, Any]]:
    targets={assembly.method_symbol(index) for index in check_indexes}; sites=[]
    for caller_index in _candidate_methods(assembly, check_indexes):
        record=assembly.method_record(caller_index, assembly_sha256)
        for instruction_index, instruction in enumerate(record["instructions"]):
            if instruction["opcode"] not in {"call", "callvirt"} or instruction["operand"] not in targets: continue
            semantic={"caller":record["symbolSignature"],"instructionIndex":instruction_index,"target":instruction["operand"]}
            sites.append({**semantic,"classification":_classify_check_caller(record["symbolSignature"]),
                          "provenance":{**_proof(record),"semanticWitnessSha256":witness_sha256(semantic)}})
    sites.sort(key=lambda row:(row["caller"],row["instructionIndex"],row["target"]))
    for index,row in enumerate(sites):row["checkSiteId"]=f"LIFECYCLE.CHECK.{index:02d}"
    if len(sites)!=14 or Counter(row["classification"] for row in sites)!={
        "turnBoundaryOrCoreDelegation":8,"actionExecutor":1,"developerCommand":3,"automation":2}:
        raise SourceExtractionError("centralized win-check call-site closure drift")
    if any("CreatureCmd+<Kill" in row["caller"] for row in sites):
        raise SourceExtractionError("Kill must not directly call CheckWinCondition")
    return sites


def _nodes(prefix: str, stages: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    return [{"nodeId":f"{prefix}.{index:02d}.{slug}","order":index,"condition":condition,"effect":effect}
            for index,(slug,condition,effect) in enumerate(stages)]


def _linear_edges(nodes: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    return [{"edgeId":f"{prefix}.EDGE.{index:02d}","from":nodes[index]["nodeId"],"to":nodes[index+1]["nodeId"],
             "kind":"sourceOrder"} for index in range(len(nodes)-1)]


def _semantic_components() -> dict[str, Any]:
    list_nodes=_nodes("LIFECYCLE.KILL.LIST",[
        ("emptyReturn","creatures.Count == 0","return completed task without mutation"),
        ("snapshotRun","nonempty","snapshot runState from first player body when present"),
        ("snapshotBodies","nonempty","snapshot IReadOnlyList in source order"),
        ("sequentialInner","for each snapshotted body","await KillWithoutCheckingWinCondition(body, force, recursion:0) sequentially"),
        ("managerGuard","after all inner calls","return if RunManager is absent or cleaning up"),
        ("allPlayersDead","after manager guard","branch on whether every snapshotted run player is dead"),
        ("liveCombatLoss","all players dead and combat is live","call LoseCombat, setting PendingLoss once, then continue to the test-mode gate"),
        ("testModeGate","all players dead after optional live-combat LoseCombat","evaluate TestMode.IsOff for both live and non-live combat"),
        ("gameOver","all players dead and TestMode.IsOff","stop music, call OnEnded(false) synchronously, then show game over"),
        ("endKilledTurns","at least one run player remains alive","if combat remains live, end turn for each killed attached dead player-side player"),
    ])
    inner_nodes=_nodes("LIFECYCLE.KILL.INNER",[
        ("captureCombatId","entry","capture CurrentCombatId before evaluating body attachment"),
        ("entryGuards","immediately after combat ID capture","return completed without HP or death hooks for a detached non-player or any body attached to a non-live combat"),
        ("outOfCombatPlayerSafety","entry guards passed; CombatManager is not in progress, creature is a player, run player count > 1, and force == false","log error, await CreatureCmd.Heal(player, 1), and return only after success"),
        ("resolveStates","entry guards passed and safety branch did not return","resolve combatState and runState from creature"),
        ("zeroHp","CurrentHp > 0","LoseHpInternal(CurrentHp, damageType:6), then await AfterCurrentHpChanged with negative old HP"),
        ("beforeDeath","always after entry guards, including entry at zero HP","await BeforeDeath sequential dispatcher"),
        ("preventionGate","force == false and MaxHp > 0","run ordered ShouldDie early then late; first false listener is preventer"),
        ("forceBoundary","force == true or MaxHp <= 0","bypass only ShouldDie/prevention and take allowed-death branch"),
        ("died","death allowed","invoke Creature.Died synchronously"),
        ("removePredicate","death allowed","aggregate ShouldCreatureBeRemovedFromCombatAfterDeath; null combat yields false"),
        ("animation","death allowed","start node death animation when present; pass shouldRemove && IsMonster; request node removal for removable monster"),
        ("afterDeathAllowed","death allowed","await AfterDeath(wasRemovalPrevented:false, deathAnimLength)"),
        ("teammateSnapshot","death allowed","snapshot living teammates after AfterDeath"),
        ("managerRemoval","removable enemy currently in enemy list","CombatManager.RemoveCreature before state-list removal"),
        ("stateRemoval","removable enemy and monster is not performing a move","CombatState.RemoveCreature(creature,true); otherwise defer state-list removal to move completion"),
        ("powerCleanup","removable","snapshot IsPrimaryEnemy; remove Powers matching death-removal predicate and await AfterRemoved for each actually removed Power"),
        ("secondaryCleanup","removed primary with nonempty living teammates all secondary","await Kill(teammates, force:false)"),
        ("playerCleanup","creature is player","clear orbs; kill living Osty with same force; deactivate player hooks; if attached await HandlePlayerDeath(captured combat ID)"),
        ("recursionCap","death prevented and recursion == 10","throw InvalidOperationException before prevented-death hooks"),
        ("afterDeathPrevented","death prevented and recursion < 10","await AfterDeath(wasRemovalPrevented:true, deathAnimLength:0)"),
        ("afterPreventing","previous await succeeded","await AfterPreventingDeath with exact preventer"),
        ("recurse","creature remains dead","await KillWithoutCheckingWinCondition(creature, force, recursion+1); otherwise return"),
        ("awaiterFailure","any awaited task faults or cancels","propagate task state; retain only effects completed before failure; do not infer later stages"),
    ])
    escape_nodes=_nodes("LIFECYCLE.ESCAPE",[
        ("guard","creature dead, detached, or combat not live","return Task.CompletedTask without mutation"),
        ("powers","live attached creature","synchronously remove all Powers"),
        ("node","removeCreatureNode == true and node exists","request NCombatRoom removal, disable interaction, and hide node"),
        ("manager","after Power removal","CombatManager.RemoveCreature"),
        ("monsterManager","creature is monster","invoke virtual BeforeRemovedFromRoom, then ResetStateMachine"),
        ("tracker","manager removal","unsubscribe creature from CombatStateTracker, then fire manager CreaturesChanged with current state"),
        ("escapedHistory","still-attached captured state","append exact creature to EscapedCreatures"),
        ("stateRemoval","after history append","CombatState.RemoveCreature(creature,true), then return completed task"),
    ])
    victory_nodes=_nodes("LIFECYCLE.COMBAT.VICTORY",[
        ("markEnded","victory selected","set turn IsInProgress=false"),
        ("clearTurns","then","clear extra-turn state, player phases, and actions synchronously"),
        ("revivePlayers","after turn/action clearing","for each player, await ReviveBeforeCombatEnd sequentially"),
        ("afterCombatEnd","all player revives succeeded","await AfterCombatEnd sequential dispatcher"),
        ("history","AfterCombatEnd await succeeded","clear combat history"),
        ("roomEnd","then","call CombatRoom.OnCombatEnded"),
        ("playerCleanup","then","perform player combat cleanup"),
        ("afterVictory","then","await AfterCombatVictory sequential dispatcher"),
        ("record","await succeeded","record turns taken and mark room pre-finished"),
        ("save","then","save run"),
        ("progress","save succeeded","update map/progress, achievements, multiplayer scaling, and progress file"),
        ("events","then","fire CombatWon, unpause action queues, update synchronization/music, then fire CombatEnded"),
        ("downstream","after this E2d2a pipeline","terminal reward presentation and parent-event routing are pending E2d2c"),
    ])
    check_nodes=_nodes("LIFECYCLE.COMBAT.CHECK",[
        ("resolveTurn","CheckWinCondition entry","resolve current turn for no-argument overload; provided turn remains exact"),
        ("pendingLoss","PendingLoss != null","ProcessPendingLoss and return true"),
        ("isEnding","no pending loss","evaluate in-progress, primary-enemy, and stop-ending predicates"),
        ("endVictory","IsCombatEnding == true","await EndCombatInternal(turnState), then return true"),
        ("notEnding","IsCombatEnding == false","return false without termination effects"),
    ])
    def outcomes(*ids: str) -> list[dict[str, Any]]:
        return [{"outcomeId":value} for value in ids]
    def edge(edge_id: str, source: str, target: str, kind: str, condition: str) -> dict[str, Any]:
        return {"edgeId":edge_id,"from":source,"to":target,"kind":kind,"condition":condition}
    L=lambda i:list_nodes[i]["nodeId"]; I=lambda i:inner_nodes[i]["nodeId"]
    E=lambda i:escape_nodes[i]["nodeId"]; V=lambda i:victory_nodes[i]["nodeId"]; C=lambda i:check_nodes[i]["nodeId"]
    list_edges=[
        edge("LIFECYCLE.KILL.LIST.EDGE.EMPTY",L(0),"LIFECYCLE.KILL.LIST.OUTCOME.EMPTY","conditionTrue","count == 0"),
        edge("LIFECYCLE.KILL.LIST.EDGE.NONEMPTY",L(0),L(1),"conditionFalse","count > 0"),
        *[edge(f"LIFECYCLE.KILL.LIST.EDGE.ORDER.{i:02d}",L(i),L(i+1),"sourceOrder","previous synchronous stage completed") for i in range(1,3)],
        edge("LIFECYCLE.KILL.LIST.EDGE.NO_MANAGER",L(4),"LIFECYCLE.KILL.LIST.OUTCOME.MANAGER_UNAVAILABLE","conditionTrue","RunManager absent or cleaning"),
        edge("LIFECYCLE.KILL.LIST.EDGE.MANAGER",L(4),L(5),"conditionFalse","RunManager available"),
        edge("LIFECYCLE.KILL.LIST.EDGE.LIVE_COMBAT_LOSS",L(5),L(6),"conditionTrue","all players dead and combat live"),
        edge("LIFECYCLE.KILL.LIST.EDGE.NON_LIVE_ALL_DEAD",L(5),L(7),"conditionTrue","all players dead and combat not live"),
        edge("LIFECYCLE.KILL.LIST.EDGE.PLAYER_REMAINS",L(5),L(9),"conditionFalse","at least one run player alive"),
        edge("LIFECYCLE.KILL.LIST.EDGE.LOSS_FALLTHROUGH",L(6),L(7),"sourceOrder","LoseCombat returned synchronously; evaluate TestMode.IsOff next"),
        edge("LIFECYCLE.KILL.LIST.EDGE.TEST_OFF",L(7),L(8),"conditionTrue","TestMode.IsOff"),
        edge("LIFECYCLE.KILL.LIST.EDGE.TEST_ON",L(7),"LIFECYCLE.KILL.LIST.OUTCOME.TEST_MODE_SKIPPED","conditionFalse","test mode is on; skip game-over sequence and EndTurn handling"),
        edge("LIFECYCLE.KILL.LIST.EDGE.INNER_SUCCEEDED",L(3),L(4),"awaitSuccess","all sequential inner kills succeeded"),
        edge("LIFECYCLE.KILL.LIST.EDGE.INNER_FAILED",L(3),"LIFECYCLE.KILL.LIST.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","an inner kill faulted or cancelled; no manager, loss, game-over, or turn-ending stage is inferred"),
        edge("LIFECYCLE.KILL.LIST.EDGE.GAME_OVER",L(8),"LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER","sourceOrder","OnEnded(false) returned synchronously and ShowGameOverScreen was called"),
        edge("LIFECYCLE.KILL.LIST.EDGE.COMPLETE",L(9),"LIFECYCLE.KILL.LIST.OUTCOME.COMPLETED","sourceOrder","combat-live check and eligible EndTurn calls completed"),
    ]
    inner_edges=[
        edge("LIFECYCLE.KILL.INNER.EDGE.ENTRY",I(0),I(1),"sourceOrder","CurrentCombatId captured"),
        edge("LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED",I(1),"LIFECYCLE.KILL.INNER.OUTCOME.DETACHED_NON_PLAYER_COMPLETED","conditionTrue","CombatState == null and IsPlayer == false"),
        edge("LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED",I(1),"LIFECYCLE.KILL.INNER.OUTCOME.ATTACHED_NON_LIVE_COMPLETED","conditionTrue","CombatState != null and CombatState.IsLiveCombat == false"),
        edge("LIFECYCLE.KILL.INNER.EDGE.GUARDS_PASSED",I(1),I(2),"guardsPassed","detached player or body attached to a live combat"),
        edge("LIFECYCLE.KILL.INNER.EDGE.SAFETY_RETURN",I(2),"LIFECYCLE.KILL.INNER.OUTCOME.SAFETY_HEALED","awaitSuccess","out-of-combat multiplayer player safety Heal succeeded"),
        edge("LIFECYCLE.KILL.INNER.EDGE.SAFETY_CONTINUE",I(2),I(3),"conditionFalse","safety condition false, including force == true"),
        edge("LIFECYCLE.KILL.INNER.EDGE.RESOLVE_HP",I(3),I(4),"sourceOrder","states resolved"),
        edge("LIFECYCLE.KILL.INNER.EDGE.HP_BEFORE",I(4),I(5),"conditionOrSkip","HP change await completed or CurrentHp was already zero"),
        edge("LIFECYCLE.KILL.INNER.EDGE.CHECK_PREVENTION",I(5),I(6),"conditionTrue","force == false and MaxHp > 0"),
        edge("LIFECYCLE.KILL.INNER.EDGE.BYPASS_PREVENTION",I(5),I(7),"conditionFalse","force == true or MaxHp <= 0"),
        edge("LIFECYCLE.KILL.INNER.EDGE.DEATH_ALLOWED",I(6),I(8),"predicateResult","ShouldDie allowed"),
        edge("LIFECYCLE.KILL.INNER.EDGE.DEATH_PREVENTED",I(6),I(18),"predicateResult","first ShouldDie/ShouldDieLate false"),
        edge("LIFECYCLE.KILL.INNER.EDGE.FORCED_ALLOWED",I(7),I(8),"sourceOrder","prevention bypass only"),
        *[edge(f"LIFECYCLE.KILL.INNER.EDGE.ALLOWED.{i:02d}",I(i),I(i+1),"conditionOrSkip","stage condition applied without reordering") for i in range(8,17)],
        edge("LIFECYCLE.KILL.INNER.EDGE.ALLOWED_COMPLETE",I(17),"LIFECYCLE.KILL.INNER.OUTCOME.ALLOWED","sourceOrder","player cleanup applied or skipped"),
        edge("LIFECYCLE.KILL.INNER.EDGE.RECURSION_CAP",I(18),"LIFECYCLE.KILL.INNER.OUTCOME.RECURSION_CAP_EXCEPTION","conditionTrue","recursion == 10"),
        edge("LIFECYCLE.KILL.INNER.EDGE.PREVENTED_HOOKS",I(18),I(19),"conditionFalse","recursion < 10"),
        edge("LIFECYCLE.KILL.INNER.EDGE.AFTER_PREVENTED",I(19),I(20),"awaitSuccess","AfterDeath(true) succeeded"),
        edge("LIFECYCLE.KILL.INNER.EDGE.RECOVERY_CHECK",I(20),I(21),"awaitSuccess","AfterPreventingDeath succeeded"),
        edge("LIFECYCLE.KILL.INNER.EDGE.RECOVERED",I(21),"LIFECYCLE.KILL.INNER.OUTCOME.RECOVERED","conditionFalse","creature no longer dead"),
        edge("LIFECYCLE.KILL.INNER.EDGE.RECURSE",I(21),"LIFECYCLE.KILL.INNER.OUTCOME.RECURSED","conditionTrue","creature remains dead; recursive await succeeds"),
        *[edge(f"LIFECYCLE.KILL.INNER.EDGE.FAIL.{i:02d}",I(i),I(22),"faultOrCancellation","awaited stage faults or cancels") for i in (2,4,5,11,15,16,17,19,20,21)],
        edge("LIFECYCLE.KILL.INNER.EDGE.FAIL_OUTCOME",I(22),"LIFECYCLE.KILL.INNER.OUTCOME.FAULT_OR_CANCEL","propagate","no later stage inferred"),
    ]
    escape_edges=[
        edge("LIFECYCLE.ESCAPE.EDGE.NOOP",E(0),"LIFECYCLE.ESCAPE.OUTCOME.NOOP","conditionTrue","dead, detached, or non-live"),
        edge("LIFECYCLE.ESCAPE.EDGE.LIVE",E(0),E(1),"conditionFalse","live and attached"),
        *[edge(f"LIFECYCLE.ESCAPE.EDGE.ORDER.{i:02d}",E(i),E(i+1),"conditionOrOrder","optional node/monster stages apply or skip without reordering") for i in range(1,7)],
        edge("LIFECYCLE.ESCAPE.EDGE.COMPLETE",E(7),"LIFECYCLE.ESCAPE.OUTCOME.COMPLETED","sourceOrder","state removal completed synchronously"),
    ]
    check_edges=[
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.PENDING",C(0),C(1),"conditionTrue","PendingLoss != null"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.NO_PENDING",C(0),C(2),"conditionFalse","PendingLoss == null"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.LOSS",C(1),"LIFECYCLE.COMBAT.CHECK.OUTCOME.LOSS_PROCESSED","sourceOrder","ProcessPendingLoss returned true"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.VICTORY",C(2),C(3),"predicateResult","IsCombatEnding true"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.CONTINUE",C(2),C(4),"predicateResult","IsCombatEnding false"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.ENDED",C(3),"LIFECYCLE.COMBAT.CHECK.OUTCOME.VICTORY_ENDED","awaitSuccess","EndCombatInternal succeeded"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.NOT_ENDED",C(4),"LIFECYCLE.COMBAT.CHECK.OUTCOME.CONTINUE","sourceOrder","return false"),
        edge("LIFECYCLE.COMBAT.CHECK.EDGE.FAIL",C(3),"LIFECYCLE.COMBAT.CHECK.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","EndCombatInternal faulted or cancelled"),
    ]
    victory_edges=[
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.00",V(0),V(1),"sourceOrder","turn marked ended"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.01",V(1),V(2),"sourceOrder","synchronous turn/action clearing completed"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.02",V(2),V(3),"awaitSuccess","all sequential ReviveBeforeCombatEnd tasks succeeded"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.03",V(3),V(4),"awaitSuccess","AfterCombatEnd succeeded"),
        *[edge(f"LIFECYCLE.COMBAT.VICTORY.EDGE.{i:02d}",V(i),V(i+1),"sourceOrder","previous synchronous stage completed") for i in range(4,7)],
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.07",V(7),V(8),"awaitSuccess","AfterCombatVictory succeeded"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.08",V(8),V(9),"sourceOrder","recording completed"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.09",V(9),V(10),"awaitSuccess","SaveRun succeeded"),
        *[edge(f"LIFECYCLE.COMBAT.VICTORY.EDGE.{i:02d}",V(i),V(i+1),"sourceOrder","previous synchronous stage completed") for i in range(10,12)],
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.REVIVE_FAIL",V(2),"LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","a ReviveBeforeCombatEnd task failed or cancelled"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.AFTER_END_FAIL",V(3),"LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","AfterCombatEnd failed or cancelled"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.AFTER_VICTORY_FAIL",V(7),"LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","AfterCombatVictory failed or cancelled"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.SAVE_FAIL",V(9),"LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","SaveRun failed or cancelled"),
        edge("LIFECYCLE.COMBAT.VICTORY.EDGE.COMPLETE",V(12),"LIFECYCLE.COMBAT.VICTORY.OUTCOME.E2D2C_BOUNDARY","dependencyBoundary","rewards and parent routing pending E2d2c"),
    ]

    return {
        "core": {
            "singularKillContract": "construct one-item IReadOnlyList preserving body identity, then await list Kill with the same force",
            "listKillGraph": {"graphId":"LIFECYCLE.KILL.LIST","nodes":list_nodes,"edges":list_edges,
                "outcomes":outcomes("LIFECYCLE.KILL.LIST.OUTCOME.EMPTY","LIFECYCLE.KILL.LIST.OUTCOME.MANAGER_UNAVAILABLE","LIFECYCLE.KILL.LIST.OUTCOME.TEST_MODE_SKIPPED","LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER","LIFECYCLE.KILL.LIST.OUTCOME.COMPLETED","LIFECYCLE.KILL.LIST.OUTCOME.FAULT_OR_CANCEL")},
            "innerDeathGraph": {"graphId":"LIFECYCLE.KILL.INNER","nodes":inner_nodes,
                "edges":inner_edges,
                "outcomes":outcomes("LIFECYCLE.KILL.INNER.OUTCOME.DETACHED_NON_PLAYER_COMPLETED","LIFECYCLE.KILL.INNER.OUTCOME.ATTACHED_NON_LIVE_COMPLETED","LIFECYCLE.KILL.INNER.OUTCOME.SAFETY_HEALED","LIFECYCLE.KILL.INNER.OUTCOME.ALLOWED","LIFECYCLE.KILL.INNER.OUTCOME.RECURSION_CAP_EXCEPTION","LIFECYCLE.KILL.INNER.OUTCOME.RECOVERED","LIFECYCLE.KILL.INNER.OUTCOME.RECURSED","LIFECYCLE.KILL.INNER.OUTCOME.FAULT_OR_CANCEL"),
                "closedBranches":["detachedNonPlayerCompleted","attachedNonLiveCompleted","outOfCombatMultiplayerSafetyReturn","allowedDeath","preventedDeath","recoveryReturn","recursion","recursionCapException","faultOrCancellation"],
                "directCheckWinCondition":False,"deadBodyEntryShortCircuit":False,
                "forceContract":"entry guards complete regardless of force; after they pass, force bypasses only out-of-combat multiplayer player safety healing and ShouldDie/prevention; HP zeroing, BeforeDeath, Died, animation, AfterDeath, removal, Power cleanup, and player cleanup remain"},
            "listSnapshotOrder":"source list snapshot; sequential await; duplicates are retained",
            "emptyBehavior":"completed without reading first element or mutating state",
        },
        "dispatch": {
            "shouldDie":{"order":["ShouldDie over current registry snapshot","ShouldDieLate over current registry snapshot"],"aggregation":"first false stops and becomes exact preventer","forceBypassOnly":True},
            "awaitedDispatch":{"families":["BeforeDeath","AfterDeath","AfterPreventingDeath"],"execution":"registry order, one listener task at a time; InvokeExecutionFinished only after each successful listener task","parallelism":"none"},
            "predicates":[
                {"family":"ShouldCreatureBeRemovedFromCombatAfterDeath","aggregation":"all current listeners must return true; null combat is false"},
                {"family":"ShouldStopCombatFromEnding","aggregation":"any current listener returning true stops ending"},
            ],
            "failureContract":"fault/cancellation propagates; no later callback or lifecycle stage is claimed",
        },
        "listenerRegistry": {
            "combatOrder":[
                {"order":0,"source":"allies then enemies","collectionOrder":"stored list order"},
                {"order":1,"source":"each creature","collectionOrder":"Powers then Monster model"},
                {"order":2,"source":"active player contents","collectionOrder":"unmelted relics, non-null potions, orbs, cards in all combat piles, each card affliction then enchantment"},
                {"order":3,"source":"combat globals","collectionOrder":"combat modifiers, badges, multiplayer scaling model"},
                {"order":4,"source":"mod combat subscribers","collectionOrder":"registry order; external runtime boundary"},
            ],
            "runOrder":[
                {"order":0,"source":"active-player deck","collectionOrder":"cards then each enchantment"},
                {"order":1,"source":"active-player inventory","collectionOrder":"relics then potions"},
                {"order":2,"source":"run globals","collectionOrder":"run modifiers, badges, multiplayer scaling model"},
                {"order":3,"source":"mod run subscribers","collectionOrder":"registry order; external runtime boundary"},
                {"order":4,"source":"child combat registry","collectionOrder":"combat registry order above"},
            ],
            "membership":"yield only models still contained by the relevant current state when filtered",
            "snapshot":"dispatcher enumeration snapshots current registries at source-defined boundaries",
            "duplicates":"preserved; no sorting or de-duplication by model type or ID",
            "dynamicValues":"player cards/relics/potions/orbs/enchantments and mod subscribers are runtime values, never assumed empty",
        },
        "removal": {
            "escapeGraph":{"graphId":"LIFECYCLE.ESCAPE","nodes":escape_nodes,"edges":escape_edges,
                "outcomes":outcomes("LIFECYCLE.ESCAPE.OUTCOME.NOOP","LIFECYCLE.ESCAPE.OUTCOME.COMPLETED")},
            "stateRemoval":{"guards":["already detached returns","different attached combat throws","absent from both side lists throws"],"order":["remove from exactly one allies/enemies list","if unattach then null CombatState","fire state CreaturesChanged"]},
            "deathMoveDeferral":"manager removal is immediate; state-list removal is deferred while a dying monster performs its move",
            "separateCleanup":"CombatRoom.Exit/reset cleanup is not death or escape",
            "escapeDeathHooks":[],"escapeResultEnum":None,
        },
        "combatTermination": {
            "pendingLoss":{"representation":"nullable PendingLoss state; no result enum exists","order":["clear PendingLoss","set IsInProgress=false","invoke CombatEnded(pending.Room)","return true"]},
            "victoryPredicate":{"all":["turnState.IsInProgress","no enemy where IsAlive && IsPrimaryEnemy","no current listener stops ending"],"secondaryOnlyEnemiesBlock":False,"allEscaped":"ordinary victory at the next centralized check"},
            "checkGraph":{"graphId":"LIFECYCLE.COMBAT.CHECK","nodes":check_nodes,"edges":check_edges,
                "outcomes":outcomes("LIFECYCLE.COMBAT.CHECK.OUTCOME.LOSS_PROCESSED","LIFECYCLE.COMBAT.CHECK.OUTCOME.VICTORY_ENDED","LIFECYCLE.COMBAT.CHECK.OUTCOME.CONTINUE","LIFECYCLE.COMBAT.CHECK.OUTCOME.FAULT_OR_CANCEL")},
            "victoryGraph":{"graphId":"LIFECYCLE.COMBAT.VICTORY","nodes":victory_nodes,"edges":victory_edges,
                "outcomes":outcomes("LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","LIFECYCLE.COMBAT.VICTORY.OUTCOME.E2D2C_BOUNDARY")},
            "actionExecutorEdges":[
                {"edgeId":"LIFECYCLE.ACTION.NORMAL","from":"action task resolved normally","to":"centralized CheckWinCondition","result":"check runs"},
                {"edgeId":"LIFECYCLE.ACTION.LOGGED_FAULT","from":"action task fault observed and logged by executor","to":"centralized CheckWinCondition","result":"check still runs; fault is not reclassified as gameplay success"},
                {"edgeId":"LIFECYCLE.ACTION.CANCEL","from":"action cancellation/queue stop","to":"no success edge","result":"must not infer check or later completion from cancellation"},
                {"edgeId":"LIFECYCLE.AWAIT.FAILURE","from":"awaited termination stage fault/cancel","to":"task fault/cancel","result":"no later victory stage inferred"},
            ],
            "killDirectWinCheck":False,"resultEnum":None,
        },
    }


def _classify_lifecycle_invocation(callee: str) -> str:
    if callee in _BODY_PINS:return "closedLifecycleMethod"
    if callee.startswith("MegaCrit.Sts2.Core.Hooks.Hook::") or callee.startswith("MegaCrit.Sts2.Core.Models.AbstractModel::"):
        return "listenerDispatch"
    member=callee.split("::",1)[1].split(" sig:",1)[0] if "::" in callee else ""
    if member.startswith("get_"):return "sourceStateRead"
    if member.startswith("set_"):return "sourceStateWrite"
    if callee.startswith("System.Runtime.CompilerServices.") or callee.startswith("System.Threading.Tasks."):
        return "asyncOrTaskPlumbing"
    if callee.startswith("System."):return "sourceLibraryOperation"
    if callee.startswith("Godot."):return "enginePresentationBoundary"
    if callee.startswith("MegaCrit.Sts2.Core.Commands."):return "sourceCommandOrEffect"
    if callee.startswith("<TypeSpec:"):return "sourceDefinedDelegateBoundary"
    if callee.startswith("MegaCrit.Sts2."):return "sourceDefinedRuntimeBoundary"
    return "externalLibraryBoundary"


def _invocation_census(assembly: AssemblyMetadata, assembly_sha256: str) -> dict[str, Any]:
    symbol_to_index={assembly.method_symbol(index):index for index in range(1,len(assembly.md.MethodDef.rows)+1)}
    if not set(_BODY_PINS)<=set(symbol_to_index):raise SourceExtractionError("lifecycle method closure symbol missing")
    rows=[]
    for caller in sorted(_BODY_PINS):
        record=assembly.method_record(symbol_to_index[caller],assembly_sha256)
        for instruction_index,instruction in enumerate(record["instructions"]):
            if instruction["opcode"] not in {"call","callvirt","newobj"}:continue
            callee=instruction["operand"]
            if not isinstance(callee,str):raise SourceExtractionError(f"unresolved lifecycle invocation target at {caller}:{instruction_index}")
            semantic={"callee":callee,"caller":caller,"instructionIndex":instruction_index,"opcode":instruction["opcode"]}
            rows.append({**semantic,"classification":_classify_lifecycle_invocation(callee),
                         "provenance":{"assemblySha256":assembly_sha256,
                            "callerMethodBodySha256":record["methodBodySha256"],
                            "callerNormalizedInstructionsSha256":record["normalizedInstructionsSha256"],
                            "semanticWitnessSha256":witness_sha256(semantic)}})
    rows.sort(key=lambda row:(row["caller"],row["instructionIndex"],row["callee"]))
    for index,row in enumerate(rows):row["invocationId"]=f"LIFECYCLE.INVOCATION.{index:03d}"
    counts=dict(sorted(Counter(row["classification"] for row in rows).items()))
    if len(rows)!=707 or any(row["classification"]=="ignored" for row in rows):
        raise SourceExtractionError("lifecycle invocation classification closure drift")
    return {"closureKind":"transitiveWithinExactLogicalPhysicalLifecycleMethodSet",
            "externalCalls":"retained as exact classified boundaries, never ignored",
            "decisions":rows,"summary":{"classificationCounts":counts,"denominator":len(rows),"resolved":len(rows),"unresolved":0}}


def _boundary_declarations(assembly: AssemblyMetadata, assembly_sha256: str) -> list[dict[str, Any]]:
    specs=(
        ("MegaCrit.Sts2.Core.Models.Relics.GremlinHorn","AfterDeath"),
        ("MegaCrit.Sts2.Core.Models.Relics.BookRepairKnife","AfterDiedToDoom"),
        ("MegaCrit.Sts2.Core.Models.Relics.LizardTail","ShouldDieLate"),
        ("MegaCrit.Sts2.Core.Models.Relics.LizardTail","AfterPreventingDeath"),
        ("MegaCrit.Sts2.Core.Models.Potions.FairyInABottle","ShouldDie"),
        ("MegaCrit.Sts2.Core.Models.Potions.FairyInABottle","AfterPreventingDeath"),
        ("MegaCrit.Sts2.Core.Models.Cards.Melancholy","AfterDeath"),
    )
    result=[]
    for owner,name in specs:
        indexes=assembly.find_methods(owner,name)
        if len(indexes)!=1: raise SourceExtractionError(f"lifecycle vanilla runtime-boundary declaration drift: {owner}::{name}")
        record=assembly.method_record(indexes[0],assembly_sha256)
        result.append({"boundaryId":f"LIFECYCLE.BOUNDARY.{owner.rsplit('.',1)[-1].upper()}.{name.upper()}",
                       "classification":"vanillaExternalRunOrPlayerListener","effectStatus":"pendingE2d2b",
                       "method":_proof(record),"sourceType":owner})
    result.sort(key=lambda row:row["boundaryId"])
    return result


def extract_lifecycle(assembly: AssemblyMetadata, assembly_sha256: str,
                      behavior: Mapping[str, Any]) -> dict[str, Any]:
    async_map=_async_map(assembly)
    command=[]
    for spec in _DECLARATIONS:
        command.append(_method_contract(assembly,assembly_sha256,spec,async_map,
                      async_required=spec[1] in {"Kill","KillWithoutCheckingWinCondition"}))
    dispatch=[]
    for spec in _DISPATCH:
        dispatch.append(_method_contract(assembly,assembly_sha256,spec,async_map,
                      async_required=spec[1] in {"BeforeDeath","AfterDeath","AfterPreventingDeath"}))
    termination=[]
    for spec in _TERMINATION:
        termination.append(_method_contract(assembly,assembly_sha256,spec,async_map,
                      async_required=spec[1] in {"CheckWinCondition","EndCombatInternal"}))
    registry_specs=(
        (_HOOK,"IterateCombatHookListeners","0001151281f50112889c12aa88",("combatState",),f"{_HOOK}+<IterateCombatHookListeners>d__0","MoveNext","200002"),
        (_COMBAT_STATE,"IterateHookListeners","2000151281f50112889c",(),f"{_COMBAT_STATE}+<IterateHookListeners>d__69","MoveNext","200002"),
        (_RUN_STATE,"IterateHookListeners","2001151281f50112889c12aa88",("childCombatState",),f"{_RUN_STATE}+<IterateHookListeners>d__118","MoveNext","200002"),
    )
    registries=[]
    for owner,name,sig,params,physical_owner,physical_name,physical_sig in registry_specs:
        _,logical=_exact_method(assembly,assembly_sha256,owner,name,sig,params)
        _,physical=_exact_method(assembly,assembly_sha256,physical_owner,physical_name,physical_sig,())
        registries.append({"method":_proof(logical),"parameters":[{"name":p,"position":i,"sourceMetadata":True} for i,p in enumerate(params)],"physicalBody":_proof(physical)})
    removal=[]
    for spec in (
        (_COMBAT_MANAGER,"RemoveCreature","20010112a7e4",("creature",)),
        (_COMBAT_STATE,"CreatureEscaped","20010112a7e4",("creature",)),
        (_COMBAT_STATE,"RemoveCreature","20020112a7e402",("creature","unattach")),
    ):
        removal.append(_method_contract(assembly,assembly_sha256,spec,async_map)[1])
    _,action=_exact_method(assembly,assembly_sha256,f"{_ACTION_EXECUTOR}+<ExecuteActions>d__28","MoveNext","200001",())
    current_operations=[op for move in behavior["registrations"] for op in move["operations"] if op.get("kind")=="kill"]
    current_move_sites={(op["provenance"]["symbolSignature"],op["sourceOrder"]) for op in current_operations}
    if len(current_operations)!=2 or len(current_move_sites)!=2:
        raise SourceExtractionError("current encounter Kill operation/call-site join drift")
    call_sites=_command_call_sites(assembly,assembly_sha256,command,current_move_sites)
    check_indexes=[index for (index,row),spec in zip(termination,_TERMINATION,strict=True) if spec[1]=="CheckWinCondition"]
    check_sites=_check_call_sites(assembly,assembly_sha256,check_indexes)
    semantic=_semantic_components(); boundaries=_boundary_declarations(assembly,assembly_sha256)
    invocation_census=_invocation_census(assembly,assembly_sha256)
    dependencies=[
        {"dependencyId":"DEPENDENCY.LIFECYCLE.E2B.CONCRETE_LISTENERS","kind":"listenerEffectsPhasesRelationshipsDeathAdd","status":"pendingE2d2b"},
        {"dependencyId":"DEPENDENCY.LIFECYCLE.E2C.EVENT_TERMINATION","kind":"eventRewardsBattleParentRouting","status":"pendingE2d2c"},
        {"dependencyId":"DEPENDENCY.LIFECYCLE.E2D.RUN_TERMINATION","kind":"architectRunTermination","status":"pendingE2d2d"},
        {"dependencyId":"DEPENDENCY.LIFECYCLE.HP","kind":"hpMutationContract","resolvedComponentRef":"hpPipeline.assignment","status":"sourceComplete"},
        {"dependencyId":"DEPENDENCY.LIFECYCLE.INITIAL","kind":"initialStateContract","resolvedComponentRef":"initialState","status":"sourceComplete"},
        {"dependencyId":"DEPENDENCY.LIFECYCLE.PRODUCTION","kind":"productionContract","resolvedComponentRef":"production.productionSemantics","status":"sourceComplete"},
        {"dependencyId":"DEPENDENCY.LIFECYCLE.EVENT_SCRIPTS","kind":"eventScriptContract","resolvedComponentRef":"eventScripts","status":"sourceComplete"},
    ]
    denominators={
        "commandDeclarations":len(command),"commandPhysicalBodies":len(command),
        "killCallSites":sum("::Kill sig:" in row["target"] or "::KillWithoutCheckingWinCondition sig:" in row["target"] for row in call_sites),
        "escapeCallSites":sum("::Escape sig:" in row["target"] for row in call_sites),
        "dispatchMethods":len(dispatch),"listenerRegistryLogicalMethods":len(registries),
        "listenerRegistryPhysicalBodies":len(registries),"removalMethods":len(removal)+1,
        "terminationDeclarations":4,"terminationPhysicalBodies":4,
        "terminationSupportMethods":3,"centralizedCheckCallSites":len(check_sites),
        "runtimeBoundaries":len(boundaries),"dependencies":len(dependencies),
        "invocations":invocation_census["summary"]["denominator"],
        "semanticNodes":sum(len(value["nodes"]) for value in (
            semantic["core"]["listKillGraph"],semantic["core"]["innerDeathGraph"],
            semantic["removal"]["escapeGraph"],semantic["combatTermination"]["checkGraph"],semantic["combatTermination"]["victoryGraph"])),
    }
    expected={"commandDeclarations":4,"commandPhysicalBodies":4,"killCallSites":21,"escapeCallSites":3,
              "dispatchMethods":6,"listenerRegistryLogicalMethods":3,"listenerRegistryPhysicalBodies":3,
              "removalMethods":4,"terminationDeclarations":4,"terminationPhysicalBodies":4,
              "terminationSupportMethods":3,"centralizedCheckCallSites":14,"runtimeBoundaries":7,
              "dependencies":7,"invocations":707,"semanticNodes":59}
    if denominators!=expected: raise SourceExtractionError(f"lifecycle source denominator drift: {denominators!r}")
    component={
        "componentId":"LIFECYCLE.CORE.E2D2A","status":"sourceCompleteE2d2a",
        **semantic,
        "api":{"commandDeclarations":[row for _,row in command],"commandCallSites":call_sites},
        "dispatchMethods":[row for _,row in dispatch],
        "listenerRegistryMethods":registries,
        "removalMethods":removal,
        "combatTerminationMethods":[row for _,row in termination],
        "centralizedCheckCallSites":check_sites,"actionExecutorMethod":_proof(action),
        "invocationCensus":invocation_census,
        "runtimeStateContracts":[
            {"contractId":"LIFECYCLE.STATE.FORCE","initial":"call argument","mutation":"propagated unchanged except secondary cleanup fixes false","ownership":"command invocation"},
            {"contractId":"LIFECYCLE.STATE.RECURSION","initial":0,"mutation":"increment only after prevention while still dead","cap":10,"ownership":"inner kill invocation"},
            {"contractId":"LIFECYCLE.STATE.PREVENTER","initial":None,"mutation":"first early/late ShouldDie listener returning false","ownership":"dispatch result"},
            {"contractId":"LIFECYCLE.STATE.PENDING_LOSS","initial":None,"mutation":"LoseCombat sets once; ProcessPendingLoss clears","ownership":"CombatManager"},
            {"contractId":"LIFECYCLE.STATE.ESCAPED_CREATURES","initial":"runtime collection","mutation":"append exact escaped body before state removal","ownership":"CombatState"},
            {"contractId":"LIFECYCLE.STATE.LISTENERS","initial":"runtime collections","mutation":"dynamic source-defined membership","ownership":"run/combat/player/mod registries"},
            {"contractId":"LIFECYCLE.STATE.MOVE_REMOVAL","initial":"runtime Monster performing-move state","mutation":"move completion owns deferred state-list removal","ownership":"MonsterModel/CombatState"},
        ],
        "runtimeBoundaries":boundaries,"dependencies":dependencies,"sourceDenominators":denominators,
    }
    component["digests"]={
        "callSiteOrderingSha256":witness_sha256([(row["caller"],row["instructionIndex"],row["target"]) for row in call_sites]),
        "coreSemanticsSha256":witness_sha256(semantic),
        "dependencySha256":witness_sha256(dependencies),
        "methodClosureSha256":witness_sha256(sorted(_BODY_PINS.items())),
        "invocationOrderingSha256":witness_sha256([(row["caller"],row["instructionIndex"],row["callee"],row["classification"]) for row in invocation_census["decisions"]]),
    }
    validate_lifecycle(component)
    return component


def validate_lifecycle(value: Any) -> None:
    if not isinstance(value,dict): raise SourceExtractionError("lifecycle component must be an object")
    required={"componentId","status","core","dispatch","listenerRegistry","removal","combatTermination","api",
              "dispatchMethods","listenerRegistryMethods","removalMethods","combatTerminationMethods",
              "centralizedCheckCallSites","actionExecutorMethod","invocationCensus","runtimeStateContracts","runtimeBoundaries",
              "dependencies","sourceDenominators","digests"}
    if set(value)!=required: raise SourceExtractionError("lifecycle component fields changed")
    if value["componentId"]!="LIFECYCLE.CORE.E2D2A" or value["status"]!="sourceCompleteE2d2a":
        raise SourceExtractionError("lifecycle component identity/status changed")
    text=repr(value)
    if "playDeathEffects" in text: raise SourceExtractionError("legacy playDeathEffects is forbidden in lifecycle schema")
    if "CombatResult" in text: raise SourceExtractionError("invented CombatResult is forbidden in lifecycle schema")
    graphs=(value["core"]["listKillGraph"],value["core"]["innerDeathGraph"],value["removal"]["escapeGraph"],
            value["combatTermination"]["checkGraph"],value["combatTermination"]["victoryGraph"])
    for graph in graphs:
        nodes=graph.get("nodes");edges=graph.get("edges");outcomes=graph.get("outcomes")
        if not isinstance(nodes,list) or not isinstance(edges,list) or not isinstance(outcomes,list) or not nodes or not edges or not outcomes:
            raise SourceExtractionError("lifecycle graph nodes/edges/outcomes must be closed and nonempty")
        node_ids=[row.get("nodeId") for row in nodes];outcome_ids=[row.get("outcomeId") for row in outcomes]
        edge_ids=[row.get("edgeId") for row in edges]
        if len(set(node_ids))!=len(node_ids) or len(set(outcome_ids))!=len(outcome_ids) or len(set(edge_ids))!=len(edge_ids):
            raise SourceExtractionError("duplicate lifecycle graph node/edge/outcome ID")
        if [row.get("order") for row in nodes]!=list(range(len(nodes))):
            raise SourceExtractionError("lifecycle graph source order changed")
        if any(edge.get("from") not in set(node_ids) or edge.get("to") not in set(node_ids)|set(outcome_ids) for edge in edges):
            raise SourceExtractionError("lifecycle graph edge has unknown endpoint")
        if set(node_ids)-{edge.get("from") for edge in edges}:
            raise SourceExtractionError("lifecycle graph node has no closed outgoing edge")
        if set(outcome_ids)-{edge.get("to") for edge in edges}:
            raise SourceExtractionError("lifecycle graph outcome is unreachable")
    list_graph=value["core"]["listKillGraph"]
    list_node_ids=[row["nodeId"] for row in list_graph["nodes"]]
    if list_node_ids != [
        "LIFECYCLE.KILL.LIST.00.emptyReturn", "LIFECYCLE.KILL.LIST.01.snapshotRun",
        "LIFECYCLE.KILL.LIST.02.snapshotBodies", "LIFECYCLE.KILL.LIST.03.sequentialInner",
        "LIFECYCLE.KILL.LIST.04.managerGuard", "LIFECYCLE.KILL.LIST.05.allPlayersDead",
        "LIFECYCLE.KILL.LIST.06.liveCombatLoss", "LIFECYCLE.KILL.LIST.07.testModeGate",
        "LIFECYCLE.KILL.LIST.08.gameOver", "LIFECYCLE.KILL.LIST.09.endKilledTurns",
    ]:
        raise SourceExtractionError("list kill source node order changed")
    list_outcomes={row["outcomeId"] for row in list_graph["outcomes"]}
    if list_outcomes != {
        "LIFECYCLE.KILL.LIST.OUTCOME.EMPTY", "LIFECYCLE.KILL.LIST.OUTCOME.MANAGER_UNAVAILABLE",
        "LIFECYCLE.KILL.LIST.OUTCOME.TEST_MODE_SKIPPED", "LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER",
        "LIFECYCLE.KILL.LIST.OUTCOME.COMPLETED", "LIFECYCLE.KILL.LIST.OUTCOME.FAULT_OR_CANCEL",
    }:
        raise SourceExtractionError("list kill outcomes changed")
    list_edge_ids={row["edgeId"]:(row["from"],row["to"],row["kind"],row["condition"]) for row in list_graph["edges"]}
    expected_list_edges={
        "LIFECYCLE.KILL.LIST.EDGE.INNER_SUCCEEDED":("LIFECYCLE.KILL.LIST.03.sequentialInner","LIFECYCLE.KILL.LIST.04.managerGuard","awaitSuccess","all sequential inner kills succeeded"),
        "LIFECYCLE.KILL.LIST.EDGE.INNER_FAILED":("LIFECYCLE.KILL.LIST.03.sequentialInner","LIFECYCLE.KILL.LIST.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation","an inner kill faulted or cancelled; no manager, loss, game-over, or turn-ending stage is inferred"),
        "LIFECYCLE.KILL.LIST.EDGE.LIVE_COMBAT_LOSS":("LIFECYCLE.KILL.LIST.05.allPlayersDead","LIFECYCLE.KILL.LIST.06.liveCombatLoss","conditionTrue","all players dead and combat live"),
        "LIFECYCLE.KILL.LIST.EDGE.NON_LIVE_ALL_DEAD":("LIFECYCLE.KILL.LIST.05.allPlayersDead","LIFECYCLE.KILL.LIST.07.testModeGate","conditionTrue","all players dead and combat not live"),
        "LIFECYCLE.KILL.LIST.EDGE.PLAYER_REMAINS":("LIFECYCLE.KILL.LIST.05.allPlayersDead","LIFECYCLE.KILL.LIST.09.endKilledTurns","conditionFalse","at least one run player alive"),
        "LIFECYCLE.KILL.LIST.EDGE.LOSS_FALLTHROUGH":("LIFECYCLE.KILL.LIST.06.liveCombatLoss","LIFECYCLE.KILL.LIST.07.testModeGate","sourceOrder","LoseCombat returned synchronously; evaluate TestMode.IsOff next"),
        "LIFECYCLE.KILL.LIST.EDGE.TEST_OFF":("LIFECYCLE.KILL.LIST.07.testModeGate","LIFECYCLE.KILL.LIST.08.gameOver","conditionTrue","TestMode.IsOff"),
        "LIFECYCLE.KILL.LIST.EDGE.TEST_ON":("LIFECYCLE.KILL.LIST.07.testModeGate","LIFECYCLE.KILL.LIST.OUTCOME.TEST_MODE_SKIPPED","conditionFalse","test mode is on; skip game-over sequence and EndTurn handling"),
        "LIFECYCLE.KILL.LIST.EDGE.GAME_OVER":("LIFECYCLE.KILL.LIST.08.gameOver","LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER","sourceOrder","OnEnded(false) returned synchronously and ShowGameOverScreen was called"),
    }
    if any(list_edge_ids.get(edge_id)!=contract for edge_id,contract in expected_list_edges.items()):
        raise SourceExtractionError("list kill loss/test-mode fallthrough or awaited contract changed")
    inner=value["core"]["innerDeathGraph"]
    inner_node_ids=[row["nodeId"] for row in inner["nodes"]]
    if len(inner_node_ids)!=23 or inner_node_ids[:8] != [
        "LIFECYCLE.KILL.INNER.00.captureCombatId", "LIFECYCLE.KILL.INNER.01.entryGuards",
        "LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety", "LIFECYCLE.KILL.INNER.03.resolveStates",
        "LIFECYCLE.KILL.INNER.04.zeroHp", "LIFECYCLE.KILL.INNER.05.beforeDeath",
        "LIFECYCLE.KILL.INNER.06.preventionGate", "LIFECYCLE.KILL.INNER.07.forceBoundary",
    ] or inner_node_ids[8]!="LIFECYCLE.KILL.INNER.08.died" or inner_node_ids[-1]!="LIFECYCLE.KILL.INNER.22.awaiterFailure":
        raise SourceExtractionError("inner kill entry guard/death node order changed")
    inner_edge_ids={row["edgeId"]:(row["from"],row["to"],row["kind"],row["condition"]) for row in inner["edges"]}
    expected_inner_edges={
        "LIFECYCLE.KILL.INNER.EDGE.ENTRY":("LIFECYCLE.KILL.INNER.00.captureCombatId","LIFECYCLE.KILL.INNER.01.entryGuards","sourceOrder","CurrentCombatId captured"),
        "LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED":("LIFECYCLE.KILL.INNER.01.entryGuards","LIFECYCLE.KILL.INNER.OUTCOME.DETACHED_NON_PLAYER_COMPLETED","conditionTrue","CombatState == null and IsPlayer == false"),
        "LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED":("LIFECYCLE.KILL.INNER.01.entryGuards","LIFECYCLE.KILL.INNER.OUTCOME.ATTACHED_NON_LIVE_COMPLETED","conditionTrue","CombatState != null and CombatState.IsLiveCombat == false"),
        "LIFECYCLE.KILL.INNER.EDGE.GUARDS_PASSED":("LIFECYCLE.KILL.INNER.01.entryGuards","LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","guardsPassed","detached player or body attached to a live combat"),
        "LIFECYCLE.KILL.INNER.EDGE.SAFETY_RETURN":("LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","LIFECYCLE.KILL.INNER.OUTCOME.SAFETY_HEALED","awaitSuccess","out-of-combat multiplayer player safety Heal succeeded"),
        "LIFECYCLE.KILL.INNER.EDGE.SAFETY_CONTINUE":("LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","LIFECYCLE.KILL.INNER.03.resolveStates","conditionFalse","safety condition false, including force == true"),
        "LIFECYCLE.KILL.INNER.EDGE.FAIL.02":("LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","LIFECYCLE.KILL.INNER.22.awaiterFailure","faultOrCancellation","awaited stage faults or cancels"),
    }
    if any(inner_edge_ids.get(edge_id)!=contract for edge_id,contract in expected_inner_edges.items()):
        raise SourceExtractionError("inner kill completed guards or safety Heal success/failure contract changed")
    completed_guard_outcomes={
        inner_edge_ids["LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED"][1],
        inner_edge_ids["LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED"][1],
    }
    death_nodes={"LIFECYCLE.KILL.INNER.04.zeroHp","LIFECYCLE.KILL.INNER.05.beforeDeath","LIFECYCLE.KILL.INNER.08.died"}
    if completed_guard_outcomes & set(inner_node_ids) or any(row["from"] in completed_guard_outcomes and row["to"] in death_nodes for row in inner["edges"]):
        raise SourceExtractionError("completed inner kill guard reaches HP or death hooks")
    victory=value["combatTermination"]["victoryGraph"]
    victory_edge_ids={row["edgeId"]:(row["from"],row["to"],row["kind"]) for row in victory["edges"]}
    if victory_edge_ids.get("LIFECYCLE.COMBAT.VICTORY.EDGE.02")!=("LIFECYCLE.COMBAT.VICTORY.02.revivePlayers","LIFECYCLE.COMBAT.VICTORY.03.afterCombatEnd","awaitSuccess") or victory_edge_ids.get("LIFECYCLE.COMBAT.VICTORY.EDGE.REVIVE_FAIL")!=("LIFECYCLE.COMBAT.VICTORY.02.revivePlayers","LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation"):
        raise SourceExtractionError("victory player-revive success/failure contract changed")
    if inner.get("directCheckWinCondition") is not False or inner.get("deadBodyEntryShortCircuit") is not False:
        raise SourceExtractionError("inner kill invented a win check or dead-body short circuit")
    if inner.get("forceContract") != 'entry guards complete regardless of force; after they pass, force bypasses only out-of-combat multiplayer player safety healing and ShouldDie/prevention; HP zeroing, BeforeDeath, Died, animation, AfterDeath, removal, Power cleanup, and player cleanup remain':
        raise SourceExtractionError("force bypass/entry-guard boundary changed")
    if value["removal"].get("escapeDeathHooks")!=[] or value["removal"].get("escapeResultEnum") is not None:
        raise SourceExtractionError("escape invented death hooks or a result enum")
    if value["combatTermination"].get("killDirectWinCheck") is not False or value["combatTermination"].get("resultEnum") is not None:
        raise SourceExtractionError("combat termination invented Kill win check/result enum")
    den=value["sourceDenominators"]
    expected={"commandDeclarations":4,"commandPhysicalBodies":4,"killCallSites":21,"escapeCallSites":3,
              "dispatchMethods":6,"listenerRegistryLogicalMethods":3,"listenerRegistryPhysicalBodies":3,
              "removalMethods":4,"terminationDeclarations":4,"terminationPhysicalBodies":4,
              "terminationSupportMethods":3,"centralizedCheckCallSites":14,"runtimeBoundaries":7,
              "dependencies":7,"invocations":707,"semanticNodes":59}
    if den!=expected: raise SourceExtractionError("lifecycle source denominators changed")
    declarations=value["api"]["commandDeclarations"]
    parameter_rows=[[p["name"] for p in row["parameters"]] for row in declarations]
    if parameter_rows!=[["creature","force"],["creatures","force"],["creature","force","recursion"],["creature","removeCreatureNode"]]:
        raise SourceExtractionError("lifecycle command parameter names/order changed")
    sites=value["api"]["commandCallSites"]
    if len(sites)!=24 or len({row["callSiteId"] for row in sites})!=24:
        raise SourceExtractionError("lifecycle command call-site closure changed")
    for row in sites:
        params=[arg["parameter"] for arg in row["arguments"]]
        if ("::Kill sig:" in row["target"] or "::KillWithoutCheckingWinCondition sig:" in row["target"]) and "force" not in params:
            raise SourceExtractionError("Kill call site omitted force stack argument")
    encounter=[row for row in sites if row["classification"]=="currentEncounterMove"]
    if len(encounter)!=2 or any(next(arg for arg in row["arguments"] if arg["parameter"]=="force").get("value") is not False for row in encounter):
        raise SourceExtractionError("Gas Bomb/Waterfall force:false contract changed")
    if len(value["centralizedCheckCallSites"])!=14 or any("CreatureCmd+<Kill" in row["caller"] for row in value["centralizedCheckCallSites"]):
        raise SourceExtractionError("centralized win-check closure changed")
    if any(row.get("classification")=="ignored" for row in value["runtimeBoundaries"]):
        raise SourceExtractionError("broad ignored lifecycle runtime boundary")
    census=value["invocationCensus"]; decisions=census.get("decisions",[]); summary=census.get("summary",{})
    if len(decisions)!=707 or summary.get("denominator")!=707 or summary.get("resolved")!=707 or summary.get("unresolved")!=0:
        raise SourceExtractionError("lifecycle invocation classification denominator changed")
    if len({row.get("invocationId") for row in decisions})!=707 or any(row.get("classification")=="ignored" for row in decisions):
        raise SourceExtractionError("lifecycle invocation classification is duplicate or ignored")
    if {row["status"] for row in value["dependencies"]}!={"sourceComplete","pendingE2d2b","pendingE2d2c","pendingE2d2d"}:
        raise SourceExtractionError("lifecycle dependencies were silently resolved/omitted")
    dig=value["digests"]
    expected_dig={
        "callSiteOrderingSha256":witness_sha256([(row["caller"],row["instructionIndex"],row["target"]) for row in sites]),
        "coreSemanticsSha256":witness_sha256({k:value[k] for k in ("core","dispatch","listenerRegistry","removal","combatTermination")}),
        "dependencySha256":witness_sha256(value["dependencies"]),
        "methodClosureSha256":witness_sha256(sorted(_BODY_PINS.items())),
        "invocationOrderingSha256":witness_sha256([(row["caller"],row["instructionIndex"],row["callee"],row["classification"]) for row in decisions]),
    }
    if dig!=expected_dig: raise SourceExtractionError("lifecycle canonical digest mismatch")
