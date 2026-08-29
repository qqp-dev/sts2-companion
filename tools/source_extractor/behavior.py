"""Deterministic source combat-behavior extraction for pinned v0.111.0.

The extractor reads metadata and CIL only.  It deliberately separates the
registration/graph construction methods from action state-machine bodies and
retains a normalized witness for every fact.  Research counts are checked only
after all records have been derived from the assembly.
"""
from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import re
from typing import TYPE_CHECKING, Any, Mapping

from .canonical import slugify_ascii_type_name, witness_sha256
from .errors import SourceExtractionError
from .invocations import ClosedWorldInvocationAudit

if TYPE_CHECKING:
    from .metadata import AssemblyMetadata
from .cil_eval import (CilDataFlow, CilType, Invocation, SymbolicValue, contains_origin,
                       decode_method_signature, ensure_resolved, integer_constant,
                       value_expression)

MONSTER_NS = "MegaCrit.Sts2.Core.Models.Monsters."
MOVE_CTOR = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState::.ctor sig:200301"
MACHINE_CTOR = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MonsterMoveStateMachine::.ctor"
FOLLOW_UP = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState::set_FollowUpState"
MUST_ONCE = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.MoveState::set_MustPerformOnceBeforeTransitioning"
RANDOM_CTOR = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.RandomBranchState::.ctor"
RANDOM_ADD = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.RandomBranchState::AddBranch"
CONDITIONAL_CTOR = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.ConditionalBranchState::.ctor"
CONDITIONAL_ADD = "MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.ConditionalBranchState::AddState"
ASYNC_ATTRIBUTE = "System.Runtime.CompilerServices.AsyncStateMachineAttribute::.ctor"

# Every gameplay sink observed in current monster action state machines.  The
# first fragment is deliberately the most specific where names overlap.
# Expected sites are regression pins discovered from the source-derived closed
# invocation census. Classification never depends on these counts.
REQUIRED_SEMANTIC_FIELDS = {
    "attack": 2, "attackHitCount": 1, "applyPower": 3, "gainBlock": 2,
    "addStatusCard": 3, "addGeneratedCard": 3, "summon": 3,
    "escape": 1, "heal": 2, "removeCard": 1, "kill": 2,
    "removePower": 2, "stateWrite": 2,
}
EXPECTED_SINKS = {
    "attack": 204, "applyPower": 126, "attackHitCount": 49,
    "gainBlock": 23, "addStatusCard": 14, "addGeneratedCard": 6,
    "summon": 5, "escape": 2, "heal": 2, "removeCard": 1,
    "kill": 2, "removePower": 6, "stateWrite": 51,
}
HELPERS: Mapping[str, tuple[str, str]] = {
    "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment::ReattachMove": ("reattach", "MegaCrit.Sts2.Core.Models.Powers.ReattachPower::DoReattach"),
    "MegaCrit.Sts2.Core.Models.Monsters.Fabricator::FabricateMove": ("fabricate", "MegaCrit.Sts2.Core.Models.Monsters.Fabricator::Spawn"),
    "MegaCrit.Sts2.Core.Models.Monsters.KnowledgeDemon::CurseOfKnowledgeMove": ("chooseCurse", "MegaCrit.Sts2.Core.Models.Monsters.KnowledgeDemon::ChooseCurse"),
    "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg::HatchMove": ("hatch", "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg::Hatch"),
    "MegaCrit.Sts2.Core.Models.Monsters.WaterfallGiant::AboutToBlowMove": ("pressureState", "MegaCrit.Sts2.Core.Models.Monsters.WaterfallGiant::set_SteamEruptionDamage"),
}

def const(value: int) -> dict[str, Any]:
    return {"kind": "constant", "value": value, "valueType": "integer"}


def _ldc(instruction: Mapping[str, Any]) -> int | None:
    return integer_constant(instruction)


INTENT_KINDS = {
    "SingleAttackIntent": "attack", "MultiAttackIntent": "attack",
    "DefendIntent": "block", "StatusIntent": "status",
    "BuffIntent": "buff", "DebuffIntent": "debuff",
    "CardDebuffIntent": "cardDebuff", "SummonIntent": "summon",
    "HealIntent": "heal", "EscapeIntent": "escape",
    "SleepIntent": "sleep", "StunIntent": "stun",
    "UnknownIntent": "unknown", "HiddenIntent": "hidden",
    "DeathBlowIntent": "deathBlow",
}


def _method(record: Mapping[str, Any], *, include_slice: bool = False) -> dict[str, Any]:
    keys = ("assemblySha256", "cilInstructionsSha256", "diagnosticMetadataToken",
            "metadataSignature", "methodBodySha256", "normalizedInstructionsSha256",
            "symbolSignature")
    out = {key: record[key] for key in keys}
    if include_slice:
        normalized = [{"opcode": x["opcode"], "operand": x["operand"]} for x in record["instructions"]]
        out["normalizedSliceSha256"] = witness_sha256(normalized)
    return out


def _slice_provenance(record: Mapping[str, Any], instructions: list[Mapping[str, Any]], semantic: Any) -> dict[str, Any]:
    normalized = [{"opcode": x["opcode"], "operand": x["operand"]} for x in instructions]
    return {
        **_method(record),
        "normalizedSliceSha256": witness_sha256(normalized),
        "semanticWitnessSha256": witness_sha256(semantic),
    }


def _local(opcode: str, operand: Any) -> str | None:
    m = re.fullmatch(r"(?:ld|st)loc\.(\d)", opcode)
    if m: return m.group(1)
    if opcode in {"ldloc", "ldloc.s", "stloc", "stloc.s"}:
        m = re.fullmatch(r"local\(0x([0-9a-fA-F]{4})\)", str(operand))
        if m: return str(int(m.group(1), 16))
    return None


def _string(operand: Any) -> str | None:
    if isinstance(operand, str) and operand.startswith("string:"):
        return operand[7:]
    return None


def _owner_and_name(symbol: str) -> tuple[str, str]:
    head = symbol.split(" sig:", 1)[0]
    owner, name = head.split("::", 1)
    return owner, name


def _custom_attribute_type_name(blob: bytes) -> str:
    # ECMA-335 custom attribute: 0x0001 prolog, SerString, zero named args.
    if len(blob) < 5 or blob[:2] != b"\x01\x00" or blob[-2:] != b"\x00\x00":
        raise SourceExtractionError("malformed AsyncStateMachineAttribute blob")
    first = blob[2]
    if first == 0xFF:
        raise SourceExtractionError("null async state-machine type")
    if first & 0x80 == 0:
        length, pos = first, 3
    elif first & 0xC0 == 0x80 and len(blob) >= 6:
        length, pos = ((first & 0x3F) << 8) | blob[3], 4
    else:
        raise SourceExtractionError("unsupported async attribute SerString length")
    if pos + length + 2 != len(blob):
        raise SourceExtractionError("async attribute SerString length mismatch")
    try: return blob[pos:pos + length].decode("utf-8")
    except UnicodeDecodeError as exc: raise SourceExtractionError("invalid async attribute UTF-8") from exc


