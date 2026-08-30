"""Fail-closed linked-event script extraction for the E2c2a source slice.

Discovery starts exclusively from E1 placement.eventLinkage.  The module reads
CLI metadata/CIL and never loads or executes the assembly.  Architect is left as
an explicit later-slice dependency.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import re
from typing import Any, Iterable, Mapping

from .canonical import witness_sha256
from .cil_eval import CilDataFlow, Invocation, SymbolicValue
from .errors import SourceExtractionError

_EVENT_NS = "MegaCrit.Sts2.Core.Models.Events."
_TRANSITION = "MegaCrit.Sts2.Core.Models.EventModel::EnterCombatWithoutExitingEvent"
_OPTION_CTOR = "MegaCrit.Sts2.Core.Events.EventOption::.ctor"
_REWARD_PREFIX = "MegaCrit.Sts2.Core.Rewards."
_ARCHITECT = "EVENT.THE_ARCHITECT"
# Discovered from the pinned v0.111.0 slice after all explicit semantic
# normalizers run. This recognizes an exact residual declaration vocabulary;
# it is not a prefix ignore and any added/removed call fails.
_BOUNDED_PLUMBING_VOCABULARY_SHA256 = "660a142439d32f8e921e2df4de14bf29d6e22d8140718d9662d2e87cf0d34666"
_BOUNDED_PLUMBING_VOCABULARY_SIZE = 496

# Exact external gameplay/presentation boundaries seen in this bounded slice.
# Anything under Commands that is not listed is an extraction failure.
_GAMEPLAY_CALLS = {
    "MegaCrit.Sts2.Core.Commands.CardCmd::Upgrade": "upgradeCard",
    "MegaCrit.Sts2.Core.Commands.CardPileCmd::AddToDeck": "addCardToDeck",
    "MegaCrit.Sts2.Core.Commands.CardPileCmd::AddCurseToDeck": "addCurseToDeck",
    "MegaCrit.Sts2.Core.Commands.CreatureCmd::Damage": "damage",
    "MegaCrit.Sts2.Core.Commands.CreatureCmd::Heal": "heal",
    "MegaCrit.Sts2.Core.Commands.PlayerCmd::GainGold": "gainGold",
    "MegaCrit.Sts2.Core.Commands.PlayerCmd::MimicRestSiteHeal": "restSiteHeal",
    "MegaCrit.Sts2.Core.Commands.RewardsCmd::OfferCustom": "offerRewards",
}
_PRESENTATION_CALLS = {
    "MegaCrit.Sts2.Core.Commands.Cmd::CustomScaledWait", "MegaCrit.Sts2.Core.Commands.Cmd::Wait",
    "MegaCrit.Sts2.Core.Commands.SfxCmd::Play", "MegaCrit.Sts2.Core.Commands.SfxCmd::PlayLoop",
    "MegaCrit.Sts2.Core.Commands.SfxCmd::StopLoop", "MegaCrit.Sts2.Core.Commands.VfxCmd::Play",
    "MegaCrit.Sts2.Core.Commands.VfxCmd::PlayOnCreatureCenter",
    "MegaCrit.Sts2.Core.Commands.VfxCmd::PlayNonCombatVfx",
    "MegaCrit.Sts2.Core.Commands.CreatureCmd::TriggerAnim",
    "MegaCrit.Sts2.Core.Audio.Debug.NDebugAudioManager::Play",
    "MegaCrit.Sts2.Core.Audio.Debug.NDebugAudioManager::Stop",
    "MegaCrit.Sts2.Core.Nodes.NGame::ScreenRumble",
}


def _method(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in (
        "assemblySha256", "cilInstructionsSha256", "metadataSignature",
        "methodBodySha256", "normalizedInstructionsSha256", "symbolSignature",
    )}


def _base(symbol: str) -> str:
    return symbol.split(" sig:", 1)[0]


def _generic(symbol: str) -> str | None:
    match = re.search(r" generic:([^ ]+)", symbol)
    return match.group(1) if match else None


def _simple(symbol: str) -> str:
    return _base(symbol).rsplit(".", 1)[-1].split("::", 1)[0]


def _slug(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value).upper()).strip("_")


def _find_record(assembly: Any, symbol: str, sha: str) -> tuple[int, dict[str, Any]]:
    matches = [i for i in range(1, len(assembly.md.MethodDef.rows) + 1) if assembly.method_symbol(i) == symbol]
    if len(matches) != 1:
        raise SourceExtractionError(f"event script method root {symbol!r} matched {len(matches)} declarations")
    return matches[0], assembly.method_record(matches[0], sha)


def _owner_records(assembly: Any, owner: str, sha: str) -> list[tuple[int, dict[str, Any]]]:
    rows=[]
    for ti, physical in assembly.type_names.items():
        if physical != owner and not physical.startswith(owner + "+"):
            continue
        for mi in assembly.md.TypeDef.rows[ti-1].MethodList:
            if mi.row.Rva:
                rows.append((mi.row_index, assembly.method_record(mi.row_index, sha)))
    return sorted(rows, key=lambda row: row[1]["symbolSignature"])


def _effective(assembly: Any, owner: str, name: str, sha: str, *, optional: bool=False) -> tuple[str, dict[str, Any]] | None:
    current=owner; seen=set()
    while current:
        if current in seen: raise SourceExtractionError(f"event script inheritance cycle at {current}")
        seen.add(current)
        methods=assembly.find_methods(current,name)
        methods=[m for m in methods if assembly.md.MethodDef.rows[m-1].Rva]
        if len(methods)>1: raise SourceExtractionError(f"ambiguous effective event method {owner}::{name}")
        if methods:
            return current, assembly.method_record(methods[0],sha)
        current=assembly.base_by_type.get(current)
    if optional:return None
    raise SourceExtractionError(f"missing effective event method {owner}::{name}")


def _delegate_target(instructions: list[Mapping[str, Any]], index: int) -> tuple[str, int]:
    start=max(0,index-16)
    candidates=[(i,str(instructions[i].get("operand"))) for i in range(start,index)
                if instructions[i]["opcode"] in {"ldftn","ldvirtftn"}]
    if not candidates: raise SourceExtractionError(f"event option at instruction {index} has no delegate target")
    # The nearest function pointer belongs to the delegate constructor.  Reject
    # another pointer after it rather than selecting by event name.
    target_i,target=candidates[-1]
    if not target or "::" not in target: raise SourceExtractionError(f"unresolved event option delegate at {index}")
    return target,target_i


def _options(owner: str, event_id: str, records: list[tuple[int,dict[str,Any]]]) -> list[dict[str,Any]]:
    output=[]
    for _,record in records:
        ins=record["instructions"]
        for i,item in enumerate(ins):
            if item["opcode"]!="newobj" or not str(item.get("operand","")).startswith(_OPTION_CTOR): continue
            target,target_i=_delegate_target(ins,i)
            keys=[str(ins[j].get("operand"))[7:] for j in range(target_i+1,i)
                  if ins[j]["opcode"]=="ldstr" and str(ins[j].get("operand","")).startswith("string:")]
            if len(keys)!=1: raise SourceExtractionError(f"event option at {record['symbolSignature']}:{i} has {len(keys)} localization keys")
            key=keys[0]
            stage_match=re.search(r"\.pages\.([^.]+)\.options\.",key)
            if not stage_match: raise SourceExtractionError(f"event option localization does not identify a stage: {key}")
            callback_base=_base(target)
            callback_matches=[r for _,r in records if _base(r["symbolSignature"])==callback_base]
            if len(callback_matches)!=1: raise SourceExtractionError(f"event option callback {target} matched {len(callback_matches)} physical methods")
            oid=f"EVENT_OPTION.{event_id.removeprefix('EVENT.')}/{_slug(key.rsplit('.',1)[-1])}"
            if any(x["optionId"]==oid for x in output): raise SourceExtractionError(f"duplicate event option identity {oid}")
            after=ins[i+1:min(len(ins),i+6)]
            damage=next((str(x.get("operand")) for x in after if "EventOption::ThatDoesDamage" in str(x.get("operand"))),None)
            row={
                "callback": {"receiver":"eventInstance", "signature":target.split(" sig:",1)[1], "target":target},
                "constructionIndex":i, "constructionMethod":_method(record),
                "enabledWhen":{"kind":"constant","value":True,"valueType":"boolean"},
                "eventId":event_id, "localizationKey":key, "optionId":oid,
                "orderInMethod":sum(1 for x in output if x["constructionMethod"]["symbolSignature"]==record["symbolSignature"]),
                "stage":stage_match.group(1),
                "visibleWhen":{"kind":"constant","value":True,"valueType":"boolean"},
            }
            if damage:
                row["displayEffect"]={"amount":{"kind":"runtimeInput","name":"event.dynamicVars.HpLoss.baseValue","valueType":"decimal"},"kind":"damagePreview"}
            output.append(row)
    return sorted(output,key=lambda x:(x["eventId"],x["constructionMethod"]["symbolSignature"],x["constructionIndex"]))


def _bool(value: SymbolicValue, where: str) -> bool:
    if value.kind!="constant" or value.data not in (0,1): raise SourceExtractionError(f"{where}: unresolved Boolean stack argument ({value.kind})")
    return bool(value.data)


def _encounter_from(inv: Invocation) -> tuple[str,int]:
    generic=_generic(inv.symbol)
    if generic: return generic,0
    candidates=[]
    for n,arg in enumerate(inv.arguments):
        if arg.kind=="call" and isinstance(arg.data,str) and "ModelDb::Encounter" in arg.data:
            typ=_generic(arg.data)
            if typ:candidates.append((typ,n))
    if len(candidates)!=1: raise SourceExtractionError(f"transition at {inv.index} has {len(candidates)} decoded encounter arguments")
    return candidates[0]


def _reward_rows(record: Mapping[str,Any], call_index: int, reward_value: SymbolicValue) -> list[dict[str,Any]]:
    if reward_value.kind=="call" and isinstance(reward_value.data,str) and reward_value.data.startswith("System.Array::Empty"):
        if _generic(reward_value.data)!="MegaCrit.Sts2.Core.Rewards.Reward": raise SourceExtractionError("transition used unknown empty reward element type")
        return []
    rows=[]; ins=record["instructions"]
    for i,item in enumerate(ins[:call_index]):
        symbol=str(item.get("operand", ""))
        if item["opcode"]!="newobj" or not symbol.startswith(_REWARD_PREFIX) or "Reward::.ctor" not in symbol: continue
        kind=_base(symbol).split("::",1)[0].rsplit(".",1)[-1]
        preceding=[str(x.get("operand","")) for x in ins[max(0,i-10):i]]
        models=[_generic(x) for x in preceding if _generic(x) and ("ModelDb::" in x or "CreateCard" in x)]
        contract:dict[str,Any]
        if models:
            contract={"kind":"fixedModel","sourceType":models[-1]}
        elif any("MerchantRelicEntry::get_Model" in x for x in preceding):
            contract={"kind":"runtimeModel","name":"event.inventory.unstockedRelic.model"}
        elif kind in {"PotionReward","RelicReward"}:
            contract={"kind":"runtimePull","rewardKind":kind}
        else:
            raise SourceExtractionError(f"unknown reward model contract for {symbol} at {record['symbolSignature']}:{i}")
        condition={"kind":"constant","value":True,"valueType":"boolean"}
        if contract["kind"]=="runtimeModel":
            condition={"kind":"allOf","operands":[
                {"kind":"comparison","operator":"greaterThan","left":{"kind":"runtimeInput","name":"run.playerCount","valueType":"integer"},"right":{"kind":"constant","value":1,"valueType":"integer"},"valueType":"boolean"},
                {"kind":"runtimeInput","name":"event.inventory.entry.isUnstocked","valueType":"boolean"}],"valueType":"boolean"}
        rows.append({"condition":condition,"constructionIndex":i,"model":contract,"rewardType":kind})
    if not rows: raise SourceExtractionError(f"non-empty transition reward argument has no normalized constructors in {record['symbolSignature']}")
    return rows


def _transition(record: Mapping[str,Any], event_id: str, expected: Mapping[str,Any]) -> dict[str,Any]:
    calls=CilDataFlow(record["instructions"]).run()
    found=[x for x in calls.values() if x.symbol.startswith(_TRANSITION)]
    if len(found)!=1: raise SourceExtractionError(f"{record['symbolSignature']} has {len(found)} event combat transition calls")
    inv=found[0]; encounter_type,enc_arg=_encounter_from(inv)
    generic=_generic(inv.symbol)
    if generic:
        if len(inv.arguments)!=2: raise SourceExtractionError("generic event transition overload parameter count changed")
        rewards_i,resume_i=0,1
    else:
        if len(inv.arguments)!=3 or enc_arg!=0: raise SourceExtractionError("non-generic event transition overload parameter order changed")
        rewards_i,resume_i=1,2
    encounter="ENCOUNTER."+_slug(encounter_type.rsplit(".",1)[-1])
    if encounter!=expected["canonicalEncounter"]: raise SourceExtractionError(f"transition encounter {encounter} does not join E1 {expected['canonicalEncounter']}")
    e1_methods=[x["method"] for x in expected["linkMechanisms"] if x["kind"]=="eventCombatTransition"]
    if len(e1_methods)!=1 or e1_methods[0]!=_method(record): raise SourceExtractionError(f"transition method does not exactly reuse E1 provenance: {record['symbolSignature']}")
    resume=_bool(inv.arguments[resume_i],f"{record['symbolSignature']} transition")
    return {
        "addedRewards":_reward_rows(record,inv.index,inv.arguments[rewards_i]),
        "callbackMethod":_method(record), "canonicalEncounter":encounter,
        "e1EventLinkRef":f"SOURCE.EVENT_LINK.{encounter}", "eventId":event_id,
        "instructionIndex":inv.index, "overload":{"genericEncounter":bool(generic),"symbolSignature":inv.symbol},
        "resume":{"mode":"resumeParentEvent" if resume else "proceedToMapAfterCombat","shouldResume":resume},
        "transitionId":f"EVENT_TRANSITION.{event_id.removeprefix('EVENT.')}/{encounter.removeprefix('ENCOUNTER.')}",
    }


def _availability(owner: str, event_id: str, assembly: Any, sha: str) -> dict[str,Any]:
    row=_effective(assembly,owner,"IsAllowed",sha,optional=True)
    if row is None:
        return {"eventId":event_id,"expression":{"kind":"constant","value":True,"valueType":"boolean"},"method":None}
    physical,record=row; ops=[(x["opcode"],str(x.get("operand",""))) for x in record["instructions"]]
    simple=owner.rsplit(".",1)[-1]
    if simple=="DenseVegetation":
        required=["Creature::get_CurrentHp","DynamicVarSet::get_HpLoss","DynamicVar::get_BaseValue","Decimal::op_LessThanOrEqual"]
        if any(not any(r in operand for _,operand in ops) for r in required): raise SourceExtractionError("Dense Vegetation eligibility lost dynamic HpLoss comparison")
        expr={"kind":"anyOf","operands":[
            {"kind":"comparison","operator":"equal","left":{"kind":"runtimeInput","name":"run.playerCount","valueType":"integer"},"right":{"kind":"constant","value":1,"valueType":"integer"},"valueType":"boolean"},
            {"kind":"allPlayers","predicate":{"kind":"comparison","operator":"greaterThan","left":{"kind":"runtimeInput","name":"player.currentHp","valueType":"integer"},"right":{"kind":"runtimeInput","name":"event.dynamicVars.HpLoss.baseValue","valueType":"decimal"},"valueType":"boolean"},"valueType":"boolean"}],"valueType":"boolean"}
    elif simple=="FakeMerchant":
        if not any("CurrentActIndex" in x for _,x in ops) or not any("Enumerable::All" in x for _,x in ops): raise SourceExtractionError("Fake Merchant eligibility shape changed")
        expr={"kind":"allOf","operands":[
            {"kind":"comparison","operator":"greaterThanOrEqual","left":{"kind":"runtimeInput","name":"run.currentActIndex","valueType":"integer"},"right":{"kind":"constant","value":1,"valueType":"integer"},"valueType":"boolean"},
            {"kind":"comparison","operator":"lessThanOrEqual","left":{"kind":"runtimeInput","name":"run.playerCount","valueType":"integer"},"right":{"kind":"constant","value":1,"valueType":"integer"},"valueType":"boolean"},
            {"kind":"allPlayers","predicate":{"kind":"anyOf","operands":[
                {"kind":"comparison","operator":"greaterThanOrEqual","left":{"kind":"runtimeInput","name":"player.gold","valueType":"integer"},"right":{"kind":"constant","value":100,"valueType":"integer"},"valueType":"boolean"},
                {"kind":"anyPotion","predicate":{"kind":"typeTest","input":{"kind":"runtimeInput","name":"player.potion","valueType":"object"},"sourceType":"MegaCrit.Sts2.Core.Models.Potions.FoulPotion","valueType":"boolean"},"valueType":"boolean"}],"valueType":"boolean"},"valueType":"boolean"}],"valueType":"boolean"}
    elif simple=="PunchOff":
        constants=[x for x in record["instructions"] if x["opcode"].startswith("ldc.i4")]
        six=next((6 for x in constants if x["opcode"]=="ldc.i4.6"),None)
        if six is None or not any(x["opcode"]=="clt" for x in record["instructions"]): raise SourceExtractionError("Punch Off eligibility comparison changed")
        expr={"kind":"comparison","operator":"greaterThanOrEqual","left":{"kind":"runtimeInput","name":"run.totalFloor","valueType":"integer"},"right":{"kind":"constant","value":six,"valueType":"integer"},"valueType":"boolean"}
    else:
        # Absence of a specialized predicate parser is explicit rather than a guessed formula.
        expr={"kind":"sourcePredicate","methodBodySha256":record["methodBodySha256"],"valueType":"boolean"}
    return {"eventId":event_id,"expression":expr,"method":_method(record),"physicalOwner":physical}


def _display_scaling(owner: str, event_id: str, records: list[tuple[int,dict[str,Any]]]) -> list[dict[str,Any]]:
    if not owner.endswith(".BattlewornDummy"): return []
    roots=[r for _,r in records if _base(r["symbolSignature"])==owner+"::GenerateInitialOptions"]
    if len(roots)!=1: raise SourceExtractionError("Battle display scaling root ambiguity")
    record=roots[0]; calls=CilDataFlow(record["instructions"]).run()
    rows=[]
    for inv in calls.values():
        if not inv.symbol.startswith("MegaCrit.Sts2.Core.Entities.Creatures.Creature::ScaleHpForMultiplayer"):continue
        if len(inv.arguments)!=4: raise SourceExtractionError("Battle display scaling signature changed")
        first=inv.arguments[0]
        models=[]
        def walk(v:SymbolicValue)->None:
            if isinstance(v.data,str) and "ModelDb::Monster" in v.data and _generic(v.data):models.append(_generic(v.data))
            for x in v.operands:walk(x)
        walk(first)
        encounter=inv.arguments[1]
        if len(models)!=1 or encounter.kind!="call" or not isinstance(encounter.data,str) or not _generic(encounter.data):
            raise SourceExtractionError(f"Battle display scaling arguments unresolved at {inv.index}")
        # The destination dynamic-var key is the nearest preceding string load.
        keys=[str(x.get("operand"))[7:] for x in record["instructions"][:inv.index] if x["opcode"]=="ldstr" and str(x.get("operand","")).startswith("string:Setting")]
        if not keys: raise SourceExtractionError("Battle display scaling destination key unresolved")
        rows.append({"destination":f"event.dynamicVars.{keys[-1]}.baseValue","eventId":event_id,
                     "formulaRef":"FORMULA.HP_MULTIPLAYER_SCALE","instructionIndex":inv.index,
                     "sourceEncounterType":_generic(encounter.data),"sourceMonsterType":models[0]})
    if len(rows)!=3: raise SourceExtractionError(f"Battle display scaling discovered {len(rows)} calls")
    return rows


def _state_contracts(event_id: str, records: list[tuple[int,dict[str,Any]]]) -> list[dict[str,Any]]:
    symbols=[str(x.get("operand","")) for _,r in records for x in r["instructions"]]
    rows=[]
    for suffix,name,typ in (("RanOutOfTime","encounter.RanOutOfTime","boolean"),("StartedFight","event.StartedFight","boolean")):
        if any(suffix in x for x in symbols): rows.append({"domain":[False,True],"eventId":event_id,"name":name,"valueType":typ})
    if any("get_Inventory" in x for x in symbols): rows.append({"domain":"runtimeMerchantInventory","eventId":event_id,"name":"event.Inventory","valueType":"object"})
    if any("CancellationTokenSource" in x for x in symbols): rows.append({"domain":"activeOrCancelled","eventId":event_id,"name":"event.presentationCancellation","valueType":"state"})
    if event_id=="EVENT.BATTLEWORN_DUMMY" and any("ScaleHpForMultiplayer" in x for x in symbols):
        rows.append({"domain":"sourceEncounterAndMonsterHpAtRuntime","eventId":event_id,"formulaRef":"FORMULA.HP_MULTIPLAYER_SCALE","name":"event.displayHpScalingInputs","valueType":"runtimeContract"})
    if event_id=="EVENT.DENSE_VEGETATION" and any("MimicRestSiteHeal" in x for x in symbols):
        rows.append({"domain":"ownerAndFalseRestFlag","eventId":event_id,"formulaRef":"FORMULA.REST_SITE_HEAL_AMOUNT","name":"event.restHealInputs","valueType":"runtimeContract"})
    if event_id=="EVENT.FAKE_MERCHANT":
        if any("UnstableShuffle" in x for x in symbols):
            rows.append({"domain":"eventRngShuffleTakeAndStockState","eventId":event_id,"name":"event.inventoryRngAndStock","valueType":"runtimeContract"})
        rows.append({"domain":"combatOrMerchantOrFakeMerchantRoomWithOpenTargetNode","eventId":event_id,"name":"foulPotion.usabilityAndTarget","valueType":"runtimeContract"})
        rows.append({"domain":"everyRunPlayerMutableFakeMerchantEvent","eventId":event_id,"name":"foulPotion.eventInstanceDispatch","valueType":"runtimeContract"})
    if event_id=="EVENT.PUNCH_OFF" and any("add_" in x or "remove_" in x for x in symbols):
        rows.append({"domain":"subscribedUntilRoomExitOrCancellation","eventId":event_id,"name":"event.presentationSubscription","valueType":"runtimeContract"})
    return rows


def _effects(event_id: str, records: list[tuple[int,dict[str,Any]]]) -> list[dict[str,Any]]:
    rows=[]
    for _,record in records:
        for i,item in enumerate(record["instructions"]):
            symbol=str(item.get("operand", "")); base=_base(symbol)
            kind=_GAMEPLAY_CALLS.get(base)
            if kind:
                effect={"effectId":f"EVENT_EFFECT.{event_id.removeprefix('EVENT.')}/{len(rows):03d}","eventId":event_id,"instructionIndex":i,
                        "kind":kind,"method":_method(record),"recipient":"sourceCallReceiverOrArgument","sourceSymbol":symbol}
                if kind=="damage" and event_id=="EVENT.DENSE_VEGETATION":
                    effect.update({"amount":{"kind":"runtimeInput","name":"event.dynamicVars.HpLoss.baseValue","valueType":"decimal"},"recipient":"event.owner.creature"})
                elif kind=="gainGold":
                    effect.update({"amount":{"kind":"runtimeInput","name":"event.dynamicVars.Gold.baseValue","valueType":"decimal"},"recipient":"event.owner"})
                elif kind=="restSiteHeal":
                    effect.update({"formulaRef":"FORMULA.REST_SITE_HEAL_AMOUNT","mimicRestFlag":False,"recipient":"event.owner"})
                elif kind=="addCurseToDeck":
                    effect.update({"model":"CARD.INJURY","recipient":"event.owner"})
                elif kind=="upgradeCard":
                    effect.update({"maximum":2,"previewStyle":1,"recipient":"runtimeSelectedUpgradableCards"})
                elif kind=="offerRewards":
                    effect.update({"condition":"rewardListNonEmpty","recipient":"event.owner"})
                rows.append(effect)
            if (event_id=="EVENT.PUNCH_OFF" and "PunchOff+<Nab>" in record["symbolSignature"]
                    and item["opcode"]=="newobj" and base=="MegaCrit.Sts2.Core.Rewards.RelicReward::.ctor"):
                rows.append({"effectId":f"EVENT_EFFECT.{event_id.removeprefix('EVENT.')}/{len(rows):03d}","eventId":event_id,
                             "instructionIndex":i,"kind":"constructReward","method":_method(record),
                             "recipient":"event.owner","reward":{"model":{"kind":"runtimePull","rewardKind":"RelicReward"},"rewardType":"RelicReward"},
                             "sourceSymbol":symbol})
            if ".Models.Events." in base and "::set_" in base and any(x in base for x in ("StartedFight","EventFinished")):
                rows.append({"effectId":f"EVENT_EFFECT.{event_id.removeprefix('EVENT.')}/{len(rows):03d}","eventId":event_id,"instructionIndex":i,
                             "kind":"stateWrite","method":_method(record),"recipient":"eventInstance","sourceSymbol":symbol,
                             "value":True if "StartedFight" in base else "sourceArgument"})
    return rows


def _method_rows(event_id: str, owner: str, records: list[tuple[int,dict[str,Any]]]) -> list[dict[str,Any]]:
    return [{"effectiveOwner":owner,"eventId":event_id,"method":_method(r),"physicalOwner":r["symbolSignature"].split("::",1)[0]}
            for _,r in records]


def _framework_methods(assembly: Any, sha: str) -> list[dict[str, Any]]:
    roots = {
        "MegaCrit.Sts2.Core.Rooms.EventRoom": {"EnterInternal", "Resume", "Exit"},
        "MegaCrit.Sts2.Core.Multiplayer.Game.EventSynchronizer": {
            "BeginEvent", "HandleVotedForSharedEventOptionMessage", "PlayerVotedForSharedOptionIndex",
            "ChooseSharedEventOption", "HandleSharedEventOptionChosenMessage", "HandleEventOptionChosenMessage",
            "ChooseLocalOption", "ChooseOptionForSharedEvent", "ChooseOptionForEvent", "SaveEventOptionToHistory",
            "ClearPlayerVotes", "ResumeEvents", "BeforeExitingRoom", "AwaitPendingOptionTasks",
        },
        "MegaCrit.Sts2.Core.Models.EventModel": {
            "BeginEvent", "SetInitialEventState", "GenerateInitialOptionsWrapper",
            "BeforeEventStarted", "AfterEventStarted", "EnsureCleanup",
            "set_IsFinished", "SetEventFinished", "SetEventState",
            "EnterCombatWithoutExitingEvent",
        },
        "MegaCrit.Sts2.Core.Events.EventOption": {"Chosen"},
        "MegaCrit.Sts2.Core.Multiplayer.Game.EventCombatSynchronizer": {
            "InitializeForEvent", "ReadyToEnterCombat", "EnterCombat", "ResetState",
        },
        "MegaCrit.Sts2.Core.Nodes.Rooms.NEventRoom": {
            "SetupLayout", "SetOptions", "OptionButtonClicked", "BeforeOptionChosen", "OnEnteringEventCombat", "Proceed",
        },
        "MegaCrit.Sts2.Core.Nodes.Events.NEventLayout": {"SetEvent", "BeforeSharedOptionChosen"},
        "MegaCrit.Sts2.Core.Nodes.Events.NCombatEventLayout": {"SetEvent", "SetCombatRoomNode"},
        "MegaCrit.Sts2.Core.Runs.RunManager": {"ProceedFromTerminalRewardsScreen"},
    }
    output=[]
    for owner,names in sorted(roots.items()):
        for name in sorted(names):
            matches=[m for m in assembly.find_methods(owner,name) if assembly.md.MethodDef.rows[m-1].Rva]
            expected=2 if owner.endswith(".EventModel") and name=="EnterCombatWithoutExitingEvent" else 1
            if len(matches)!=expected:
                raise SourceExtractionError(f"common event framework root {owner}::{name} matched {len(matches)}, expected {expected}")
            for mi in matches:
                record=assembly.method_record(mi,sha)
                output.append({"edgeRole":name,"method":_method(record),"owner":owner})
                # Include the compiler-generated MoveNext body for this exact
                # root when present; no prefix-wide state-machine ingestion.
                prefix=owner+"+<"+name+">d__"
                nested=[]
                for ti,physical in assembly.type_names.items():
                    if not physical.startswith(prefix):continue
                    nested.extend(m.row_index for m in assembly.md.TypeDef.rows[ti-1].MethodList
                                  if m.row.Rva and str(m.row.Name)=="MoveNext")
                if len(nested)>1:raise SourceExtractionError(f"ambiguous framework async body for {owner}::{name}")
                if nested:
                    output.append({"edgeRole":name+"AsyncBody","method":_method(assembly.method_record(nested[0],sha)),"owner":owner})
    return sorted(output,key=lambda x:x["method"]["symbolSignature"])


def _resume_outcomes(assembly: Any, sha: str, transitions: list[dict[str,Any]],
                     records_by_event: Mapping[str,list[tuple[int,dict[str,Any]]]]) -> list[dict[str,Any]]:
    rows=[]
    for transition in transitions:
        event_id=transition["eventId"]
        if not transition["resume"]["shouldResume"]:
            rows.append({"eventId":event_id,"outcomeId":"EVENT_OUTCOME."+transition["transitionId"].removeprefix("EVENT_TRANSITION."),
                         "classification":"standardCombatOutcomeBoundary","transitionRef":transition["transitionId"],
                         "dependencyRefs":["LIFECYCLE.COMBAT.EVENT_TERMINAL_RESULT"]})
            continue
        # Resolve directly from the event owner if the generated-body lookup above
        # did not produce a declaration owner.
        wrappers=[r for _,r in records_by_event[event_id] if _base(r["symbolSignature"]).endswith("BattlewornDummy::Resume")]
        bodies=[r for _,r in records_by_event[event_id] if "BattlewornDummy+<Resume>" in r["symbolSignature"] and "::MoveNext" in r["symbolSignature"]]
        if len(wrappers)!=1 or len(bodies)!=1:raise SourceExtractionError("Battle custom resume wrapper/body ambiguity")
        symbols=[str(x.get("operand","")) for x in bodies[0]["instructions"]]
        required=["get_RanOutOfTime","PotionReward::.ctor","CardCmd::Upgrade","RelicReward::.ctor","RewardsCmd::OfferCustom"]
        if any(not any(x in symbol for symbol in symbols) for x in required):raise SourceExtractionError("Battle custom resume semantic branch changed")
        encounter=transition["canonicalEncounter"]
        if "_V1_" in encounter:
            success={"kind":"dynamicPotionReward","selection":{"kind":"runtimeRng","name":"owner.playerRng.rewards","pool":"characterUnlockedPlusSharedUnlocked"}}
        elif "_V2_" in encounter:
            success={"kind":"upgradeCards","selection":{"kind":"runtimeSelection","name":"owner.drawPile.upgradableStableShuffleTake","maximum":2},"previewStyle":1}
        elif "_V3_" in encounter:
            success={"kind":"dynamicRelicReward","selection":{"kind":"runtimePull","name":"RelicFactory.PullNextRelicFromFront(owner)"}}
        else:raise SourceExtractionError(f"unknown Battle resume encounter variant {encounter}")
        rows.append({"eventId":event_id,"outcomeId":"EVENT_OUTCOME."+transition["transitionId"].removeprefix("EVENT_TRANSITION."),
                     "classification":"customRanOutOfTimeBranch","transitionRef":transition["transitionId"],
                     "resumeMethod":_method(wrappers[0]),"resumeBody":_method(bodies[0]),
                     "stateRead":{"name":"encounter.RanOutOfTime","valueType":"boolean"},
                     "timeout":{"eventPage":"DEFEAT","effects":[]},
                     "success":{"eventPage":"VICTORY","versionEffect":success,
                                "extraRewards":{"condition":"resultingListNonEmpty","source":"combatRoom.ExtraRewards[event.owner]"}},
                     "dependencyRefs":["LIFECYCLE.POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER.AFTER_SIDE_TURN_END",
                                       "LIFECYCLE.COMMAND.CREATURE_ESCAPE/BATTLE_FRIEND_OWNER",
                                       "LIFECYCLE.COMBAT.EVENT_TERMINAL_RESULT"]})
    return rows


def _validate_bounded_plumbing_vocabulary(decisions: Iterable[Mapping[str, Any]]) -> None:
    vocabulary=sorted({str(row["symbolSignature"]) for row in decisions
                       if row["classification"]=="sourceProvenFrameworkOrRuntimePlumbing"})
    digest=witness_sha256(vocabulary)
    if len(vocabulary)!=_BOUNDED_PLUMBING_VOCABULARY_SIZE or digest!=_BOUNDED_PLUMBING_VOCABULARY_SHA256:
        raise SourceExtractionError(
            f"unclassified event framework/runtime call vocabulary changed: {len(vocabulary)} symbols, {digest}"
        )


def extract_event_scripts(assembly: Any, assembly_sha256: str, placement: Mapping[str,Any]) -> dict[str,Any]:
    links=[deepcopy(x) for x in placement["eventLinkage"] if x["canonicalEvent"]!=_ARCHITECT]
    by_event:dict[str,list[dict[str,Any]]]=defaultdict(list)
    for row in links:by_event[row["canonicalEvent"]].append(row)
    if len(by_event)!=5 or len(links)!=7: raise SourceExtractionError(f"E2c2a roots discovered {len(by_event)} owners/{len(links)} links")
    owners=[]; options=[]; transitions=[]; contracts=[]; effects=[]; methods=[]; display=[]; records_by_event={}
    for event_id,event_links in sorted(by_event.items()):
        source_types={x["eventSourceType"] for x in event_links}
        if len(source_types)!=1: raise SourceExtractionError(f"{event_id} has ambiguous E1 owners")
        owner=next(iter(source_types)); records=_owner_records(assembly,owner,assembly_sha256)
        if not records:raise SourceExtractionError(f"no physical methods discovered for {owner}")
        records_by_event[event_id]=records
        owner_options=_options(owner,event_id,records)
        owner_transitions=[]
        for link in event_links:
            roots=[m["method"] for m in link["linkMechanisms"] if m["kind"]=="eventCombatTransition"]
            if len(roots)!=1:raise SourceExtractionError(f"{link['canonicalEncounter']} lacks one E1 transition root")
            _,record=_find_record(assembly,roots[0]["symbolSignature"],assembly_sha256)
            owner_transitions.append(_transition(record,event_id,link))
        availability=_availability(owner,event_id,assembly,assembly_sha256)
        owner_contracts=_state_contracts(event_id,records); owner_effects=_effects(event_id,records)
        owners.append({"availability":availability,"canonicalEvent":event_id,
                       "e1EncounterLinkRefs":[f"SOURCE.EVENT_LINK.{x['canonicalEncounter']}" for x in sorted(event_links,key=lambda x:x['canonicalEncounter'])],
                       "eventSourceType":owner,"optionIds":[x["optionId"] for x in owner_options],
                       "transitionIds":[x["transitionId"] for x in owner_transitions]})
        options.extend(owner_options);transitions.extend(owner_transitions);contracts.extend(owner_contracts);effects.extend(owner_effects)
        methods.extend(_method_rows(event_id,owner,records));display.extend(_display_scaling(owner,event_id,records))

    # Fake Merchant must remain potion-driven: its effective initial option root
    # is present but constructs no options, while FoulPotion dispatch reaches the
    # E1 transition state machine.
    fake=next(x for x in owners if x["canonicalEvent"]=="EVENT.FAKE_MERCHANT")
    initial=_effective(assembly,fake["eventSourceType"],"GenerateInitialOptions",assembly_sha256)
    assert initial is not None
    if any(str(x.get("operand","")).startswith(_OPTION_CTOR) for x in initial[1]["instructions"]):
        raise SourceExtractionError("Fake Merchant fight unexpectedly became option-driven")
    potion_methods=[]
    for ti,physical in assembly.type_names.items():
        if physical=="MegaCrit.Sts2.Core.Models.Potions.FoulPotion" or physical.startswith("MegaCrit.Sts2.Core.Models.Potions.FoulPotion+"):
            for mi in assembly.md.TypeDef.rows[ti-1].MethodList:
                if mi.row.Rva:potion_methods.append(assembly.method_record(mi.row_index,assembly_sha256))
    potion_symbols=[str(x.get("operand","")) for r in potion_methods for x in r["instructions"]]
    if not any("FakeMerchant::FoulPotionThrown" in x for x in potion_symbols) or not any("Task::WhenAll" in x for x in potion_symbols):
        raise SourceExtractionError("Foul Potion event-instance fan-out/await chain is incomplete")
    framework=_framework_methods(assembly,assembly_sha256)
    outcomes=_resume_outcomes(assembly,assembly_sha256,transitions,records_by_event)

    # Nodes and edges are generated only from discovered options/transitions.
    nodes=[];edges=[]
    for owner in owners:
        start=f"EVENT_NODE.{owner['canonicalEvent'].removeprefix('EVENT.')}/START";nodes.append({"eventId":owner["canonicalEvent"],"kind":"stage","nodeId":start,"order":0})
        for n,oid in enumerate(owner["optionIds"],1):
            option=next(x for x in options if x["optionId"]==oid); node="EVENT_NODE."+oid.removeprefix("EVENT_OPTION.")
            nodes.append({"eventId":owner["canonicalEvent"],"kind":"optionCallback","nodeId":node,"order":n,"successSemantics":"taskCompletionOnly","exceptionSemantics":"propagateNoSuccessEdge"})
            constructor=option["constructionMethod"]["symbolSignature"]
            predecessor=start
            if "::GenerateInitialOptions" not in constructor:
                physical=constructor.split("::",1)[0]
                generated=re.search(r"\+<([^>]+)>d__",physical)
                producer=(owner["eventSourceType"]+"::"+generated.group(1)) if generated else _base(constructor)
                candidates=[x for x in options if x["eventId"]==owner["canonicalEvent"] and _base(x["callback"]["target"])==producer]
                if len(candidates)!=1:raise SourceExtractionError(f"option stage predecessor ambiguity for {option['optionId']}")
                predecessor="EVENT_NODE."+candidates[0]["optionId"].removeprefix("EVENT_OPTION.")
            edges.append({"edgeId":f"EVENT_EDGE.{owner['canonicalEvent'].removeprefix('EVENT.')}/{len(edges):03d}","from":predecessor,"kind":"optionAvailableAfterSuccess","order":option["orderInMethod"],"to":node})
        for transition_id in owner["transitionIds"]:
            t=next(x for x in transitions if x["transitionId"]==transition_id); target="EVENT_NODE."+transition_id.removeprefix("EVENT_TRANSITION.")
            nodes.append({"eventId":owner["canonicalEvent"],"kind":"combatTransition","nodeId":target,"order":len(nodes)})
            callbacks=[x for x in options if _base(x["callback"]["target"])==_base(t["callbackMethod"]["symbolSignature"])]
            source=("EVENT_NODE."+callbacks[0]["optionId"].removeprefix("EVENT_OPTION.")) if len(callbacks)==1 else start
            edges.append({"edgeId":f"EVENT_EDGE.{owner['canonicalEvent'].removeprefix('EVENT.')}/{len(edges):03d}","from":source,"kind":"combatTransition","order":0,"to":target})

    fake_start="EVENT_NODE.FAKE_MERCHANT/START"; fake_use="EVENT_NODE.FAKE_MERCHANT/FOUL_POTION_USE"
    fake_transition="EVENT_NODE.FAKE_MERCHANT/FAKE_MERCHANT_EVENT_ENCOUNTER"
    nodes.append({"eventId":"EVENT.FAKE_MERCHANT","kind":"potionDispatch","nodeId":fake_use,"order":1,"successSemantics":"Task.WhenAll completion","exceptionSemantics":"propagateNoTransition"})
    # Replace the provisional direct transition edge with exact potion dispatch.
    edges=[x for x in edges if not (x["from"]==fake_start and x["to"]==fake_transition)]
    edges.extend([
        {"edgeId":"EVENT_EDGE.FAKE_MERCHANT/FOUL_POTION","from":fake_start,"kind":"foulPotionUse","order":0,"to":fake_use},
        {"edgeId":"EVENT_EDGE.FAKE_MERCHANT/COMBAT","from":fake_use,"kind":"eventInstanceFanOutThenCombat","order":0,"to":fake_transition},
    ])

    dependencies=[
        {"dependencyId":"LIFECYCLE.POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER.AFTER_SIDE_TURN_END","kind":"lifecycle","status":"pendingE2d2"},
        {"dependencyId":"LIFECYCLE.COMMAND.CREATURE_ESCAPE/BATTLE_FRIEND_OWNER","kind":"lifecycle","status":"pendingE2d2"},
        {"dependencyId":"LIFECYCLE.COMBAT.EVENT_TERMINAL_RESULT","kind":"lifecycle","status":"pendingE2d2"},
        {"dependencyId":"LIFECYCLE.RUN.ARCHITECT_TERMINAL","kind":"lifecycle","status":"pendingE2d2"},
        {"dependencyId":"FORMULA.REST_SITE_HEAL_AMOUNT","kind":"formula","status":"pendingE2e"},
        {"dependencyId":"FORMULA.HP_MULTIPLAYER_SCALE","kind":"formula","status":"sourceRefE2b"},
    ]
    # Closed physical call census. Calls are retained as proof only in raw data.
    decisions=[]
    local_symbols={_base(x["method"]["symbolSignature"]) for x in methods}
    census_records=[_find_record(assembly,row["method"]["symbolSignature"],assembly_sha256)[1] for row in methods]
    census_records.extend(potion_methods)
    census_records.extend(_find_record(assembly,row["method"]["symbolSignature"],assembly_sha256)[1] for row in framework)
    unique_census={r["symbolSignature"]:r for r in census_records}
    for record in unique_census.values():
        for i,item in enumerate(record["instructions"]):
            if item["opcode"] not in {"call","callvirt","newobj"}:continue
            symbol=str(item.get("operand",""));base=_base(symbol)
            if base.startswith("MegaCrit.Sts2.Core.Commands.DamageCmd::"):
                raise SourceExtractionError(f"unclassified event damage command {symbol} in {record['symbolSignature']}")
            if base.startswith("MegaCrit.Sts2.Core.Commands.") and base not in _GAMEPLAY_CALLS and base not in _PRESENTATION_CALLS:
                raise SourceExtractionError(f"unclassified event command {symbol} in {record['symbolSignature']}")
            if base in _GAMEPLAY_CALLS:classification="normalizedGameplayEffect"
            elif base in _PRESENTATION_CALLS:classification="presentationOnly"
            elif base in local_symbols:classification="traversedEventHelper"
            elif base.startswith(_OPTION_CTOR) or base.startswith(_TRANSITION) or base.startswith(_REWARD_PREFIX):classification="normalizedEventFramework"
            else:classification="sourceProvenFrameworkOrRuntimePlumbing"
            decisions.append({"classification":classification,"instructionIndex":i,"sourceMethod":record["symbolSignature"],"symbolSignature":symbol})
    decisions.sort(key=lambda x:(x["sourceMethod"],x["instructionIndex"],x["symbolSignature"]))
    _validate_bounded_plumbing_vocabulary(decisions)
    den={"owners":len(owners),"encounterScripts":len(transitions),"options":len(options),"methods":len(methods),
         "nodes":len(nodes),"edges":len(edges),"stateContracts":len(contracts),"effects":len(effects),
         "invocations":len(decisions),"dependencies":len(dependencies),"displayScalingCalls":len(display),
         "outcomes":len(outcomes),"frameworkMethods":len(framework),"supportMethods":len(potion_methods)}
    result={"owners":owners,"options":options,"transitions":transitions,"stateContracts":contracts,"effects":effects,
            "nodes":nodes,"edges":edges,"methods":methods,"displayScaling":display,"dependencies":dependencies,
            "outcomes":outcomes,"frameworkMethods":framework,
            "foulPotionDispatch":{"classification":"potionDrivenEventInstanceFanOut","methods":[_method(x) for x in potion_methods],"taskJoin":"Task.WhenAll"},
            "invocationCensus":{"decisions":decisions,"summary":{"denominator":len(decisions),"resolved":len(decisions),"unresolved":0}},
            "sourceDenominators":den}
    validate_event_scripts(result)
    return result


def validate_event_scripts(value: Any) -> None:
    if not isinstance(value,dict):raise SourceExtractionError("eventScripts must be an object")
    required={"owners","options","transitions","stateContracts","effects","nodes","edges","methods","displayScaling","dependencies","foulPotionDispatch","invocationCensus","sourceDenominators","outcomes","frameworkMethods"}
    if set(value)!=required:raise SourceExtractionError(f"eventScripts keys differ: {sorted(set(value)^required)}")
    den=value["sourceDenominators"]
    mapping={"owners":"owners","encounterScripts":"transitions","options":"options","methods":"methods","nodes":"nodes","edges":"edges","stateContracts":"stateContracts","effects":"effects","dependencies":"dependencies","displayScalingCalls":"displayScaling","outcomes":"outcomes","frameworkMethods":"frameworkMethods"}
    for d,k in mapping.items():
        if den.get(d)!=len(value[k]):raise SourceExtractionError(f"eventScripts denominator {d} is stale")
    if den.get("invocations")!=len(value["invocationCensus"]["decisions"]):raise SourceExtractionError("event script invocation denominator is stale")
    if len(value["owners"])!=5 or len(value["transitions"])!=7:raise SourceExtractionError("event script owner/link closure is incomplete")
    option_ids={x["optionId"] for x in value["options"]};transition_ids={x["transitionId"] for x in value["transitions"]}
    if len(option_ids)!=len(value["options"]) or len(transition_ids)!=7:raise SourceExtractionError("duplicate event script semantic identity")
    if any(x["canonicalEvent"]==_ARCHITECT for x in value["owners"]):raise SourceExtractionError("Architect leaked into E2c2a")
    dense=next(x for x in value["owners"] if x["canonicalEvent"]=="EVENT.DENSE_VEGETATION")
    if "event.dynamicVars.HpLoss.baseValue" not in repr(dense["availability"]["expression"]):raise SourceExtractionError("Dense HpLoss was flattened or omitted")
    for row in value["transitions"]:
        if type(row["resume"]["shouldResume"]) is not bool or not row["overload"]["symbolSignature"].startswith(_TRANSITION):raise SourceExtractionError("transition semantic arguments are incomplete")
    if len(value["outcomes"])!=7 or {x["transitionRef"] for x in value["outcomes"]}!=transition_ids:
        raise SourceExtractionError("event transition-to-outcome closure is incomplete")
    battle=[x for x in value["transitions"] if x["eventId"]=="EVENT.BATTLEWORN_DUMMY"]
    if len(battle)!=3 or any(x["addedRewards"] or x["resume"]["shouldResume"] is not True for x in battle):
        raise SourceExtractionError("Battle transition arguments are not independently closed")
    nonbattle=[x for x in value["transitions"] if x["eventId"]!="EVENT.BATTLEWORN_DUMMY"]
    if len(nonbattle)!=4 or any(x["resume"]["shouldResume"] is not False for x in nonbattle):
        raise SourceExtractionError("standard event transition resume arguments are incomplete")
    if len(value["frameworkMethods"])!=value["sourceDenominators"]["frameworkMethods"]:
        raise SourceExtractionError("common event framework closure is incomplete")
