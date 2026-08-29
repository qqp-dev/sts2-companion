"""Small stdlib-only guards shared by bounded CIL slice interpreters."""

from __future__ import annotations

from typing import Any, Collection

from .errors import SourceExtractionError


def validate_cil_slice(
    instructions: Any,
    *,
    allowed_opcodes: Collection[str],
    allowed_calls: Collection[str] = (),
    maximum_instructions: int = 4096,
) -> None:
    if not isinstance(instructions, list) or len(instructions) > maximum_instructions:
        raise SourceExtractionError("invalid or over-depth CIL slice")
    for index, instruction in enumerate(instructions):
        if not isinstance(instruction, dict) or set(instruction) != {"opcode", "operand"}:
            raise SourceExtractionError(f"malformed CIL instruction {index}")
        opcode = instruction["opcode"]
        if opcode not in allowed_opcodes:
            if isinstance(opcode, str) and (opcode.startswith("br") or opcode in {"switch", "leave", "leave.s"}):
                raise SourceExtractionError(f"unsupported branch opcode on required CIL slice: {opcode}")
            raise SourceExtractionError(f"unknown opcode on required CIL slice: {opcode}")
        if opcode in {"call", "callvirt", "newobj"}:
            operand = instruction["operand"]
            if not isinstance(operand, str) or operand not in allowed_calls:
                raise SourceExtractionError(f"unknown call/signature on required CIL slice: {operand}")
