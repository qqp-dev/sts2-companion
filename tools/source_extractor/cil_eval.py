"""Bounded, non-executing CIL stack/data-flow analysis for gameplay slices.

This module interprets *metadata shapes*, not program behavior.  It decodes CLI
method signatures to obtain exact stack contracts and carries immutable symbolic
values through a bounded CFG.  Values at unequal control-flow joins are marked
unresolved; callers must fail closed if such a value reaches a required fact.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Mapping

from .errors import SourceExtractionError

MAX_INSTRUCTIONS = 4096
MAX_WORK_STEPS = 200_000
MAX_VALUE_DEPTH = 64

_ASCENSION_VALUE = "MegaCrit.Sts2.Core.Helpers.AscensionHelper::GetValueIfAscension sig:00030811a8980808"


def integer_constant(instruction: Mapping[str, Any]) -> int | None:
    opcode = instruction["opcode"]
    if opcode in {"ldc.i4", "ldc.i4.s"}:
        value = instruction.get("operand")
        if type(value) is not int:
            raise SourceExtractionError(f"non-integer {opcode} operand")
        return value
    return {
        "ldc.i4.m1": -1, "ldc.i4.0": 0, "ldc.i4.1": 1, "ldc.i4.2": 2,
        "ldc.i4.3": 3, "ldc.i4.4": 4, "ldc.i4.5": 5, "ldc.i4.6": 6,
        "ldc.i4.7": 7, "ldc.i4.8": 8,
    }.get(opcode)


@dataclass(frozen=True)
class CilType:
    kind: str
    arguments: tuple["CilType", ...] = ()

    @property
    def numeric(self) -> str | None:
        if self.kind in {"i1", "u1", "i2", "u2", "i4", "u4", "i8", "u8", "nativeInt", "nativeUInt"}:
            return "integer"
        if self.kind in {"r4", "r8", "decimal"}:
            return "decimal"
        if self.kind == "bool":
            return "boolean"
        return None


@dataclass(frozen=True)
class MethodSignature:
    has_this: bool
    parameters: tuple[CilType, ...]
    returns: CilType


class _BlobReader:
    def __init__(self, value: bytes):
        self.value = value
        self.position = 0

    def byte(self) -> int:
        if self.position >= len(self.value):
            raise SourceExtractionError("truncated CLI signature")
        result = self.value[self.position]
        self.position += 1
        return result

    def compressed_uint(self) -> int:
        first = self.byte()
        if first & 0x80 == 0:
            return first
        if first & 0xC0 == 0x80:
            return ((first & 0x3F) << 8) | self.byte()
        if first & 0xE0 == 0xC0:
            return ((first & 0x1F) << 24) | (self.byte() << 16) | (self.byte() << 8) | self.byte()
        raise SourceExtractionError("invalid compressed integer in CLI signature")


_PRIMITIVES = {
    0x01: "void", 0x02: "bool", 0x03: "char", 0x04: "i1", 0x05: "u1",
    0x06: "i2", 0x07: "u2", 0x08: "i4", 0x09: "u4", 0x0A: "i8",
    0x0B: "u8", 0x0C: "r4", 0x0D: "r8", 0x0E: "string",
    0x16: "typedref", 0x18: "nativeInt", 0x19: "nativeUInt", 0x1C: "object",
}


def _signature_type(reader: _BlobReader, depth: int = 0) -> CilType:
    if depth > 32:
        raise SourceExtractionError("CLI signature type depth exceeded")
    element = reader.byte()
    while element in {0x1F, 0x20}:  # required/optional custom modifier
        reader.compressed_uint()
        element = reader.byte()
    if element in _PRIMITIVES:
        return CilType(_PRIMITIVES[element])
    if element in {0x0F, 0x10, 0x1D, 0x45}:  # ptr, byref, szarray, pinned
        names = {0x0F: "pointer", 0x10: "byref", 0x1D: "array", 0x45: "pinned"}
        return CilType(names[element], (_signature_type(reader, depth + 1),))
    if element in {0x11, 0x12}:  # valuetype/class TypeDefOrRefEncoded
        token = reader.compressed_uint()
        # Decimal is a value type.  Its pinned token is not stable authority, but
        # its signature token is useful solely as a type diagnostic.  Calls to
        # Decimal operators are promoted by symbol below.
        return CilType("valuetype" if element == 0x11 else "class", (CilType(f"token:{token}"),))
    if element in {0x13, 0x1E}:  # generic VAR/MVAR
        return CilType("var" if element == 0x13 else "mvar", (CilType(str(reader.compressed_uint())),))
    if element == 0x15:  # genericinst class|valuetype token count types...
        base_kind = reader.byte()
        if base_kind not in {0x11, 0x12}:
            raise SourceExtractionError("invalid genericinst base in CLI signature")
        token = reader.compressed_uint()
        count = reader.compressed_uint()
        arguments = tuple(_signature_type(reader, depth + 1) for _ in range(count))
        return CilType("genericInstance", (CilType(f"token:{token}"),) + arguments)
    if element == 0x14:  # multidimensional array
        item = _signature_type(reader, depth + 1)
        rank = reader.compressed_uint()
        sizes = reader.compressed_uint()
        for _ in range(sizes): reader.compressed_uint()
        lows = reader.compressed_uint()
        for _ in range(lows): reader.compressed_uint()
        return CilType("mdarray", (item, CilType(f"rank:{rank}")))
    if element == 0x1B:  # function pointer embeds a complete method signature
        nested = _method_signature(reader)
        return CilType("fnptr", (nested.returns,) + nested.parameters)
    if element == 0x21:  # INTERNAL is pointer-sized implementation data
        # ECMA permits a native pointer payload. It is never numeric authority in
        # the reviewed sinks, but consumes four bytes in these metadata blobs.
        for _ in range(4): reader.byte()
        return CilType("internal")
    raise SourceExtractionError(f"unsupported CLI signature element 0x{element:02x}")


def _method_signature(reader: _BlobReader) -> MethodSignature:
    convention = reader.byte()
    if convention & 0x0F in {0x06, 0x07, 0x08}:  # field/local/property are not calls
        raise SourceExtractionError("metadata signature is not a method signature")
    has_this = bool(convention & 0x20)
    if convention & 0x10:
        reader.compressed_uint()  # generic parameter count
    count = reader.compressed_uint()
    returns = _signature_type(reader)
    parameters: list[CilType] = []
    while len(parameters) < count:
        if reader.position < len(reader.value) and reader.value[reader.position] == 0x41:  # sentinel
            reader.position += 1
            continue
        parameters.append(_signature_type(reader))
    return MethodSignature(has_this, tuple(parameters), returns)


_SIG_RE = re.compile(r" sig:([0-9a-fA-F]+)")


def decode_method_signature(symbol: str) -> MethodSignature:
    """Decode the exact raw signature carried by a resolved metadata symbol."""
    if not isinstance(symbol, str):
        raise SourceExtractionError("callee symbol is not a string")
    match = _SIG_RE.search(symbol)
    if not match:
        raise SourceExtractionError(f"callee has no required metadata signature: {symbol}")
    try:
        blob = bytes.fromhex(match.group(1))
    except ValueError as exc:
        raise SourceExtractionError(f"invalid callee signature hex: {symbol}") from exc
    reader = _BlobReader(blob)
    signature = _method_signature(reader)
    if reader.position != len(blob):
        raise SourceExtractionError(f"unconsumed bytes in callee signature: {symbol}")
    return signature


@dataclass(frozen=True)
class SymbolicValue:
    kind: str
    cil_type: CilType | None = None
    data: Any = None
    operands: tuple["SymbolicValue", ...] = ()
    origins: frozenset[int] = field(default_factory=frozenset, compare=False)

    def with_origins(self, origins: Iterable[int]) -> "SymbolicValue":
        return SymbolicValue(self.kind, self.cil_type, self.data, self.operands,
                             self.origins | frozenset(origins))


@dataclass(frozen=True)
class Invocation:
    index: int
    symbol: str
    signature: MethodSignature
    arguments: tuple[SymbolicValue, ...]
    receiver: SymbolicValue | None
    result: SymbolicValue | None


@dataclass
class _Frame:
    stack: list[SymbolicValue]
    locals: dict[str, SymbolicValue]
    fields: dict[str, SymbolicValue]

    def clone(self) -> "_Frame":
        return _Frame(list(self.stack), dict(self.locals), dict(self.fields))


_UNKNOWN_TYPE = CilType("unknown")


def _unknown(reason: str, origins: Iterable[int] = ()) -> SymbolicValue:
    return SymbolicValue("unresolved", _UNKNOWN_TYPE, reason, origins=frozenset(origins))


def _address(kind: str, name: str, value: SymbolicValue, index: int) -> SymbolicValue:
    return SymbolicValue("address", CilType("byref", (value.cil_type or _UNKNOWN_TYPE,)),
                         (kind, name), (value,), frozenset({index}) | value.origins)


def _local_number(opcode: str, operand: Any) -> str | None:
    match = re.fullmatch(r"(?:ld|st)loc\.(\d+)", opcode)
    if match:
        return str(int(match.group(1)))
    if opcode in {"ldloc", "ldloc.s", "ldloca", "ldloca.s", "stloc", "stloc.s"}:
        match = re.fullmatch(r"local\(0x([0-9a-fA-F]{4})\)", str(operand))
        if match:
            return str(int(match.group(1), 16))
    return None


def _argument_number(opcode: str, operand: Any) -> str | None:
    match = re.fullmatch(r"ldarg\.(\d+)", opcode)
    if match:
        return str(int(match.group(1)))
    if opcode in {"ldarg", "ldarg.s", "ldarga", "ldarga.s"}:
        match = re.fullmatch(r"argument\(0x([0-9a-fA-F]{4})\)", str(operand))
        if match:
            return str(int(match.group(1), 16))
        if type(operand) is int:
            return str(operand)
    return None


def _merge_value(left: SymbolicValue | None, right: SymbolicValue | None, where: int, name: str) -> SymbolicValue:
    if left is None and right is None:
        raise AssertionError
    if left is None or right is None:
        value = left or right
        assert value is not None
        return _unknown(f"non-unique {name} at IL_{where:04x}", value.origins)
    if left == right:
        return left.with_origins(right.origins)
    origins = left.origins | right.origins
    # A generated async spill field on a resume edge denotes the value stored
    # into that exact field on the pre-await edge. Prefer the concrete reaching
    # definition; this is metadata-proven persistence, not a guessed default.
    if left.kind == "field" and right.kind not in {"field", "unresolved"}:
        return right.with_origins(left.origins)
    if right.kind == "field" and left.kind not in {"field", "unresolved"}:
        return left.with_origins(right.origins)
    # Recurse through identical wrappers (for example convert(spill F) versus
    # convert(the value stored to F)) before widening to a join.
    if left.kind == right.kind and left.cil_type == right.cil_type and left.data == right.data and len(left.operands) == len(right.operands) and left.operands:
        operands = tuple(_merge_value(a, b, where, name) for a, b in zip(left.operands, right.operands))
        return SymbolicValue(left.kind, left.cil_type, left.data, operands, origins)
    # Unresolved is lattice top. Re-wrapping it at loop back-edges would create
    # an infinite ascending chain and cannot recover semantic precision.
    if left.kind == "unresolved": return left.with_origins(right.origins)
    if right.kind == "unresolved": return right.with_origins(left.origins)
    values: list[SymbolicValue] = []
    for value in (left, right):
        for candidate in (value.operands if value.kind == "join" else (value,)):
            if candidate not in values:
                values.append(candidate)
    if len(values) > 16:
        return _unknown(f"over-width {name} join at IL_{where:04x}", origins)
    return SymbolicValue("join", left.cil_type if left.cil_type == right.cil_type else _UNKNOWN_TYPE,
                         f"{name} at IL_{where:04x}", tuple(values), origins)


def _merge_frame(current: _Frame | None, incoming: _Frame, where: int) -> tuple[_Frame, bool]:
    if current is None:
        return incoming.clone(), True
    if len(current.stack) != len(incoming.stack):
        raise SourceExtractionError(
            f"non-unique CIL stack depth at IL_{where:04x}: {len(current.stack)} != {len(incoming.stack)}"
        )
    merged_stack = [_merge_value(a, b, where, f"stack[{i}]")
                    for i, (a, b) in enumerate(zip(current.stack, incoming.stack))]
    merged_locals = {key: _merge_value(current.locals.get(key), incoming.locals.get(key), where, f"local {key}")
                     for key in sorted(set(current.locals) | set(incoming.locals))}
    merged_fields = {}
    for key in sorted(set(current.fields) | set(incoming.fields)):
        left = current.fields.get(key, SymbolicValue("field", _UNKNOWN_TYPE, key))
        right = incoming.fields.get(key, SymbolicValue("field", _UNKNOWN_TYPE, key))
        merged_fields[key] = _merge_value(left, right, where, f"field {key}")
    merged = _Frame(merged_stack, merged_locals, merged_fields)
    changed = merged.stack != current.stack or merged.locals != current.locals or merged.fields != current.fields
    return merged, changed


class CilDataFlow:
    """Forward symbolic evaluation with strict stack contracts and bounded joins."""

    def __init__(self, instructions: list[Mapping[str, Any]]):
        if not isinstance(instructions, list) or not instructions or len(instructions) > MAX_INSTRUCTIONS:
            raise SourceExtractionError("invalid or over-depth behavior CIL method")
        self.instructions = instructions
        self.invocations: dict[int, Invocation] = {}
        self.frames: dict[int, _Frame] = {}
        self._offset_to_index: dict[int, int] = {}
        for index, item in enumerate(instructions):
            if not isinstance(item, Mapping) or not isinstance(item.get("opcode"), str):
                raise SourceExtractionError(f"malformed behavior CIL instruction {index}")
            offset = item.get("offsetDiagnostic", index)
            if type(offset) is not int or offset in self._offset_to_index:
                raise SourceExtractionError(f"invalid/duplicate CIL offset at instruction {index}")
            self._offset_to_index[offset] = index

    @staticmethod
    def _pop(frame: _Frame, index: int, purpose: str) -> SymbolicValue:
        if not frame.stack:
            raise SourceExtractionError(f"CIL stack underflow at instruction {index} ({purpose})")
        return frame.stack.pop()

    def _target(self, operand: Any, index: int) -> int:
        if type(operand) is not int or operand not in self._offset_to_index:
            raise SourceExtractionError(f"unresolved branch target at instruction {index}: {operand!r}")
        return self._offset_to_index[operand]

    def _successors(self, index: int, frame: _Frame) -> list[tuple[int, _Frame]]:
        item = self.instructions[index]
        opcode, operand = item["opcode"], item.get("operand")
        following = index + 1
        if opcode in {"ret", "throw"}:
            return []
        if opcode in {"br", "br.s", "leave", "leave.s"}:
            if opcode.startswith("leave"):
                frame.stack.clear()
            return [(self._target(operand, index), frame)]
        if opcode == "switch":
            if not isinstance(operand, list) or any(type(x) is not int for x in operand):
                raise SourceExtractionError(f"unresolved switch targets at instruction {index}")
            result = [(self._target(target, index), frame.clone()) for target in operand]
            if following < len(self.instructions): result.append((following, frame))
            return result
        if opcode.startswith(("brtrue", "brfalse", "beq", "bne", "bge", "bgt", "ble", "blt")):
            result = [(self._target(operand, index), frame.clone())]
            if following < len(self.instructions): result.append((following, frame))
            return result
        if following < len(self.instructions):
            return [(following, frame)]
        return []

    def _record_invocation(self, invocation: Invocation) -> None:
        previous = self.invocations.get(invocation.index)
        if previous is None:
            self.invocations[invocation.index] = invocation
            return
        if previous.symbol != invocation.symbol or previous.signature != invocation.signature:
            raise SourceExtractionError(f"callee changed across CFG paths at instruction {invocation.index}")
        args = tuple(_merge_value(a, b, invocation.index, f"call argument {i}")
                     for i, (a, b) in enumerate(zip(previous.arguments, invocation.arguments)))
        if previous.receiver is None and invocation.receiver is None:
            receiver = None
        else:
            receiver = _merge_value(previous.receiver, invocation.receiver, invocation.index, "call receiver")
        result = invocation.result
        self.invocations[invocation.index] = Invocation(invocation.index, invocation.symbol,
                                                         invocation.signature, args, receiver, result)

    def _execute(self, index: int, incoming: _Frame) -> _Frame:
        frame = incoming.clone()
        item = self.instructions[index]
        opcode, operand = item["opcode"], item.get("operand")
        origin = frozenset({index})
        integer = integer_constant(item)
        if integer is not None:
            frame.stack.append(SymbolicValue("constant", CilType("i4"), integer, origins=origin)); return frame
        if opcode in {"ldc.r4", "ldc.r8"}:
            if not isinstance(operand, (int, float)):
                raise SourceExtractionError(f"invalid floating constant at instruction {index}")
            frame.stack.append(SymbolicValue("constant", CilType("r4" if opcode == "ldc.r4" else "r8"),
                                             str(operand), origins=origin)); return frame
        if opcode == "ldnull":
            frame.stack.append(SymbolicValue("null", CilType("class"), None, origins=origin)); return frame
        if opcode == "ldstr":
            if not isinstance(operand, str) or not operand.startswith("string:"):
                raise SourceExtractionError(f"invalid string constant at instruction {index}")
            frame.stack.append(SymbolicValue("string", CilType("string"), operand[7:], origins=origin)); return frame
        arg = _argument_number(opcode, operand)
        if arg is not None:
            value = SymbolicValue("argument", _UNKNOWN_TYPE, arg, origins=origin)
            frame.stack.append(_address("argument", arg, value, index) if opcode.startswith("ldarga") else value)
            return frame
        local = _local_number(opcode, operand)
        if local is not None:
            if opcode.startswith("stloc"):
                frame.locals[local] = self._pop(frame, index, "store local").with_origins(origin); return frame
            value = frame.locals.get(local, SymbolicValue("local", _UNKNOWN_TYPE, local, origins=origin))
            frame.stack.append(_address("local", local, value, index) if opcode.startswith("ldloca") else value.with_origins(origin))
            return frame
        if opcode in {"ldfld", "ldflda"}:
            receiver = self._pop(frame, index, "load field")
            if not isinstance(operand, str): raise SourceExtractionError(f"unresolved field at instruction {index}")
            value = frame.fields.get(operand, SymbolicValue("field", _UNKNOWN_TYPE, operand, (receiver,), origin | receiver.origins))
            frame.stack.append(_address("field", operand, value, index) if opcode == "ldflda" else value.with_origins(origin)); return frame
        if opcode == "stfld":
            value = self._pop(frame, index, "store field value")
            self._pop(frame, index, "store field receiver")
            if not isinstance(operand, str): raise SourceExtractionError(f"unresolved field at instruction {index}")
            frame.fields[operand] = value.with_origins(origin); return frame
        if opcode == "stind.ref":
            # C# collection expressions use CollectionsMarshal.AsSpan/get_Item
            # followed by stind.ref.  Consume this only when metadata proves a
            # managed by-reference destination; accepting a plain object would
            # hide a malformed stack or changed compiler shape.
            value = self._pop(frame, index, "indirect store value")
            address = self._pop(frame, index, "indirect store address")
            if address.cil_type is None or address.cil_type.kind != "byref":
                raise SourceExtractionError(
                    f"stind.ref destination is not a managed byref at instruction {index}: {address.kind}"
                )
            if address.kind == "address":
                kind, name = address.data
                if kind == "local": frame.locals[name] = value.with_origins(origin)
                elif kind == "field": frame.fields[name] = value.with_origins(origin)
                elif kind != "argument":
                    raise SourceExtractionError(f"unsupported stind.ref address kind {kind!r} at instruction {index}")
            return frame
        if opcode == "ldsfld":
            if not isinstance(operand, str): raise SourceExtractionError(f"unresolved static field at instruction {index}")
            if operand.startswith("System.Decimal::One"):
                operand = "System.Decimal::One"
                value = SymbolicValue("constant", CilType("decimal"), "1", origins=origin)
            elif operand.startswith("System.Decimal::Zero"):
                operand = "System.Decimal::Zero"
                value = SymbolicValue("constant", CilType("decimal"), "0", origins=origin)
            elif operand.startswith("System.Decimal::MinusOne"):
                operand = "System.Decimal::MinusOne"
                value = SymbolicValue("constant", CilType("decimal"), "-1", origins=origin)
            else:
                value = frame.fields.get(operand, SymbolicValue("staticField", _UNKNOWN_TYPE, operand, origins=origin))
            frame.stack.append(value); return frame
        if opcode == "stsfld":
            if not isinstance(operand, str): raise SourceExtractionError(f"unresolved static field at instruction {index}")
            frame.fields[operand] = self._pop(frame, index, "store static field").with_origins(origin); return frame
        if opcode == "dup":
            value = self._pop(frame, index, "duplicate")
            frame.stack.extend((value, value.with_origins(origin))); return frame
        if opcode == "pop": self._pop(frame, index, "pop"); return frame
        if opcode in {"add", "sub", "mul", "rem", "rem.un"}:
            right = self._pop(frame, index, opcode); left = self._pop(frame, index, opcode)
            numeric = (left.cil_type.numeric if left.cil_type else None) or (right.cil_type.numeric if right.cil_type else None)
            result_type = CilType("decimal" if numeric == "decimal" else "i4")
            frame.stack.append(SymbolicValue("arithmetic", result_type,
                                             {"add":"add","sub":"subtract","mul":"multiply",
                                              "rem":"remainder","rem.un":"remainder"}[opcode],
                                             (left,right), origin | left.origins | right.origins)); return frame
        if opcode == "neg":
            value=self._pop(frame,index,"neg")
            zero=SymbolicValue("constant",value.cil_type or CilType("i4"),0,origins=origin)
            frame.stack.append(SymbolicValue("arithmetic",value.cil_type,"subtract",(zero,value),origin|value.origins)); return frame
        if opcode == "ceq":
            right=self._pop(frame,index,"compare"); left=self._pop(frame,index,"compare")
            frame.stack.append(SymbolicValue("compare",CilType("bool"),"equal",(left,right),origin|left.origins|right.origins)); return frame
        if opcode.startswith("conv."):
            value=self._pop(frame,index,"conversion")
            target={"conv.i4":"i4","conv.i8":"i8","conv.r4":"r4"}.get(opcode)
            if target is None: raise SourceExtractionError(f"unsupported conversion at instruction {index}: {opcode}")
            frame.stack.append(SymbolicValue("convert",CilType(target),opcode,(value,),origin|value.origins)); return frame
        if opcode in {"call", "callvirt", "newobj"}:
            signature=decode_method_signature(operand)
            args=[self._pop(frame,index,f"argument {n} of {operand}") for n in range(len(signature.parameters)-1,-1,-1)]
            args.reverse()
            receiver=None
            if signature.has_this and opcode != "newobj": receiver=self._pop(frame,index,f"receiver of {operand}")
            call_origins=origin | frozenset().union(*(x.origins for x in args), receiver.origins if receiver else frozenset())
            if opcode == "newobj":
                result=SymbolicValue("new",CilType("class"),operand,tuple(args),call_origins)
            elif operand.startswith("System.Decimal::op_Implicit"):
                result=SymbolicValue("convert",CilType("decimal"),"exact",tuple(args),call_origins)
            elif signature.returns.kind != "void":
                result=SymbolicValue("call",signature.returns,operand,((receiver,) if receiver else ())+tuple(args),call_origins)
            else: result=None
            invocation=Invocation(index,operand,signature,tuple(args),receiver,result)
            self._record_invocation(invocation)
            if result is not None: frame.stack.append(result)
            return frame
        if opcode == "newarr":
            count=self._pop(frame,index,"new array length")
            frame.stack.append(SymbolicValue("array",CilType("array"),operand,(count,),origin|count.origins)); return frame
        if opcode in {"stelem", "stelem.i4", "stelem.ref"}:
            self._pop(frame,index,"array value"); self._pop(frame,index,"array index"); self._pop(frame,index,"array"); return frame
        if opcode in {"ldelem.i4", "ldelem.ref"}:
            sub=self._pop(frame,index,"array index"); array=self._pop(frame,index,"array")
            element_type = CilType("i4") if opcode == "ldelem.i4" else _UNKNOWN_TYPE
            frame.stack.append(SymbolicValue("arrayElement",element_type,opcode,(array,sub),origin|array.origins|sub.origins)); return frame
        if opcode == "ldlen":
            array=self._pop(frame,index,"array length")
            frame.stack.append(SymbolicValue("arrayLength",CilType("nativeUInt"),None,(array,),origin|array.origins)); return frame
        if opcode in {"castclass", "isinst"}:
            value=self._pop(frame,index,opcode)
            frame.stack.append(SymbolicValue(opcode,CilType("class"),operand,(value,),origin|value.origins)); return frame
        if opcode == "ldftn":
            frame.stack.append(SymbolicValue("function",CilType("fnptr"),operand,origins=origin)); return frame
        if opcode == "initobj":
            address=self._pop(frame,index,"initobj")
            if address.kind == "address" and isinstance(address.data,tuple):
                kind,name=address.data
                value=SymbolicValue("initialized",CilType("valuetype"),operand,origins=origin)
                if kind=="local": frame.locals[name]=value
                elif kind=="field": frame.fields[name]=value
            return frame
        if opcode == "switch": self._pop(frame,index,"switch selector"); return frame
        if opcode.startswith(("brtrue", "brfalse")):
            self._pop(frame,index,"branch condition"); return frame
        if opcode.startswith(("beq", "bne", "bge", "bgt", "ble", "blt")):
            self._pop(frame,index,"branch right"); self._pop(frame,index,"branch left"); return frame
        if opcode == "throw": self._pop(frame,index,"throw"); return frame
        if opcode == "ret":
            # MoveNext methods are void. A nonempty evaluation stack here is a
            # malformed reviewed method, but async catch plumbing can leave no value.
            return frame
        if opcode in {"br", "br.s", "leave", "leave.s", "nop", "endfinally", "constrained."}:
            return frame
        raise SourceExtractionError(f"unknown stack-affecting opcode at instruction {index}: {opcode}")

    def run(self) -> dict[int, Invocation]:
        entry=_Frame([],{},{}); pending=deque([(0,entry)]); steps=0
        while pending:
            index,incoming=pending.popleft(); steps+=1
            if steps>MAX_WORK_STEPS: raise SourceExtractionError("behavior CIL data-flow step limit exceeded")
            offset=self.instructions[index].get("offsetDiagnostic",index)
            merged,changed=_merge_frame(self.frames.get(index),incoming,offset)
            if not changed: continue
            self.frames[index]=merged
            outgoing=self._execute(index,merged)
            for successor,frame in self._successors(index,outgoing): pending.append((successor,frame))
        return self.invocations

    def return_value(self, method_symbol: str) -> SymbolicValue:
        """Return the unique symbolic value consumed by every reachable ``ret``."""
        signature = decode_method_signature(method_symbol)
        if signature.returns.kind == "void":
            raise SourceExtractionError(f"void method has no return value: {method_symbol}")
        if not self.frames:
            self.run()
        result: SymbolicValue | None = None
        for index, instruction in enumerate(self.instructions):
            if instruction["opcode"] != "ret" or index not in self.frames:
                continue
            stack = self.frames[index].stack
            if len(stack) != 1:
                raise SourceExtractionError(
                    f"invalid return stack depth in {method_symbol} at instruction {index}: {len(stack)}"
                )
            candidate = stack[0]
            result = candidate if result is None else _merge_value(
                result, candidate, index, "return value"
            )
        if result is None:
            raise SourceExtractionError(f"no reachable return value in {method_symbol}")
        return result


def contains_origin(value: SymbolicValue | None, instruction_index: int) -> bool:
    return value is not None and instruction_index in value.origins


def ensure_resolved(value: SymbolicValue, field_name: str, instruction_index: int) -> SymbolicValue:
    active=[value]; seen:set[int]=set(); depth=0
    while active:
        item=active.pop(); identity=id(item)
        if identity in seen: continue
        seen.add(identity); depth+=1
        if depth>4096: raise SourceExtractionError(f"{field_name} value graph limit exceeded at instruction {instruction_index}")
        if item.kind=="unresolved":
            raise SourceExtractionError(f"unresolved {field_name} at instruction {instruction_index}: {item.data}")
        active.extend(item.operands)
    return value


def value_expression(value: SymbolicValue, *, field_name: str, instruction_index: int) -> dict[str, Any]:
    """Project a uniquely resolved numeric symbolic value to the closed AST."""
    ensure_resolved(value,field_name,instruction_index)
    def visit(item: SymbolicValue,depth:int=0,inferred_type:str|None=None)->dict[str,Any]:
        if depth>MAX_VALUE_DEPTH: raise SourceExtractionError(f"{field_name} expression depth exceeded at instruction {instruction_index}")
        if item.kind=="join":
            expressions=[visit(candidate,depth+1,inferred_type) for candidate in item.operands]
            if not expressions or any(candidate != expressions[0] for candidate in expressions[1:]):
                raise SourceExtractionError(f"non-unique {field_name} expression at instruction {instruction_index}: {item.data}")
            return expressions[0]
        if item.kind in {"field","staticField"}:
            numeric=(item.cil_type.numeric if item.cil_type else None) or inferred_type
            if numeric not in {"integer","decimal"}:
                raise SourceExtractionError(f"untyped {field_name} field at instruction {instruction_index}: {item.data}")
            return {"kind":"sourceField","symbol":item.data,"valueType":numeric}
        if item.kind=="constant":
            numeric=(item.cil_type.numeric if item.cil_type else None) or inferred_type
            if numeric=="integer": return {"kind":"constant","value":int(item.data),"valueType":"integer"}
            if numeric=="decimal": return {"kind":"constant","value":str(item.data),"valueType":"decimal"}
        if item.kind=="new" and isinstance(item.data,str) and item.data.startswith("System.Decimal::.ctor") and len(item.operands)==1:
            source=visit(item.operands[0],depth+1,"integer")
            if source["valueType"]=="decimal": return source
            return {"expression":source,"fromType":source["valueType"],"kind":"convert","mode":"exact","toType":"decimal","valueType":"decimal"}
        if item.kind=="call" and isinstance(item.data,str):
            numeric=item.cil_type.numeric if item.cil_type else None
            if numeric is None:
                # Getter signatures in the shipped assembly identify primitive
                # return types exactly. A required nonnumeric call is not coerced.
                raise SourceExtractionError(f"non-numeric {field_name} call at instruction {instruction_index}: {item.data}")
            signature=decode_method_signature(item.data)
            expected_operands=len(signature.parameters)+(1 if signature.has_this else 0)
            if len(item.operands)!=expected_operands:
                raise SourceExtractionError(
                    f"malformed {field_name} call operands at instruction {instruction_index}: "
                    f"{item.data} has {len(item.operands)}, expected {expected_operands}"
                )
            arguments=item.operands[1:] if signature.has_this else item.operands
            if item.data==_ASCENSION_VALUE:
                if signature.has_this or len(arguments)!=3 or numeric not in {"integer","decimal"}:
                    raise SourceExtractionError(
                        f"unsupported {field_name} ascension call at instruction {instruction_index}: {item.data}"
                    )
                threshold=visit(arguments[0],depth+1,"integer")
                at_or_above=visit(arguments[1],depth+1,numeric)
                below=visit(arguments[2],depth+1,numeric)
                if threshold.get("kind")!="constant" or threshold.get("valueType")!="integer":
                    raise SourceExtractionError(
                        f"dynamic {field_name} ascension threshold at instruction {instruction_index}: {item.data}"
                    )
                if at_or_above.get("valueType")!=numeric or below.get("valueType")!=numeric:
                    raise SourceExtractionError(
                        f"mismatched {field_name} ascension branches at instruction {instruction_index}: {item.data}"
                    )
                return {"kind":"ascensionSelect","threshold":threshold["value"],
                        "atOrAbove":at_or_above,"below":below,"valueType":numeric}
            result={"kind":"reference","reference":item.data,"valueType":numeric}
            if arguments:
                result["arguments"]=[
                    visit(argument,depth+1,parameter.numeric)
                    for argument,parameter in zip(arguments,signature.parameters,strict=True)
                ]
            return result
        if item.kind=="arithmetic" and len(item.operands)==2:
            if item.data not in {"add", "subtract", "multiply", "divide", "remainder"}:
                raise SourceExtractionError(
                    f"unsupported {field_name} arithmetic at instruction {instruction_index}: {item.data}"
                )
            operands=[visit(x,depth+1) for x in item.operands]
            result_type="decimal" if any(x["valueType"]=="decimal" for x in operands) else "integer"
            return {"kind":"arithmetic","operator":item.data,"operands":operands,"valueType":result_type}
        if item.kind=="convert" and len(item.operands)==1:
            target=item.cil_type.numeric if item.cil_type else None
            source=visit(item.operands[0],depth+1,"integer" if target=="decimal" else "decimal")
            if target not in {"integer","decimal"}: raise SourceExtractionError(f"unsupported {field_name} conversion at instruction {instruction_index}")
            if source["valueType"]==target: return source
            mode="exact" if target=="decimal" else "truncateTowardZero"
            return {"expression":source,"fromType":source["valueType"],"kind":"convert","mode":mode,"toType":target,"valueType":target}
        raise SourceExtractionError(f"unresolved {field_name} expression at instruction {instruction_index}: {item.kind}")
    return visit(value)
