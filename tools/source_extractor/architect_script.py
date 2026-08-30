"""Source-derived terminal script for The Architect.

The extractor reads only pinned CLI metadata/CIL and the selected ancients
localization mapping supplied by :mod:`extractor`.  Dialogue values are used
only to compute witnesses and are never returned.  Template cardinalities,
character keys, visits, lines, attackers, and localization keys are discovered
from source shape before any version regression assertions are applied.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from .canonical import witness_sha256
from .cil_eval import CilDataFlow, SymbolicValue, integer_constant
from .errors import SourceExtractionError

_EVENT = "EVENT.THE_ARCHITECT"
_ENCOUNTER = "ENCOUNTER.THE_ARCHITECT_EVENT_ENCOUNTER"
_OWNER = "MegaCrit.Sts2.Core.Models.Events.TheArchitect"
_DIALOGUE = "MegaCrit.Sts2.Core.Entities.Ancients.AncientDialogue"
_DIALOGUE_SET = "MegaCrit.Sts2.Core.Entities.Ancients.AncientDialogueSet"
_LAYOUT = "MegaCrit.Sts2.Core.Nodes.Events.NCombatEventLayout"
_COMBAT_ROOM = "MegaCrit.Sts2.Core.Nodes.Rooms.NCombatRoom"
_RUN_MANAGER = "MegaCrit.Sts2.Core.Runs.RunManager"
_EVENT_SYNC = "MegaCrit.Sts2.Core.Multiplayer.Game.EventCombatSynchronizer"
_SCORE_CALL = "MegaCrit.Sts2.Core.Runs.ScoreUtility::CalculateScore"
_OPTION_CTOR = "MegaCrit.Sts2.Core.Events.EventOption::.ctor"

_PRESENTATION_COMMANDS = {
    "MegaCrit.Sts2.Core.Commands.Cmd::Wait",
    "MegaCrit.Sts2.Core.Commands.CreatureCmd::TriggerAnim",
    "MegaCrit.Sts2.Core.Commands.TalkCmd::Play",
    "MegaCrit.Sts2.Core.Commands.VfxCmd::PlayOnCreature",
    "MegaCrit.Sts2.Core.Commands.VfxCmd::PlayOnCreatureCenter",
}
_PRESENTATION_SINKS = {
    "MegaCrit.Sts2.Core.Bindings.MegaSpine.MegaAnimationState::SetAnimation": "animationTrack",
    "MegaCrit.Sts2.Core.Commands.Cmd::Wait": "wait",
    "MegaCrit.Sts2.Core.Commands.CreatureCmd::TriggerAnim": "triggerAnimation",
    "MegaCrit.Sts2.Core.Commands.TalkCmd::Play": "talkSpeechBubble",
    "MegaCrit.Sts2.Core.Commands.VfxCmd::PlayOnCreature": "creatureVfx",
    "MegaCrit.Sts2.Core.Commands.VfxCmd::PlayOnCreatureCenter": "creatureCenterVfx",
    "MegaCrit.Sts2.Core.Nodes.NGame::ScreenShake": "screenShake",
    "MegaCrit.Sts2.Core.Nodes.Vfx.NDamageNumVfx::Create": "damageNumberVfx",
    "MegaCrit.Sts2.Core.Nodes.Vfx.NFireBurstVfx::Create": "fireVfx",
    "MegaCrit.Sts2.Core.Nodes.Vfx.NHitSparkVfx::Create": "hitVfx",
    "MegaCrit.Sts2.Core.Nodes.Vfx.NSpeechBubbleVfx::AnimOut": "speechBubbleAnimation",
}
_PRESENTATION_METHOD_NAMES = {
    "AnimArchitectAttackIfNecessary", "AnimPlayerAttackIfNecessary", "DivideWildly",
    "GetArchitectAnimationState", "GetSpeaker", "PlayCurrentLine", "ShowSpeechBubble",
}
_NORMALIZED_CONTROL = {
    "MegaCrit.Sts2.Core.Models.EventModel::ClearCurrentOptions": "clearOptions",
    "MegaCrit.Sts2.Core.Models.EventModel::SetEventState": "setEventState",
    "MegaCrit.Sts2.Core.Models.Events.TheArchitect::set_CurrentLineIndex": "lineIndexWrite",
    "MegaCrit.Sts2.Core.Models.Events.TheArchitect::set_Dialogue": "dialogueWrite",
    "MegaCrit.Sts2.Core.Models.Events.TheArchitect::set_Score": "scoreWrite",
    "MegaCrit.Sts2.Core.Runs.RunManager::WinRun": "terminalWinRun",
    "MegaCrit.Sts2.Core.Runs.RunManager::OnEnded": "lifecycleDependency",
    "MegaCrit.Sts2.Core.Runs.RunManager::GuaranteeKillAllPlayers": "lifecycleDependency",
    _SCORE_CALL: "scoreReference",
}
_CALL_OPS = {"call", "callvirt", "newobj"}
# Pinned only after the source-driven semantic classifier independently closed
# the v0.111.0 component. This is an exact residual declaration vocabulary,
# never a namespace/prefix ignore.
_RESIDUAL_VOCABULARY_SIZE = 174
_RESIDUAL_VOCABULARY_SHA256 = "7aac765fd42a8282414bed67181b4a066deff87a9cef9fc322aaf3037011df7a"


def _base(symbol: str) -> str:
    return symbol.split(" sig:", 1)[0]


def _method(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in (
        "assemblySha256", "cilInstructionsSha256", "metadataSignature",
        "methodBodySha256", "normalizedInstructionsSha256", "symbolSignature",
    )}


def _find(assembly: Any, owner: str, name: str, sha: str) -> tuple[int, dict[str, Any]]:
    matches = [i for i in assembly.find_methods(owner, name) if assembly.md.MethodDef.rows[i - 1].Rva]
    if len(matches) != 1:
        raise SourceExtractionError(f"Architect root {owner}::{name} matched {len(matches)} methods")
    return matches[0], assembly.method_record(matches[0], sha)


def _find_symbol(assembly: Any, symbol: str, sha: str) -> tuple[int, dict[str, Any]]:
    matches = [i for i in range(1, len(assembly.md.MethodDef.rows) + 1)
               if assembly.method_symbol(i) == symbol and assembly.md.MethodDef.rows[i - 1].Rva]
    if len(matches) != 1:
        raise SourceExtractionError(f"Architect source symbol {symbol!r} matched {len(matches)} methods")
    return matches[0], assembly.method_record(matches[0], sha)



def _async_body(assembly: Any, owner: str, name: str, sha: str) -> tuple[int, dict[str, Any]]:
    prefix = owner + "+<" + name + ">d__"
    matches = [(i, assembly.method_record(i, sha)) for i, method in enumerate(assembly.md.MethodDef.rows, 1)
               if method.Rva and str(method.Name) == "MoveNext"
               and assembly.type_names.get(assembly.method_owner.get(i), "").startswith(prefix)]
    if len(matches) != 1:
        raise SourceExtractionError(f"Architect async body {owner}::{name} matched {len(matches)} methods")
    return matches[0]

def _owner_records(assembly: Any, owner: str, sha: str) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    for type_index, physical in assembly.type_names.items():
        if physical != owner and not physical.startswith(owner + "+"):
            continue
        for method in assembly.md.TypeDef.rows[type_index - 1].MethodList:
            if method.row.Rva:
                rows.append((method.row_index, assembly.method_record(method.row_index, sha)))
    return sorted(rows, key=lambda row: row[1]["symbolSignature"])


def _integer(instructions: list[Mapping[str, Any]], index: int, context: str) -> int:
    if index < 0:
        raise SourceExtractionError(f"missing Architect integer for {context}")
    value = integer_constant(instructions[index])
    if value is None:
        raise SourceExtractionError(f"non-constant Architect integer for {context} at {index}")
    return value


def _enum_values(assembly: Any, suffix: str) -> dict[int, str]:
    matches = [(i, name) for i, name in assembly.type_names.items() if name.endswith("." + suffix)]
    if len(matches) != 1:
        raise SourceExtractionError(f"Architect enum {suffix} matched {len(matches)} CLI types")
    type_index, type_name = matches[0]
    if assembly.base_by_type.get(type_name) != "System.Enum":
        raise SourceExtractionError(f"Architect enum {type_name} is not a CLI enum")
    result: dict[int, str] = {}
    constants = assembly.md.Constant.rows
    for field in assembly.md.TypeDef.rows[type_index - 1].FieldList:
        if str(field.row.Name) == "value__":
            continue
        rows = [row for row in constants if getattr(getattr(row, "Parent", None), "row", None) is field.row]
        if len(rows) != 1 or int(rows[0].Type) != 8:
            raise SourceExtractionError(f"Architect enum member {type_name}.{field.row.Name} lacks one Int32 constant")
        raw = bytes(rows[0].Value.value)
        if len(raw) != 4:
            raise SourceExtractionError(f"Architect enum member {type_name}.{field.row.Name} has malformed value")
        value = int.from_bytes(raw, "little", signed=True)
        if value in result:
            raise SourceExtractionError(f"Architect enum {type_name} has duplicate value {value}")
        result[value] = str(field.row.Name)
    if not result:
        raise SourceExtractionError(f"Architect enum {type_name} is empty")
    return result


def _setter_constant(instructions: list[Mapping[str, Any]], start: int, end: int,
                     setter: str, *, required: bool, default: int = 0) -> int:
    calls = [i for i in range(start, end) if instructions[i]["opcode"] in {"call", "callvirt"}
             and _base(str(instructions[i].get("operand", ""))) == setter]
    if not calls:
        if required:
            raise SourceExtractionError(f"Architect template lacks {setter}")
        return default
    if len(calls) != 1:
        raise SourceExtractionError(f"Architect template has {len(calls)} calls to {setter}")
    call = calls[0]
    if setter.endswith("::set_VisitIndex"):
        # Nullable<T> constructors resolve as TypeSpec; the source constant is
        # the nearest integer before the setter and after the dialogue ctor.
        candidates = [(i, integer_constant(instructions[i])) for i in range(start, call)]
        candidates = [(i, value) for i, value in candidates if value is not None]
        if not candidates:
            raise SourceExtractionError("Architect visit nullable constructor has no source integer")
        return int(candidates[-1][1])
    return _integer(instructions, call - 1, setter)


def discover_dialogue_templates(assembly: Any, assembly_sha256: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Decode the straight-line ``DefineDialogues`` collection initializer."""
    _, record = _find(assembly, _OWNER, "DefineDialogues", assembly_sha256)
    instructions = record["instructions"]
    if any(item["opcode"].startswith(("br", "leave")) or item["opcode"] == "switch" for item in instructions):
        raise SourceExtractionError("Architect dialogue declaration is no longer a straight-line collection initializer")
    character_calls = [i for i, item in enumerate(instructions)
                       if item["opcode"] == "call" and _base(str(item.get("operand", ""))) == _OWNER + "::CharKey"]
    if not character_calls:
        raise SourceExtractionError("Architect dialogue declaration has no source-discovered characters")
    attackers = _enum_values(assembly, "ArchitectAttackers")
    if set(attackers.values()) != {"None", "Player", "Architect", "Both"}:
        raise SourceExtractionError("Architect attacker enum variants changed or are incomplete")
    templates: list[dict[str, Any]] = []
    for char_order, call_index in enumerate(character_calls):
        symbol = str(instructions[call_index].get("operand", ""))
        match = re.search(r" generic:([^ ]+)$", symbol)
        if match is None:
            raise SourceExtractionError("Architect CharKey call lacks exact generic character identity")
        source_type = match.group(1)
        character_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", source_type.rsplit(".", 1)[-1]).upper()
        segment_end = character_calls[char_order + 1] if char_order + 1 < len(character_calls) else len(instructions)
        array_sites = [i for i in range(call_index, segment_end)
                       if instructions[i]["opcode"] == "newarr"
                       and str(instructions[i].get("operand")) == _DIALOGUE]
        if len(array_sites) != 1:
            raise SourceExtractionError(f"Architect character {source_type} has {len(array_sites)} dialogue arrays")
        array_index = array_sites[0]
        declared_count = _integer(instructions, array_index - 1, f"{source_type} template count")
        ctor_sites = [i for i in range(array_index + 1, segment_end)
                      if instructions[i]["opcode"] == "newobj"
                      and _base(str(instructions[i].get("operand", ""))) == _DIALOGUE + "::.ctor"]
        if declared_count != len(ctor_sites) or declared_count <= 0:
            raise SourceExtractionError(f"Architect character {source_type} dialogue array cardinality mismatch")
        for template_order, ctor_index in enumerate(ctor_sites):
            template_end = ctor_sites[template_order + 1] if template_order + 1 < len(ctor_sites) else segment_end
            line_arrays = [i for i in range(array_index + 1 if template_order == 0 else ctor_sites[template_order - 1] + 1, ctor_index)
                           if instructions[i]["opcode"] == "newarr"
                           and str(instructions[i].get("operand")) == "System.String"]
            if len(line_arrays) != 1:
                raise SourceExtractionError(f"Architect dialogue {source_type}/{template_order} has {len(line_arrays)} line arrays")
            line_array = line_arrays[0]
            line_count = _integer(instructions, line_array - 1, f"{source_type}/{template_order} line count")
            if line_count <= 0:
                raise SourceExtractionError("Architect dialogue may not contain an empty source line array")
            line_stores = [i for i in range(line_array + 1, ctor_index) if instructions[i]["opcode"] == "stelem.ref"]
            strings = [str(instructions[i].get("operand", "")) for i in range(line_array + 1, ctor_index)
                       if instructions[i]["opcode"] == "ldstr"]
            if len(line_stores) != line_count or strings != ["string:"] * line_count:
                raise SourceExtractionError("Architect dialogue SFX/line placeholder array shape changed")
            # The next stelem.ref stores the fully initialized dialogue object.
            stores = [i for i in range(ctor_index + 1, template_end) if instructions[i]["opcode"] == "stelem.ref"]
            if not stores:
                raise SourceExtractionError("Architect dialogue object is not stored in its declared collection")
            object_end = stores[0]
            visit = _setter_constant(instructions, ctor_index + 1, object_end,
                                     _DIALOGUE + "::set_VisitIndex", required=True)
            start_value = _setter_constant(instructions, ctor_index + 1, object_end,
                                           _DIALOGUE + "::set_StartAttackers", required=False)
            end_value = _setter_constant(instructions, ctor_index + 1, object_end,
                                         _DIALOGUE + "::set_EndAttackers", required=False)
            if start_value not in attackers or end_value not in attackers:
                raise SourceExtractionError("Architect dialogue uses an unknown attacker enum value")
            templates.append({
                "characterKey": character_key,
                "characterOrder": char_order,
                "characterSourceType": source_type,
                "endAttackers": attackers[end_value],
                "lineCount": line_count,
                "sourceOrder": template_order,
                "startAttackers": attackers[start_value],
                "templateId": f"ARCHITECT_DIALOGUE.{character_key}.{visit}",
                "visitIndex": visit,
            })
    ids = [row["templateId"] for row in templates]
    pairs = [(row["characterKey"], row["visitIndex"]) for row in templates]
    if len(ids) != len(set(ids)) or len(pairs) != len(set(pairs)):
        raise SourceExtractionError("Architect dialogue declaration has duplicate template identity")
    return templates, _method(record)


