"""Fail-closed validation for source input and compact C0 projection schema."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from source_extractor.ast import (
    GRAPH_NODE_KINDS, OPERATION_KINDS, validate_expression, validate_operation,
    validate_selection,
)
from source_extractor.canonical import witness_sha256
from source_extractor.errors import SourceExtractionError
from source_extractor.identity import validate_observation_identities
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
        _fail("source", "schema 5 must remain incomplete and not runtime-ready")
    for family, (status, denominator, numerator, unresolved) in REQUIRED_COVERAGE.items():
        expected = {"denominator": denominator, "numerator": numerator, "status": status, "unresolved": unresolved}
        try:
            actual = _source_coverage(source, family)
        except (KeyError, TypeError) as exc:
            _fail(f"source.coverage.{family}", f"missing required coverage: {exc}")
        if actual != expected:
            _fail(f"source.coverage.{family}", f"coverage mismatch: expected {expected!r}, got {actual!r}")

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
    if len(registrations) != 307:
        _fail("source.behavior.registrations", "expected 307 registrations")
    move_ids = _unique(registrations, "canonicalId", "source.behavior.registrations")
    operation_ids: set[str] = set()
    for index, row in enumerate(registrations):
        for op_index, operation in enumerate(row["operations"]):
            validate_operation(operation, path=f"source.behavior.registrations[{index}].operations[{op_index}]")
            op_id = operation["operationId"]
            if op_id in operation_ids:
                _fail(f"source.behavior.registrations[{index}].operations[{op_index}].operationId", "duplicate operation ID")
            operation_ids.add(op_id)
    graphs = source["behavior"]["graphs"]
    if len(graphs) != 100:
        _fail("source.behavior.graphs", "expected 100 behavior graphs")
    _unique(graphs, "graphId", "source.behavior.graphs")
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


def _validate_source_facts(source_facts: Any) -> dict[str, set[str]]:
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
        expected_count = 9 if family == "cards" else 43
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
    if len(owners) != 100:
        _fail("payload.sourceFacts.behaviorOwners", "expected 100 behavior owners")
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
            if obj.get("modelRef") != f"SOURCE.{owner}" or owner not in model_ids or obj["applicabilityKind"] != "directModel" or applicable != [owner]:
                _fail(path, "broken direct behavior-owner model join")
        elif obj["classification"] == "abstractBehavior":
            if "modelRef" in obj or obj["applicabilityKind"] != "inheritedBehavior":
                _fail(path, "abstract behavior owner lacks explicit inheritance applicability")
        else:
            _fail(path + ".classification", "unsupported owner classification")

    owner_applicability = {row["canonicalMonster"]: row["applicableConcreteModels"] for row in owners}

    move_rows = _list(sf["moves"], "payload.sourceFacts.moves")
    if len(move_rows) != 307:
        _fail("payload.sourceFacts.moves", "expected 307 move registrations")
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
    if len(graph_rows) != 100:
        _fail("payload.sourceFacts.graphs", "expected 100 graphs")
    graph_ids = set()
    graph_fact_ids = set()
    for index, row in enumerate(graph_rows):
        path = f"payload.sourceFacts.graphs[{index}]"
        obj = _object(row, path, {"applicableConcreteModels", "canonicalMonster", "edges", "factId", "graphId", "initial", "nodes", "sourceType", "topology"})
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
        initial = obj["initial"]
        initials = initial if isinstance(initial, list) else [initial]
        if not initials or any(item not in node_ids for item in initials):
            _fail(path + ".initial", "unknown graph initial node")
        for edge_index, edge in enumerate(_list(obj["edges"], path + ".edges")):
            ep = f"{path}.edges[{edge_index}]"
            eo = _object(edge, ep, {"from", "kind", "order", "predicate", "to", "weight"}, {"from", "kind", "to"})
            if eo["kind"] not in {"followUp", "randomBranch", "conditionalBranch"}:
                _fail(ep + ".kind", "unsupported graph edge kind")
            if eo["from"] not in node_ids or eo["to"] not in node_ids:
                _fail(ep, "edge refers to unknown node")
            if "predicate" in eo:
                validate_expression(eo["predicate"], path=ep + ".predicate", expected_type="boolean")
        topology = _object(obj["topology"], path + ".topology", {
            "conditionalBranches", "conditionalNodes", "followUpEdges", "moveNodes",
            "mustOnceFlags", "randomBranches", "randomNodes",
        })
        for key, value in topology.items():
            _integer(value, path + ".topology." + key)

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

    scaling = _object(sf["scaling"], "payload.sourceFacts.scaling", {"block", "hp", "ordinaryMonsterAttack", "power"})
    scaling_fact_ids = set()
    for name, row in scaling.items():
        obj = _object(row, f"payload.sourceFacts.scaling.{name}", {"factId", "rule"})
        scaling_fact_ids.add(_string(obj["factId"], f"payload.sourceFacts.scaling.{name}.factId", prefix="SOURCE.SCALING."))
        _walk_expressions(obj["rule"], f"payload.sourceFacts.scaling.{name}.rule")

    if not {row["graphId"] for row in move_rows} <= graph_ids:
        _fail("payload.sourceFacts.moves", "move refers to unknown graph")
    all_source_facts = (
        encounter_fact_ids | monster_fact_ids | state_fact_ids | referenced_fact_ids |
        owner_fact_ids | move_fact_ids | graph_fact_ids | scaling_fact_ids | placement_fact_ids |
        identity_fact_ids | {state_rules["factId"]}
    )
    return {
        "all": all_source_facts, "encounters": encounter_fact_ids, "models": model_ids,
        "moves": move_fact_ids, "operations": operation_ids,
    }

_LEGACY_BODY_FIELDS = {
    "count", "displayName", "hpA8", "monsterId", "moves", "pack", "patchChecked",
    "pattern", "role", "sourceFlags", "sourcePage", "startsWithA9", "type",
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
                    "count", "displayName", "hpA8", "monsterId", "moves", "pattern", "sourcePage", "type",
                })
                _string(body_annotations["monsterId"], bp + ".annotations.monsterId")
                _string(body_annotations["displayName"], bp + ".annotations.displayName")
                _integer(body_annotations["count"], bp + ".annotations.count", minimum=1)
                hp = _list(body_annotations["hpA8"], bp + ".annotations.hpA8")
                if len(hp) not in {1, 2} or any(type(item) is not int or item <= 0 for item in hp):
                    _fail(bp + ".annotations.hpA8", "must be a one/two endpoint positive integer range")
                pattern = _object(body_annotations["pattern"], bp + ".annotations.pattern", {"text", "type"})
                _string(pattern["text"], bp + ".annotations.pattern.text")
                _string(pattern["type"], bp + ".annotations.pattern.type")
                _string(body_annotations["sourcePage"], bp + ".annotations.sourcePage")
                for move_index, move in enumerate(_list(body_annotations["moves"], bp + ".annotations.moves")):
                    mp = f"{bp}.annotations.moves[{move_index}]"
                    mo = _object(move, mp, {"intent", "name", "textA9"}, {"name", "textA9"})
                    _string(mo["name"], mp + ".name")
                    _string(mo["textA9"], mp + ".textA9")
                    if "intent" in mo:
                        _string(mo["intent"], mp + ".intent")
                _validate_provenance_status(bo["provenanceStatus"], bp + ".provenanceStatus", encounter=False)
    if "DOORMAKER_BOSS" in current_ids:
        _fail("payload.legacyAnnotations.current", "Doormaker must not be current")

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
    comparisons = _list(payload["laneComparisons"], "payload.laneComparisons")
    comparison_ids = _unique(comparisons, "comparisonId", "payload.laneComparisons")
    conflict_comparisons = set()
    for index, row in enumerate(comparisons):
        path = f"payload.laneComparisons[{index}]"
        obj = _object(row, path, {"comparisonId", "family", "left", "reasonCode", "right", "status"}, {"comparisonId", "family", "left", "right", "status"})
        if obj["family"] not in {"encounterTitle", "monsterTitle", "initialHpA8SinglePlayer", "encounterActPlacement", "encounterRoomClass", "observedMonsterIdentity"}:
            _fail(path + ".family", "unsupported overlap family")
        if obj["status"] not in {"agrees", "conflict", "notStaticallyComparable"}:
            _fail(path + ".status", "unsupported overlap classification")
        if (obj["status"] == "notStaticallyComparable") != ("reasonCode" in obj):
            _fail(path, "not-comparable overlap requires exactly one reason code")
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
        "INITIAL_STATE_COVERAGE_ABSENT", "EVENT_BEHAVIOR_COVERAGE_ABSENT",
        "SOURCE_VS_STABLE_HP_ROUNDING_CONFLICT", "LEGACY_PER_FACT_PROVENANCE_INCOMPLETE",
        "BROADER_WORLD_MODEL_FAMILIES_ABSENT",
    }
    actual_reasons = {row["reasonCode"] for row in unknowns}
    retired_e1_reasons = {"SOURCE_ACT_PLACEMENT_ABSENT", "SOURCE_ROOM_CLASS_PLACEMENT_ABSENT", "OBSERVED_IDENTITY_ALIAS_JOIN_ABSENT", "ABSTRACT_BEHAVIOR_INHERITANCE_JOIN_ABSENT"}
    if actual_reasons & retired_e1_reasons:
        _fail("payload.knownUnknowns", "resolved E1 absence reason was retained")
    if not required_reasons <= actual_reasons:
        _fail("payload.knownUnknowns", f"missing reason classifications {sorted(required_reasons-actual_reasons)!r}")

    readiness = _object(payload["readiness"], "payload.readiness", {"global", "root", "runtimeScopes"})
    for name in ("global", "root"):
        gate = _object(readiness[name], f"payload.readiness.{name}", {"ready", "reasonRefs", "status"})
        if gate["ready"] is not False or gate["status"] != "incomplete" or not set(gate["reasonRefs"]) <= unknown_ids:
            _fail(f"payload.readiness.{name}", "global/root readiness must be computed false/incomplete")
    scopes = _object(readiness["runtimeScopes"], "payload.readiness.runtimeScopes", {"encounterCompanion", "encounterProjection"})
    companion = _object(scopes["encounterCompanion"], "payload.readiness.runtimeScopes.encounterCompanion", {"ready", "reasonRefs", "status"})
    if companion["ready"] is not False or companion["status"] != "incomplete" or not companion["reasonRefs"]:
        _fail("payload.readiness.runtimeScopes.encounterCompanion", "E1 companion scope cannot be ready")
    projected = _object(scopes["encounterProjection"], "payload.readiness.runtimeScopes.encounterProjection", {"ready", "requiredCoverageFamilies", "requiredJoins", "status"})
    if projected["ready"] is not True or projected["status"] != "complete":
        _fail("payload.readiness.runtimeScopes.encounterProjection", "independent projection section should be complete")
    if projected["requiredCoverageFamilies"] != [row["family"] for row in coverage_rows()]:
        _fail("payload.readiness.runtimeScopes.encounterProjection.requiredCoverageFamilies", "coverage gate mismatch")
    expected_joins = {"encounterToMonster", "stateToModel", "registrationToBehaviorOwner", "graphTopology", "operationModel", "legacyToCanonical", "factToEvidence", "encounterPlacement", "eventEncounterLinkage", "observationIdentity", "behaviorApplicability"}
    if set(projected["requiredJoins"]) != expected_joins or len(projected["requiredJoins"]) != len(expected_joins):
        _fail("payload.readiness.runtimeScopes.encounterProjection.requiredJoins", "join gate mismatch")


def validate_artifact(artifact: Any, *, source: dict[str, Any], legacy: dict[str, Any]) -> None:
    """Validate the closed projection and every claim against its two inputs."""
    _validate_source_document(source)
    if not isinstance(legacy, dict) or set(legacy) != {"encounters", "meta"}:
        _fail("legacy", "malformed legacy input root")
    if legacy.get("meta", {}).get("targetVersion") != "v0.111.0" or legacy.get("meta", {}).get("targetBranch") != "public-beta":
        _fail("legacy.meta", "wrong legacy game version/branch")
    if len(legacy.get("encounters", {})) != 82:
        _fail("legacy.encounters", "expected exactly 82 legacy records")

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

    source_sets = _validate_source_facts(payload["sourceFacts"])
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