def _async_map(assembly: AssemblyMetadata) -> dict[int, int]:
    type_index = {name: index for index, name in assembly.type_names.items()}
    result: dict[int, int] = {}
    for row in assembly.md.CustomAttribute.rows:
        if not row.Parent or row.Parent.table.name != "MethodDef":
            continue
        typ = row.Type
        token = (0x0A000000 if typ.table.name == "MemberRef" else 0x06000000) | typ.row_index
        ctor = assembly.resolve_token(token)
        if not ctor.startswith(ASYNC_ATTRIBUTE):
            continue
        generated = _custom_attribute_type_name(bytes(row.Value.value))
        ti = type_index.get(generated)
        if ti is None:
            raise SourceExtractionError(f"unresolved async state-machine type {generated}")
        moves = [m.row_index for m in assembly.md.TypeDef.rows[ti - 1].MethodList if str(m.row.Name) == "MoveNext"]
        if len(moves) != 1:
            raise SourceExtractionError(f"async state-machine {generated} has {len(moves)} MoveNext methods")
        method = row.Parent.row_index
        if method in result:
            raise SourceExtractionError(f"duplicate async state-machine attribute on method {method}")
        result[method] = moves[0]
    return result


def _state_id_to_key(state_id: str) -> str:
    return state_id[:-5] if state_id.endswith("_MOVE") else state_id


def _canonical_for_type(source_type: str, source_to_model: Mapping[str, str]) -> str:
    model = source_to_model.get(source_type)
    if model is None:
        # DecimillipedeSegment is abstract but its three concrete subclasses use
        # the one assembly-proven behavior implementation/root.
        if source_type == MONSTER_NS + "DecimillipedeSegment":
            return "MONSTER.DECIMILLIPEDE_SEGMENT"
        raise SourceExtractionError(f"behavior type has no canonical monster identity: {source_type}")
    return model


def _title(state_id: str, canonical: str, localization: Mapping[str, Any], *, pck_sha256: str, blob_sha256: str) -> dict[str, Any]:
    root = canonical.removeprefix("MONSTER.")
    if root in {"DECIMILLIPEDE_FRONT", "DECIMILLIPEDE_MIDDLE", "DECIMILLIPEDE_BACK"}:
        root = "DECIMILLIPEDE_SEGMENT"
    direct_key = f"{root}.moves.{_state_id_to_key(state_id)}.title"
    key = direct_key
    value = localization.get(key)
    alias_kind = None
    # The source lookup normalizes a second internal MOVE variant to the same
    # display key while registration identity remains distinct.
    if value is None and state_id.endswith("_MOVE_2"):
        alias_key = f"{root}.moves.{state_id[:-7]}.title"
        if alias_key in localization:
            key, value, alias_kind = alias_key, localization[alias_key], "secondInternalMoveVariant"
    base = {"localizationKey": key, "localizationRoot": root, "requestedLocalizationKey": direct_key}
    if value is None:
        return {**base, "classification": "missingLocalization"}
    if not isinstance(value, str) or not value:
        raise SourceExtractionError(f"invalid move localization {key}")
    return {**base, "classification": "localized", "english": value,
            **({"aliasKind": alias_kind} if alias_kind else {}),
            "provenance": {"blobSha256": blob_sha256, "key": key, "pckSha256": pck_sha256,
                           "valueSha256": hashlib.sha256(value.encode()).hexdigest()}}


def _delegate_binding(value: SymbolicValue, *, instruction_index: int) -> dict[str, Any]:
    ensure_resolved(value, "intent delegate receiver", instruction_index)
    if value.kind == "argument" and isinstance(value.data, str) and value.data.isdigit():
        return {"argumentIndex": int(value.data), "kind": "methodArgument"}
    if value.kind == "null":
        return {"kind": "null"}
    raise SourceExtractionError(
        f"unsupported intent delegate receiver at instruction {instruction_index}: {value.kind}"
    )


def _unique_function(value: SymbolicValue, *, instruction_index: int) -> str:
    ensure_resolved(value, "intent delegate target", instruction_index)
    alternatives = value.operands if value.kind == "join" else (value,)
    targets = {item.data for item in alternatives
               if item.kind == "function" and isinstance(item.data, str)}
    if len(targets) != 1 or len(targets) != len(alternatives):
        raise SourceExtractionError(
            f"unsupported or non-unique intent delegate target at instruction {instruction_index}"
        )
    return next(iter(targets))


def _boolean_intent_argument(value: SymbolicValue, *, instruction_index: int) -> dict[str, Any]:
    ensure_resolved(value, "boolean intent argument", instruction_index)
    alternatives = value.operands if value.kind == "join" else (value,)
    constants = {item.data for item in alternatives
                 if item.kind == "constant" and type(item.data) is int and item.data in {0, 1}}
    if len(constants) != 1 or len(constants) != len(alternatives):
        raise SourceExtractionError(
            f"unsupported or non-unique boolean intent argument at instruction {instruction_index}"
        )
    return {"kind": "constant", "value": bool(next(iter(constants))), "valueType": "boolean"}


def _intent_argument(value: SymbolicValue, parameter: CilType, *, instruction_index: int,
                     assembly: AssemblyMetadata | None, assembly_sha256: str | None) -> dict[str, Any]:
    numeric = parameter.numeric
    if numeric in {"integer", "decimal"}:
        expression = value_expression(value, field_name="intent argument", instruction_index=instruction_index)
        if expression.get("valueType") != numeric:
            raise SourceExtractionError(
                f"intent argument type mismatch at instruction {instruction_index}: "
                f"stack expression is {expression.get('valueType')}, signature requires {numeric}"
            )
        return expression
    if parameter.kind == "bool":
        return _boolean_intent_argument(value, instruction_index=instruction_index)
    if parameter.kind != "genericInstance":
        raise SourceExtractionError(
            f"unsupported intent parameter type at instruction {instruction_index}: {parameter.kind}"
        )

    ensure_resolved(value, "intent delegate argument", instruction_index)
    alternatives = value.operands if value.kind == "join" else (value,)
    projected: list[dict[str, Any]] = []
    for candidate in alternatives:
        if candidate.kind != "new" or not isinstance(candidate.data, str):
            raise SourceExtractionError(
                f"unsupported intent delegate value at instruction {instruction_index}: {candidate.kind}"
            )
        constructor = decode_method_signature(candidate.data)
        expected = (CilType("object"), CilType("nativeInt"))
        if not constructor.has_this or constructor.returns.kind != "void" or constructor.parameters != expected:
            raise SourceExtractionError(
                f"unsupported intent delegate constructor at instruction {instruction_index}: {candidate.data}"
            )
        if len(candidate.operands) != 2:
            raise SourceExtractionError(
                f"intent delegate constructor argument mismatch at instruction {instruction_index}"
            )
        binding = _delegate_binding(candidate.operands[0], instruction_index=instruction_index)
        target = _unique_function(candidate.operands[1], instruction_index=instruction_index)
        if assembly is None or assembly_sha256 is None:
            raise SourceExtractionError("intent delegate metadata resolver is required")
        owner, name = _owner_and_name(target)
        matches = [index for index in assembly.find_methods(owner, name)
                   if assembly.method_symbol(index) == target]
        if len(matches) != 1:
            raise SourceExtractionError(f"intent delegate target is not unique: {target}")
        target_record = assembly.method_record(matches[0], assembly_sha256)
        target_flow = CilDataFlow(target_record["instructions"])
        target_flow.run()
        result_expression = value_expression(
            target_flow.return_value(target), field_name="intent delegate result",
            instruction_index=instruction_index,
        )
        projected.append({
            "binding": binding,
            "constructorSymbolSignature": candidate.data,
            "kind": "sourceDelegate",
            "resultExpression": result_expression,
            "targetMethod": _method(target_record, include_slice=True),
        })
    if not projected or any(item != projected[0] for item in projected[1:]):
        raise SourceExtractionError(
            f"non-unique intent delegate argument at instruction {instruction_index}"
        )
    return projected[0]