def _value_digest(key: str, value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        raise SourceExtractionError(f"Architect localization control key {key!r} is not a string")
    return {"key": key, "keyValueWitnessSha256": witness_sha256([key, value]),
            "valueSha256": witness_sha256(value)}


def join_localization_structure(templates: list[dict[str, Any]], localization: Mapping[str, Any],
                                blob: Mapping[str, Any], *, event_entry: str) -> dict[str, Any]:
    """Join discovered templates to structural keys without returning values."""
    if event_entry != _EVENT.removeprefix("EVENT."):
        raise SourceExtractionError(f"Architect localization entry identity changed: {event_entry!r}")
    talk_prefix = event_entry + ".talk."
    actual_talk = {key for key in localization if key.startswith(talk_prefix)}
    expected_talk: set[str] = set()
    lines_total = 0
    continuation_total = 0
    for template in templates:
        base = f"{talk_prefix}{template['characterKey']}.{template['visitIndex']}-"
        first_variants = []
        for repeat_suffix in ("", "r"):
            first_variants.append(any(f"{base}0{repeat_suffix}.{speaker}" in localization
                                      for speaker in ("ancient", "char")))
        if first_variants.count(True) != 1:
            raise SourceExtractionError(f"Architect template {template['templateId']} has ambiguous/missing repetition suffix")
        repeating = first_variants[1]
        suffix = "r" if repeating else ""
        lines: list[dict[str, Any]] = []
        for line_index in range(template["lineCount"]):
            stem = f"{base}{line_index}{suffix}"
            speaker_keys = [(speaker, f"{stem}.{speaker}") for speaker in ("ancient", "char")
                            if f"{stem}.{speaker}" in localization]
            if len(speaker_keys) != 1:
                raise SourceExtractionError(f"Architect line {stem} has {len(speaker_keys)} speaker mappings")
            speaker_suffix, line_key = speaker_keys[0]
            line = {
                "index": line_index,
                "lineId": f"{template['templateId']}.LINE.{line_index}",
                "lineLocalization": _value_digest(line_key, localization[line_key]),
                "speaker": "Ancient" if speaker_suffix == "ancient" else "Character",
            }
            expected_talk.add(line_key)
            if line_index < template["lineCount"] - 1:
                next_key = stem + ".next"
                if next_key not in localization:
                    raise SourceExtractionError(f"Architect continuation key {next_key!r} is missing")
                line["nextButtonLocalization"] = _value_digest(next_key, localization[next_key])
                expected_talk.add(next_key)
                continuation_total += 1
            elif stem + ".next" in localization:
                raise SourceExtractionError(f"Architect terminal line unexpectedly has a continuation key: {stem}.next")
            lines.append(line)
            lines_total += 1
        template["lines"] = lines
        template["repeating"] = repeating
    if actual_talk != expected_talk:
        missing = sorted(expected_talk - actual_talk)
        extra = sorted(actual_talk - expected_talk)
        raise SourceExtractionError(f"Architect localization talk-key closure differs; missing={missing!r}, extra={extra!r}")
    controls = []
    for key in ("PROCEED.description", event_entry + ".CONTINUE", event_entry + ".RESPOND"):
        if key not in localization:
            raise SourceExtractionError(f"Architect localization control key {key!r} is missing")
        controls.append(_value_digest(key, localization[key]))
    selected = controls + [_value_digest(key, localization[key]) for key in sorted(actual_talk)]
    key_witnesses = [{"key": row["key"], "keyValueWitnessSha256": row["keyValueWitnessSha256"],
                      "valueSha256": row["valueSha256"]} for row in selected]
    provenance = {key: blob[key] for key in (
        "entryFlags", "entryMd5", "entrySha256", "pckDirectoryOffset", "pckFileCount",
        "pckFormat", "pckGodotVersion", "pckPath", "pckSha256",
    )}
    return {
        "controlKeys": controls,
        "keyValueWitnesses": key_witnesses,
        "lineKeyCount": lines_total,
        "nextButtonKeyCount": continuation_total,
        "proseEmitted": False,
        "provenance": provenance,
        "selectedKeyCount": len(selected),
        "semanticWitnessSha256": witness_sha256(key_witnesses),
        "table": "ancients",
    }


def _flow(record: Mapping[str, Any]) -> dict[int, Any]:
    return CilDataFlow(record["instructions"]).run()


def _invocations(record: Mapping[str, Any], base: str) -> list[Any]:
    return [inv for inv in _flow(record).values() if _base(inv.symbol) == base]


def _constant(value: SymbolicValue, expected: int, context: str) -> None:
    if value.kind != "constant" or value.data != expected:
        raise SourceExtractionError(f"Architect {context} argument changed: {value!r}")


def _require_bases(record: Mapping[str, Any], bases: list[str], context: str) -> dict[str, int]:
    found: dict[str, list[int]] = {base: [] for base in bases}
    for index, item in enumerate(record["instructions"]):
        if item["opcode"] in _CALL_OPS:
            base = _base(str(item.get("operand", "")))
            if base in found:
                found[base].append(index)
    if any(len(rows) != 1 for rows in found.values()):
        raise SourceExtractionError(f"Architect {context} required call cardinality changed: {found!r}")
    return {base: rows[0] for base, rows in found.items()}


def _call_counts(record: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in record["instructions"]:
        if item["opcode"] in _CALL_OPS:
            base = _base(str(item.get("operand", "")))
            counts[base] = counts.get(base, 0) + 1
    return counts


def _require_call_counts(record: Mapping[str, Any], expected: Mapping[str, tuple[int, int | None]], context: str) -> None:
    counts = _call_counts(record)
    for base, (minimum, maximum) in expected.items():
        count = counts.get(base, 0)
        if count < minimum or (maximum is not None and count > maximum):
            raise SourceExtractionError(f"Architect {context} call {base} cardinality changed: {count}")


def _validate_dialogue_control_helpers(assembly: Any, sha: str) -> None:
    """Prove selection/key grammar from helpers rather than normalized prose."""
    _, char_key = _find(assembly, _OWNER, "CharKey", sha)
    _require_call_counts(char_key, {
        "MegaCrit.Sts2.Core.Models.ModelDb::Character": (1, 1),
        "MegaCrit.Sts2.Core.Models.AbstractModel::get_Id": (1, 1),
        "MegaCrit.Sts2.Core.Models.ModelId::get_Entry": (1, 1),
    }, "character key")

    _, dialogue_set_getter = _find(assembly, _OWNER, "get_DialogueSet", sha)
    _require_call_counts(dialogue_set_getter, {
        _OWNER + "::DefineDialogues": (1, 1),
        "MegaCrit.Sts2.Core.Models.AbstractModel::get_Id": (1, 1),
        "MegaCrit.Sts2.Core.Models.ModelId::get_Entry": (1, 1),
        _DIALOGUE_SET + "::PopulateLocKeys": (1, 1),
    }, "dialogue localization population")

    _, valid = _find(assembly, _DIALOGUE_SET, "GetValidDialogues", sha)
    _require_call_counts(valid, {
        _DIALOGUE_SET + "::get_FirstVisitEverDialogue": (2, 2),
        _DIALOGUE_SET + "::get_CharacterDialogues": (1, 1),
        _DIALOGUE_SET + "::get_AgnosticDialogues": (2, 2),
        "System.Linq.Enumerable::Where": (2, 2),
        "System.Linq.Enumerable::ToList": (2, 2),
        _DIALOGUE_SET + "::AddRepeatingDialogues": (2, 2),
    }, "valid-dialogue selection")
    if not any(item["opcode"].startswith("ble") for item in valid["instructions"]):
        raise SourceExtractionError("Architect exact dialogue candidates no longer precede repeating fallback")

    _, repeating = _find(assembly, _DIALOGUE_SET, "AddRepeatingDialogues", sha)
    _require_call_counts(repeating, {
        _DIALOGUE + "::get_IsRepeating": (1, 1), _DIALOGUE + "::get_VisitIndex": (2, 2),
    }, "repeating-dialogue fallback")
    repeating_ops = [item["opcode"] for item in repeating["instructions"]]
    if repeating_ops.count("clt") != 1 or repeating_ops.count("and") != 1:
        raise SourceExtractionError("Architect repeating visit-at-most comparison shape changed")

    closure_records = [record for _, record in _owner_records(assembly, _DIALOGUE_SET, sha)
                       if "<GetValidDialogues>b__" in record["symbolSignature"]]
    if len(closure_records) != 2:
        raise SourceExtractionError("Architect exact-visit selection closure is ambiguous")
    for record in closure_records:
        _require_call_counts(record, {_DIALOGUE + "::get_VisitIndex": (1, 1)}, "exact-visit closure")
        opcodes = [item["opcode"] for item in record["instructions"]]
        if opcodes.count("ceq") != 1 or opcodes.count("and") != 1:
            raise SourceExtractionError("Architect nullable exact-visit comparison shape changed")

    _, populate_set = _find(assembly, _DIALOGUE_SET, "PopulateLocKeys", sha)
    _require_call_counts(populate_set, {
        _DIALOGUE + "::PopulateLines": (2, None),
        _DIALOGUE + "::get_Lines": (1, None),
    }, "dialogue key population")
    _, populate_lines = _find(assembly, _DIALOGUE, "PopulateLines", sha)
    literal_values = {str(item.get("operand", ""))[7:] for item in populate_lines["instructions"]
                      if item["opcode"] == "ldstr" and str(item.get("operand", "")).startswith("string:")}
    required_literals = {".talk.", ".", "-0", "-", "r", ".ancient", ".char", "ancients"}
    if not required_literals <= literal_values:
        raise SourceExtractionError(f"Architect localization key grammar changed: {sorted(required_literals-literal_values)!r}")
    _require_call_counts(populate_lines, {
        _DIALOGUE + "::HasRepeatingSuffix": (2, 2),
        "MegaCrit.Sts2.Core.Localization.LocString::Exists": (1, 1),
        "MegaCrit.Sts2.Core.Entities.Ancients.AncientDialogueLine::set_LineText": (2, 2),
        "MegaCrit.Sts2.Core.Entities.Ancients.AncientDialogueLine::set_Speaker": (2, 2),
    }, "line/speaker localization")


def _validate_line_control_shape(play_body: Mapping[str, Any], assembly: Any, sha: str) -> None:
    _require_call_counts(play_body, {
        "MegaCrit.Sts2.Core.Context.LocalContext::IsMe": (1, 1),
        _OWNER + "::get_Dialogue": (1, None), _OWNER + "::get_CurrentLineIndex": (1, None),
        _DIALOGUE + "::get_Lines": (1, None),
        "MegaCrit.Sts2.Core.Entities.Ancients.AncientDialogueLine::get_LineText": (1, None),
        _OWNER + "::GetSpeaker": (1, 1),
    }, "current-line null/index/text/speaker control")
    conditional_branches = [item for item in play_body["instructions"]
                            if item["opcode"].startswith(("brtrue", "brfalse", "beq", "bne", "bge", "bgt", "ble", "blt"))]
    if len(conditional_branches) < 8:
        raise SourceExtractionError("Architect current-line early-return branch closure changed")
    _, get_speaker = _find(assembly, _OWNER, "GetSpeaker", sha)
    speaker_instructions = get_speaker["instructions"]
    enum_branches = [i for i, item in enumerate(speaker_instructions) if item["opcode"].startswith("beq")]
    enum_values = [integer_constant(speaker_instructions[i - 1]) for i in enum_branches]
    speaker_enum = _enum_values(assembly, "AncientDialogueSpeaker")
    if (len(enum_branches) != 2 or enum_values != [1, 2]
            or [speaker_enum.get(value) for value in enum_values] != ["Ancient", "Character"]
            or sum(item["opcode"] == "ldnull" for item in speaker_instructions) != 1):
        raise SourceExtractionError("Architect speaker enum branch/default mapping is ambiguous")


def _event_option(record: Mapping[str, Any], callback: str, option_kind: str) -> dict[str, Any]:
    sites = [(i, item) for i, item in enumerate(record["instructions"])
             if item["opcode"] == "newobj" and _base(str(item.get("operand", ""))) == _OPTION_CTOR]
    if len(sites) != 1:
        raise SourceExtractionError(f"Architect {option_kind} option constructor matched {len(sites)} sites")
    index, item = sites[0]
    pointers = [str(record["instructions"][i].get("operand", "")) for i in range(max(0, index - 24), index)
                if record["instructions"][i]["opcode"] in {"ldftn", "ldvirtftn"}]
    if pointers != [callback]:
        raise SourceExtractionError(f"Architect {option_kind} delegate binding changed: {pointers!r}")
    signature = callback.split(" sig:", 1)
    if len(signature) != 2:
        raise SourceExtractionError("Architect option callback lacks exact CLI signature")
    return {
        "callback": {"receiver": "eventInstance", "signature": signature[1], "target": callback},
        "constructionIndex": index,
        "constructionMethod": _method(record),
        "eventId": _EVENT,
        "optionId": f"EVENT_OPTION.THE_ARCHITECT/{option_kind}",
    }


def _collect_methods(assembly: Any, sha: str) -> list[tuple[int, dict[str, Any], str]]:
    rows: list[tuple[int, dict[str, Any], str]] = []
    for owner, role in ((_OWNER, "architectOwnerClosure"), (_DIALOGUE, "dialogueLineControlClosure"),
                        (_DIALOGUE_SET, "dialogueSelectionClosure")):
        rows.extend((i, record, role) for i, record in _owner_records(assembly, owner, sha))
    roots = [
        (_LAYOUT, "SetEvent", "visualOnlyLayout"), (_LAYOUT, "SetCombatRoomNode", "visualOnlyLayout"),
        (_COMBAT_ROOM, "Create", "visualOnlyRoomFactory"),
        (_RUN_MANAGER, "EnterNextAct", "architectPlacement"), (_RUN_MANAGER, "WinRun", "runTerminalBoundary"),
        (_EVENT_SYNC, "InitializeForEvent", "eventVisualStateInitialization"),
    ]
    for owner, name, role in roots:
        _, record = _find(assembly, owner, name, sha)
        rows.append((_find_symbol(assembly, record["symbolSignature"], sha)[0], record, role))
        prefix = owner + "+<" + name + ">d__"
        nested = [(i, assembly.method_record(i, sha)) for i, method in enumerate(assembly.md.MethodDef.rows, 1)
                  if method.Rva and str(method.Name) == "MoveNext"
                  and assembly.type_names.get(assembly.method_owner.get(i), "").startswith(prefix)]
        if len(nested) > 1:
            raise SourceExtractionError(f"Architect async root {owner}::{name} has ambiguous MoveNext bodies")
        rows.extend((i, record, role + "AsyncBody") for i, record in nested)
    unique: dict[str, tuple[int, dict[str, Any], set[str]]] = {}
    for index, record, role in rows:
        symbol = record["symbolSignature"]
        if symbol not in unique:
            unique[symbol] = (index, record, {role})
        else:
            unique[symbol][2].add(role)
    return [(index, record, ",".join(sorted(roles))) for index, record, roles in
            sorted(unique.values(), key=lambda row: row[1]["symbolSignature"])]


def _classify_calls(methods: list[tuple[int, dict[str, Any], str]]) -> dict[str, Any]:
    local_bases = {_base(record["symbolSignature"]) for _, record, _ in methods}
    decisions: list[dict[str, Any]] = []
    residual_symbols: set[str] = set()
    presentation_method_symbols = {record["symbolSignature"] for _, record, _ in methods
                                   if record["symbolSignature"].split("::", 1)[1].split(" sig:", 1)[0]
                                   in _PRESENTATION_METHOD_NAMES
                                   or any("<" + name + ">" in record["symbolSignature"]
                                          for name in _PRESENTATION_METHOD_NAMES)}
    presentation_categories: set[str] = set()
    for _, record, _ in methods:
        in_presentation = record["symbolSignature"] in presentation_method_symbols
        for index, item in enumerate(record["instructions"]):
            if item["opcode"] not in _CALL_OPS:
                continue
            symbol = str(item.get("operand", "")); base = _base(symbol)
            if (base.startswith("MegaCrit.Sts2.Core.Commands.DamageCmd::")
                    or base in {"MegaCrit.Sts2.Core.Commands.CreatureCmd::Damage",
                                "MegaCrit.Sts2.Core.Commands.CreatureCmd::Attack"}):
                raise SourceExtractionError(f"gameplay damage/attack entered Architect script closure: {symbol}")
            if base == "MegaCrit.Sts2.Core.Models.EventModel::EnterCombatWithoutExitingEvent":
                raise SourceExtractionError("active event-combat transition entered Architect terminal closure")
            if base.startswith("MegaCrit.Sts2.Core.Rewards.") or base.startswith("MegaCrit.Sts2.Core.Commands.RewardsCmd::"):
                raise SourceExtractionError(f"reward construction/dispatch entered Architect terminal closure: {symbol}")
            if base.startswith("MegaCrit.Sts2.Core.Commands.") and base not in _PRESENTATION_COMMANDS:
                raise SourceExtractionError(f"unclassified Architect command {symbol} in {record['symbolSignature']}")
            if (".Nodes.Vfx." in base or ".Commands.VfxCmd::" in base) and base not in _PRESENTATION_SINKS:
                raise SourceExtractionError(f"unclassified Architect VFX call {symbol} in {record['symbolSignature']}")
            if base in _NORMALIZED_CONTROL:
                classification = "normalizedControlOrDependency"
            elif base in _PRESENTATION_SINKS:
                classification = "presentationOnly"
                presentation_categories.add(_PRESENTATION_SINKS[base])
            elif base in local_bases:
                classification = "traversedExactHelper"
            elif base == _OPTION_CTOR:
                classification = "normalizedOptionFramework"
            elif (base.startswith("MegaCrit.Sts2.Core.Localization.")
                  or base.startswith(_DIALOGUE + "::") or base.startswith(_DIALOGUE_SET + "::")):
                classification = "localizationOrDialogueControl"
            elif base.startswith("MegaCrit.Sts2.Core.Random.Rng::"):
                classification = "typedRuntimeRng"
            else:
                classification = "sourceProvenFrameworkOrRuntimePlumbing"
                residual_symbols.add(symbol)
            if in_presentation and classification == "normalizedControlOrDependency" and base not in {
                "MegaCrit.Sts2.Core.Models.EventModel::SetEventState",
            }:
                raise SourceExtractionError(f"gameplay/control sink entered Architect presentation slice: {symbol}")
            decisions.append({"classification": classification, "instructionIndex": index,
                              "sourceMethod": record["symbolSignature"], "symbolSignature": symbol})
    decisions.sort(key=lambda row: (row["sourceMethod"], row["instructionIndex"], row["symbolSignature"]))
    residual = sorted(residual_symbols)
    residual_digest = witness_sha256(residual)
    if len(residual) != _RESIDUAL_VOCABULARY_SIZE or residual_digest != _RESIDUAL_VOCABULARY_SHA256:
        raise SourceExtractionError(
            f"Architect framework/runtime call vocabulary changed: {len(residual)} symbols, {residual_digest}"
        )
    return {
        "decisions": decisions,
        "presentationCategories": sorted(presentation_categories),
        "presentationMethodSymbols": sorted(presentation_method_symbols),
        "residualVocabulary": {"sha256": residual_digest, "size": len(residual)},
        "summary": {"denominator": len(decisions), "resolved": len(decisions), "unresolved": 0},
    }


def extract_architect_script(assembly: Any, assembly_sha256: str, placement: Mapping[str, Any],
                             localization: Mapping[str, Any], localization_blob: Mapping[str, Any]) -> dict[str, Any]:
    links = [row for row in placement["eventLinkage"] if row["canonicalEvent"] == _EVENT]
    if len(links) != 1:
        raise SourceExtractionError(f"Architect E1 event linkage matched {len(links)} rows")
    link = links[0]
    if link["canonicalEncounter"] != _ENCOUNTER or link["availabilityClassification"] != "sourceProvenNonPool":
        raise SourceExtractionError("Architect E1 owner/link/placement identity changed")
    nonpool = link.get("nonPoolPlacement")
    if not isinstance(nonpool, Mapping) or nonpool.get("kind") != "scriptedRunTransition":
        raise SourceExtractionError("Architect E1 non-pool placement proof is missing")
    _, enter_next_act = _find_symbol(assembly, nonpool["method"]["symbolSignature"], assembly_sha256)
    placement_required = {
        "MegaCrit.Sts2.Core.Runs.RunState::get_CurrentActIndex": (1, None),
        "MegaCrit.Sts2.Core.Runs.RunState::get_Acts": (1, 1),
        "MegaCrit.Sts2.Core.Rooms.AbstractRoom::get_IsVictoryRoom": (1, 1),
        "MegaCrit.Sts2.Core.Models.ModelDb::Event": (1, 1),
        "MegaCrit.Sts2.Core.Rooms.EventRoom::.ctor": (1, 1),
        _RUN_MANAGER + "::EnterRoom": (1, 1),
    }
    placement_calls: dict[str, list[int]] = {base: [] for base in placement_required}
    for index, item in enumerate(enter_next_act["instructions"]):
        if item["opcode"] in _CALL_OPS:
            base = _base(str(item.get("operand", "")))
            if base in placement_calls:
                placement_calls[base].append(index)
    for base, (minimum, maximum) in placement_required.items():
        count = len(placement_calls[base])
        if count < minimum or (maximum is not None and count > maximum):
            raise SourceExtractionError(f"Architect placement call {base} cardinality changed: {count}")
    guard_act_index = placement_calls["MegaCrit.Sts2.Core.Runs.RunState::get_CurrentActIndex"][0]
    guard_acts = placement_calls["MegaCrit.Sts2.Core.Runs.RunState::get_Acts"][0]
    guard_tail = enter_next_act["instructions"][guard_acts + 1:guard_acts + 5]
    if (guard_act_index >= guard_acts or len(guard_tail) != 4
            or guard_tail[0]["opcode"] != "callvirt" or "::get_Count sig:" not in str(guard_tail[0].get("operand", ""))
            or integer_constant(guard_tail[1]) != 1 or guard_tail[2]["opcode"] != "sub"
            or not guard_tail[3]["opcode"].startswith("blt")):
        raise SourceExtractionError("Architect last-act guard shape changed")
    victory_index = placement_calls["MegaCrit.Sts2.Core.Rooms.AbstractRoom::get_IsVictoryRoom"][0]
    victory_tail = enter_next_act["instructions"][victory_index + 1:victory_index + 5]
    if (len(victory_tail) != 4 or not victory_tail[0]["opcode"].startswith("brfalse")
            or victory_tail[2]["opcode"] != "newobj"
            or _base(str(victory_tail[2].get("operand", ""))) != "System.InvalidOperationException::.ctor"
            or victory_tail[3]["opcode"] != "throw"):
        raise SourceExtractionError("Architect victory-room throw branch shape changed")
    event_factory = next(str(item.get("operand", "")) for item in enter_next_act["instructions"]
                         if item["opcode"] == "call" and _base(str(item.get("operand", ""))) == "MegaCrit.Sts2.Core.Models.ModelDb::Event")
    if not event_factory.endswith(" generic:" + _OWNER):
        raise SourceExtractionError("Architect placement constructs a different event type")
    if not any(item["opcode"] == "throw" for item in enter_next_act["instructions"]):
        raise SourceExtractionError("Architect victory-room placement failure branch disappeared")
    placement_order = _require_bases(enter_next_act, [
        _RUN_MANAGER + "::FadeOut", _RUN_MANAGER + "::ClearScreens",
        "MegaCrit.Sts2.Core.Models.ModelDb::Event", "MegaCrit.Sts2.Core.Rooms.EventRoom::.ctor",
        _RUN_MANAGER + "::EnterRoom", _RUN_MANAGER + "::FadeIn",
    ], "placement control order")
    ordered_placement = [placement_order[_RUN_MANAGER + "::FadeOut"], placement_order[_RUN_MANAGER + "::ClearScreens"],
                         placement_order["MegaCrit.Sts2.Core.Models.ModelDb::Event"],
                         placement_order["MegaCrit.Sts2.Core.Rooms.EventRoom::.ctor"],
                         placement_order[_RUN_MANAGER + "::EnterRoom"], placement_order[_RUN_MANAGER + "::FadeIn"]]
    if ordered_placement != sorted(ordered_placement):
        raise SourceExtractionError("Architect placement entry control order changed")
    _require_bases(enter_next_act, [
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetException",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetResult",
    ], "placement async success/exception")

    templates, declaration_method = discover_dialogue_templates(assembly, assembly_sha256)
    _validate_dialogue_control_helpers(assembly, assembly_sha256)
    localization_structure = join_localization_structure(
        templates, localization, localization_blob, event_entry=_EVENT.removeprefix("EVENT."),
    )

    _, load = _find(assembly, _OWNER, "LoadDialogue", assembly_sha256)
    load_flow = _flow(load)
    valid_calls = [inv for inv in load_flow.values() if _base(inv.symbol) == _DIALOGUE_SET + "::GetValidDialogues"]
    rng_calls = [inv for inv in load_flow.values() if _base(inv.symbol).endswith("Rng::NextItem")]
    if len(valid_calls) != 1 or len(valid_calls[0].arguments) != 4 or len(rng_calls) != 1:
        raise SourceExtractionError("Architect dialogue selection call closure changed")
    _constant(valid_calls[0].arguments[3], 0, "includeAgnostic")
    load_bases = {_base(str(item.get("operand", ""))) for item in load["instructions"] if item["opcode"] in _CALL_OPS}
    for base in ("MegaCrit.Sts2.Core.Saves.ProgressState::GetStatsForCharacter",
                 "MegaCrit.Sts2.Core.Saves.CharacterStats::get_TotalWins",
                 "MegaCrit.Sts2.Core.Saves.ProgressState::get_Wins"):
        if base not in load_bases:
            raise SourceExtractionError(f"Architect dialogue selection input {base} is missing")

    _, initial = _find(assembly, _OWNER, "SetInitialEventState", assembly_sha256)
    _require_bases(initial, ["MegaCrit.Sts2.Core.Models.EventModel::GenerateInitialOptionsWrapper",
                             "MegaCrit.Sts2.Core.Models.EventModel::SetEventState"], "initial state")
    _, generate = _find(assembly, _OWNER, "GenerateInitialOptions", assembly_sha256)
    _require_bases(generate, [_OWNER + "::LoadDialogue", _OWNER + "::set_CurrentLineIndex",
                                               _OWNER + "::CreateOptionForCurrentLine", _OWNER + "::CreateProceedOption"],
                                   "initial options")
    initial_writes = _invocations(generate, _OWNER + "::set_CurrentLineIndex")
    if len(initial_writes) != 1:
        raise SourceExtractionError("Architect line-zero initialization is ambiguous")
    _constant(initial_writes[0].arguments[0], 0, "initial line index")
    _, continue_method = _find(assembly, _OWNER, "CreateOptionForCurrentLine", assembly_sha256)
    _, proceed_method = _find(assembly, _OWNER, "CreateProceedOption", assembly_sha256)
    options = [
        _event_option(continue_method, _OWNER + "::AdvanceDialogue sig:2000128121", "CURRENT_LINE"),
        _event_option(proceed_method, _OWNER + "::WinRun sig:2000128121", "PROCEED"),
    ]

    _, layout_type = _find(assembly, _OWNER, "get_LayoutType", assembly_sha256)
    layout_constant = _integer(layout_type["instructions"], 0, "layout type")
    layout_enums = _enum_values(assembly, "EventLayoutType")
    if layout_enums.get(layout_constant) != "Combat":
        raise SourceExtractionError("Architect event layout is no longer Combat")
    _, canonical_encounter = _find(assembly, _OWNER, "get_CanonicalEncounter", assembly_sha256)
    encounter_calls = [str(item.get("operand", "")) for item in canonical_encounter["instructions"]
                       if item["opcode"] == "call" and _base(str(item.get("operand", ""))) == "MegaCrit.Sts2.Core.Models.ModelDb::Encounter"]
    if encounter_calls != ["MegaCrit.Sts2.Core.Models.ModelDb::Encounter sig:1001001e00 generic:MegaCrit.Sts2.Core.Models.Encounters.TheArchitectEventEncounter"]:
        raise SourceExtractionError("Architect canonical encounter factory changed")
    _, layout_set = _find(assembly, _LAYOUT, "SetEvent", assembly_sha256)
    room_create = _invocations(layout_set, _COMBAT_ROOM + "::Create")
    if len(room_create) != 1 or len(room_create[0].arguments) != 2:
        raise SourceExtractionError("Architect visual combat room factory call is ambiguous")
    mode_value = room_create[0].arguments[1]
    if mode_value.kind != "constant" or type(mode_value.data) is not int:
        raise SourceExtractionError("Architect combat room mode is not an exact source enum constant")
    room_modes = _enum_values(assembly, "CombatRoomMode")
    if room_modes.get(mode_value.data) != "VisualOnly":
        raise SourceExtractionError("Architect pseudo-combat room is not VisualOnly")

    _, room_enter = _find(assembly, _OWNER, "OnRoomEnter", assembly_sha256)
    score_calls = _invocations(room_enter, _SCORE_CALL)
    if len(score_calls) != 1 or len(score_calls[0].arguments) != 2:
        raise SourceExtractionError("Architect room-entry score overload is ambiguous")
    _constant(score_calls[0].arguments[1], 1, "score won")
    room_order = _require_bases(room_enter, [
        "MegaCrit.Sts2.Core.Platform.StatsManager::RefreshGlobalStats",
        _SCORE_CALL, _OWNER + "::set_Score", "MegaCrit.Sts2.Core.Context.LocalContext::IsMe",
        "MegaCrit.Sts2.Core.Bindings.MegaSpine.MegaAnimationState::SetAnimation",
        "MegaCrit.Sts2.Core.Models.EventModel::ClearCurrentOptions", _OWNER + "::PlayCurrentLine",
        "MegaCrit.Sts2.Core.Helpers.TaskHelper::RunSafely",
    ], "room entry")
    if not (room_order[_SCORE_CALL] < room_order[_OWNER + "::set_Score"] < room_order["MegaCrit.Sts2.Core.Context.LocalContext::IsMe"]):
        raise SourceExtractionError("Architect room-entry score/local-owner control order changed")

    _, advance_body = _async_body(assembly, _OWNER, "AdvanceDialogue", assembly_sha256)
    advance_order = _require_bases(advance_body, [
        _OWNER + "::set_CurrentLineIndex", _OWNER + "::PlayCurrentLine",
        _OWNER + "::CreateOptionForCurrentLine", _OWNER + "::CreateProceedOption",
        "MegaCrit.Sts2.Core.Models.EventModel::SetEventState",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetException",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetResult",
    ], "line advance")
    if not (advance_order[_OWNER + "::set_CurrentLineIndex"] < advance_order[_OWNER + "::PlayCurrentLine"]
            < advance_order["MegaCrit.Sts2.Core.Models.EventModel::SetEventState"]):
        raise SourceExtractionError("Architect line increment/play/state order changed")

    _, play_body = _async_body(assembly, _OWNER, "PlayCurrentLine", assembly_sha256)
    _validate_line_control_shape(play_body, assembly, assembly_sha256)
    play_required = _require_bases(play_body, [
        "MegaCrit.Sts2.Core.Context.LocalContext::IsMe", _OWNER + "::AnimPlayerAttackIfNecessary",
        _OWNER + "::AnimArchitectAttackIfNecessary", _OWNER + "::ShowSpeechBubble",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetException",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetResult",
    ], "current-line playback")
    if not (play_required[_OWNER + "::AnimPlayerAttackIfNecessary"]
            < play_required[_OWNER + "::AnimArchitectAttackIfNecessary"]
            < play_required[_OWNER + "::ShowSpeechBubble"]):
        raise SourceExtractionError("Architect line presentation order changed")

    _, terminal_body = _async_body(assembly, _OWNER, "WinRun", assembly_sha256)
    terminal_order = _require_bases(terminal_body, [
        "MegaCrit.Sts2.Core.Context.LocalContext::IsMe", _OWNER + "::AnimPlayerAttackIfNecessary",
        _OWNER + "::AnimArchitectAttackIfNecessary", _RUN_MANAGER + "::WinRun",
        "MegaCrit.Sts2.Core.Models.EventModel::SetEventState",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetException",
        "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetResult",
    ], "terminal")
    required_order = [terminal_order[_OWNER + "::AnimPlayerAttackIfNecessary"],
                      terminal_order[_OWNER + "::AnimArchitectAttackIfNecessary"],
                      terminal_order[_RUN_MANAGER + "::WinRun"],
                      terminal_order["MegaCrit.Sts2.Core.Models.EventModel::SetEventState"]]
    if required_order != sorted(required_order) or terminal_order["MegaCrit.Sts2.Core.Context.LocalContext::IsMe"] >= required_order[0]:
        raise SourceExtractionError("Architect local-owner terminal call/animation order changed")

    _, run_win_body = _async_body(assembly, _RUN_MANAGER, "WinRun", assembly_sha256)
    run_order = _require_bases(run_win_body, [_RUN_MANAGER + "::get_State", _RUN_MANAGER + "::OnEnded",
                                               _RUN_MANAGER + "::GuaranteeKillAllPlayers",
                                               "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetException",
                                               "System.Runtime.CompilerServices.AsyncTaskMethodBuilder::SetResult"],
                               "run terminal dependency")
    on_ended = _invocations(run_win_body, _RUN_MANAGER + "::OnEnded")
    if len(on_ended) != 1 or len(on_ended[0].arguments) != 1:
        raise SourceExtractionError("RunManager.OnEnded terminal call is ambiguous")
    _constant(on_ended[0].arguments[0], 1, "OnEnded victory")
    if not (run_order[_RUN_MANAGER + "::get_State"] < run_order[_RUN_MANAGER + "::OnEnded"]
            < run_order[_RUN_MANAGER + "::GuaranteeKillAllPlayers"]):
        raise SourceExtractionError("RunManager terminal lifecycle ordering changed")

    line_nodes: list[dict[str, Any]] = []
    line_edges: list[dict[str, Any]] = []
    for template in templates:
        for line in template["lines"]:
            line_nodes.append({"index": line["index"], "kind": "localizedDialogueLine",
                               "nodeId": line["lineId"], "speaker": line["speaker"],
                               "templateRef": template["templateId"]})
            terminal_line = line["index"] == template["lineCount"] - 1
            target = (f"{template['templateId']}.LINE.{line['index'] + 1}" if not terminal_line
                      else "ARCHITECT_NODE.TERMINAL_PROCEED")
            line_edges.append({"edgeId": line["lineId"] + (".CONTINUE" if not terminal_line else ".PROCEED"),
                               "from": line["lineId"], "kind": "continuation" if not terminal_line else "terminalProceed",
                               "order": line["index"], "to": target})

    methods = _collect_methods(assembly, assembly_sha256)
    invocation_census = _classify_calls(methods)
    method_rows = [{"method": _method(record), "role": role} for _, record, role in methods]
    dependencies = [
        {"dependencyId": "FORMULA.SCORE_UTILITY.CALCULATE_SCORE", "kind": "formula", "status": "pendingE2e"},
        {"dependencyId": "LIFECYCLE.RUN.ON_ENDED_TRUE", "kind": "lifecycle", "status": "pendingE2d2"},
        {"dependencyId": "LIFECYCLE.RUN.GUARANTEE_KILL_ALL_PLAYERS", "kind": "lifecycle", "status": "pendingE2d2"},
        {"dependencyId": "LIFECYCLE.RUN.SERIALIZED_SCORE_STATS_HISTORY", "kind": "lifecycle", "status": "pendingE2d2"},
        {"dependencyId": "LIFECYCLE.RUN.ARCHITECT_TERMINAL_ORDER", "kind": "lifecycle", "status": "pendingE2d2"},
    ]
    result = {
        "applicability": {
            "canonicalEncounter": _ENCOUNTER, "canonicalEvent": _EVENT,
            "e1EventLinkRef": "SOURCE.EVENT_LINK." + _ENCOUNTER,
            "eventSourceType": link["eventSourceType"], "ownerMultiplicity": "perMutablePlayerEventInstance",
        },
        "dependencies": dependencies,
        "dialogue": {
            "declarationMethod": declaration_method,
            "selection": {
                "agnosticCandidatesIncluded": False,
                "candidateOrder": ["exactNullableVisitEqualsCharacterWins", "repeatingVisitAtMostCharacterWinsWhenNoExact"],
                "characterIdInput": "event.owner.character.id",
                "characterWinsInput": "progress.characterStats.totalWinsOrZeroWhenMissing",
                "concreteTemplate": {"kind": "runtimeSelection", "valueType": "AncientDialogue"},
                "globalProgressInput": "progress.wins",
                "method": _method(load), "rngInput": "event.rng.nextItem(validCandidates)",
            },
            "templates": templates,
        },
        "initialState": {
            "emptyDescriptionKey": "PROCEED.description",
            "lineIndexInitialization": 0,
            "missingOrEmptyDialogueBranch": "createProceedOption",
            "nonEmptyDialogueBranch": "setLineZeroAndCreateCurrentLineOption",
            "options": options,
            "setInitialMethod": _method(initial),
        },
        "invocationCensus": invocation_census,
        "lineControl": {
            "advanceMethod": _method(advance_body),
            "asyncExceptionSemantics": "SetExceptionNotSuccess",
            "branches": [
                "nonLocalOwnerEarlyReturn", "missingDialogueEarlyReturn", "negativeOrPastEndIndexEarlyReturn",
                "missingLineTextEarlyReturn", "missingSpeakerEntityEarlyReturn", "missingCreatureNodeNoAnimation",
                "missingAnimationStateNoAnimation", "lineZeroStartAttackSequence", "continuation",
                "terminalProceed", "defensiveOutOfRangeProceed",
            ],
            "edges": line_edges, "nodes": line_nodes,
            "playMethod": _method(play_body),
        },
        "localization": localization_structure,
        "methods": method_rows,
        "placement": {
            "asyncExceptionSemantics": "SetExceptionNotSuccess",
            "entryOrder": ["fadeOut", "clearScreens", "constructArchitectEventRoom", "enterRoom", "fadeIn"],
            "failureBranch": {"condition": "currentRoom.isVictoryRoom", "outcome": "throw"},
            "guard": {"kind": "compare", "left": "run.currentActIndex", "operator": "greaterThanOrEqual",
                      "right": "run.acts.countMinusOne"},
            "method": _method(enter_next_act), "placementKind": "scriptedRunTransition",
        },
        "presentation": {
            "apparentDamageClassification": "damageNumberVfxNotHpDamage",
            "categories": invocation_census["presentationCategories"],
            "completeSliceHasGameplayDamage": False,
            "scoreSplit": {"count": {"kind": "runtimeInput", "name": "character.architectAttackVfx.count", "valueType": "integer"},
                           "formula": "sourceReferencedDivideWildly", "renderDeterministically": False,
                           "rng": "event.rng", "score": "event.score"},
            "sliceMethodSymbols": invocation_census["presentationMethodSymbols"],
        },
        "roomEntry": {
            "architectLookup": "firstEnemySideCreatureNodeOrNull",
            "localOwnerBranch": "readingAnimationClearOptionsAndRunPlayCurrentLineSafely",
            "method": _method(room_enter),
            "scoreReference": {"arguments": ["event.owner.runState", True], "destination": "event.score",
                               "formulaRef": "FORMULA.SCORE_UTILITY.CALCULATE_SCORE",
                               "symbolSignature": score_calls[0].symbol},
            "statsRefresh": True,
        },
        "runtimeContracts": [
            {"domain": "sourceCharacterModelId", "name": "event.owner.character.id", "valueType": "ModelId"},
            {"domain": "zeroWhenCharacterStatsMissing", "name": "progress.characterStats.totalWins", "valueType": "integer"},
            {"domain": "globalProgress", "name": "progress.wins", "valueType": "integer"},
            {"domain": "validDialogueCandidateChoice", "name": "event.rng.nextItem", "valueType": "runtimeRng"},
            {"domain": "ScoreUtilityResult", "name": "event.score", "valueType": "integer"},
            {"domain": "characterArchitectAttackVfxCollection", "name": "presentation.vfxCount", "valueType": "integer"},
            {"domain": "DivideWildlyRandomWeights", "name": "presentation.scoreSplitRng", "valueType": "runtimeRng"},
            {"domain": "selectedDialogueLineRange", "name": "event.currentLineIndex", "valueType": "integer"},
        ],
        "semanticEffects": [
            {"effectId": "ARCHITECT_EFFECT.SELECT_DIALOGUE", "kind": "stateWrite", "target": "event.dialogue"},
            {"effectId": "ARCHITECT_EFFECT.INIT_LINE_ZERO", "kind": "stateWrite", "target": "event.currentLineIndex"},
            {"effectId": "ARCHITECT_EFFECT.ADVANCE_LINE", "kind": "stateWrite", "target": "event.currentLineIndex"},
            {"effectId": "ARCHITECT_EFFECT.CAPTURE_SCORE", "formulaRef": "FORMULA.SCORE_UTILITY.CALCULATE_SCORE", "kind": "stateWrite", "target": "event.score"},
            {"effectId": "ARCHITECT_EFFECT.WIN_RUN", "dependencyRef": "LIFECYCLE.RUN.ARCHITECT_TERMINAL_ORDER", "kind": "terminalSink", "target": "runManager"},
            {"effectId": "ARCHITECT_EFFECT.FINISH_EMPTY_OPTIONS", "kind": "stateWrite", "target": "event.currentOptions"},
        ],
        "sourceDenominators": {
            "dependencies": len(dependencies), "edges": len(line_edges),
            "invocations": invocation_census["summary"]["denominator"],
            "localizationKeys": localization_structure["selectedKeyCount"],
            "methods": len(method_rows), "nodes": len(line_nodes), "options": len(options),
            "presentationMethods": len(invocation_census["presentationMethodSymbols"]),
            "runtimeContracts": 8, "semanticEffects": 6,
            "templates": len(templates), "lines": sum(row["lineCount"] for row in templates),
        },
        "terminal": {
            "cleanupBoundary": {"classification": "commonEventFrameworkIfExitReached", "frameworkRole": "EnsureCleanup"},
            "eventCombatTransition": False, "finishedState": "emptyOptionCollection",
            "localOwnerGuarded": True, "method": _method(terminal_body),
            "noResume": True, "noRewardPage": True,
            "orderedControl": ["animatePlayerEndAttackers", "animateArchitectEndAttackers",
                               "localOwnerRunManagerWinRun", "awaitWinRun", "setEmptyOptionsFinishedState"],
            "runManagerBoundary": {"missingRunState": "returnWithoutOnEndedOrForcedKills",
                                   "onEndedArgument": True,
                                   "order": ["OnEnded(true)", "GuaranteeKillAllPlayers"],
                                   "method": _method(run_win_body)},
        },
        "visualOnlyCombat": {
            "canonicalEncounter": _ENCOUNTER, "classification": "notActiveCombat",
            "hiddenTurnFactRole": "referencedNoOpTurnFactNotScriptCompleteness",
            "layoutMethod": _method(layout_set), "layoutType": "Combat",
            "roomMode": "VisualOnly", "roomModeValue": int(mode_value.data),
        },
    }
    validate_architect_script(result)
    return result


def _no_text_values(value: Any, path: str = "architect") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"value", "text", "prose", "template"}:
                raise SourceExtractionError(f"{path}.{key}: localized text/prose may not be emitted")
            _no_text_values(child, path + "." + str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _no_text_values(child, f"{path}[{index}]")


def validate_architect_script(value: Any) -> None:
    if not isinstance(value, Mapping):
        raise SourceExtractionError("Architect event script must be an object")
    required = {"applicability", "dependencies", "dialogue", "initialState", "invocationCensus",
                "lineControl", "localization", "methods", "placement", "presentation", "roomEntry",
                "runtimeContracts", "semanticEffects", "sourceDenominators", "terminal", "visualOnlyCombat"}
    if set(value) != required:
        raise SourceExtractionError(f"Architect event script keys differ: {sorted(set(value) ^ required)}")
    _no_text_values(value)
    applicability = value["applicability"]
    if applicability.get("canonicalEvent") != _EVENT or applicability.get("canonicalEncounter") != _ENCOUNTER:
        raise SourceExtractionError("Architect applicability owner/link identity changed")
    templates = value["dialogue"].get("templates")
    if not isinstance(templates, list) or not templates:
        raise SourceExtractionError("Architect template census is empty")
    template_ids = [row.get("templateId") for row in templates]
    if None in template_ids or len(template_ids) != len(set(template_ids)):
        raise SourceExtractionError("Architect template identities are missing/duplicate")
    line_ids: set[str] = set()
    expected_template_fields = {"characterKey", "characterOrder", "characterSourceType", "endAttackers", "lineCount",
                                "lines", "repeating", "sourceOrder", "startAttackers", "templateId", "visitIndex"}
    selected_line_localizations = []
    for template in templates:
        if set(template) != expected_template_fields:
            raise SourceExtractionError("Architect template contains missing/unknown fields")
        if template.get("startAttackers") not in {"None", "Player", "Architect", "Both"} or template.get("endAttackers") not in {"None", "Player", "Architect", "Both"}:
            raise SourceExtractionError("Architect attacker enum variant is unknown")
        lines = template.get("lines")
        if not isinstance(lines, list) or len(lines) != template.get("lineCount"):
            raise SourceExtractionError("Architect template line census/order mismatch")
        if [row.get("index") for row in lines] != list(range(len(lines))):
            raise SourceExtractionError("Architect line index order is malformed")
        for line in lines:
            has_next = "nextButtonLocalization" in line
            expected_line_fields = {"index", "lineId", "lineLocalization", "speaker"} | ({"nextButtonLocalization"} if has_next else set())
            if set(line) != expected_line_fields:
                raise SourceExtractionError("Architect line contains missing/unknown fields or copied prose")
            line_id = line.get("lineId")
            if not isinstance(line_id, str) or line_id in line_ids or line.get("speaker") not in {"Ancient", "Character"}:
                raise SourceExtractionError("Architect line identity/speaker mapping is malformed")
            line_ids.add(line_id)
            loc = line.get("lineLocalization")
            if not isinstance(loc, Mapping) or set(loc) != {"key", "keyValueWitnessSha256", "valueSha256"}:
                raise SourceExtractionError("Architect line localization provenance is malformed")
            selected_line_localizations.append(dict(loc))
            if has_next:
                next_loc = line["nextButtonLocalization"]
                if not isinstance(next_loc, Mapping) or set(next_loc) != {"key", "keyValueWitnessSha256", "valueSha256"}:
                    raise SourceExtractionError("Architect continuation localization provenance is malformed")
                selected_line_localizations.append(dict(next_loc))
            if has_next != (line["index"] < len(lines) - 1):
                raise SourceExtractionError("Architect continuation key/order mismatch")
    localization = value["localization"]
    expected_localization_fields = {"controlKeys", "keyValueWitnesses", "lineKeyCount", "nextButtonKeyCount",
                                    "proseEmitted", "provenance", "selectedKeyCount", "semanticWitnessSha256", "table"}
    if set(localization) != expected_localization_fields:
        raise SourceExtractionError("Architect localization contains missing/unknown fields or copied prose")
    if localization.get("proseEmitted") is not False or localization.get("table") != "ancients":
        raise SourceExtractionError("Architect localization prose boundary is not explicit")
    witnesses = localization.get("keyValueWitnesses")
    if not isinstance(witnesses, list) or len(witnesses) != localization.get("selectedKeyCount"):
        raise SourceExtractionError("Architect localization key denominator mismatch")
    for row in witnesses:
        if not isinstance(row, Mapping) or set(row) != {"key", "keyValueWitnessSha256", "valueSha256"} or any(
                not isinstance(row.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", row[key])
                for key in ("keyValueWitnessSha256", "valueSha256")):
            raise SourceExtractionError("Architect localization key/value digest is malformed")
    keys = [row.get("key") for row in witnesses]
    controls = localization.get("controlKeys")
    if not isinstance(controls, list) or any(not isinstance(row, Mapping) or set(row) != {"key", "keyValueWitnessSha256", "valueSha256"} for row in controls):
        raise SourceExtractionError("Architect localization control-key closure is malformed")
    expected_selected = selected_line_localizations + [dict(row) for row in controls]
    by_key = {row["key"]: dict(row) for row in witnesses}
    if (None in keys or len(keys) != len(set(keys)) or localization.get("semanticWitnessSha256") != witness_sha256(witnesses)
            or {row["key"] for row in expected_selected} != set(keys)
            or any(by_key.get(row["key"]) != row for row in expected_selected)):
        raise SourceExtractionError("Architect localization refs/digests are invalid")
    provenance = localization.get("provenance")
    expected_provenance_fields = {"entryFlags", "entryMd5", "entrySha256", "pckDirectoryOffset", "pckFileCount",
                                  "pckFormat", "pckGodotVersion", "pckPath", "pckSha256"}
    if not isinstance(provenance, Mapping) or set(provenance) != expected_provenance_fields:
        raise SourceExtractionError("Architect selected localization entry provenance is malformed")
    options = value["initialState"].get("options")
    if not isinstance(options, list) or len(options) != 2:
        raise SourceExtractionError("Architect option/delegate closure is incomplete")
    if {row.get("callback", {}).get("target") for row in options} != {
        _OWNER + "::AdvanceDialogue sig:2000128121", _OWNER + "::WinRun sig:2000128121",
    } or any(row.get("callback", {}).get("receiver") != "eventInstance" for row in options):
        raise SourceExtractionError("Architect delegate receiver/target/signature closure changed")
    nodes = value["lineControl"].get("nodes"); edges = value["lineControl"].get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) != len(line_ids) or len(edges) != len(line_ids):
        raise SourceExtractionError("Architect line node/edge graph census mismatch")
    if {row.get("nodeId") for row in nodes} != line_ids or {row.get("from") for row in edges} != line_ids:
        raise SourceExtractionError("Architect line graph refs are dangling")
    for edge in edges:
        if edge.get("kind") == "continuation" and edge.get("to") not in line_ids:
            raise SourceExtractionError("Architect continuation edge target is dangling")
        if edge.get("kind") == "terminalProceed" and edge.get("to") != "ARCHITECT_NODE.TERMINAL_PROCEED":
            raise SourceExtractionError("Architect terminal-proceed edge target changed")
        if edge.get("kind") not in {"continuation", "terminalProceed"}:
            raise SourceExtractionError("Architect line graph has an unknown edge kind")
    if value["visualOnlyCombat"].get("classification") != "notActiveCombat" or value["visualOnlyCombat"].get("roomMode") != "VisualOnly":
        raise SourceExtractionError("Architect visual-only mode was classified as active combat")
    presentation = value["presentation"]
    if presentation.get("completeSliceHasGameplayDamage") is not False or presentation.get("apparentDamageClassification") != "damageNumberVfxNotHpDamage" or presentation.get("scoreSplit", {}).get("renderDeterministically") is not False:
        raise SourceExtractionError("Architect presentation/gameplay boundary is invalid")
    terminal = value["terminal"]
    if terminal.get("orderedControl") != ["animatePlayerEndAttackers", "animateArchitectEndAttackers",
                                           "localOwnerRunManagerWinRun", "awaitWinRun", "setEmptyOptionsFinishedState"]:
        raise SourceExtractionError("Architect WinRun was reordered before terminal animations")
    if terminal.get("localOwnerGuarded") is not True or terminal.get("eventCombatTransition") is not False or terminal.get("noResume") is not True or terminal.get("noRewardPage") is not True:
        raise SourceExtractionError("Architect terminal incorrectly claims active combat/reward/resume")
    if terminal.get("cleanupBoundary") != {"classification": "commonEventFrameworkIfExitReached", "frameworkRole": "EnsureCleanup"}:
        raise SourceExtractionError("Architect common cleanup boundary changed")
    boundary = terminal.get("runManagerBoundary", {})
    if boundary.get("onEndedArgument") is not True or boundary.get("order") != ["OnEnded(true)", "GuaranteeKillAllPlayers"]:
        raise SourceExtractionError("Architect OnEnded/forced-kill lifecycle dependency changed")
    dependencies = value["dependencies"]
    expected_dependencies = {
        "FORMULA.SCORE_UTILITY.CALCULATE_SCORE", "LIFECYCLE.RUN.ON_ENDED_TRUE",
        "LIFECYCLE.RUN.GUARANTEE_KILL_ALL_PLAYERS", "LIFECYCLE.RUN.SERIALIZED_SCORE_STATS_HISTORY",
        "LIFECYCLE.RUN.ARCHITECT_TERMINAL_ORDER",
    }
    if not isinstance(dependencies, list) or {row.get("dependencyId") for row in dependencies} != expected_dependencies:
        raise SourceExtractionError("Architect score/formula or lifecycle dependency refs are incomplete")
    census = value["invocationCensus"]
    decisions = census.get("decisions", [])
    summary = census.get("summary", {})
    if summary.get("unresolved") != 0 or summary.get("resolved") != summary.get("denominator") or summary.get("denominator") != len(decisions):
        raise SourceExtractionError("Architect transitive invocation census is unresolved/stale")
    allowed_classifications = {"normalizedControlOrDependency", "presentationOnly", "traversedExactHelper",
                               "normalizedOptionFramework", "localizationOrDialogueControl", "typedRuntimeRng",
                               "sourceProvenFrameworkOrRuntimePlumbing"}
    residual_symbols = set()
    for index, decision in enumerate(decisions):
        if not isinstance(decision, Mapping) or set(decision) != {"classification", "instructionIndex", "sourceMethod", "symbolSignature"}:
            raise SourceExtractionError(f"Architect invocation decision {index} is malformed")
        classification = decision["classification"]; symbol = decision["symbolSignature"]; base = _base(symbol)
        if classification not in allowed_classifications:
            raise SourceExtractionError(f"Architect invocation decision {index} is unclassified")
        if (base.startswith("MegaCrit.Sts2.Core.Commands.DamageCmd::")
                or base in {"MegaCrit.Sts2.Core.Commands.CreatureCmd::Damage",
                            "MegaCrit.Sts2.Core.Commands.CreatureCmd::Attack"}):
            raise SourceExtractionError("gameplay damage/attack was hidden in Architect presentation")
        if base == "MegaCrit.Sts2.Core.Models.EventModel::EnterCombatWithoutExitingEvent":
            raise SourceExtractionError("active event-combat transition entered Architect invocation census")
        if base.startswith("MegaCrit.Sts2.Core.Rewards.") or base.startswith("MegaCrit.Sts2.Core.Commands.RewardsCmd::"):
            raise SourceExtractionError("reward construction/dispatch entered Architect invocation census")
        if base.startswith("MegaCrit.Sts2.Core.Commands.") and base not in _PRESENTATION_COMMANDS:
            raise SourceExtractionError(f"unclassified Architect command in invocation census: {symbol}")
        if (".Nodes.Vfx." in base or ".Commands.VfxCmd::" in base) and base not in _PRESENTATION_SINKS:
            raise SourceExtractionError(f"unclassified Architect VFX in invocation census: {symbol}")
        if classification == "sourceProvenFrameworkOrRuntimePlumbing":
            residual_symbols.add(symbol)
    residual = sorted(residual_symbols); residual_digest = witness_sha256(residual)
    if census.get("residualVocabulary") != {"sha256": residual_digest, "size": len(residual)}:
        raise SourceExtractionError("Architect invocation residual vocabulary digest is stale")
    if len(residual) != _RESIDUAL_VOCABULARY_SIZE or residual_digest != _RESIDUAL_VOCABULARY_SHA256:
        raise SourceExtractionError("Architect invocation residual vocabulary changed")
    runtime_contracts = value["runtimeContracts"]
    semantic_effects = value["semanticEffects"]
    if not isinstance(runtime_contracts, list) or len({row.get("name") for row in runtime_contracts}) != len(runtime_contracts):
        raise SourceExtractionError("Architect state/runtime input contracts are duplicate or malformed")
    if not isinstance(semantic_effects, list) or len({row.get("effectId") for row in semantic_effects}) != len(semantic_effects):
        raise SourceExtractionError("Architect semantic effects are duplicate or malformed")
    den = value["sourceDenominators"]
    expected_den = {"dependencies": len(dependencies), "edges": len(edges),
                    "invocations": len(census["decisions"]), "localizationKeys": len(witnesses),
                    "methods": len(value["methods"]), "nodes": len(nodes), "options": len(options),
                    "presentationMethods": len(presentation["sliceMethodSymbols"]),
                    "runtimeContracts": len(runtime_contracts), "semanticEffects": len(semantic_effects),
                    "templates": len(templates), "lines": len(line_ids)}
    if den != expected_den:
        raise SourceExtractionError("Architect source denominator accounting mismatch")
