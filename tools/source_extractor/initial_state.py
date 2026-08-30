"""Fail-closed extraction of intrinsic initial creature gameplay state.

The family starts at every current encounter generator, follows explicit model
construction/defaults, resolves the effective ``AfterAddedToRoom`` method for
all current reachable monsters, and closes immediately applicable Power hooks.
It reads CLI metadata/CIL only; no shipped code is loaded or executed.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy
import re
from typing import TYPE_CHECKING, Any, Iterable, Mapping, Sequence

from .ast import validate_expression
from .behavior import (
    _async_map,
    _model_from_values,
    _slice_for_invocation,
    _source_target,
)
from .canonical import slugify_ascii_type_name, witness_sha256
from .cil_eval import (
    CilDataFlow,
    Invocation,
    SymbolicValue,
    decode_method_signature,
    ensure_resolved,
    value_expression,
)
from .errors import SourceExtractionError
if TYPE_CHECKING:
    from .metadata import AssemblyMetadata

_MONSTER_BASE = "MegaCrit.Sts2.Core.Models.MonsterModel"
_ENCOUNTER_BASE = "MegaCrit.Sts2.Core.Models.EncounterModel"
_POWER_BASE = "MegaCrit.Sts2.Core.Models.PowerModel"
_ABSTRACT_MODEL = "MegaCrit.Sts2.Core.Models.AbstractModel"
_MONSTER_NS = "MegaCrit.Sts2.Core.Models.Monsters."
_POWER_NS = "MegaCrit.Sts2.Core.Models.Powers."
_RELIC_NS = "MegaCrit.Sts2.Core.Models.Relics."
_HOOK = "MegaCrit.Sts2.Core.Hooks.Hook"

_STAGE_ORDER = {
    "constructorDefault": 0,
    "encounterGeneration": 1,
    "creatureCreation": 2,
    "encounterSpawnRegistration": 3,
    "creatureAdded": 4,
    "afterAddedToRoom": 5,
    "powerAfterApplied": 6,
    "beforeCombatStart": 7,
}
_EFFECT_KINDS = {
    "applyPower", "gainBlock", "setMaxAndCurrentHp", "setCurrentHp", "setState", "subscribe",
    "relationship", "forceMoveState", "afflictCard", "configurePowerTarget",
}
_OWNER_CLASSES = {"orderedGameplayEffects", "sourceProvenNoOp", "sourceProvenNonGameplayOnly"}
_CALL_CLASSES = {
    "normalizedGameplayEffect", "traversedGameplayHelper", "sourceProvenNoOp",
    "sourceProvenNonGameplayPlumbing", "sourceProvenPresentation",
    "sourceQuery", "runtimeExternalBoundary",
}
_RUNTIME_OWNERSHIP = {"monsterModel", "powerModel", "combatState", "runState", "externalHookRegistry"}
_INITIAL_RECIPIENTS = {
    "appliedPowerDynamicVariable", "appliedPowerOwner", "constructedMonsterModel", "customPowerInstance",
    "eligiblePlayerCombatCards", "sourceMonster", "sourceMonsterLifecycle", "sourceMonsterModel",
    "sourceMonsterMoveState", "sourceMonsterOpponents",
}
_INITIAL_PREDICATES = {"powerHookCondition", "restoredHatchedState", "sourceCardEligibilityPredicate"}


def _method(record: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
        "assemblySha256", "cilInstructionsSha256", "diagnosticMetadataToken",
        "metadataSignature", "methodBodySha256", "normalizedInstructionsSha256",
        "symbolSignature",
    )
    return {key: record[key] for key in keys}


def _slice(record: Mapping[str, Any], indexes: Iterable[int], semantic: Any) -> dict[str, Any]:
    positions = sorted({i for i in indexes if 0 <= i < len(record["instructions"])})
    if not positions:
        raise SourceExtractionError(f"empty initial-state evidence slice for {record['symbolSignature']}")
    rows = [record["instructions"][i] for i in positions]
    normalized = [{"opcode": row["opcode"], "operand": row.get("operand")} for row in rows]
    return {
        **_method(record),
        "normalizedSliceSha256": witness_sha256(normalized),
        "semanticWitnessSha256": witness_sha256(semantic),
    }


def _single_method(assembly: AssemblyMetadata, owner: str, name: str) -> int:
    rows = assembly.find_methods(owner, name)
    if len(rows) != 1:
        raise SourceExtractionError(f"required initial-state declaration is not unique: {owner}::{name} ({len(rows)})")
    return rows[0]


def _owner_member(symbol: str) -> tuple[str, str]:
    head = symbol.split(" sig:", 1)[0]
    if "::" not in head:
        raise SourceExtractionError(f"initial-state callee lacks exact owner/member: {symbol}")
    return tuple(head.rsplit("::", 1))  # type: ignore[return-value]


def _nearest_method(assembly: AssemblyMetadata, source_type: str, name: str) -> tuple[int, list[str]]:
    path: list[str] = []
    seen: set[str] = set()
    current = source_type
    while current:
        if current in seen:
            raise SourceExtractionError(f"initial-state inheritance cycle at {current}")
        seen.add(current); path.append(current)
        rows = assembly.find_methods(current, name)
        if len(rows) > 1:
            raise SourceExtractionError(f"ambiguous effective method {current}::{name}")
        if rows:
            return rows[0], path
        current = assembly.base_by_type.get(current, "")
    raise SourceExtractionError(f"no effective {name} implementation for {source_type}")


def _canonical_from_type(source_type: str, category: str) -> str:
    simple = source_type.rsplit(".", 1)[-1].split("+", 1)[0]
    return category + "." + slugify_ascii_type_name(simple)


def _bool_expression(value: SymbolicValue, index: int, field: str) -> dict[str, Any]:
    ensure_resolved(value, field, index)
    if value.kind == "constant" and type(value.data) is int and value.data in {0, 1}:
        return {"kind": "constant", "value": bool(value.data), "valueType": "boolean"}
    if value.kind == "join":
        choices = {_bool_expression(item, index, field)["value"] for item in value.operands}
        if choices == {False, True}:
            raise SourceExtractionError(f"conditional boolean {field} lacks a normalized predicate at instruction {index}")
    raise SourceExtractionError(f"unsupported boolean {field} at instruction {index}: {value.kind}")


def _typed_value(value: SymbolicValue, parameter_kind: str, index: int, field: str) -> dict[str, Any]:
    if parameter_kind == "bool":
        return _bool_expression(value, index, field)
    if parameter_kind in {"i1", "u1", "i2", "u2", "i4", "u4", "i8", "u8", "nativeint", "nativeuint"}:
        result = value_expression(value, field_name=field, instruction_index=index)
        if result["valueType"] != "integer":
            raise SourceExtractionError(f"non-integer {field} for integer member at instruction {index}")
        return result
    if parameter_kind in {"r4", "r8", "valuetype"}:
        result = value_expression(value, field_name=field, instruction_index=index)
        if result["valueType"] not in {"integer", "decimal"}:
            raise SourceExtractionError(f"nonnumeric {field} at instruction {index}")
        return result
    raise SourceExtractionError(f"unsupported initial-state member type {parameter_kind} at instruction {index}")


def _unit(member: str, value_type: str, effect_kind: str) -> str:
    lower = member.lower()
    if effect_kind in {"gainBlock"}: return "block"
    if effect_kind in {"setMaxAndCurrentHp", "setCurrentHp"} or "hp" in lower: return "hitPoints"
    if effect_kind == "applyPower": return "powerAmount"
    if effect_kind in {"subscribe", "relationship", "forceMoveState", "configurePowerTarget"}: return "state"
    if value_type == "boolean": return "flag"
    if "move" in lower and ("idx" in lower or "index" in lower): return "moveIndex"
    if "turn" in lower: return "turns"
    if "scale" in lower: return "ratio"
    return "counter"


def _fact_id(owner_model: str, stage: str, ordinal: int, effect_kind: str) -> str:
    return f"INITIAL.{owner_model}.{stage.upper()}.{ordinal:03d}.{effect_kind.upper()}"


def _fact(
    *, owner_model: str, applicable_models: Sequence[str], stage: str, trigger: str,
    ordinal: int, effect: Mapping[str, Any], recipient: Mapping[str, Any],
    value: Mapping[str, Any], unit: str, provenance: Mapping[str, Any],
    condition: Mapping[str, Any] | None = None, encounter: str | None = None,
    runtime_modifiers: Sequence[str] = (), source_inputs: Sequence[str] = (),
) -> dict[str, Any]:
    kind = str(effect["kind"])
    row = {
        "applicableModels": sorted(applicable_models),
        "baseValue": {"expression": deepcopy(value), "unit": unit, "valueType": value["valueType"]},
        "condition": deepcopy(condition or {"kind": "unconditional"}),
        "effect": deepcopy(dict(effect)),
        "factId": _fact_id(owner_model, stage, ordinal, kind),
        "finalValueContract": {
            "classification": "intrinsicRequestedBaseline",
            "runtimeModifierInputs": sorted(runtime_modifiers),
            "scalingRefs": [],
        },
        "order": {"sourceOrder": ordinal, "stageOrder": _STAGE_ORDER[stage]},
        "ownerModel": owner_model,
        "provenance": deepcopy(dict(provenance)),
        "recipient": deepcopy(dict(recipient)),
        "sourceStateInputs": sorted(source_inputs),
        "stage": stage,
        "trigger": trigger,
    }
    if encounter is not None:
        row["encounterApplicability"] = "ENCOUNTER." + encounter
        row["factId"] += ".ENCOUNTER." + encounter
    return row


def _target(value: SymbolicValue, invocation: Invocation, record: Mapping[str, Any]) -> str:
    try:
        return _source_target(value, field_name="initial-state recipient", instruction_index=invocation.index, record=record)
    except SourceExtractionError:
        # A loop-current creature reached from GetOpponentsOf is still exact even
        # when the general move target normalizer cannot collapse the iterator.
        symbols: set[str] = set(); active = [value]; seen: set[int] = set()
        while active:
            item = active.pop()
            if id(item) in seen: continue
            seen.add(id(item))
            if isinstance(item.data, str): symbols.add(item.data)
            active.extend(item.operands)
        if any("PowerModel::get_Owner sig:" in s for s in symbols):
            return "appliedPowerOwner"
        if any("ICombatState::GetOpponentsOf sig:" in s for s in symbols):
            if any("::get_Current sig:" in s for s in symbols): return "iteratedOpponent"
            return "sourceMonsterOpponents"
        raise


def _power_apply(invocation: Invocation, record: Mapping[str, Any]) -> tuple[str, str, dict[str, Any], list[int]]:
    owner, member = _owner_member(invocation.symbol)
    if owner != "MegaCrit.Sts2.Core.Commands.PowerCmd" or member != "Apply":
        raise SourceExtractionError(f"not a PowerCmd.Apply invocation: {invocation.symbol}")
    args = list(invocation.arguments)
    if len(invocation.signature.parameters) == 6 and len(args) == 6:
        power_value = None; target_index = 1; amount_index = 2
    elif len(invocation.signature.parameters) == 7 and len(args) == 7:
        power_value = args[1]; target_index = 2; amount_index = 3
    else:
        raise SourceExtractionError(f"unknown PowerCmd.Apply overload: {invocation.symbol}")
    values = args if power_value is None else [power_value]
    model = _model_from_values(values, [invocation.symbol])
    if not model or not model.startswith("POWER."):
        raise SourceExtractionError(f"unresolved initial Power model at instruction {invocation.index}")
    target = _target(args[target_index], invocation, record)
    try:
        amount = value_expression(args[amount_index], field_name="initial Power amount", instruction_index=invocation.index)
    except SourceExtractionError:
        # The only accepted join form is an exact two-branch 1/2 choice guarded
        # by CombatState.CurrentSide in the same pre-sink slice.
        value = args[amount_index]
        if value.kind == "join":
            alternatives = list(value.operands)
        elif value.kind == "convert" and len(value.operands) == 1 and value.operands[0].kind == "join":
            alternatives = [SymbolicValue("convert", value.cil_type, value.data, (item,), value.origins | item.origins)
                            for item in value.operands[0].operands]
        else:
            alternatives = []
        projected = [value_expression(item, field_name="initial Power branch amount", instruction_index=invocation.index)
                     for item in alternatives]
        def scalar(expression: Mapping[str, Any]) -> str | int | None:
            current = expression
            while current.get("kind") == "convert": current = current["expression"]
            return current.get("value") if current.get("kind") == "constant" else None
        by_value = {str(scalar(expression)): expression for expression in projected}
        prefix = record["instructions"][:invocation.index]
        current_side = [i for i, row in enumerate(prefix) if isinstance(row.get("operand"), str)
                        and "ICombatState::get_CurrentSide sig:" in row["operand"]]
        value_types = {expression["valueType"] for expression in projected}
        if set(by_value) != {"1", "2"} or len(current_side) != 1 or len(value_types) != 1:
            raise
        result_type = value_types.pop()
        amount = {
            "condition": {
                "kind": "compare", "operator": "equal",
                "left": {"kind": "stateVariable", "name": "combat.currentSide", "valueType": "integer", "domain": {"minimum": 0, "maximum": 1}},
                "right": {"kind": "constant", "value": 0, "valueType": "integer"}, "valueType": "boolean",
            },
            "kind": "conditional", "valueType": result_type,
            "whenFalse": by_value["2"], "whenTrue": by_value["1"],
        }
    validate_expression(amount)
    origins = set(args[target_index].origins) | set(args[amount_index].origins) | {invocation.index}
    if power_value is not None:
        origins.update(power_value.origins)
    return model, target, amount, sorted(origins)


def _encounter_initializers(
    assembly: AssemblyMetadata, assembly_sha256: str, encounters: Sequence[Mapping[str, Any]],
    reachable_models: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    roots: list[dict[str, Any]] = []
    facts: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for encounter in sorted(encounters, key=lambda row: row["canonicalId"]):
        source_type = encounter["sourceType"]
        method_index = _single_method(assembly, source_type, "GenerateMonsters")
        record = assembly.method_record(method_index, assembly_sha256)
        setter_indexes = {index for index, row in enumerate(record["instructions"])
                          if row["opcode"] in {"call", "callvirt"}
                          and isinstance(row.get("operand"), str)
                          and row["operand"].startswith(_MONSTER_NS)
                          and "::set_" in row["operand"]}
        invocations = CilDataFlow(record["instructions"]).run() if setter_indexes else {}
        root_setters: list[str] = []; root_rng: list[str] = []; root_constructions: list[str] = []
        setter_ordinal = 0
        # Construction and RNG sites are declaration-classified directly. Their
        # roster semantics were independently closed by the roster AST family;
        # E2a only needs to prove whether each root also mutates model state.
        for index, instruction in enumerate(record["instructions"]):
            symbol = instruction.get("operand")
            if instruction["opcode"] not in {"call", "callvirt"} or not isinstance(symbol, str):
                continue
            owner, member = _owner_member(symbol)
            if owner == "MegaCrit.Sts2.Core.Models.ModelDb" and member == "Monster":
                model = _model_from_values([], [symbol])
                if not model or model not in reachable_models:
                    raise SourceExtractionError(f"generator constructs unresolved/nonreachable model: {symbol}")
                decision_id = f"INITIALIZER.{encounter['canonicalId']}.CONSTRUCT.{index:03d}"
                root_constructions.append(decision_id)
                decisions.append({"classification": "rosterModelConstruction", "decisionId": decision_id,
                                  "encounter": "ENCOUNTER." + encounter["canonicalId"], "model": model,
                                  "provenance": _slice(record, {index}, {"model": model})})
            if owner.startswith("MegaCrit.Sts2.Core.Random.") or member.startswith("get_Rng"):
                decision_id = f"INITIALIZER.{encounter['canonicalId']}.RNG.{index:03d}"
                root_rng.append(decision_id)
                classification = "nonRosterInitializationRng" if encounter["nonRosterInitializationRng"] else "rosterSelectionRng"
                decisions.append({"classification": classification, "decisionId": decision_id,
                                  "encounter": "ENCOUNTER." + encounter["canonicalId"],
                                  "symbolSignature": symbol,
                                  "provenance": _slice(record, {index}, {"classification": classification})})
        for index, invocation in sorted(invocations.items()):
            owner, member = _owner_member(invocation.symbol)
            if owner.startswith(_MONSTER_NS) and member.startswith("set_"):
                if invocation.receiver is None or len(invocation.arguments) != 1 or len(invocation.signature.parameters) != 1:
                    raise SourceExtractionError(f"malformed generator setter: {invocation.symbol}")
                model = _model_from_values([invocation.receiver], [invocation.symbol])
                if not model or model not in reachable_models:
                    raise SourceExtractionError(f"generator setter receiver is not exact reachable model: {invocation.symbol}")
                expression = _typed_value(invocation.arguments[0], invocation.signature.parameters[0].kind, index, member)
                effect = {"kind": "setState", "member": invocation.symbol}
                provenance = _slice(record, set(invocation.receiver.origins) | set(invocation.arguments[0].origins) | {index},
                                    {"effect": effect, "model": model, "value": expression})
                fact = _fact(owner_model=model, applicable_models=[model], stage="encounterGeneration",
                             trigger="encounterGenerateMonsters", ordinal=setter_ordinal, effect=effect,
                             recipient={"kind": "constructedMonsterModel"}, value=expression,
                             unit=_unit(member, expression["valueType"], "setState"), provenance=provenance,
                             encounter=encounter["canonicalId"])
                facts.append(fact); root_setters.append(fact["factId"]); setter_ordinal += 1
        roots.append({
            "canonicalEncounter": "ENCOUNTER." + encounter["canonicalId"],
            "classification": "orderedInitializers" if root_setters else "sourceProvenNoInitializerWrites",
            "constructionDecisionRefs": sorted(root_constructions), "factRefs": root_setters,
            "method": _method(record), "rngDecisionRefs": sorted(root_rng), "sourceType": source_type,
        })
    if len(roots) != len(encounters) or len({row["canonicalEncounter"] for row in roots}) != len(encounters):
        raise SourceExtractionError("encounter initializer root denominator did not close")
    return roots, facts, decisions


def _constructor_defaults(
    assembly: AssemblyMetadata, assembly_sha256: str, source_to_model: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    facts: list[dict[str, Any]] = []; decisions: list[dict[str, Any]] = []
    for source_type, model in sorted(source_to_model.items(), key=lambda item: item[1]):
        for method_index in assembly.find_methods(source_type, ".ctor"):
            record = assembly.method_record(method_index, assembly_sha256)
            flow = CilDataFlow(record["instructions"]); flow.run()
            ordinal = 0
            for index, instruction in enumerate(record["instructions"]):
                member = instruction.get("operand")
                if instruction["opcode"] != "stfld" or not isinstance(member, str) or not member.startswith(source_type + "::"):
                    continue
                frame = flow.frames.get(index)
                if frame is None or len(frame.stack) < 2:
                    raise SourceExtractionError(f"unresolved constructor field write {member}")
                value = frame.stack[-1]
                if value.kind == "constant" and value.cil_type and value.cil_type.kind in {"r4", "r8"}:
                    expression = {"kind": "constant", "value": str(value.data), "valueType": "decimal"}
                else:
                    expression = value_expression(value, field_name="constructor default", instruction_index=index)
                validate_expression(expression)
                effect = {"kind": "setState", "member": member}
                provenance = _slice(record, set(value.origins) | {index}, {"effect": effect, "value": expression})
                fact = _fact(owner_model=model, applicable_models=[model], stage="constructorDefault",
                             trigger="modelConstruction", ordinal=ordinal, effect=effect,
                             recipient={"kind": "constructedMonsterModel"}, value=expression,
                             unit=_unit(member, expression["valueType"], "setState"), provenance=provenance)
                facts.append(fact); ordinal += 1
                decisions.append({"classification": "explicitGameplayStateDefault", "decisionId": fact["factId"],
                                  "factRef": fact["factId"], "member": member, "provenance": provenance})
    return facts, decisions


def _is_empty_completed_task(record: Mapping[str, Any]) -> bool:
    meaningful = [(row["opcode"], row.get("operand")) for row in record["instructions"]
                  if row["opcode"] not in {"nop"}]
    return meaningful == [
        ("call", "System.Threading.Tasks.Task::get_CompletedTask sig:0000128121"),
        ("ret", None),
    ]


def _find_declared_method(assembly: AssemblyMetadata, symbol: str) -> int | None:
    owner, member = _owner_member(symbol)
    candidates = [idx for idx in assembly.find_methods(owner, member) if assembly.method_symbol(idx) == symbol.split(" generic:", 1)[0].split(" methodspec:", 1)[0]]
    return candidates[0] if len(candidates) == 1 else None


def _call_decision(
    *, root_id: str, record: Mapping[str, Any], invocation: Invocation,
    classification: str, role: str,
) -> dict[str, Any]:
    if classification not in _CALL_CLASSES:
        raise SourceExtractionError(f"unknown initial call classification {classification}")
    semantic = {"classification": classification, "role": role, "symbolSignature": invocation.symbol}
    return {
        **semantic, "decisionId": f"CALL.{root_id}.{invocation.index:04d}",
        "provenance": _slice(record, {invocation.index}, semantic),
    }


def _claim_helper(seen: set[int], method_index: int, symbol: str) -> None:
    if method_index in seen:
        raise SourceExtractionError(f"initial-state helper cycle/repeated helper: {symbol}")
    seen.add(method_index)


def _after_added(
    assembly: AssemblyMetadata, assembly_sha256: str, source_to_model: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int], dict[str, str]]:
    async_methods = _async_map(assembly)
    implementation_models: dict[int, list[str]] = defaultdict(list)
    paths: dict[str, list[str]] = {}
    declarations: dict[str, int] = {}
    for source_type, model in source_to_model.items():
        method_index, path = _nearest_method(assembly, source_type, "AfterAddedToRoom")
        implementation_models[method_index].append(model); paths[model] = path; declarations[model] = method_index

    owners: list[dict[str, Any]] = []; facts: list[dict[str, Any]] = []; decisions: list[dict[str, Any]] = []
    direct_counts: Counter[str] = Counter(); power_types: dict[str, str] = {}
    fact_refs_by_model: dict[str, list[str]] = defaultdict(list)
    implementation_class: dict[int, str] = {}

    # Helpers are traversed once per effective implementation. Their facts are
    # later expanded through exact implementation applicability.
    helper_queue: deque[tuple[int, str, list[str], str]] = deque()
    seen_helpers: set[int] = set()

    for method_index, models in sorted(implementation_models.items(), key=lambda item: sorted(item[1])):
        declaration_symbol = assembly.method_symbol(method_index)
        body_index = async_methods.get(method_index, method_index)
        record = assembly.method_record(body_index, assembly_sha256)
        root_id = "HOOK." + witness_sha256(declaration_symbol)[:16].upper()
        if _is_empty_completed_task(record):
            implementation_class[method_index] = "sourceProvenNoOp"
            continue
        flow = CilDataFlow(record["instructions"]); invocations = flow.run()
        gameplay = 0; presentation = 0; ordinal = 0
        for index, invocation in sorted(invocations.items()):
            owner, member = _owner_member(invocation.symbol)
            if owner == "MegaCrit.Sts2.Core.Commands.PowerCmd" and member == "Apply":
                model, target, amount, origins = _power_apply(invocation, record)
                generic = re.search(r"generic:(MegaCrit\.Sts2\.Core\.Models\.Powers\.[A-Za-z0-9]+)$", invocation.symbol)
                if generic: power_types[model] = generic.group(1)
                else:
                    # Custom Power overload: recover exact generic ModelDb.Power
                    # construction from the model-bearing argument graph.
                    symbols: list[str] = []; active = list(invocation.arguments); seen: set[int] = set()
                    while active:
                        value = active.pop()
                        if id(value) in seen: continue
                        seen.add(id(value))
                        if isinstance(value.data, str): symbols.append(value.data)
                        active.extend(value.operands)
                    matches = {m.group(1) for symbol in symbols if (m := re.search(r"generic:(MegaCrit\.Sts2\.Core\.Models\.Powers\.[A-Za-z0-9]+)$", symbol))}
                    if len(matches) != 1: raise SourceExtractionError(f"custom initial Power type is ambiguous: {sorted(matches)}")
                    power_types[model] = matches.pop()
                effect = {"kind": "applyPower", "model": model}
                provenance = _slice(record, origins, {"effect": effect, "target": target, "value": amount})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": target}, value=amount, unit="powerAmount", provenance=provenance,
                                 runtime_modifiers=["RUNTIME.EXTERNAL.POWER_AMOUNT_HOOKS"])
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1; direct_counts["applyPower"] += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="applyPower")); continue
            if owner == "MegaCrit.Sts2.Core.Commands.CreatureCmd" and member in {"GainBlock", "SetMaxAndCurrentHp"}:
                args = list(invocation.arguments)
                expected_arity = 5 if member == "GainBlock" else 2
                if len(args) != expected_arity or len(invocation.signature.parameters) != expected_arity:
                    raise SourceExtractionError(f"unknown {member} overload: {invocation.symbol}")
                target = _target(args[0], invocation, record)
                if member == "SetMaxAndCurrentHp" and args[1].kind == "unresolved":
                    # Preserve the exact source algorithm as a dynamic contract;
                    # it is evaluated from current MaxHp, teammate state, act,
                    # player count and the source multiplayer HP helper.
                    required = ("Creature::get_MaxHp sig:", "ICombatState::GetTeammatesOf sig:",
                                "IRunState::get_CurrentActIndex sig:", "Creature::ScaleHpForMultiplayer sig:")
                    prefix_symbols = [str(row.get("operand") or "") for row in record["instructions"][:index]]
                    if not all(any(token in symbol for symbol in prefix_symbols) for token in required):
                        raise SourceExtractionError(f"unclosed dynamic HP input at {record['symbolSignature']}:{index}")
                    amount = {"kind": "stateVariable", "name": "initial.decimillipedeSharedMaxHp",
                              "valueType": "decimal", "domain": {"minimum": "0"}}
                    source_inputs = ["RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP"]
                else:
                    amount = value_expression(args[1], field_name=f"initial {member} amount", instruction_index=index)
                    source_inputs = []
                validate_expression(amount)
                kind = "gainBlock" if member == "GainBlock" else "setMaxAndCurrentHp"
                effect = {"kind": kind}
                provenance = _slice(record, set(args[0].origins) | set(args[1].origins) | {index},
                                    {"effect": effect, "target": target, "value": amount})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": target}, value=amount, unit=_unit(member, amount["valueType"], kind),
                                 provenance=provenance, source_inputs=source_inputs)
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1; direct_counts[kind] += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role=kind)); continue
            if owner == "MegaCrit.Sts2.Core.Entities.Creatures.Creature" and member == "SetCurrentHpInternal":
                if invocation.receiver is None or len(invocation.arguments) != 1 or len(invocation.signature.parameters) != 1:
                    raise SourceExtractionError(f"unknown SetCurrentHpInternal overload: {invocation.symbol}")
                target = _target(invocation.receiver, invocation, record)
                amount = value_expression(invocation.arguments[0], field_name="initial current HP", instruction_index=index)
                effect = {"kind": "setCurrentHp", "member": invocation.symbol}
                provenance = _slice(record, set(invocation.receiver.origins) | set(invocation.arguments[0].origins) | {index},
                                    {"effect": effect, "target": target, "value": amount})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": target}, value=amount, unit="hitPoints", provenance=provenance)
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1; direct_counts["setCurrentHp"] += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="setCurrentHp")); continue
            if owner.startswith(_MONSTER_NS) and member.startswith("set_"):
                if len(invocation.arguments) != 1 or len(invocation.signature.parameters) != 1:
                    raise SourceExtractionError(f"malformed initial monster setter: {invocation.symbol}")
                parameter_kind = invocation.signature.parameters[0].kind
                if parameter_kind == "class":
                    symbols: set[str] = set(); active = [invocation.arguments[0]]; seen_values: set[int] = set()
                    while active:
                        value = active.pop()
                        if id(value) in seen_values: continue
                        seen_values.add(id(value))
                        if isinstance(value.data, str): symbols.add(value.data)
                        active.extend(value.operands)
                    if any(token in symbol for symbol in symbols for token in ("Core.Nodes.", "Godot.")):
                        presentation += 1
                        decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                        classification="sourceProvenPresentation", role="visualStateStorage")); continue
                    predicate_symbols = [symbol for symbol in symbols if " sig:" in symbol and "::<" in symbol]
                    target_types: set[str] = set()
                    for predicate in predicate_symbols:
                        predicate_index = _find_declared_method(assembly, predicate)
                        if predicate_index is None: continue
                        predicate_record = assembly.method_record(predicate_index, assembly_sha256)
                        target_types.update(str(row["operand"]) for row in predicate_record["instructions"]
                                            if row["opcode"] == "isinst" and isinstance(row.get("operand"), str)
                                            and row["operand"].startswith(_MONSTER_NS))
                    if len(target_types) != 1:
                        raise SourceExtractionError(f"unresolved initial relationship target for {invocation.symbol}: {sorted(target_types)}")
                    target_model = _canonical_from_type(target_types.pop(), "MONSTER")
                    if target_model not in source_to_model.values():
                        raise SourceExtractionError(f"relationship target is not reachable: {target_model}")
                    expression = {"kind": "constant", "value": True, "valueType": "boolean"}
                    effect = {"kind": "relationship", "member": invocation.symbol, "targetModel": target_model,
                              "selection": "firstMatchingCombatEnemy"}
                else:
                    expression = _typed_value(invocation.arguments[0], parameter_kind, index, member)
                    effect = {"kind": "setState", "member": invocation.symbol}
                provenance = _slice(record, set(invocation.arguments[0].origins) | {index}, {"effect": effect, "value": expression})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": "sourceMonsterModel"}, value=expression,
                                 unit=_unit(member, expression["valueType"], "setState"), provenance=provenance)
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="stateWrite")); continue
            if member.startswith("add_") and owner.startswith("MegaCrit.Sts2.Core.Entities.Creatures."):
                effect = {"kind": "subscribe", "member": invocation.symbol}
                value = {"kind": "constant", "value": True, "valueType": "boolean"}
                provenance = _slice(record, {index}, {"effect": effect})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": "sourceMonsterLifecycle"}, value=value, unit="state", provenance=provenance)
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="eventSubscription")); continue
            if member == "ForceCurrentState" and "MonsterMoveStateMachine" in owner:
                effect = {"kind": "forceMoveState", "member": invocation.symbol}
                value = {"kind": "constant", "value": True, "valueType": "boolean"}
                provenance = _slice(record, {index}, {"effect": effect})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": "sourceMonsterMoveState"}, value=value, unit="state", provenance=provenance,
                                 condition={"kind": "sourcePredicate", "classification": "restoredHatchedState",
                                            "symbolSignature": declaration_symbol})
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="forceMoveState")); continue
            if owner == "MegaCrit.Sts2.Core.Models.PowerModel" and member == "set_Target":
                effect = {"kind": "configurePowerTarget", "member": invocation.symbol}
                value = {"kind": "constant", "value": True, "valueType": "boolean"}
                provenance = _slice(record, {index}, {"effect": effect})
                for applicable in sorted(models):
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": "customPowerInstance"}, value=value, unit="state", provenance=provenance)
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1; gameplay += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="powerTargetConfiguration")); continue

            # Exact declaration/category-based call closure.
            local_index = _find_declared_method(assembly, invocation.symbol)
            if member.startswith(("get_", "op_")) or (invocation.signature.returns.kind != "void" and member not in {"Hatch", "Sleep"}):
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceQuery", role="sourceValueOrPredicate")); continue
            if member in {"Sleep", "Hatch"} and local_index is not None and owner.startswith(_MONSTER_NS):
                helper_queue.append((local_index, root_id, sorted(models), owner))
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="traversedGameplayHelper", role="sourceMethodBody")); continue
            if member.startswith("<>n__") and local_index is not None:
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceProvenNoOp", role="baseHookCall")); continue
            if owner.startswith("MegaCrit.Sts2.Core.Models.Encounters.") and invocation.signature.returns.kind == "void" and all(
                parameter.kind == "class" for parameter in invocation.signature.parameters
            ):
                presentation += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceProvenPresentation", role="encounterVisualPlacement")); continue
            if owner.startswith(("MegaCrit.Sts2.Core.Nodes.", "MegaCrit.Sts2.Core.Helpers.", "Godot.")) or owner in {
                "MegaCrit.Sts2.Core.Commands.SfxCmd", "MegaCrit.Sts2.Core.Commands.CreatureCmd",
            } and member in {"TriggerAnim", "PlayLoop"}:
                presentation += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceProvenPresentation", role="audioVisual")); continue
            if member == ".ctor" or owner.startswith(("System.", "<TypeSpec:")):
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceProvenNonGameplayPlumbing", role="compilerCollectionOrContext")); continue
            if owner.startswith(("MegaCrit.Sts2.Core.Models.ModelDb", "MegaCrit.Sts2.Core.Models.MonsterModel",
                                 "MegaCrit.Sts2.Core.Models.PowerModel", "MegaCrit.Sts2.Core.Combat.ICombatState",
                                 "MegaCrit.Sts2.Core.TestSupport.")):
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceQuery", role="modelOrCombatQuery")); continue
            raise SourceExtractionError(f"unclassified initial-state invocation: {invocation.symbol}")
        implementation_class[method_index] = "orderedGameplayEffects" if gameplay else "sourceProvenNonGameplayOnly"

    # Traverse selected monster helpers. Helper recursion is always a failure.
    while helper_queue:
        method_index, parent_root, models, owner_type = helper_queue.popleft()
        _claim_helper(seen_helpers, method_index, assembly.method_symbol(method_index))
        body_index = async_methods.get(method_index, method_index); record = assembly.method_record(body_index, assembly_sha256)
        flow = CilDataFlow(record["instructions"]); invocations = flow.run(); ordinal = 500
        root_id = parent_root + ".HELPER." + witness_sha256(assembly.method_symbol(method_index))[:16].upper()
        for index, invocation in sorted(invocations.items()):
            call_owner, member = _owner_member(invocation.symbol)
            if call_owner == "MegaCrit.Sts2.Core.Commands.PowerCmd" and member == "Apply":
                model, target, amount, origins = _power_apply(invocation, record)
                generic = re.search(r"generic:(MegaCrit\.Sts2\.Core\.Models\.Powers\.[A-Za-z0-9]+)$", invocation.symbol)
                if not generic: raise SourceExtractionError(f"helper custom Power type unresolved: {invocation.symbol}")
                power_types[model] = generic.group(1)
                effect = {"kind": "applyPower", "model": model}; provenance = _slice(record, origins, {"effect": effect, "value": amount})
                for applicable in models:
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": target}, value=amount, unit="powerAmount", provenance=provenance,
                                 runtime_modifiers=["RUNTIME.EXTERNAL.POWER_AMOUNT_HOOKS"])
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="applyPower")); continue
            if call_owner.startswith(_MONSTER_NS) and member.startswith("set_"):
                parameter_kind = invocation.signature.parameters[0].kind
                if parameter_kind == "class":
                    symbols: set[str] = set(); active = [invocation.arguments[0]]; seen_values: set[int] = set()
                    while active:
                        value = active.pop()
                        if id(value) in seen_values: continue
                        seen_values.add(id(value))
                        if isinstance(value.data, str): symbols.add(value.data)
                        active.extend(value.operands)
                    if not any(token in symbol for symbol in symbols for token in ("Core.Nodes.", "Godot.")):
                        raise SourceExtractionError(f"unresolved helper relationship setter: {invocation.symbol}")
                    decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                    classification="sourceProvenPresentation", role="visualStateStorage")); continue
                expression = _typed_value(invocation.arguments[0], parameter_kind, index, member)
                effect = {"kind": "setState", "member": invocation.symbol}; provenance = _slice(record, set(invocation.arguments[0].origins) | {index}, {"effect": effect, "value": expression})
                for applicable in models:
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="creatureAddedToCombat", ordinal=ordinal, effect=effect,
                                 recipient={"kind": "sourceMonsterModel"}, value=expression,
                                 unit=_unit(member, expression["valueType"], "setState"), provenance=provenance)
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="stateWrite")); continue
            if call_owner == "MegaCrit.Sts2.Core.Commands.CreatureCmd" and member == "SetMaxAndCurrentHp":
                # Tough Egg's Hatch helper reuses the exact state formula already
                # extracted from this same method body in the source artifact.
                expression = {"kind": "stateVariable", "name": "initial.toughEggHatchHp",
                              "valueType": "decimal", "domain": {"minimum": "0"}}
                effect = {"kind": "setMaxAndCurrentHp"}; provenance = _slice(record, {index}, {"effect": effect, "value": expression})
                for applicable in models:
                    fact = _fact(owner_model=applicable, applicable_models=models, stage="afterAddedToRoom",
                                 trigger="restoredCreatureAdded", ordinal=ordinal, effect=effect,
                                 recipient={"kind": "sourceMonster"}, value=expression, unit="hitPoints", provenance=provenance,
                                 source_inputs=["RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP"],
                                 condition={"kind": "sourcePredicate", "classification": "restoredHatchedState",
                                            "symbolSignature": assembly.method_symbol(method_index)})
                    facts.append(fact); fact_refs_by_model[applicable].append(fact["factId"])
                ordinal += 1
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="normalizedGameplayEffect", role="setMaxAndCurrentHp")); continue
            if member.startswith(("get_", "op_")) or invocation.signature.returns.kind != "void":
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceQuery", role="sourceValueOrPredicate")); continue
            if call_owner.startswith(("MegaCrit.Sts2.Core.Nodes.", "MegaCrit.Sts2.Core.Helpers.", "Godot.")) or (call_owner == "MegaCrit.Sts2.Core.Commands.CreatureCmd" and member == "TriggerAnim"):
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceProvenPresentation", role="audioVisual")); continue
            if member == ".ctor" or call_owner.startswith(("System.", "<TypeSpec:")):
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceProvenNonGameplayPlumbing", role="compilerCollectionOrContext")); continue
            if call_owner.startswith(("MegaCrit.Sts2.Core.Models.MonsterModel", "MegaCrit.Sts2.Core.Combat.ICombatState",
                                      "MegaCrit.Sts2.Core.Random.", "MegaCrit.Sts2.Core.Entities.Creatures.Creature")):
                decisions.append(_call_decision(root_id=root_id, record=record, invocation=invocation,
                                                classification="sourceQuery", role="runtimeStateQuery")); continue
            raise SourceExtractionError(f"unclassified initial helper invocation: {invocation.symbol}")

    for source_type, model in sorted(source_to_model.items(), key=lambda item: item[1]):
        method_index = declarations[model]; applicable = sorted(implementation_models[method_index])
        classification = "orderedGameplayEffects" if fact_refs_by_model[model] else implementation_class[method_index]
        owners.append({
            "applicableModels": applicable, "classification": classification,
            "effectiveHook": assembly.method_symbol(method_index), "factRefs": sorted(fact_refs_by_model[model]),
            "inheritancePath": paths[model], "ownerModel": model, "sourceType": source_type,
            "provenance": {"assemblySha256": assembly_sha256, "inheritanceRelation": "TypeDef.Extends.transitiveClosure",
                           "relationWitnessSha256": witness_sha256(paths[model])},
        })
    return owners, facts, decisions, dict(sorted(direct_counts.items())), power_types


def _runtime_contracts(facts: Sequence[Mapping[str, Any]], assembly: AssemblyMetadata, assembly_sha256: str) -> list[dict[str, Any]]:
    members: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for fact in facts:
        member = fact["effect"].get("member")
        if member and fact["effect"]["kind"] in {"setState", "relationship", "configurePowerTarget"}:
            members[member].append(fact)
    contracts: list[dict[str, Any]] = []
    for member, rows in sorted(members.items()):
        value_type = rows[0]["baseValue"]["valueType"]
        if any(row["baseValue"]["valueType"] != value_type for row in rows):
            raise SourceExtractionError(f"runtime member has inconsistent types: {member}")
        domain: Any
        if value_type == "boolean": domain = [False, True]
        elif value_type == "integer": domain = {"maximum": 2_147_483_647, "minimum": -2_147_483_648}
        elif value_type == "decimal": domain = {"classification": "cliDecimalValue"}
        else: raise SourceExtractionError(f"runtime contract unsupported value type: {value_type}")
        owner = member.split("::", 1)[0]
        read_records: list[dict[str, Any]] = []
        if "::set_" in member:
            getter_name = "get_" + member.split("::set_", 1)[1].split(" sig:", 1)[0]
            getter_indexes = assembly.find_methods(owner, getter_name)
            if len(getter_indexes) != 1:
                raise SourceExtractionError(f"runtime member getter is not unique: {member}")
            getter_record = assembly.method_record(getter_indexes[0], assembly_sha256)
            read_records.append({"classification": "sourceGetter", "methodBodySha256": getter_record["methodBodySha256"],
                                 "symbolSignature": getter_record["symbolSignature"]})
        elif "::" in member and " sig:" not in member:
            for method_index, method_owner_index in assembly.method_owner.items():
                if assembly.type_names[method_owner_index] != owner and not assembly.type_names[method_owner_index].startswith(owner + "+"): continue
                method_row = assembly.md.MethodDef.rows[method_index - 1]
                if not method_row.Rva: continue
                candidate = assembly.method_record(method_index, assembly_sha256)
                if any(row["opcode"] in {"ldfld", "ldsfld"} and row.get("operand") == member for row in candidate["instructions"]):
                    read_records.append({"classification": "sourceFieldRead", "methodBodySha256": candidate["methodBodySha256"],
                                         "symbolSignature": candidate["symbolSignature"]})
            if not read_records:
                raise SourceExtractionError(f"runtime field has no exact read site: {member}")
        else:
            raise SourceExtractionError(f"unsupported runtime state member declaration: {member}")
        ownership = "powerModel" if owner.startswith(("MegaCrit.Sts2.Core.Models.PowerModel", "MegaCrit.Sts2.Core.Localization.DynamicVars.")) else "monsterModel"
        contracts.append({
            "consumerMeaning": rows[0]["baseValue"]["unit"], "contractId": "RUNTIME.MEMBER." + witness_sha256(member)[:16].upper(),
            "default": deepcopy(rows[0]["baseValue"]["expression"]) if rows[0]["stage"] == "constructorDefault" else None,
            "domain": domain, "owner": rows[0]["ownerModel"], "ownership": ownership,
            "readSites": sorted(read_records, key=lambda row: row["symbolSignature"]), "sourceInputs": [],
            "sourceMember": member, "sourceType": owner, "unit": rows[0]["baseValue"]["unit"],
            "updateSites": [{"factRef": row["factId"], "methodBodySha256": row["provenance"]["methodBodySha256"],
                             "symbolSignature": row["provenance"]["symbolSignature"]} for row in rows],
            "valueType": value_type,
        })
    # Every dynamic normalized expression input gets an explicit source/member
    # contract. Pure constants/arithmetic introduce no runtime input.
    dynamic_contracts: dict[str, dict[str, Any]] = {}
    player_count_symbols: set[str] = set()
    state_contract_ids = {
        "combat.currentSide": "RUNTIME.COMBAT.CURRENT_SIDE",
        "initial.decimillipedeSharedMaxHp": "RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP",
        "initial.toughEggHatchHp": "RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP",
    }
    def walk_expression(node: Mapping[str, Any], fact: Mapping[str, Any]) -> None:
        kind = node.get("kind")
        if kind == "stateVariable":
            contract_id = state_contract_ids.get(str(node["name"]))
            if contract_id is None: raise SourceExtractionError(f"unregistered initial source field {node['name']}")
            if contract_id not in fact["sourceStateInputs"]: fact["sourceStateInputs"].append(contract_id)
            return
        if kind == "reference":
            symbol = str(node["reference"])
            if fact["baseValue"]["unit"] == "playerCount" and "RUNTIME.RUN.PLAYER_COUNT" in fact["sourceStateInputs"]:
                player_count_symbols.add(symbol); return
            contract_id = "RUNTIME.EXPRESSION." + witness_sha256(symbol)[:16].upper()
            value_type = node["valueType"]
            domain = ({"maximum": 2_147_483_647, "minimum": -2_147_483_648} if value_type == "integer"
                      else ([False, True] if value_type == "boolean" else {"classification": "sourceDecimalResult"}))
            owner_type = symbol.split("::", 1)[0]
            ownership = "monsterModel" if owner_type.startswith(_MONSTER_NS) else (
                "combatState" if ".Combat." in owner_type else "runState")
            dynamic_contracts.setdefault(contract_id, {
                "consumerMeaning": "dynamic source expression input", "contractId": contract_id,
                "default": None, "domain": domain, "owner": fact["ownerModel"], "ownership": ownership,
                "readSites": [{"classification": "sourceExpressionRead", "symbolSignature": symbol}], "sourceInputs": [],
                "sourceMember": symbol, "sourceType": owner_type,
                "unit": fact["baseValue"]["unit"], "updateSites": [], "valueType": value_type,
            })
            if contract_id not in fact["sourceStateInputs"]: fact["sourceStateInputs"].append(contract_id)
        for key, child in node.items():
            if isinstance(child, dict) and "kind" in child: walk_expression(child, fact)
            elif isinstance(child, list):
                for item in child:
                    if isinstance(item, dict) and "kind" in item: walk_expression(item, fact)
    for fact in facts:
        walk_expression(fact["baseValue"]["expression"], fact)
        fact["sourceStateInputs"].sort()
    contracts.extend(dynamic_contracts.values())
    contracts.extend([
        {
            "consumerMeaning": "side selecting Tough Egg Hatch amount", "contractId": "RUNTIME.COMBAT.CURRENT_SIDE",
            "default": None, "domain": {"maximum": 1, "minimum": 0}, "owner": "combatState",
            "ownership": "combatState", "readSites": [{"classification": "sourceGetter", "symbolSignature": "MegaCrit.Sts2.Core.Combat.ICombatState::get_CurrentSide sig:200011aa6c"}],
            "sourceInputs": [], "sourceMember": "MegaCrit.Sts2.Core.Combat.ICombatState::get_CurrentSide sig:200011aa6c",
            "sourceType": "MegaCrit.Sts2.Core.Combat.ICombatState", "unit": "side", "updateSites": [], "valueType": "integer",
        },
        {
            "consumerMeaning": "source algorithm selecting a common even HP for Decimillipede segments",
            "contractId": "RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP", "default": None,
            "domain": {"minimum": "0"}, "owner": "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT",
            "ownership": "monsterModel", "readSites": [{"classification": "gameplaySink", "symbolSignature": "MegaCrit.Sts2.Core.Commands.CreatureCmd::SetMaxAndCurrentHp sig:000212812112a7e4118449"}],
            "sourceInputs": [
                {"sourceMember": "MegaCrit.Sts2.Core.Entities.Creatures.Creature::get_MaxHp sig:200008", "unit": "hitPoints", "valueType": "integer"},
                {"sourceMember": "MegaCrit.Sts2.Core.Combat.ICombatState::get_Players sig:2000151281fd0112a74c", "unit": "players", "valueType": "collection"},
                {"sourceMember": "MegaCrit.Sts2.Core.Runs.IRunState::get_CurrentActIndex sig:200008", "unit": "actIndex", "valueType": "integer"},
                {"sourceMember": "MegaCrit.Sts2.Core.Combat.ICombatState::GetTeammatesOf sig:2001151281fd0112a7e412a7e4", "unit": "creatures", "valueType": "collection"},
                {"sourceMember": "MegaCrit.Sts2.Core.Entities.Creatures.Creature::ScaleHpForMultiplayer sig:00041184491184491288c80808", "unit": "hitPoints", "valueType": "decimal"},
            ],
            "sourceMember": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment+<>c__DisplayClass46_0::maxHp",
            "sourceType": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment", "unit": "hitPoints",
            "updateSites": [{"classification": "currentMaxHpEveningAndTeammateSelection",
                             "symbolSignature": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment+<AfterAddedToRoom>d__46::MoveNext sig:200001"}],
            "valueType": "decimal",
        },
        {
            "consumerMeaning": "inclusive hatchling HP selection followed by multiplayer HP scaling",
            "contractId": "RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP", "default": None,
            "domain": {"minimum": "0"}, "owner": "MONSTER.TOUGH_EGG", "ownership": "monsterModel",
            "readSites": [{"classification": "gameplaySink", "symbolSignature": "MegaCrit.Sts2.Core.Commands.CreatureCmd::SetMaxAndCurrentHp sig:000212812112a7e4118449"}],
            "sourceInputs": [
                {"sourceMember": "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg::get_HatchlingMinHp sig:200008", "unit": "hitPoints", "valueType": "integer"},
                {"sourceMember": "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg::get_HatchlingMaxHp sig:200008", "unit": "hitPoints", "valueType": "integer"},
                {"sourceMember": "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:2002080808", "unit": "hitPoints", "valueType": "integer"},
                {"sourceMember": "MegaCrit.Sts2.Core.Entities.Creatures.Creature::ScaleHpForMultiplayer sig:00041184491184491288c80808", "unit": "hitPoints", "valueType": "decimal"},
            ],
            "sourceMember": "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg::Hatch sig:2000128121",
            "sourceType": "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg", "unit": "hitPoints",
            "updateSites": [{"classification": "sourceRngSelectionAndHpScaling",
                             "symbolSignature": "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg+<Hatch>d__36::MoveNext sig:200001"}],
            "valueType": "decimal",
        },
        {
            "consumerMeaning": "number of players used by intrinsic initial Power state", "contractId": "RUNTIME.RUN.PLAYER_COUNT",
            "default": None, "domain": {"minimum": 1}, "owner": "runState", "ownership": "runState",
            "readSites": [{"classification": "sourceCountGetter", "symbolSignature": symbol} for symbol in sorted(player_count_symbols)],
            "sourceInputs": [{"sourceMember": "MegaCrit.Sts2.Core.Runs.IPlayerCollection::get_Players sig:2000151281fd0112a74c", "unit": "players", "valueType": "collection"}],
            "sourceMember": next(iter(sorted(player_count_symbols))),
            "sourceType": "MegaCrit.Sts2.Core.Runs.IPlayerCollection", "unit": "players", "updateSites": [], "valueType": "integer",
        },
        {
            "consumerMeaning": "Power amount and listener changes owned by run-state hook listeners",
            "contractId": "RUNTIME.EXTERNAL.POWER_AMOUNT_HOOKS", "default": None,
            "domain": {"classification": "sourceOwnedDynamic"}, "owner": "externalHookRegistry",
            "ownership": "externalHookRegistry", "readSites": [{"classification": "PowerCmd.Apply hook dispatch"}],
            "sourceInputs": [{"sourceMember": "MegaCrit.Sts2.Core.Combat.ICombatState::IterateHookListeners sig:2000151281f50112889c", "unit": "listeners", "valueType": "collection"}],
            "sourceMember": "MegaCrit.Sts2.Core.Commands.PowerCmd::Apply", "sourceType": "MegaCrit.Sts2.Core.Commands.PowerCmd",
            "unit": "powerAmount", "updateSites": [], "valueType": "decimal",
        },
    ])
    if any(contract["ownership"] not in _RUNTIME_OWNERSHIP for contract in contracts):
        raise SourceExtractionError("unsupported runtime contract ownership")
    return sorted(contracts, key=lambda row: row["contractId"])


def _external_boundaries(assembly: AssemblyMetadata, assembly_sha256: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []; chain: list[dict[str, Any]] = []
    chain_specs = [
        ("MegaCrit.Sts2.Core.Combat.CombatState", "CreateCreature", "creatureCreation"),
        (_ENCOUNTER_BASE, "OnCreatureSpawned", "encounterSpawnRegistration"),
        ("MegaCrit.Sts2.Core.Combat.CombatManager", "StartCombatInternal", "combatStart"),
        ("MegaCrit.Sts2.Core.Combat.CombatManager", "AfterCreatureAdded", "creatureAdded"),
        ("MegaCrit.Sts2.Core.Entities.Creatures.Creature", "AfterAddedToRoom", "modelAdditionHookDispatch"),
        (_MONSTER_BASE, "AfterAddedToRoom", "effectiveMonsterAdditionHook"),
        (_HOOK, "BeforeCombatStart", "beforeCombatStartDispatch"),
    ]
    async_methods = _async_map(assembly)
    start_index = _single_method(assembly, "MegaCrit.Sts2.Core.Combat.CombatManager", "StartCombatInternal")
    start_body = assembly.method_record(async_methods.get(start_index, start_index), assembly_sha256)
    after_symbols = {row["operand"] for row in start_body["instructions"]
                     if row["opcode"] in {"call", "callvirt"} and isinstance(row.get("operand"), str)
                     and row["operand"].startswith("MegaCrit.Sts2.Core.Combat.CombatManager::AfterCreatureAdded sig:")}
    if len(after_symbols) != 1:
        raise SourceExtractionError(f"StartCombatInternal AfterCreatureAdded dispatch is not unique: {sorted(after_symbols)}")
    after_symbol = after_symbols.pop()
    method_by_stage: dict[str, int] = {}
    row_by_stage: dict[str, dict[str, Any]] = {}
    for owner, member, stage in chain_specs:
        if owner == "MegaCrit.Sts2.Core.Combat.CombatManager" and member == "AfterCreatureAdded":
            matches = [idx for idx in assembly.find_methods(owner, member) if assembly.method_symbol(idx) == after_symbol]
            if len(matches) != 1: raise SourceExtractionError("called AfterCreatureAdded declaration is not unique")
            method_index = matches[0]
        else:
            method_index = _single_method(assembly, owner, member)
        method_by_stage[stage] = method_index
        record = assembly.method_record(method_index, assembly_sha256)
        row = {"classification": "requiredInitializationChain", "method": _method(record), "stage": stage}
        row_by_stage[stage] = row; chain.append(row)
    dispatches = {
        "encounterSpawnRegistration": "creatureCreation",
        "creatureAdded": "combatStart",
        "modelAdditionHookDispatch": "creatureAdded",
        "effectiveMonsterAdditionHook": "modelAdditionHookDispatch",
        "beforeCombatStartDispatch": "combatStart",
    }
    for target_stage, caller_stage in dispatches.items():
        caller_index = method_by_stage[caller_stage]
        caller_body = assembly.method_record(async_methods.get(caller_index, caller_index), assembly_sha256)
        target_symbol = assembly.method_symbol(method_by_stage[target_stage])
        sites = {i for i, instruction in enumerate(caller_body["instructions"])
                 if instruction["opcode"] in {"call", "callvirt"} and instruction.get("operand") == target_symbol}
        if len(sites) != 1:
            raise SourceExtractionError(f"initialization dispatch is not unique: {caller_stage} -> {target_stage} ({len(sites)})")
        row_by_stage[target_stage]["dispatchProvenance"] = _slice(
            caller_body, sites, {"calledMethod": target_symbol, "callerStage": caller_stage, "targetStage": target_stage}
        )
    for family in ("BeforeCombatStart", "AfterCreatureAddedToCombat"):
        declarations = []
        for index, method_row in enumerate(assembly.md.MethodDef.rows, 1):
            if str(method_row.Name) != family: continue
            owner = assembly.type_names[assembly.method_owner[index]]
            symbol = assembly.method_symbol(index)
            if owner.startswith(_RELIC_NS) or owner.startswith("MegaCrit.Sts2.Core.Models.Modifiers."):
                classification = "externalRuntimeOwned"
            elif owner.startswith(_POWER_NS):
                classification = "intrinsicPowerListener"
            elif owner in {_ABSTRACT_MODEL, _HOOK}:
                classification = "registryDeclarationOrDispatcher"
            else:
                classification = "externalRuntimeOwned"
            declarations.append({"classification": classification, "method": _method(assembly.method_record(index, assembly_sha256)), "sourceType": owner})
        rows.append({"declarations": sorted(declarations, key=lambda row: row["method"]["symbolSignature"]),
                     "family": family, "registryClassification": "sourceListenerIteration"})
    return rows, chain


def _power_hook_closure(
    assembly: AssemblyMetadata, assembly_sha256: str, power_types: Mapping[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    async_methods = _async_map(assembly); rows: list[dict[str, Any]] = []; facts: list[dict[str, Any]] = []; decisions: list[dict[str, Any]] = []
    discovered = dict(power_types)
    queue = deque(sorted(discovered)); closed: set[str] = set()
    while queue:
        model = queue.popleft()
        if model in closed: continue
        closed.add(model); source_type = discovered[model]
        hook_rows=[]
        for hook_name in ("BeforeApplied", "AfterApplied", "BeforeCombatStart"):
            method_index, path = _nearest_method(assembly, source_type, hook_name)
            body_index = async_methods.get(method_index, method_index); record = assembly.method_record(body_index, assembly_sha256)
            declaration_owner = assembly.type_names[assembly.method_owner[method_index]]
            if _is_empty_completed_task(record):
                classification = "sourceProvenNoOp"; effect_refs=[]
            else:
                classification = "orderedGameplayEffects"; effect_refs=[]
                flow = CilDataFlow(record["instructions"]); invocations = flow.run(); ordinal=700
                for index, invocation in sorted(invocations.items()):
                    owner, member = _owner_member(invocation.symbol)
                    if owner == "MegaCrit.Sts2.Core.Commands.PowerCmd" and member == "Apply":
                        secondary, target, amount, origins = _power_apply(invocation, record)
                        generic = re.search(r"generic:(MegaCrit\.Sts2\.Core\.Models\.Powers\.[A-Za-z0-9]+)$", invocation.symbol)
                        if not generic: raise SourceExtractionError(f"Power hook secondary type unresolved: {invocation.symbol}")
                        if secondary not in discovered: discovered[secondary]=generic.group(1);queue.append(secondary)
                        effect={"kind":"applyPower","model":secondary};prov=_slice(record,origins,{"effect":effect,"value":amount})
                        # Power-hook effects apply to every monster that introduced
                        # this Power; owner/applicability is represented by Power.
                        fact=_fact(owner_model="POWER_OWNER."+model,applicable_models=[],stage="powerAfterApplied",
                                   trigger="powerAfterApplied",ordinal=ordinal,effect=effect,recipient={"kind":target},
                                   value=amount,unit="powerAmount",provenance=prov,
                                   condition={"kind":"sourcePredicate","classification":"powerHookCondition","symbolSignature":record["symbolSignature"]},
                                   runtime_modifiers=["RUNTIME.EXTERNAL.POWER_AMOUNT_HOOKS"])
                        facts.append(fact);effect_refs.append(fact["factId"]);ordinal+=1
                        decisions.append(_call_decision(root_id="POWER."+model,record=record,invocation=invocation,classification="normalizedGameplayEffect",role="applyPower"));continue
                    if owner == "MegaCrit.Sts2.Core.Commands.CardCmd" and member == "Afflict":
                        generic = re.search(r"generic:MegaCrit\.Sts2\.Core\.Models\.Afflictions\.([A-Za-z0-9]+)$", invocation.symbol)
                        affliction = "AFFLICTION." + slugify_ascii_type_name(generic.group(1)) if generic else None
                        if not affliction: raise SourceExtractionError(f"unresolved initial affliction: {invocation.symbol}")
                        amount=value_expression(invocation.arguments[-1],field_name="affliction amount",instruction_index=index)
                        effect={"kind":"afflictCard","model":affliction};prov=_slice(record,{index}, {"effect":effect,"value":amount})
                        fact=_fact(owner_model="POWER_OWNER."+model,applicable_models=[],stage="beforeCombatStart",
                                   trigger="beforeCombatStart",ordinal=ordinal,effect=effect,
                                   recipient={"kind":"eligiblePlayerCombatCards"},value=amount,unit="afflictionAmount",provenance=prov,
                                   condition={"kind":"sourcePredicate","classification":"sourceCardEligibilityPredicate","symbolSignature":record["symbolSignature"]})
                        facts.append(fact);effect_refs.append(fact["factId"]);ordinal+=1
                        decisions.append(_call_decision(root_id="POWER."+model,record=record,invocation=invocation,classification="normalizedGameplayEffect",role="afflictCard"));continue
                    if member == "set_BaseValue" and owner.endswith("DynamicVar"):
                        value=value_expression(invocation.arguments[0],field_name="Power dynamic variable",instruction_index=index)
                        effect={"kind":"setState","member":invocation.symbol};prov=_slice(record,{index}, {"effect":effect,"value":value})
                        fact=_fact(owner_model="POWER_OWNER."+model,applicable_models=[],stage="powerAfterApplied",
                                   trigger="powerAfterApplied",ordinal=ordinal,effect=effect,recipient={"kind":"appliedPowerDynamicVariable"},
                                   value=value,unit="playerCount",provenance=prov,source_inputs=["RUNTIME.RUN.PLAYER_COUNT"])
                        facts.append(fact);effect_refs.append(fact["factId"]);ordinal+=1
                        decisions.append(_call_decision(root_id="POWER."+model,record=record,invocation=invocation,classification="normalizedGameplayEffect",role="powerDynamicVariable"));continue
                    if member.startswith(("get_","op_")) or invocation.signature.returns.kind != "void":
                        decisions.append(_call_decision(root_id="POWER."+model,record=record,invocation=invocation,classification="sourceQuery",role="sourceValueOrPredicate"));continue
                    if member==".ctor" or owner.startswith(("System.","<TypeSpec:")):
                        decisions.append(_call_decision(root_id="POWER."+model,record=record,invocation=invocation,classification="sourceProvenNonGameplayPlumbing",role="compilerCollectionOrContext"));continue
                    raise SourceExtractionError(f"unclassified selected Power hook invocation: {invocation.symbol}")
            hook_rows.append({"classification":classification,"effectiveMethod":assembly.method_symbol(method_index),
                              "effectFactRefs":effect_refs,"hook":hook_name,"inheritancePath":path,"method":_method(record)})
        rows.append({"canonicalPower":model,"hooks":hook_rows,"sourceType":source_type})
    return sorted(rows,key=lambda row:row["canonicalPower"]),facts,decisions


def validate_initial_state(value: Any, *, reachable_models: set[str], encounter_ids: set[str]) -> None:
    if not isinstance(value, dict): raise SourceExtractionError("initialState must be an object")
    required={"constructorDecisions","encounterInitializerDecisions","encounterInitializers","externalHookBoundary","initialStateFacts","initialStateOwners",
              "initializationChain","invocationDecisions","powerHookClosure","runtimeStateContracts","sourceDenominators","summary"}
    if set(value)!=required: raise SourceExtractionError(f"initialState keys mismatch: {sorted(set(value)^required)}")
    roots=value["encounterInitializers"]
    if len(roots)!=len(encounter_ids) or {r["canonicalEncounter"] for r in roots}!={"ENCOUNTER."+x for x in encounter_ids}:
        raise SourceExtractionError("initialState encounter initializer coverage incomplete")
    initializer_decisions=value["encounterInitializerDecisions"]
    initializer_ids={row.get("decisionId") for row in initializer_decisions}
    if len(initializer_ids)!=len(initializer_decisions) or None in initializer_ids:
        raise SourceExtractionError("duplicate/missing encounter initializer decision")
    for root in roots:
        refs=root["constructionDecisionRefs"]+root["rngDecisionRefs"]
        if any(ref not in initializer_ids for ref in refs):
            raise SourceExtractionError("encounter initializer has broken decision ref")
    owners=value["initialStateOwners"]
    if len(owners)!=len(reachable_models) or {r["ownerModel"] for r in owners}!=reachable_models:
        raise SourceExtractionError("initialState owner coverage incomplete")
    if any(r["classification"] not in _OWNER_CLASSES for r in owners): raise SourceExtractionError("initialState owner classification invalid")
    facts=value["initialStateFacts"]; ids=set(); fact_by_id={}
    for row in facts:
        fact_id=row.get("factId")
        if not isinstance(fact_id,str) or fact_id in ids: raise SourceExtractionError(f"duplicate/missing initial fact ID: {fact_id}")
        ids.add(fact_id);fact_by_id[fact_id]=row
        if row.get("stage") not in _STAGE_ORDER or row.get("effect",{}).get("kind") not in _EFFECT_KINDS:
            raise SourceExtractionError(f"unsupported initial fact {fact_id}")
        if row["ownerModel"].startswith("MONSTER.") and row["ownerModel"] not in reachable_models:
            raise SourceExtractionError(f"initial fact owner is not reachable: {fact_id}")
        base=row.get("baseValue",{})
        if set(base)!={"expression","unit","valueType"} or validate_expression(base["expression"])!=base["valueType"]:
            raise SourceExtractionError(f"invalid initial fact base value: {fact_id}")
        owner_model=row["ownerModel"]; applicable=row.get("applicableModels")
        if owner_model.startswith("MONSTER."):
            if not isinstance(applicable,list) or not applicable or owner_model not in applicable or not set(applicable)<=reachable_models:
                raise SourceExtractionError(f"missing/unknown initial applicability edge: {fact_id}")
        elif not owner_model.startswith("POWER_OWNER.POWER.") or applicable != []:
            raise SourceExtractionError(f"unsupported initial owner/applicability: {fact_id}")
        condition=row.get("condition")
        if condition == {"kind":"unconditional"}:
            pass
        elif (not isinstance(condition,dict) or set(condition)!={"classification","kind","symbolSignature"}
              or condition.get("kind")!="sourcePredicate" or condition.get("classification") not in _INITIAL_PREDICATES
              or " sig:" not in condition.get("symbolSignature","")):
            raise SourceExtractionError(f"unsupported initial condition: {fact_id}")
        if row.get("recipient") not in ({"kind": kind} for kind in _INITIAL_RECIPIENTS):
            raise SourceExtractionError(f"unsupported initial recipient: {fact_id}")
        final=row.get("finalValueContract")
        if not isinstance(final,dict) or set(final)!={"classification","runtimeModifierInputs","scalingRefs"} or final["classification"]!="intrinsicRequestedBaseline":
            raise SourceExtractionError(f"invalid initial final-value contract: {fact_id}")
        provenance=row.get("provenance",{})
        for key in ("assemblySha256","methodBodySha256","normalizedInstructionsSha256","normalizedSliceSha256","semanticWitnessSha256"):
            digest=provenance.get(key)
            if not isinstance(digest,str) or len(digest)!=64: raise SourceExtractionError(f"initial fact lacks {key}: {fact_id}")
    for owner in owners:
        refs=owner["factRefs"]
        if any(ref not in ids for ref in refs): raise SourceExtractionError("initial owner has broken fact ref")
        if (owner["classification"]=="orderedGameplayEffects") != bool(refs):
            raise SourceExtractionError("initial owner effects/classification mismatch")
        if owner["effectiveHook"].startswith("MegaCrit.Sts2.Core.Models.MonsterModel::AfterAddedToRoom") and owner["classification"]!="sourceProvenNoOp":
            raise SourceExtractionError("base no-op was not source-inspected")
    decisions=value["invocationDecisions"]
    decision_ids=set()
    for row in decisions:
        if row.get("classification") not in _CALL_CLASSES: raise SourceExtractionError("initial invocation classification invalid")
        if row.get("decisionId") in decision_ids: raise SourceExtractionError("duplicate initial invocation decision")
        decision_ids.add(row.get("decisionId"))
        proof=row.get("provenance",{})
        if not isinstance(proof.get("methodBodySha256"),str) or len(proof["methodBodySha256"])!=64:
            raise SourceExtractionError("initial invocation decision lacks provenance")
    contracts=value["runtimeStateContracts"]; contract_ids={r.get("contractId") for r in contracts}
    if len(contract_ids)!=len(contracts) or None in contract_ids: raise SourceExtractionError("duplicate/missing runtime contract ID")
    for contract in contracts:
        if contract.get("ownership") not in _RUNTIME_OWNERSHIP or "domain" not in contract or not contract.get("readSites"):
            raise SourceExtractionError(f"runtime contract is not closed: {contract.get('contractId')}")
        for site in contract.get("updateSites",[]):
            if "factRef" in site and site["factRef"] not in ids: raise SourceExtractionError("runtime contract has broken fact ref")
    for fact in facts:
        refs=set(fact["sourceStateInputs"]) | set(fact["finalValueContract"]["runtimeModifierInputs"])
        if not refs <= contract_ids:
            raise SourceExtractionError(f"initial fact has unregistered runtime input: {fact['factId']} {sorted(refs-contract_ids)}")
    for row in value["powerHookClosure"]:
        if not row.get("hooks") or len(row["hooks"])!=3: raise SourceExtractionError("Power hook closure incomplete")
        for hook in row["hooks"]:
            if any(ref not in ids for ref in hook["effectFactRefs"]): raise SourceExtractionError("Power hook broken fact ref")
    if len(value["constructorDecisions"])!=5 or len(value["invocationDecisions"])!=1092 or len(value["runtimeStateContracts"])!=47:
        raise SourceExtractionError("initial-state closed denominator drift")
    if len(value["powerHookClosure"])!=41 or len(value["initializationChain"])!=7 or sum(len(row["declarations"]) for row in value["externalHookBoundary"])!=29:
        raise SourceExtractionError("initial Power/chain/boundary denominator drift")
    expected_denominators={
        "constructorExplicitWrites":5,"constructorOwners":4,
        "directSinkSitesByKind":{"applyPower":54,"gainBlock":1,"setCurrentHp":1,"setMaxAndCurrentHp":1},
        "effectiveHookImplementations":59,"encounterGenerationOwners":89,"generatorSetterSites":25,
        "generatorSetterOwners":13,"generatorConstructionSites":137,"generatorRngSites":38,
        "nonRosterInitializationRngRoots":5,"initialStateModels":108,"powerModels":41,
    }
    if value["sourceDenominators"]!=expected_denominators:
        raise SourceExtractionError("initial-state source denominator drift")
    summary=value["summary"]
    expected={"encounterRoots":len(encounter_ids),"modelOwners":len(reachable_models),"facts":len(facts),
              "invocationDecisions":len(decisions),"runtimeContracts":len(contracts),"powerModels":len(value["powerHookClosure"])}
    for key,count in expected.items():
        if summary.get(key)!=count: raise SourceExtractionError(f"initialState summary mismatch for {key}")


def extract_initial_state(
    assembly: AssemblyMetadata, assembly_sha256: str, monsters: Sequence[Mapping[str, Any]],
    encounters: Sequence[Mapping[str, Any]], *, reachable_models: set[str] | None = None,
    power_scaling: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    explicit_reachable = reachable_models
    source_to_model={row["sourceType"]:"MONSTER."+row["canonicalId"] for row in monsters
                     if (("MONSTER."+row["canonicalId"] in explicit_reachable) if explicit_reachable is not None
                         else row.get("reachability",{}).get("classification") in {"ordinaryReachable","eventOnly"})}
    if len(source_to_model)!=108 or len(set(source_to_model.values()))!=108:
        raise SourceExtractionError(f"initial-state reachable model denominator is not exact: {len(source_to_model)}")
    reachable=set(source_to_model.values()); encounter_ids={row["canonicalId"] for row in encounters}
    if len(encounters)!=89 or len(encounter_ids)!=89: raise SourceExtractionError("initial-state encounter denominator is not exact")
    roots,generator_facts,initializer_decisions=_encounter_initializers(assembly,assembly_sha256,encounters,reachable)
    constructor_facts,constructor_decisions=_constructor_defaults(assembly,assembly_sha256,source_to_model)
    owners,hook_facts,hook_decisions,direct_counts,power_types=_after_added(assembly,assembly_sha256,source_to_model)
    power_rows,power_facts,power_decisions=_power_hook_closure(assembly,assembly_sha256,power_types)
    facts=sorted(generator_facts+constructor_facts+hook_facts+power_facts,key=lambda row:row["factId"])
    scaled_powers = {row["canonicalPower"] for row in (power_scaling or {}).get("optIns", [])}
    for fact in facts:
        if fact["effect"]["kind"] == "applyPower" and fact["effect"]["model"] in scaled_powers:
            fact["finalValueContract"]["scalingRefs"] = ["multiplayerScaling.power"]
    decisions=sorted(hook_decisions+power_decisions,key=lambda row:row["decisionId"])
    boundaries,chain=_external_boundaries(assembly,assembly_sha256)
    contracts=_runtime_contracts(facts,assembly,assembly_sha256)
    result={
        "constructorDecisions":sorted(constructor_decisions,key=lambda row:row["decisionId"]),
        "encounterInitializerDecisions":sorted(initializer_decisions,key=lambda row:row["decisionId"]),
        "encounterInitializers":roots,"externalHookBoundary":boundaries,"initialStateFacts":facts,
        "initialStateOwners":owners,"initializationChain":chain,"invocationDecisions":decisions,
        "powerHookClosure":power_rows,"runtimeStateContracts":contracts,
        "sourceDenominators":{
            "constructorExplicitWrites":len(constructor_decisions),"constructorOwners":len({r["ownerModel"] for r in constructor_facts}),
            "directSinkSitesByKind":direct_counts,"effectiveHookImplementations":len({r["effectiveHook"] for r in owners}),
            "encounterGenerationOwners":len(roots),"generatorSetterSites":len(generator_facts),
            "generatorSetterOwners":len({r["encounterApplicability"] for r in generator_facts}),
            "generatorConstructionSites":sum(len(row["constructionDecisionRefs"]) for row in roots),
            "generatorRngSites":sum(len(row["rngDecisionRefs"]) for row in roots),
            "nonRosterInitializationRngRoots":sum(any(
                decision["classification"] == "nonRosterInitializationRng"
                for ref in row["rngDecisionRefs"] for decision in initializer_decisions if decision["decisionId"] == ref
            ) for row in roots),
            "initialStateModels":len(owners),"powerModels":len(power_rows),
        },
        "summary":{
            "encounterRoots":len(roots),"facts":len(facts),"invocationDecisions":len(decisions),
            "modelOwners":len(owners),"powerModels":len(power_rows),"runtimeContracts":len(contracts),
        },
    }
    validate_initial_state(result,reachable_models=reachable,encounter_ids=encounter_ids)
    return result