def _intent_records(segment: list[dict[str, Any]], record: Mapping[str, Any], *,
                    invocations: Mapping[int, Invocation] | None = None,
                    assembly: AssemblyMetadata | None = None,
                    assembly_sha256: str | None = None) -> list[dict[str, Any]]:
    if invocations is None:
        invocations = CilDataFlow(record["instructions"]).run()
    segment_offsets = {item["offsetDiagnostic"] for item in segment}
    sites: list[tuple[int, str, re.Match[str]]] = []
    for index, instruction in enumerate(record["instructions"]):
        operand = instruction.get("operand")
        if (instruction.get("offsetDiagnostic") not in segment_offsets
                or instruction.get("opcode") != "newobj" or not isinstance(operand, str)):
            continue
        match = re.search(r"\.Intents\.([A-Za-z]+Intent)::\.ctor", operand)
        if match:
            sites.append((index, operand, match))

    result: list[dict[str, Any]] = []
    for index, operand, match in sites:
        class_name = match.group(1)
        kind = INTENT_KINDS.get(class_name)
        if kind is None:
            raise SourceExtractionError(f"unknown constructed intent {class_name}")
        invocation = invocations.get(index)
        if invocation is None or invocation.symbol != operand:
            raise SourceExtractionError(
                f"intent constructor stack contract unresolved in {record['symbolSignature']} at {index}"
            )
        if len(invocation.arguments) != len(invocation.signature.parameters):
            raise SourceExtractionError(
                f"intent constructor argument count mismatch in {record['symbolSignature']} at {index}"
            )
        arguments = [
            _intent_argument(value, parameter, instruction_index=index,
                             assembly=assembly, assembly_sha256=assembly_sha256)
            for value, parameter in zip(invocation.arguments, invocation.signature.parameters)
        ]
        semantic = {
            "arguments": arguments,
            "constructorSymbolSignature": invocation.symbol,
            "intentClass": class_name,
            "kind": kind,
        }
        result.append({
            **semantic,
            "provenance": _slice_provenance(
                record, _slice_for_invocation(record, invocation), semantic
            ),
        })
    return result



def _param_count(signature: str) -> int | None:
    match = re.search(r" sig:(20|00|10)([0-9a-fA-F]{2})", signature)
    if not match: return None
    return int(match.group(2), 16)


def _is_cached_lambda_field(operand: Any) -> bool:
    return isinstance(operand, str) and "+<>c::<>9" in operand



