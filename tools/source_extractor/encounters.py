"""Source-faithful encounter roster, candidate, and production extraction."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .ast import validate_selection
from .canonical import slugify_ascii_type_name, witness_sha256
from .cil_safety import validate_cil_slice
from .errors import SourceExtractionError

if TYPE_CHECKING:
    from .metadata import AssemblyMetadata


ENCOUNTER_NAMESPACE = "MegaCrit.Sts2.Core.Models.Encounters"
_MONSTER_GENERIC = re.compile(r" generic:MegaCrit\.Sts2\.Core\.Models\.Monsters\.([A-Za-z0-9]+)$")


def ref(simple: str) -> str:
    return "MONSTER." + slugify_ascii_type_name(simple)


def fixed(simple: str) -> dict[str, Any]:
    return {"kind": "fixed", "model": ref(simple)}


def sequence(*children: dict[str, Any], order: str = "fixed") -> dict[str, Any]:
    return {"children": list(children), "kind": "sequence", "order": order}


def uniform(*children: dict[str, Any]) -> dict[str, Any]:
    return {"choices": list(children), "kind": "uniformChoice"}


def _selection_provenance(record: dict[str, Any], semantic: Any, extra: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    methods = [
        {
            key: record[key]
            for key in (
                "assemblySha256",
                "cilInstructionsSha256",
                "diagnosticMetadataToken",
                "metadataSignature",
                "methodBodySha256",
                "normalizedInstructionsSha256",
                "symbolSignature",
            )
        }
    ]
    for item in extra or []:
        methods.append({key: item[key] for key in methods[0]})
    methods.sort(key=lambda item: item["symbolSignature"])
    return {
        "methods": methods,
        "normalizedSemanticWitnessSha256": witness_sha256(semantic),
        "semanticWitnessSha256": witness_sha256({"methods": [x["symbolSignature"] for x in methods], "selection": semantic}),
    }


def _method_without_instructions(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "instructions"}


def _model_calls(record: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for instruction in record["instructions"]:
        if instruction["opcode"] != "call" or not isinstance(instruction["operand"], str):
            continue
        if "MegaCrit.Sts2.Core.Models.ModelDb::Monster " not in instruction["operand"]:
            continue
        match = _MONSTER_GENERIC.search(instruction["operand"])
        if not match:
            raise SourceExtractionError(f"unresolved ModelDb.Monster signature in {record['symbolSignature']}: {instruction['operand']}")
        result.append(match.group(1))
    return result


_SPECIAL_SELECTIONS: dict[str, dict[str, Any]] = {
    # The delegate-cache branch in these methods occurs only after the fixed
    # collection has been fully populated.  Exact method hashes below bind
    # these reviewed fixed selections to that compiler-generated CFG.
    "CORPSE_SLUGS_NORMAL": sequence(
        fixed("CorpseSlug"), fixed("CorpseSlug"), fixed("CorpseSlug")
    ),
    "CORPSE_SLUGS_WEAK": sequence(fixed("CorpseSlug"), fixed("CorpseSlug")),
    "BOWLBUGS_NORMAL": sequence(
        fixed("BowlbugRock"),
        {
            "choices": [fixed("BowlbugEgg"), fixed("BowlbugSilk"), fixed("BowlbugNectar")],
            "constraint": "modelCountLimit",
            "count": 2,
            "draws": "withoutReplacement",
            "kind": "filteredChoice",
        },
    ),
    "BOWLBUGS_WEAK": sequence(
        fixed("BowlbugRock"),
        uniform(fixed("BowlbugEgg"), fixed("BowlbugNectar")),
    ),
    "FLYCONID_NORMAL": sequence(
        uniform(fixed("LeafSlimeM"), fixed("TwigSlimeM")),
        fixed("Flyconid"),
    ),
    "RUBY_RAIDERS_NORMAL": {
        "choices": [
            fixed("AxeRubyRaider"),
            fixed("AssassinRubyRaider"),
            fixed("BruteRubyRaider"),
            fixed("CrossbowRubyRaider"),
            fixed("TrackerRubyRaider"),
        ],
        "constraint": "modelCountLimit",
        "count": 3,
        "draws": "withoutReplacement",
        "kind": "filteredChoice",
    },
    "SLIMES_NORMAL": sequence(
        fixed("TwigSlimeM"),
        fixed("LeafSlimeM"),
        uniform(
            sequence(fixed("TwigSlimeS"), fixed("LeafSlimeS")),
            sequence(fixed("LeafSlimeS"), fixed("TwigSlimeS")),
        ),
    ),
    "SLIMES_WEAK": uniform(
        sequence(
            fixed("LeafSlimeS"),
            uniform(fixed("LeafSlimeM"), fixed("TwigSlimeM")),
            fixed("TwigSlimeS"),
        ),
        sequence(
            fixed("TwigSlimeS"),
            uniform(fixed("LeafSlimeM"), fixed("TwigSlimeM")),
            fixed("LeafSlimeS"),
        ),
    ),
    "SLITHERING_STRANGLER_NORMAL": sequence(
        uniform(
            fixed("SnappingJaxfruit"),
            uniform(fixed("LeafSlimeM"), fixed("TwigSlimeM")),
            sequence(
                uniform(fixed("LeafSlimeS"), fixed("TwigSlimeS")),
                uniform(fixed("LeafSlimeS"), fixed("TwigSlimeS")),
            ),
        ),
        fixed("SlitheringStrangler"),
    ),
}

# Semantic recognizers for the nine reviewed roster-selection shapes.  These
# hashes bind the normalized ASTs above to exact CIL instruction streams; a new
# input manifest must update/review these recognizers rather than reusing old
# semantics accidentally.
_SPECIAL_METHOD_IL: dict[str, dict[str, str]] = {
    "BOWLBUGS_NORMAL": {
        "MegaCrit.Sts2.Core.Models.Encounters.BowlbugsNormal::.cctor sig:000001": "9afc0e9886d48d42710eac46b91e18eaf8cddfe7e4fcfc77cc798d525cfef266",
        "MegaCrit.Sts2.Core.Models.Encounters.BowlbugsNormal::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "a51493f3aede3ca2d453c98353e54d2a6e108015508230b7d348fa7eb634c646",
        "MegaCrit.Sts2.Core.Models.Encounters.BowlbugsNormal+<>c__DisplayClass10_0::<GenerateMonsters>b__0 sig:2001021288e4": "531e19050edb33be78b0c067629ff12a5f16adc5771a2345662d6bec119cfeba",
        "MegaCrit.Sts2.Core.Models.Encounters.BowlbugsNormal+<>c__DisplayClass10_1::<GenerateMonsters>b__1 sig:2001021288e4": "e6e85088c27d9de37a90dfa07a4b21ca243a683e8d0aac007daac001178a1d7a",
    },
    "BOWLBUGS_WEAK": {
        "MegaCrit.Sts2.Core.Models.Encounters.BowlbugsWeak::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "0c0430d52fc0bb1ee6e368d5b8aac044399adee8154fec9934eb30ab623c9c19",
        "MegaCrit.Sts2.Core.Models.Encounters.BowlbugsWeak::get_Bugs sig:00001d1288e4": "8d56ed1ad34d474298ea08e4406f2b2251755a72d508ae59f1c47f3d5ab3d000",
    },
    "CORPSE_SLUGS_NORMAL": {
        "MegaCrit.Sts2.Core.Models.Encounters.CorpseSlugsNormal::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "bcb526ad7b9dcfff1ef1b0abff2e99e72e4a1bdca3ec274ececfa045160a848c",
    },
    "CORPSE_SLUGS_WEAK": {
        "MegaCrit.Sts2.Core.Models.Encounters.CorpseSlugsWeak::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "83c0e1cb2a9d9d15cd6be08ed145dce01f1ac0ea411f32fe29170c84286d4f28",
    },
    "FLYCONID_NORMAL": {
        "MegaCrit.Sts2.Core.Models.Encounters.FlyconidNormal::.cctor sig:000001": "8692429f55439174aac849d0e0cb8c419f2047b9fc1b4e7b63c82527b8dbd2c9",
        "MegaCrit.Sts2.Core.Models.Encounters.FlyconidNormal::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "cd0d7906a1ceac6bddea6e6087a9c4c300a8e1d6fa0abb12c17e1c27a59a7eec",
    },
    "RUBY_RAIDERS_NORMAL": {
        "MegaCrit.Sts2.Core.Models.Encounters.RubyRaidersNormal::.cctor sig:000001": "8dbe2a58c6227fc844244972e10a7bb1cacb9ec7c284f3bceb955378c8817fc5",
        "MegaCrit.Sts2.Core.Models.Encounters.RubyRaidersNormal::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "e21a20b7ac65ccc47f20f002fcd8447264313076359fe4f6fcf21bbeda61ceee",
        "MegaCrit.Sts2.Core.Models.Encounters.RubyRaidersNormal+<>c__DisplayClass5_0::<GenerateMonsters>b__0 sig:2001021288e4": "b092b54298765899f33043b1f8d7972b833b886a56f7e333835c4c3ee2dc16fd",
        "MegaCrit.Sts2.Core.Models.Encounters.RubyRaidersNormal+<>c__DisplayClass5_1::<GenerateMonsters>b__1 sig:2001021288e4": "550aaf803b7abcb9b68d2625674d806d508a1669260ac86c1d94fff65306d73c",
    },
    "SLIMES_NORMAL": {
        "MegaCrit.Sts2.Core.Models.Encounters.SlimesNormal::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "5ac1ae6ba10cd1fb5a3e37f05e1a47185e0e46230ff47086382399350bd1426d",
    },
    "SLIMES_WEAK": {
        "MegaCrit.Sts2.Core.Models.Encounters.SlimesWeak::.cctor sig:000001": "67ebedbfe4a7abc41e3e7ef25a8ceb31199b954911cf8d78eb874350bbbbd180",
        "MegaCrit.Sts2.Core.Models.Encounters.SlimesWeak::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "5a5f31f35763b108d67dddf98bacfa088e7fd62169e2488f16e776c1bf38a0bd",
    },
    "SLITHERING_STRANGLER_NORMAL": {
        "MegaCrit.Sts2.Core.Models.Encounters.SlitheringStranglerNormal::.cctor sig:000001": "573d3a4b14b4d55d94a1d241f50087069184b824d0f5454c6b3ee44755e24620",
        "MegaCrit.Sts2.Core.Models.Encounters.SlitheringStranglerNormal::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "34a29a0a52e4fc8c352e5c6ee7f2fb3a3375723ce2d4a890efc79a2a84192f49",
    },
}

# Dense Vegetation is intentionally not represented by a hardcoded selection.
# Its reviewed foreach CFG produces one Wriggler for every exact source slot;
# the slot count is derived from get_Slots and both methods are hash-bound.
_SLOT_LOOP_METHOD_IL: dict[str, dict[str, str]] = {
    "DENSE_VEGETATION_EVENT_ENCOUNTER": {
        "MegaCrit.Sts2.Core.Models.Encounters.DenseVegetationEventEncounter::GenerateMonsters sig:2000151281fd01151182e9021288e40e": "9d0459ca4af4eaaf921f7eb16b738c2a043eac4bd18d3de950d808b23fa2d122",
        "MegaCrit.Sts2.Core.Models.Encounters.DenseVegetationEventEncounter::get_Slots sig:2000151281fd010e": "71ecd23ab3ccd7e361e4e82a718904b350595d2c7591fb60b1b51f242ca73976",
    },
}

# RNG in these methods initializes per-monster state and does not alter model
# identity/cardinality. Keeping this explicit prevents a "fixed roster" label
# from implying that the whole GenerateMonsters method is deterministic.
_NON_ROSTER_RNG = {
    "DECIMILLIPEDE_ELITE",
    "PUNCH_OFF_EVENT_ENCOUNTER",
    "SCROLLS_OF_BITING_NORMAL",
    "SCROLLS_OF_BITING_WEAK",
    "TWO_TAILED_RATS_NORMAL",
}


# Generic fixed-roster methods in the pinned build use only these reviewed CIL
# shapes.  Keeping these lists exact prevents a newly introduced helper call,
# branch, collection operation, or state input from being flattened into a
# sequence of ModelDb call sites.
_FIXED_ROSTER_OPCODES = {
    "add", "call", "callvirt", "castclass", "dup", "ldarg.0",
    "ldc.i4.0", "ldc.i4.1", "ldc.i4.2", "ldc.i4.3", "ldc.i4.4",
    "ldc.i4.s", "ldloc.0", "ldloc.1", "ldloc.2", "ldloc.3",
    "ldloc.s", "ldnull", "ldstr", "newarr", "newobj", "rem", "ret",
    "stelem", "stloc.0", "stloc.1", "stloc.2", "stloc.3", "stloc.s",
}
_SLOT_CTOR = "<TypeSpec:151182e9021288e40e>::.ctor sig:20020113001301"
_LIST_CTOR = "<TypeSpec:1512809901151182e9021288e40e>::.ctor sig:200001"
_LIST_ADD = "<TypeSpec:1512809901151182e9021288e40e>::Add sig:2001011300"
_ARRAY_COLLECTION_CTOR = "<TypeSpec:1512b74801151182e9021288e40e>::.ctor sig:2001011d1300"
_SINGLE_COLLECTION_CTOR = "<TypeSpec:1512b75001151182e9021288e40e>::.ctor sig:2001011300"
_TO_MUTABLE = "MegaCrit.Sts2.Core.Models.MonsterModel::ToMutable sig:20001288e4"
_FIXED_ROSTER_CALLS = {
    _SLOT_CTOR, _LIST_CTOR, _LIST_ADD, _ARRAY_COLLECTION_CTOR,
    _SINGLE_COLLECTION_CTOR,
    "<TypeSpec:151281fd010e>::get_Item sig:2001130008",
    "MegaCrit.Sts2.Core.Models.EncounterModel::get_Rng sig:2000128544",
    "MegaCrit.Sts2.Core.Models.EncounterModel::get_Slots sig:2000151281fd010e",
    _TO_MUTABLE,
    "MegaCrit.Sts2.Core.Models.Monsters.Chomper::set_ScreamFirst sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment::set_StarterMoveIdx sig:20010108",
    "MegaCrit.Sts2.Core.Models.Monsters.Inklet::set_MiddleInklet sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.KinFollower::set_StartsWithDance sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.Nibbit::set_IsAlone sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.Nibbit::set_IsFront sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.PunchConstruct::set_StartingHpReduction sig:20010108",
    "MegaCrit.Sts2.Core.Models.Monsters.PunchConstruct::set_StartsWithFastPunch sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.ScrollOfBiting::set_StarterMoveIdx sig:20010108",
    "MegaCrit.Sts2.Core.Models.Monsters.Toadpole::set_IsFront sig:20010102",
    "MegaCrit.Sts2.Core.Models.Monsters.TwoTailedRat::set_StarterMoveIndex sig:20010108",
    "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:20010808",
    "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:2002080808",
}
_SETTER_CALLS = {item for item in _FIXED_ROSTER_CALLS if "::set_" in item}
_FIXED_CALL_OPCODES = {
    _SLOT_CTOR: "newobj",
    _LIST_CTOR: "newobj",
    _LIST_ADD: "callvirt",
    _ARRAY_COLLECTION_CTOR: "newobj",
    _SINGLE_COLLECTION_CTOR: "newobj",
    _TO_MUTABLE: "callvirt",
    "<TypeSpec:151281fd010e>::get_Item sig:2001130008": "callvirt",
    "MegaCrit.Sts2.Core.Models.EncounterModel::get_Rng sig:2000128544": "call",
    "MegaCrit.Sts2.Core.Models.EncounterModel::get_Slots sig:2000151281fd010e": "callvirt",
    "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:20010808": "callvirt",
    "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:2002080808": "callvirt",
    **{item: "callvirt" for item in _SETTER_CALLS},
}
_MODEL_CALL = "MegaCrit.Sts2.Core.Models.ModelDb::Monster "
_REVIEWED_BASE_CASTS = {
    "DecimillipedeSegmentFront": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment",
    "DecimillipedeSegmentMiddle": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment",
    "DecimillipedeSegmentBack": "MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment",
}


@dataclass
class _RosterArray:
    members: list[str | None]


@dataclass
class _RosterCollection:
    members: list[str]


_SCALAR = object()
_RNG = object()
_SLOTS = object()


def _local_index(opcode: str, operand: Any) -> str:
    if opcode.endswith(".0") or opcode.endswith(".1") or opcode.endswith(".2") or opcode.endswith(".3"):
        return opcode[-1]
    if opcode.endswith(".s") and isinstance(operand, str) and operand.startswith("local("):
        return operand
    raise SourceExtractionError(f"unresolved local operand for fixed roster: {opcode} {operand!r}")


def _pop(stack: list[Any], where: str) -> Any:
    if not stack:
        raise SourceExtractionError(f"CIL stack underflow while compiling fixed roster at {where}")
    return stack.pop()


def _expect_scalar(value: Any, where: str) -> None:
    if isinstance(value, (_RosterArray, _RosterCollection)) or (isinstance(value, tuple) and value and value[0] in {"model", "slot"}):
        raise SourceExtractionError(f"unexpected roster value in scalar position at {where}")


def _integer_constant(opcode: str, operand: Any) -> int | None:
    values = {f"ldc.i4.{value}": value for value in range(5)}
    if opcode in values:
        return values[opcode]
    if opcode == "ldc.i4.s" and type(operand) is int:
        return operand
    return None


def _compile_fixed_selection(record: dict[str, Any]) -> dict[str, Any]:
    """Interpret a reviewed straight-line collection builder, never call sites."""
    instructions = record.get("instructions")
    if not isinstance(instructions, list):
        raise SourceExtractionError("fixed roster method has no normalized CIL instructions")
    normalized = [{"opcode": item.get("opcode"), "operand": item.get("operand")} for item in instructions]
    model_operands = {
        item["operand"]
        for item in normalized
        if item["opcode"] == "call" and isinstance(item["operand"], str) and _MODEL_CALL in item["operand"]
    }
    for operand in model_operands:
        if _MONSTER_GENERIC.search(operand) is None:
            raise SourceExtractionError(f"unresolved ModelDb.Monster signature in {record.get('symbolSignature')}: {operand}")
    validate_cil_slice(
        normalized,
        allowed_opcodes=_FIXED_ROSTER_OPCODES,
        allowed_calls=_FIXED_ROSTER_CALLS | model_operands,
        maximum_instructions=256,
    )
    if set(_FIXED_CALL_OPCODES) != _FIXED_ROSTER_CALLS:
        raise SourceExtractionError("internal fixed-roster call policy is incomplete")
    for item in normalized:
        if item["opcode"] not in {"call", "callvirt", "newobj"}:
            continue
        expected_opcode = "call" if item["operand"] in model_operands else _FIXED_CALL_OPCODES[item["operand"]]
        if item["opcode"] != expected_opcode:
            raise SourceExtractionError(
                f"unrecognized invocation opcode for fixed-roster call: "
                f"{item['opcode']} {item['operand']}"
            )

    stack: list[Any] = []
    locals_: dict[str, Any] = {}
    returned: _RosterCollection | None = None
    for index, item in enumerate(normalized):
        opcode, operand = item["opcode"], item["operand"]
        where = f"instruction {index} ({opcode})"
        constant = _integer_constant(opcode, operand)
        if constant is not None:
            stack.append(constant)
        elif opcode in {"ldarg.0", "ldnull", "ldstr"}:
            stack.append(_SCALAR)
        elif opcode.startswith("stloc"):
            locals_[_local_index(opcode, operand)] = _pop(stack, where)
        elif opcode.startswith("ldloc"):
            key = _local_index(opcode, operand)
            if key not in locals_:
                raise SourceExtractionError(f"read of unresolved local in fixed roster at {where}")
            stack.append(locals_[key])
        elif opcode == "dup":
            if not stack:
                _pop(stack, where)
            stack.append(stack[-1])
        elif opcode in {"add", "rem"}:
            _expect_scalar(_pop(stack, where), where)
            _expect_scalar(_pop(stack, where), where)
            stack.append(_SCALAR)
        elif opcode == "castclass":
            value = _pop(stack, where)
            if not (isinstance(value, tuple) and value[0] == "model"):
                raise SourceExtractionError(f"castclass did not consume a monster at {where}")
            expected_types = {
                "MegaCrit.Sts2.Core.Models.Monsters." + value[1],
                _REVIEWED_BASE_CASTS.get(value[1]),
            } - {None}
            if operand not in expected_types:
                raise SourceExtractionError(
                    f"castclass target does not match the monster in "
                    f"{record.get('symbolSignature')} at {where}: {value[1]} -> {operand}"
                )
            stack.append(value)
        elif opcode == "newarr":
            count = _pop(stack, where)
            if type(count) is not int or count <= 0 or count > 32 or operand != "TypeSpec:151182e9021288e40e":
                raise SourceExtractionError(f"unresolved fixed roster array construction at {where}")
            stack.append(_RosterArray([None] * count))
        elif opcode == "stelem":
            value, element_index, array = _pop(stack, where), _pop(stack, where), _pop(stack, where)
            if operand != "TypeSpec:151182e9021288e40e":
                raise SourceExtractionError(f"unresolved fixed roster array element type at {where}")
            if not isinstance(array, _RosterArray) or type(element_index) is not int or not (isinstance(value, tuple) and value[0] == "slot"):
                raise SourceExtractionError(f"unresolved fixed roster array write at {where}")
            if element_index < 0 or element_index >= len(array.members) or array.members[element_index] is not None:
                raise SourceExtractionError(f"invalid or duplicate fixed roster array index at {where}")
            array.members[element_index] = value[1]
        elif opcode == "call" and isinstance(operand, str) and _MODEL_CALL in operand:
            match = _MONSTER_GENERIC.search(operand)
            assert match is not None
            stack.append(("model", match.group(1)))
        elif operand == _TO_MUTABLE:
            value = _pop(stack, where)
            if not (isinstance(value, tuple) and value[0] == "model"):
                raise SourceExtractionError(f"ToMutable did not consume a monster at {where}")
            stack.append(value)
        elif operand == _SLOT_CTOR:
            slot_name, model = _pop(stack, where), _pop(stack, where)
            _expect_scalar(slot_name, where)
            if not (isinstance(model, tuple) and model[0] == "model"):
                raise SourceExtractionError(f"MonsterSlot constructor did not consume a monster at {where}")
            stack.append(("slot", model[1]))
        elif operand == _LIST_CTOR:
            stack.append(_RosterCollection([]))
        elif operand == _LIST_ADD:
            slot, collection = _pop(stack, where), _pop(stack, where)
            if not isinstance(collection, _RosterCollection) or not (isinstance(slot, tuple) and slot[0] == "slot"):
                raise SourceExtractionError(f"unresolved fixed roster Add at {where}")
            collection.members.append(slot[1])
        elif operand == _ARRAY_COLLECTION_CTOR:
            array = _pop(stack, where)
            if not isinstance(array, _RosterArray) or any(item is None for item in array.members):
                raise SourceExtractionError(f"incomplete fixed roster array at {where}")
            stack.append(_RosterCollection([str(item) for item in array.members]))
        elif operand == _SINGLE_COLLECTION_CTOR:
            slot = _pop(stack, where)
            if not (isinstance(slot, tuple) and slot[0] == "slot"):
                raise SourceExtractionError(f"single-item roster constructor did not consume a slot at {where}")
            stack.append(_RosterCollection([slot[1]]))
        elif operand == "MegaCrit.Sts2.Core.Models.EncounterModel::get_Rng sig:2000128544":
            _expect_scalar(_pop(stack, where), where)
            stack.append(_RNG)
        elif operand == "MegaCrit.Sts2.Core.Models.EncounterModel::get_Slots sig:2000151281fd010e":
            _expect_scalar(_pop(stack, where), where)
            stack.append(_SLOTS)
        elif operand == "<TypeSpec:151281fd010e>::get_Item sig:2001130008":
            _expect_scalar(_pop(stack, where), where)
            slots = _pop(stack, where)
            if slots is not _SLOTS:
                raise SourceExtractionError(f"slot lookup did not consume EncounterModel.Slots at {where}")
            stack.append(_SCALAR)
        elif operand in _SETTER_CALLS:
            _expect_scalar(_pop(stack, where), where)
            model = _pop(stack, where)
            if not (isinstance(model, tuple) and model[0] == "model"):
                raise SourceExtractionError(f"monster setter did not consume a monster at {where}")
        elif operand == "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:20010808":
            _expect_scalar(_pop(stack, where), where)
            if _pop(stack, where) is not _RNG:
                raise SourceExtractionError(f"NextInt did not consume encounter RNG at {where}")
            stack.append(_SCALAR)
        elif operand == "MegaCrit.Sts2.Core.Random.Rng::NextInt sig:2002080808":
            _expect_scalar(_pop(stack, where), where)
            _expect_scalar(_pop(stack, where), where)
            if _pop(stack, where) is not _RNG:
                raise SourceExtractionError(f"NextInt did not consume encounter RNG at {where}")
            stack.append(_SCALAR)
        elif opcode == "ret":
            value = _pop(stack, where)
            if not isinstance(value, _RosterCollection) or not value.members:
                raise SourceExtractionError("fixed roster method did not return a non-empty proven collection")
            if stack:
                raise SourceExtractionError("residual evaluation stack after fixed roster return")
            if index != len(normalized) - 1 or returned is not None:
                raise SourceExtractionError("fixed roster method has unresolved return control flow")
            returned = value
        else:  # validate_cil_slice should make this unreachable.
            raise SourceExtractionError(f"unhandled allowed fixed-roster instruction at {where}: {operand}")

    if returned is None:
        raise SourceExtractionError("fixed roster method has no proven return")
    return sequence(*(fixed(item) for item in returned.members))


_SLOT_LOOP_OPCODES = {
    "br.s", "brfalse.s", "brtrue.s", "call", "callvirt", "castclass",
    "endfinally", "ldarg.0", "ldc.i4.0", "ldloc.0", "ldloc.1",
    "ldloc.2", "ldloc.3", "leave.s", "newobj", "ret", "stloc.0",
    "stloc.1", "stloc.2", "stloc.3",
}
_SLOT_LOOP_CALLS = {
    _LIST_CTOR, _LIST_ADD, _SLOT_CTOR, _TO_MUTABLE,
    "MegaCrit.Sts2.Core.Models.EncounterModel::get_Slots sig:2000151281fd010e",
    "<TypeSpec:151281f5010e>::GetEnumerator sig:20001512825d011300",
    "<TypeSpec:1512825d010e>::get_Current sig:20001300",
    "MegaCrit.Sts2.Core.Models.Monsters.Wriggler::set_StartStunned sig:20010102",
    "System.Collections.IEnumerator::MoveNext sig:200002",
    "System.IDisposable::Dispose sig:200001",
}
_SLOT_GETTER_OPCODES = {
    "dup", "ldc.i4.0", "ldc.i4.1", "ldc.i4.2", "ldc.i4.3", "ldc.i4.4",
    "ldstr", "newarr", "newobj", "ret", "stelem.ref",
}
_SLOT_ARRAY_CTOR = "<TypeSpec:1512b748010e>::.ctor sig:2001011d1300"


def _derive_fixed_slot_names(getter_instructions: list[dict[str, Any]]) -> list[str]:
    """Derive a bounded fixed string-array getter or fail without a guess."""
    getter_instructions = [{"opcode": x.get("opcode"), "operand": x.get("operand")} for x in getter_instructions]
    validate_cil_slice(
        getter_instructions,
        allowed_opcodes=_SLOT_GETTER_OPCODES,
        allowed_calls={_SLOT_ARRAY_CTOR},
        maximum_instructions=64,
    )
    if len(getter_instructions) < 4:
        raise SourceExtractionError("slot getter has no proven fixed cardinality")
    slot_count = _integer_constant(getter_instructions[0]["opcode"], getter_instructions[0]["operand"])
    if type(slot_count) is not int or slot_count <= 0 or slot_count > 32:
        raise SourceExtractionError("slot getter has an unresolved fixed cardinality")
    if len(getter_instructions) != 2 + 4 * slot_count + 2 or getter_instructions[1] != {"opcode": "newarr", "operand": "System.String"}:
        raise SourceExtractionError("slot getter is not a proven fixed string array")
    slot_names: list[str] = []
    for expected_index in range(slot_count):
        start = 2 + expected_index * 4
        duplicate, index_value, name, store = getter_instructions[start : start + 4]
        if duplicate != {"opcode": "dup", "operand": None} or store != {"opcode": "stelem.ref", "operand": None}:
            raise SourceExtractionError("slot getter has an unresolved array store")
        if _integer_constant(index_value["opcode"], index_value["operand"]) != expected_index:
            raise SourceExtractionError("slot getter has a missing, duplicate, or unordered slot index")
        if name["opcode"] != "ldstr" or not isinstance(name["operand"], str) or not name["operand"].startswith("string:"):
            raise SourceExtractionError("slot getter has an unresolved slot identity")
        slot_names.append(name["operand"])
    if getter_instructions[-2:] != [
        {"opcode": "newobj", "operand": _SLOT_ARRAY_CTOR},
        {"opcode": "ret", "operand": None},
    ] or len(set(slot_names)) != slot_count:
        raise SourceExtractionError("slot getter has unresolved or duplicate slot identities")
    return slot_names


def _compile_slot_loop_selection(record: dict[str, Any], getter: dict[str, Any]) -> dict[str, Any]:
    """Prove the reviewed foreach CFG and derive its exact source slot count."""
    actual = {
        item["symbolSignature"]: item["normalizedInstructionsSha256"]
        for item in (record, getter)
    }
    expected = _SLOT_LOOP_METHOD_IL["DENSE_VEGETATION_EVENT_ENCOUNTER"]
    if actual != expected:
        raise SourceExtractionError(f"unrecognized required slot-loop roster CIL: {actual!r}")

    generate = [{"opcode": x["opcode"], "operand": x["operand"]} for x in record["instructions"]]
    model_operands = {
        item["operand"] for item in generate
        if item["opcode"] == "call" and isinstance(item["operand"], str) and _MODEL_CALL in item["operand"]
    }
    expected_model = "MegaCrit.Sts2.Core.Models.ModelDb::Monster sig:1001001e00 generic:MegaCrit.Sts2.Core.Models.Monsters.Wriggler"
    if model_operands != {expected_model}:
        raise SourceExtractionError(f"slot-loop monster body is unresolved: {sorted(model_operands)!r}")
    validate_cil_slice(generate, allowed_opcodes=_SLOT_LOOP_OPCODES, allowed_calls=_SLOT_LOOP_CALLS | model_operands)

    offsets = {item["offsetDiagnostic"]: index for index, item in enumerate(record["instructions"])}
    edges: list[tuple[int, str, int]] = []
    for index, item in enumerate(record["instructions"]):
        if item["opcode"] in {"br.s", "brtrue.s", "brfalse.s", "leave.s"}:
            target = offsets.get(item["operand"])
            if target is None:
                raise SourceExtractionError("slot-loop branch target is outside the method CFG")
            edges.append((index, item["opcode"], target))
    if edges != [(6, "br.s", 22), (24, "brtrue.s", 7), (25, "leave.s", 31), (27, "brfalse.s", 30)]:
        raise SourceExtractionError(f"unrecognized slot-loop CFG edges: {edges!r}")

    slot_names = _derive_fixed_slot_names(getter["instructions"])
    return sequence(*(fixed("Wriggler") for _ in slot_names))


def _required_special_methods(assembly: AssemblyMetadata, source_type: str, canonical_id: str, assembly_sha256: str) -> list[dict[str, Any]]:
    names: list[tuple[str, str]] = []
    if canonical_id in {"BOWLBUGS_NORMAL", "RUBY_RAIDERS_NORMAL", "SLIMES_WEAK", "SLITHERING_STRANGLER_NORMAL"}:
        names.append((source_type, ".cctor"))
    if canonical_id == "BOWLBUGS_WEAK":
        names.append((source_type, "get_Bugs"))
    if canonical_id in _SLOT_LOOP_METHOD_IL:
        names.append((source_type, "get_Slots"))
    if canonical_id == "FLYCONID_NORMAL":
        names.append((source_type, ".cctor"))
    if canonical_id == "BOWLBUGS_NORMAL":
        names.extend([
            (source_type + "+<>c__DisplayClass10_0", "<GenerateMonsters>b__0"),
            (source_type + "+<>c__DisplayClass10_1", "<GenerateMonsters>b__1"),
        ])
    if canonical_id == "RUBY_RAIDERS_NORMAL":
        names.extend([
            (source_type + "+<>c__DisplayClass5_0", "<GenerateMonsters>b__0"),
            (source_type + "+<>c__DisplayClass5_1", "<GenerateMonsters>b__1"),
        ])
    result: list[dict[str, Any]] = []
    for owner, name in names:
        matches = assembly.find_methods(owner, name)
        if len(matches) != 1:
            raise SourceExtractionError(f"required roster helper {owner}::{name} matched {len(matches)} methods")
        result.append(assembly.method_record(matches[0], assembly_sha256))
    return result


def _all_type_model_references(assembly: AssemblyMetadata, source_type: str, assembly_sha256: str) -> tuple[set[str], list[dict[str, Any]]]:
    """Collect source model references and exact contributing methods."""
    result: set[str] = set()
    methods: list[dict[str, Any]] = []
    for index, row in enumerate(assembly.md.MethodDef.rows, 1):
        owner = assembly.type_names.get(assembly.method_owner.get(index), "")
        if owner != source_type and not owner.startswith(source_type + "+"):
            continue
        if not row.Rva:
            continue
        record = assembly.method_record(index, assembly_sha256)
        calls = _model_calls(record)
        if calls:
            result.update(ref(item) for item in calls)
            methods.append(_method_without_instructions(record))
    methods.sort(key=lambda item: item["symbolSignature"])
    return result, methods


def _membership_provenance(models: set[str], methods: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = sorted(models)
    return {
        "methods": methods,
        "normalizedSemanticWitness": normalized,
        "normalizedSemanticWitnessSha256": witness_sha256(normalized),
        "semanticWitnessSha256": witness_sha256({"members": normalized, "methods": [item["symbolSignature"] for item in methods]}),
    }


def _fabricator_pools(assembly: AssemblyMetadata, assembly_sha256: str) -> tuple[list[dict[str, Any]], set[str]]:
    owner = "MegaCrit.Sts2.Core.Models.Monsters.Fabricator"
    matches = assembly.find_methods(owner, ".cctor")
    if len(matches) != 1:
        raise SourceExtractionError("Fabricator static spawn pools are unresolved")
    record = assembly.method_record(matches[0], assembly_sha256)
    models = _model_calls(record)
    expected = ["Zapbot", "Stabbot", "Guardbot", "Noisebot"]
    if models != expected:
        raise SourceExtractionError(f"Fabricator spawn pool drift: got {models!r}, expected {expected!r}")
    provenance = {
        "assemblySha256": assembly_sha256,
        "cilInstructionsSha256": record["cilInstructionsSha256"],
        "diagnosticMetadataToken": record["diagnosticMetadataToken"],
        "metadataSignature": record["metadataSignature"],
        "methodBodySha256": record["methodBodySha256"],
        "normalizedInstructionsSha256": record["normalizedInstructionsSha256"],
        "symbolSignature": record["symbolSignature"],
    }
    pools = [
        {"members": [ref("Zapbot"), ref("Stabbot")], "poolId": "aggressive", "provenance": provenance},
        {"members": [ref("Guardbot"), ref("Noisebot")], "poolId": "defensive", "provenance": provenance},
    ]
    return pools, {item for pool in pools for item in pool["members"]}


def extract_rosters(
    dll_path: Path,
    assembly_sha256: str,
    encounter_census: dict[str, Any],
    known_models: set[str],
    *,
    assembly: AssemblyMetadata | None = None,
) -> dict[str, Any]:
    owns_assembly = assembly is None
    if assembly is None:
        from .metadata import AssemblyMetadata
        assembly = AssemblyMetadata(Path(dll_path))
    try:
        fabricator_pools, fabricator_models = _fabricator_pools(assembly, assembly_sha256)
        output: dict[str, list[dict[str, Any]]] = {"ordinary": [], "event": []}
        ordinary_members: set[str] = set()
        event_members: set[str] = set()

        for kind in ("ordinary", "event"):
            for source in encounter_census[kind]:
                source_type, canonical_id = source["sourceType"], source["canonicalId"]
                matches = assembly.find_methods(source_type, "GenerateMonsters")
                if len(matches) != 1:
                    raise SourceExtractionError(f"required roster method {source_type}::GenerateMonsters matched {len(matches)} methods")
                generate = assembly.method_record(matches[0], assembly_sha256)
                extras = _required_special_methods(assembly, source_type, canonical_id, assembly_sha256)
                if canonical_id in _SPECIAL_SELECTIONS:
                    actual_methods = {
                        item["symbolSignature"]: item["cilInstructionsSha256"]
                        for item in [generate, *extras]
                    }
                    if actual_methods != _SPECIAL_METHOD_IL[canonical_id]:
                        raise SourceExtractionError(
                            f"unrecognized required roster CIL for {canonical_id}: {actual_methods!r}"
                        )
                    selection = deepcopy(_SPECIAL_SELECTIONS[canonical_id])
                elif canonical_id in _SLOT_LOOP_METHOD_IL:
                    if len(extras) != 1:
                        raise SourceExtractionError(f"required slot getter is unresolved for {canonical_id}")
                    selection = _compile_slot_loop_selection(generate, extras[0])
                else:
                    selection = _compile_fixed_selection(generate)
                low, high, initial_members = validate_selection(selection, known_models=known_models)
                if low <= 0 or high < low:
                    raise SourceExtractionError(f"invalid roster cardinality for {canonical_id}")

                semantic = {
                    "cardinality": {"maximum": high, "minimum": low},
                    "selection": selection,
                }
                selection_provenance = _selection_provenance(generate, semantic, extras)
                selection["provenance"] = selection_provenance
                initial_fact = {
                    "cardinality": semantic["cardinality"],
                    "provenance": selection_provenance,
                    "selection": selection,
                }
                possible_references, possible_methods = _all_type_model_references(assembly, source_type, assembly_sha256)
                possible = possible_references | initial_members
                production_pools: list[dict[str, Any]] = []
                if canonical_id == "FABRICATOR_NORMAL":
                    possible |= fabricator_models
                    production_pools = fabricator_pools
                    pool_method = production_pools[0]["provenance"]
                    possible_methods.append(pool_method)
                    possible_methods.sort(key=lambda item: item["symbolSignature"])
                unresolved = possible - known_models
                if unresolved:
                    raise SourceExtractionError(f"unresolved possible model references for {canonical_id}: {sorted(unresolved)!r}")
                produced = possible - initial_members
                record = {
                    "canonicalId": canonical_id,
                    "initialRoster": initial_fact,
                    "kind": kind,
                    "nonRosterInitializationRng": canonical_id in _NON_ROSTER_RNG,
                    "possibleMonsters": sorted(possible),
                    "possibleMonstersProvenance": _membership_provenance(possible, possible_methods),
                    "producedMonsters": sorted(produced),
                    "producedMonstersProvenance": _membership_provenance(produced, possible_methods),
                    "productionPools": production_pools,
                    "rosterMethod": _method_without_instructions(generate),
                }
                output[kind].append(record)
                (ordinary_members if kind == "ordinary" else event_members).update(possible)

        for values in output.values():
            values.sort(key=lambda item: item["canonicalId"])
        event_only = event_members - ordinary_members
        if len(output["ordinary"]) != 81 or len(output["event"]) != 8:
            raise SourceExtractionError("post-roster encounter count drift")
        if len(ordinary_members) != 102:
            raise SourceExtractionError(f"ordinary model reachability drift: got {len(ordinary_members)}, expected 102")
        if len(event_only) != 6 or len(ordinary_members | event_members) != 108:
            raise SourceExtractionError(f"event model reachability drift: event-only={len(event_only)}, total={len(ordinary_members | event_members)}")
        return {
            "event": output["event"],
            "eventOnlyModels": sorted(event_only),
            "eventReachableModels": sorted(event_members),
            "ordinary": output["ordinary"],
            "ordinaryReachableModels": sorted(ordinary_members),
            "reachableModels": sorted(ordinary_members | event_members),
        }
    finally:
        if owns_assembly:
            assembly.close()
