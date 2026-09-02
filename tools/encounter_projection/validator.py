"""Fail-closed validation for source input and compact E2d2a projection schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from source_extractor.ast import (
    GRAPH_NODE_KINDS, OPERATION_KINDS, validate_expression, validate_graph,
    validate_operation, validate_selection,
)
from source_extractor.canonical import witness_sha256
from source_extractor.errors import SourceExtractionError
from source_extractor.event_scripts import validate_event_scripts
from source_extractor.identity import validate_observation_identities
from source_extractor.hp_pipeline import validate_hp_pipeline
from source_extractor.lifecycle import validate_lifecycle
from source_extractor.placement import validate_placement
from .contract import (
    AUTHORITY, EMBEDDED_SOURCE_INPUTS, GAME, GENERATOR_NAME, GENERATOR_VERSION,
    INTENT_KINDS, METADATA_KEYS, PAYLOAD_KEYS, PROJECTION_INPUTS, REQUIRED_COVERAGE,
    ROOT_KEYS, SCHEMA_VERSION, SOURCE_AUTHORITY, SOURCE_EXTRACTOR_VERSION,
    SOURCE_FACT_KEYS, SOURCE_SCHEMA_VERSION, coverage_rows,
)


def _fail(path: str, message: str) -> None:
    raise SourceExtractionError(f"projection validation failed at {path}: {message}")


def _object(value: Any, path: str, allowed: set[str], required: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    required = allowed if required is None else required
    unknown = set(value) - allowed
    missing = required - set(value)
    if unknown:
        _fail(path, f"unknown fields {sorted(unknown)!r}")
    if missing:
        _fail(path, f"missing fields {sorted(missing)!r}")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be a list")
    return value


def _string(value: Any, path: str, *, prefix: str | None = None) -> str:
    if not isinstance(value, str) or not value:
        _fail(path, "must be a nonempty string")
    if prefix is not None and not value.startswith(prefix):
        _fail(path, f"must start with {prefix!r}")
    return value


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(path, f"must be an integer >= {minimum}")
    return value


def _unique(rows: Iterable[dict[str, Any]], key: str, path: str) -> set[str]:
    result: set[str] = set()
    for index, row in enumerate(rows):
        value = _string(row.get(key), f"{path}[{index}].{key}")
        if value in result:
            _fail(f"{path}[{index}].{key}", f"duplicate ID {value!r}")
        result.add(value)
    return result


def _source_coverage(source: dict[str, Any], family: str) -> dict[str, Any]:
    if family.startswith("operationDirectSinksByKind."):
        return source["coverage"]["operationDirectSinksByKind"][family.split(".", 1)[1]]
    return source["coverage"][family]


def _validate_name(value: Any, path: str) -> None:
    if not isinstance(value, dict) or value.get("kind") not in {"localizedText", "localizedTemplate"}:
        _fail(path, "unsupported source name shape")
    if value["kind"] == "localizedText":
        _object(value, path, {"kind", "text"})
        _string(value["text"], path + ".text")
    else:
        obj = _object(value, path, {"inputs", "kind", "template"})
        _string(obj["template"], path + ".template")
        if not isinstance(obj["inputs"], dict) or not obj["inputs"]:
            _fail(path + ".inputs", "must be a nonempty expression map")
        for key, expression in obj["inputs"].items():
            _string(key, path + ".inputs key")
            validate_expression(expression, path=f"{path}.inputs.{key}")



_INITIAL_RECIPIENTS = {
    "appliedPowerDynamicVariable", "appliedPowerOwner", "constructedMonsterModel", "customPowerInstance",
    "eligiblePlayerCombatCards", "sourceMonster", "sourceMonsterLifecycle", "sourceMonsterModel",
    "sourceMonsterMoveState", "sourceMonsterOpponents",
}
_INITIAL_STAGES = {"constructorDefault", "encounterGeneration", "afterAddedToRoom", "powerAfterApplied", "beforeCombatStart"}
_INITIAL_PREDICATES = {"powerHookCondition", "restoredHatchedState", "sourceCardEligibilityPredicate"}


def _validate_initial_fact_contract(row: dict[str, Any], path: str, model_ids: set[str]) -> None:
    owner = _string(row.get("ownerModel"), path + ".ownerModel")
    applicable = _list(row.get("applicableModels"), path + ".applicableModels")
    if owner.startswith("MONSTER."):
        if owner not in model_ids or not applicable or owner not in applicable or not set(applicable) <= model_ids:
            _fail(path + ".applicableModels", "missing/unknown initial applicability edge")
    elif owner.startswith("POWER_OWNER.POWER."):
        if applicable:
            _fail(path + ".applicableModels", "Power-hook fact cannot invent monster applicability")
    else:
        _fail(path + ".ownerModel", "unsupported initial owner category")
    condition = row.get("condition")
    if not isinstance(condition, dict) or condition.get("kind") not in {"unconditional", "sourcePredicate"}:
        _fail(path + ".condition", "unsupported initial condition")
    if condition["kind"] == "unconditional":
        _object(condition, path + ".condition", {"kind"})
    else:
        predicate = _object(condition, path + ".condition", {"classification", "kind", "symbolSignature"})
        if predicate["classification"] not in _INITIAL_PREDICATES or " sig:" not in predicate["symbolSignature"]:
            _fail(path + ".condition", "unknown source predicate contract")
    recipient = _object(row.get("recipient"), path + ".recipient", {"kind"})
    if recipient["kind"] not in _INITIAL_RECIPIENTS:
        _fail(path + ".recipient.kind", "unsupported initial recipient")
    if row.get("stage") not in _INITIAL_STAGES:
        _fail(path + ".stage", "unsupported initial stage")
    _string(row.get("trigger"), path + ".trigger")
    order = _object(row.get("order"), path + ".order", {"sourceOrder", "stageOrder"})
    _integer(order["sourceOrder"], path + ".order.sourceOrder", minimum=0)
    _integer(order["stageOrder"], path + ".order.stageOrder", minimum=0)
    final = _object(row.get("finalValueContract"), path + ".finalValueContract",
                    {"classification", "runtimeModifierInputs", "scalingRefs"})
    if final["classification"] != "intrinsicRequestedBaseline":
        _fail(path + ".finalValueContract.classification", "baseline authority changed")
    for key in ("runtimeModifierInputs", "scalingRefs", "sourceStateInputs"):
        values = _list(row.get(key) if key == "sourceStateInputs" else final[key], path + "." + key)
        if len(values) != len(set(values)) or any(not isinstance(value, str) or not value for value in values):
            _fail(path + "." + key, "runtime/scaling refs must be unique nonempty strings")


def _initial_state_variable_names(value: Any) -> set[str]:
    result: set[str] = set()
    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("kind") == "stateVariable": result.add(str(node.get("name")))
            for child in node.values(): walk(child)
        elif isinstance(node, list):
            for child in node: walk(child)
    walk(value)
    return result


def _validate_state_collection(value: Any, path: str, node_ids: set[str]) -> None:
    row = _object(value, path, {"cardinality", "constructor", "elementType", "kind", "orderedNodes"})
    if row["elementType"] != "MoveState":
        _fail(path + ".elementType", "unknown graph collection element type")
    constructors = {
        "genericList": "<TypeSpec:1512809901128848>::.ctor sig:200001",
        "readOnlySingle": "<TypeSpec:1512b75001128848>::.ctor sig:2001011300",
    }
    if row["kind"] not in constructors or row["constructor"] != constructors[row["kind"]]:
        _fail(path, "unknown graph collection constructor/overload")
    ordered = _list(row["orderedNodes"], path + ".orderedNodes")
    cardinality = _integer(row["cardinality"], path + ".cardinality", minimum=1)
    if cardinality != len(ordered) or len(ordered) != len(set(ordered)):
        _fail(path, "graph collection order/cardinality is inconsistent")
    if row["kind"] == "readOnlySingle" and cardinality != 1:
        _fail(path + ".cardinality", "read-only single-element constructor cardinality changed")
    if any(node not in node_ids for node in ordered):
        _fail(path + ".orderedNodes", "graph collection element join is unknown")



def _production_method(value: Any, path: str, *, compact: bool) -> None:
    required = {"methodBodySha256", "normalizedSliceSha256", "symbolSignature"}
    if not isinstance(value, dict) or not required <= set(value):
        _fail(path, "production method provenance is incomplete")
    if compact and set(value) != required:
        _fail(path, "compact production provenance retained proof bulk")
    if not compact and "semanticWitnessSha256" not in value:
        _fail(path, "raw production semantic witness is missing")
    for key in required - {"symbolSignature"} | ({"semanticWitnessSha256"} if not compact else set()):
        if not isinstance(value.get(key), str) or len(value[key]) != 64:
            _fail(path + "." + key, "must be a SHA-256 digest")
    _string(value["symbolSignature"], path + ".symbolSignature")


def _validate_production_semantics(value: Any, path: str, *, move_ids: set[str],
                                   initial_fact_ids: set[str], compact: bool) -> set[str]:
    semantics = _object(value, path, {"dependencies", "pools", "postAddEffects", "producers",
                                      "runtimeStateContracts", "slotStrategies", "sourceDenominators", "status"})
    if semantics["status"] != "sourceComplete":
        _fail(path + ".status", "E2d1b producer semantics are not source-complete")
    expected_denominators = {"candidateEntries": 9, "candidateRngSelections": 1, "dependencyRefs": 4,
                             "pools": 7, "postAddEffects": 4, "producers": 7,
                             "runtimeStateContracts": 12, "slotStrategies": 6}
    if semantics["sourceDenominators"] != expected_denominators:
        _fail(path + ".sourceDenominators", "production semantic denominator drift")
    fact_ids: set[str] = set()

    pools = _list(semantics["pools"], path + ".pools")
    pool_ids = _unique(pools, "poolId", path + ".pools")
    candidates: list[str] = []
    dynamic_pools = 0
    for index, pool in enumerate(pools):
        pp = f"{path}.pools[{index}]"
        if compact:
            fact_ids.add(_string(pool.get("factId"), pp + ".factId", prefix="SOURCE.PRODUCTION_POOL."))
        elif "factId" in pool:
            _fail(pp + ".factId", "raw production pool cannot contain projection ID")
        models = _list(pool.get("candidateModels"), pp + ".candidateModels")
        if not models or len(models) != len(set(models)) or any(not isinstance(model, str) or not model.startswith("MONSTER.") for model in models):
            _fail(pp + ".candidateModels", "production pool candidate identity/order is invalid")
        candidates.extend(models)
        selection = pool.get("selection", {})
        if selection.get("kind") == "runtimeRng":
            dynamic_pools += 1
            if (models not in (["MONSTER.ZAPBOT", "MONSTER.STABBOT"], ["MONSTER.GUARDBOT", "MONSTER.NOISEBOT"])
                    or pool.get("replacementPolicy") != "reusablePoolWithImmediateSameReferenceExclusion"
                    or pool.get("filter") != {"comparison": "canonicalModelReferenceIdentity",
                        "excludeRuntimeStateRef": "RUNTIME.PRODUCTION.FABRICATOR_LAST_SPAWNED",
                        "kind": "excludeImmediatePreviousReference"}
                    or pool.get("emptySelection") != "NextItemReturnsNullThenToMutableFaults"):
                _fail(pp, "Fabricator reusable immediate-reference pool semantics changed")
            provenance = _object(pool.get("selectionProvenance"), pp + ".selectionProvenance",
                                 {"filter", "selectionAndWriteBeforeAdd", "uniformRng"})
            for key, method in provenance.items(): _production_method(method, pp + ".selectionProvenance." + key, compact=compact)
        elif (selection != {"kind": "fixedCanonicalModel"} or len(models) != 1
              or pool.get("replacementPolicy") != "reusableFixedCandidate"
              or pool.get("filter") != {"kind": "none"}):
            _fail(pp, "fixed reusable production pool semantics changed")
        _production_method(pool.get("provenance"), pp + ".provenance", compact=compact)
    if len(pools) != 7 or len(candidates) != 9 or len(set(candidates)) != 9 or dynamic_pools != 2:
        _fail(path + ".pools", "production pool/candidate/RNG closure incomplete")

    slots = _list(semantics["slotStrategies"], path + ".slotStrategies")
    slot_ids = _unique(slots, "slotStrategyId", path + ".slotStrategies")
    slot_kinds: dict[str, int] = {}
    no_slot: dict[str, int] = {}
    for index, slot in enumerate(slots):
        sp = f"{path}.slotStrategies[{index}]"
        if compact: fact_ids.add(_string(slot.get("factId"), sp + ".factId", prefix="SOURCE.SLOT_STRATEGY."))
        elif "factId" in slot: _fail(sp + ".factId", "raw slot strategy cannot contain projection ID")
        kind = slot.get("kind"); slot_kinds[kind] = slot_kinds.get(kind, 0) + 1
        behavior = slot.get("noSlotBehavior"); no_slot[behavior] = no_slot.get(behavior, 0) + 1
        ordered = slot.get("orderedEncounterSlots")
        if not isinstance(ordered, list) or not ordered or len(ordered) != len(set(ordered)):
            _fail(sp + ".orderedEncounterSlots", "ordered static slots are incomplete")
        if kind == "fixedName" and slot.get("fixedName") not in ordered:
            _fail(sp + ".fixedName", "fixed production slot is outside encounter slots")
        provenance = _object(slot.get("provenance"), sp + ".provenance", {"selection", "slots"})
        for key, method in provenance.items(): _production_method(method, sp + ".provenance." + key, compact=compact)
    if (len(slots) != 6 or slot_kinds != {"firstFreeDeclaredSlot": 2, "fixedName": 2, "lastFreeDeclaredSlot": 2}
            or no_slot != {"passEmptyStringToCoreAdd": 1, "passFixedNameWithoutOccupancyCheck": 2, "skipAttempt": 3}):
        _fail(path + ".slotStrategies", "slot/no-slot policy closure changed")

    effects = _list(semantics["postAddEffects"], path + ".postAddEffects")
    effect_ids = _unique(effects, "effectId", path + ".postAddEffects")
    expected_effects = {"POST_ADD.PRODUCTION.MINION.FABRICATOR", "POST_ADD.PRODUCTION.MINION.OVICOPTER",
                        "POST_ADD.PRODUCTION.OBSCURA_HAS_SUMMONED", "POST_ADD.PRODUCTION.RAT_GROUP_COUNTER_SYNC"}
    if effect_ids != expected_effects:
        _fail(path + ".postAddEffects", "producer-local post-Add effect census changed")
    for index, effect in enumerate(effects):
        ep = f"{path}.postAddEffects[{index}]"
        if compact: fact_ids.add(_string(effect.get("factId"), ep + ".factId", prefix="SOURCE.POST_ADD.PRODUCTION."))
        elif "factId" in effect: _fail(ep + ".factId", "raw post-Add effect cannot contain projection ID")
        if effect.get("ordering") != "afterNormalAddTaskReturn":
            _fail(ep + ".ordering", "post-Add effect moved before Add completion")
        _production_method(effect.get("provenance"), ep + ".provenance", compact=compact)
        support = effect.get("supportProvenance", [])
        if (effect["effectId"].endswith("RAT_GROUP_COUNTER_SYNC")) != bool(support):
            _fail(ep + ".supportProvenance", "Rat group setter closure mismatch")
        for si, method in enumerate(support): _production_method(method, f"{ep}.supportProvenance[{si}]", compact=compact)
        if compact and "validatedOrderInstructionIndices" in effect:
            _fail(ep, "compact post-Add effect retained diagnostic instruction indexes")
        if not compact and (not isinstance(effect.get("validatedOrderInstructionIndices"), list)
                            or effect["validatedOrderInstructionIndices"] != sorted(effect["validatedOrderInstructionIndices"])):
            _fail(ep + ".validatedOrderInstructionIndices", "raw post-Add order witness missing")

    contracts = _list(semantics["runtimeStateContracts"], path + ".runtimeStateContracts")
    contract_ids = _unique(contracts, "contractId", path + ".runtimeStateContracts")
    expected_contract_ids = {"RUNTIME.PRODUCTION.COMBAT_IS_LIVE", "RUNTIME.PRODUCTION.ENCOUNTER",
        "RUNTIME.PRODUCTION.CURRENT_ENEMIES", "RUNTIME.PRODUCTION.SAME_SIDE_CREATURES",
        "RUNTIME.PRODUCTION.CREATURE_IS_ALIVE", "RUNTIME.PRODUCTION.MONSTER_NEXT_MOVE_ID",
        "RUNTIME.PRODUCTION.MONSTER_AI_RNG", "RUNTIME.PRODUCTION.FABRICATOR_LAST_SPAWNED",
        "RUNTIME.PRODUCTION.RAT_TURNS_UNTIL_SUMMONABLE", "RUNTIME.PRODUCTION.RAT_CALL_FOR_BACKUP_COUNT",
        "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT", "RUNTIME.PRODUCTION.OBSCURA_HAS_SUMMONED"}
    if contract_ids != expected_contract_ids:
        _fail(path + ".runtimeStateContracts", "production runtime-state contract closure changed")
    by_contract = {row["contractId"]: row for row in contracts}
    expected_defaults = {"RUNTIME.PRODUCTION.FABRICATOR_LAST_SPAWNED": None,
                         "RUNTIME.PRODUCTION.RAT_TURNS_UNTIL_SUMMONABLE": 2,
                         "RUNTIME.PRODUCTION.RAT_CALL_FOR_BACKUP_COUNT": 0,
                         "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT": 1,
                         "RUNTIME.PRODUCTION.OBSCURA_HAS_SUMMONED": False}
    for contract_id, expected in expected_defaults.items():
        if by_contract[contract_id].get("default") != expected:
            _fail(path + ".runtimeStateContracts", "production state default changed")
    for index, contract in enumerate(contracts):
        cp = f"{path}.runtimeStateContracts[{index}]"
        if contract.get("observationAvailability") != "unavailableNoCurrentAdapter":
            _fail(cp + ".observationAvailability", "source getter was promoted into an observed value")
        if compact: fact_ids.add(_string(contract.get("factId"), cp + ".factId", prefix="SOURCE.RUNTIME.PRODUCTION."))
        elif "factId" in contract: _fail(cp + ".factId", "raw runtime contract cannot contain projection ID")
        methods = _list(contract.get("provenance"), cp + ".provenance")
        if not methods: _fail(cp + ".provenance", "runtime contract has no provenance")
        for mi, method in enumerate(methods): _production_method(method, f"{cp}.provenance[{mi}]", compact=compact)

    dependencies = _list(semantics["dependencies"], path + ".dependencies")
    dependency_ids = _unique(dependencies, "dependencyId", path + ".dependencies")
    expected_dependencies = {"DEPENDENCY.PRODUCTION.CURRENT_ENEMY_LIFECYCLE",
                             "DEPENDENCY.PRODUCTION.AFTER_CREATURE_ADDED_LISTENERS",
                             "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH", "DEPENDENCY.PRODUCTION.DEATH_POWER_ADD_SITES"}
    if dependency_ids != expected_dependencies:
        _fail(path + ".dependencies", "production E2d2 dependency boundary changed")
    for index, dependency in enumerate(dependencies):
        dp = f"{path}.dependencies[{index}]"
        expected_ref = {
            "DEPENDENCY.PRODUCTION.CURRENT_ENEMY_LIFECYCLE": "lifecycle.core.removal",
            "DEPENDENCY.PRODUCTION.AFTER_CREATURE_ADDED_LISTENERS": "lifecycle.listenerImplementations",
            "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH": "lifecycle.phaseSystems.LIFECYCLE.PHASE.TOUGH_EGG_HATCH",
            "DEPENDENCY.PRODUCTION.DEATH_POWER_ADD_SITES": "lifecycle.deathProduction",
        }[dependency["dependencyId"]]
        if (dependency.get("status") != "sourceComplete" or not dependency.get("sourceRefs")
                or dependency.get("resolvedComponentRef") != expected_ref):
            _fail(dp, "production lifecycle dependency is not exactly resolved")
        if compact: fact_ids.add(_string(dependency.get("factId"), dp + ".factId", prefix="SOURCE.DEPENDENCY.PRODUCTION."))
        elif "factId" in dependency: _fail(dp + ".factId", "raw dependency cannot contain projection ID")

    producers = _list(semantics["producers"], path + ".producers")
    producer_ids = _unique(producers, "producerId", path + ".producers")
    semantic_kinds: dict[str, int] = {}
    seen_moves: set[str] = set()
    for index, producer in enumerate(producers):
        pp = f"{path}.producers[{index}]"
        if compact: fact_ids.add(_string(producer.get("factId"), pp + ".factId", prefix="SOURCE.PRODUCTION.MONSTER."))
        elif "factId" in producer: _fail(pp + ".factId", "raw producer cannot contain projection ID")
        move = producer.get("moveRef")
        if move not in move_ids or move in seen_moves or producer.get("producerId") != "PRODUCTION." + move.replace("#", "."):
            _fail(pp, "producer/move identity join is ambiguous")
        seen_moves.add(move)
        kind = producer.get("semanticKind"); semantic_kinds[kind] = semantic_kinds.get(kind, 0) + 1
        attempts = _list(producer.get("attempts"), pp + ".attempts")
        if not attempts or any(attempt.get("poolRef") not in pool_ids or attempt.get("slotStrategyRef") not in slot_ids
                               or not set(attempt.get("postAddEffectRefs", [])) <= effect_ids
                               or attempt.get("awaitedResult") != "exactCreatedCreatureBody" for attempt in attempts):
            _fail(pp + ".attempts", "producer attempt pool/slot/body/post-Add join changed")
        runtime_refs = set(producer.get("availability", {}).get("runtimeInputRefs", []))
        if not runtime_refs <= contract_ids:
            _fail(pp + ".availability.runtimeInputRefs", "unknown production runtime input")
        deps = producer.get("dependencies", {})
        expected_hp_ref = "SOURCE.HP_ASSIGNMENT_PIPELINE" if compact else "hpPipeline.assignment"
        expected_lifecycle_refs = {("SOURCE." if compact else "") + value for value in dependency_ids}
        expected_initial_refs = {("SOURCE." if compact else "") + value for value in initial_fact_ids}
        if (deps.get("e2bHpAssignmentRef") != expected_hp_ref
                or not set(deps.get("e2d2LifecycleRefs", [])) <= expected_lifecycle_refs
                or not set(deps.get("e2aInitialStateFactRefs", [])) <= expected_initial_refs):
            _fail(pp + ".dependencies", "E2a/E2b/E2d2 producer dependency join changed")
        _production_method(producer.get("provenance"), pp + ".provenance", compact=compact)
    expected_kinds = {"orderedHelperBatch": 2, "fixedGraphOnce": 1, "runtimeCardinalityRepeating": 1,
                      "fixedThreeAttemptBatch": 1, "fixedGraphOnceWithStatePostAdd": 1, "groupCounterBounded": 1}
    if len(producers) != 7 or semantic_kinds != expected_kinds or seen_moves != move_ids & seen_moves:
        _fail(path + ".producers", "seven producer trigger semantics changed")
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for row in producers: by_kind.setdefault(row["semanticKind"], []).append(row)
    fabricators = by_kind["orderedHelperBatch"]
    expected_fabricator_maxima = {
        "PRODUCTION.MONSTER.FABRICATOR.FABRICATE_MOVE": (2, 5),
        "PRODUCTION.MONSTER.FABRICATOR.FABRICATING_STRIKE_MOVE": (1, 4),
    }
    if ({row.get("producerId") for row in fabricators} != set(expected_fabricator_maxima)
            or any(row.get("activationCardinality", {}).get("normallyAddedBodies", {}).get("maximum") != expected_fabricator_maxima[row["producerId"]][0]
                   or len(row["attempts"]) != expected_fabricator_maxima[row["producerId"]][0]
                   or row.get("concurrentPolicy") != {"classification": "predicateBounded",
                       "possiblePostActivationAliveSameSideMaximum": expected_fabricator_maxima[row["producerId"]][1],
                       "preActivationAliveSameSideMaximum": 3}
                   for row in fabricators)
            or any(row.get("lifetimePolicy") != {"classification": "sourceProvenNoLifetimeCapInClosedGraph", "poolDepletion": False}
                   for row in fabricators)
            or any(row.get("availability", {}).get("expression", {}).get("operator") != "lessThan"
                   or row["availability"]["expression"].get("right", {}).get("value") != 4 for row in fabricators)):
        _fail(path + ".producers", "Fabricator availability/batch/concurrent/lifetime semantics changed")
    ovi = by_kind["fixedThreeAttemptBatch"][0]
    if (ovi.get("activationCardinality") != {"bodyAddAttempts": {"exact": 3}, "normallyAddedBodies": {"maximum": 3, "minimum": 0}}
            or [row.get("path") for row in ovi.get("availability", {}).get("expression", {}).get("paths", [])] != ["initial", "repeatAfterTenderizer"]
            or ovi.get("lifetimePolicy", {}).get("hatchDependencyRef") != "DEPENDENCY.PRODUCTION.TOUGH_EGG_HATCH"):
        _fail(path + ".producers", "Ovicopter path/cardinality/Hatch boundary changed")
    living = by_kind["runtimeCardinalityRepeating"][0]
    if (living.get("activationCardinality", {}).get("bodyAddAttempts", {}).get("runtimeStateRef") != "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT"
            or living.get("lifetimePolicy") != {"classification": "sourceProvenNoLifetimeCapInClosedGraph", "poolDepletion": False}):
        _fail(path + ".producers", "Living Fog dynamic cardinality/no-lifetime-cap changed")
    rat = by_kind["groupCounterBounded"][0]
    if (rat.get("lifetimePolicy") != {"classification": "groupCounterBounded", "completedCallPathMaximum": 3,
                                     "normallyAddedBodyMaximum": 3, "scope": "allCurrentTwoTailedRats"}
            or rat.get("repeatPolicy", {}).get("classification") != "graphPerBodyUseOnlyOnce"
            or rat.get("availability", {}).get("evaluationOrder") != ["turnsAtOrBelowZero", "groupCallCountBelowThree",
                "encounterAndFirstFreeSlot", "noOtherTeammatePlansCallForBackup"]):
        _fail(path + ".producers", "Rat availability/repeat/group-counter lifetime bound changed")
    if (by_kind["fixedGraphOnce"][0].get("repeatPolicy", {}).get("classification") != "graphLifetimeOnce"
            or by_kind["fixedGraphOnceWithStatePostAdd"][0].get("repeatPolicy", {}).get("classification") != "graphLifetimeOnce"):
        _fail(path + ".producers", "fixed-slot graph-lifetime-once semantics changed")
    attempt_ids = [attempt.get("attemptId") for row in producers for attempt in row["attempts"]]
    if len(attempt_ids) != 8 or len(set(attempt_ids)) != 8:
        _fail(path + ".producers", "production attempt IDs/order are incomplete")
    for dependency in dependencies:
        if not set(dependency.get("affectedProducerRefs", [])) <= producer_ids:
            _fail(path + ".dependencies", "dependency refers to unknown producer")
    return fact_ids


def _validate_source_document(source: dict[str, Any]) -> None:
    if source.get("schemaVersion") != SOURCE_SCHEMA_VERSION:
        _fail("source.schemaVersion", f"expected {SOURCE_SCHEMA_VERSION}")
    if source.get("extractorVersion") != SOURCE_EXTRACTOR_VERSION:
        _fail("source.extractorVersion", f"expected {SOURCE_EXTRACTOR_VERSION!r}")
    if source.get("game") != GAME:
        _fail("source.game", "wrong version/branch/commit/main assembly identity")
    if source.get("inputs") != EMBEDDED_SOURCE_INPUTS:
        _fail("source.inputs", "wrong exact embedded input set/path/size/SHA-256")
    if source.get("authority") != SOURCE_AUTHORITY:
        _fail("source.authority", "malformed raw-only authority/fallback policy")
    if source.get("runtimeReady") is not False or source.get("status") != "incomplete":
        _fail("source", "source schema must remain incomplete and not runtime-ready")
    for family, (status, denominator, numerator, unresolved) in REQUIRED_COVERAGE.items():
        expected = {"denominator": denominator, "numerator": numerator, "status": status, "unresolved": unresolved}
        try:
            actual = _source_coverage(source, family)
        except (KeyError, TypeError) as exc:
            _fail(f"source.coverage.{family}", f"missing required coverage: {exc}")
        if actual != expected:
            _fail(f"source.coverage.{family}", f"coverage mismatch: expected {expected!r}, got {actual!r}")

    try:
        validate_hp_pipeline(source.get("hpPipeline"), path="source.hpPipeline")
    except SourceExtractionError as exc:
        _fail("source.hpPipeline", str(exc))
    try:
        validate_event_scripts(source.get("eventScripts"))
    except SourceExtractionError as exc:
        _fail("source.eventScripts", str(exc))
    try:
        validate_lifecycle(source.get("lifecycle"))
    except SourceExtractionError as exc:
        _fail("source.lifecycle", str(exc))

    encounters = source.get("encounters", {})
    if set(encounters) != {"ordinary", "event"} or len(encounters["ordinary"]) != 81 or len(encounters["event"]) != 8:
        _fail("source.encounters", "expected exactly 81 ordinary and 8 event encounters")
    all_models = {f"MONSTER.{row['canonicalId']}" for row in source.get("monsters", [])}
    current_models = {
        f"MONSTER.{row['canonicalId']}" for row in source.get("monsters", [])
        if row.get("reachability", {}).get("classification") in {"ordinaryReachable", "eventOnly"}
    }
    if len(current_models) != 108:
        _fail("source.monsters", "expected exactly 108 current reachable models")
    try:
        validate_placement(source.get("placement"))
        validate_observation_identities(source.get("observationIdentities"), reachable_models=current_models)
    except SourceExtractionError as exc:
        _fail("source.e1", str(exc))
    encounter_ids: set[str] = set()
    for kind in ("ordinary", "event"):
        for index, row in enumerate(encounters[kind]):
            path = f"source.encounters.{kind}[{index}]"
            canonical_id = _string(row.get("canonicalId"), path + ".canonicalId")
            if canonical_id in encounter_ids:
                _fail(path + ".canonicalId", "duplicate encounter ID")
            encounter_ids.add(canonical_id)
            low, high, members = validate_selection(row["initialRoster"]["selection"], path=path + ".initialRoster.selection", known_models=all_models)
            if row["initialRoster"]["cardinality"] != {"minimum": low, "maximum": high}:
                _fail(path + ".initialRoster.cardinality", "does not match roster AST")
            possible = set(row["possibleMonsters"])
            produced = set(row["producedMonsters"])
            if not members <= possible or not produced <= possible or not possible <= all_models:
                _fail(path, "broken possible/produced encounter-to-monster reference")
    for index, row in enumerate(source["monsters"]):
        path = f"source.monsters[{index}]"
        validate_expression(row["initialHp"]["expression"], path=path + ".initialHp.expression", expected_type="integerRange")
        if f"MONSTER.{row['canonicalId']}" in current_models:
            _validate_name(row["name"], path + ".name")
    registrations = source["behavior"]["registrations"]
    if len(registrations) != 315:
        _fail("source.behavior.registrations", "expected 315 registrations")
    move_ids = _unique(registrations, "canonicalId", "source.behavior.registrations")
    operation_ids: set[str] = set()
    for index, row in enumerate(registrations):
        for op_index, operation in enumerate(row["operations"]):
            validate_operation(operation, path=f"source.behavior.registrations[{index}].operations[{op_index}]")
            op_id = operation["operationId"]
            if op_id in operation_ids:
                _fail(f"source.behavior.registrations[{index}].operations[{op_index}].operationId", "duplicate operation ID")
            operation_ids.add(op_id)
    behavior_summary = source["behavior"].get("summary", {})
    derived_intents = sum(len(row["intents"]) for row in registrations)
    derived_intent_arguments = sum(len(intent["arguments"]) for row in registrations for intent in row["intents"])
    derived_async = sum(row["execution"]["kind"] == "asyncStateMachine" for row in registrations)
    derived_no_op = sum(row["execution"]["kind"] == "synchronousNoOp" for row in registrations)
    derived_localized = sum(row["title"]["classification"] == "localized" for row in registrations)
    if (derived_intents, derived_intent_arguments, derived_async, derived_no_op, derived_localized) != (393, 316, 305, 10, 297):
        _fail("source.behavior.registrations", "intent/action/title denominator drift")
    if (behavior_summary.get("intentConstructorSites"), behavior_summary.get("resolvedIntentConstructorSites"),
        behavior_summary.get("requiredIntentArguments"), behavior_summary.get("resolvedIntentArguments"),
        behavior_summary.get("asyncActions"), behavior_summary.get("synchronousNoOpActions"),
        behavior_summary.get("localizedTitles"), behavior_summary.get("missingOrInternalTitles")) != (393, 393, 316, 316, 305, 10, 297, 18):
        _fail("source.behavior.summary", "behavior summary denominator drift")
    expected_sink_counts = {"addGeneratedCard": 6, "addStatusCard": 14, "applyPower": 128, "attack": 207,
                            "attackHitCount": 50, "escape": 2, "gainBlock": 23, "heal": 2, "kill": 2,
                            "removeCard": 1, "removePower": 6, "stateWrite": 51, "summon": 5}
    derived_sinks = {kind: 0 for kind in expected_sink_counts}
    for row in registrations:
        if not row["operations"]:
            _fail("source.behavior.registrations", "registration operation closure missing")
        for operation in row["operations"]:
            if operation["kind"] in derived_sinks:
                derived_sinks[operation["kind"]] += 1
    if derived_sinks != expected_sink_counts or behavior_summary.get("directSinkCounts") != expected_sink_counts:
        _fail("source.behavior.summary.directSinkCounts", "operation sink denominator drift")
    invocation_census = source["behavior"].get("invocationCensus", {})
    invocation_decisions = invocation_census.get("decisions", [])
    invocation_ids = {row.get("invocationId") for row in invocation_decisions}
    if len(invocation_decisions) != 6786 or len(invocation_ids) != 6786 or invocation_census.get("summary", {}).get("denominator") != 6786 or invocation_census.get("summary", {}).get("resolved") != 6786 or invocation_census.get("summary", {}).get("unresolved") != 0:
        _fail("source.behavior.invocationCensus", "closed invocation denominator drift")

    graphs = source["behavior"]["graphs"]
    if len(graphs) != 105:
        _fail("source.behavior.graphs", "expected 105 behavior graphs")
    _unique(graphs, "graphId", "source.behavior.graphs")
    for index, graph in enumerate(graphs):
        graph_ast = {key: graph[key] for key in ("canonicalMonster", "graphId", "sourceType", "topology", "provenance", "nodes", "edges", "initial")}
        validate_graph(graph_ast, path=f"source.behavior.graphs[{index}]")
    random_contract = source["behavior"].get("randomSelectionContract")
    if not isinstance(random_contract, dict) or random_contract.get("summary") != {
        "branches": 61, "floatCallbacks": 8, "graphs": 21, "overloads": 10,
        "repeatTypeDistribution": {"CanRepeatForever": 4, "CanRepeatXTimes": 10, "CannotRepeat": 45, "UseOnlyOnce": 2},
    }:
        _fail("source.behavior.randomSelectionContract", "random runtime denominator/repeat distribution drift")
    if set(random_contract.get("methods", {})) != {"callbackEvaluation", "effectiveWeight", "selection"} or len(random_contract.get("overloads", [])) != 10:
        _fail("source.behavior.randomSelectionContract", "random overload/runtime method closure incomplete")
    expected_random_algorithm = {
        "effectiveWeight": "repeat/state-log/cooldown suppression multiplier times current float weight callback",
        "historyInputs": ["moveStateMachine.states", "moveStateMachine.stateLog"],
        "normalization": "dynamic effective weights are summed; zeroed branches remain unavailable",
        "selection": "Rng.NextFloat(effectiveWeightTotal), then source-order cumulative subtraction",
        "zeroTotal": "throws InvalidOperationException when no valid state is selected",
    }
    if random_contract.get("algorithm") != expected_random_algorithm:
        _fail("source.behavior.randomSelectionContract.algorithm", "state-log/effective-weight/RNG contract changed")
    expected_random_methods = {"callbackEvaluation": "::GetWeight sig:20000c", "effectiveWeight": "::GetStateWeight sig:00020c11bf6c12a7e4", "selection": "::GetNextState sig:20020e12a7e4128544"}
    if any(not random_contract["methods"][key]["symbolSignature"].endswith(suffix) for key, suffix in expected_random_methods.items()):
        _fail("source.behavior.randomSelectionContract.methods", "random runtime method identity changed")
    expected_overload_parameters = sorted([
        (("state", "class"), ("maxRepeats", "i4")), (("state", "class"), ("repeatType", "valuetype")),
        (("state", "class"), ("maxRepeats", "i4"), ("weight", "r4")),
        (("state", "class"), ("cooldown", "i4"), ("repeatType", "valuetype")),
        (("state", "class"), ("maxRepeats", "i4"), ("weight", "genericInstance")),
        (("state", "class"), ("repeatType", "valuetype"), ("weight", "r4")),
        (("state", "class"), ("repeatType", "valuetype"), ("weight", "genericInstance")),
        (("state", "class"), ("cooldown", "i4"), ("repeatType", "valuetype"), ("weight", "r4")),
        (("state", "class"), ("cooldown", "i4"), ("repeatType", "valuetype"), ("weight", "genericInstance")),
        (("state", "class"), ("cooldown", "i4"), ("maxRepeats", "i4"), ("weight", "genericInstance")),
    ])
    actual_overload_parameters = sorted(tuple((item["name"], item["cliKind"]) for item in row["parameters"]) for row in random_contract["overloads"])
    if actual_overload_parameters != expected_overload_parameters or len({row["method"]["symbolSignature"] for row in random_contract["overloads"]}) != 10:
        _fail("source.behavior.randomSelectionContract.overloads", "AddBranch overload parameter/type/order closure changed")
    if random_contract.get("enum", {}).get("values") != [
        {"name": "CanRepeatForever", "value": 0}, {"name": "CanRepeatXTimes", "value": 1},
        {"name": "CannotRepeat", "value": 2}, {"name": "UseOnlyOnce", "value": 3},
    ]:
        _fail("source.behavior.randomSelectionContract.enum", "MoveRepeatType metadata mismatch")
    applicability = source["behavior"].get("applicability")
    if not isinstance(applicability, list) or len(applicability) != len(graphs):
        _fail("source.behavior.applicability", "owner/graph applicability denominator mismatch")
    app_by_owner = {}
    for index, relation in enumerate(applicability):
        owner = _string(relation.get("behaviorOwnerSourceType"), f"source.behavior.applicability[{index}].behaviorOwnerSourceType")
        if owner in app_by_owner:
            _fail(f"source.behavior.applicability[{index}]", "duplicate behavior owner relation")
        rows = relation.get("applicableConcreteModels")
        if not isinstance(rows, list) or not rows:
            _fail(f"source.behavior.applicability[{index}]", "owner has no concrete applicability")
        models = [row.get("canonicalMonster") for row in rows]
        if len(models) != len(set(models)) or not set(models) <= current_models:
            _fail(f"source.behavior.applicability[{index}]", "ambiguous or unknown concrete applicability")
        app_by_owner[owner] = models
    for family, rows in (("graphs", graphs), ("registrations", registrations)):
        for index, row in enumerate(rows):
            if row.get("applicableConcreteModels") != app_by_owner.get(row.get("sourceType")):
                _fail(f"source.behavior.{family}[{index}].applicableConcreteModels", "does not equal exact owner applicability")
    if any(row["canonicalId"] not in move_ids for row in registrations):
        raise AssertionError("unreachable")

    graph_by_id = {row["graphId"]: row for row in graphs}
    registration_by_id = {row["canonicalId"]: row for row in registrations}
    for index, graph in enumerate(graphs):
        node_ids = {node["nodeId"] for node in graph["nodes"]}
        _validate_state_collection(graph.get("stateCollection"), f"source.behavior.graphs[{index}].stateCollection", node_ids)

    dependencies = _list(source["behavior"].get("eventDependencies"), "source.behavior.eventDependencies")
    if len(dependencies) != 4:
        _fail("source.behavior.eventDependencies", "expected four explicit script/lifecycle dependency boundaries")
    dependency_ids = _unique(dependencies, "dependencyId", "source.behavior.eventDependencies")
    initial_source_fact_ids = {row["factId"] for row in source["initialState"]["initialStateFacts"]}
    for index, dependency in enumerate(dependencies):
        path = f"source.behavior.eventDependencies[{index}]"
        obj = _object(dependency, path, {"dependencyId", "initialStateFactRefs", "kind", "resolvedComponentRef", "sourceRoots", "sourceType", "status"},
                      {"dependencyId", "kind", "sourceRoots", "sourceType", "status"})
        if obj["kind"] not in {"scriptedEventSemantics", "eventLifecycleTimeoutResultSemantics"}:
            _fail(path, "event dependency kind is not explicit")
        if obj["kind"] == "scriptedEventSemantics":
            if obj["status"] != "sourceComplete" or obj.get("resolvedComponentRef") != "EVENT_SCRIPT_COMPONENT.THE_ARCHITECT":
                _fail(path, "Architect scripted dependency is not resolved by the extracted component")
        elif obj["status"] != "sourceComplete" or obj.get("resolvedComponentRef") != "lifecycle.eventCombat":
            _fail(path, "event lifecycle dependency is not resolved by lifecycle event combat")
        roots = _list(obj["sourceRoots"], path + ".sourceRoots")
        if not roots or any(not isinstance(root.get("methodBodySha256"), str) or not isinstance(root.get("symbolSignature"), str) for root in roots):
            _fail(path + ".sourceRoots", "event dependency source roots/provenance missing")
        refs = obj.get("initialStateFactRefs", [])
        if not set(refs) <= initial_source_fact_ids:
            _fail(path + ".initialStateFactRefs", "unknown event lifecycle initial-state fact")
        if obj["kind"] == "eventLifecycleTimeoutResultSemantics" and len(refs) != 1:
            _fail(path + ".initialStateFactRefs", "event lifecycle dependency needs one timeout initial-state fact")
        if obj["kind"] == "scriptedEventSemantics" and refs:
            _fail(path + ".initialStateFactRefs", "scripted event dependency cannot guess lifecycle facts")

    production = _object(source.get("production"), "source.production", {
        "addApiCensus", "applicability", "coreAddContract", "directSites", "helperCallSites",
        "ostySummonCensus", "ostySummonContract", "producerRoots", "productionSemantics", "summary",
    })
    expected_production_summary = {
        "addAssemblySites": 14, "currentDirectSites": 6, "helperCallEdges": 5, "helperMethods": 3,
        "ostyAssemblySites": 17, "ownerEncounterApplicability": 6, "producerOwners": 6,
        "producerRoots": 7, "siteClassifications": {"coreAddForwarding": 2,
            "currentEnemyEncounterProduction": 6, "outOfScopeDeathPower": 4,
            "outOfScopeMock": 1, "outOfScopePlayerPet": 1},
    }
    if production["summary"] != expected_production_summary:
        _fail("source.production.summary", "production discovery denominator drift")
    add_sites = _list(production["addApiCensus"], "source.production.addApiCensus")
    osty_sites = _list(production["ostySummonCensus"], "source.production.ostySummonCensus")
    add_ids = _unique(add_sites, "siteId", "source.production.addApiCensus")
    _unique(osty_sites, "siteId", "source.production.ostySummonCensus")
    if len(add_sites) != 14 or len(osty_sites) != 17:
        _fail("source.production", "Add/Osty census incomplete")
    derived_site_counts: dict[str, int] = {}
    for row in add_sites:
        derived_site_counts[row["classification"]] = derived_site_counts.get(row["classification"], 0) + 1
    if derived_site_counts != expected_production_summary["siteClassifications"] or any(row["classification"] == "currentEnemyEncounterProduction" for row in osty_sites):
        _fail("source.production.addApiCensus", "Add classification/Osty separation mismatch")
    roots = _list(production["producerRoots"], "source.production.producerRoots")
    root_ids = _unique(roots, "moveId", "source.production.producerRoots")
    if len(roots) != 7 or not root_ids <= move_ids or len({row["ownerModel"] for row in roots}) != 6:
        _fail("source.production.producerRoots", "producer registration/owner join incomplete")
    for index, root in enumerate(roots):
        if not set(root["discoveryDecisionRefs"]) <= invocation_ids or not root["discoveryDecisionRefs"]:
            _fail(f"source.production.producerRoots[{index}]", "missing behavior invocation evidence reuse")
    helpers = _list(production["helperCallSites"], "source.production.helperCallSites")
    if len(helpers) != 5 or len(_unique(helpers, "callSiteId", "source.production.helperCallSites")) != 5 or len({row["calleeSymbolSignature"] for row in helpers}) != 3 or any(row["calleeSymbolSignature"] == row["callerSymbolSignature"] for row in helpers):
        _fail("source.production.helperCallSites", "helper closure duplicated/incomplete/cyclic")
    direct_sites = _list(production["directSites"], "source.production.directSites")
    if len(direct_sites) != 6 or any(row["apiSiteRef"] not in add_ids or not set(row["rootRefs"]) <= root_ids for row in direct_sites):
        _fail("source.production.directSites", "direct Add/root join incomplete")
    if any(row.get("awaitedResult") != "exactCreatedCreatureBody" or row.get("side") != {"enumName": "Enemy", "enumValue": 2} or not isinstance(row.get("slotArgument"), str) or not row["slotArgument"] or row.get("targetCombat") != "sourceMonsterCombatState" for row in direct_sites):
        _fail("source.production.directSites", "target/side/slot/awaited body identity changed")
    if len(production["applicability"]) != 6 or {row["ownerModel"] for row in production["applicability"]} != {row["ownerModel"] for row in roots}:
        _fail("source.production.applicability", "owner/encounter applicability closure incomplete")
    core = production["coreAddContract"]
    if len(core.get("overloads", [])) != 3 or len(core.get("methods", {})) != 6 or core.get("hookBoundary") != {
        "afterCreatureAddedToCombat": "awaited", "afterSummon": "absentSeparateOstyApi"}:
        _fail("source.production.coreAddContract", "core Add overload/method/hook closure incomplete")
    if core.get("semanticBoundaries") != {"coreSlotValidation": "absent", "emptyOrNoSlot": "producerOwnedSourceCompleteE2d1b"} or core.get("failureSemantics", {}).get("rollback") != "absent":
        _fail("source.production.coreAddContract", "core slot/failure boundary changed")
    expected_core_order = ["createBody", "encounterOnCreatureSpawned", "coreLiveCheck", "combatBodyListInsertion", "combatManagerNodeInsertion", "roomNodeInsertion", "awaitInitialStateDispatch", "prepareForNextTurn", "uniqueRoomMonsterIdHistory", "awaitAfterCreatureAddedToCombat", "returnCreatedBody"]
    dependencies = core.get("dependencies", {})
    if (dependencies.get("hpAssignmentComponentRef") != "hpPipeline.assignment" or dependencies.get("initialStateComponentRef") != "initialState"
            or len(dependencies.get("initialStateFactRefs", [])) != 7 or len(dependencies.get("initialStateOwnerModels", [])) != 9
            or len(dependencies.get("initialStateNoGameplayFactModels", [])) != 4 or dependencies.get("lifecycle") != "sourceCompleteE2d2"
            or dependencies.get("producerSemantics") != "sourceCompleteE2d1b"):
        _fail("source.production.coreAddContract.dependencies", "E2a/E2b/E2d1b/E2d2 dependency join incomplete")
    if core.get("callOrder") != expected_core_order:
        _fail("source.production.coreAddContract", "core Add order or E2a/E2b/E2d1b/E2d2 dependency changed")
    if core.get("resultIdentity") != "generic and explicit-model wrappers return the exact body created before awaiting core Add" or core.get("history", {}).get("not") != ["bodyCount", "productionCap", "poolDepletion"]:
        _fail("source.production.coreAddContract", "awaited identity or unique-model history meaning changed")
    if any(not row.get("candidateMembership", {}).get("canonicalModels") for row in direct_sites):
        _fail("source.production.directSites", "exact candidate membership missing")
    osty_contract = production["ostySummonContract"]
    if osty_contract.get("afterSummon") != "awaitedAfterOstyAddOrReviveHistory" or osty_contract.get("classification") != "separateFromCreatureCmdAddEnemyProduction" or len(osty_contract.get("methods", {})) != 2:
        _fail("source.production.ostySummonContract", "Osty AfterSummon separation incomplete")
    _validate_production_semantics(production["productionSemantics"], "source.production.productionSemantics",
                                   move_ids=move_ids,
                                   initial_fact_ids={row["factId"] for row in source["initialState"]["initialStateFacts"]},
                                   compact=False)

    event_turn = _list(source["behavior"].get("eventTurnMachines"), "source.behavior.eventTurnMachines")
    event_ids = {row["canonicalId"] for row in encounters["event"]}
    if len(event_turn) != 8 or {row.get("canonicalEncounter") for row in event_turn} != event_ids:
        _fail("source.behavior.eventTurnMachines", "expected one classification for every event encounter")
    classifications = {"normalTurnMachine", "inheritedTurnMachine", "noOpTurnMachineWithLifecycle", "scriptedNonTurnCombat"}
    event_only_models = set(source["reachability"]["eventOnlyModels"])
    physical_owners: set[str] = set(); physical_registrations: set[str] = set()
    reuse_count = no_op_count = physical_title_count = 0
    encounter_by_id = {row["canonicalId"]: row for row in encounters["event"]}
    link_by_id = {row["canonicalEncounter"].removeprefix("ENCOUNTER."): row for row in source["placement"]["eventLinkage"]}
    for index, row in enumerate(event_turn):
        path = f"source.behavior.eventTurnMachines[{index}]"
        obj = _object(row, path, {"applicability", "behaviorClassification", "behaviorOwner", "behaviorOwnerSourceType", "canonicalEncounter", "canonicalEvent", "canonicalModel", "dependencyRefs", "eventSourceType", "graphId", "initialStateFactRefs", "registrationIds", "titles"})
        encounter = encounter_by_id[obj["canonicalEncounter"]]; link = link_by_id.get(obj["canonicalEncounter"])
        if encounter["possibleMonsters"] != [obj["canonicalModel"]] or link is None or obj["canonicalEvent"] != link["canonicalEvent"] or obj["eventSourceType"] != link["eventSourceType"]:
            _fail(path, "event encounter/model/link join mismatch")
        graph = graph_by_id.get(obj["graphId"])
        if graph is None or graph["canonicalMonster"] != obj["behaviorOwner"] or graph["sourceType"] != obj["behaviorOwnerSourceType"] or obj["canonicalModel"] not in graph["applicableConcreteModels"]:
            _fail(path, "event graph/owner/applicability join mismatch")
        regs = [registration_by_id.get(ref) for ref in obj["registrationIds"]]
        if not regs or any(reg is None or reg["graphId"] != obj["graphId"] or obj["canonicalModel"] not in reg["applicableConcreteModels"] for reg in regs):
            _fail(path + ".registrationIds", "event registration/applicability join mismatch")
        direct = obj["canonicalModel"] == obj["behaviorOwner"]
        if obj["applicability"] != ("direct" if direct else "inherited"):
            _fail(path + ".applicability", "event applicability kind mismatch")
        if obj["behaviorClassification"] not in classifications:
            _fail(path + ".behaviorClassification", "unknown event turn classification")
        dependency_refs = obj["dependencyRefs"]
        if not set(dependency_refs) <= dependency_ids:
            _fail(path + ".dependencyRefs", "unknown event classification dependency")
        incomplete = obj["behaviorClassification"] in {"noOpTurnMachineWithLifecycle", "scriptedNonTurnCombat"}
        if len(dependency_refs) != (1 if incomplete else 0):
            _fail(path + ".dependencyRefs", "event classification dependency cardinality mismatch")
        if obj["behaviorClassification"] == "inheritedTurnMachine" and direct:
            _fail(path, "inherited event graph has no inherited owner edge")
        if obj["behaviorClassification"] == "normalTurnMachine" and not direct:
            _fail(path, "normal event graph silently guessed an inherited owner")
        if incomplete:
            if any(reg["execution"]["kind"] != "synchronousNoOp" or reg["operations"][0].get("transition") != "noOp" for reg in regs):
                _fail(path, "no-op/scripted graph was not source-inspected as an explicit no-op")
            no_op_count += len(regs)
        titles = _list(obj["titles"], path + ".titles")
        if len(titles) != len(regs):
            _fail(path + ".titles", "event title/registration denominator mismatch")
        title_by_state = {item["stateId"]: item["title"] for item in titles}
        expected_root = obj["canonicalModel"].removeprefix("MONSTER.")
        if set(title_by_state) != {reg["stateId"] for reg in regs}:
            _fail(path + ".titles", "event title state join mismatch")
        for title in title_by_state.values():
            if title.get("classification") != "localized" or title.get("localizationRoot") != expected_root:
                _fail(path + ".titles", "event localization root/title join mismatch")
        if direct and obj["canonicalModel"] in event_only_models:
            physical_owners.add(obj["behaviorOwnerSourceType"]); physical_registrations.update(obj["registrationIds"]); physical_title_count += len(titles)
        else:
            reuse_count += 1
    if (len(physical_owners), len(physical_registrations), physical_title_count, no_op_count, reuse_count) != (5, 8, 8, 4, 3):
        _fail("source.behavior.eventTurnMachines", "event physical/reuse/no-op denominator drift")
    event_invocations = source["behavior"].get("eventTurnInvocationCensus", {})
    event_decision_refs = event_invocations.get("decisionRefs", [])
    if (event_invocations.get("summary") != {
            "classificationCounts": {"normalizedGameplayOperation": 6, "provenNonGameplayPlumbing": 76, "traversedGameplayHelper": 21},
            "denominator": 103, "resolved": 103, "unresolved": 0,
        } or len(event_decision_refs) != 103 or len(set(event_decision_refs)) != 103
            or not set(event_decision_refs) <= invocation_ids):
        _fail("source.behavior.eventTurnInvocationCensus", "event helper invocation classification is incomplete")
    expected_event_summary = {
        "classifications": 8, "eventIntentArguments": 5, "eventIntentConstructorSites": 6,
        "eventTurnDirectOperations": 6, "eventTurnOperationsIncludingNoOpProofs": 10,
        "noOpProofs": 4, "physicalOwners": 5, "physicalRegistrations": 8,
        "physicalTitles": 8, "reuseOrInheritanceApplicability": 3,
    }
    if source["behavior"].get("eventTurnSummary") != expected_event_summary:
        _fail("source.behavior.eventTurnSummary", "event turn source denominator drift")

    initial = _object(source.get("initialState"), "source.initialState", {
        "constructorDecisions", "encounterInitializerDecisions", "encounterInitializers", "externalHookBoundary",
        "initialStateFacts", "initialStateOwners", "initializationChain", "invocationDecisions", "powerHookClosure",
        "runtimeStateContracts", "sourceDenominators", "summary",
    })
    roots = _list(initial["encounterInitializers"], "source.initialState.encounterInitializers")
    if len(roots) != 89 or {row.get("canonicalEncounter") for row in roots} != {"ENCOUNTER." + value for value in encounter_ids}:
        _fail("source.initialState.encounterInitializers", "expected all 89 exact generator roots")
    initializer_decisions = _list(initial["encounterInitializerDecisions"], "source.initialState.encounterInitializerDecisions")
    initializer_ids = _unique(initializer_decisions, "decisionId", "source.initialState.encounterInitializerDecisions")
    for index, root in enumerate(roots):
        refs = root.get("constructionDecisionRefs", []) + root.get("rngDecisionRefs", [])
        if not set(refs) <= initializer_ids or not isinstance(root.get("method", {}).get("methodBodySha256"), str):
            _fail(f"source.initialState.encounterInitializers[{index}]", "broken initializer site refs/provenance")
    constructor_decisions = _list(initial["constructorDecisions"], "source.initialState.constructorDecisions")
    if len(constructor_decisions) != 5:
        _fail("source.initialState.constructorDecisions", "expected five explicit constructor writes")
    owners = _list(initial["initialStateOwners"], "source.initialState.initialStateOwners")
    if len(owners) != 108 or {row.get("ownerModel") for row in owners} != current_models:
        _fail("source.initialState.initialStateOwners", "expected all 108 exact reachable owners")
    source_initial_facts = _list(initial["initialStateFacts"], "source.initialState.initialStateFacts")
    if len(source_initial_facts) != 111:
        _fail("source.initialState.initialStateFacts", "expected 111 ordered initial facts")
    source_initial_ids = _unique(source_initial_facts, "factId", "source.initialState.initialStateFacts")
    allowed_effects = {"applyPower", "gainBlock", "setMaxAndCurrentHp", "setCurrentHp", "setState", "subscribe",
                       "relationship", "forceMoveState", "afflictCard", "configurePowerTarget"}
    for index, row in enumerate(source_initial_facts):
        path = f"source.initialState.initialStateFacts[{index}]"
        required = {"applicableModels", "baseValue", "condition", "effect", "factId", "finalValueContract", "order",
                    "ownerModel", "provenance", "recipient", "sourceStateInputs", "stage", "trigger"}
        if not required <= set(row) or set(row) - required - {"encounterApplicability"}:
            _fail(path, "initial fact fields are not closed")
        if row["effect"].get("kind") not in allowed_effects:
            _fail(path + ".effect.kind", "unsupported initial effect")
        base = _object(row["baseValue"], path + ".baseValue", {"expression", "unit", "valueType"})
        validate_expression(base["expression"], path=path + ".baseValue.expression", expected_type=base["valueType"])
        _validate_initial_fact_contract(row, path, current_models)
        proof = row["provenance"]
        for key in ("assemblySha256", "methodBodySha256", "normalizedInstructionsSha256", "normalizedSliceSha256", "semanticWitnessSha256"):
            value = proof.get(key)
            if not isinstance(value, str) or len(value) != 64:
                _fail(path + ".provenance." + key, "missing exact SHA-256 provenance")
    for index, owner in enumerate(owners):
        if owner.get("classification") not in {"orderedGameplayEffects", "sourceProvenNoOp", "sourceProvenNonGameplayOnly"}:
            _fail(f"source.initialState.initialStateOwners[{index}].classification", "unsupported owner classification")
        refs = owner.get("factRefs", [])
        if not set(refs) <= source_initial_ids:
            _fail(f"source.initialState.initialStateOwners[{index}].factRefs", "broken initial fact ref")
        if (owner["classification"] == "orderedGameplayEffects") != bool(refs):
            _fail(f"source.initialState.initialStateOwners[{index}]", "owner effects/classification mismatch")
        if owner.get("effectiveHook", "").startswith("MegaCrit.Sts2.Core.Models.MonsterModel::AfterAddedToRoom") and owner["classification"] != "sourceProvenNoOp":
            _fail(f"source.initialState.initialStateOwners[{index}]", "base no-op was not source-inspected")
    calls = _list(initial["invocationDecisions"], "source.initialState.invocationDecisions")
    if len(calls) != 1092 or len(_unique(calls, "decisionId", "source.initialState.invocationDecisions")) != 1092:
        _fail("source.initialState.invocationDecisions", "closed 1092-call census is incomplete")
    contracts = _list(initial["runtimeStateContracts"], "source.initialState.runtimeStateContracts")
    if len(contracts) != 47:
        _fail("source.initialState.runtimeStateContracts", "expected 47 runtime contracts")
    contract_ids = _unique(contracts, "contractId", "source.initialState.runtimeStateContracts")
    for index, contract in enumerate(contracts):
        if "domain" not in contract or not contract.get("readSites") or not isinstance(contract.get("sourceInputs"), list):
            _fail(f"source.initialState.runtimeStateContracts[{index}]", "runtime domain/read site/source-input inventory missing")
        for source_input in contract["sourceInputs"]:
            if set(source_input) != {"sourceMember", "unit", "valueType"} or not source_input["sourceMember"]:
                _fail(f"source.initialState.runtimeStateContracts[{index}].sourceInputs", "malformed source input")
        for site in contract.get("updateSites", []):
            if "factRef" in site and site["factRef"] not in source_initial_ids:
                _fail(f"source.initialState.runtimeStateContracts[{index}].updateSites", "broken fact update ref")
    for index, fact in enumerate(source_initial_facts):
        refs = set(fact["sourceStateInputs"]) | set(fact["finalValueContract"]["runtimeModifierInputs"])
        if not refs <= contract_ids:
            _fail(f"source.initialState.initialStateFacts[{index}]", "unregistered runtime input")
        required_state_contracts = {
            "combat.currentSide": "RUNTIME.COMBAT.CURRENT_SIDE",
            "initial.decimillipedeSharedMaxHp": "RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP",
            "initial.toughEggHatchHp": "RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP",
        }
        names = _initial_state_variable_names(fact["baseValue"]["expression"])
        if not names <= set(required_state_contracts) or not {required_state_contracts[name] for name in names} <= set(fact["sourceStateInputs"]):
            _fail(f"source.initialState.initialStateFacts[{index}]", "unregistered source field")
    hooks = _list(initial["powerHookClosure"], "source.initialState.powerHookClosure")
    if len(hooks) != 41:
        _fail("source.initialState.powerHookClosure", "expected 41 initially reachable Powers")
    for index, row in enumerate(hooks):
        if len(row.get("hooks", [])) != 3:
            _fail(f"source.initialState.powerHookClosure[{index}]", "apply/start hook family omitted")
        for hook in row["hooks"]:
            if not set(hook.get("effectFactRefs", [])) <= source_initial_ids:
                _fail(f"source.initialState.powerHookClosure[{index}]", "broken Power hook fact ref")
    if len(initial["initializationChain"]) != 7 or sum(len(row["declarations"]) for row in initial["externalHookBoundary"]) != 29:
        _fail("source.initialState", "initialization chain/external boundary denominator drift")
    expected_initial_denominators = {
        "constructorExplicitWrites": 5, "constructorOwners": 4,
        "directSinkSitesByKind": {"applyPower": 54, "gainBlock": 1, "setCurrentHp": 1, "setMaxAndCurrentHp": 1},
        "effectiveHookImplementations": 59, "encounterGenerationOwners": 89,
        "generatorConstructionSites": 137, "generatorRngSites": 38, "generatorSetterOwners": 13,
        "generatorSetterSites": 25, "initialStateModels": 108, "nonRosterInitializationRngRoots": 5,
        "powerModels": 41,
    }
    if initial["sourceDenominators"] != expected_initial_denominators:
        _fail("source.initialState.sourceDenominators", "initial-state source denominator drift")
    expected_summary = {"encounterRoots": 89, "facts": 111, "invocationDecisions": 1092,
                        "modelOwners": 108, "powerModels": 41, "runtimeContracts": 47}
    if initial["summary"] != expected_summary:
        _fail("source.initialState.summary", "initial-state summary drift")

_EXPR_KINDS = {
    "actRoomFactor", "arithmetic", "ascensionSelect", "combatQuery", "compare",
    "conditional", "constant", "convert", "range", "reference", "round",
    "sourceField", "stateVariable",
}
_SHA_KEYS = {"methodBodySha256", "normalizedSliceSha256"}


def _walk_expressions(value: Any, path: str) -> None:
    if isinstance(value, dict):
        if value.get("kind") in _EXPR_KINDS:
            validate_expression(value, path=path)
            return
        for key, child in value.items():
            _walk_expressions(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_expressions(child, f"{path}[{index}]")


def _dummy_proof() -> dict[str, Any]:
    return {
        "assemblySha256": "0" * 64, "cilInstructionsSha256": "0" * 64,
        "metadataSignature": "00", "methodBodySha256": "0" * 64,
        "normalizedInstructionsSha256": "0" * 64, "normalizedSliceSha256": "0" * 64,
        "semanticWitnessSha256": "0" * 64, "symbolSignature": "Projection::Evidence sig:00",
    }


def _validate_projected_operation(value: Any, path: str) -> None:
    if not isinstance(value, dict):
        _fail(path, "operation must be an object")
    if value.get("kind") not in OPERATION_KINDS:
        _fail(path + ".kind", f"unsupported operation kind {value.get('kind')!r}")
    hydrated = deepcopy(value)
    hydrated["provenance"] = _dummy_proof()
    if hydrated["kind"] == "attack":
        hydrated["targetProvenance"] = _dummy_proof()
    validate_operation(hydrated, path=path)


def _validate_intent(value: Any, path: str) -> None:
    obj = _object(value, path, {"arguments", "constructorSymbolSignature", "intentClass", "kind"})
    if obj["kind"] not in INTENT_KINDS:
        _fail(path + ".kind", f"unsupported intent kind {obj['kind']!r}")
    _string(obj["constructorSymbolSignature"], path + ".constructorSymbolSignature")
    _string(obj["intentClass"], path + ".intentClass")
    for index, argument in enumerate(_list(obj["arguments"], path + ".arguments")):
        apath = f"{path}.arguments[{index}]"
        if isinstance(argument, dict) and argument.get("kind") == "sourceDelegate":
            delegate = _object(argument, apath, {"binding", "constructorSymbolSignature", "kind", "resultExpression", "targetMethod"})
            binding = _object(delegate["binding"], apath + ".binding", {"argumentIndex", "kind"})
            if binding["kind"] != "methodArgument":
                _fail(apath + ".binding.kind", "unsupported delegate binding")
            _integer(binding["argumentIndex"], apath + ".binding.argumentIndex")
            _string(delegate["constructorSymbolSignature"], apath + ".constructorSymbolSignature")
            validate_expression(delegate["resultExpression"], path=apath + ".resultExpression")
            method = _object(delegate["targetMethod"], apath + ".targetMethod", {"methodBodySha256", "normalizedSliceSha256", "symbolSignature"})
            for key in _SHA_KEYS:
                if not isinstance(method[key], str) or len(method[key]) != 64 or any(c not in "0123456789abcdef" for c in method[key]):
                    _fail(apath + f".targetMethod.{key}", "must be SHA-256")
            _string(method["symbolSignature"], apath + ".targetMethod.symbolSignature")
        else:
            validate_expression(argument, path=apath)


def _validate_title(value: Any, path: str) -> None:
    obj = _object(
        value, path,
        {"aliasKind", "classification", "english", "localizationKey", "localizationRoot", "requestedLocalizationKey"},
        {"classification", "localizationKey", "localizationRoot", "requestedLocalizationKey"},
    )
    if obj["classification"] not in {"localized", "missingLocalization"}:
        _fail(path + ".classification", "unsupported move title classification")
    if obj["classification"] == "localized":
        _string(obj.get("english"), path + ".english")
    elif "english" in obj or "aliasKind" in obj:
        _fail(path, "missing/internal title cannot carry a selected fallback")
    for key in ("localizationKey", "localizationRoot", "requestedLocalizationKey"):
        _string(obj[key], path + f".{key}")



def _validate_compact_architect(value: Any, placement_fact_ids: set[str]) -> set[str]:
    path="payload.sourceFacts.eventScripts.architect"
    required={"applicability","dependencies","dialogue","initialState","lineControl","localization","placement",
              "presentation","roomEntry","runtimeContracts","semanticEffects","sourceDenominators","terminal","visualOnlyCombat"}
    architect=_object(value,path,required)
    forbidden_nested={"decisions","instructions"}
    if {"methods","invocationCensus"} & set(architect):
        _fail(path,"Architect method/call proof bulk leaked into compact projection")
    fact_ids=[]
    def walk(node:Any,current:str)->None:
        if isinstance(node,dict):
            if forbidden_nested & set(node):_fail(current,"Architect method/call proof bulk leaked into compact projection")
            if "factId" in node:fact_ids.append(_string(node["factId"],current+".factId",prefix="SOURCE.ARCHITECT."))
            for key,child in node.items():
                if key in {"value","text","prose","template"}:_fail(current+"."+key,"localized dialogue prose was copied")
                walk(child,current+"."+str(key))
        elif isinstance(node,list):
            for index,child in enumerate(node):walk(child,f"{current}[{index}]")
    walk(architect,path)
    if len(fact_ids)!=len(set(fact_ids)):_fail(path,"duplicate Architect fact identity")

    applicability=architect["applicability"]
    if applicability.get("canonicalEvent")!="EVENT.THE_ARCHITECT" or applicability.get("canonicalEncounter")!="ENCOUNTER.THE_ARCHITECT_EVENT_ENCOUNTER":
        _fail(path+".applicability","Architect owner/encounter identity changed")
    if applicability.get("e1EventLinkRef") not in placement_fact_ids or applicability.get("ownerMultiplicity")!="perMutablePlayerEventInstance":
        _fail(path+".applicability","Architect E1 link/applicability is broken")

    den=architect["sourceDenominators"]
    expected_den={"dependencies":5,"edges":39,"invocations":715,"lines":39,"localizationKeys":64,
                  "methods":96,"nodes":39,"options":2,"presentationMethods":13,
                  "runtimeContracts":8,"semanticEffects":6,"templates":17}
    if den!=expected_den:_fail(path+".sourceDenominators","source-discovered Architect denominator drift")

    dialogue=architect["dialogue"]
    selection=dialogue.get("selection",{})
    if selection.get("agnosticCandidatesIncluded") is not False or selection.get("candidateOrder")!=[
        "exactNullableVisitEqualsCharacterWins","repeatingVisitAtMostCharacterWinsWhenNoExact"]:
        _fail(path+".dialogue.selection","exact/repeating selection order or agnostic flag changed")
    if selection.get("characterWinsInput")!="progress.characterStats.totalWinsOrZeroWhenMissing" or selection.get("globalProgressInput")!="progress.wins" or "event.rng.nextItem" not in str(selection.get("rngInput")):
        _fail(path+".dialogue.selection","runtime wins/progress/RNG input was lost")
    if selection.get("concreteTemplate")!={"kind":"runtimeSelection","valueType":"AncientDialogue"}:
        _fail(path+".dialogue.selection","dynamic template selection was collapsed")
    templates=_list(dialogue.get("templates"),path+".dialogue.templates")
    if len(templates)!=den["templates"]:_fail(path+".dialogue.templates","template census mismatch")
    template_ids=set();line_ids=set();speakers=set();attackers=set();line_count=0;next_count=0
    for ti,template in enumerate(templates):
        tp=f"{path}.dialogue.templates[{ti}]"
        expected_template_fields={"characterKey","characterOrder","characterSourceType","endAttackers","factId","lineCount","lines","repeating","sourceOrder","startAttackers","templateId","visitIndex"}
        if set(template)!=expected_template_fields:_fail(tp,"template contains missing/unknown fields or copied prose")
        tid=_string(template.get("templateId"),tp+".templateId",prefix="ARCHITECT_DIALOGUE.")
        if tid in template_ids:_fail(tp+".templateId","duplicate template")
        template_ids.add(tid);attackers|={template.get("startAttackers"),template.get("endAttackers")}
        if template.get("startAttackers") not in {"None","Player","Architect","Both"} or template.get("endAttackers") not in {"None","Player","Architect","Both"}:
            _fail(tp,"unknown attacker enum")
        lines=_list(template.get("lines"),tp+".lines")
        if len(lines)!=template.get("lineCount") or [row.get("index") for row in lines]!=list(range(len(lines))):
            _fail(tp+".lines","line count/order mismatch")
        if type(template.get("repeating")) is not bool:_fail(tp+".repeating","repetition selector is not Boolean")
        for li,line in enumerate(lines):
            lp=f"{tp}.lines[{li}]";has_next="nextButtonLocalization" in line
            expected_line_fields={"factId","index","lineId","lineLocalization","speaker"}|({"nextButtonLocalization"} if has_next else set())
            if set(line)!=expected_line_fields:_fail(lp,"line contains missing/unknown fields or copied prose")
            lid=_string(line.get("lineId"),lp+".lineId",prefix=tid+".LINE.")
            if lid in line_ids:_fail(lp+".lineId","duplicate line")
            line_ids.add(lid);speakers.add(line.get("speaker"));line_count+=1
            loc=line.get("lineLocalization",{})
            if set(loc)!={"key","keyValueWitnessSha256","valueSha256"} or not str(loc.get("key","")).startswith("THE_ARCHITECT.talk."):
                _fail(lp+".lineLocalization","line key/digest provenance malformed")
            if has_next!=(li<len(lines)-1):_fail(lp,"continuation/terminal key order mismatch")
            if has_next:
                nxt=line["nextButtonLocalization"];next_count+=1
                if set(nxt)!={"key","keyValueWitnessSha256","valueSha256"} or not str(nxt.get("key","")).endswith(".next"):
                    _fail(lp+".nextButtonLocalization","button key/digest provenance malformed")
    if line_count!=den["lines"] or next_count!=22 or speakers!={"Ancient","Character"}:
        _fail(path+".dialogue.templates","line/continuation/speaker closure mismatch")
    if attackers!={"None","Player","Architect","Both"}:
        _fail(path+".dialogue.templates","all source-discovered attacker variants are not represented")

    localization=architect["localization"]
    witnesses=_list(localization.get("keyValueWitnesses"),path+".localization.keyValueWitnesses")
    if localization.get("proseEmitted") is not False or localization.get("table")!="ancients" or len(witnesses)!=den["localizationKeys"]:
        _fail(path+".localization","structural localization boundary/count changed")
    witness_keys=[]
    for wi,row in enumerate(witnesses):
        if set(row)!={"key","keyValueWitnessSha256","valueSha256"}:_fail(f"{path}.localization.keyValueWitnesses[{wi}]","malformed key/value digest")
        witness_keys.append(row.get("key"))
    if len(witness_keys)!=len(set(witness_keys)) or localization.get("semanticWitnessSha256")!=witness_sha256(witnesses):
        _fail(path+".localization","duplicate/bad localization refs/digests")
    witness_by_key={row["key"]:row for row in witnesses}
    selected_refs=[]
    for template in templates:
        for line in template["lines"]:
            selected_refs.append(line["lineLocalization"])
            if "nextButtonLocalization" in line:selected_refs.append(line["nextButtonLocalization"])
    selected_refs.extend(localization.get("controlKeys",[]))
    if {row.get("key") for row in selected_refs}!=set(witness_keys) or any(witness_by_key.get(row.get("key"))!=row for row in selected_refs):
        _fail(path+".localization","line/button/control refs do not join selected key/value digests")
    provenance=localization.get("provenance",{})
    if provenance.get("pckPath")!="localization/eng/ancients.json" or provenance.get("pckSha256")!=EMBEDDED_SOURCE_INPUTS[0]["sha256"] or provenance.get("entrySha256")!="cd0d1c321f5c42db844b22178abf88297ba3942d557402537bef7437c9c41593":
        _fail(path+".localization.provenance","selected PCK entry/path/hash mismatch")

    options=_list(architect["initialState"].get("options"),path+".initialState.options")
    targets=set()
    for oi,row in enumerate(options):
        callback=row.get("callback",{});targets.add(callback.get("target"))
        if callback.get("receiver")!="eventInstance" or not callback.get("signature"):_fail(f"{path}.initialState.options[{oi}]","delegate receiver/signature ambiguity")
    if targets!={"MegaCrit.Sts2.Core.Models.Events.TheArchitect::AdvanceDialogue sig:2000128121",
                 "MegaCrit.Sts2.Core.Models.Events.TheArchitect::WinRun sig:2000128121"}:
        _fail(path+".initialState.options","option target closure changed")
    if architect["initialState"].get("lineIndexInitialization")!=0 or architect["initialState"].get("missingOrEmptyDialogueBranch")!="createProceedOption":
        _fail(path+".initialState","line-zero/missing-dialogue branch changed")

    control=architect["lineControl"];nodes=_list(control.get("nodes"),path+".lineControl.nodes");edges=_list(control.get("edges"),path+".lineControl.edges")
    node_ids={row.get("nodeId") for row in nodes}
    if len(nodes)!=den["nodes"] or node_ids!=line_ids or len(edges)!=den["edges"] or {row.get("from") for row in edges}!=line_ids:
        _fail(path+".lineControl","line node/edge graph closure mismatch")
    for edge in edges:
        if edge.get("kind")=="continuation" and edge.get("to") not in node_ids:_fail(path+".lineControl.edges","continuation endpoint missing")
        if edge.get("kind")=="terminalProceed" and edge.get("to")!="ARCHITECT_NODE.TERMINAL_PROCEED":_fail(path+".lineControl.edges","terminal endpoint changed")
        if edge.get("kind") not in {"continuation","terminalProceed"}:_fail(path+".lineControl.edges","unknown edge kind")
    if control.get("asyncExceptionSemantics")!="SetExceptionNotSuccess" or "missingSpeakerEntityEarlyReturn" not in control.get("branches",[]):
        _fail(path+".lineControl","failure/exception branch closure incomplete")

    visual=architect["visualOnlyCombat"]
    if visual.get("roomMode")!="VisualOnly" or visual.get("roomModeValue")!=2 or visual.get("classification")!="notActiveCombat" or visual.get("hiddenTurnFactRole")!="referencedNoOpTurnFactNotScriptCompleteness":
        _fail(path+".visualOnlyCombat","active-combat or hidden-no-op sufficiency was claimed")
    score=architect["roomEntry"].get("scoreReference",{})
    if score.get("arguments")!=["event.owner.runState",True] or score.get("formulaRef")!="FORMULA.SCORE_UTILITY.CALCULATE_SCORE" or "sig:00020812841c02" not in score.get("symbolSignature",""):
        _fail(path+".roomEntry.scoreReference","wrong score overload/argument")
    presentation=architect["presentation"]
    if presentation.get("completeSliceHasGameplayDamage") is not False or presentation.get("apparentDamageClassification")!="damageNumberVfxNotHpDamage" or presentation.get("scoreSplit",{}).get("renderDeterministically") is not False:
        _fail(path+".presentation","real/apparent damage or score split classification changed")
    terminal=architect["terminal"]
    if terminal.get("orderedControl")!=["animatePlayerEndAttackers","animateArchitectEndAttackers","localOwnerRunManagerWinRun","awaitWinRun","setEmptyOptionsFinishedState"] or terminal.get("localOwnerGuarded") is not True:
        _fail(path+".terminal","WinRun order/local-owner branch changed")
    if terminal.get("eventCombatTransition") is not False or terminal.get("noResume") is not True or terminal.get("noRewardPage") is not True or terminal.get("finishedState")!="emptyOptionCollection":
        _fail(path+".terminal","reward/resume/active-combat claim introduced")
    if terminal.get("cleanupBoundary") != {"classification":"commonEventFrameworkIfExitReached","frameworkRole":"EnsureCleanup"}:
        _fail(path+".terminal.cleanupBoundary","common cleanup boundary changed")
    boundary=terminal.get("runManagerBoundary",{})
    if boundary.get("onEndedArgument") is not True or boundary.get("order")!=["OnEnded(true)","GuaranteeKillAllPlayers"] or boundary.get("missingRunState")!="returnWithoutOnEndedOrForcedKills":
        _fail(path+".terminal.runManagerBoundary","lifecycle dependency argument/order changed")

    dependencies=_list(architect["dependencies"],path+".dependencies")
    dependency_ids={row.get("dependencyId") for row in dependencies}
    if dependency_ids!={"FORMULA.SCORE_UTILITY.CALCULATE_SCORE","LIFECYCLE.RUN.ON_ENDED_TRUE",
                        "LIFECYCLE.RUN.GUARANTEE_KILL_ALL_PLAYERS","LIFECYCLE.RUN.SERIALIZED_SCORE_STATS_HISTORY",
                        "LIFECYCLE.RUN.ARCHITECT_TERMINAL_ORDER"}:
        _fail(path+".dependencies","score/formula/lifecycle dependency refs incomplete")
    contracts=_list(architect["runtimeContracts"],path+".runtimeContracts")
    if len(contracts)!=den["runtimeContracts"] or len({row.get("name") for row in contracts})!=len(contracts):_fail(path+".runtimeContracts","state/runtime contract closure mismatch")
    effects=_list(architect["semanticEffects"],path+".semanticEffects")
    if len(effects)!=den["semanticEffects"] or len({row.get("effectId") for row in effects})!=len(effects):_fail(path+".semanticEffects","semantic effect closure mismatch")
    if any(row.get("kind") in {"damage","attack","kill"} for row in effects):_fail(path+".semanticEffects","forced kill/dialogue VFX represented as dialogue damage")
    return set(fact_ids)

def _validate_compact_lifecycle(value: Any, source: dict[str, Any]) -> set[str]:
    path="payload.sourceFacts.lifecycle"
    obj=_object(value,path,{"api","combatTermination","componentId","core","dependencies","digests","dispatch","factId","listenerRegistry","methodRefs","removal","runtimeBoundaries","runtimeStateContracts","sourceDenominators","status","listenerCensus","mechanics","semanticPipelineAudit","closeoutDigests"})
    if obj["componentId"]!="LIFECYCLE.CORE.E2D2A" or obj["status"]!="sourceCompleteE2Lifecycle" or obj["factId"]!="SOURCE.LIFECYCLE.CORE.E2D2A":
        _fail(path,"core lifecycle identity/status/fact changed")
    text=repr(obj)
    if "playDeathEffects" in text:_fail(path,"legacy kill Boolean field is forbidden")
    if "CombatResult" in text:_fail(path,"invented combat result enum is forbidden")
    forbidden_proof_keys = {"diagnosticMetadataToken", "cilInstructionsSha256", "methodBodySha256",
                            "commandCallSites", "invocationCensus", "instructions", "instructionOrigins"}
    def proof_keys(node: Any) -> set[str]:
        if isinstance(node, dict):
            return (set(node) & forbidden_proof_keys) | set().union(
                *(proof_keys(child) for child in node.values()), set())
        if isinstance(node, list):
            return set().union(*(proof_keys(child) for child in node), set())
        return set()
    if proof_keys(obj):
        _fail(path,"raw lifecycle call/proof bulk leaked into compact projection")
    api=_object(obj["api"],path+".api",{"commandDeclarations"})
    commands=_list(api["commandDeclarations"],path+".api.commandDeclarations")
    expected_params=[["creature","force"],["creatures","force"],["creature","force","recursion"],["creature","removeCreatureNode"]]
    if len(commands)!=4 or [row.get("parameters") for row in commands]!=expected_params:
        _fail(path+".api.commandDeclarations","exact force/removeCreatureNode declarations changed")
    for index,row in enumerate(commands):
        _object(row,f"{path}.api.commandDeclarations[{index}]",{"parameters","physicalSymbolSignature","symbolSignature"})
        if " sig:" not in row["symbolSignature"] or " sig:" not in row["physicalSymbolSignature"]:_fail(path+".api","method signature ref is not exact")
    refs=_object(obj["methodRefs"],path+".methodRefs",{"actionExecutor","commands","dispatch","listenerRegistries","removal","termination"})
    if refs["commands"]!=commands or [len(refs[k]) for k in ("dispatch","listenerRegistries","removal","termination")]!=[6,3,3,7]:
        _fail(path+".methodRefs","compact method closure denominators changed")
    if "ActionExecutor+<ExecuteActions>" not in refs["actionExecutor"]:_fail(path+".methodRefs.actionExecutor","action executor physical ref changed")
    den=obj["sourceDenominators"]
    expected={"commandDeclarations":4,"commandPhysicalBodies":4,"killCallSites":21,"escapeCallSites":3,"dispatchMethods":6,
              "listenerRegistryLogicalMethods":3,"listenerRegistryPhysicalBodies":3,"removalMethods":4,
              "terminationDeclarations":4,"terminationPhysicalBodies":4,"terminationSupportMethods":3,
              "centralizedCheckCallSites":14,"runtimeBoundaries":7,"dependencies":7,"invocations":707,"semanticNodes":59,
              "closeout.beforeRemovedCleanup":11,"closeout.deathAddPhysicalSites":4,"closeout.deathProductionSystems":3,
              "closeout.effectiveListenerApplications":1861,"closeout.eventCombatRegistrations":7,
              "closeout.fixedPointPowerTypes":71,"closeout.invocationDecisions":1265,"closeout.listenerImplementations":80,
              "closeout.monsterOwnerTypes":108,"closeout.phaseSystems":6,"closeout.powerSeedTypes":69,
              "closeout.relationships":6,"closeout.runTerminationSystems":1,"closeout.subscriptions":3}
    if den!=expected:_fail(path+".sourceDenominators","closed lifecycle denominator drift")
    census=_object(obj["listenerCensus"],path+".listenerCensus",{"effectiveApplications","fixedPointPowerTypes","implementationRecords","monsterOwnerTypes","postDiscoveryAssertions","powerSeedTypes"})
    if (census["effectiveApplications"],census["fixedPointPowerTypes"],census["implementationRecords"],census["monsterOwnerTypes"],census["powerSeedTypes"])!=(1861,71,80,108,69):
        _fail(path+".listenerCensus","fixed-point listener census changed")
    mechanics=_object(obj["mechanics"],path+".mechanics",{"cleanup","deathProduction","doom","eventCombat","phaseSystems","powerRetentionPolicies","relationships","runTermination","subscriptions"})
    if [len(mechanics[key]) for key in ("cleanup","deathProduction","phaseSystems","powerRetentionPolicies","relationships","subscriptions")] != [11,3,6,18,6,3]:
        _fail(path+".mechanics","compact lifecycle mechanics cardinality changed")
    if len(mechanics["eventCombat"].get("registrations",[]))!=7:
        _fail(path+".mechanics.eventCombat","event combat registration closure changed")
    audit=_object(obj["semanticPipelineAudit"],path+".semanticPipelineAudit",{"coreDeathEvaluatorRef","duplicateDeathEvaluator","coreAddRef","duplicateAddEvaluator","hpAssignmentRef","duplicateHpEvaluator","eventEffectsRef","eventEffectsCopied"})
    if any(audit[key] is not False for key in ("duplicateDeathEvaluator","duplicateAddEvaluator","duplicateHpEvaluator","eventEffectsCopied")):
        _fail(path+".semanticPipelineAudit","duplicate semantic pipeline")
    core=_object(obj["core"],path+".core",{"emptyBehavior","innerDeathGraph","listKillGraph","listSnapshotOrder","singularKillContract"})
    inner=core["innerDeathGraph"]
    if (inner.get("directCheckWinCondition") is not False or inner.get("deadBodyEntryShortCircuit") is not False
            or inner.get("forceContract") != 'entry guards complete regardless of force; after they pass, force bypasses only out-of-combat multiplayer player safety healing and ShouldDie/prevention; HP zeroing, BeforeDeath, Died, animation, AfterDeath, removal, Power cleanup, and player cleanup remain'):
        _fail(path+".core.innerDeathGraph","force/entry-guard/dead-body/direct-win boundary changed")
    if len(core["listKillGraph"].get("nodes",[]))!=10 or len(inner.get("nodes",[]))!=23:
        _fail(path+".core","kill graph node closure changed")
    list_edges={row.get("edgeId"):(row.get("from"),row.get("to"),row.get("kind")) for row in core["listKillGraph"].get("edges",[])}
    expected_list_edges={
        "LIFECYCLE.KILL.LIST.EDGE.INNER_SUCCEEDED":("LIFECYCLE.KILL.LIST.03.sequentialInner","LIFECYCLE.KILL.LIST.04.managerGuard","awaitSuccess"),
        "LIFECYCLE.KILL.LIST.EDGE.INNER_FAILED":("LIFECYCLE.KILL.LIST.03.sequentialInner","LIFECYCLE.KILL.LIST.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation"),
        "LIFECYCLE.KILL.LIST.EDGE.LIVE_COMBAT_LOSS":("LIFECYCLE.KILL.LIST.05.allPlayersDead","LIFECYCLE.KILL.LIST.06.liveCombatLoss","conditionTrue"),
        "LIFECYCLE.KILL.LIST.EDGE.NON_LIVE_ALL_DEAD":("LIFECYCLE.KILL.LIST.05.allPlayersDead","LIFECYCLE.KILL.LIST.07.testModeGate","conditionTrue"),
        "LIFECYCLE.KILL.LIST.EDGE.LOSS_FALLTHROUGH":("LIFECYCLE.KILL.LIST.06.liveCombatLoss","LIFECYCLE.KILL.LIST.07.testModeGate","sourceOrder"),
        "LIFECYCLE.KILL.LIST.EDGE.TEST_OFF":("LIFECYCLE.KILL.LIST.07.testModeGate","LIFECYCLE.KILL.LIST.08.gameOver","conditionTrue"),
        "LIFECYCLE.KILL.LIST.EDGE.TEST_ON":("LIFECYCLE.KILL.LIST.07.testModeGate","LIFECYCLE.KILL.LIST.OUTCOME.TEST_MODE_SKIPPED","conditionFalse"),
        "LIFECYCLE.KILL.LIST.EDGE.GAME_OVER":("LIFECYCLE.KILL.LIST.08.gameOver","LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER","sourceOrder"),
    }
    if any(list_edges.get(edge_id)!=contract for edge_id,contract in expected_list_edges.items()):
        _fail(path+".core.listKillGraph","loss/test-mode fallthrough or awaited inner kill changed")
    inner_edges={row.get("edgeId"):(row.get("from"),row.get("to"),row.get("kind")) for row in inner.get("edges",[])}
    expected_guard_edges={
        "LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED":("LIFECYCLE.KILL.INNER.01.entryGuards","LIFECYCLE.KILL.INNER.OUTCOME.DETACHED_NON_PLAYER_COMPLETED","conditionTrue"),
        "LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED":("LIFECYCLE.KILL.INNER.01.entryGuards","LIFECYCLE.KILL.INNER.OUTCOME.ATTACHED_NON_LIVE_COMPLETED","conditionTrue"),
        "LIFECYCLE.KILL.INNER.EDGE.GUARDS_PASSED":("LIFECYCLE.KILL.INNER.01.entryGuards","LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","guardsPassed"),
        "LIFECYCLE.KILL.INNER.EDGE.SAFETY_RETURN":("LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","LIFECYCLE.KILL.INNER.OUTCOME.SAFETY_HEALED","awaitSuccess"),
        "LIFECYCLE.KILL.INNER.EDGE.FAIL.02":("LIFECYCLE.KILL.INNER.02.outOfCombatPlayerSafety","LIFECYCLE.KILL.INNER.22.awaiterFailure","faultOrCancellation"),
    }
    if any(inner_edges.get(edge_id)!=contract for edge_id,contract in expected_guard_edges.items()):
        _fail(path+".core.innerDeathGraph","completed entry guards or safety Heal success/failure changed")
    dispatch=obj["dispatch"]
    if dispatch.get("awaitedDispatch",{}).get("parallelism")!="none" or "one listener task at a time" not in dispatch.get("awaitedDispatch",{}).get("execution",""):
        _fail(path+".dispatch","ordered awaited dispatch was parallelized")
    removal=obj["removal"]
    if removal.get("escapeDeathHooks")!=[] or removal.get("escapeResultEnum") is not None or len(removal.get("escapeGraph",{}).get("nodes",[]))!=8:
        _fail(path+".removal","escape death/result/node contract changed")
    termination=obj["combatTermination"]
    if termination.get("killDirectWinCheck") is not False or termination.get("resultEnum") is not None:
        _fail(path+".combatTermination","Kill win check or result enum invented")
    victory=termination.get("victoryGraph",{})
    if len(victory.get("nodes",[]))!=13:_fail(path+".combatTermination.victoryGraph","victory graph node closure changed")
    victory_edges={row.get("edgeId"):(row.get("from"),row.get("to"),row.get("kind")) for row in victory.get("edges",[])}
    if victory_edges.get("LIFECYCLE.COMBAT.VICTORY.EDGE.02")!=("LIFECYCLE.COMBAT.VICTORY.02.revivePlayers","LIFECYCLE.COMBAT.VICTORY.03.afterCombatEnd","awaitSuccess") or victory_edges.get("LIFECYCLE.COMBAT.VICTORY.EDGE.REVIVE_FAIL")!=("LIFECYCLE.COMBAT.VICTORY.02.revivePlayers","LIFECYCLE.COMBAT.VICTORY.OUTCOME.FAULT_OR_CANCEL","faultOrCancellation"):
        _fail(path+".combatTermination.victoryGraph","player revive success/failure changed")
    if termination.get("victoryPredicate",{}).get("secondaryOnlyEnemiesBlock") is not False or termination.get("victoryPredicate",{}).get("allEscaped")!="ordinary victory at the next centralized check":
        _fail(path+".combatTermination.victoryPredicate","secondary/all-escape result semantics changed")
    edges=termination.get("actionExecutorEdges",[])
    if len(edges)!=4 or {row.get("edgeId") for row in edges}!={"LIFECYCLE.ACTION.NORMAL","LIFECYCLE.ACTION.LOGGED_FAULT","LIFECYCLE.ACTION.CANCEL","LIFECYCLE.AWAIT.FAILURE"}:
        _fail(path+".combatTermination.actionExecutorEdges","normal/fault/cancel/await-failure edge closure changed")
    boundaries=_list(obj["runtimeBoundaries"],path+".runtimeBoundaries")
    if len(boundaries)!=7 or any(row.get("classification")!="vanillaExternalRunOrPlayerListener" or row.get("effectStatus")!="runtimeDynamicExternalBoundary" for row in boundaries):
        _fail(path+".runtimeBoundaries","vanilla dynamic runtime boundaries were omitted or assumed empty")
    deps=_list(obj["dependencies"],path+".dependencies");dep_ids=set();fact_ids={obj["factId"]}
    if len(deps)!=7:_fail(path+".dependencies","dependency closure changed")
    for index,row in enumerate(deps):
        dep=_object(row,f"{path}.dependencies[{index}]",{"dependencyId","factId","kind","status","resolvedComponentRef"}, {"dependencyId","factId","kind","status"})
        expected_fact="SOURCE."+dep["dependencyId"]
        if dep["factId"]!=expected_fact or dep["factId"] in fact_ids:_fail(path+".dependencies","dependency fact ID mismatch/duplicate")
        dep_ids.add(dep["dependencyId"]);fact_ids.add(dep["factId"])
    if {row["status"] for row in deps}!={"sourceComplete"} or any(not row.get("resolvedComponentRef") for row in deps):
        _fail(path+".dependencies","lifecycle dependency closure is incomplete")
    if obj["digests"]!=source["lifecycle"]["digests"]:_fail(path+".digests","source lifecycle digest join mismatch")
    for key in ("core","dispatch","listenerRegistry","removal","combatTermination","runtimeStateContracts","sourceDenominators"):
        if obj[key]!=source["lifecycle"][key]:_fail(path+"."+key,"source lifecycle semantic join mismatch")
    expected_dependencies=[{"factId":"SOURCE."+row["dependencyId"],**row} for row in source["lifecycle"]["dependencies"]]
    if deps!=expected_dependencies:_fail(path+".dependencies","source lifecycle dependency join mismatch")
    expected_boundaries=[{"boundaryId":row["boundaryId"],"classification":row["classification"],"effectStatus":row["effectStatus"],
                          "sourceType":row["sourceType"],"symbolSignature":row["method"]["symbolSignature"]}
                         for row in source["lifecycle"]["runtimeBoundaries"]]
    if boundaries!=expected_boundaries:_fail(path+".runtimeBoundaries","source lifecycle runtime-boundary join mismatch")
    if len(obj["runtimeStateContracts"])!=16:_fail(path+".runtimeStateContracts","runtime state contract closure changed")
    return fact_ids


def _validate_source_facts(source_facts: Any, source: dict[str, Any]) -> dict[str, set[str]]:
    sf = _object(source_facts, "payload.sourceFacts", SOURCE_FACT_KEYS)
    encounter_groups = _object(sf["encounters"], "payload.sourceFacts.encounters", {"event", "ordinary"})
    if len(encounter_groups["ordinary"]) != 81 or len(encounter_groups["event"]) != 8:
        _fail("payload.sourceFacts.encounters", "expected exactly 81 ordinary and 8 event records")
    monster_rows = _list(sf["monsters"], "payload.sourceFacts.monsters")
    if len(monster_rows) != 108:
        _fail("payload.sourceFacts.monsters", "expected 108 current reachable models")
    monster_fact_ids: set[str] = set()
    model_ids: set[str] = set()
    for index, row in enumerate(monster_rows):
        path = f"payload.sourceFacts.monsters[{index}]"
        obj = _object(row, path, {"canonicalId", "canonicalModel", "factId", "initialHp", "name", "reachability", "sourceType"})
        model = _string(obj["canonicalModel"], path + ".canonicalModel", prefix="MONSTER.")
        if model != f"MONSTER.{obj['canonicalId']}":
            _fail(path + ".canonicalModel", "canonical model/id mismatch")
        if model in model_ids:
            _fail(path + ".canonicalModel", "duplicate monster model")
        model_ids.add(model)
        monster_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE.MONSTER."))
        hp = _object(obj["initialHp"], path + ".initialHp", {"a8SinglePlayer", "expression"})
        _object(hp["a8SinglePlayer"], path + ".initialHp.a8SinglePlayer", {"maximum", "minimum"})
        validate_expression(hp["expression"], path=path + ".initialHp.expression", expected_type="integerRange")
        _validate_name(obj["name"], path + ".name")
        if obj["reachability"] not in {"ordinaryReachable", "eventOnly"}:
            _fail(path + ".reachability", "not a current reachability class")

    encounter_fact_ids: set[str] = set()
    for kind in ("ordinary", "event"):
        for index, row in enumerate(_list(encounter_groups[kind], f"payload.sourceFacts.encounters.{kind}")):
            path = f"payload.sourceFacts.encounters.{kind}[{index}]"
            obj = _object(row, path, {
                "canonicalId", "factId", "initialRoster", "kind", "nonRosterInitializationRng",
                "possibleMonsters", "producedMonsters", "productionPools", "sourceType", "title",
            })
            if obj["kind"] != kind:
                _fail(path + ".kind", "encounter kind/group mismatch")
            encounter_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE.ENCOUNTER."))
            roster = _object(obj["initialRoster"], path + ".initialRoster", {"cardinality", "selection"})
            low, high, members = validate_selection(roster["selection"], path=path + ".initialRoster.selection", known_models=model_ids)
            if roster["cardinality"] != {"minimum": low, "maximum": high}:
                _fail(path + ".initialRoster.cardinality", "does not match roster AST")
            possible = set(_list(obj["possibleMonsters"], path + ".possibleMonsters"))
            produced = set(_list(obj["producedMonsters"], path + ".producedMonsters"))
            if not members <= possible or not produced <= possible or not possible <= model_ids:
                _fail(path, "broken encounter-to-monster reference")
            for pool_index, pool in enumerate(obj["productionPools"]):
                pp = f"{path}.productionPools[{pool_index}]"
                pool_obj = _object(pool, pp, {"members", "poolId"})
                if not set(pool_obj["members"]) <= model_ids:
                    _fail(pp + ".members", "unknown production-pool monster")
            _string(obj["title"], path + ".title")

    state_rows = _list(sf["states"], "payload.sourceFacts.states")
    if len(state_rows) != 8:
        _fail("payload.sourceFacts.states", "expected eight explicit state identities")
    state_fact_ids = set()
    state_ids = set()
    for index, row in enumerate(state_rows):
        path = f"payload.sourceFacts.states[{index}]"
        obj = _object(row, path, {"canonicalModel", "displayName", "displayNameKey", "factId", "hpState", "stateId"})
        if obj["canonicalModel"] not in model_ids:
            _fail(path + ".canonicalModel", "state refers to unknown model")
        sid = _string(obj["stateId"], path + ".stateId", prefix=obj["canonicalModel"] + "#")
        if sid in state_ids:
            _fail(path + ".stateId", "duplicate state ID")
        state_ids.add(sid)
        state_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE.STATE."))
        _validate_name(obj["displayName"], path + ".displayName")
    state_rules = _object(sf["stateRules"], "payload.sourceFacts.stateRules", {"factId", "rules"})
    _walk_expressions(state_rules["rules"], "payload.sourceFacts.stateRules.rules")

    models = _object(sf["models"], "payload.sourceFacts.models", {"cards", "powers"})
    referenced_model_ids: set[str] = set(model_ids)
    referenced_fact_ids: set[str] = set()
    for family, prefix in (("cards", "CARD."), ("powers", "POWER.")):
        expected_count = 9 if family == "cards" else 69
        rows = _list(models[family], f"payload.sourceFacts.models.{family}")
        if len(rows) != expected_count:
            _fail(f"payload.sourceFacts.models.{family}", f"expected {expected_count} records")
        for index, row in enumerate(rows):
            path = f"payload.sourceFacts.models.{family}[{index}]"
            obj = _object(row, path, {"canonicalId", "englishTitle", "factId"})
            model = _string(obj["canonicalId"], path + ".canonicalId", prefix=prefix)
            if model in referenced_model_ids:
                _fail(path + ".canonicalId", "duplicate referenced model")
            referenced_model_ids.add(model)
            referenced_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE." + prefix))
            _string(obj["englishTitle"], path + ".englishTitle")

    owners = _list(sf["behaviorOwners"], "payload.sourceFacts.behaviorOwners")
    if len(owners) != 105:
        _fail("payload.sourceFacts.behaviorOwners", "expected 105 behavior owners")
    owner_ids = set()
    owner_fact_ids = set()
    for index, row in enumerate(owners):
        path = f"payload.sourceFacts.behaviorOwners[{index}]"
        obj = _object(row, path, {"applicableConcreteModels", "applicabilityKind", "canonicalMonster", "classification", "factId", "modelRef", "sourceType"}, {"applicableConcreteModels", "applicabilityKind", "canonicalMonster", "classification", "factId", "sourceType"})
        owner = _string(obj["canonicalMonster"], path + ".canonicalMonster", prefix="MONSTER.")
        if owner in owner_ids:
            _fail(path + ".canonicalMonster", "duplicate behavior owner")
        owner_ids.add(owner)
        owner_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE.BEHAVIOR_OWNER.MONSTER."))
        applicable = _list(obj["applicableConcreteModels"], path + ".applicableConcreteModels")
        if not applicable or len(applicable) != len(set(applicable)) or not set(applicable) <= model_ids:
            _fail(path + ".applicableConcreteModels", "missing, duplicate, or unknown concrete applicability")
        if obj["classification"] == "concreteModel":
            expected_kind = "directModel" if applicable == [owner] else "directModelWithInheritedApplicability"
            if (obj.get("modelRef") != f"SOURCE.{owner}" or owner not in model_ids
                    or obj["applicabilityKind"] != expected_kind or owner not in applicable
                    or (expected_kind == "directModelWithInheritedApplicability" and len(applicable) < 2)):
                _fail(path, "broken direct/inherited concrete behavior-owner model join")
        elif obj["classification"] == "abstractBehavior":
            if "modelRef" in obj or obj["applicabilityKind"] != "inheritedBehavior":
                _fail(path, "abstract behavior owner lacks explicit inheritance applicability")
        else:
            _fail(path + ".classification", "unsupported owner classification")

    owner_applicability = {row["canonicalMonster"]: row["applicableConcreteModels"] for row in owners}

    move_rows = _list(sf["moves"], "payload.sourceFacts.moves")
    if len(move_rows) != 315:
        _fail("payload.sourceFacts.moves", "expected 315 move registrations")
    move_ids = set()
    move_fact_ids = set()
    operation_ids = set()
    for index, row in enumerate(move_rows):
        path = f"payload.sourceFacts.moves[{index}]"
        obj = _object(row, path, {
            "action", "applicableConcreteModels", "canonicalId", "canonicalMonster", "factId", "graphId", "intents", "operations",
            "ordinal", "ownerRef", "sourceType", "stateId", "title",
        })
        move_id = _string(obj["canonicalId"], path + ".canonicalId", prefix="MONSTER.")
        if move_id in move_ids:
            _fail(path + ".canonicalId", "duplicate move registration")
        move_ids.add(move_id)
        owner = _string(obj["canonicalMonster"], path + ".canonicalMonster", prefix="MONSTER.")
        if move_id != f"{owner}#{obj['stateId']}":
            _fail(path, "registration canonical ID/owner/state mismatch")
        if owner not in owner_ids or obj["ownerRef"] != f"SOURCE.BEHAVIOR_OWNER.{owner}":
            _fail(path + ".ownerRef", "broken registration-to-owner join")
        if obj["applicableConcreteModels"] != owner_applicability[owner]:
            _fail(path + ".applicableConcreteModels", "registration applicability differs from owner")
        move_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE.MOVE.MONSTER."))
        action = _object(obj["action"], path + ".action", {"executionKind", "symbolSignature"})
        if action["executionKind"] not in {"asyncStateMachine", "synchronousNoOp"}:
            _fail(path + ".action.executionKind", "unsupported action execution kind")
        _string(action["symbolSignature"], path + ".action.symbolSignature")
        _integer(obj["ordinal"], path + ".ordinal")
        for intent_index, intent in enumerate(_list(obj["intents"], path + ".intents")):
            _validate_intent(intent, f"{path}.intents[{intent_index}]")
        for op_index, operation in enumerate(_list(obj["operations"], path + ".operations")):
            _validate_projected_operation(operation, f"{path}.operations[{op_index}]")
            op_id = operation["operationId"]
            if op_id in operation_ids:
                _fail(f"{path}.operations[{op_index}].operationId", "duplicate operation ID")
            operation_ids.add(op_id)
            model = operation.get("model")
            if model is not None and model not in referenced_model_ids:
                _fail(f"{path}.operations[{op_index}].model", "broken operation-model reference")
        _validate_title(obj["title"], path + ".title")

    graph_rows = _list(sf["graphs"], "payload.sourceFacts.graphs")
    if len(graph_rows) != 105:
        _fail("payload.sourceFacts.graphs", "expected 105 graphs")
    graph_ids = set()
    graph_fact_ids = set()
    for index, row in enumerate(graph_rows):
        path = f"payload.sourceFacts.graphs[{index}]"
        obj = _object(row, path, {"applicableConcreteModels", "canonicalMonster", "edges", "factId", "graphId", "initial", "nodes", "sourceType", "stateCollection", "topology"})
        graph_id = _string(obj["graphId"], path + ".graphId", prefix="GRAPH.")
        if graph_id in graph_ids:
            _fail(path + ".graphId", "duplicate graph ID")
        graph_ids.add(graph_id)
        graph_fact_ids.add(_string(obj["factId"], path + ".factId", prefix="SOURCE.GRAPH."))
        owner = obj["canonicalMonster"]
        if owner not in owner_ids:
            _fail(path + ".canonicalMonster", "graph has unknown behavior owner")
        if obj["applicableConcreteModels"] != owner_applicability[owner]:
            _fail(path + ".applicableConcreteModels", "graph applicability differs from owner")
        nodes = _list(obj["nodes"], path + ".nodes")
        node_ids = set()
        for node_index, node in enumerate(nodes):
            np = f"{path}.nodes[{node_index}]"
            no = _object(node, np, {"kind", "mustPerformOnce", "nodeId", "stateId"}, {"kind", "nodeId", "stateId"})
            if no["kind"] not in GRAPH_NODE_KINDS:
                _fail(np + ".kind", "unsupported graph node kind")
            nid = _string(no["nodeId"], np + ".nodeId", prefix=graph_id + "/")
            if nid in node_ids:
                _fail(np + ".nodeId", "duplicate graph node")
            node_ids.add(nid)
            if no["kind"] == "move" and f"{owner}#{no['stateId']}" not in move_ids:
                _fail(np + ".stateId", "move graph node has no registration")
            if "mustPerformOnce" in no and type(no["mustPerformOnce"]) is not bool:
                _fail(np + ".mustPerformOnce", "must be boolean")
        _validate_state_collection(obj["stateCollection"], path + ".stateCollection", node_ids)
        initial = obj["initial"]
        initials = initial if isinstance(initial, list) else [initial]
        if not initials or any(item not in node_ids for item in initials):
            _fail(path + ".initial", "unknown graph initial node")
        graph_ast = {key: deepcopy(obj[key]) for key in ("canonicalMonster", "graphId", "sourceType", "topology", "nodes", "edges", "initial")}
        graph_ast["provenance"] = _dummy_proof()
        validate_graph(graph_ast, path=path)
        topology = _object(obj["topology"], path + ".topology", {
            "conditionalBranches", "conditionalNodes", "followUpEdges", "moveNodes",
            "mustOnceFlags", "randomBranches", "randomNodes",
        })
        for key, value in topology.items():
            _integer(value, path + ".topology." + key)

    random_selection = _object(sf["randomSelection"], "payload.sourceFacts.randomSelection", {
        "algorithm", "enumValues", "factId", "methods", "overloads", "summary",
    })
    random_fact_id = _string(random_selection["factId"], "payload.sourceFacts.randomSelection.factId", prefix="SOURCE.RANDOM_SELECTION.")
    if random_selection["summary"] != {
        "branches": 61, "floatCallbacks": 8, "graphs": 21, "overloads": 10,
        "repeatTypeDistribution": {"CanRepeatForever": 4, "CanRepeatXTimes": 10, "CannotRepeat": 45, "UseOnlyOnce": 2},
    } or len(random_selection["overloads"]) != 10 or set(random_selection["methods"]) != {"callbackEvaluation", "effectiveWeight", "selection"}:
        _fail("payload.sourceFacts.randomSelection", "compact random runtime closure incomplete")
    source_random = source["behavior"]["randomSelectionContract"]
    if random_selection["algorithm"] != source_random["algorithm"]:
        _fail("payload.sourceFacts.randomSelection.algorithm", "state-log/RNG rule differs from source")
    compact_parameters = [row["parameters"] for row in random_selection["overloads"]]
    if compact_parameters != [row["parameters"] for row in source_random["overloads"]]:
        _fail("payload.sourceFacts.randomSelection.overloads", "AddBranch parameter/type/order differs from source")
    if any(random_selection["methods"][key]["methodBodySha256"] != source_random["methods"][key]["methodBodySha256"] for key in random_selection["methods"]):
        _fail("payload.sourceFacts.randomSelection.methods", "runtime method provenance differs from source")
    if random_selection["enumValues"] != [
        {"name": "CanRepeatForever", "value": 0}, {"name": "CanRepeatXTimes", "value": 1},
        {"name": "CannotRepeat", "value": 2}, {"name": "UseOnlyOnce", "value": 3},
    ]:
        _fail("payload.sourceFacts.randomSelection.enumValues", "MoveRepeatType mismatch")

    production = _object(sf["production"], "payload.sourceFacts.production", {
        "addApiCensus", "applicability", "coreAddContract", "directSites", "factId", "helperCallSites",
        "ostySummonCensus", "ostySummonContract", "producerRoots", "productionSemantics", "summary",
    })
    production_fact_id = _string(production["factId"], "payload.sourceFacts.production.factId", prefix="SOURCE.PRODUCTION.")
    expected_summary = {"addAssemblySites": 14, "currentDirectSites": 6, "helperCallEdges": 5,
        "helperMethods": 3, "ostyAssemblySites": 17, "ownerEncounterApplicability": 6,
        "producerOwners": 6, "producerRoots": 7, "siteClassifications": {"coreAddForwarding": 2,
        "currentEnemyEncounterProduction": 6, "outOfScopeDeathPower": 4, "outOfScopeMock": 1,
        "outOfScopePlayerPet": 1}}
    if production["summary"] != expected_summary:
        _fail("payload.sourceFacts.production", "compact production summary mismatch")
    production_semantic_fact_ids = _validate_production_semantics(
        production["productionSemantics"], "payload.sourceFacts.production.productionSemantics",
        move_ids=move_ids,
        initial_fact_ids={row["factId"] for row in source["initialState"]["initialStateFacts"]},
        compact=True,
    )
    add_rows = _list(production["addApiCensus"], "payload.sourceFacts.production.addApiCensus")
    osty_rows = _list(production["ostySummonCensus"], "payload.sourceFacts.production.ostySummonCensus")
    add_ids = _unique(add_rows, "siteId", "payload.sourceFacts.production.addApiCensus")
    _unique(osty_rows, "siteId", "payload.sourceFacts.production.ostySummonCensus")
    roots = _list(production["producerRoots"], "payload.sourceFacts.production.producerRoots")
    root_ids = _unique(roots, "moveId", "payload.sourceFacts.production.producerRoots")
    helpers = _list(production["helperCallSites"], "payload.sourceFacts.production.helperCallSites")
    if (len(add_rows), len(osty_rows), len(roots), len(helpers), len(production["directSites"]), len(production["applicability"])) != (14, 17, 7, 5, 6, 6):
        _fail("payload.sourceFacts.production", "compact production denominator drift")
    compact_counts: dict[str, int] = {}
    for row in add_rows:
        compact_counts[row["classification"]] = compact_counts.get(row["classification"], 0) + 1
    if compact_counts != expected_summary["siteClassifications"] or any(row["classification"] == "currentEnemyEncounterProduction" for row in osty_rows):
        _fail("payload.sourceFacts.production", "compact Add classification/Osty separation mismatch")
    if len(_unique(helpers, "callSiteId", "payload.sourceFacts.production.helperCallSites")) != 5 or len({row["calleeSymbolSignature"] for row in helpers}) != 3 or any(row["calleeSymbolSignature"] == row["callerSymbolSignature"] for row in helpers):
        _fail("payload.sourceFacts.production.helperCallSites", "compact helper closure duplicated/incomplete/cyclic")
    if not root_ids <= move_ids or any(row["apiSiteRef"] not in add_ids or not set(row["rootRefs"]) <= root_ids for row in production["directSites"]):
        _fail("payload.sourceFacts.production", "compact production root/site join incomplete")
    if any(row.get("awaitedResult") != "exactCreatedCreatureBody" or row.get("side") != {"enumName": "Enemy", "enumValue": 2} or row.get("targetCombat") != "sourceMonsterCombatState" for row in production["directSites"]):
        _fail("payload.sourceFacts.production.directSites", "compact target/side/awaited body identity changed")
    if any(not row.get("candidateMembership", {}).get("canonicalModels") for row in production["directSites"]):
        _fail("payload.sourceFacts.production.directSites", "compact exact candidate membership missing")
    if production["ostySummonContract"].get("afterSummon") != "awaitedAfterOstyAddOrReviveHistory" or production["ostySummonContract"].get("classification") != "separateFromCreatureCmdAddEnemyProduction":
        _fail("payload.sourceFacts.production.ostySummonContract", "compact Osty AfterSummon separation incomplete")
    core = production["coreAddContract"]
    if len(core.get("overloads", [])) != 3 or len(core.get("methods", {})) != 6 or core.get("hookBoundary", {}).get("afterSummon") != "absentSeparateOstyApi" or core.get("semanticBoundaries", {}).get("coreSlotValidation") != "absent":
        _fail("payload.sourceFacts.production.coreAddContract", "compact core Add boundary incomplete")
    source_core = source["production"]["coreAddContract"]
    if core.get("callOrder") != source_core["callOrder"] or core.get("dependencies") != source_core["dependencies"] or core.get("resultIdentity") != source_core["resultIdentity"] or core.get("history") != source_core["history"]:
        _fail("payload.sourceFacts.production.coreAddContract", "compact core order/dependency/history differs from source")

    placement = _object(sf["placement"], "payload.sourceFacts.placement", {"acts", "encounters", "eventLinkage", "pools", "sourceDenominators"})
    placement_fact_ids = set()
    clean_placement = deepcopy(placement)
    for family, prefix, expected_count in (("acts", "SOURCE.ACT.", 4), ("pools", "SOURCE.POOL.", 20), ("encounters", "SOURCE.PLACEMENT.", 89), ("eventLinkage", "SOURCE.EVENT_LINK.", 8)):
        rows = _list(clean_placement[family], f"payload.sourceFacts.placement.{family}")
        if len(rows) != expected_count:
            _fail(f"payload.sourceFacts.placement.{family}", f"expected {expected_count} records")
        for index, row in enumerate(rows):
            placement_fact_ids.add(_string(row.pop("factId", None), f"payload.sourceFacts.placement.{family}[{index}].factId", prefix=prefix))
    try:
        validate_placement(clean_placement)
    except SourceExtractionError as exc:
        _fail("payload.sourceFacts.placement", str(exc))

    observed = _object(sf["observationIdentities"], "payload.sourceFacts.observationIdentities", {"aliases", "entries", "matchingPolicy", "observationContracts", "policyFactId", "resourceRepresentations", "sourceConclusions", "sourceDenominators", "stateObservationContracts"})
    identity_fact_ids = {_string(observed["policyFactId"], "payload.sourceFacts.observationIdentities.policyFactId", prefix="SOURCE.OBSERVATION_IDENTITY_POLICY")}
    clean_observed = deepcopy(observed)
    clean_observed.pop("policyFactId")
    for index, row in enumerate(clean_observed["entries"]):
        identity_fact_ids.add(_string(row.pop("factId", None), f"payload.sourceFacts.observationIdentities.entries[{index}].factId", prefix="SOURCE.OBSERVED_IDENTITY.MONSTER."))
    for index, row in enumerate(clean_observed["resourceRepresentations"]):
        identity_fact_ids.add(_string(row.pop("factId", None), f"payload.sourceFacts.observationIdentities.resourceRepresentations[{index}].factId", prefix="SOURCE.OBSERVED_RESOURCE.MONSTER."))
    for index, row in enumerate(clean_observed["stateObservationContracts"]):
        identity_fact_ids.add(_string(row.pop("factId", None), f"payload.sourceFacts.observationIdentities.stateObservationContracts[{index}].factId", prefix="SOURCE.OBSERVED_STATE.MONSTER."))
    try:
        validate_observation_identities(clean_observed, reachable_models=model_ids)
    except SourceExtractionError as exc:
        _fail("payload.sourceFacts.observationIdentities", str(exc))

    hp_pipeline = _object(sf["hpPipeline"], "payload.sourceFacts.hpPipeline", {
        "applicability", "assignment", "baseSelection", "commandWrappers", "factId", "networkStorage",
        "regressionWitnesses", "ruleId", "sourceDenominators", "specialCallPaths", "storage",
    })
    hp_pipeline_fact_id = _string(hp_pipeline["factId"], "payload.sourceFacts.hpPipeline.factId", prefix="SOURCE.HP_ASSIGNMENT_PIPELINE")
    if "callCensus" in hp_pipeline or "provenance" in hp_pipeline:
        _fail("payload.sourceFacts.hpPipeline", "proof/call bulk leaked")
    try:
        validate_expression(hp_pipeline["assignment"]["conversion"], path="payload.sourceFacts.hpPipeline.assignment.conversion", expected_type="integer")
    except (KeyError, TypeError, SourceExtractionError) as exc:
        _fail("payload.sourceFacts.hpPipeline.assignment.conversion", str(exc))
    if hp_pipeline["sourceDenominators"] != {
        "baseSelectionChainMethods": 4, "capClampPreconditionSemanticFields": 8,
        "commandAndSpecialCallerApplicability": 52, "completePipelineSemanticFields": 85,
        "multiplayerWrapperHelperCallSites": 9, "setterMethodsAndDirectCallSites": 11,
        "storageAndNetworkSerializationJoins": 10,
    }:
        _fail("payload.sourceFacts.hpPipeline.sourceDenominators", "HP pipeline denominator drift")

    scaling = _object(sf["scaling"], "payload.sourceFacts.scaling", {"block", "hp", "ordinaryMonsterAttack", "power"})
    scaling_fact_ids = set()
    for name, row in scaling.items():
        obj = _object(row, f"payload.sourceFacts.scaling.{name}", {"factId", "rule"})
        scaling_fact_ids.add(_string(obj["factId"], f"payload.sourceFacts.scaling.{name}.factId", prefix="SOURCE.SCALING."))
        _walk_expressions(obj["rule"], f"payload.sourceFacts.scaling.{name}.rule")

    if not {row["graphId"] for row in move_rows} <= graph_ids:
        _fail("payload.sourceFacts.moves", "move refers to unknown graph")
    projected_initial = _object(sf["initialState"], "payload.sourceFacts.initialState", {
        "externalHookBoundary", "facts", "legacyComparisonFacts", "owners", "powerHookClosure",
        "runtimeStateContracts", "sourceDenominators", "stageOrdering", "summary",
    })
    projected_initial_facts = _list(projected_initial["facts"], "payload.sourceFacts.initialState.facts")
    if len(projected_initial_facts) != 111:
        _fail("payload.sourceFacts.initialState.facts", "expected 111 compact facts")
    initial_fact_ids = _unique(projected_initial_facts, "factId", "payload.sourceFacts.initialState.facts")
    for index, row in enumerate(projected_initial_facts):
        path = f"payload.sourceFacts.initialState.facts[{index}]"
        if "provenance" in row or not row["factId"].startswith("SOURCE.INITIAL."):
            _fail(path, "proof bulk leaked or fact ID is not source-laned")
        base = _object(row["baseValue"], path + ".baseValue", {"expression", "unit", "valueType"})
        validate_expression(base["expression"], path=path + ".baseValue.expression", expected_type=base["valueType"])
        _validate_initial_fact_contract(row, path, model_ids)
    initial_owner_rows = _list(projected_initial["owners"], "payload.sourceFacts.initialState.owners")
    if len(initial_owner_rows) != 108 or {row.get("ownerModel") for row in initial_owner_rows} != model_ids:
        _fail("payload.sourceFacts.initialState.owners", "expected all 108 owners")
    initial_owner_fact_ids = _unique(initial_owner_rows, "factId", "payload.sourceFacts.initialState.owners")
    for index, owner in enumerate(initial_owner_rows):
        path = f"payload.sourceFacts.initialState.owners[{index}]"
        if owner.get("classification") not in {"orderedGameplayEffects", "sourceProvenNoOp", "sourceProvenNonGameplayOnly"}:
            _fail(path + ".classification", "unsupported owner classification")
        refs = owner.get("factRefs", [])
        if not set(refs) <= initial_fact_ids:
            _fail(path + ".factRefs", "broken initial fact ref")
        applicable = owner.get("applicableModels", [])
        if not applicable or owner["ownerModel"] not in applicable or set(applicable) - model_ids:
            _fail(path + ".applicableModels", "missing/unknown applicability model")
        if (owner["classification"] == "orderedGameplayEffects") != bool(refs):
            _fail(path, "owner effects/classification mismatch")
        if owner.get("effectiveHook", "").startswith("MegaCrit.Sts2.Core.Models.MonsterModel::AfterAddedToRoom") and owner["classification"] != "sourceProvenNoOp":
            _fail(path, "base no-op was not source-inspected")
    runtime_rows = _list(projected_initial["runtimeStateContracts"], "payload.sourceFacts.initialState.runtimeStateContracts")
    if len(runtime_rows) != 47:
        _fail("payload.sourceFacts.initialState.runtimeStateContracts", "expected 47 contracts")
    runtime_fact_ids = _unique(runtime_rows, "factId", "payload.sourceFacts.initialState.runtimeStateContracts")
    runtime_contract_ids = _unique(runtime_rows, "contractId", "payload.sourceFacts.initialState.runtimeStateContracts")
    for index, contract in enumerate(runtime_rows):
        path = f"payload.sourceFacts.initialState.runtimeStateContracts[{index}]"
        if "domain" not in contract or not contract.get("readSites") or not isinstance(contract.get("sourceInputs"), list):
            _fail(path, "runtime contract domain/read site/source-input inventory missing")
        for source_input in contract["sourceInputs"]:
            if set(source_input) != {"sourceMember", "unit", "valueType"} or not source_input["sourceMember"]:
                _fail(path + ".sourceInputs", "malformed source input")
        for site in contract.get("updateSites", []):
            if "factRef" in site and site["factRef"] not in initial_fact_ids:
                _fail(path + ".updateSites", "broken compact fact ref")
    for index, fact in enumerate(projected_initial_facts):
        refs = set(fact["sourceStateInputs"]) | set(fact["finalValueContract"]["runtimeModifierInputs"])
        if not refs <= runtime_contract_ids:
            _fail(f"payload.sourceFacts.initialState.facts[{index}]", "unregistered compact runtime input")
        required_state_contracts = {
            "combat.currentSide": "RUNTIME.COMBAT.CURRENT_SIDE",
            "initial.decimillipedeSharedMaxHp": "RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP",
            "initial.toughEggHatchHp": "RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP",
        }
        names = _initial_state_variable_names(fact["baseValue"]["expression"])
        if not names <= set(required_state_contracts) or not {required_state_contracts[name] for name in names} <= set(fact["sourceStateInputs"]):
            _fail(f"payload.sourceFacts.initialState.facts[{index}]", "unregistered source field")
    power_hooks = _list(projected_initial["powerHookClosure"], "payload.sourceFacts.initialState.powerHookClosure")
    if len(power_hooks) != 41:
        _fail("payload.sourceFacts.initialState.powerHookClosure", "expected 41 Power closures")
    for index, row in enumerate(power_hooks):
        if len(row.get("hooks", [])) != 3:
            _fail(f"payload.sourceFacts.initialState.powerHookClosure[{index}]", "hook omitted")
        for hook in row["hooks"]:
            if not set(hook.get("effectFactRefs", [])) <= initial_fact_ids:
                _fail(f"payload.sourceFacts.initialState.powerHookClosure[{index}]", "broken hook fact ref")
    comparison_fact_rows = _list(projected_initial["legacyComparisonFacts"], "payload.sourceFacts.initialState.legacyComparisonFacts")
    if len(comparison_fact_rows) != 57:
        _fail("payload.sourceFacts.initialState.legacyComparisonFacts", "expected all 57 starts-with comparisons")
    initial_comparison_fact_ids = _unique(comparison_fact_rows, "factId", "payload.sourceFacts.initialState.legacyComparisonFacts")
    for index, row in enumerate(comparison_fact_rows):
        if not set(row.get("sourceFactRefs", [])) <= (initial_fact_ids | state_fact_ids):
            _fail(f"payload.sourceFacts.initialState.legacyComparisonFacts[{index}]", "broken source comparison refs")
    boundaries = _list(projected_initial["externalHookBoundary"], "payload.sourceFacts.initialState.externalHookBoundary")
    if sum(len(row.get("declarations", [])) for row in boundaries) != 29:
        _fail("payload.sourceFacts.initialState.externalHookBoundary", "external boundary denominator drift")
    if len(projected_initial["stageOrdering"]) != 7:
        _fail("payload.sourceFacts.initialState.stageOrdering", "stage ordering chain incomplete")
    expected_projected_denominators = {
        "constructorExplicitWrites": 5, "constructorOwners": 4,
        "directSinkSitesByKind": {"applyPower": 54, "gainBlock": 1, "setCurrentHp": 1, "setMaxAndCurrentHp": 1},
        "effectiveHookImplementations": 59, "encounterGenerationOwners": 89,
        "generatorConstructionSites": 137, "generatorRngSites": 38, "generatorSetterOwners": 13,
        "generatorSetterSites": 25, "initialStateModels": 108, "nonRosterInitializationRngRoots": 5,
        "powerModels": 41,
    }
    if projected_initial["sourceDenominators"] != expected_projected_denominators:
        _fail("payload.sourceFacts.initialState.sourceDenominators", "initial-state source denominator drift")
    if projected_initial["summary"] != {"encounterRoots": 89, "facts": 111, "invocationDecisions": 1092,
                                        "modelOwners": 108, "powerModels": 41, "runtimeContracts": 47}:
        _fail("payload.sourceFacts.initialState.summary", "summary drift")
    # The compact contract intentionally excludes all transitive proof/call bulk.
    if any(key in projected_initial for key in {"invocationDecisions", "constructorDecisions", "encounterInitializerDecisions"}):
        _fail("payload.sourceFacts.initialState", "proof bulk leaked")

    event_behavior = _object(sf["eventTurnBehavior"], "payload.sourceFacts.eventTurnBehavior",
                             {"dependencies", "encounters", "invocationSummary", "sourceDenominators"})
    dependency_rows = _list(event_behavior["dependencies"], "payload.sourceFacts.eventTurnBehavior.dependencies")
    if len(dependency_rows) != 4:
        _fail("payload.sourceFacts.eventTurnBehavior.dependencies", "expected four dependency boundaries")
    event_dependency_fact_ids = _unique(dependency_rows, "factId", "payload.sourceFacts.eventTurnBehavior.dependencies")
    dependency_by_fact = {}
    for index, row in enumerate(dependency_rows):
        path = f"payload.sourceFacts.eventTurnBehavior.dependencies[{index}]"
        obj = _object(row, path, {"dependencyId", "factId", "initialStateFactRefs", "kind", "resolvedComponentRef", "sourceRootSymbols", "sourceType", "status"},
                      {"dependencyId", "factId", "initialStateFactRefs", "kind", "sourceRootSymbols", "sourceType", "status"})
        if obj["factId"] != "SOURCE." + obj["dependencyId"] or obj["kind"] not in {"scriptedEventSemantics", "eventLifecycleTimeoutResultSemantics"}:
            _fail(path, "event dependency identity/kind mismatch")
        if obj["kind"] == "scriptedEventSemantics":
            if obj["status"] != "sourceComplete" or obj.get("resolvedComponentRef") != "EVENT_SCRIPT_COMPONENT.THE_ARCHITECT":
                _fail(path, "Architect scripted component ref unresolved")
        elif obj["status"] != "sourceComplete" or obj.get("resolvedComponentRef") != "lifecycle.eventCombat":
            _fail(path, "event lifecycle dependency is not exactly resolved")
        roots = _list(obj["sourceRootSymbols"], path + ".sourceRootSymbols")
        if not roots or any(not isinstance(root, str) or "::" not in root or " sig:" not in root for root in roots):
            _fail(path + ".sourceRootSymbols", "event dependency roots missing")
        if not set(obj["initialStateFactRefs"]) <= initial_fact_ids:
            _fail(path + ".initialStateFactRefs", "event dependency initial-state ref is unknown")
        expected_refs = 1 if obj["kind"] == "eventLifecycleTimeoutResultSemantics" else 0
        if len(obj["initialStateFactRefs"]) != expected_refs:
            _fail(path + ".initialStateFactRefs", "event dependency initial-state ref cardinality mismatch")
        dependency_by_fact[obj["factId"]] = obj

    event_rows = _list(event_behavior["encounters"], "payload.sourceFacts.eventTurnBehavior.encounters")
    if len(event_rows) != 8:
        _fail("payload.sourceFacts.eventTurnBehavior.encounters", "expected all eight event turn classifications")
    event_turn_fact_ids = _unique(event_rows, "factId", "payload.sourceFacts.eventTurnBehavior.encounters")
    event_encounter_ids = {row["canonicalId"] for row in encounter_groups["event"]}
    compact_moves_by_fact = {row["factId"]: row for row in move_rows}
    compact_graphs_by_fact = {row["factId"]: row for row in graph_rows}
    class_counts: dict[str, int] = {}
    for index, row in enumerate(event_rows):
        path = f"payload.sourceFacts.eventTurnBehavior.encounters[{index}]"
        obj = _object(row, path, {
            "applicability", "behaviorClassification", "behaviorOwner", "behaviorOwnerRef", "behaviorOwnerSourceType",
            "canonicalEncounter", "canonicalEvent", "canonicalModel", "dependencyRefs", "encounterRef", "eventLinkRef",
            "eventSourceType", "factId", "graphId", "graphRef", "initialStateFactRefs", "modelRef", "registrationRefs", "titles",
        })
        encounter_id = obj["canonicalEncounter"]
        if encounter_id not in event_encounter_ids or obj["factId"] != "SOURCE.EVENT_TURN." + encounter_id:
            _fail(path, "event turn fact/encounter identity mismatch")
        expected_refs = {
            "encounterRef": "SOURCE.ENCOUNTER." + encounter_id,
            "eventLinkRef": "SOURCE.EVENT_LINK." + encounter_id,
            "modelRef": "SOURCE." + obj["canonicalModel"],
            "behaviorOwnerRef": "SOURCE.BEHAVIOR_OWNER." + obj["behaviorOwner"],
            "graphRef": "SOURCE." + obj["graphId"],
        }
        for key, expected in expected_refs.items():
            if obj[key] != expected:
                _fail(path + "." + key, "event turn fact join mismatch")
        if obj["encounterRef"] not in encounter_fact_ids or obj["eventLinkRef"] not in placement_fact_ids or obj["modelRef"] not in monster_fact_ids or obj["behaviorOwnerRef"] not in owner_fact_ids or obj["graphRef"] not in graph_fact_ids:
            _fail(path, "event turn fact has an unknown encounter/link/model/owner/graph ref")
        graph = compact_graphs_by_fact[obj["graphRef"]]
        if graph["canonicalMonster"] != obj["behaviorOwner"] or graph["sourceType"] != obj["behaviorOwnerSourceType"] or obj["canonicalModel"] not in graph["applicableConcreteModels"]:
            _fail(path, "event turn graph applicability/ref mismatch")
        registrations = [compact_moves_by_fact.get(ref) for ref in obj["registrationRefs"]]
        if not registrations or any(reg is None or reg["graphId"] != obj["graphId"] or obj["canonicalModel"] not in reg["applicableConcreteModels"] for reg in registrations):
            _fail(path + ".registrationRefs", "event turn registration/applicability ref mismatch")
        if not set(obj["dependencyRefs"]) <= event_dependency_fact_ids or not set(obj["initialStateFactRefs"]) <= initial_fact_ids:
            _fail(path, "event classification dependency/initial-state ref mismatch")
        classification = obj["behaviorClassification"]
        class_counts[classification] = class_counts.get(classification, 0) + 1
        incomplete = classification in {"noOpTurnMachineWithLifecycle", "scriptedNonTurnCombat"}
        if len(obj["dependencyRefs"]) != (1 if incomplete else 0):
            _fail(path + ".dependencyRefs", "event classification dependency cardinality mismatch")
        direct = obj["canonicalModel"] == obj["behaviorOwner"]
        if obj["applicability"] != ("direct" if direct else "inherited") or (classification == "inheritedTurnMachine") != (not direct):
            _fail(path + ".applicability", "event inherited applicability edge missing or guessed")
        if incomplete and any(reg["action"]["executionKind"] != "synchronousNoOp" or reg["operations"][0].get("transition") != "noOp" for reg in registrations):
            _fail(path, "hidden/no-op graph was not explicitly source-inspected")
        titles = _list(obj["titles"], path + ".titles")
        if len(titles) != len(registrations) or {title["stateId"] for title in titles} != {reg["stateId"] for reg in registrations}:
            _fail(path + ".titles", "event title/registration join mismatch")
        expected_root = obj["canonicalModel"].removeprefix("MONSTER.")
        for title_index, title_row in enumerate(titles):
            title = title_row["title"]
            _validate_title(title, f"{path}.titles[{title_index}].title")
            if title.get("classification") != "localized" or title.get("localizationRoot") != expected_root:
                _fail(f"{path}.titles[{title_index}]", "event title-root collision or guessed owner title")
    if class_counts != {"inheritedTurnMachine": 1, "noOpTurnMachineWithLifecycle": 3, "normalTurnMachine": 3, "scriptedNonTurnCombat": 1}:
        _fail("payload.sourceFacts.eventTurnBehavior.encounters", "event classification distribution drift")
    if event_behavior["invocationSummary"] != {
        "classificationCounts": {"normalizedGameplayOperation": 6, "provenNonGameplayPlumbing": 76, "traversedGameplayHelper": 21},
        "denominator": 103, "resolved": 103, "unresolved": 0,
    }:
        _fail("payload.sourceFacts.eventTurnBehavior.invocationSummary", "event helper invocation census drift")
    expected_event_denominators = {
        "classifications": 8, "eventIntentArguments": 5, "eventIntentConstructorSites": 6,
        "eventTurnDirectOperations": 6, "eventTurnOperationsIncludingNoOpProofs": 10,
        "noOpProofs": 4, "physicalOwners": 5, "physicalRegistrations": 8,
        "physicalTitles": 8, "reuseOrInheritanceApplicability": 3,
    }
    if event_behavior["sourceDenominators"] != expected_event_denominators:
        _fail("payload.sourceFacts.eventTurnBehavior.sourceDenominators", "event turn source denominator drift")
    if any(key in event_behavior for key in {"decisionRefs", "eventTurnInvocationCensus", "sourceRoots"}):
        _fail("payload.sourceFacts.eventTurnBehavior", "event proof/call bulk leaked")

    event_scripts = _object(sf["eventScripts"], "payload.sourceFacts.eventScripts", {
        "architect", "dependencies", "displayScaling", "edges", "effects", "foulPotionDispatch", "framework",
        "invocationSummary", "nodes", "options", "outcomes", "owners", "sourceDenominators",
        "stateContracts", "transitions",
    })
    expected_counts={"owners":5,"options":12,"transitions":7,"stateContracts":10,"effects":10,
                     "nodes":25,"edges":20,"displayScaling":3,"dependencies":6,"outcomes":7}
    event_script_fact_ids=set()
    event_ids=set();option_ids=set();transition_ids=set();node_ids=set();dependency_ids=set()
    for family,count in expected_counts.items():
        rows=_list(event_scripts[family],f"payload.sourceFacts.eventScripts.{family}")
        if len(rows)!=count:_fail(f"payload.sourceFacts.eventScripts.{family}",f"expected {count} source-discovered rows")
        ids=_unique(rows,"factId",f"payload.sourceFacts.eventScripts.{family}")
        if event_script_fact_ids & ids:_fail(f"payload.sourceFacts.eventScripts.{family}","duplicate cross-family fact ID")
        event_script_fact_ids |= ids
    for i,row in enumerate(event_scripts["owners"]):
        path=f"payload.sourceFacts.eventScripts.owners[{i}]";event_ids.add(_string(row.get("canonicalEvent"),path+".canonicalEvent",prefix="EVENT."))
        if row.get("eventSourceType") is None or row.get("availability") is None:_fail(path,"owner identity/availability missing")
        refs=set(_list(row.get("e1EncounterLinkRefs"),path+".e1EncounterLinkRefs"))
        if not refs or not refs <= placement_fact_ids:_fail(path+".e1EncounterLinkRefs","broken E1 event linkage refs")
    if len(event_ids)!=5 or "EVENT.THE_ARCHITECT" in event_ids:_fail("payload.sourceFacts.eventScripts.owners","E2c2a owner slice mismatch")
    dense=next(x for x in event_scripts["owners"] if x["canonicalEvent"]=="EVENT.DENSE_VEGETATION")
    if "event.dynamicVars.HpLoss.baseValue" not in repr(dense["availability"]["expression"]):
        _fail("payload.sourceFacts.eventScripts.owners","Dense dynamic HpLoss was flattened")
    for i,row in enumerate(event_scripts["options"]):
        path=f"payload.sourceFacts.eventScripts.options[{i}]";oid=_string(row.get("optionId"),path+".optionId",prefix="EVENT_OPTION.")
        if oid in option_ids:
            _fail(path+".optionId","duplicate option")
        option_ids.add(oid)
        callback=_object(row.get("callback"),path+".callback",{"receiver","signature","target"})
        if callback["receiver"]!="eventInstance" or "::" not in callback["target"] or not callback["signature"]:
            _fail(path+".callback","delegate receiver/target/signature unresolved")
        if row.get("eventId") not in event_ids:_fail(path+".eventId","unknown owner")
    link_by_fact={"SOURCE.EVENT_LINK."+x["canonicalEncounter"].removeprefix("ENCOUNTER."):x for x in sf["placement"]["eventLinkage"]}
    # The builder's placement fact IDs include no doubled ENCOUNTER segment.
    link_by_fact={x["factId"]:x for x in sf["placement"]["eventLinkage"]}
    for i,row in enumerate(event_scripts["transitions"]):
        path=f"payload.sourceFacts.eventScripts.transitions[{i}]";tid=_string(row.get("transitionId"),path+".transitionId",prefix="EVENT_TRANSITION.")
        if tid in transition_ids:
            _fail(path+".transitionId","duplicate transition")
        transition_ids.add(tid)
        ref=row.get("e1EventLinkRef");link=link_by_fact.get(ref)
        if link is None or link["canonicalEncounter"]!=row.get("canonicalEncounter") or link["canonicalEvent"]!=row.get("eventId"):
            _fail(path+".e1EventLinkRef","transition/E1 owner/encounter join mismatch")
        resume=_object(row.get("resume"),path+".resume",{"mode","shouldResume"})
        if type(resume["shouldResume"]) is not bool:_fail(path+".resume.shouldResume","must be exact decoded Boolean")
        overload=_object(row.get("overload"),path+".overload",{"genericEncounter","symbolSignature"})
        if "EnterCombatWithoutExitingEvent" not in overload["symbolSignature"]:_fail(path+".overload","wrong transition overload")
        rewards=row.get("addedRewards")
        if not isinstance(rewards,list):_fail(path+".addedRewards","reward argument not normalized")
        for reward_index,reward in enumerate(rewards):
            rp=f"{path}.addedRewards[{reward_index}]"
            reward_obj=_object(reward,rp,{"condition","constructionIndex","model","rewardType"})
            if reward_obj["rewardType"] not in {"PotionReward","RelicReward","SpecialCardReward"}:
                _fail(rp+".rewardType","unknown reward constructor")
            model=_object(reward_obj["model"],rp+".model",{"kind","name","rewardKind","sourceType"},{"kind"})
            if model["kind"] not in {"fixedModel","runtimeModel","runtimePull"}:
                _fail(rp+".model.kind","unknown reward model contract")
            if model["kind"]=="fixedModel" and not model.get("sourceType"):
                _fail(rp+".model.sourceType","fixed reward model missing")
            if model["kind"]=="runtimeModel" and not model.get("name"):
                _fail(rp+".model.name","runtime reward model missing")
    for row in event_scripts["nodes"]:node_ids.add(row["nodeId"])
    if len(node_ids)!=25:_fail("payload.sourceFacts.eventScripts.nodes","duplicate node identity")
    for i,row in enumerate(event_scripts["edges"]):
        if row.get("from") not in node_ids or row.get("to") not in node_ids:_fail(f"payload.sourceFacts.eventScripts.edges[{i}]","edge endpoint missing")
    for row in event_scripts["dependencies"]:dependency_ids.add(row["dependencyId"])
    if len(dependency_ids)!=6 or not any(x.startswith("LIFECYCLE.") for x in dependency_ids) or not any(x.startswith("FORMULA.") for x in dependency_ids):
        _fail("payload.sourceFacts.eventScripts.dependencies","lifecycle/formula dependency closure missing")
    outcomes=event_scripts["outcomes"]
    if {x.get("transitionRef") for x in outcomes}!=transition_ids:_fail("payload.sourceFacts.eventScripts.outcomes","transition outcome closure mismatch")
    for i,row in enumerate(outcomes):
        if not set(row.get("dependencyRefs",[])) <= dependency_ids:_fail(f"payload.sourceFacts.eventScripts.outcomes[{i}].dependencyRefs","unknown dependency")
    if event_scripts["invocationSummary"]!={"denominator":1549,"resolved":1549,"unresolved":0}:
        _fail("payload.sourceFacts.eventScripts.invocationSummary","closed invocation denominator drift")
    den=event_scripts["sourceDenominators"]
    for family,count in {**expected_counts,"encounterScripts":7,"displayScalingCalls":3,"invocations":1549,
                         "methods":76,"frameworkMethods":53,"supportMethods":14}.items():
        key={"transitions":"encounterScripts","displayScaling":"displayScalingCalls"}.get(family,family)
        if den.get(key)!=count:_fail("payload.sourceFacts.eventScripts.sourceDenominators",f"stale {key} denominator")
    if event_scripts["framework"].get("methodCount")!=53 or not event_scripts["framework"].get("roles"):
        _fail("payload.sourceFacts.eventScripts.framework","common framework closure missing")
    dispatch=event_scripts["foulPotionDispatch"]
    event_script_fact_ids.add(_string(dispatch.get("factId"),"payload.sourceFacts.eventScripts.foulPotionDispatch.factId",prefix="SOURCE.EVENT_SCRIPT."))
    if dispatch.get("classification")!="potionDrivenEventInstanceFanOut" or dispatch.get("taskJoin")!="Task.WhenAll":
        _fail("payload.sourceFacts.eventScripts.foulPotionDispatch","Fake Merchant selector/dispatch changed")
    if any(key in event_scripts for key in {"methods","frameworkMethods","invocationCensus","decisions"}):
        _fail("payload.sourceFacts.eventScripts","event method/call proof bulk leaked into compact projection")
    architect_fact_ids=_validate_compact_architect(event_scripts["architect"],placement_fact_ids)
    event_script_fact_ids |= architect_fact_ids
    lifecycle_fact_ids=_validate_compact_lifecycle(sf["lifecycle"],source)

    all_source_facts = (
        encounter_fact_ids | monster_fact_ids | state_fact_ids | referenced_fact_ids |
        owner_fact_ids | move_fact_ids | graph_fact_ids | scaling_fact_ids | placement_fact_ids |
        identity_fact_ids | initial_fact_ids | initial_owner_fact_ids | runtime_fact_ids |
        initial_comparison_fact_ids | event_dependency_fact_ids | event_turn_fact_ids | event_script_fact_ids | lifecycle_fact_ids |
        production_semantic_fact_ids | {state_rules["factId"], hp_pipeline_fact_id, random_fact_id, production_fact_id}
    )
    return {
        "all": all_source_facts, "encounters": encounter_fact_ids, "models": model_ids,
        "moves": move_fact_ids, "operations": operation_ids,
        "randomSelection": {random_fact_id}, "production": {production_fact_id} | production_semantic_fact_ids,
        "lifecycle": lifecycle_fact_ids,
    }

_LEGACY_BODY_FIELDS = {
    "count", "displayName", "hpA8", "hpBelowA8", "monsterId", "moves", "pack", "patchChecked",
    "pattern", "retainedProvenance", "role", "sourceFlags", "sourcePage", "startsWithA9", "type",
    "typedConflicts",
}


def _validate_provenance_status(value: Any, path: str, *, encounter: bool) -> None:
    allowed = {"classification", "missingPerFactFields"} | ({"claimedTarget"} if encounter else set())
    obj = _object(value, path, allowed)
    if obj["classification"] != "incompleteKnownUnknown" or obj["missingPerFactFields"] != ["confidence", "status"]:
        _fail(path, "legacy provenance must remain explicitly incomplete")
    if encounter:
        if obj["claimedTarget"] != {"branch": "public-beta", "version": "v0.111.0"}:
            _fail(path + ".claimedTarget", "wrong legacy claimed target")


def _validate_legacy_annotations(value: Any, source_sets: dict[str, set[str]]) -> set[str]:
    legacy = _object(value, "payload.legacyAnnotations", {"archive", "current", "moveTitleFallbackCandidates", "provenanceContract"})
    contract = _object(legacy["provenanceContract"], "payload.legacyAnnotations.provenanceContract", {
        "authority", "globalSourceDescription", "perFactProvenance", "requiredButAbsent",
    })
    if contract["authority"] != "legacyCommunityAnnotation" or contract["perFactProvenance"] != "incompleteKnownUnknown" or contract["requiredButAbsent"] != ["confidence", "status"]:
        _fail("payload.legacyAnnotations.provenanceContract", "fabricated or malformed community provenance")
    _string(contract["globalSourceDescription"], "payload.legacyAnnotations.provenanceContract.globalSourceDescription")

    all_fact_ids: set[str] = set()
    current_ids = set()
    for family, expected_count in (("current", 81), ("archive", 1)):
        rows = _list(legacy[family], f"payload.legacyAnnotations.{family}")
        if len(rows) != expected_count:
            _fail(f"payload.legacyAnnotations.{family}", f"expected {expected_count} records")
        for index, row in enumerate(rows):
            path = f"payload.legacyAnnotations.{family}[{index}]"
            common = {"annotations", "factId", "legacyEncounterId", "presentationBodies", "provenanceStatus"}
            allowed = common | ({"canonicalEncounterRef", "joinBasis"} if family == "current" else {"archiveReason"})
            obj = _object(row, path, allowed)
            encounter_id = _string(obj["legacyEncounterId"], path + ".legacyEncounterId")
            fact_id = _string(obj["factId"], path + ".factId", prefix="LEGACY.ENCOUNTER.")
            if fact_id != f"LEGACY.ENCOUNTER.{encounter_id}" or fact_id in all_fact_ids:
                _fail(path + ".factId", "duplicate/mismatched legacy encounter fact")
            all_fact_ids.add(fact_id)
            annotations = _object(obj["annotations"], path + ".annotations", {"act", "displayName", "roomClass", "rules", "timing"})
            for key in ("act", "displayName", "roomClass"):
                _string(annotations[key], path + ".annotations." + key)
            for key in ("rules", "timing"):
                if any(not isinstance(item, str) for item in _list(annotations[key], path + ".annotations." + key)):
                    _fail(path + ".annotations." + key, "must be a string list")
            _validate_provenance_status(obj["provenanceStatus"], path + ".provenanceStatus", encounter=True)
            if family == "current":
                current_ids.add(encounter_id)
                if obj["canonicalEncounterRef"] != f"SOURCE.ENCOUNTER.{encounter_id}" or obj["canonicalEncounterRef"] not in source_sets["encounters"]:
                    _fail(path + ".canonicalEncounterRef", "broken legacy-to-canonical encounter join")
                if obj["joinBasis"] != "exactCanonicalEncounterId":
                    _fail(path + ".joinBasis", "heuristic legacy join is forbidden")
            else:
                if encounter_id != "DOORMAKER_BOSS" or obj["archiveReason"] != "absentFromCurrentSourceEncounterCensus":
                    _fail(path, "only archived Doormaker may be outside current source scope")
                if f"SOURCE.ENCOUNTER.{encounter_id}" in source_sets["encounters"]:
                    _fail(path, "archived encounter unexpectedly in current source scope")
            for body_index, body in enumerate(_list(obj["presentationBodies"], path + ".presentationBodies")):
                bp = f"{path}.presentationBodies[{body_index}]"
                bo = _object(body, bp, {"annotations", "factId", "provenanceStatus"})
                body_fact = _string(bo["factId"], bp + ".factId", prefix=f"LEGACY.BODY.{encounter_id}.")
                if body_fact != f"LEGACY.BODY.{encounter_id}.{body_index}" or body_fact in all_fact_ids:
                    _fail(bp + ".factId", "duplicate/mismatched legacy body fact")
                all_fact_ids.add(body_fact)
                body_annotations = _object(bo["annotations"], bp + ".annotations", _LEGACY_BODY_FIELDS, {
                    "count", "displayName", "hpA8", "hpBelowA8", "monsterId", "moves", "pattern", "retainedProvenance", "sourcePage", "type",
                })
                _string(body_annotations["monsterId"], bp + ".annotations.monsterId")
                _string(body_annotations["displayName"], bp + ".annotations.displayName")
                _integer(body_annotations["count"], bp + ".annotations.count", minimum=1)
                for hp_field in ("hpBelowA8", "hpA8"):
                    hp = _list(body_annotations[hp_field], bp + f".annotations.{hp_field}")
                    if len(hp) not in {1, 2} or any(type(item) is not int or item <= 0 for item in hp):
                        _fail(bp + f".annotations.{hp_field}", "must be a one/two endpoint positive integer range")
                    if len(hp) == 2 and hp[0] > hp[1]:
                        _fail(bp + f".annotations.{hp_field}", "range endpoints must be ordered")
                pattern = _object(body_annotations["pattern"], bp + ".annotations.pattern", {"text", "type"})
                _string(pattern["text"], bp + ".annotations.pattern.text")
                _string(pattern["type"], bp + ".annotations.pattern.type")
                _string(body_annotations["sourcePage"], bp + ".annotations.sourcePage")
                provenance = _object(body_annotations["retainedProvenance"], bp + ".annotations.retainedProvenance",
                                     {"article", "articleLocator", "bodyKey", "module"})
                body_key = _string(provenance["bodyKey"], bp + ".annotations.retainedProvenance.bodyKey")
                if body_key != body_annotations["displayName"]:
                    _fail(bp + ".annotations.retainedProvenance.bodyKey", "must exactly own the retained display body")
                article = _object(provenance["article"], bp + ".annotations.retainedProvenance.article",
                                  {"owner", "pageKey", "revisionId", "template", "templateOrdinal"})
                if article["owner"] != body_key or not isinstance(article["revisionId"], int) or article["revisionId"] <= 0:
                    _fail(bp + ".annotations.retainedProvenance.article", "article owner/revision mismatch")
                _string(article["pageKey"], bp + ".annotations.retainedProvenance.article.pageKey")
                if article["template"] not in {"Enemy Infobox", "#invoke:Infobox"} or not isinstance(article["templateOrdinal"], int) or article["templateOrdinal"] <= 0:
                    _fail(bp + ".annotations.retainedProvenance.article", "invalid exact article template coordinate")
                locator = _object(provenance["articleLocator"], bp + ".annotations.retainedProvenance.articleLocator",
                                  {"pageKey", "sectionOwner"})
                if locator["pageKey"] != article["pageKey"]:
                    _fail(bp + ".annotations.retainedProvenance.articleLocator", "page key does not match article coordinate")
                _string(locator["sectionOwner"], bp + ".annotations.retainedProvenance.articleLocator.sectionOwner")
                module = _object(provenance["module"], bp + ".annotations.retainedProvenance.module",
                                 {"path", "reason", "recordOrdinal", "synthetic", "tableKey"}, set())
                if module.get("synthetic") is True:
                    if body_key != "Hatchling" or set(module) != {"synthetic", "reason"}:
                        _fail(bp + ".annotations.retainedProvenance.module", "only Hatchling may use the explicit synthetic module fallback")
                    _string(module["reason"], bp + ".annotations.retainedProvenance.module.reason")
                else:
                    if set(module) != {"path", "recordOrdinal", "tableKey"} or module["tableKey"] != body_key:
                        _fail(bp + ".annotations.retainedProvenance.module", "invalid exact retained module coordinate")
                    if not str(module["path"]).startswith("tools/.wiki/") or not isinstance(module["recordOrdinal"], int) or module["recordOrdinal"] <= 0:
                        _fail(bp + ".annotations.retainedProvenance.module", "invalid module path/ordinal")
                for move_index, move in enumerate(_list(body_annotations["moves"], bp + ".annotations.moves")):
                    mp = f"{bp}.annotations.moves[{move_index}]"
                    mo = _object(move, mp, {"intent", "name", "textA9"}, {"name", "textA9"})
                    _string(mo["name"], mp + ".name")
                    _string(mo["textA9"], mp + ".textA9")
                    if "intent" in mo:
                        _string(mo["intent"], mp + ".intent")
                _validate_provenance_status(bo["provenanceStatus"], bp + ".provenanceStatus", encounter=False)
                if "typedConflicts" in body_annotations:
                    for conflict_index, conflict in enumerate(_list(body_annotations["typedConflicts"], bp + ".annotations.typedConflicts")):
                        cp = f"{bp}.annotations.typedConflicts[{conflict_index}]"
                        obj = _object(conflict, cp, {
                            "actor", "articleValue", "authority", "field", "id", "independentKnownUnknown",
                            "kind", "move", "resolution", "retainedOriginPath", "retainedValue",
                            "sourceFactId", "sourceInitialFactId", "sourceValue",
                        }, {"id", "kind", "retainedValue", "sourceValue", "resolution", "authority"})
                        if obj["resolution"] != "source-wins" or obj["authority"] != "closed-source":
                            _fail(cp, "typed retained/source conflict must be source-winning and closed")
                        if obj["retainedValue"] == obj["sourceValue"]:
                            _fail(cp, "typed conflict values must disagree")
                        _string(obj["id"], cp + ".id", prefix="RETAINED.CONFLICT.")
    if "DOORMAKER_BOSS" in current_ids:
        _fail("payload.legacyAnnotations.current", "Doormaker must not be current")
    typed_ids = {
        row["id"]
        for family in ("current", "archive")
        for encounter in legacy[family]
        for body in encounter["presentationBodies"]
        for row in (body["annotations"].get("typedConflicts") or [])
    }
    expected_typed = {
        "RETAINED.CONFLICT.AXEBOT.A8_HP",
        "RETAINED.CONFLICT.OWL_MAGISTRATE.A8_HP",
        "RETAINED.CONFLICT.SCROLL_OF_BITING.A8_HP",
        "RETAINED.CONFLICT.SLIMED_BERSERKER.A8_HP",
        "RETAINED.CONFLICT.INFESTED_PRISM.RADIATE",
        "RETAINED.CONFLICT.TERROR_EEL.MOVE_TITLE.TERROR",
        "RETAINED.CONFLICT.KIN_FOLLOWER.TYPE",
    }
    if typed_ids != expected_typed:
        _fail("payload.legacyAnnotations", f"typed retained/source conflicts drifted: {sorted(typed_ids)}")

    candidates = _list(legacy["moveTitleFallbackCandidates"], "payload.legacyAnnotations.moveTitleFallbackCandidates")
    if len(candidates) != 18:
        _fail("payload.legacyAnnotations.moveTitleFallbackCandidates", "expected exactly 18 missing-title candidate sets")
    candidate_ids = set()
    for index, row in enumerate(candidates):
        path = f"payload.legacyAnnotations.moveTitleFallbackCandidates[{index}]"
        obj = _object(row, path, {"basis", "candidateId", "candidates", "sourceMoveFactId", "status"})
        candidate_id = _string(obj["candidateId"], path + ".candidateId", prefix="FALLBACK_CANDIDATES.")
        if candidate_id in candidate_ids:
            _fail(path + ".candidateId", "duplicate fallback candidate set")
        candidate_ids.add(candidate_id)
        if obj["sourceMoveFactId"] not in source_sets["moves"]:
            _fail(path + ".sourceMoveFactId", "unknown source move")
        if obj["basis"] != "sameExactCanonicalMonsterIdOnly" or obj["status"] != "unjoinedCandidateSet":
            _fail(path, "move fallback was heuristically joined or selected")
        for ci, candidate in enumerate(obj["candidates"]):
            cp = f"{path}.candidates[{ci}]"
            co = _object(candidate, cp, {"legacyBodyFactId", "legacyMoveIndex", "title"})
            if co["legacyBodyFactId"] not in all_fact_ids:
                _fail(cp + ".legacyBodyFactId", "unknown legacy body")
            _integer(co["legacyMoveIndex"], cp + ".legacyMoveIndex")
            _string(co["title"], cp + ".title")
    return all_fact_ids


def _resolve_pointer(document: Any, pointer: str, path: str) -> Any:
    if pointer == "":
        return document
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        _fail(path, "must be an RFC 6901 JSON pointer")
    value = document
    try:
        for raw in pointer.split("/")[1:]:
            token = raw.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        _fail(path, f"broken JSON pointer: {exc}")
    return value


def _validate_evidence_and_refs(payload: dict[str, Any], source: dict[str, Any], legacy: dict[str, Any], source_facts: set[str], legacy_facts: set[str]) -> None:
    evidence_rows = _list(payload["evidence"], "payload.evidence")
    evidence_ids = _unique(evidence_rows, "evidenceId", "payload.evidence")
    evidence_lanes: dict[str, str] = {}
    for index, row in enumerate(evidence_rows):
        path = f"payload.evidence[{index}]"
        obj = _object(row, path, {"artifactInput", "evidenceId", "lane", "pointers"})
        expected_lane = "source" if obj["artifactInput"] == "INPUT.SOURCE" else "legacy" if obj["artifactInput"] == "INPUT.LEGACY" else None
        if expected_lane is None or obj["lane"] != expected_lane:
            _fail(path, "evidence artifact/lane mismatch")
        evidence_lanes[obj["evidenceId"]] = obj["lane"]
        document = source if expected_lane == "source" else legacy
        pointers = _list(obj["pointers"], path + ".pointers")
        if not pointers:
            _fail(path + ".pointers", "must not be empty")
        pointer_names = set()
        for pi, pointer in enumerate(pointers):
            pp = f"{path}.pointers[{pi}]"
            po = _object(pointer, pp, {"jsonPointer", "valueSha256"})
            if po["jsonPointer"] in pointer_names:
                _fail(pp + ".jsonPointer", "duplicate evidence pointer")
            pointer_names.add(po["jsonPointer"])
            pointed = _resolve_pointer(document, po["jsonPointer"], pp + ".jsonPointer")
            if po["valueSha256"] != witness_sha256(pointed):
                _fail(pp + ".valueSha256", "evidence value digest mismatch")

    expected_facts = source_facts | legacy_facts
    if source_facts & legacy_facts:
        _fail("payload.factReferences", "source/legacy fact ID lane collision")
    ref_rows = _list(payload["factReferences"], "payload.factReferences")
    ref_ids = _unique(ref_rows, "factId", "payload.factReferences")
    if ref_ids != expected_facts:
        _fail("payload.factReferences", f"fact/evidence table mismatch (missing={sorted(expected_facts-ref_ids)!r}, extra={sorted(ref_ids-expected_facts)!r})")
    used_evidence = set()
    for index, row in enumerate(ref_rows):
        path = f"payload.factReferences[{index}]"
        obj = _object(row, path, {"evidenceRefs", "factId", "lane"})
        expected_lane = "source" if obj["factId"] in source_facts else "legacy"
        if obj["lane"] != expected_lane:
            _fail(path + ".lane", "fact lane mismatch")
        refs = _list(obj["evidenceRefs"], path + ".evidenceRefs")
        if not refs or len(refs) != len(set(refs)):
            _fail(path + ".evidenceRefs", "must be a nonempty unique reference list")
        for ref in refs:
            if ref not in evidence_ids or evidence_lanes[ref] != expected_lane:
                _fail(path + ".evidenceRefs", "broken fact-to-evidence reference or cross-lane evidence")
            used_evidence.add(ref)
    if used_evidence != evidence_ids:
        _fail("payload.evidence", "orphan evidence records are forbidden")


def _validate_comparisons_conflicts_unknowns(payload: dict[str, Any], all_facts: set[str]) -> None:
    audits = _list(payload["resolvedAudits"], "payload.resolvedAudits")
    if len(audits) != 6:
        _fail("payload.resolvedAudits", "expected HP, production, lifecycle, event-turn, linked-event, and Architect resolved audits")
    audit_ids = _unique(audits, "auditId", "payload.resolvedAudits")
    if audit_ids != {"AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING", "AUDIT.RESOLVED.PRODUCTION_SEMANTICS", "AUDIT.RESOLVED.CORE_LIFECYCLE", "AUDIT.RESOLVED.EVENT_TURN_MACHINES", "AUDIT.RESOLVED.LINKED_EVENT_SCRIPTS", "AUDIT.RESOLVED.ARCHITECT_SCRIPT"}:
        _fail("payload.resolvedAudits", "resolved audit identity set drift")
    by_id = {row["auditId"]: row for row in audits}
    hp_audit = _object(by_id["AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING"], "payload.resolvedAudits[HP]", {"auditId", "family", "historicalStatus", "lanes", "resolution"})
    if (hp_audit["family"], hp_audit["historicalStatus"]) != ("hpAssignmentRounding", "resolved"):
        _fail("payload.resolvedAudits[HP]", "HP audit identity/status drift")
    expected_lanes = [
        {"factId": "SOURCE.SCALING.HP", "lane": "rawSourceHelper", "statement": {"arithmeticRounding": "none", "outputType": "System.Decimal"}},
        {"factId": "SOURCE.HP_ASSIGNMENT_PIPELINE", "lane": "rawSourceAssignment", "statement": {"assignmentConversion": "truncateTowardZero", "nonNegativeEquivalence": "floor", "storageType": "Int32"}},
        {"implementationPath": "src/book.mjs::scaleRange", "lane": "stableLegacyConsumer", "statement": {"conversion": "Math.floor", "domain": "displayedNonNegativeHp"}},
    ]
    if hp_audit["lanes"] != expected_lanes:
        _fail("payload.resolvedAudits[HP].lanes", "authority lanes/history changed")
    if any(row.get("factId") not in all_facts for row in hp_audit["lanes"] if "factId" in row):
        _fail("payload.resolvedAudits[HP].lanes", "broken source fact reference")
    if hp_audit["resolution"] != {
        "classification": "agreementForNonNegativeFinalAssignedHp",
        "detail": "The helper performs no rounding; downstream assignment truncates toward zero, which equals floor only for source-proven non-negative HP. The stable legacy consumer floors displayed non-negative HP.",
        "negativeValuesGeneralized": False, "precedenceSelected": False,
    }:
        _fail("payload.resolvedAudits[HP].resolution", "must resolve by non-negative agreement without precedence")

    production_audit = _object(by_id["AUDIT.RESOLVED.PRODUCTION_SEMANTICS"], "payload.resolvedAudits[production]",
                               {"auditId", "boundary", "classificationFactRefs", "dependencyFactRefs", "family", "historicalStatus", "sourceDenominators"})
    production = payload["sourceFacts"]["production"]["productionSemantics"]
    expected_production_classifications = {row["factId"] for family in ("producers", "pools", "slotStrategies", "postAddEffects", "runtimeStateContracts") for row in production[family]}
    expected_production_dependencies = {row["factId"] for row in production["dependencies"]}
    if (production_audit["family"], production_audit["historicalStatus"]) != ("enemyBodyProduction", "sourceComplete"):
        _fail("payload.resolvedAudits[production]", "production audit identity/status drift")
    if (set(production_audit["classificationFactRefs"]) != expected_production_classifications
            or set(production_audit["dependencyFactRefs"]) != expected_production_dependencies
            or production_audit["sourceDenominators"] != production["sourceDenominators"]):
        _fail("payload.resolvedAudits[production]", "production audit denominators/fact refs drift")
    if not set(production_audit["classificationFactRefs"] + production_audit["dependencyFactRefs"]) <= all_facts:
        _fail("payload.resolvedAudits[production]", "production audit has broken fact refs")
    if ("lifecycle refs are source-complete" not in production_audit["boundary"]
            or "joined by refs rather than copied" not in production_audit["boundary"]):
        _fail("payload.resolvedAudits[production]", "production audit lifecycle/ref boundary changed")

    lifecycle_audit=_object(by_id["AUDIT.RESOLVED.CORE_LIFECYCLE"],"payload.resolvedAudits[lifecycle]",{"auditId","boundary","classificationFactRefs","dependencyFactRefs","family","historicalStatus","sourceDenominators"})
    lifecycle=payload["sourceFacts"]["lifecycle"]
    if (lifecycle_audit["family"],lifecycle_audit["historicalStatus"])!=("coreLifecycle","sourceComplete"):
        _fail("payload.resolvedAudits[lifecycle]","core lifecycle audit identity/status drift")
    if lifecycle_audit["classificationFactRefs"]!=[lifecycle["factId"]] or set(lifecycle_audit["dependencyFactRefs"])!={row["factId"] for row in lifecycle["dependencies"]} or lifecycle_audit["sourceDenominators"]!=lifecycle["sourceDenominators"]:
        _fail("payload.resolvedAudits[lifecycle]","core lifecycle audit fact/denominator refs drift")
    if ("aggregate listener/phase/relationship/death-Add/event/run lifecycle are source-complete" not in lifecycle_audit["boundary"]
            or "formula runtime contracts remain outside" not in lifecycle_audit["boundary"]):
        _fail("payload.resolvedAudits[lifecycle]","lifecycle audit formula boundary changed")

    event_audit = _object(by_id["AUDIT.RESOLVED.EVENT_TURN_MACHINES"], "payload.resolvedAudits[eventTurn]",
                          {"auditId", "boundary", "classificationFactRefs", "dependencyFactRefs", "family", "historicalStatus", "sourceDenominators"})
    if (event_audit["family"], event_audit["historicalStatus"], event_audit["boundary"]) != (
        "eventTurnMachines", "sourceComplete", "Architect scripting and lifecycle timeout/result refs are separately source-complete; formula boundaries remain independent."
    ):
        _fail("payload.resolvedAudits[eventTurn]", "event turn completion/boundary drift")
    if len(event_audit["classificationFactRefs"]) != 8 or len(event_audit["dependencyFactRefs"]) != 4:
        _fail("payload.resolvedAudits[eventTurn]", "event turn audit denominator drift")
    if not set(event_audit["classificationFactRefs"] + event_audit["dependencyFactRefs"]) <= all_facts:
        _fail("payload.resolvedAudits[eventTurn]", "event turn audit has broken fact refs")
    expected_event_denominators = {
        "classifications": 8, "eventIntentArguments": 5, "eventIntentConstructorSites": 6,
        "eventTurnDirectOperations": 6, "eventTurnOperationsIncludingNoOpProofs": 10,
        "noOpProofs": 4, "physicalOwners": 5, "physicalRegistrations": 8,
        "physicalTitles": 8, "reuseOrInheritanceApplicability": 3,
    }
    if event_audit["sourceDenominators"] != expected_event_denominators:
        _fail("payload.resolvedAudits[eventTurn].sourceDenominators", "event turn audit source denominators drift")
    script_audit = _object(by_id["AUDIT.RESOLVED.LINKED_EVENT_SCRIPTS"], "payload.resolvedAudits[eventScripts]",
                           {"auditId", "boundary", "classificationFactRefs", "dependencyFactRefs", "family", "historicalStatus", "sourceDenominators"})
    if (script_audit["family"], script_audit["historicalStatus"], script_audit["boundary"]) != (
            "linkedEventStartOptionTransitionResume", "sourceComplete",
            "The non-Architect scripts, Architect component, and lifecycle producers/results are separately source-complete; formula dependencies remain explicit."):
        _fail("payload.resolvedAudits[eventScripts]", "linked event audit status/boundary drift")
    script_facts={row["factId"] for row in payload["sourceFacts"]["eventScripts"]["owners"]}
    script_dependencies={row["factId"] for row in payload["sourceFacts"]["eventScripts"]["dependencies"]}
    if set(script_audit["classificationFactRefs"])!=script_facts or set(script_audit["dependencyFactRefs"])!=script_dependencies:
        _fail("payload.resolvedAudits[eventScripts]", "linked event audit fact refs drift")
    if script_audit["sourceDenominators"]!=payload["sourceFacts"]["eventScripts"]["sourceDenominators"]:
        _fail("payload.resolvedAudits[eventScripts].sourceDenominators", "linked event denominator drift")

    architect_audit = _object(by_id["AUDIT.RESOLVED.ARCHITECT_SCRIPT"], "payload.resolvedAudits[architect]",
                              {"auditId", "boundary", "classificationFactRefs", "dependencyFactRefs", "family", "historicalStatus", "sourceDenominators"})
    architect = payload["sourceFacts"]["eventScripts"]["architect"]
    expected_architect_classifications = {architect[name]["factId"] for name in ("applicability", "placement", "localization", "initialState", "lineControl", "presentation", "roomEntry", "terminal", "visualOnlyCombat")}
    expected_architect_classifications |= {row["factId"] for row in architect["dialogue"]["templates"]}
    expected_architect_dependencies = {row["factId"] for row in architect["dependencies"]}
    if (architect_audit["family"], architect_audit["historicalStatus"]) != ("architectTerminalScript", "sourceComplete"):
        _fail("payload.resolvedAudits[architect]", "Architect audit identity/status drift")
    if set(architect_audit["classificationFactRefs"]) != expected_architect_classifications or set(architect_audit["dependencyFactRefs"]) != expected_architect_dependencies:
        _fail("payload.resolvedAudits[architect]", "Architect audit refs drift")
    if architect_audit["sourceDenominators"] != architect["sourceDenominators"] or not set(architect_audit["classificationFactRefs"] + architect_audit["dependencyFactRefs"]) <= all_facts:
        _fail("payload.resolvedAudits[architect]", "Architect audit denominators/refs are invalid")
    if ("score formula values remain a dependency" not in architect_audit["boundary"]
            or "forced-kill ordering are source-complete" not in architect_audit["boundary"]):
        _fail("payload.resolvedAudits[architect]", "Architect audit formula/lifecycle boundary changed")

    comparisons = _list(payload["laneComparisons"], "payload.laneComparisons")
    comparison_ids = _unique(comparisons, "comparisonId", "payload.laneComparisons")
    conflict_comparisons = set()
    for index, row in enumerate(comparisons):
        path = f"payload.laneComparisons[{index}]"
        obj = _object(row, path, {"comparisonId", "family", "left", "reasonCode", "right", "status"}, {"comparisonId", "family", "left", "right", "status"})
        if obj["family"] not in {"encounterTitle", "monsterTitle", "initialHpA8SinglePlayer", "encounterActPlacement", "encounterRoomClass", "observedMonsterIdentity", "initialStateLegacyAnnotation"}:
            _fail(path + ".family", "unsupported overlap family")
        reason_statuses = {"notStaticallyComparable", "sourceSuperset", "dynamicNotComparable", "stateNotModel", "unmatchedLegacyIdentity", "partialNonEquivalent"}
        if obj["status"] not in {"agrees", "conflict"} | reason_statuses:
            _fail(path + ".status", "unsupported overlap classification")
        if (obj["status"] in reason_statuses) != ("reasonCode" in obj):
            _fail(path, "non-equivalent/non-comparable overlap requires exactly one reason code")
        for side, lane in (("left", "source"), ("right", "legacy")):
            so = _object(obj[side], path + "." + side, {"factId", "lane", "value"})
            if so["lane"] != lane or so["factId"] not in all_facts:
                _fail(path + "." + side, "comparison fact/lane mismatch")
        values_equal = obj["left"]["value"] == obj["right"]["value"]
        if obj["status"] == "agrees" and not values_equal:
            _fail(path, "facts disagree but overlap is classified as agrees")
        if obj["status"] == "conflict":
            if values_equal:
                _fail(path, "equal values cannot be a conflict")
            conflict_comparisons.add(obj["comparisonId"])

    initial_comparison_count = sum(row["family"] == "initialStateLegacyAnnotation" for row in comparisons)
    if initial_comparison_count != 57:
        _fail("payload.laneComparisons", f"expected 57 initial-state comparisons, got {initial_comparison_count}")
    conflicts = _list(payload["conflicts"], "payload.conflicts")
    _unique(conflicts, "conflictId", "payload.conflicts")
    represented = set()
    for index, row in enumerate(conflicts):
        path = f"payload.conflicts[{index}]"
        obj = _object(row, path, {"conflictId", "family", "left", "resolution", "right"})
        comparison_id = obj["conflictId"].removeprefix("CONFLICT.")
        if comparison_id not in comparison_ids or comparison_id in represented:
            _fail(path + ".conflictId", "orphan/duplicate conflict")
        represented.add(comparison_id)
        if obj["resolution"] != "unresolved":
            _fail(path + ".resolution", "E1 must not select a conflict winner")
        comparison = next(item for item in comparisons if item["comparisonId"] == comparison_id)
        if obj["family"] != comparison["family"] or obj["left"] != comparison["left"] or obj["right"] != comparison["right"]:
            _fail(path, "conflict does not retain both comparable facts and values")
    if represented != conflict_comparisons:
        _fail("payload.conflicts", "unclassified disagreement or missing explicit conflict row")

    unknowns = _list(payload["knownUnknowns"], "payload.knownUnknowns")
    unknown_ids = _unique(unknowns, "unknownId", "payload.knownUnknowns")
    missing_title_count = 0
    for index, row in enumerate(unknowns):
        path = f"payload.knownUnknowns[{index}]"
        obj = _object(row, path, {"affectedFactIds", "detail", "reasonCode", "scope", "status", "unknownId"})
        if obj["status"] != "unresolved":
            _fail(path + ".status", "known-unknown cannot be silently resolved")
        for fact_id in _list(obj["affectedFactIds"], path + ".affectedFactIds"):
            if fact_id not in all_facts:
                _fail(path + ".affectedFactIds", f"unknown affected fact {fact_id!r}")
        for key in ("detail", "reasonCode", "scope"):
            _string(obj[key], path + "." + key)
        if obj["reasonCode"] == "SOURCE_MOVE_TITLE_MISSING_OR_INTERNAL":
            missing_title_count += 1
    if missing_title_count != 18:
        _fail("payload.knownUnknowns", "all 18 missing source move titles must be individually classified")
    required_reasons = {
        "FORMULA_RUNTIME_CONTRACT_COVERAGE_INCOMPLETE", "LEGACY_PER_FACT_PROVENANCE_INCOMPLETE",
        "BROADER_WORLD_MODEL_FAMILIES_ABSENT",
    }
    actual_reasons = {row["reasonCode"] for row in unknowns}
    retired_e1_reasons = {"SCRIPTED_EVENT_BEHAVIOR_UNEXTRACTED", "SOURCE_ACT_PLACEMENT_ABSENT", "SOURCE_ROOM_CLASS_PLACEMENT_ABSENT", "OBSERVED_IDENTITY_ALIAS_JOIN_ABSENT", "ABSTRACT_BEHAVIOR_INHERITANCE_JOIN_ABSENT", "INITIAL_STATE_COVERAGE_ABSENT", "SOURCE_VS_STABLE_HP_ROUNDING_CONFLICT", "PRODUCTION_SEMANTICS_PENDING_E2D1B"}
    retired_lifecycle_reasons = {"LIFECYCLE_COVERAGE_REMAINING", "EVENT_BEHAVIOR_AGGREGATE_INCOMPLETE",
                                 "EVENT_LIFECYCLE_TIMEOUT_RESULT_UNEXTRACTED"}
    if actual_reasons & retired_e1_reasons:
        _fail("payload.knownUnknowns", "resolved E1 absence reason was retained")
    if actual_reasons & retired_lifecycle_reasons:
        _fail("payload.knownUnknowns", "resolved lifecycle reason was retained")
    if not required_reasons <= actual_reasons:
        _fail("payload.knownUnknowns", f"missing reason classifications {sorted(required_reasons-actual_reasons)!r}")

    readiness = _object(payload["readiness"], "payload.readiness", {"global", "root", "runtimeScopes"})
    for name in ("global", "root"):
        gate = _object(readiness[name], f"payload.readiness.{name}", {"ready", "reasonRefs", "status"})
        if gate["ready"] is not False or gate["status"] != "incomplete" or not set(gate["reasonRefs"]) <= unknown_ids:
            _fail(f"payload.readiness.{name}", "global/root readiness must be computed false/incomplete")
    scopes = _object(readiness["runtimeScopes"], "payload.readiness.runtimeScopes", {"encounterCompanion", "encounterProjection"})
    companion = _object(scopes["encounterCompanion"], "payload.readiness.runtimeScopes.encounterCompanion", {"ready", "reasonRefs", "status"})
    if (companion["ready"] is not False or companion["status"] != "incomplete"
            or companion["reasonRefs"] != ["UNKNOWN.FORMULA_RUNTIME_CONTRACTS"]):
        _fail("payload.readiness.runtimeScopes.encounterCompanion", "formula must remain the sole hard-false companion gate")
    projected = _object(scopes["encounterProjection"], "payload.readiness.runtimeScopes.encounterProjection", {"ready", "requiredCoverageFamilies", "requiredJoins", "status"})
    if projected["ready"] is not True or projected["status"] != "complete":
        _fail("payload.readiness.runtimeScopes.encounterProjection", "independent projection section should be complete")
    if projected["requiredCoverageFamilies"] != [row["family"] for row in coverage_rows()]:
        _fail("payload.readiness.runtimeScopes.encounterProjection.requiredCoverageFamilies", "coverage gate mismatch")
    expected_joins = {"encounterToMonster", "stateToModel", "registrationToBehaviorOwner", "graphTopology", "operationModel", "legacyToCanonical", "factToEvidence", "encounterPlacement", "eventEncounterLinkage", "observationIdentity", "behaviorApplicability", "initialStateOwnerApplicability", "initialStateFactRuntimeContract", "initialPowerHookClosure", "initialStateLegacyComparisons", "hpArithmeticAssignmentStorage", "eventTurnClassificationDependencies", "eventScriptOwnerEncounterLink", "eventScriptOptionDelegate", "eventScriptTransitionArguments", "eventScriptOutcomeDependency", "architectOwnerPlacementApplicability", "architectLocalizationStructure", "architectDialogueLineGraph", "architectOptionDelegates", "architectVisualOnlyLayout", "architectPresentationGameplayBoundary", "architectTerminalOrder", "architectDependencyRefs", "randomBranchRepeatWeight", "randomSelectionRuntime", "productionDiscovery", "coreAddDependencies", "productionProducerPool", "productionAvailabilityCapRepeat", "productionSlotFailure", "productionRuntimeState", "productionPostAddOrder", "productionLifecycleDependencies", "coreLifecycleApiDispatchRegistryRemovalTermination", "reachableListenerPhaseRelationshipDeathAddEventRunClosure"}
    if set(projected["requiredJoins"]) != expected_joins or len(projected["requiredJoins"]) != len(expected_joins):
        _fail("payload.readiness.runtimeScopes.encounterProjection.requiredJoins", "join gate mismatch")


def validate_artifact(artifact: Any, *, source: dict[str, Any], legacy: dict[str, Any]) -> None:
    """Validate the closed projection and every claim against its two inputs."""
    _validate_source_document(source)
    if not isinstance(legacy, dict):
        _fail("legacy", "malformed legacy input root")
    allowed_root = {"archive", "encounters", "meta", "retainedReferences"}
    unknown = set(legacy) - allowed_root
    missing = {"encounters", "meta"} - set(legacy)
    if unknown or missing:
        _fail("legacy", "malformed legacy input root")
    if legacy.get("meta", {}).get("targetVersion") != "v0.111.0" or legacy.get("meta", {}).get("targetBranch") != "public-beta":
        _fail("legacy.meta", "wrong legacy game version/branch")
    if len(legacy.get("encounters", {})) != 81:
        _fail("legacy.encounters", "expected exactly 81 current retained encounters")
    if "DOORMAKER_BOSS" in legacy.get("encounters", {}) or "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER" in legacy.get("encounters", {}):
        _fail("legacy.encounters", "archive/reference records must not occupy current encounters")
    archive = legacy.get("archive") or {}
    if set((archive.get("encounters") or {})) != {"DOORMAKER_BOSS"}:
        _fail("legacy.archive", "expected exactly archived DOORMAKER_BOSS")
    references = legacy.get("retainedReferences") or {}
    if set(references) != {"MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"}:
        _fail("legacy.retainedReferences", "expected exactly Mysterious Knight current reference")

    root = _object(artifact, "$", ROOT_KEYS)
    if root["schemaVersion"] != SCHEMA_VERSION:
        _fail("$.schemaVersion", f"expected {SCHEMA_VERSION}")
    if root["authority"] != AUTHORITY:
        _fail("$.authority", "authority/raw-only/patch-none policy mismatch or silent merge attempt")
    metadata = _object(root["metadata"], "$.metadata", METADATA_KEYS)
    if metadata["generator"] != {"name": GENERATOR_NAME, "version": GENERATOR_VERSION}:
        _fail("$.metadata.generator", "wrong deterministic generator identity")
    if metadata["sourceSchemaVersion"] != SOURCE_SCHEMA_VERSION or metadata["sourceExtractorVersion"] != SOURCE_EXTRACTOR_VERSION:
        _fail("$.metadata", "wrong source schema/extractor identity")
    if metadata["game"] != GAME:
        _fail("$.metadata.game", "wrong version/branch/commit/main assembly identity")
    if metadata["projectionInputs"] != PROJECTION_INPUTS:
        _fail("$.metadata.projectionInputs", "wrong exact source/legacy path/size/SHA-256")
    if metadata["embeddedSourceInputManifest"] != EMBEDDED_SOURCE_INPUTS:
        _fail("$.metadata.embeddedSourceInputManifest", "wrong exact embedded game input set")
    if metadata["embeddedSourceInputManifestSha256"] != witness_sha256(EMBEDDED_SOURCE_INPUTS):
        _fail("$.metadata.embeddedSourceInputManifestSha256", "canonical embedded-input-manifest digest mismatch")
    if metadata["requiredCoverage"] != coverage_rows():
        _fail("$.metadata.requiredCoverage", "required coverage status/denominator/numerator/unresolved mismatch")
    payload = _object(root["payload"], "$.payload", PAYLOAD_KEYS)
    if metadata["payloadSha256"] != witness_sha256(payload):
        _fail("$.metadata.payloadSha256", "canonical payload digest mismatch")

    source_sets = _validate_source_facts(payload["sourceFacts"], source)
    legacy_facts = _validate_legacy_annotations(payload["legacyAnnotations"], source_sets)
    _validate_evidence_and_refs(payload, source, legacy, source_sets["all"], legacy_facts)
    all_facts = source_sets["all"] | legacy_facts
    _validate_comparisons_conflicts_unknowns(payload, all_facts)

    # The closed schema above makes failures actionable.  Exact re-derivation is
    # the final anti-merge gate: no projected value may drift from either lane
    # while a caller merely updates the payload digest.
    from .builder import build_payload
    expected_payload = build_payload(source, legacy)
    if payload != expected_payload:
        _fail("$.payload", "payload differs from deterministic two-lane derivation")