def _compile_graph(record: dict[str, Any], canonical: str, graph_id: str, source_type: str) -> dict[str, Any]:
    instructions = record["instructions"]
    by_offset = {item["offsetDiagnostic"]: index for index, item in enumerate(instructions)}
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    initials: list[str] = []
    seen: set[tuple[Any, ...]] = set()

    def node_from(value: Any) -> str | None:
        if isinstance(value, dict) and value.get("kind") == "graphNode":
            return value["nodeId"]
        return None

    def add_node(kind: str, state_id: str) -> dict[str, Any]:
        node_id = graph_id + "/" + state_id
        nodes[node_id] = {"kind": kind, "nodeId": node_id, "stateId": state_id, **({"mustPerformOnce": True} if node_id in nodes and nodes[node_id].get("mustPerformOnce") else {})}
        if node_id in nodes and "mustPerformOnce" in nodes[node_id]:
            pass
        if node_id not in nodes:
            nodes[node_id] = {"kind": kind, "nodeId": node_id, "stateId": state_id}
        else:
            nodes[node_id]["kind"] = kind
            nodes[node_id]["stateId"] = state_id
        return {"kind": "graphNode", "nodeId": node_id}

    def snapshot(pc: int, stack: list[Any], locals_: dict[str, Any]) -> tuple[Any, ...]:
        def freeze(value: Any) -> Any:
            if isinstance(value, dict):
                return tuple(sorted((k, freeze(v)) for k, v in value.items()))
            if isinstance(value, (list, tuple)):
                return tuple(freeze(v) for v in value)
            return value
        return (pc, freeze(stack), freeze(sorted(locals_.items())))

    def run(pc: int, stack: list[Any], locals_: dict[str, Any], fields: dict[str, Any], fuel: int) -> None:
        if fuel <= 0:
            raise SourceExtractionError(f"graph interpreter bound exceeded in {record['symbolSignature']}")
        key = snapshot(pc, stack, locals_)
        if key in seen:
            return
        seen.add(key)
        while 0 <= pc < len(instructions):
            item = instructions[pc]
            opcode, operand = item["opcode"], item["operand"]
            def push(value: Any) -> None:
                if len(stack) > 256:
                    raise SourceExtractionError(f"graph stack overflow in {record['symbolSignature']}")
                stack.append(value)
            def pop() -> Any:
                if not stack:
                    raise SourceExtractionError(f"graph stack underflow in {record['symbolSignature']} at {opcode}")
                return stack.pop()
            const_value = _ldc(item)
            if const_value is not None:
                push(("int", const_value))
            elif opcode == "ldc.r4":
                push(("float", operand))
            elif opcode == "ldarg.0":
                push(("self", source_type))
            elif opcode == "ldstr":
                text = _string(operand)
                if text is None:
                    raise SourceExtractionError("non-string ldstr")
                push(("string", text))
            elif opcode == "ldftn":
                push(("ftn", operand))
            elif opcode == "dup":
                push(stack[-1])
            elif opcode == "pop":
                pop()
            elif opcode.startswith("stloc"):
                locals_[_local(opcode, operand) or ""] = pop()
            elif opcode.startswith("ldloc"):
                push(locals_[_local(opcode, operand) or ""])
            elif opcode == "ldsfld":
                push(("field", operand, _is_cached_lambda_field(operand)))
            elif opcode == "stsfld":
                pop()
            elif opcode in {"ldfld", "ldflda"}:
                pop(); push(("field", operand, False))
            elif opcode == "newarr":
                pop(); push(("array", operand))
            elif opcode == "stelem.ref":
                pop(); pop(); pop()
            elif opcode == "rem":
                right, left = pop(), pop(); push(("rem", left, right))
            elif opcode in {"call", "callvirt", "newobj"}:
                if not isinstance(operand, str):
                    raise SourceExtractionError(f"unresolved call {operand}")
                if operand.startswith(MOVE_CTOR):
                    intents, action, state = pop(), pop(), pop()
                    if not (isinstance(state, tuple) and state[0] == "string"):
                        raise SourceExtractionError("move state id unresolved")
                    push(add_node("move", state[1]))
                elif operand.startswith(RANDOM_CTOR):
                    state = pop(); push(add_node("random", state[1]))
                elif operand.startswith(CONDITIONAL_CTOR):
                    state = pop(); push(add_node("conditional", state[1]))
                elif operand.startswith(FOLLOW_UP):
                    target, source = pop(), pop()
                    src, dst = node_from(source), node_from(target)
                    if src is None or dst is None:
                        raise SourceExtractionError("follow-up edge unresolved")
                    edges.append({"kind": "followUp", "from": src, "to": dst})
                elif operand.startswith(MUST_ONCE):
                    flag, source = pop(), pop()
                    node_id = node_from(source)
                    if node_id is None:
                        raise SourceExtractionError("must-once target unresolved")
                    nodes[node_id]["mustPerformOnce"] = True
                    push(source)
                elif operand.startswith(RANDOM_ADD):
                    count = _param_count(operand)
                    if count is None:
                        raise SourceExtractionError(f"unrecognized AddBranch signature {operand}")
                    args = [pop() for _ in range(count)]; receiver = pop()
                    src, dst = node_from(receiver), next((node_from(x) for x in reversed(args) if node_from(x)), None)
                    if src is None or dst is None:
                        raise SourceExtractionError("random branch unresolved")
                    weight = next((x[1] for x in args if isinstance(x, tuple) and x[0] == "int"), None)
                    predicate = next((x[1] for x in args if isinstance(x, tuple) and x[0] in {"ftn", "func"}), None)
                    edge = {"kind": "randomBranch", "from": src, "to": dst, "order": sum(e["kind"]=="randomBranch" and e["from"]==src for e in edges)}
                    if weight is not None: edge["weight"] = weight
                    if predicate is not None: edge["predicate"] = {"kind": "reference", "reference": predicate, "valueType": "boolean"}
                    edges.append(edge)
                elif operand.startswith(CONDITIONAL_ADD):
                    pred, target, receiver = pop(), pop(), pop()
                    src, dst = node_from(receiver), node_from(target)
                    if src is None or dst is None:
                        raise SourceExtractionError("conditional branch unresolved")
                    predicate_symbol = pred[1] if isinstance(pred, tuple) and pred[0] in {"ftn", "func"} else None
                    edge = {"kind": "conditionalBranch", "from": src, "to": dst, "order": sum(e["kind"]=="conditionalBranch" and e["from"]==src for e in edges)}
                    if predicate_symbol:
                        edge["predicate"] = {"kind": "reference", "reference": predicate_symbol, "valueType": "boolean"}
                    edges.append(edge)
                elif operand.startswith(MACHINE_CTOR):
                    initial, listing = pop(), pop()
                    node_id = node_from(initial)
                    if node_id is None:
                        raise SourceExtractionError("machine initial state unresolved")
                    initials.append(node_id)
                    push(("machine", node_id))
                elif operand.endswith("::.ctor sig:2002011c18") or operand.startswith("<TypeSpec:151281c102") or operand.startswith("<TypeSpec:151281bd01"):
                    method, receiver = pop(), pop()
                    push(("func", method[1] if isinstance(method, tuple) else method))
                elif "Intents." in operand and "::.ctor" in operand:
                    count = _param_count(operand) or 0
                    for _ in range(count): pop()
                    push(("intent", operand))
                elif operand.startswith("<TypeSpec:1512809901128848>::.ctor"):
                    push(("list", []))
                elif operand.startswith("<TypeSpec:1512809901128848>::Add"):
                    pop(); pop()
                elif "System.Array::Empty" in operand:
                    push(("array", "empty"))
                elif "::get_" in operand or "::set_" in operand or "HasValue" in operand or "GetValueOrDefault" in operand:
                    count = _param_count(operand)
                    if count is None:
                        raise SourceExtractionError(f"unrecognized getter signature {operand}")
                    instance = operand.split(" sig:",1)[-1].startswith("20")
                    args = [pop() for _ in range(count)]
                    if instance: pop()
                    name = operand.split("::",1)[-1]
                    if name.startswith("set_"):
                        if args: fields[name[4:].split(" ",1)[0]] = args[-1]
                    elif "HasValue" in operand:
                        push(("bool", "hasStockOverride"))
                    elif name.startswith("get_") and name.split(" ",1)[0][4:] in fields:
                        push(fields[name.split(" ",1)[0][4:]])
                    else:
                        push(("value", operand))
                else:
                    raise SourceExtractionError(f"unknown call on required graph slice: {operand} in {record['symbolSignature']}")
            elif opcode in {"br", "br.s"}:
                pc = by_offset[operand]
                continue
            elif opcode in {"brtrue", "brtrue.s", "brfalse", "brfalse.s", "beq", "beq.s", "bne.un.s"}:
                cond = pop()
                if isinstance(cond, tuple) and cond[0] == "field" and cond[2]:
                    pc += 1
                    continue
                target = by_offset[operand]
                run(pc + 1, copy.deepcopy(stack), copy.deepcopy(locals_), copy.deepcopy(fields), fuel - 1)
                run(target, copy.deepcopy(stack), copy.deepcopy(locals_), copy.deepcopy(fields), fuel - 1)
                return
            elif opcode == "ret":
                return
            else:
                raise SourceExtractionError(f"unknown opcode on required graph slice: {opcode} in {record['symbolSignature']}")
            pc += 1

    run(0, [], {}, {}, 64)
    if not nodes:
        raise SourceExtractionError(f"no graph nodes in {record['symbolSignature']}")
    unique_initials = list(dict.fromkeys(initials))
    seen_edges = []
    seen_keys = set()
    for edge in edges:
        key = (edge["kind"], edge["from"], edge["to"], edge.get("weight"), str(edge.get("predicate")))
        if key in seen_keys: continue
        seen_keys.add(key); seen_edges.append(edge)
    # Topology regression pins are constructor/assignment sites, including a
    # repeated follow-up assignment that collapses in the unique edge set.
    topology = {
        "conditionalBranches": sum(isinstance(x["operand"], str) and x["operand"].startswith(CONDITIONAL_ADD) for x in instructions),
        "conditionalNodes": sum(x["opcode"]=="newobj" and isinstance(x["operand"], str) and x["operand"].startswith(CONDITIONAL_CTOR) for x in instructions),
        "followUpEdges": sum(isinstance(x["operand"], str) and x["operand"].startswith(FOLLOW_UP) for x in instructions),
        "moveNodes": sum(x["opcode"]=="newobj" and isinstance(x["operand"], str) and x["operand"].startswith(MOVE_CTOR) for x in instructions),
        "mustOnceFlags": sum(isinstance(x["operand"], str) and x["operand"].startswith(MUST_ONCE) for x in instructions),
        "randomBranches": sum(isinstance(x["operand"], str) and x["operand"].startswith(RANDOM_ADD) for x in instructions),
        "randomNodes": sum(x["opcode"]=="newobj" and isinstance(x["operand"], str) and x["operand"].startswith(RANDOM_CTOR) for x in instructions),
    }
    return {
        "canonicalMonster": canonical,
        "edges": seen_edges,
        "graphId": graph_id,
        "initial": unique_initials[0] if len(unique_initials)==1 else unique_initials,
        "nodes": sorted(nodes.values(), key=lambda n: n["nodeId"]),
        "provenance": _slice_provenance(record, instructions, {"initial": unique_initials, "topology": topology}),
        "sourceType": source_type,
        "topology": topology,
    }


