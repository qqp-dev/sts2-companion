"""Consolidated E2 lifecycle closeout derived from pinned CLI metadata/CIL.

This module extends :mod:`lifecycle`'s core dispatch authority.  It discovers
reachable effective listeners and their transitive model closure; it does not
implement a second kill, removal, Add, HP, or event evaluator.  Normalized
records below join those already-validated component contracts by stable refs.
The shipped assembly is read as metadata/CIL only and is never loaded.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import deepcopy
import re
from typing import Any, Iterable, Mapping, Sequence

from .behavior import _async_map
from .canonical import slugify_ascii_type_name, witness_sha256
from .cil_eval import CilDataFlow
from .errors import SourceExtractionError

_ABSTRACT = "MegaCrit.Sts2.Core.Models.AbstractModel"
_MONSTER = "MegaCrit.Sts2.Core.Models.MonsterModel"
_POWER = "MegaCrit.Sts2.Core.Models.PowerModel"
_MONSTER_NS = "MegaCrit.Sts2.Core.Models.Monsters."
_POWER_NS = "MegaCrit.Sts2.Core.Models.Powers."
_HOOK = "MegaCrit.Sts2.Core.Hooks.Hook"
_RUN_MANAGER = "MegaCrit.Sts2.Core.Runs.RunManager"

# Logical signatures are discovered from the bases, then asserted here as a
# pinned-version recognizer.  Overload names alone are never identities.
_SHARED_HOOKS = {
    "BeforeDeath": "200112812112a7e4",
    "AfterDeath": "200412812112a64c12a7e4020c",
    "ShouldCreatureBeRemovedFromCombatAfterDeath": "20010212a7e4",
    "ShouldStopCombatFromEnding": "200002",
    "ShouldPowerBeRemovedOnDeath": "2001021288f4",
    "ShouldDie": "20010212a7e4",
    "ShouldDieLate": "20010212a7e4",
    "AfterPreventingDeath": "200112812112a7e4",
    "AfterDiedToDoom": "200212812112a64c151281fd0112a7e4",
}
_POWER_HOOKS = {
    "ShouldPowerBeRemovedAfterOwnerDeath": "200002",
    "ShouldOwnerDeathTriggerFatal": "200002",
}
_MONSTER_HOOKS = {"BeforeRemovedFromRoom": "200001"}

_PROOF_KEYS = (
    "assemblySha256", "cilInstructionsSha256", "diagnosticMetadataToken",
    "metadataSignature", "methodBodySha256", "normalizedInstructionsSha256",
    "symbolSignature",
)


def _proof(record: Mapping[str, Any], *, semantic: Any | None = None,
           origins: Iterable[int] | None = None) -> dict[str, Any]:
    result = {key: record[key] for key in _PROOF_KEYS}
    indexes = sorted(set(range(len(record["instructions"]))) if origins is None else {
        index for index in origins if 0 <= index < len(record["instructions"])
    })
    if not indexes:
        raise SourceExtractionError(f"empty lifecycle-closeout CIL slice: {record['symbolSignature']}")
    normalized = [{"opcode": record["instructions"][index]["opcode"],
                   "operand": record["instructions"][index].get("operand")} for index in indexes]
    result["instructionOrigins"] = indexes
    result["normalizedSliceSha256"] = witness_sha256(normalized)
    if semantic is not None:
        result["semanticWitnessSha256"] = witness_sha256(semantic)
    return result


def _canonical_type(source_type: str) -> str:
    name = source_type.rsplit(".", 1)[-1]
    if source_type.startswith(_POWER_NS) and name.endswith("Power"):
        return "POWER." + slugify_ascii_type_name(name)
    if source_type.startswith(_MONSTER_NS):
        return "MONSTER." + slugify_ascii_type_name(name)
    raise SourceExtractionError(f"lifecycle model type is outside exact model namespaces: {source_type}")


def _all_model_refs(value: Any) -> set[str]:
    result: set[str] = set()
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            if item.startswith(("POWER.", "MONSTER.")):
                result.add(item)
        elif isinstance(item, Mapping):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
    return result


def _method_by_signature(assembly: Any, owner: str, name: str,
                         signature: str) -> int | None:
    rows = [index for index in assembly.find_methods(owner, name)
            if assembly.md.MethodDef.rows[index - 1].Signature.value.hex() == signature]
    if len(rows) > 1:
        raise SourceExtractionError(
            f"ambiguous lifecycle effective declaration {owner}::{name} sig:{signature}"
        )
    return rows[0] if rows else None


def _effective_method(assembly: Any, source_type: str, name: str,
                      signature: str) -> tuple[int, str, list[str]]:
    current = source_type
    path: list[str] = []
    seen: set[str] = set()
    while current and current not in seen:
        path.append(current); seen.add(current)
        index = _method_by_signature(assembly, current, name, signature)
        if index is not None:
            return index, current, path
        current = assembly.base_by_type.get(current, "")
    raise SourceExtractionError(
        f"missing inherited lifecycle declaration {source_type}::{name} sig:{signature}"
    )


def _physical_index(index: int, async_methods: Mapping[int, int]) -> int:
    return async_methods.get(index, index)


def _model_types_in_record(record: Mapping[str, Any], known_types: set[str]) -> set[str]:
    found: set[str] = set()
    for instruction in record["instructions"]:
        operand = instruction.get("operand")
        if not isinstance(operand, str):
            continue
        for source_type in re.findall(
            r"MegaCrit\.Sts2\.Core\.Models\.(?:Powers|Monsters)\.[A-Za-z][A-Za-z0-9]*", operand
        ):
            if source_type in known_types:
                found.add(source_type)
    return found


def _discover_doom_roots(assembly: Any, assembly_sha256: str,
                         power_types: set[str], async_methods: Mapping[int, int]) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    methods_by_owner: dict[str, list[tuple[int, Any]]] = defaultdict(list)
    for index, row in enumerate(assembly.md.MethodDef.rows, 1):
        owner = assembly.type_names.get(assembly.method_owner.get(index))
        if owner in power_types and str(row.Name) == "DoomKill":
            methods_by_owner[owner].append((index, row))
    for source_type in sorted(power_types):
        for index, row in methods_by_owner[source_type]:
            if getattr(row.Flags, "mdAbstract", False):
                continue
            physical = assembly.method_record(_physical_index(index, async_methods), assembly_sha256)
            calls = [item["operand"] for item in physical["instructions"]
                     if item["opcode"] in {"call", "callvirt"} and isinstance(item.get("operand"), str)]
            kill_sites = [symbol for symbol in calls if
                          symbol.startswith("MegaCrit.Sts2.Core.Commands.CreatureCmd::Kill sig:")]
            doom_sites = [symbol for symbol in calls if
                          symbol.startswith(f"{_HOOK}::AfterDiedToDoom sig:")]
            if kill_sites or doom_sites:
                if len(kill_sites) == 1 and len(doom_sites) == 1:
                    logical = assembly.method_record(index, assembly_sha256)
                    roots.append({
                        "canonicalPower": _canonical_type(source_type),
                        "discoveryKind": "ordinaryKillThenPostBatchDoomDispatch",
                        "logicalMethod": _proof(logical),
                        "physicalBody": _proof(physical),
                        "sourceType": source_type,
                    })
                elif doom_sites:
                    raise SourceExtractionError(
                        f"Doom dispatcher root has unsupported kill/hook cardinality: {physical['symbolSignature']}"
                    )
    if len(roots) != 1:
        raise SourceExtractionError(f"Doom lifecycle root discovery drift: {len(roots)}")
    return roots


def _boolean_default(record: Mapping[str, Any]) -> bool | None:
    try:
        value = CilDataFlow(record["instructions"]).return_value(record["symbolSignature"])
    except SourceExtractionError:
        return None
    if value.kind == "constant" and type(value.data) is bool:
        return value.data
    return None


def _classify_effective_method(assembly: Any, assembly_sha256: str, index: int,
                               async_methods: Mapping[int, int],
                               exact_symbols: Mapping[str, int]) -> str:
    physical_index = _physical_index(index, async_methods)
    queue = deque([physical_index]); seen: set[int] = set(); gameplay = False; presentation = False
    gameplay_members = {
        "Add", "Apply", "Attack", "Damage", "Decrement", "Escape", "Heal", "Kill",
        "Remove", "SetMaxAndCurrentHp", "SetMaxHp", "SetMoveImmediate", "ForceCurrentState",
        "LoseGold", "GainGold", "MarkGoldStolen", "SetCreatureIsInteractable",
    }
    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current); record = assembly.method_record(current, assembly_sha256)
        for instruction in record["instructions"]:
            opcode = instruction["opcode"]; operand = instruction.get("operand")
            if opcode == "stfld" and isinstance(operand, str):
                if operand.startswith((_MONSTER_NS, _POWER_NS, "MegaCrit.Sts2.Core.Runs.ExtraRunFields::")) and "+<" not in operand:
                    gameplay = True
            if opcode not in {"call", "callvirt", "newobj"} or not isinstance(operand, str):
                continue
            owner_member = operand.split(" sig:", 1)[0]
            owner, _, member = owner_member.rpartition("::")
            if member in gameplay_members or owner.startswith("MegaCrit.Sts2.Core.MonsterMoves."):
                gameplay = True
            if owner.startswith(("MegaCrit.Sts2.Core.Nodes.", "Godot.")) or member in {
                "Play", "TriggerAnim", "SetNodeVisible", "UpdateMusicParameter", "FadeOut"
            }:
                presentation = True
            target = exact_symbols.get(operand.split(" generic:", 1)[0].split(" methodspec:", 1)[0])
            if target is not None and target not in seen and owner.startswith("MegaCrit.Sts2.Core."):
                target_row = assembly.md.MethodDef.rows[target - 1]
                if not getattr(target_row.Flags, "mdAbstract", False) and target_row.Rva:
                    queue.append(_physical_index(target, async_methods))
    if gameplay:
        return "gameplay"
    if presentation:
        return "exactPresentationOrAudioCleanup"
    logical = assembly.method_record(index, assembly_sha256)
    if len(logical["instructions"]) <= 2:
        return "sourceNoOpOrDefault"
    return "gameplayCleanup"


def _call_classification(assembly: Any, symbol: str,
                         exact_symbols: Mapping[str, int]) -> str:
    head = symbol.split(" generic:", 1)[0].split(" methodspec:", 1)[0]
    owner_member = head.split(" sig:", 1)[0]
    owner, sep, member = owner_member.rpartition("::")
    if not sep:
        raise SourceExtractionError(f"call-like lifecycle site lacks exact identity: {symbol}")
    gameplay = {
        "Add", "Apply", "Attack", "Damage", "Decrement", "Escape", "GainGold", "Heal", "Kill",
        "LoseGold", "MarkGoldStolen", "Remove", "SetMaxAndCurrentHp", "SetMaxHp",
        "SetMoveImmediate", "ForceCurrentState", "set_CurrentHp", "set_MaxHp",
    }
    if member in gameplay or owner.startswith("MegaCrit.Sts2.Core.MonsterMoves."):
        return "normalized"
    if owner.startswith(("MegaCrit.Sts2.Core.Nodes.", "Godot.")) or member in {
        "Play", "TriggerAnim", "SetNodeVisible", "UpdateMusicParameter", "FadeOut"
    }:
        return "presentationOnlyAtExactSite"
    if owner.startswith(("MegaCrit.Sts2.Core.Platform.", "MegaCrit.Sts2.Core.Mods.")):
        return "externalRuntimeBoundary"
    if owner.startswith("System.") or owner.startswith("<TypeSpec:"):
        return "frameworkPlumbingAtExactSite"
    if member.startswith(("get_", "set_", ".ctor")):
        return ("normalized" if member.startswith("set_") and owner.startswith(
            ("MegaCrit.Sts2.Core.Models.Monsters.", "MegaCrit.Sts2.Core.Models.Powers.",
             "MegaCrit.Sts2.Core.Runs.ExtraRunFields")) else "frameworkPlumbingAtExactSite")
    if owner.startswith(("MegaCrit.Sts2.Core.Commands.", "MegaCrit.Sts2.Core.Helpers.",
                         "MegaCrit.Sts2.Core.Hooks.")):
        return "frameworkPlumbingAtExactSite"
    # A resolvable local game method is traversed rather than semantically
    # ignored.  Exact symbol matching prevents a prefix-wide no-op rule.
    local = head in exact_symbols
    if local and owner.startswith("MegaCrit.Sts2.Core.Models."):
        return "recursivelyTraversed"
    if local and owner.startswith("MegaCrit.Sts2.Core."):
        return "frameworkPlumbingAtExactSite"
    return "unresolved"


def _invocation_decisions(assembly: Any, assembly_sha256: str,
                          physical_indexes: Iterable[int]) -> list[dict[str, Any]]:
    queue = deque(sorted(set(physical_indexes))); visited: set[int] = set(); rows: list[dict[str, Any]] = []
    symbols = {assembly.method_symbol(i): i for i in range(1, len(assembly.md.MethodDef.rows) + 1)}
    while queue:
        index = queue.popleft()
        if index in visited:
            continue
        visited.add(index); record = assembly.method_record(index, assembly_sha256)
        for instruction_index, instruction in enumerate(record["instructions"]):
            if instruction["opcode"] not in {"call", "callvirt", "newobj"}:
                continue
            callee = instruction.get("operand")
            if not isinstance(callee, str):
                raise SourceExtractionError(f"non-symbol call-like lifecycle site in {record['symbolSignature']}")
            classification = _call_classification(assembly, callee, symbols)
            semantic = {"callee": callee, "caller": record["symbolSignature"],
                        "classification": classification, "instructionIndex": instruction_index}
            rows.append({
                **semantic,
                "opcode": instruction["opcode"],
                "provenance": _proof(record, semantic=semantic, origins={instruction_index}),
            })
            if classification == "recursivelyTraversed":
                head = callee.split(" generic:", 1)[0].split(" methodspec:", 1)[0]
                target = symbols.get(head)
                if target is not None and assembly.md.MethodDef.rows[target - 1].Rva:
                    queue.append(target)
    rows.sort(key=lambda row: (row["caller"], row["instructionIndex"], row["callee"]))
    for ordinal, row in enumerate(rows):
        row["invocationId"] = f"LIFECYCLE.CLOSEOUT.INVOCATION.{ordinal:05d}"
    if any(row["classification"] in {"ignored", "unresolved"} for row in rows):
        bad = next(row for row in rows if row["classification"] in {"ignored", "unresolved"})
        raise SourceExtractionError(
            f"unresolved lifecycle closeout call-like site: {bad['caller']}:{bad['instructionIndex']} {bad['callee']}"
        )
    return rows


def extract_listener_closure(assembly: Any, assembly_sha256: str, *,
                             monsters: Sequence[Mapping[str, Any]],
                             reachable_models: set[str],
                             prior_components: Sequence[Any]) -> dict[str, Any]:
    async_methods = _async_map(assembly)
    exact_symbols = {assembly.method_symbol(i): i for i in range(1, len(assembly.md.MethodDef.rows) + 1)}
    declaration_indexes: dict[tuple[str, str, str], int] = {}
    relevant_hooks = set(_SHARED_HOOKS) | set(_POWER_HOOKS) | set(_MONSTER_HOOKS)
    for method_index, method_row in enumerate(assembly.md.MethodDef.rows, 1):
        method_name = str(method_row.Name)
        if method_name not in relevant_hooks:
            continue
        method_owner = assembly.type_names.get(assembly.method_owner.get(method_index), "")
        key = (method_owner, method_name, method_row.Signature.value.hex())
        if key in declaration_indexes:
            raise SourceExtractionError(f"duplicate exact lifecycle declaration: {key}")
        declaration_indexes[key] = method_index
    effective_cache: dict[tuple[str, str, str], tuple[int, str, list[str]]] = {}
    def effective_for(source_type: str, name: str, signature: str) -> tuple[int, str, list[str]]:
        cache_key = (source_type, name, signature)
        if cache_key in effective_cache:
            return effective_cache[cache_key]
        current = source_type; path: list[str] = []; seen: set[str] = set()
        while current and current not in seen:
            path.append(current); seen.add(current)
            index = declaration_indexes.get((current, name, signature))
            if index is not None:
                result = (index, current, path)
                effective_cache[cache_key] = result
                return result
            current = assembly.base_by_type.get(current, "")
        raise SourceExtractionError(
            f"missing inherited lifecycle declaration {source_type}::{name} sig:{signature}"
        )
    monster_by_canonical = {
        (row["canonicalId"] if str(row["canonicalId"]).startswith("MONSTER.")
         else "MONSTER." + row["canonicalId"]): row["sourceType"] for row in monsters
    }
    if len(monster_by_canonical) != len(monsters):
        raise SourceExtractionError("duplicate lifecycle monster source/canonical identity")
    missing = reachable_models - set(monster_by_canonical)
    if missing:
        raise SourceExtractionError(f"lifecycle reachable models lack source types: {sorted(missing)}")
    monster_types = {monster_by_canonical[model] for model in reachable_models}
    if len(monster_types) != 108:
        raise SourceExtractionError(f"lifecycle owner denominator drift: {len(monster_types)}")

    all_power_types = {source_type for source_type in assembly.type_names.values()
                       if source_type.startswith(_POWER_NS) and assembly.derives_from(source_type, _POWER)}
    power_by_canonical = {_canonical_type(source_type): source_type for source_type in all_power_types}
    if len(power_by_canonical) != len(all_power_types):
        raise SourceExtractionError("duplicate canonical Power type in lifecycle discovery")
    prior_refs: set[str] = set()
    for component in prior_components:
        prior_refs.update(_all_model_refs(component))
    unknown_prior_powers = sorted(ref for ref in prior_refs if ref.startswith("POWER.") and ref not in power_by_canonical)
    if unknown_prior_powers:
        raise SourceExtractionError(f"prior lifecycle Power refs lack source types: {unknown_prior_powers}")
    seed_types = {power_by_canonical[ref] for ref in prior_refs if ref in power_by_canonical}
    if len(seed_types) != 69:
        raise SourceExtractionError(f"lifecycle prior Power seed denominator drift: {len(seed_types)}")

    doom_roots = _discover_doom_roots(assembly, assembly_sha256, all_power_types, async_methods)
    power_types = set(seed_types) | {row["sourceType"] for row in doom_roots}
    type_index_by_name = {name: index for index, name in assembly.type_names.items()}
    concrete_monster_types = {
        source_type for source_type in assembly.type_names.values()
        if source_type.startswith(_MONSTER_NS) and assembly.derives_from(source_type, _MONSTER)
        and not getattr(assembly.md.TypeDef.rows[type_index_by_name[source_type] - 1].Flags, "tdAbstract", False)
    }
    known_types = all_power_types | concrete_monster_types
    iterations: list[dict[str, Any]] = []
    record_cache: dict[int, dict[str, Any]] = {}
    model_ref_cache: dict[int, set[str]] = {}
    def record_for(index: int) -> dict[str, Any]:
        if index not in record_cache:
            record_cache[index] = assembly.method_record(index, assembly_sha256)
        return record_cache[index]
    def model_refs_for(index: int) -> set[str]:
        if index not in model_ref_cache:
            model_ref_cache[index] = _model_types_in_record(record_for(index), known_types)
        return model_ref_cache[index]
    while True:
        before_powers = set(power_types); before_monsters = set(monster_types)
        scan_types = sorted(power_types | monster_types)
        for source_type in scan_types:
            hook_specs = dict(_SHARED_HOOKS)
            hook_specs.update(_POWER_HOOKS if source_type in power_types else _MONSTER_HOOKS)
            for name, signature in hook_specs.items():
                index, _, _ = effective_for(source_type, name, signature)
                physical_i = _physical_index(index, async_methods)
                for discovered in model_refs_for(physical_i):
                    if discovered in all_power_types:
                        power_types.add(discovered)
                    elif assembly.derives_from(discovered, _MONSTER):
                        monster_types.add(discovered)
        additions_p = sorted(power_types - before_powers); additions_m = sorted(monster_types - before_monsters)
        iterations.append({
            "iteration": len(iterations),
            "addedMonsters": [_canonical_type(t) for t in additions_m],
            "addedPowers": [_canonical_type(t) for t in additions_p],
            "monsterCount": len(monster_types), "powerCount": len(power_types),
        })
        if not additions_p and not additions_m:
            break
        if len(iterations) > len(known_types):
            raise SourceExtractionError("lifecycle model fixed point failed to converge")
    if len(power_types) != 71 or len(monster_types) != 108:
        raise SourceExtractionError(
            f"lifecycle fixed-point denominator drift: monsters={len(monster_types)} powers={len(power_types)} iterations={iterations!r}"
        )
    if {_canonical_type(t) for t in power_types - seed_types} != {"POWER.DOOM_POWER", "POWER.HEIST_POWER"}:
        raise SourceExtractionError("lifecycle fixed point additions changed")

    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    classification_cache: dict[int, str] = {}
    def classification_for(index: int) -> str:
        if index not in classification_cache:
            classification_cache[index] = _classify_effective_method(
                assembly, assembly_sha256, index, async_methods, exact_symbols
            )
        return classification_cache[index]
    effective_applications = 0; declaration_owners: dict[str, set[str]] = defaultdict(set)
    physical_indexes: set[int] = set()
    for domain, source_types, extra_hooks in (
        ("monster", monster_types, _MONSTER_HOOKS),
        ("power", power_types, _POWER_HOOKS),
    ):
        specs = dict(_SHARED_HOOKS); specs.update(extra_hooks)
        for source_type in sorted(source_types):
            canonical = _canonical_type(source_type)
            for name, signature in specs.items():
                index, declaration_owner, path = effective_for(source_type, name, signature)
                logical = record_for(index)
                physical_i = _physical_index(index, async_methods)
                physical = record_for(physical_i); physical_indexes.add(physical_i)
                effective_applications += 1; declaration_owners[f"{domain}.{name}"].add(declaration_owner)
                key = (domain, name, signature, logical["symbolSignature"])
                row = groups.setdefault(key, {
                    "applicableOwners": [],
                    "classification": classification_for(index),
                    "declarationKind": "inheritedDefault" if declaration_owner in {_ABSTRACT, _MONSTER, _POWER} else "effectiveOverride",
                    "declarationOwnerSourceType": declaration_owner,
                    "hook": name,
                    "listenerDomain": domain,
                    "logicalMethod": _proof(logical),
                    "physicalBody": _proof(physical),
                    "returnDefault": _boolean_default(logical),
                    "signature": signature,
                })
                row["applicableOwners"].append({
                    "canonicalModel": canonical,
                    "concreteSourceType": source_type,
                    "inheritancePath": path,
                })
    implementations = []
    for ordinal, key in enumerate(sorted(groups)):
        row = groups[key]; row["applicableOwners"].sort(key=lambda item: item["canonicalModel"])
        row["implementationId"] = f"LIFECYCLE.LISTENER.{row['listenerDomain'].upper()}.{row['hook'].upper()}.{ordinal:03d}"
        row["applicabilitySha256"] = witness_sha256(row["applicableOwners"])
        implementations.append(row)

    # Post-discovery assertions: these never seed the owner sets.
    def nondefault(domain: str, hook: str) -> list[dict[str, Any]]:
        return [row for row in implementations if row["listenerDomain"] == domain and row["hook"] == hook
                and row["declarationKind"] == "effectiveOverride"]
    assertions = {
        "monsterBeforeDeathDeclarations": len(nondefault("monster", "BeforeDeath")),
        "monsterAfterDeathDeclarationOwners": len(nondefault("monster", "AfterDeath")),
        "monsterAfterDeathEffectiveModels": sum(len(row["applicableOwners"]) for row in nondefault("monster", "AfterDeath")),
        "monsterBeforeRemovedDeclarations": len(nondefault("monster", "BeforeRemovedFromRoom")),
        "powerBeforeDeathBaselineDeclarations": sum(
            row["declarationKind"] == "effectiveOverride" for row in implementations
            if row["listenerDomain"] == "power" and row["hook"] == "BeforeDeath"
            and all(owner["canonicalModel"] != "POWER.HEIST_POWER" for owner in row["applicableOwners"])
        ),
        "powerBeforeDeathFixedPointDeclarations": len(nondefault("power", "BeforeDeath")),
        "powerAfterDeathBaselineDeclarations": sum(
            1 for row in nondefault("power", "AfterDeath")
            if all(owner["canonicalModel"] not in {"POWER.DOOM_POWER", "POWER.HEIST_POWER"} for owner in row["applicableOwners"])
        ),
        "powerRemovePredicateDeclarations": len(nondefault("power", "ShouldCreatureBeRemovedFromCombatAfterDeath")),
        "powerStopEndingDeclarations": len(nondefault("power", "ShouldStopCombatFromEnding")),
        "powerRemovedOnDeathDeclarations": len(nondefault("power", "ShouldPowerBeRemovedOnDeath")),
        "powerOwnerRetentionDeclarations": len(nondefault("power", "ShouldPowerBeRemovedAfterOwnerDeath")),
        "powerOwnerFatalDeclarations": len(nondefault("power", "ShouldOwnerDeathTriggerFatal")),
        "reachableShouldDieFamilyOverrides": sum(len(nondefault(domain, hook)) for domain in ("monster", "power")
                                                   for hook in ("ShouldDie", "ShouldDieLate", "AfterPreventingDeath", "AfterDiedToDoom")),
    }
    expected = {
        "monsterBeforeDeathDeclarations": 2, "monsterAfterDeathDeclarationOwners": 10,
        "monsterAfterDeathEffectiveModels": 12, "monsterBeforeRemovedDeclarations": 11,
        "powerBeforeDeathBaselineDeclarations": 1, "powerBeforeDeathFixedPointDeclarations": 2,
        "powerAfterDeathBaselineDeclarations": 16, "powerRemovePredicateDeclarations": 5,
        "powerStopEndingDeclarations": 5, "powerRemovedOnDeathDeclarations": 1,
        "powerOwnerRetentionDeclarations": 5, "powerOwnerFatalDeclarations": 2,
        "reachableShouldDieFamilyOverrides": 0,
    }
    if assertions != expected:
        raise SourceExtractionError(f"reachable listener post-discovery assertion drift: {assertions}")

    invocations = _invocation_decisions(assembly, assembly_sha256, physical_indexes)
    return {
        "discovery": {
            "doomRoots": doom_roots,
            "fixedPointIterations": iterations,
            "powerSeedCanonicalIds": sorted(_canonical_type(t) for t in seed_types),
            "powerSeedKind": "canonical refs discovered across prior source components",
            "transitiveRule": "scan every effective listener physical body for exact Power/Monster model type refs until no additions",
        },
        "listenerCensus": {
            "effectiveApplications": effective_applications,
            "fixedPointPowerTypes": len(power_types),
            "implementationRecords": len(implementations),
            "monsterOwnerTypes": len(monster_types),
            "postDiscoveryAssertions": assertions,
            "powerSeedTypes": len(seed_types),
        },
        "listenerImplementations": implementations,
        "invocationDecisions": invocations,
        "physicalRootIndexes": sorted(physical_indexes),
    }


def _runtime(name: str, value_type: str) -> dict[str, Any]:
    return {"kind": "runtimeInput", "name": name, "valueType": value_type}


def _constant(value: Any, value_type: str | None = None) -> dict[str, Any]:
    if value_type is None:
        value_type = "boolean" if type(value) is bool else "integer" if type(value) is int else "string"
    return {"kind": "constant", "value": value, "valueType": value_type}


def _equal(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "comparison", "left": left, "operator": "equal", "right": right,
            "valueType": "boolean"}


def _all(*operands: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "allOf", "operands": list(operands), "valueType": "boolean"}


def _effect(order: int, kind: str, *, execution: str = "synchronous",
            owner: str, target: str, **fields: Any) -> dict[str, Any]:
    return {"execution": execution, "kind": kind, "order": order,
            "owner": owner, "target": target, **fields}


class _Methods:
    def __init__(self, assembly: Any, assembly_sha256: str):
        self.assembly = assembly; self.sha = assembly_sha256
        self.async_methods = _async_map(assembly)
        self.rows: dict[tuple[str, str, str], int] = {}
        self.symbols: dict[str, int] = {}
        for index, row in enumerate(assembly.md.MethodDef.rows, 1):
            owner = assembly.type_names.get(assembly.method_owner.get(index), "")
            name = str(row.Name); signature = row.Signature.value.hex()
            key = (owner, name, signature)
            if key in self.rows:
                raise SourceExtractionError(f"duplicate semantic lifecycle method identity: {key}")
            self.rows[key] = index; self.symbols[assembly.method_symbol(index)] = index

    def one(self, owner: str, name: str, signature: str | None = None) -> tuple[int, dict[str, Any], dict[str, Any]]:
        candidates = [(key, index) for key, index in self.rows.items()
                      if key[0] == owner and key[1] == name and (signature is None or key[2] == signature)]
        if len(candidates) != 1:
            raise SourceExtractionError(
                f"semantic lifecycle method is not unique: {owner}::{name} sig:{signature} ({len(candidates)})"
            )
        index = candidates[0][1]; logical = self.assembly.method_record(index, self.sha)
        physical = self.assembly.method_record(self.async_methods.get(index, index), self.sha)
        return index, logical, physical

    def evidence(self, owner: str, name: str, signature: str | None = None,
                 semantic: Any | None = None) -> dict[str, Any]:
        _, logical, physical = self.one(owner, name, signature)
        return {"logicalMethod": _proof(logical),
                "physicalBody": _proof(physical, semantic=semantic)}


def _phase_systems(methods: _Methods) -> list[dict[str, Any]]:
    actual_death = _all(
        _equal(_runtime("death.wasRemovalPrevented", "boolean"), _constant(False)),
        _equal(_runtime("death.targetIsPowerOwner", "boolean"), _constant(True)),
    )
    same_body = {"kind": "sameBody", "newBodyCreated": False, "slotChanged": False,
                 "positionChanged": False}
    test = {
        "bodyIdentity": same_body,
        "ownerModel": "MONSTER.TEST_SUBJECT",
        "phaseSystemId": "LIFECYCLE.PHASE.TEST_SUBJECT_ADAPTABLE",
        "sourceSignals": ["POWER.ADAPTABLE_POWER"],
        "provenance": [
            methods.evidence(_POWER_NS + "AdaptablePower", "AfterDeath"),
            methods.evidence(_MONSTER_NS + "TestSubject", "TriggerDeadState"),
            methods.evidence(_MONSTER_NS + "TestSubject", "RespawnMove"),
            methods.evidence(_MONSTER_NS + "TestSubject", "Revive"),
        ],
        "transitions": [
            {
                "condition": actual_death, "repeatability": "while Adaptable Power remains",
                "transitionId": "LIFECYCLE.TRANSITION.TEST_SUBJECT.ACTUAL_DEATH_TO_DEAD_STATE",
                "trigger": "fourArgumentAfterDeath",
                "orderedEffects": [
                    _effect(0, "writeState", owner="POWER.ADAPTABLE_POWER", target="sameOwnerBody",
                            field="AdaptablePower.Data.isReviving", value=True),
                    _effect(1, "awaitMethod", execution="awaited", owner="POWER.ADAPTABLE_POWER",
                            target="sameOwnerBody", method="TestSubject.TriggerDeadState"),
                    _effect(2, "incrementState", owner="MONSTER.TEST_SUBJECT", target="runState",
                            field="ExtraRunFields.TestSubjectKills", attribution="TriggerDeadState"),
                    _effect(3, "triggerAnimation", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", animation="DeadTrigger", attribution="TriggerDeadState"),
                    _effect(4, "forceMove", owner="MONSTER.TEST_SUBJECT", target="sameOwnerBody",
                            move="DeadState", transition=True, attribution="TriggerDeadState"),
                ],
            },
            {
                "condition": _equal(_runtime("monster.Respawns", "integer"), _constant(1)),
                "repeatability": "first completed revive", "trigger": "RespawnMove",
                "transitionId": "LIFECYCLE.TRANSITION.TEST_SUBJECT.REVIVE_FORM_1",
                "orderedEffects": [
                    _effect(0, "incrementState", owner="MONSTER.TEST_SUBJECT", target="sameOwnerBody",
                            field="Respawns", timing="beforeSwitch"),
                    _effect(1, "writeState", owner="POWER.ADAPTABLE_POWER", target="sameOwnerBody",
                            field="AdaptablePower.Data.isReviving", value=False),
                    _effect(2, "reviveHpByRef", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", baseHp={"belowA8": 200, "atOrAboveA8": 212},
                            hpPipelineRef="hpPipeline.assignment", orderWithinRef=["awaitSetMaxHp", "awaitHealScaledTrue"]),
                    _effect(3, "applyPowerByRef", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", power="POWER.PAINFUL_STABS_POWER",
                            initialStateRef="initialState.powerHookClosure"),
                ],
            },
            {
                "condition": _equal(_runtime("monster.Respawns", "integer"), _constant(2)),
                "repeatability": "second and final completed revive", "trigger": "RespawnMove",
                "transitionId": "LIFECYCLE.TRANSITION.TEST_SUBJECT.REVIVE_FORM_2",
                "orderedEffects": [
                    _effect(0, "incrementState", owner="MONSTER.TEST_SUBJECT", target="sameOwnerBody",
                            field="Respawns", timing="beforeSwitch"),
                    _effect(1, "writeState", owner="POWER.ADAPTABLE_POWER", target="sameOwnerBody",
                            field="AdaptablePower.Data.isReviving", value=False),
                    _effect(2, "reviveHpByRef", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", baseHp={"belowA8": 300, "atOrAboveA8": 313},
                            hpPipelineRef="hpPipeline.assignment", orderWithinRef=["awaitSetMaxHp", "awaitHealScaledTrue"]),
                    _effect(3, "applyPowerByRef", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", power="POWER.NEMESIS_POWER",
                            initialStateRef="initialState.powerHookClosure"),
                    _effect(4, "removePower", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", power="POWER.ADAPTABLE_POWER"),
                    _effect(5, "removePower", execution="awaited", owner="MONSTER.TEST_SUBJECT",
                            target="sameOwnerBody", power="POWER.PAINFUL_STABS_POWER"),
                ],
            },
            {
                "condition": _equal(_runtime("owner.hasAdaptablePower", "boolean"), _constant(False)),
                "repeatability": "terminal after two completed revives", "trigger": "subsequentActualDeath",
                "transitionId": "LIFECYCLE.TRANSITION.TEST_SUBJECT.FINAL_ORDINARY_DEATH",
                "orderedEffects": [_effect(0, "coreDeathByRef", execution="awaited",
                                                   owner="coreLifecycle", target="sameOwnerBody",
                                                   lifecycleRef="lifecycle.core.innerDeathGraph")],
            },
        ],
        "derivedCompletedReviveCount": 2,
        "capField": None,
        "stateReset": False,
    }
    egg = {
        "bodyIdentity": same_body, "ownerModel": "MONSTER.TOUGH_EGG",
        "phaseSystemId": "LIFECYCLE.PHASE.TOUGH_EGG_HATCH",
        "sourceSignals": ["DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH"],
        "provenance": [methods.evidence(_POWER_NS + "HatchPower", "AfterSideTurnEnd"),
                       methods.evidence(_MONSTER_NS + "ToughEgg", "HatchMove"),
                       methods.evidence(_MONSTER_NS + "ToughEgg", "Hatch"),
                       methods.evidence(_MONSTER_NS + "ToughEgg", "AfterAddedToRoom"),
                       methods.evidence(_MONSTER_NS + "ToughEgg", "get_Title")],
        "transitions": [
            {
                "condition": _equal(_runtime("sideTurn.participantsContainsOwner", "boolean"), _constant(True)),
                "repeatability": "each owner-participating side turn end", "trigger": "ownerSideTurnEnd",
                "transitionId": "LIFECYCLE.TRANSITION.TOUGH_EGG.HATCH_COUNTDOWN",
                "orderedEffects": [_effect(0, "decrementPower", execution="awaited", owner="POWER.HATCH_POWER",
                                                   target="sameOwnerBody", amount=1)],
            },
            {
                "condition": _equal(_runtime("monster.IsHatched", "boolean"), _constant(False)),
                "repeatability": "once", "trigger": "HatchMove",
                "transitionId": "LIFECYCLE.TRANSITION.TOUGH_EGG.NORMAL_HATCH",
                "orderedEffects": [
                    _effect(0, "writeState", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            field="IsHatched/_isHatched", value=True),
                    _effect(1, "removePower", execution="awaited", owner="MONSTER.TOUGH_EGG",
                            target="sameOwnerBody", power="POWER.HATCH_POWER"),
                    _effect(2, "writeState", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            field="_hatched", value=True, distinctFrom="IsHatched/_isHatched"),
                    _effect(3, "playSfx", owner="MONSTER.TOUGH_EGG", target="presentation"),
                    _effect(4, "snapshotPowers", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            filter="all except MinionPower"),
                    _effect(5, "removeSnapshottedPowers", execution="awaitedSequential", owner="MONSTER.TOUGH_EGG",
                            target="sameOwnerBody", retainedPower="POWER.MINION_POWER"),
                    _effect(6, "hatch", execution="awaited", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            hpInclusiveRange={"belowA8": [19, 22], "atOrAboveA8": [20, 23]},
                            hpPipelineRef="hpPipeline.assignment.setMaxAndCurrentHp"),
                ],
            },
            {
                "condition": _equal(_runtime("monster.IsHatched", "boolean"), _constant(True)),
                "repeatability": "on restored hatched body", "trigger": "AfterAddedToRoom",
                "transitionId": "LIFECYCLE.TRANSITION.TOUGH_EGG.RESTORED_HATCH",
                "orderedEffects": [
                    _effect(0, "skipPowerApplication", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            power="POWER.HATCH_POWER"),
                    _effect(1, "hatch", execution="awaited", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            rerunsPowerRemovalLoop=False),
                    _effect(2, "forceMove", owner="MONSTER.TOUGH_EGG", target="sameOwnerBody",
                            move="stored AfterHatchedState"),
                ],
            },
        ],
        "titleContract": {"getterField": "_hatched", "hatchWritesTitle": False,
                          "isHatchedField": "_isHatched"},
        "deathOrAdd": False,
    }
    deci = {
        "bodyIdentity": same_body, "ownerModels": [
            "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
            "MONSTER.DECIMILLIPEDE_SEGMENT_BACK"],
        "phaseSystemId": "LIFECYCLE.PHASE.DECIMILLIPEDE_REATTACH",
        "sourceSignals": ["POWER.REATTACH_POWER"],
        "provenance": [methods.evidence(_POWER_NS + "ReattachPower", "AfterDeath"),
                       methods.evidence(_POWER_NS + "ReattachPower", "DoReattach")],
        "initialStateRefs": ["initialState.setMaxAndCurrentHp.base25BeforeScaling",
                             "initialState.applyPower.POWER.REATTACH_POWER"],
        "transitions": [
            {
                "condition": _equal(_runtime("sameSide.anyOtherSegmentAlive", "boolean"), _constant(True)),
                "repeatability": "while another same-side segment lives", "trigger": "actualOwnerDeath",
                "transitionId": "LIFECYCLE.TRANSITION.DECIMILLIPEDE.DEAD_STATE",
                "orderedEffects": [
                    _effect(0, "writeState", owner="POWER.REATTACH_POWER", target="sameOwnerBody",
                            field="Data.isReviving", value=True),
                    _effect(1, "forceMove", owner="POWER.REATTACH_POWER", target="sameOwnerBody",
                            move="DeadState", transition=False),
                    _effect(2, "setInteraction", owner="POWER.REATTACH_POWER", target="sameOwnerBody", enabled=False),
                ],
            },
            {
                "condition": _equal(_runtime("sameSide.anyOtherSegmentAliveAtMove", "boolean"), _constant(True)),
                "repeatability": "reattach move recheck", "trigger": "DoReattach",
                "transitionId": "LIFECYCLE.TRANSITION.DECIMILLIPEDE.REATTACH",
                "orderedEffects": [
                    _effect(0, "playVfx", owner="POWER.REATTACH_POWER", target="sameOwnerBody"),
                    _effect(1, "writeState", owner="POWER.REATTACH_POWER", target="sameOwnerBody",
                            field="Data.isReviving", value=False),
                    _effect(2, "setInteraction", owner="POWER.REATTACH_POWER", target="sameOwnerBody", enabled=True),
                    _effect(3, "heal", execution="awaited", owner="POWER.REATTACH_POWER", target="sameOwnerBody",
                            amountRef="POWER.REATTACH_POWER.currentAmount", commandFlag=True),
                ],
            },
            {
                "condition": _all(_equal(_runtime("sameSide.allOtherSegmentsDead", "boolean"), _constant(True)),
                                  _equal(_runtime("owner.isDead", "boolean"), _constant(True))),
                "repeatability": "terminal", "trigger": "AfterDeath",
                "transitionId": "LIFECYCLE.TRANSITION.DECIMILLIPEDE.ALL_DEAD",
                "orderedEffects": [_effect(0, "presentationFade", execution="fireAndForgetSafe",
                                                   owner="POWER.REATTACH_POWER", target="allSegments",
                                                   gameplayEffect=False)],
            },
        ],
        "fatalPredicate": "true exactly when all other same-side segments are dead",
        "modelAfterDeathClassification": "exactPresentationTextureOnly",
        "addOrSlotChange": False,
    }
    illusion = {
        "bodyIdentity": same_body, "ownerModels": ["MONSTER.EYE_WITH_TEETH", "MONSTER.PARAFRIGHT"],
        "phaseSystemId": "LIFECYCLE.PHASE.ILLUSION_REVIVE",
        "sourceSignals": ["POWER.ILLUSION_POWER"],
        "provenance": [methods.evidence(_POWER_NS + "IllusionPower", "AfterDeath")],
        "transitions": [{
            "condition": actual_death, "repeatability": "while Illusion remains", "trigger": "fourArgumentAfterDeath",
            "transitionId": "LIFECYCLE.TRANSITION.ILLUSION.REVIVE_MOVE",
            "orderedEffects": [
                _effect(0, "writeState", owner="POWER.ILLUSION_POWER", target="sameOwnerBody",
                        field="Data.isReviving", value=True),
                _effect(1, "configureMove", owner="POWER.ILLUSION_POWER", target="sameOwnerBody",
                        move="REVIVE_MOVE", followUp="configured FollowUpStateId else previous StateLog last ID",
                        mustPerformOnce=True),
                _effect(2, "forceMove", owner="POWER.ILLUSION_POWER", target="sameOwnerBody", move="REVIVE_MOVE"),
                _effect(3, "heal", execution="awaited", owner="POWER.ILLUSION_POWER", target="sameOwnerBody",
                        amountExpression="MaxHp - CurrentHp"),
                _effect(4, "writeState", owner="POWER.ILLUSION_POWER", target="sameOwnerBody",
                        field="Data.isReviving", value=False),
            ],
        }],
    }
    steam = {
        "bodyIdentity": same_body, "ownerModel": "MONSTER.WATERFALL_GIANT",
        "phaseSystemId": "LIFECYCLE.PHASE.WATERFALL_GIANT_STEAM_ERUPTION",
        "sourceSignals": ["POWER.STEAM_ERUPTION_POWER", "MONSTER.WATERFALL_GIANT"],
        "provenance": [methods.evidence(_POWER_NS + "SteamEruptionPower", "AfterDeath"),
                       methods.evidence(_MONSTER_NS + "WaterfallGiant", "TriggerAboutToBlowState"),
                       methods.evidence(_MONSTER_NS + "WaterfallGiant", "AboutToBlowMove"),
                       methods.evidence(_MONSTER_NS + "WaterfallGiant", "ExplodeMove")],
        "transitions": [
            {
                "condition": actual_death, "repeatability": "once while Steam Eruption exists",
                "trigger": "fourArgumentAfterDeath",
                "transitionId": "LIFECYCLE.TRANSITION.WATERFALL_GIANT.ABOUT_TO_BLOW",
                "orderedEffects": [
                    _effect(0, "writeState", owner="MONSTER.WATERFALL_GIANT", target="sameOwnerBody",
                            field="IsAboutToBlow", value=True),
                    _effect(1, "setMaxAndCurrentHp", execution="awaited", owner="MONSTER.WATERFALL_GIANT",
                            target="sameOwnerBody", value=999999999, hpPipelineRef="hpPipeline.assignment"),
                    _effect(2, "changeHpDisplay", owner="MONSTER.WATERFALL_GIANT", target="sameOwnerBody"),
                    _effect(3, "forceMove", owner="MONSTER.WATERFALL_GIANT", target="sameOwnerBody",
                            move="AboutToBlow"),
                ],
            },
            {
                "condition": _constant(True), "repeatability": "terminal because Power removed",
                "trigger": "AboutToBlowMoveThenExplodeMove",
                "transitionId": "LIFECYCLE.TRANSITION.WATERFALL_GIANT.EXPLODE",
                "orderedEffects": [
                    _effect(0, "snapshotDamage", owner="MONSTER.WATERFALL_GIANT", target="runtimeState",
                            source="POWER.STEAM_ERUPTION_POWER.currentAmount"),
                    _effect(1, "removePower", execution="awaited", owner="MONSTER.WATERFALL_GIANT",
                            target="sameOwnerBody", power="POWER.STEAM_ERUPTION_POWER"),
                    _effect(2, "attack", execution="awaited", owner="MONSTER.WATERFALL_GIANT", target="players",
                            amountRef="snapshotted Steam amount"),
                    _effect(3, "kill", execution="awaited", owner="MONSTER.WATERFALL_GIANT",
                            target="sameOwnerBody", force=False, lifecycleRef="lifecycle.core"),
                ],
            },
        ],
        "runtimePressure": "dynamic",
    }
    gas = {
        "bodyIdentity": same_body, "ownerModel": "MONSTER.GAS_BOMB",
        "phaseSystemId": "LIFECYCLE.PHASE.GAS_BOMB_EXPLOSION",
        "sourceSignals": ["MONSTER.GAS_BOMB"],
        "provenanceRefs": ["behavior.MONSTER.GAS_BOMB operations.attack", "behavior.MONSTER.GAS_BOMB operations.kill"],
        "transitions": [{"condition": _constant(True), "repeatability": "terminal", "trigger": "explosionMove",
                         "transitionId": "LIFECYCLE.TRANSITION.GAS_BOMB.EXPLODE_AND_DIE",
                         "orderedEffects": [
                             _effect(0, "attack", execution="awaited", owner="MONSTER.GAS_BOMB", target="players",
                                     sourceRef="behavior.operations.attack"),
                             _effect(1, "kill", execution="awaited", owner="MONSTER.GAS_BOMB", target="sameOwnerBody",
                                     force=False, lifecycleRef="lifecycle.core"),
                         ]}],
    }
    return [test, egg, deci, illusion, steam, gas]


def _death_production(methods: _Methods, listener: Mapping[str, Any]) -> list[dict[str, Any]]:
    sites: list[dict[str, Any]] = []
    for implementation in listener["listenerImplementations"]:
        if implementation["listenerDomain"] != "power" or implementation["hook"] != "AfterDeath":
            continue
        physical_symbol = implementation["physicalBody"]["symbolSignature"]
        index = methods.symbols.get(physical_symbol)
        if index is None:
            raise SourceExtractionError(f"listener physical body is not a local method: {physical_symbol}")
        record = methods.assembly.method_record(index, methods.sha)
        for instruction_index, instruction in enumerate(record["instructions"]):
            operand = instruction.get("operand")
            if instruction["opcode"] in {"call", "callvirt"} and isinstance(operand, str) \
                    and operand.startswith("MegaCrit.Sts2.Core.Commands.CreatureCmd::Add sig:"):
                sites.append({
                    "addSiteId": f"LIFECYCLE.DEATH_ADD.SITE.{len(sites):02d}",
                    "instructionIndex": instruction_index,
                    "producerSourceType": implementation["declarationOwnerSourceType"],
                    "provenance": _proof(record, semantic={"target": operand}, origins={instruction_index}),
                    "symbolSignature": operand,
                })
    sites.sort(key=lambda row: (row["producerSourceType"], row["instructionIndex"], row["symbolSignature"]))
    for ordinal, row in enumerate(sites): row["addSiteId"] = f"LIFECYCLE.DEATH_ADD.SITE.{ordinal:02d}"
    if len(sites) != 4 or Counter(row["producerSourceType"] for row in sites) != {
        _POWER_NS + "InfestedPower": 1, _POWER_NS + "StockPower": 1, _POWER_NS + "SurprisePower": 2,
    }:
        raise SourceExtractionError("death-Power physical Add-site discovery drift")
    by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for site in sites: by_owner[site["producerSourceType"]].append(site)
    common = {
        "bodyIdentity": "newBodyViaCoreAdd",
        "condition": _all(_equal(_runtime("death.wasRemovalPrevented", "boolean"), _constant(False)),
                          _equal(_runtime("death.targetIsPowerOwner", "boolean"), _constant(True))),
        "coreAddRef": "production.coreAddContract", "hpAssignmentRef": "hpPipeline.assignment",
        "initialStateRef": "initialState", "trigger": "actualNonPreventedOwnerDeath",
        "d1Producer": False, "replacementWindowStopsCombatEnding": True,
    }
    return [
        {
            **common, "deathProductionId": "LIFECYCLE.DEATH_PRODUCTION.INFESTED",
            "producerPower": "POWER.INFESTED_POWER", "physicalAddSites": by_owner[_POWER_NS + "InfestedPower"],
            "orderedEffects": [
                _effect(0, "repeatAttempts", owner="POWER.INFESTED_POWER", target="ownerSide", count=4,
                        attemptOrder="index ascending 0..3"),
                _effect(1, "createMutableBody", owner="POWER.INFESTED_POWER", target="newBody",
                        model="MONSTER.WRIGGLER", fieldWrite={"StartStunned": True}),
                _effect(2, "coreAddByRef", execution="awaitedSequential", owner="POWER.INFESTED_POWER",
                        target="ownerSide", slot="PhrogParasiteElite.GetWrigglerSlotName(i)",
                        resultIdentity="exact returned body"),
                _effect(3, "setNodeVisible", owner="POWER.INFESTED_POWER", target="exactReturnedBody", value=False),
                _effect(4, "delayedReveal", execution="fireAndForgetSafe", owner="POWER.INFESTED_POWER",
                        target="orderedReturnedBodies", faultBoundary="TaskHelper.RunSafely"),
            ],
        },
        {
            **common, "deathProductionId": "LIFECYCLE.DEATH_PRODUCTION.STOCK",
            "producerPower": "POWER.STOCK_POWER", "physicalAddSites": by_owner[_POWER_NS + "StockPower"],
            "condition": _all(common["condition"],
                              {"kind": "comparison", "left": _runtime("power.amount", "integer"),
                               "operator": "greaterThan", "right": _constant(0), "valueType": "boolean"}),
            "orderedEffects": [
                _effect(0, "createBody", owner="POWER.STOCK_POWER", target="newBody", model="MONSTER.AXEBOT",
                        spawnAnimation=True, fieldWrite={"StockAmount": "power.amount - 1"}),
                _effect(1, "coreAddByRef", execution="awaited", owner="POWER.STOCK_POWER", target="ownerSide",
                        slot="exact owner slot", resultIdentity="exact returned body"),
                _effect(2, "setNodeVisible", owner="POWER.STOCK_POWER", target="exactReturnedBody", value=False),
                _effect(3, "delayedReveal", execution="fireAndForgetSafe", owner="POWER.STOCK_POWER",
                        target="exactReturnedBody", faultBoundary="TaskHelper.RunSafely"),
            ],
        },
        {
            **common, "deathProductionId": "LIFECYCLE.DEATH_PRODUCTION.SURPRISE",
            "producerPower": "POWER.SURPRISE_POWER", "physicalAddSites": by_owner[_POWER_NS + "SurprisePower"],
            "orderedEffects": [
                _effect(0, "precreateBody", owner="POWER.SURPRISE_POWER", target="fatBody",
                        model="MONSTER.FAT_GREMLIN", slot="fat"),
                _effect(1, "accumulateRuntimeGold", execution="awaitedSequential", owner="POWER.SURPRISE_POWER",
                        target="runtimeAccumulator", source="each POWER.THIEVERY_POWER"),
                _effect(2, "applyTargetedPower", execution="awaitedSequential", owner="POWER.SURPRISE_POWER",
                        target="exact precreated fatBody", power="POWER.HEIST_POWER"),
                _effect(3, "coreAddByRef", execution="awaited", owner="POWER.SURPRISE_POWER", target="ownerSide",
                        model="MONSTER.SNEAKY_GREMLIN", slot="sneaky"),
                _effect(4, "coreAddByRef", execution="awaited", owner="POWER.SURPRISE_POWER", target="ownerSide",
                        body="exact precreated fatBody", slot="fat"),
                _effect(5, "markGoldStolen", owner="POWER.SURPRISE_POWER", target="encounter",
                        condition="totalStolen != 0 and encounter is GremlinMercNormal"),
            ],
        },
    ]


def _subscriptions(methods: _Methods, reachable_source_types: set[str]) -> list[dict[str, Any]]:
    event_members = {"add_Died", "remove_Died", "add_CurrentHpChanged", "remove_CurrentHpChanged"}
    sites: list[dict[str, Any]] = []
    for index, row in enumerate(methods.assembly.md.MethodDef.rows, 1):
        owner = methods.assembly.type_names.get(methods.assembly.method_owner.get(index), "")
        outer = owner.split("+", 1)[0]
        if outer not in reachable_source_types or not row.Rva:
            continue
        record = methods.assembly.method_record(index, methods.sha)
        for instruction_index, instruction in enumerate(record["instructions"]):
            operand = instruction.get("operand")
            if instruction["opcode"] not in {"call", "callvirt"} or not isinstance(operand, str): continue
            member = operand.split(" sig:", 1)[0].rsplit("::", 1)[-1]
            if member not in event_members: continue
            callback = next((prior.get("operand") for prior in reversed(record["instructions"][:instruction_index])
                             if prior["opcode"] == "ldftn" and isinstance(prior.get("operand"), str)), None)
            sites.append({"callback": callback, "instructionIndex": instruction_index, "member": member,
                          "method": _proof(record), "owner": outer, "publisherType": operand.split("::", 1)[0]})
    if Counter(row["member"] for row in sites) != {
        "add_Died": 2, "remove_Died": 2, "add_CurrentHpChanged": 1, "remove_CurrentHpChanged": 1,
    }:
        raise SourceExtractionError("lifecycle subscription add/remove census drift")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sites:
        event = "Died" if row["member"].endswith("Died") else "CurrentHpChanged"
        groups[(row["owner"], event)].append(row)
    records = []
    for ordinal, ((owner, event), rows) in enumerate(sorted(groups.items())):
        add = [row for row in rows if row["member"].startswith("add_")]
        remove = [row for row in rows if row["member"].startswith("remove_")]
        if len(add) != 1 or len(remove) != 1 or not add[0]["callback"]:
            raise SourceExtractionError(f"subscription does not have exact add/callback/remove closure: {owner} {event}")
        canonical = _canonical_type(owner)
        presentation = event in {"Died", "CurrentHpChanged"}
        records.append({
            "addSite": {"instructionIndex": add[0]["instructionIndex"], "method": add[0]["method"]},
            "callbackSignature": add[0]["callback"], "classification": "exactPresentationOrAudioCleanup",
            "condition": _constant(True), "event": event, "orderedEffects": (
                [_effect(0, "unsubscribeSelf", owner=canonical, target="sameOwnerBody"),
                 _effect(1, "presentationCleanup", owner=canonical, target="sameOwnerBody",
                         detail="stop sleeping or clear exact animation")] if event == "Died"
                else [_effect(0, "playHpChangeSfx", owner=canonical, target="sameOwnerBody")]),
            "publisherBody": "sameOwnerBody", "repeatability": "oneShot" if event == "Died" else "untilRemoval",
            "restoredBehavior": "AfterAddedToRoom resubscribes exact callback",
            "subscriber": canonical, "subscriptionId": f"LIFECYCLE.SUBSCRIPTION.{ordinal:02d}.{event.upper()}",
            "unsubscribeSite": {"instructionIndex": remove[0]["instructionIndex"], "method": remove[0]["method"]},
        })
    return records


def _relationships_and_cleanup(methods: _Methods, listener: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cleanup_impls = [row for row in listener["listenerImplementations"]
                     if row["listenerDomain"] == "monster" and row["hook"] == "BeforeRemovedFromRoom"
                     and row["declarationKind"] == "effectiveOverride"]
    cleanup: list[dict[str, Any]] = []
    for ordinal, implementation in enumerate(sorted(cleanup_impls, key=lambda row: row["declarationOwnerSourceType"])):
        physical = methods.assembly.method_record(methods.symbols[implementation["physicalBody"]["symbolSignature"]], methods.sha)
        calls = [{"instructionIndex": i, "symbolSignature": item["operand"]}
                 for i, item in enumerate(physical["instructions"])
                 if item["opcode"] in {"call", "callvirt"} and isinstance(item.get("operand"), str)]
        cleanup.append({
            "cleanupId": f"LIFECYCLE.CLEANUP.{ordinal:02d}", "classification": "gameplayCleanup" if
                implementation["classification"] == "gameplayCleanup" else "exactPresentationOrAudioCleanup",
            "method": implementation["physicalBody"], "orderedCallSites": calls,
            "ownerModel": implementation["applicableOwners"][0]["canonicalModel"],
            "survivorGameplayEffects": False, "trigger": "BeforeRemovedFromRoom",
        })
    if len(cleanup) != 11:
        raise SourceExtractionError("BeforeRemovedFromRoom cleanup denominator drift")
    relationships = [
        {
            "relationshipId": "LIFECYCLE.RELATIONSHIP.QUEEN_AMALGAM_DEATH", "classification": "gameplay",
            "subscriber": "MONSTER.QUEEN", "publisherBody": "MONSTER.TORCH_HEAD_AMALGAM",
            "trigger": "fourArgumentAfterDeath", "repeatability": "once per matching body death",
            "condition": _all(_equal(_runtime("target.isTorchHeadAmalgam", "boolean"), _constant(True)),
                              _equal(_runtime("queen.isAlive", "boolean"), _constant(True))),
            "orderedEffects": ["write HasAmalgamDied=true", "clear exact Amalgam reference",
                               "exact music/talk presentation",
                               "force Enraged only when next move is BurnBrightForMe"],
            "unsubscribe": None, "restoredBehavior": "runtime body relation rebuilt from current teammates",
            "provenance": methods.evidence(_MONSTER_NS + "Queen", "AfterDeath"),
        },
        {
            "relationshipId": "LIFECYCLE.RELATIONSHIP.QUEEN_OWN_DEATH", "classification": "exactPresentationOrAudioCleanup",
            "subscriber": "MONSTER.QUEEN", "publisherBody": "sameQueenBody", "trigger": "fourArgumentAfterDeath",
            "condition": _equal(_runtime("targetIsQueenOwner", "boolean"), _constant(True)),
            "orderedEffects": ["queen-own-death presentation"], "repeatability": "once per dispatch",
            "unsubscribe": None, "restoredBehavior": "not applicable after removal",
            "provenance": methods.evidence(_MONSTER_NS + "Queen", "AfterDeath"),
        },
        {
            "relationshipId": "LIFECYCLE.RELATIONSHIP.KIN_FOLLOWER_PRIESTS", "classification": "gameplay",
            "subscriber": "each applicable alive MONSTER.KIN_PRIEST", "publisherBody": "matching Kin follower",
            "trigger": "fourArgumentAfterDeath", "condition": _all(
                _equal(_runtime("target.isKinFollower", "boolean"), _constant(True)),
                _equal(_runtime("orderedCurrentTeammates.anyLivingFollower", "boolean"), _constant(False))),
            "orderedEffects": ["for each applicable alive Priest in current teammate order",
                               "play exact surviving Priest AllFollowerDeathResponse"],
            "repeatability": "multi-Priest applicability retained", "unsubscribe": None,
            "restoredBehavior": "queries current teammates at dispatch", "singletonAssumption": False,
            "provenance": methods.evidence(_MONSTER_NS + "KinPriest", "AfterDeath"),
        },
        {
            "relationshipId": "LIFECYCLE.RELATIONSHIP.KAISER_CRUSHER", "classification": "exactPresentationOrAudioCleanup",
            "subscriber": "MONSTER.CRUSHER", "publisherBody": "sameCrusherBody", "trigger": "BeforeDeath",
            "condition": _constant(True), "orderedEffects": ["background arm/body animation", "music/SFX"],
            "repeatability": "per dispatch", "unsubscribe": None, "restoredBehavior": "presentation only",
            "provenance": methods.evidence(_MONSTER_NS + "Crusher", "BeforeDeath"),
        },
        {
            "relationshipId": "LIFECYCLE.RELATIONSHIP.KAISER_ROCKET", "classification": "exactPresentationOrAudioCleanup",
            "subscriber": "MONSTER.ROCKET", "publisherBody": "sameRocketBody", "trigger": "BeforeDeath",
            "condition": _constant(True), "orderedEffects": ["background arm/body animation", "music/SFX"],
            "repeatability": "per dispatch", "unsubscribe": None, "restoredBehavior": "presentation only",
            "provenance": methods.evidence(_MONSTER_NS + "Rocket", "BeforeDeath"),
        },
        {
            "relationshipId": "LIFECYCLE.RELATIONSHIP.WATERFALL_AMBIENT_CLEANUP",
            "classification": "exactPresentationOrAudioCleanup", "subscriber": "MONSTER.WATERFALL_GIANT",
            "publisherBody": "sameWaterfallGiantBody", "trigger": "BeforeRemovedFromRoom",
            "condition": _constant(True), "orderedEffects": ["ambient/music cleanup only"],
            "repeatability": "once on removal", "unsubscribe": None, "restoredBehavior": "ambient setup is separate",
            "gameplayPhaseRef": "LIFECYCLE.PHASE.WATERFALL_GIANT_STEAM_ERUPTION",
            "provenance": methods.evidence(_MONSTER_NS + "WaterfallGiant", "BeforeRemovedFromRoom"),
        },
    ]
    typed_relationship_effects = {
        "LIFECYCLE.RELATIONSHIP.QUEEN_AMALGAM_DEATH": [
            _effect(0, "writeState", owner="MONSTER.QUEEN", target="sameQueenBody", field="HasAmalgamDied", value=True),
            _effect(1, "clearRelationship", owner="MONSTER.QUEEN", target="exactAmalgamBody", field="Amalgam"),
            _effect(2, "musicAndTalk", owner="MONSTER.QUEEN", target="presentation"),
            _effect(3, "forceMoveConditional", owner="MONSTER.QUEEN", target="sameQueenBody",
                    condition="next move is BurnBrightForMe", move="Enraged"),
        ],
        "LIFECYCLE.RELATIONSHIP.QUEEN_OWN_DEATH": [
            _effect(0, "presentationCleanup", owner="MONSTER.QUEEN", target="sameQueenBody"),
        ],
        "LIFECYCLE.RELATIONSHIP.KIN_FOLLOWER_PRIESTS": [
            _effect(0, "orderedTeammateQuery", owner="each applicable alive MONSTER.KIN_PRIEST",
                    target="currentSameSideTeammates", singleton=False),
            _effect(1, "allFollowerDeathResponse", owner="each applicable alive MONSTER.KIN_PRIEST",
                    target="samePriestBody"),
        ],
        "LIFECYCLE.RELATIONSHIP.KAISER_CRUSHER": [
            _effect(0, "backgroundAnimation", owner="MONSTER.CRUSHER", target="presentation"),
            _effect(1, "musicAndSfx", owner="MONSTER.CRUSHER", target="presentation"),
        ],
        "LIFECYCLE.RELATIONSHIP.KAISER_ROCKET": [
            _effect(0, "backgroundAnimation", owner="MONSTER.ROCKET", target="presentation"),
            _effect(1, "musicAndSfx", owner="MONSTER.ROCKET", target="presentation"),
        ],
        "LIFECYCLE.RELATIONSHIP.WATERFALL_AMBIENT_CLEANUP": [
            _effect(0, "ambientAndMusicCleanup", owner="MONSTER.WATERFALL_GIANT", target="presentation"),
        ],
    }
    for relationship in relationships:
        relationship["orderedEffects"] = typed_relationship_effects[relationship["relationshipId"]]
        relationship["source"] = relationship["subscriber"]
        relationship["target"] = relationship["publisherBody"]
        relationship["targetSide"] = "sameSideOrExactBodyAsConditioned"
        relationship["bodyIdentity"] = "existingBodyReference"
    return relationships, cleanup


def _doom_contract(methods: _Methods) -> dict[str, Any]:
    return {
        "doomContractId": "LIFECYCLE.DOOM.LIST_KILL",
        "inputCardinality": "original selected body list, 0..N",
        "listIdentity": "same original list passed to one post-batch hook",
        "orderedEffects": [
            _effect(0, "doomVfx", execution="awaitedSequential", owner="POWER.DOOM_POWER",
                    target="each selected body in source order"),
            _effect(1, "kill", execution="awaitedSequential", owner="POWER.DOOM_POWER",
                    target="same selected body", force=False, lifecycleRef="lifecycle.core"),
            _effect(2, "afterDiedToDoom", execution="awaitedOnceAfterCompleteList",
                    owner="Hook", target="combatState and originalList", perBody=False),
        ],
        "failureContract": "a failed/cancelled awaited body stage prevents inference of later bodies or post-batch hook",
        "provenance": methods.evidence(_POWER_NS + "DoomPower", "DoomKill"),
    }


def _event_combat(methods: _Methods, event_scripts: Mapping[str, Any]) -> dict[str, Any]:
    transitions = event_scripts.get("transitions")
    outcomes = event_scripts.get("outcomes")
    if not isinstance(transitions, list) or not isinstance(outcomes, list):
        raise SourceExtractionError("event lifecycle requires prior E2c transitions/outcomes")
    combat = [row for row in transitions if isinstance(row, Mapping) and row.get("canonicalEncounter")]
    registrations = []
    for row in sorted(combat, key=lambda item: item["transitionId"]):
        resume = row.get("resume", {})
        should_resume = resume.get("shouldResume")
        if type(should_resume) is not bool:
            raise SourceExtractionError(f"event combat transition has no exact resume Boolean: {row.get('transitionId')}")
        registrations.append({
            "canonicalEncounter": row["canonicalEncounter"], "eventId": row["eventId"],
            "eventTransitionRef": row["transitionId"],
            "rewardEffectsRef": f"eventScripts.transitions[{row['transitionId']}].addedRewards",
            "routeAfterTerminalRewards": "awaitResumePreviousRoom" if should_resume else "normalMapTravel",
            "shouldResumeParentEventAfterCombat": should_resume,
        })
    if len(registrations) != 7 or Counter(row["shouldResumeParentEventAfterCombat"] for row in registrations) != {True: 3, False: 4}:
        raise SourceExtractionError("event combat registration/resume denominator drift")
    battle_outcomes = sorted(row["outcomeId"] for row in outcomes
                             if row.get("eventId") == "EVENT.BATTLEWORN_DUMMY")
    if len(battle_outcomes) != 3:
        raise SourceExtractionError("Battleworn Resume outcome denominator drift")
    time_limit = {
        "listener": "POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER", "trigger": "AfterSideTurnEnd",
        "participantPolicy": "only when participants contains exact Power owner",
        "branches": [
            {
                "branchId": "LIFECYCLE.EVENT.BATTLEWORN.NONPARTICIPANT",
                "condition": _equal(_runtime("participants.containsOwner", "boolean"), _constant(False)),
                "orderedEffects": [], "outcome": "completedNoOp",
            },
            {
                "branchId": "LIFECYCLE.EVENT.BATTLEWORN.DECREMENT",
                "condition": _all(_equal(_runtime("participants.containsOwner", "boolean"), _constant(True)),
                                  {"kind": "comparison", "left": _runtime("power.amount", "integer"),
                                   "operator": "greaterThan", "right": _constant(1), "valueType": "boolean"}),
                "orderedEffects": [_effect(0, "decrementPower", execution="awaited", owner="POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER",
                                                   target="exactOwnerBody", amount=1)],
            },
            {
                "branchId": "LIFECYCLE.EVENT.BATTLEWORN.INVALID_ENCOUNTER_CAST",
                "condition": _all(_equal(_runtime("participants.containsOwner", "boolean"), _constant(True)),
                                  {"kind": "comparison", "left": _runtime("power.amount", "integer"),
                                   "operator": "lessThanOrEqual", "right": _constant(1), "valueType": "boolean"},
                                  _equal(_runtime("owner.encounterExactCastSucceeds", "boolean"), _constant(False))),
                "orderedEffects": [], "outcome": "completedWithoutWriteOrEscape",
            },
            {
                "branchId": "LIFECYCLE.EVENT.BATTLEWORN.TIMEOUT",
                "condition": _all(_equal(_runtime("participants.containsOwner", "boolean"), _constant(True)),
                                  {"kind": "comparison", "left": _runtime("power.amount", "integer"),
                                   "operator": "lessThanOrEqual", "right": _constant(1), "valueType": "boolean"},
                                  _equal(_runtime("owner.encounterExactCastSucceeds", "boolean"), _constant(True))),
                "orderedEffects": [
                    _effect(0, "writeState", owner="POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER", target="exactEncounter",
                            field="RanOutOfTime", value=True, decrementBeforeWrite=False),
                    _effect(1, "escape", execution="awaited", owner="POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER",
                            target="exactOwnerBody", removeCreatureNode=True, lifecycleRef="lifecycle.removal.escapeGraph"),
                    _effect(2, "ordinaryCentralizedVictoryByRef", owner="coreLifecycle", target="combat",
                            lifecycleRef="lifecycle.combatTermination", timeoutResultEnum=None),
                ],
            },
        ],
        "provenance": methods.evidence(_POWER_NS + "BattlewornDummyTimeLimitPower", "AfterSideTurnEnd"),
    }
    state = {
        "contractId": "LIFECYCLE.STATE.BATTLEWORN.RAN_OUT_OF_TIME", "field": "_ranOutOfTime",
        "valueType": "boolean", "default": False, "defaultProof": "CLI zero-initialized Boolean backing field",
        "write": methods.evidence("MegaCrit.Sts2.Core.Models.Encounters.BattlewornDummyEventEncounter", "set_RanOutOfTime"),
        "read": methods.evidence("MegaCrit.Sts2.Core.Models.Encounters.BattlewornDummyEventEncounter", "get_RanOutOfTime"),
        "serializationRefs": ["eventScripts.stateContracts.encounter.RanOutOfTime",
                              "eventScripts.invocationCensus serialization/save/load witnesses"],
        "resumeReadRefs": battle_outcomes, "observationAvailability": "future adapter only",
    }
    routing = {
        "terminalRewardsMethod": methods.evidence(_RUN_MANAGER, "ProceedFromTerminalRewardsScreen"),
        "resumePreviousRoomMethod": methods.evidence(_RUN_MANAGER, "ResumePreviousRoom"),
        "battleResumeMethod": methods.evidence("MegaCrit.Sts2.Core.Models.Events.BattlewornDummy", "Resume"),
        "trueBranch": "await ResumePreviousRoom; existing Resume selects DEFEAT/no effects when RanOutOfTime else version VICTORY reward",
        "falseBranch": "normal map travel after terminal rewards",
        "eventEffectsCopied": False,
    }
    return {"battleTimeLimit": time_limit, "ranOutOfTime": state,
            "registrations": registrations, "routing": routing}


def _run_termination(methods: _Methods) -> dict[str, Any]:
    return {
        "architectVisualBoundary": {
            "activeCombat": False, "attackAnimationsDealDamage": False,
            "eventTerminalRef": "eventScripts.architect.terminal", "classification": "visualPseudoCombat",
        },
        "winRun": {
            "method": methods.evidence(_RUN_MANAGER, "WinRun"),
            "branches": [
                {"condition": _equal(_runtime("RunManager.State.isNull", "boolean"), _constant(True)),
                 "orderedEffects": [], "outcome": "completedWithoutOnEndedOrKills"},
                {"condition": _equal(_runtime("RunManager.State.isNull", "boolean"), _constant(False)),
                 "orderedEffects": [
                     _effect(0, "onEnded", owner="RunManager", target="currentRun", winning=True,
                             execution="synchronous"),
                     _effect(1, "guaranteeKillAllPlayers", owner="RunManager", target="runPlayers",
                             execution="awaited"),
                 ], "outcome": "completedOnlyAfterForcedKills"},
            ],
        },
        "onEnded": {
            "method": methods.evidence(_RUN_MANAGER, "OnEnded"),
            "winningArgument": True,
            "orderedEffects": [
                "update player/map-point history and turns",
                "serialize winning run with ToSave",
                "guard one run-history upload",
                "update enemy/epoch discovery, progress, and achievements",
                "create run-history entry and upload metrics",
                "delete current single/multiplayer saves as applicable",
                "calculate score from serialized winning run and increment Architect damage",
                "launch applicable daily uploads through TaskHelper.RunSafely",
            ],
            "scoreSerializationOrder": "serialization before forced player kills",
            "externalSideEffects": [
                {"kind": "platformStats", "resultClaim": "attemptedExternalSideEffect", "remoteSuccessClaimed": False},
                {"kind": "metricsUpload", "resultClaim": "attemptedExternalSideEffect", "remoteSuccessClaimed": False},
                {"kind": "dailyUpload", "faultBoundary": "TaskHelper.RunSafely", "remoteSuccessClaimed": False},
            ],
        },
        "guaranteeKillAllPlayers": {
            "method": methods.evidence(_RUN_MANAGER, "GuaranteeKillAllPlayers"),
            "enumeration": "RunState.Players snapshot/enumerator in source order",
            "orderedPerPlayer": [
                _effect(0, "kill", execution="awaitedSequential", owner="RunManager", target="player.Creature",
                        force=True, lifecycleRef="lifecycle.core", bypasses="prevention only",
                        hooksRetained=["BeforeDeath", "Died", "AfterDeath", "cleanup"]),
                _effect(1, "presentationWait", execution="awaitedSequential", owner="RunManager",
                        target="presentation", customScaledRange=[0.25, 0.5]),
            ],
            "faultContract": "fault/cancellation stops later waits/players; no success inference",
        },
    }


def _power_retention(listener: Mapping[str, Any]) -> list[dict[str, Any]]:
    hooks = {"ShouldCreatureBeRemovedFromCombatAfterDeath", "ShouldStopCombatFromEnding",
             "ShouldPowerBeRemovedOnDeath", "ShouldPowerBeRemovedAfterOwnerDeath",
             "ShouldOwnerDeathTriggerFatal"}
    rows = []
    for implementation in listener["listenerImplementations"]:
        if implementation["listenerDomain"] != "power" or implementation["hook"] not in hooks \
                or implementation["declarationKind"] != "effectiveOverride":
            continue
        owner = _canonical_type(implementation["declarationOwnerSourceType"])
        result = {
            "ShouldCreatureBeRemovedFromCombatAfterDeath": False,
            "ShouldStopCombatFromEnding": True,
            "ShouldPowerBeRemovedOnDeath": False,
            "ShouldPowerBeRemovedAfterOwnerDeath": False,
            "ShouldOwnerDeathTriggerFatal": True,
        }[implementation["hook"]]
        condition: dict[str, Any] = _equal(_runtime("targetIsPowerOwner", "boolean"), _constant(True))
        if implementation["hook"] == "ShouldOwnerDeathTriggerFatal" and owner == "POWER.REATTACH_POWER":
            condition = _equal(_runtime("sameSide.allOtherSegmentsDead", "boolean"), _constant(True))
        rows.append({
            "condition": condition, "hook": implementation["hook"],
            "policyId": f"LIFECYCLE.RETENTION.{owner}.{implementation['hook'].upper()}",
            "power": owner, "result": result, "sourceImplementationRef": implementation["implementationId"],
        })
    rows.sort(key=lambda row: row["policyId"])
    if Counter(row["hook"] for row in rows) != {
        "ShouldCreatureBeRemovedFromCombatAfterDeath": 5, "ShouldStopCombatFromEnding": 5,
        "ShouldPowerBeRemovedOnDeath": 1, "ShouldPowerBeRemovedAfterOwnerDeath": 5,
        "ShouldOwnerDeathTriggerFatal": 2,
    }:
        raise SourceExtractionError("power retention policy denominator drift")
    return rows


def _runtime_contracts() -> list[dict[str, Any]]:
    return [
        {"contractId": "LIFECYCLE.STATE.TEST_SUBJECT_RESPAWNS", "valueType": "integer", "default": 0,
         "update": "+1 at RespawnMove start", "reset": None, "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.TEST_SUBJECT_KILLS", "valueType": "integer", "default": "runtime run field",
         "update": "+1 in TriggerDeadState", "reset": "run lifecycle", "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.REVIVING", "valueType": "boolean", "default": False,
         "owners": ["AdaptablePower.Data", "ReattachPower.Data", "IllusionPower.Data"],
         "update": "true on qualifying death; false in revive/reattach", "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.TOUGH_EGG_IS_HATCHED", "valueType": "boolean", "default": False,
         "backingField": "_isHatched", "serialized": True, "update": "true before Hatch Power removal",
         "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.TOUGH_EGG_TITLE_HATCHED", "valueType": "boolean", "default": False,
         "backingField": "_hatched", "distinctFrom": "_isHatched", "update": "true after awaited Hatch Power removal",
         "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.TOUGH_EGG_AFTER_HATCHED_STATE", "valueType": "moveStateRef",
         "default": "generated graph state", "update": "forced after restored Hatch", "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.DEATH_POWER_RUNTIME", "valueType": "typedRuntimeValues",
         "fields": ["amount", "slots", "targets", "returnedBodyIdentity", "dynamicGold"],
         "default": "source runtime", "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.EVENT_PARENT_REWARD", "valueType": "runtimeCollectionsAndRoomStack",
         "default": "source runtime", "update": "terminal reward/room routing", "observationAvailability": False},
        {"contractId": "LIFECYCLE.STATE.ARCHITECT_EXTERNAL", "valueType": "nullableRunAndExternalResults",
         "default": "runtime", "update": "OnEnded(true) before kills", "remoteOutcomeObservable": False},
    ]

_SEMANTIC_ROOT_SPECS = (
    (_POWER_NS + "DoomPower", "DoomKill"),
    (_POWER_NS + "AdaptablePower", "AfterDeath"),
    (_MONSTER_NS + "TestSubject", "TriggerDeadState"),
    (_MONSTER_NS + "TestSubject", "RespawnMove"),
    (_MONSTER_NS + "TestSubject", "Revive"),
    (_POWER_NS + "HatchPower", "AfterSideTurnEnd"),
    (_MONSTER_NS + "ToughEgg", "AfterAddedToRoom"),
    (_MONSTER_NS + "ToughEgg", "HatchMove"),
    (_MONSTER_NS + "ToughEgg", "Hatch"),
    (_MONSTER_NS + "ToughEgg", "get_Title"),
    (_POWER_NS + "ReattachPower", "AfterDeath"),
    (_POWER_NS + "ReattachPower", "DoReattach"),
    (_POWER_NS + "IllusionPower", "AfterDeath"),
    (_POWER_NS + "SteamEruptionPower", "AfterDeath"),
    (_MONSTER_NS + "WaterfallGiant", "TriggerAboutToBlowState"),
    (_MONSTER_NS + "WaterfallGiant", "AboutToBlowMove"),
    (_MONSTER_NS + "WaterfallGiant", "ExplodeMove"),
    (_POWER_NS + "InfestedPower", "AfterDeath"),
    (_POWER_NS + "StockPower", "AfterDeath"),
    (_POWER_NS + "SurprisePower", "AfterDeath"),
    (_POWER_NS + "BattlewornDummyTimeLimitPower", "AfterSideTurnEnd"),
    ("MegaCrit.Sts2.Core.Models.Events.BattlewornDummy", "Resume"),
    (_RUN_MANAGER, "ProceedFromTerminalRewardsScreen"),
    (_RUN_MANAGER, "ResumePreviousRoom"),
    (_RUN_MANAGER, "WinRun"),
    (_RUN_MANAGER, "OnEnded"),
    (_RUN_MANAGER, "GuaranteeKillAllPlayers"),
)

_CLOSEOUT_PHYSICAL_PINS = {
    "MegaCrit.Sts2.Core.Models.Powers.DoomPower+<DoomKill>d__6::MoveNext sig:200001": "1096cddacc9a6648b2980f59a3eef02a655e71eff07c21b791219368cb056a6b",
    "MegaCrit.Sts2.Core.Models.Powers.AdaptablePower+<AfterDeath>d__9::MoveNext sig:200001": "8bd925eea1fe89b844f32a325865be06a96a046f894304164e0a966708c9645c",
    "MegaCrit.Sts2.Core.Models.Monsters.TestSubject+<TriggerDeadState>d__67::MoveNext sig:200001": "68d246e210dcf6c6b78a5ffaf7deb8d941f76fdf446e05ba6b09155cf9137537",
    "MegaCrit.Sts2.Core.Models.Monsters.TestSubject+<RespawnMove>d__74::MoveNext sig:200001": "e6a208a7b3a36701b1760934f4978435e908ba48c8aee346b09f56457933b2e6",
    "MegaCrit.Sts2.Core.Models.Monsters.ToughEgg+<HatchMove>d__35::MoveNext sig:200001": "904a358c67645df2b1f8263165cdd8a96f2683d95ff93b34e1b15409170aa36d",
    "MegaCrit.Sts2.Core.Models.Powers.ReattachPower+<AfterDeath>d__11::MoveNext sig:200001": "3f2333ce3552589b2590180e5a981c4d7a9f647f3b2492b5126648aeac3587d1",
    "MegaCrit.Sts2.Core.Models.Powers.BattlewornDummyTimeLimitPower+<AfterSideTurnEnd>d__4::MoveNext sig:200001": "61a5c935d8cff3460c9b9a502864dcfa76115243930939ac58032967f4696d18",
    "MegaCrit.Sts2.Core.Runs.RunManager+<WinRun>d__207::MoveNext sig:200001": "bc1f591c71d9bbb6ee1acf0f2e7ef31994a7a8c89643315a61f351e8e7286ea5",
    "MegaCrit.Sts2.Core.Runs.RunManager+<GuaranteeKillAllPlayers>d__217::MoveNext sig:200001": "7a74fb6ba1ea1500064c69d430b3985081c820a6fdb2d74beb8122fe3183665a",
}


def _resolve_dependency_rows(component: Any, component_name: str,
                             ref_by_id: Mapping[str, str] | None = None) -> None:
    if not isinstance(component, dict):
        return
    rows = component.get("dependencies")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or row.get("kind") != "lifecycle": continue
            row["status"] = "sourceComplete"
            row["resolvedComponentRef"] = (ref_by_id or {}).get(
                row.get("dependencyId"), "lifecycle.closeout"
            )
    for value in component.values():
        if isinstance(value, dict):
            _resolve_dependency_rows(value, component_name, ref_by_id)


def resolve_prior_lifecycle_dependencies(*, behavior: dict[str, Any], production: dict[str, Any],
                                         event_scripts: dict[str, Any]) -> None:
    production_dependencies = production.get("productionSemantics", {}).get("dependencies", [])
    production_refs = {
        "DEPENDENCY.PRODUCTION.CURRENT_ENEMY_LIFECYCLE": "lifecycle.core.removal",
        "DEPENDENCY.PRODUCTION.AFTER_CREATURE_ADDED_LISTENERS": "lifecycle.listenerImplementations",
        "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH": "lifecycle.phaseSystems.LIFECYCLE.PHASE.TOUGH_EGG_HATCH",
        "DEPENDENCY.PRODUCTION.DEATH_POWER_ADD_SITES": "lifecycle.deathProduction",
    }
    if {row.get("dependencyId") for row in production_dependencies} != set(production_refs):
        raise SourceExtractionError("production lifecycle dependency denominator changed")
    for row in production_dependencies:
        row["status"] = "sourceComplete"; row["resolvedComponentRef"] = production_refs[row["dependencyId"]]
    core_dependencies = production.get("coreAddContract", {}).get("dependencies")
    if not isinstance(core_dependencies, dict) or core_dependencies.get("lifecycle") not in {"pendingE2d2", "sourceCompleteE2d2"}:
        raise SourceExtractionError("core Add lifecycle boundary changed before closeout")
    core_dependencies["lifecycle"] = "sourceCompleteE2d2"
    _resolve_dependency_rows(event_scripts, "eventScripts", {
        "LIFECYCLE.POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER.AFTER_SIDE_TURN_END": "lifecycle.eventCombat.battleTimeLimit",
        "LIFECYCLE.COMMAND.CREATURE_ESCAPE/BATTLE_FRIEND_OWNER": "lifecycle.eventCombat.battleTimeLimit",
        "LIFECYCLE.COMBAT.EVENT_TERMINAL_RESULT": "lifecycle.eventCombat.routing",
        "LIFECYCLE.RUN.ARCHITECT_TERMINAL": "lifecycle.runTermination",
        "LIFECYCLE.RUN.ON_ENDED_TRUE": "lifecycle.runTermination.onEnded",
        "LIFECYCLE.RUN.GUARANTEE_KILL_ALL_PLAYERS": "lifecycle.runTermination.guaranteeKillAllPlayers",
        "LIFECYCLE.RUN.SERIALIZED_SCORE_STATS_HISTORY": "lifecycle.runTermination.onEnded",
        "LIFECYCLE.RUN.ARCHITECT_TERMINAL_ORDER": "lifecycle.runTermination.winRun",
    })
    event_dependencies = behavior.get("eventDependencies")
    if isinstance(event_dependencies, list):
        for row in event_dependencies:
            if row.get("kind") == "eventLifecycleTimeoutResultSemantics":
                row["status"] = "sourceComplete"; row["resolvedComponentRef"] = "lifecycle.eventCombat"


def _discover_phase_signals(listener: Mapping[str, Any], behavior: Mapping[str, Any],
                            production: Mapping[str, Any], phases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    implementations = listener["listenerImplementations"]
    after_death = {row["declarationOwnerSourceType"] for row in implementations
                   if row["listenerDomain"] == "power" and row["hook"] == "AfterDeath"
                   and row["declarationKind"] == "effectiveOverride"}
    prevents_removal = {row["declarationOwnerSourceType"] for row in implementations
                        if row["listenerDomain"] == "power"
                        and row["hook"] == "ShouldCreatureBeRemovedFromCombatAfterDeath"
                        and row["declarationKind"] == "effectiveOverride"}
    power_signals = sorted(_canonical_type(source_type) for source_type in after_death & prevents_removal)
    self_kill_signals = sorted({registration["canonicalMonster"] for registration in behavior["registrations"]
                                if any(operation.get("kind") == "kill" for operation in registration["operations"])})
    hatch_dependencies = [row["dependencyId"] for row in production["productionSemantics"]["dependencies"]
                          if row.get("kind") == "sameBodyHatchStateTransitionNotAdd"]
    signals = sorted(set(power_signals + self_kill_signals + hatch_dependencies))
    represented = sorted({signal for phase in phases for signal in phase["sourceSignals"]})
    if signals != represented:
        raise SourceExtractionError(
            f"phase signal closure has unrepresented or invented systems: discovered={signals!r} represented={represented!r}"
        )
    if len(signals) != 7 or len(phases) != 6:
        raise SourceExtractionError("phase signal/system post-discovery denominator drift")
    return {
        "discoveryRules": ["Power AfterDeath intersect removal prevention",
                           "current behavior ordinary self-kill owners",
                           "production same-body Hatch dependency"],
        "powerDeathRetentionSignals": power_signals,
        "selfKillSignals": self_kill_signals,
        "sameBodyHatchDependencySignals": hatch_dependencies,
        "signals": signals, "representedPhaseSystems": [phase["phaseSystemId"] for phase in phases],
        "unrepresentedSignals": [],
    }


def extract_lifecycle_closeout(assembly: Any, assembly_sha256: str, *,
                               listener: dict[str, Any], monsters: Sequence[Mapping[str, Any]],
                               reachable_models: set[str], behavior: dict[str, Any],
                               production: dict[str, Any], event_scripts: dict[str, Any]) -> dict[str, Any]:
    methods = _Methods(assembly, assembly_sha256)
    roots = set(listener.pop("physicalRootIndexes"))
    for owner, name in _SEMANTIC_ROOT_SPECS:
        logical_index, _, _ = methods.one(owner, name)
        roots.add(methods.async_methods.get(logical_index, logical_index))
    invocation_decisions = _invocation_decisions(assembly, assembly_sha256, roots)
    listener["invocationDecisions"] = invocation_decisions
    phases = _phase_systems(methods)
    listener["discovery"]["phaseSignals"] = _discover_phase_signals(listener, behavior, production, phases)
    death_production = _death_production(methods, listener)
    reachable_source_types = {row["sourceType"] for row in monsters
                              if (row["canonicalId"] if row["canonicalId"].startswith("MONSTER.")
                                  else "MONSTER." + row["canonicalId"]) in reachable_models}
    subscriptions = _subscriptions(methods, reachable_source_types)
    relationships, cleanup = _relationships_and_cleanup(methods, listener)
    resolve_prior_lifecycle_dependencies(behavior=behavior, production=production, event_scripts=event_scripts)
    component = {
        "cleanup": cleanup,
        "deathProduction": death_production,
        "discovery": listener["discovery"],
        "doom": _doom_contract(methods),
        "eventCombat": _event_combat(methods, event_scripts),
        "invocationDecisions": invocation_decisions,
        "listenerCensus": listener["listenerCensus"],
        "listenerImplementations": listener["listenerImplementations"],
        "phaseSystems": phases,
        "powerRetentionPolicies": _power_retention(listener),
        "relationships": relationships,
        "runTermination": _run_termination(methods),
        "runtimeStateContracts": _runtime_contracts(),
        "semanticPipelineAudit": {
            "coreDeathEvaluatorRef": "lifecycle.core", "duplicateDeathEvaluator": False,
            "coreAddRef": "production.coreAddContract", "duplicateAddEvaluator": False,
            "hpAssignmentRef": "hpPipeline.assignment", "duplicateHpEvaluator": False,
            "eventEffectsRef": "eventScripts", "eventEffectsCopied": False,
        },
        "status": "sourceCompleteE2Lifecycle",
    }
    component["sourceDenominators"] = {
        "beforeRemovedCleanup": len(cleanup), "deathAddPhysicalSites": 4,
        "deathProductionSystems": len(death_production), "effectiveListenerApplications": listener["listenerCensus"]["effectiveApplications"],
        "eventCombatRegistrations": len(component["eventCombat"]["registrations"]),
        "fixedPointPowerTypes": listener["listenerCensus"]["fixedPointPowerTypes"],
        "invocationDecisions": len(invocation_decisions), "listenerImplementations": len(listener["listenerImplementations"]),
        "monsterOwnerTypes": listener["listenerCensus"]["monsterOwnerTypes"],
        "phaseSystems": len(phases), "powerSeedTypes": listener["listenerCensus"]["powerSeedTypes"],
        "relationships": len(relationships), "runTerminationSystems": 1,
        "subscriptions": len(subscriptions),
    }
    component["subscriptions"] = subscriptions
    component["dependencyRefs"] = [
        {"dependencyId": "DEPENDENCY.LIFECYCLE.HP", "resolvedComponentRef": "hpPipeline.assignment", "status": "sourceComplete"},
        {"dependencyId": "DEPENDENCY.LIFECYCLE.INITIAL", "resolvedComponentRef": "initialState", "status": "sourceComplete"},
        {"dependencyId": "DEPENDENCY.LIFECYCLE.PRODUCTION", "resolvedComponentRef": "production.productionSemantics", "status": "sourceComplete"},
        {"dependencyId": "DEPENDENCY.LIFECYCLE.EVENT_SCRIPTS", "resolvedComponentRef": "eventScripts", "status": "sourceComplete"},
        {"dependencyId": "DEPENDENCY.LIFECYCLE.CORE", "resolvedComponentRef": "lifecycle.core", "status": "sourceComplete"},
    ]
    component["digests"] = {
        "listenerClosureSha256": witness_sha256({key: component[key] for key in
            ("discovery", "listenerCensus", "listenerImplementations")}),
        "mechanicsSha256": witness_sha256({key: component[key] for key in
            ("doom", "phaseSystems", "powerRetentionPolicies", "relationships", "subscriptions",
             "cleanup", "deathProduction", "eventCombat", "runTermination")}),
        "invocationOrderingSha256": witness_sha256([
            (row["caller"], row["instructionIndex"], row["callee"], row["classification"])
            for row in invocation_decisions]),
        "methodPinsSha256": witness_sha256(sorted(_CLOSEOUT_PHYSICAL_PINS.items())),
        "runtimeContractsSha256": witness_sha256(component["runtimeStateContracts"]),
    }
    validate_lifecycle_closeout(component)
    return component


def validate_lifecycle_closeout(value: Any) -> None:
    if not isinstance(value, dict) or value.get("status") != "sourceCompleteE2Lifecycle":
        raise SourceExtractionError("lifecycle closeout status is not source complete")
    den = value.get("sourceDenominators", {})
    expected_fixed = {
        "beforeRemovedCleanup": 11, "deathAddPhysicalSites": 4, "deathProductionSystems": 3,
        "effectiveListenerApplications": 1861, "eventCombatRegistrations": 7,
        "fixedPointPowerTypes": 71, "listenerImplementations": 80, "monsterOwnerTypes": 108,
        "phaseSystems": 6, "powerSeedTypes": 69, "relationships": 6,
        "runTerminationSystems": 1, "subscriptions": 3,
    }
    if any(den.get(key) != expected for key, expected in expected_fixed.items()):
        raise SourceExtractionError("lifecycle closeout source denominator drift")
    decisions = value.get("invocationDecisions", [])
    if den.get("invocationDecisions") != len(decisions) or len({row.get("invocationId") for row in decisions}) != len(decisions):
        raise SourceExtractionError("lifecycle closeout invocation denominator/identity drift")
    if any(row.get("classification") in {"ignored", "unresolved"} for row in decisions):
        raise SourceExtractionError("lifecycle closeout contains broad ignore or unresolved call")
    if value["listenerCensus"].get("postDiscoveryAssertions", {}).get("reachableShouldDieFamilyOverrides") != 0:
        raise SourceExtractionError("reachable monster/Power prevention listener appeared")
    if value["discovery"]["fixedPointIterations"][-1]["addedMonsters"] or value["discovery"]["fixedPointIterations"][-1]["addedPowers"]:
        raise SourceExtractionError("listener model closure did not reach a fixed point")
    if value["discovery"]["fixedPointIterations"][0]["addedPowers"] != ["POWER.HEIST_POWER"]:
        raise SourceExtractionError("Surprise-to-Heist fixed-point attribution changed")
    phase_signals = value["discovery"].get("phaseSignals", {})
    if len(phase_signals.get("signals", [])) != 7 or phase_signals.get("unrepresentedSignals") != []             or len(phase_signals.get("representedPhaseSystems", [])) != 6:
        raise SourceExtractionError("phase signal fixed-point coverage changed")
    # Distinguish one-argument callbacks from hook override declarations.
    died = [row for row in value["subscriptions"] if row["event"] == "Died"]
    if (len(died) != 2 or any(not row["callbackSignature"].endswith(" sig:20010112a7e4") for row in died)
            or any("sig:200101151282450112a7e4" in row["callbackSignature"] for row in died)):
        raise SourceExtractionError("method-name callback conflation in Died subscriptions")
    doom = value["doom"]["orderedEffects"]
    if [row["kind"] for row in doom] != ["doomVfx", "kill", "afterDiedToDoom"] \
            or doom[1].get("force") is not False or doom[2].get("perBody") is not False:
        raise SourceExtractionError("Doom list/ordinary kill/one post-batch hook order changed")
    by_phase = {row["phaseSystemId"]: row for row in value["phaseSystems"]}
    if len(by_phase) != 6:
        raise SourceExtractionError("duplicate or missing lifecycle phase system")
    test = by_phase["LIFECYCLE.PHASE.TEST_SUBJECT_ADAPTABLE"]
    first = test["transitions"][0]["orderedEffects"]
    if [row["owner"] for row in first] != ["POWER.ADAPTABLE_POWER", "POWER.ADAPTABLE_POWER",
                                                "MONSTER.TEST_SUBJECT", "MONSTER.TEST_SUBJECT", "MONSTER.TEST_SUBJECT"]:
        raise SourceExtractionError("Test Subject effect owner attribution changed")
    if test.get("derivedCompletedReviveCount") != 2 or test.get("capField") is not None \
            or test.get("stateReset") is not False or any(row["bodyIdentity"]["kind"] != "sameBody" for row in [test]):
        raise SourceExtractionError("Test Subject body/reset/cap contract changed")
    egg = by_phase["LIFECYCLE.PHASE.TOUGH_EGG_HATCH"]
    if egg["titleContract"] != {"getterField": "_hatched", "hatchWritesTitle": False, "isHatchedField": "_isHatched"} \
            or egg.get("deathOrAdd") is not False:
        raise SourceExtractionError("Tough Egg distinct field/title/same-body contract changed")
    expected_egg_transition_ids = ["LIFECYCLE.TRANSITION.TOUGH_EGG.HATCH_COUNTDOWN",
                                   "LIFECYCLE.TRANSITION.TOUGH_EGG.NORMAL_HATCH",
                                   "LIFECYCLE.TRANSITION.TOUGH_EGG.RESTORED_HATCH"]
    if [row.get("transitionId") for row in egg["transitions"]] != expected_egg_transition_ids:
        raise SourceExtractionError("Tough Egg HatchPower participant-only decrement contract changed")
    egg_transitions = {row["transitionId"]: row for row in egg["transitions"]}
    countdown = egg_transitions["LIFECYCLE.TRANSITION.TOUGH_EGG.HATCH_COUNTDOWN"]
    expected_countdown = {
        "condition": _equal(_runtime("sideTurn.participantsContainsOwner", "boolean"), _constant(True)),
        "repeatability": "each owner-participating side turn end", "trigger": "ownerSideTurnEnd",
        "transitionId": "LIFECYCLE.TRANSITION.TOUGH_EGG.HATCH_COUNTDOWN",
        "orderedEffects": [_effect(0, "decrementPower", execution="awaited", owner="POWER.HATCH_POWER",
                                   target="sameOwnerBody", amount=1)],
    }
    if countdown != expected_countdown:
        raise SourceExtractionError("Tough Egg HatchPower participant-only decrement contract changed")
    normal_egg = egg_transitions["LIFECYCLE.TRANSITION.TOUGH_EGG.NORMAL_HATCH"]
    if [row["kind"] for row in normal_egg["orderedEffects"]][:3] != ["writeState", "removePower", "writeState"] \
            or normal_egg["orderedEffects"][4].get("filter") != "all except MinionPower":
        raise SourceExtractionError("Tough Egg order or Minion retention changed")
    deci = by_phase["LIFECYCLE.PHASE.DECIMILLIPEDE_REATTACH"]
    if deci.get("addOrSlotChange") is not False or deci["bodyIdentity"]["kind"] != "sameBody":
        raise SourceExtractionError("Decimillipede body/slot contract changed")
    if any(row.get("d1Producer") is not False for row in value["deathProduction"]):
        raise SourceExtractionError("death Add was included in d1 producer semantics")
    if len([site for row in value["deathProduction"] for site in row["physicalAddSites"]]) != 4:
        raise SourceExtractionError("death Add physical closure changed")
    battle = value["eventCombat"]["battleTimeLimit"]
    timeout = next(row for row in battle["branches"] if row["branchId"].endswith("TIMEOUT"))
    if [row["kind"] for row in timeout["orderedEffects"]] != ["writeState", "escape", "ordinaryCentralizedVictoryByRef"] \
            or timeout["orderedEffects"][2].get("timeoutResultEnum", "bad") is not None:
        raise SourceExtractionError("Battle timeout write/escape/result order changed")
    registrations = value["eventCombat"]["registrations"]
    if Counter(row["shouldResumeParentEventAfterCombat"] for row in registrations) != {True: 3, False: 4}:
        raise SourceExtractionError("event parent routing cardinality changed")
    run = value["runTermination"]
    live = run["winRun"]["branches"][1]["orderedEffects"]
    if [row["kind"] for row in live] != ["onEnded", "guaranteeKillAllPlayers"]:
        raise SourceExtractionError("Architect OnEnded-before-force-kills order changed")
    kills = run["guaranteeKillAllPlayers"]["orderedPerPlayer"]
    if kills[0].get("force") is not True or kills[1].get("customScaledRange") != [0.25, 0.5] \
            or run["architectVisualBoundary"].get("attackAnimationsDealDamage") is not False:
        raise SourceExtractionError("Architect force-kill/wait/VFX boundary changed")
    if any(effect.get("remoteSuccessClaimed") is not False
           for effect in run["onEnded"]["externalSideEffects"]):
        raise SourceExtractionError("remote external success was invented")
    audit = value["semanticPipelineAudit"]
    if any(audit[key] is not False for key in ("duplicateDeathEvaluator", "duplicateAddEvaluator",
                                                "duplicateHpEvaluator", "eventEffectsCopied")):
        raise SourceExtractionError("duplicate lifecycle semantic pipeline")
    for symbol, expected_hash in _CLOSEOUT_PHYSICAL_PINS.items():
        matching = [proof for proof in _walk_proofs(value)
                    if proof.get("symbolSignature") == symbol]
        if not matching or any(proof.get("methodBodySha256") != expected_hash for proof in matching):
            raise SourceExtractionError(f"lifecycle closeout method body pin changed: {symbol}")
    expected_digests = {
        "listenerClosureSha256": witness_sha256({key: value[key] for key in
            ("discovery", "listenerCensus", "listenerImplementations")}),
        "mechanicsSha256": witness_sha256({key: value[key] for key in
            ("doom", "phaseSystems", "powerRetentionPolicies", "relationships", "subscriptions",
             "cleanup", "deathProduction", "eventCombat", "runTermination")}),
        "invocationOrderingSha256": witness_sha256([
            (row["caller"], row["instructionIndex"], row["callee"], row["classification"])
            for row in decisions]),
        "methodPinsSha256": witness_sha256(sorted(_CLOSEOUT_PHYSICAL_PINS.items())),
        "runtimeContractsSha256": witness_sha256(value["runtimeStateContracts"]),
    }
    if value.get("digests") != expected_digests:
        raise SourceExtractionError("lifecycle closeout canonical digest mismatch")


def _walk_proofs(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if "symbolSignature" in value and "methodBodySha256" in value:
            yield value
        for child in value.values(): yield from _walk_proofs(child)
    elif isinstance(value, list):
        for child in value: yield from _walk_proofs(child)