def _registration_rows(assembly: AssemblyMetadata, assembly_sha256: str, source_to_model: Mapping[str, str], reachable_models: set[str], localization: Mapping[str, Any], pck_sha256: str, blob_sha256: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    async_methods = _async_map(assembly)
    registrations: list[dict[str, Any]] = []
    graphs: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    required_intent_sites = 0
    required_intent_arguments = 0
    for type_index, source_type in sorted(assembly.type_names.items(), key=lambda x: x[1]):
        if not source_type.startswith(MONSTER_NS) or "+" in source_type:
            continue
        generated = assembly.find_methods(source_type, "GenerateMoveStateMachine")
        if not generated: continue
        if len(generated) != 1: raise SourceExtractionError(f"ambiguous GenerateMoveStateMachine for {source_type}")
        try: canonical = _canonical_for_type(source_type, source_to_model)
        except SourceExtractionError:
            # Only concrete helper/test/obsolete classes may be excluded.
            if source_type in source_to_model: raise
            continue
        method_index = generated[0]
        record = assembly.method_record(method_index, assembly_sha256)
        if canonical not in reachable_models and canonical != "MONSTER.DECIMILLIPEDE_SEGMENT":
            move_count = sum(x["opcode"] == "newobj" and isinstance(x["operand"], str) and x["operand"].startswith(MOVE_CTOR) for x in record["instructions"])
            excluded.append({"canonicalMonster": canonical, "classification": "waveAExcludedConcrete", "moveRegistrations": move_count, "sourceType": source_type, "provenance": _method(record, include_slice=True)})
            continue
        ins = record["instructions"]
        raw_intent_constructors = [
            item["operand"] for item in ins
            if item["opcode"] == "newobj" and isinstance(item["operand"], str)
            and re.search(r"\.Intents\.[A-Za-z]+Intent::\.ctor", item["operand"])
        ]
        required_intent_sites += len(raw_intent_constructors)
        required_intent_arguments += sum(
            len(decode_method_signature(symbol).parameters)
            for symbol in raw_intent_constructors
        )
        invocations = CilDataFlow(ins).run()
        move_sites = [i for i,x in enumerate(ins) if x["opcode"] == "newobj" and isinstance(x["operand"],str) and x["operand"].startswith(MOVE_CTOR)]
        graph_id = "GRAPH." + canonical.removeprefix("MONSTER.")
        graphs.append(_compile_graph(record, canonical, graph_id, source_type))
        previous = 0
        for ordinal, site in enumerate(move_sites):
            segment = ins[previous:site + 1]
            previous = site + 1
            strings = [(i,_string(x["operand"])) for i,x in enumerate(segment) if x["opcode"] == "ldstr" and _string(x["operand"]) is not None]
            ftns = [(i,x["operand"]) for i,x in enumerate(segment) if x["opcode"] == "ldftn" and isinstance(x["operand"],str)]
            if not strings or not ftns: raise SourceExtractionError(f"move constructor identity unresolved in {record['symbolSignature']} at {site}")
            state_id = strings[-1][1]
            action_symbol = ftns[0][1]
            owner, action_name = _owner_and_name(action_symbol)
            action_matches = assembly.find_methods(owner, action_name)
            action_matches = [x for x in action_matches if assembly.method_symbol(x) == action_symbol]
            if len(action_matches) != 1: raise SourceExtractionError(f"action symbol unresolved: {action_symbol}")
            action_index = action_matches[0]
            action_record = assembly.method_record(action_index, assembly_sha256)
            move_next_index = async_methods.get(action_index)
            if move_next_index is None:
                # The only accepted synchronous action is exactly Task.CompletedTask.
                normalized = [(x["opcode"],x["operand"]) for x in action_record["instructions"]]
                expected = [("call", "System.Threading.Tasks.Task::get_CompletedTask sig:0000128121"), ("ret", None)]
                if normalized != expected: raise SourceExtractionError(f"unrecognized synchronous move action {action_symbol}")
                execution = {"kind": "synchronousNoOp", "method": _method(action_record, include_slice=True)}
            else:
                move_next = assembly.method_record(move_next_index, assembly_sha256)
                execution = {"kind": "asyncStateMachine", "moveNext": _method(move_next, include_slice=True)}
            identity = {"actionSymbol": action_symbol, "canonicalMonster": canonical,
                        "generateSymbol": record["symbolSignature"], "ordinal": ordinal,
                        "stateId": state_id}
            registrations.append({
                "action": {"method": _method(action_record), "symbolSignature": action_symbol},
                "canonicalId": canonical + "#" + state_id,
                "canonicalMonster": canonical,
                "execution": execution,
                "graphId": graph_id,
                "identityWitnessSha256": witness_sha256(identity),
                "intents": _intent_records(
                    segment, record, invocations=invocations, assembly=assembly,
                    assembly_sha256=assembly_sha256,
                ),
                "registration": {"ordinal": ordinal, "provenance": _slice_provenance(record, segment, identity)},
                "sourceType": source_type, "stateId": state_id,
                "title": _title(state_id, canonical, localization, pck_sha256=pck_sha256, blob_sha256=blob_sha256),
            })
    registrations.sort(key=lambda x:(x["canonicalMonster"],x["registration"]["ordinal"],x["stateId"]))
    graphs.sort(key=lambda x:x["graphId"])
    resolved_intent_sites = sum(len(row["intents"]) for row in registrations)
    resolved_intent_arguments = sum(
        len(intent["arguments"]) for row in registrations for intent in row["intents"]
    )
    if (resolved_intent_sites, resolved_intent_arguments) != (required_intent_sites, required_intent_arguments):
        raise SourceExtractionError(
            "intent semantic coverage incomplete: "
            f"sites {resolved_intent_sites}/{required_intent_sites}, "
            f"arguments {resolved_intent_arguments}/{required_intent_arguments}"
        )
    intent_coverage = {
        "requiredArguments": required_intent_arguments,
        "requiredSites": required_intent_sites,
        "resolvedArguments": resolved_intent_arguments,
        "resolvedSites": resolved_intent_sites,
    }
    return registrations, graphs, excluded, intent_coverage


def _value_alternatives(value: SymbolicValue) -> list[SymbolicValue]:
    if value.kind == "join":
        result: list[SymbolicValue] = []
        for item in value.operands:
            result.extend(_value_alternatives(item))
        return result
    return [value]


def _source_target(value: SymbolicValue, *, field_name: str, instruction_index: int,
                   record: Mapping[str, Any] | None = None) -> str:
    """Classify an exact creature/card/slot argument; every join must agree."""
    def one(item: SymbolicValue) -> str:
        if item.kind == "unresolved":
            if record is not None:
                fields = {str(record["instructions"][i].get("operand")) for i in item.origins
                          if 0 <= i < len(record["instructions"])
                          and record["instructions"][i].get("opcode") == "ldfld"}
                if len([name for name in fields if "cardToSteal" in name]) == 1:
                    return "rngSelectedCombatCard"
            raise SourceExtractionError(f"unresolved {field_name} at instruction {instruction_index}: {item.data}")
        if item.kind == "field" and isinstance(item.data, str):
            name = item.data.lower()
            if "cardtosteal" in name: return "selectedCombatCard"
            if name.endswith("::targets"): return "registeredTargets"
            if name.endswith("::target"): return "registeredTarget"
            if "nextslot" in name: return "selectedCombatSlot"
            if "slot" in name: return "stateCombatSlot"
        if item.kind == "string": return "namedCombatSlot"
        if item.kind == "null": return "automaticCombatSlot"
        if item.kind == "call" and isinstance(item.data, str):
            symbol = item.data
            if symbol.startswith("MegaCrit.Sts2.Core.Models.MonsterModel::get_Creature"):
                if item.operands and _is_source_model(item.operands[0]): return "sourceMonster"
                return "resolvedMonsterCreature"
            if "::get_Current sig:" in symbol: return "iteratedCreature"
            if symbol.startswith("MegaCrit.Sts2.Core.Models.EncounterModel::GetNextSlot"):
                return "nextOpenCombatSlot"
            if symbol.startswith("MegaCrit.Sts2.Core.Random.Rng::NextItem"):
                return "rngSelectedCombatCard"
            if symbol.startswith("MegaCrit.Sts2.Core.Combat.ICombatState::GetTeammatesOf"):
                return "sourceMonsterTeammates"
            if "::GetResult sig:20001300" in symbol:
                return "awaitedSummonedCreature"
            if symbol.startswith("System.Linq.Enumerable::LastOrDefault"):
                return "selectedAvailableCombatSlot"
        if item.kind == "join":
            values = {one(x) for x in item.operands}
            if len(values) == 1: return values.pop()
        raise SourceExtractionError(
            f"unresolved {field_name} at instruction {instruction_index}: {item.kind} {item.data}"
        )
    values = {one(item) for item in _value_alternatives(value)}
    if len(values) != 1:
        non_null=values-{"automaticCombatSlot"}
        if record is not None and len(non_null)==1 and "automaticCombatSlot" in values:
            sink_offset=record["instructions"][instruction_index].get("offsetDiagnostic")
            guards=[item for item in record["instructions"][:instruction_index]
                    if item.get("opcode") in {"brfalse","brfalse.s","brtrue","brtrue.s"}
                    and type(item.get("operand")) is int and type(sink_offset) is int
                    and item["operand"] > sink_offset]
            if guards: return non_null.pop()
        raise SourceExtractionError(f"non-unique {field_name} at instruction {instruction_index}: {sorted(values)}")
    return values.pop()


def _is_source_model(value: SymbolicValue) -> bool:
    if value.kind == "field" and isinstance(value.data, str) and value.data.endswith("::<>4__this"):
        return True
    if value.kind == "join": return all(_is_source_model(x) for x in value.operands)
    return False


def _combat_state_target(value: SymbolicValue, *, field_name: str, instruction_index: int) -> str:
    for item in _value_alternatives(value):
        if not (item.kind == "call" and isinstance(item.data, str)
                and item.data.startswith("MegaCrit.Sts2.Core.Models.MonsterModel::get_CombatState")
                and item.operands and _is_source_model(item.operands[0])):
            raise SourceExtractionError(f"unresolved {field_name} at instruction {instruction_index}")
    return "sourceMonsterCombatState"


def _model_from_values(values: list[SymbolicValue], fallback_symbols: list[str]) -> str | None:
    direct: set[str] = set()
    for symbol in fallback_symbols:
        generic = re.search(r" generic:MegaCrit\.Sts2\.Core\.Models\.(Powers|Cards|Monsters)\.([A-Za-z0-9]+)$", symbol)
        if generic:
            category = {"Powers":"POWER", "Cards":"CARD", "Monsters":"MONSTER"}[generic.group(1)]
            direct.add(category + "." + slugify_ascii_type_name(generic.group(2)))
    if len(direct) > 1: raise SourceExtractionError(f"ambiguous direct operation model references: {sorted(direct)}")
    if direct: return next(iter(direct))
    symbols: list[str] = []
    active = list(values); seen: set[int] = set()
    while active:
        item = active.pop()
        if id(item) in seen: continue
        seen.add(id(item))
        if isinstance(item.data, str): symbols.append(item.data)
        active.extend(item.operands)
    matches: set[str] = set()
    for symbol in symbols:
        generic = re.search(r" generic:MegaCrit\.Sts2\.Core\.Models\.(Powers|Cards|Monsters)\.([A-Za-z0-9]+)$", symbol)
        if generic:
            category = {"Powers":"POWER", "Cards":"CARD", "Monsters":"MONSTER"}[generic.group(1)]
            matches.add(category + "." + slugify_ascii_type_name(generic.group(2)))
    if len(matches) > 1: raise SourceExtractionError(f"ambiguous operation model references: {sorted(matches)}")
    return next(iter(matches), None)


def _attack_target_proof(assembly: AssemblyMetadata, assembly_sha256: str) -> dict[str, Any]:
    methods = assembly.find_methods("MegaCrit.Sts2.Core.Commands.Builders.AttackCommand", "FromMonster")
    matches = []
    for index in methods:
        record = assembly.method_record(index, assembly_sha256)
        if record["symbolSignature"] == "MegaCrit.Sts2.Core.Commands.Builders.AttackCommand::FromMonster sig:200112aa5c1288e4":
            matches.append(record)
    if len(matches) != 1: raise SourceExtractionError("required AttackCommand.FromMonster signature is not unique")
    record = matches[0]
    calls = [(i,x) for i,x in enumerate(record["instructions"])
             if x["opcode"] in {"call","callvirt"} and isinstance(x["operand"],str)
             and x["operand"].startswith("MegaCrit.Sts2.Core.Commands.Builders.AttackCommand::TargetingAllOpponents")]
    if len(calls) != 1: raise SourceExtractionError("FromMonster target helper proof is absent or ambiguous")
    i,_ = calls[0]; semantic={"target":"allOpponentsOfSourceMonster","helper":calls[0][1]["operand"]}
    return _slice_provenance(record, record["instructions"][max(0,i-5):i+1], semantic)


def _slice_for_invocation(record: Mapping[str, Any], invocation: Invocation) -> list[Mapping[str, Any]]:
    origins = {invocation.index}
    for value in invocation.arguments:
        origins.update(value.origins)
    if invocation.receiver: origins.update(invocation.receiver.origins)
    return [record["instructions"][i] for i in sorted(origins) if 0 <= i < len(record["instructions"])]


def _pile_expression(value: SymbolicValue, record: Mapping[str, Any], instruction_index: int) -> dict[str, Any]:
    try:
        return value_expression(value, field_name="generated-card pile", instruction_index=instruction_index)
    except SourceExtractionError as original:
        alternatives=_value_alternatives(value)
        constants={item.data for item in alternatives if item.kind=="constant" and item.cil_type and item.cil_type.numeric=="integer"}
        if len(constants)!=2 or len(constants)!=len(alternatives): raise original
        origins=sorted(set().union(*(item.origins for item in alternatives)))
        if not origins: raise original
        # Reviewed compiler diamond: field, integer threshold, conditional branch,
        # false constant, unconditional branch, true constant, one local store.
        lo=max(0,min(origins)-6); hi=min(len(record["instructions"]),max(origins)+3)
        segment=record["instructions"][lo:hi]
        branches=[(lo+i,item) for i,item in enumerate(segment) if item["opcode"] in {"blt","blt.s","bge","bge.s"}]
        if len(branches)!=1: raise original
        branch_index,branch=branches[0]
        predicate_segment=record["instructions"][lo:branch_index]
        fields=[item["operand"] for item in predicate_segment if item["opcode"]=="ldfld" and isinstance(item["operand"],str)]
        threshold_rows=[_ldc(item) for item in predicate_segment]
        thresholds=[x for x in threshold_rows if x is not None]
        if len(fields)!=1 or not thresholds: raise original
        threshold=thresholds[-1]
        target_offset=branch["operand"]
        target_index=next((i for i,item in enumerate(record["instructions"]) if item.get("offsetDiagnostic")==target_offset),None)
        if target_index is None: raise original
        true_value=_ldc(record["instructions"][target_index])
        false_candidates=[(_ldc(record["instructions"][i]),i) for i in origins if i!=target_index]
        false_values=[x for x,_ in false_candidates if x in constants and x!=true_value]
        if true_value not in constants or len(false_values)!=1: raise original
        op="lessThan" if branch["opcode"].startswith("blt") else "greaterOrEqual"
        condition={"kind":"compare","operator":op,
                   "left":{"kind":"sourceField","symbol":fields[0],"valueType":"integer"},
                   "right":const(threshold),"valueType":"boolean"}
        return {"kind":"conditional","condition":condition,"whenTrue":const(true_value),
                "whenFalse":const(false_values[0]),"valueType":"integer"}


def _boolean_expression(value: SymbolicValue, *, field_name: str, instruction_index: int) -> dict[str, Any]:
    ensure_resolved(value, field_name, instruction_index)
    alternatives = _value_alternatives(value)
    constants = {
        bool(item.data) for item in alternatives
        if item.kind == "constant" and type(item.data) is int and item.data in {0, 1}
    }
    if len(constants) != 1 or len(constants) != len(alternatives):
        raise SourceExtractionError(
            f"non-unique {field_name} boolean at instruction {instruction_index}"
        )
    return {"kind": "constant", "value": constants.pop(), "valueType": "boolean"}


def _runtime_power_instance(value: SymbolicValue, *, instruction_index: int) -> dict[str, Any]:
    """Describe an exact runtime-selected PowerModel without inventing its type."""
    ensure_resolved(value, "removed Power instance", instruction_index)
    active = [value]
    symbols: set[str] = set()
    kinds: set[str] = set()
    seen: set[int] = set()
    while active:
        item = active.pop()
        if id(item) in seen:
            continue
        seen.add(id(item)); kinds.add(item.kind)
        if isinstance(item.data, str) and " sig:" in item.data:
            symbols.add(item.data)
        active.extend(item.operands)
    current = sorted(symbol for symbol in symbols if "::get_Current sig:" in symbol)
    if len(current) != 1:
        raise SourceExtractionError(
            f"removed Power runtime selection is not uniquely source-linked at instruction {instruction_index}"
        )
    return {
        "classification": "runtimeSelectedPowerInstance",
        "sourceKinds": sorted(kinds),
        "sourceSymbolSignature": current[0],
    }


def _state_write_value(invocation: Invocation) -> tuple[str, dict[str, Any]]:
    if invocation.receiver is None or not _is_source_model(invocation.receiver):
        raise SourceExtractionError(
            f"state setter receiver is not the source monster at instruction {invocation.index}"
        )
    if len(invocation.arguments) != 1 or len(invocation.signature.parameters) != 1:
        raise SourceExtractionError(
            f"state setter does not have exactly one value at instruction {invocation.index}"
        )
    parameter = invocation.signature.parameters[0]
    value = invocation.arguments[0]
    if parameter.kind == "bool":
        expression = _boolean_expression(value, field_name="state write", instruction_index=invocation.index)
    elif parameter.numeric in {"integer", "decimal"}:
        expression = value_expression(value, field_name="state write", instruction_index=invocation.index)
    else:
        raise SourceExtractionError(
            f"unsupported required state setter type {parameter.kind} at instruction {invocation.index}"
        )
    return "sourceMonster", expression


def _operations(assembly: AssemblyMetadata, assembly_sha256: str,
                registrations: list[dict[str, Any]]) -> tuple[
                    list[dict[str, Any]], dict[str, int], int, int,
                    list[dict[str, Any]], dict[str, Any]
                ]:
    operations: list[dict[str, Any]]=[]
    counts={kind:0 for kind in EXPECTED_SINKS}
    unresolved: list[str]=[]; semantic_fields=0; semantic_denominator=0
    target_proof=_attack_target_proof(assembly,assembly_sha256)
    audit = ClosedWorldInvocationAudit(assembly, assembly_sha256, _async_map(assembly))
    for move in registrations:
        execution=move["execution"]
        if execution["kind"]!="asyncStateMachine":
            semantic={"kind":"transition","transition":"noOp"}
            move["operations"]=[{**semantic,"operationId":move["canonicalId"]+"/op/0","provenance":execution["method"]}]
            continue
        token=int(execution["moveNext"]["diagnosticMetadataToken"],16)&0xffffff
        record=assembly.method_record(token,assembly_sha256)
        try: invocations=CilDataFlow(record["instructions"]).run()
        except SourceExtractionError as exc:
            unresolved.append(f"{move['canonicalId']} method: {exc}"); move["operations"]=[]; continue
        move_ops=[]
        for index,invocation in sorted(invocations.items()):
            try:
                decision = audit.classify(invocation, record, move["canonicalId"])
            except SourceExtractionError as exc:
                unresolved.append(str(exc))
                continue
            if decision["classification"] == "normalizedGameplayOperation":
                kind=decision["normalizedKind"]
                if kind not in counts:
                    unresolved.append(
                        f"{move['canonicalId']} normalized operation has no semantic handler at instruction {index}: {kind}"
                    )
                    continue
                counts[kind]+=1
                semantic_denominator += REQUIRED_SEMANTIC_FIELDS[kind]
                try:
                    semantic: dict[str,Any]={"kind":kind,"sinkSymbolSignature":invocation.symbol,"sourceOrder":index}
                    args=list(invocation.arguments)
                    if kind=="attack":
                        semantic["value"]=value_expression(args[0],field_name="attack amount",instruction_index=index)
                        consumers=[x for j,x in invocations.items() if j>index and x.symbol.startswith("MegaCrit.Sts2.Core.Commands.Builders.AttackCommand::FromMonster") and contains_origin(x.receiver,index)]
                        if len(consumers)!=1: raise SourceExtractionError(f"attack builder target proof count {len(consumers)} at instruction {index}")
                        if not _is_source_model(consumers[0].arguments[0]):
                            raise SourceExtractionError(f"unresolved attack source monster at instruction {consumers[0].index}")
                        semantic["target"]="allOpponentsOfSourceMonster";semantic["targetProvenance"]=target_proof
                    elif kind=="attackHitCount":
                        semantic["value"]=value_expression(args[0],field_name="attack hit count",instruction_index=index)
                    elif kind=="applyPower":
                        amount_index,target_index=(3,2) if invocation.symbol.startswith("MegaCrit.Sts2.Core.Commands.PowerCmd::Apply sig:0007") else (2,1)
                        semantic["value"]=value_expression(args[amount_index],field_name="Power amount",instruction_index=index)
                        semantic["target"]=_source_target(args[target_index],field_name="Power target",instruction_index=index,record=record)
                        model=_model_from_values(args,[invocation.symbol])
                        if not model: raise SourceExtractionError(f"missing Power model at instruction {index}")
                        semantic["model"]=model
                    elif kind=="removePower":
                        model=_model_from_values(args,[invocation.symbol])
                        if model:
                            semantic["model"]=model
                            semantic["target"]=_source_target(args[0],field_name="removed Power target",instruction_index=index,record=record)
                        else:
                            if len(args)!=1: raise SourceExtractionError(f"runtime Power removal argument count {len(args)}")
                            semantic["modelContract"]=_runtime_power_instance(args[0],instruction_index=index)
                            semantic["target"]="runtimeSelectedPowerInstance"
                    elif kind=="kill":
                        if len(args)!=2: raise SourceExtractionError(f"Kill argument count {len(args)}")
                        semantic["target"]=_source_target(args[0],field_name="Kill target",instruction_index=index,record=record)
                        semantic["playDeathEffects"]=_boolean_expression(args[1],field_name="Kill play-death-effects",instruction_index=index)
                    elif kind=="stateWrite":
                        semantic["target"],semantic["value"]=_state_write_value(invocation)
                        semantic["memberSymbolSignature"]=invocation.symbol
                    elif kind=="gainBlock":
                        semantic["target"]=_source_target(args[0],field_name="Block target",instruction_index=index,record=record)
                        semantic["value"]=value_expression(args[1],field_name="Block amount",instruction_index=index)
                    elif kind=="addStatusCard":
                        semantic["target"]=_source_target(args[0],field_name="status-card target",instruction_index=index,record=record)
                        semantic["value"]=value_expression(args[2],field_name="status-card count",instruction_index=index)
                        model=_model_from_values(args,[invocation.symbol])
                        if not model: raise SourceExtractionError(f"missing status-card model at instruction {index}")
                        semantic["model"]=model
                    elif kind=="addGeneratedCard":
                        semantic["target"]="generatedCardCombatPile";semantic["destination"]={"pileType":_pile_expression(args[1],record,index)}
                        model=_model_from_values(args,[invocation.symbol])
                        if not model: raise SourceExtractionError(f"missing generated-card model at instruction {index}")
                        semantic["model"]=model
                    elif kind=="summon":
                        semantic["target"]=_combat_state_target(args[0],field_name="summon combat state",instruction_index=index)
                        semantic["selection"]={"slot":_source_target(args[1],field_name="summon slot",instruction_index=index,record=record)}
                        model=_model_from_values(args,[invocation.symbol])
                        if not model: raise SourceExtractionError(f"missing summon model at instruction {index}")
                        semantic["model"]=model
                    elif kind=="escape":
                        semantic["target"]=_source_target(args[0],field_name="escape target",instruction_index=index,record=record)
                    elif kind=="heal":
                        semantic["target"]=_source_target(args[0],field_name="heal target",instruction_index=index,record=record)
                        semantic["value"]=value_expression(args[1],field_name="heal amount",instruction_index=index)
                    elif kind=="removeCard":
                        semantic["target"]=_source_target(args[0],field_name="remove-card selection",instruction_index=index,record=record)
                    else: raise SourceExtractionError(f"unhandled normalized operation kind {kind}")
                    semantic_fields += REQUIRED_SEMANTIC_FIELDS[kind]
                    op={**semantic,"operationId":move["canonicalId"]+f"/op/{len(move_ops)}"}
                    op["provenance"]=_slice_provenance(record,_slice_for_invocation(record,invocation),semantic)
                    move_ops.append(op);operations.append(op)
                except SourceExtractionError as exc:
                    unresolved.append(f"{move['canonicalId']} {kind} instruction {index}: {exc}")
        helper=next((value for prefix,value in HELPERS.items() if move["action"]["symbolSignature"].startswith(prefix)),None)
        if helper:
            helper_kind,required_call=helper
            matches=[(i,x) for i,x in enumerate(record["instructions"])
                     if isinstance(x["operand"],str) and x["operand"].startswith(required_call)]
            if not matches:
                unresolved.append(f"{move['canonicalId']} helper: mandatory call absent {required_call}")
            else:
                helper_index, helper_instruction = matches[0]
                call_sites=[{"sourceOrder":i,"symbolSignature":item["operand"]} for i,item in matches]
                semantic={"kind":"helperEffect","helper":helper_kind,"sourceOrder":helper_index,
                          "helperSymbolSignature":helper_instruction["operand"],
                          "helperCallSites":call_sites}
                op={**semantic,"operationId":move["canonicalId"]+f"/op/{len(move_ops)}",
                    "provenance":_slice_provenance(record,[item for _,item in matches],semantic)}
                move_ops.append(op);operations.append(op)
        if not move_ops:
            semantic={"kind":"transition","sourceOrder":0,"transition":"nonnumericOrStateUpdate"}
            op={**semantic,"operationId":move["canonicalId"]+"/op/0",
                "provenance":_slice_provenance(record,record["instructions"],semantic)}
            move_ops.append(op);operations.append(op)
        move["operations"]=move_ops
    if unresolved:
        raise SourceExtractionError("operation/invocation semantic coverage incomplete: " + " | ".join(sorted(unresolved)))
    if semantic_fields != semantic_denominator:
        raise SourceExtractionError(f"operation semantic coverage accounting mismatch: {semantic_fields}/{semantic_denominator}")
    audit_summary = audit.summary()
    if audit_summary["resolved"] != audit_summary["denominator"] or audit_summary["unresolved"]:
        raise SourceExtractionError(f"invocation classification incomplete: {audit_summary!r}")
    return operations,counts,semantic_fields,semantic_denominator,audit.decisions,audit_summary


def extract_behavior(assembly: AssemblyMetadata, assembly_sha256: str, pck_sha256: str,
                     monsters: list[Mapping[str,Any]], reachable_models: list[str], localization: Mapping[str,Any],
                     localization_blob_sha256: str) -> dict[str, Any]:
    source_to_model = {x["sourceType"]:"MONSTER." + x["canonicalId"] for x in monsters}
    registrations, graphs, excluded, intent_coverage = _registration_rows(assembly,assembly_sha256,source_to_model,set(reachable_models),localization,pck_sha256,localization_blob_sha256)
    operations, sink_counts, semantic_fields, semantic_denominator, invocation_decisions, invocation_summary = _operations(assembly,assembly_sha256,registrations)
    async_count=sum(x["execution"]["kind"]=="asyncStateMachine" for x in registrations)
    sync_count=len(registrations)-async_count
    localized=sum(x["title"]["classification"]=="localized" for x in registrations)
    topology={
        "behaviorClasses":len(graphs), "moveConstructors":sum(x["topology"]["moveNodes"] for x in graphs),
        "followUpAssignments":sum(x["topology"]["followUpEdges"] for x in graphs),
        "randomNodes":sum(x["topology"]["randomNodes"] for x in graphs),
        "conditionalNodes":sum(x["topology"]["conditionalNodes"] for x in graphs),
        "mustOnceFlags":sum(x["topology"]["mustOnceFlags"] for x in graphs),
        "randomClasses":sum(x["topology"]["randomNodes"]>0 for x in graphs),
        "conditionalClasses":sum(x["topology"]["conditionalNodes"]>0 for x in graphs),
        "bothBranchKinds":sum(x["topology"]["randomNodes"]>0 and x["topology"]["conditionalNodes"]>0 for x in graphs),
    }
    expected_topology={"behaviorClasses":100,"moveConstructors":307,"followUpAssignments":309,
                       "randomNodes":22,"conditionalNodes":17,"mustOnceFlags":4,
                       "randomClasses":20,"conditionalClasses":16,"bothBranchKinds":2}
    failures=[]
    if (len(registrations),async_count,sync_count)!=(307,301,6): failures.append(f"registration census {len(registrations)}/{async_count}/{sync_count}")
    if localized!=289: failures.append(f"localized move titles {localized}/307")
    if sink_counts!=EXPECTED_SINKS: failures.append(f"sink census {sink_counts!r}")
    if topology!=expected_topology: failures.append(f"topology census {topology!r}")
    if failures: raise SourceExtractionError("Wave B regression disagreement: "+"; ".join(failures))
    return {"excludedRegistrations":excluded,"graphs":graphs,"registrations":registrations,
            "invocationCensus":{"decisions":invocation_decisions,"summary":invocation_summary},
            "summary":{"asyncActions":async_count,"synchronousNoOpActions":sync_count,
                       "localizedTitles":localized,"missingOrInternalTitles":len(registrations)-localized,
                       "intentConstructorSites":intent_coverage["requiredSites"],
                       "resolvedIntentConstructorSites":intent_coverage["resolvedSites"],
                       "requiredIntentArguments":intent_coverage["requiredArguments"],
                       "resolvedIntentArguments":intent_coverage["resolvedArguments"],
                       "directSinkCounts":sink_counts,"directSinkSites":sum(sink_counts.values()),
                       "requiredSemanticFields":semantic_denominator,"resolvedSemanticFields":semantic_fields,
                       "topology":topology}}
