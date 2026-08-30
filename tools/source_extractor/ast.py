"""Canonical typed formula and roster-selection AST grammar.

The grammar is deliberately small.  Extraction may only emit these reviewed
nodes; validation rejects extension-by-accident, floats, malformed domains,
and excessive nesting.  ``evaluate_expression`` is a pure interpreter for the
normalized AST and never reads or invokes game code.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN
from typing import Any, Mapping

from .errors import SourceExtractionError

MAX_AST_DEPTH = 32
MAX_AST_NODES = 4096

_ROUNDING = {
    "ceiling": ROUND_CEILING,
    "floor": ROUND_FLOOR,
    "nearestEven": ROUND_HALF_EVEN,
    "truncateTowardZero": ROUND_DOWN,
}


def _fail(path: str, message: str) -> None:
    raise SourceExtractionError(f"malformed AST at {path}: {message}")


def _object(node: Any, path: str, keys: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(node, dict):
        _fail(path, "node must be an object")
    unknown = set(node) - keys
    missing = required - set(node)
    if unknown:
        _fail(path, f"unknown fields {sorted(unknown)!r}")
    if missing:
        _fail(path, f"missing fields {sorted(missing)!r}")
    return node


def _integer(value: Any, path: str, *, minimum: int | None = None) -> int:
    if type(value) is not int:
        _fail(path, "must be an integer")
    if minimum is not None and value < minimum:
        _fail(path, f"must be >= {minimum}")
    return value


def _decimal(value: Any, path: str) -> Decimal:
    if not isinstance(value, str):
        _fail(path, "decimal values must be canonical strings")
    try:
        result = Decimal(value)
    except Exception:
        _fail(path, "invalid decimal string")
    if not result.is_finite() or str(result) != value:
        _fail(path, "decimal string is not canonical")
    return result


def _model_ref(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.startswith("MONSTER."):
        _fail(path, "model must be a MONSTER.<canonical-id> reference")
    tail = value[8:]
    if not tail or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in tail):
        _fail(path, "invalid canonical model reference")
    return value


def validate_expression(node: Any, *, path: str = "$", expected_type: str | None = None) -> str:
    """Validate one expression and return its declared value type."""
    count = [0]

    def visit(value: Any, where: str, depth: int) -> str:
        count[0] += 1
        if count[0] > MAX_AST_NODES:
            _fail(where, f"node limit {MAX_AST_NODES} exceeded")
        if depth > MAX_AST_DEPTH:
            _fail(where, f"depth limit {MAX_AST_DEPTH} exceeded")
        if not isinstance(value, dict) or not isinstance(value.get("kind"), str):
            _fail(where, "expression requires string kind")
        kind = value["kind"]

        if kind == "constant":
            obj = _object(value, where, {"kind", "valueType", "value"}, {"kind", "valueType", "value"})
            value_type = obj["valueType"]
            if value_type == "integer":
                _integer(obj["value"], where + ".value")
            elif value_type == "decimal":
                _decimal(obj["value"], where + ".value")
            elif value_type == "boolean":
                if type(obj["value"]) is not bool:
                    _fail(where + ".value", "must be boolean")
            else:
                _fail(where + ".valueType", "unsupported constant type")
            return value_type

        if kind == "stateVariable":
            obj = _object(value, where, {"kind", "name", "valueType", "domain"}, {"kind", "name", "valueType", "domain"})
            if not isinstance(obj["name"], str) or not obj["name"]:
                _fail(where + ".name", "must be a nonempty string")
            value_type = obj["valueType"]
            domain = obj["domain"]
            if value_type == "integer":
                dom = _object(domain, where + ".domain", {"minimum", "maximum"}, {"minimum"})
                low = _integer(dom["minimum"], where + ".domain.minimum")
                if "maximum" in dom and _integer(dom["maximum"], where + ".domain.maximum") < low:
                    _fail(where + ".domain.maximum", "must not be below minimum")
            elif value_type == "decimal":
                dom = _object(domain, where + ".domain", {"minimum", "maximum"}, {"minimum"})
                low = _decimal(dom["minimum"], where + ".domain.minimum")
                if "maximum" in dom and _decimal(dom["maximum"], where + ".domain.maximum") < low:
                    _fail(where + ".domain.maximum", "must not be below minimum")
            elif value_type == "boolean":
                if domain != [False, True]:
                    _fail(where + ".domain", "boolean domain must be [false,true]")
            elif value_type in {"roomType", "enum"}:
                if not isinstance(domain, list) or not domain or any(not isinstance(x, str) or not x for x in domain) or len(set(domain)) != len(domain):
                    _fail(where + ".domain", "enum domain must contain unique nonempty strings")
            else:
                _fail(where + ".valueType", "unsupported state-variable type")
            return value_type

        if kind == "ascensionSelect":
            obj = _object(value, where, {"kind", "threshold", "below", "atOrAbove", "valueType"}, {"kind", "threshold", "below", "atOrAbove", "valueType"})
            _integer(obj["threshold"], where + ".threshold", minimum=0)
            result_type = obj["valueType"]
            if result_type not in {"integer", "decimal"}:
                _fail(where + ".valueType", "ascension result must be numeric")
            for key in ("below", "atOrAbove"):
                if visit(obj[key], where + "." + key, depth + 1) != result_type:
                    _fail(where + "." + key, "branch type mismatch")
            return result_type

        if kind == "arithmetic":
            obj = _object(value, where, {"kind", "operator", "operands", "valueType"}, {"kind", "operator", "operands", "valueType"})
            operator = obj["operator"]
            if operator not in {"add", "subtract", "multiply", "divide", "remainder"}:
                _fail(where + ".operator", "unsupported arithmetic operator")
            operands = obj["operands"]
            if not isinstance(operands, list) or len(operands) < 2 or (operator in {"subtract", "divide", "remainder"} and len(operands) != 2):
                _fail(where + ".operands", "invalid operand cardinality")
            result_type = obj["valueType"]
            if result_type not in {"integer", "decimal"}:
                _fail(where + ".valueType", "arithmetic result must be numeric")
            operand_types = [visit(item, f"{where}.operands[{i}]", depth + 1) for i, item in enumerate(operands)]
            if any(item not in {"integer", "decimal"} for item in operand_types):
                _fail(where + ".operands", "arithmetic operands must be numeric")
            inferred = "decimal" if "decimal" in operand_types or operator == "divide" else "integer"
            if inferred != result_type:
                _fail(where + ".valueType", f"must be {inferred}")
            return result_type

        if kind == "compare":
            obj = _object(value, where, {"kind", "operator", "left", "right", "valueType"}, {"kind", "operator", "left", "right", "valueType"})
            if obj["operator"] not in {"equal", "notEqual", "lessThan", "lessOrEqual", "greaterThan", "greaterOrEqual"}:
                _fail(where + ".operator", "unsupported comparison")
            if obj["valueType"] != "boolean":
                _fail(where + ".valueType", "comparison type must be boolean")
            left = visit(obj["left"], where + ".left", depth + 1)
            right = visit(obj["right"], where + ".right", depth + 1)
            if left != right:
                _fail(where, "comparison operand type mismatch")
            return "boolean"

        if kind == "conditional":
            obj = _object(value, where, {"kind", "condition", "whenTrue", "whenFalse", "valueType"}, {"kind", "condition", "whenTrue", "whenFalse", "valueType"})
            if visit(obj["condition"], where + ".condition", depth + 1) != "boolean":
                _fail(where + ".condition", "must be boolean")
            result_type = obj["valueType"]
            if visit(obj["whenTrue"], where + ".whenTrue", depth + 1) != result_type or visit(obj["whenFalse"], where + ".whenFalse", depth + 1) != result_type:
                _fail(where, "conditional branch type mismatch")
            return result_type

        if kind == "actRoomFactor":
            obj = _object(value, where, {"kind", "actIndex", "boss", "factors", "valueType"}, {"kind", "actIndex", "boss", "factors", "valueType"})
            if obj["valueType"] != "decimal":
                _fail(where + ".valueType", "factor type must be decimal")
            if visit(obj["actIndex"], where + ".actIndex", depth + 1) != "integer" or visit(obj["boss"], where + ".boss", depth + 1) != "boolean":
                _fail(where, "invalid act/boss inputs")
            factors = _object(obj["factors"], where + ".factors", {"act1", "act2", "act3NonBoss", "act3Boss"}, {"act1", "act2", "act3NonBoss", "act3Boss"})
            for key, item in factors.items():
                _decimal(item, where + ".factors." + key)
            return "decimal"

        if kind == "convert":
            obj = _object(value, where, {"kind", "expression", "fromType", "toType", "mode", "valueType"}, {"kind", "expression", "fromType", "toType", "mode", "valueType"})
            source_type = visit(obj["expression"], where + ".expression", depth + 1)
            if obj["fromType"] == "integer" and obj["toType"] == "decimal" and obj["valueType"] == "decimal" and obj["mode"] == "exact":
                if source_type != "integer": _fail(where + ".expression", "conversion source must be integer")
                return "decimal"
            if obj["fromType"] == "decimal" and obj["toType"] == "integer" and obj["valueType"] == "integer" and obj["mode"] in _ROUNDING:
                if source_type != "decimal": _fail(where + ".expression", "conversion source must be decimal")
                return "integer"
            _fail(where, "unsupported conversion")

        if kind == "range":
            obj = _object(value, where, {"kind", "minimum", "maximum", "valueType"}, {"kind", "minimum", "maximum", "valueType"})
            if obj["valueType"] != "integerRange":
                _fail(where + ".valueType", "range type must be integerRange")
            if visit(obj["minimum"], where + ".minimum", depth + 1) != "integer" or visit(obj["maximum"], where + ".maximum", depth + 1) != "integer":
                _fail(where, "range endpoints must be integer expressions")
            return "integerRange"

        if kind == "sourceField":
            obj = _object(value, where, {"kind", "symbol", "valueType"}, {"kind", "symbol", "valueType"})
            if not isinstance(obj["symbol"], str) or "::" not in obj["symbol"]:
                _fail(where + ".symbol", "must be a resolved field symbol")
            if obj["valueType"] not in {"integer", "decimal", "boolean"}:
                _fail(where + ".valueType", "unsupported source-field type")
            return obj["valueType"]

        if kind == "reference":
            allowed = {"kind", "reference", "valueType", "compiled", "arguments"}
            obj = _object(value, where, allowed, {"kind", "reference", "valueType"})
            if not isinstance(obj["reference"], str) or "::" not in obj["reference"]:
                _fail(where + ".reference", "must be a method symbol signature")
            if obj["valueType"] not in {"integer", "decimal", "boolean", "integerRange"}:
                _fail(where + ".valueType", "unsupported reference type")
            # Import locally to keep the AST module's basic grammar independent
            # while still enforcing the exact argument contract encoded by CIL.
            from .cil_eval import decode_method_signature
            signature = decode_method_signature(obj["reference"])
            if signature.parameters:
                if "arguments" not in obj:
                    _fail(where + ".arguments", "required by parameterized method signature")
                arguments = obj["arguments"]
                if not isinstance(arguments, list) or len(arguments) != len(signature.parameters):
                    _fail(where + ".arguments", f"must contain exactly {len(signature.parameters)} expressions")
                for index, (argument, parameter) in enumerate(zip(arguments, signature.parameters, strict=True)):
                    argument_type = visit(argument, f"{where}.arguments[{index}]", depth + 1)
                    expected = parameter.numeric
                    if expected is not None and argument_type != expected:
                        _fail(f"{where}.arguments[{index}]", f"must be {expected}")
            elif "arguments" in obj:
                _fail(where + ".arguments", "not allowed for an argument-free method signature")
            if "compiled" in obj:
                compiled_type = visit(obj["compiled"], where + ".compiled", depth + 1)
                if compiled_type != obj["valueType"]:
                    _fail(where + ".compiled", "compiled type mismatch")
            return obj["valueType"]

        if kind == "combatQuery":
            obj = _object(value, where, {"kind", "query", "arguments", "valueType"}, {"kind", "query", "valueType"})
            if obj["query"] not in {"powerAmount", "playerCount", "field", "modelChoice"}:
                _fail(where + ".query", "unsupported combat query")
            if "arguments" in obj:
                if not isinstance(obj["arguments"], list):
                    _fail(where + ".arguments", "must be a list")
                for i, item in enumerate(obj["arguments"]):
                    visit(item, f"{where}.arguments[{i}]", depth + 1)
            return obj["valueType"]

        _fail(where + ".kind", f"unsupported expression kind {kind!r}")
        raise AssertionError

    actual = visit(node, path, 0)
    if expected_type is not None and actual != expected_type:
        _fail(path, f"expected {expected_type}, got {actual}")
    return actual


def evaluate_expression(node: Any, state: Mapping[str, Any]) -> Any:
    """Evaluate a validated normalized expression against explicit state."""
    validate_expression(node)

    def visit(value: dict[str, Any]) -> Any:
        kind = value["kind"]
        if kind == "constant":
            return Decimal(value["value"]) if value["valueType"] == "decimal" else value["value"]
        if kind == "stateVariable":
            name = value["name"]
            if name not in state:
                raise SourceExtractionError(f"missing state input {name!r}")
            result = state[name]
            value_type = value["valueType"]
            if value_type == "integer" and type(result) is not int:
                raise SourceExtractionError(f"state input {name!r} must be integer")
            if value_type == "decimal":
                try: result = result if isinstance(result, Decimal) else Decimal(str(result))
                except Exception as exc: raise SourceExtractionError(f"state input {name!r} must be decimal") from exc
            if value_type == "boolean" and type(result) is not bool:
                raise SourceExtractionError(f"state input {name!r} must be boolean")
            domain = value["domain"]
            if value_type == "integer" and (result < domain["minimum"] or ("maximum" in domain and result > domain["maximum"])):
                raise SourceExtractionError(f"state input {name!r} outside declared domain")
            if value_type == "decimal" and (result < Decimal(domain["minimum"]) or ("maximum" in domain and result > Decimal(domain["maximum"]))):
                raise SourceExtractionError(f"state input {name!r} outside declared domain")
            if value_type in {"boolean", "enum", "roomType"} and result not in domain:
                raise SourceExtractionError(f"state input {name!r} outside declared domain")
            return result
        if kind == "ascensionSelect":
            ascension = state.get("ascension")
            if type(ascension) is not int or ascension < 0:
                raise SourceExtractionError("missing or invalid state input 'ascension'")
            return visit(value["atOrAbove"] if ascension >= value["threshold"] else value["below"])
        if kind == "arithmetic":
            values = [visit(item) for item in value["operands"]]
            if value["valueType"] == "decimal":
                values = [item if isinstance(item, Decimal) else Decimal(item) for item in values]
            if value["operator"] == "add": return sum(values)
            if value["operator"] == "multiply":
                result = values[0]
                for item in values[1:]: result *= item
                return result
            if value["operator"] == "subtract": return values[0] - values[1]
            if values[1] == 0:
                raise SourceExtractionError(f"{value['operator']} by zero")
            if value["operator"] == "remainder":
                # CLI rem truncates the quotient toward zero. Python integer
                # modulo instead follows floor division for negative values.
                left, right = values
                quotient = abs(left) // abs(right)
                if (left < 0) != (right < 0): quotient = -quotient
                return left - quotient * right
            return Decimal(values[0]) / Decimal(values[1])
        if kind == "compare":
            left, right = visit(value["left"]), visit(value["right"])
            return {"equal": left == right, "notEqual": left != right, "lessThan": left < right, "lessOrEqual": left <= right, "greaterThan": left > right, "greaterOrEqual": left >= right}[value["operator"]]
        if kind == "conditional": return visit(value["whenTrue"] if visit(value["condition"]) else value["whenFalse"])
        if kind == "actRoomFactor":
            act, boss = visit(value["actIndex"]), visit(value["boss"])
            if act == 0: key = "act1"
            elif act == 1: key = "act2"
            elif act == 2: key = "act3Boss" if boss else "act3NonBoss"
            else: raise SourceExtractionError("actIndex outside reviewed multiplayer domain 0..2")
            return Decimal(value["factors"][key])
        if kind == "convert":
            source = visit(value["expression"])
            if value["toType"] == "decimal": return Decimal(source)
            return int(source.to_integral_value(rounding=_ROUNDING[value["mode"]]))
        if kind == "range": return {"minimum": visit(value["minimum"]), "maximum": visit(value["maximum"])}
        if kind == "sourceField":
            name = "field:" + value["symbol"]
            if name not in state:
                raise SourceExtractionError(f"missing state input {name!r}")
            return state[name]
        if kind == "reference":
            if "compiled" in value: return visit(value["compiled"])
            raise SourceExtractionError(f"cannot evaluate unresolved method reference {value['reference']}")
        if kind == "combatQuery":
            name = "query:" + value["query"]
            if name not in state:
                raise SourceExtractionError(f"missing state input {name!r}")
            return state[name]
        raise AssertionError(kind)

    return visit(node)


def validate_selection(node: Any, *, path: str = "$", known_models: set[str] | None = None) -> tuple[int, int, set[str]]:
    """Validate roster AST and return (minimum bodies, maximum bodies, members)."""
    count = [0]

    def visit(value: Any, where: str, depth: int) -> tuple[int, int, set[str]]:
        count[0] += 1
        if count[0] > MAX_AST_NODES: _fail(where, f"node limit {MAX_AST_NODES} exceeded")
        if depth > MAX_AST_DEPTH: _fail(where, f"depth limit {MAX_AST_DEPTH} exceeded")
        if not isinstance(value, dict) or not isinstance(value.get("kind"), str): _fail(where, "selection requires string kind")
        kind = value["kind"]
        common = {"kind", "provenance"}
        if "provenance" in value:
            p = value["provenance"]
            if not isinstance(p, dict) or not isinstance(p.get("semanticWitnessSha256"), str) or len(p["semanticWitnessSha256"]) != 64:
                _fail(where + ".provenance", "requires semanticWitnessSha256")
        if kind == "fixed":
            obj = _object(value, where, common | {"model"}, {"kind", "model"})
            model = _model_ref(obj["model"], where + ".model")
            if known_models is not None and model not in known_models: _fail(where + ".model", "unresolved model")
            return 1, 1, {model}
        if kind == "sequence":
            obj = _object(value, where, common | {"children", "order"}, {"kind", "children", "order"})
            if obj["order"] not in {"fixed", "rngSelected"}: _fail(where + ".order", "unsupported sequence order")
            if not isinstance(obj["children"], list) or not obj["children"]: _fail(where + ".children", "must be nonempty")
            rows = [visit(item, f"{where}.children[{i}]", depth + 1) for i, item in enumerate(obj["children"])]
            return sum(x[0] for x in rows), sum(x[1] for x in rows), set().union(*(x[2] for x in rows))
        if kind in {"uniformChoice", "weightedChoice"}:
            keys = common | {"choices"} | ({"weights"} if kind == "weightedChoice" else set())
            obj = _object(value, where, keys, {"kind", "choices"} | ({"weights"} if kind == "weightedChoice" else set()))
            if not isinstance(obj["choices"], list) or len(obj["choices"]) < 2: _fail(where + ".choices", "requires at least two choices")
            rows = [visit(item, f"{where}.choices[{i}]", depth + 1) for i, item in enumerate(obj["choices"])]
            if kind == "weightedChoice":
                if not isinstance(obj["weights"], list) or len(obj["weights"]) != len(rows) or any(type(x) is not int or x <= 0 for x in obj["weights"]): _fail(where + ".weights", "must be positive integer weights")
            return min(x[0] for x in rows), max(x[1] for x in rows), set().union(*(x[2] for x in rows))
        if kind == "repeat":
            obj = _object(value, where, common | {"count", "selection", "draws"}, {"kind", "count", "selection", "draws"})
            n = _integer(obj["count"], where + ".count", minimum=1)
            if obj["draws"] not in {"independent", "withoutReplacement"}: _fail(where + ".draws", "unsupported draw relation")
            low, high, members = visit(obj["selection"], where + ".selection", depth + 1)
            return n * low, n * high, members
        if kind == "permutation":
            obj = _object(value, where, common | {"selection"}, {"kind", "selection"})
            return visit(obj["selection"], where + ".selection", depth + 1)
        if kind == "filteredChoice":
            obj = _object(value, where, common | {"choices", "constraint", "draws", "count"}, {"kind", "choices", "constraint", "draws", "count"})
            if obj["constraint"] not in {"modelCountLimit", "excludePreviouslySelected"}: _fail(where + ".constraint", "unsupported filter")
            if obj["draws"] != "withoutReplacement": _fail(where + ".draws", "filtered choices must be without replacement")
            n = _integer(obj["count"], where + ".count", minimum=1)
            if not isinstance(obj["choices"], list) or len(obj["choices"]) < n: _fail(where + ".choices", "not enough choices")
            rows = [visit(item, f"{where}.choices[{i}]", depth + 1) for i, item in enumerate(obj["choices"])]
            if any(x[0] != 1 or x[1] != 1 for x in rows): _fail(where + ".choices", "filtered choice members must each produce one body")
            return n, n, set().union(*(x[2] for x in rows))
        _fail(where + ".kind", f"unsupported selection kind {kind!r}")
        raise AssertionError

    return visit(node, path, 0)


OPERATION_KINDS = {
    "attack", "attackHitCount", "applyPower", "gainBlock", "addStatusCard",
    "addGeneratedCard", "summon", "escape", "heal", "removeCard",
    "kill", "removePower", "stateWrite", "helperEffect", "transition",
}

GRAPH_NODE_KINDS = {"move", "random", "conditional"}


def validate_operation(node: Any, *, path: str = "$") -> None:
    if not isinstance(node, dict) or not isinstance(node.get("kind"), str):
        _fail(path, "operation requires string kind")
    kind = node["kind"]
    if kind not in OPERATION_KINDS:
        _fail(path + ".kind", f"unsupported operation kind {kind!r}")
    common = {"kind", "operationId", "provenance"}
    if kind == "transition":
        _object(node, path, common | {"transition", "sourceOrder", "target"}, {"kind", "operationId", "transition", "provenance"})
        if node["transition"] not in {"noOp", "nonnumericOrStateUpdate"}: _fail(path + ".transition", "unsupported transition")
        return
    if kind == "helperEffect":
        obj = _object(node, path, common | {"helper", "helperSymbolSignature", "helperCallSites", "sourceOrder"}, {"kind", "operationId", "helper", "helperSymbolSignature", "helperCallSites", "provenance"})
        if obj["helper"] not in {"reattach", "fabricate", "chooseCurse", "hatch", "pressureState"}: _fail(path + ".helper", "unsupported helper")
        if not isinstance(obj["helperSymbolSignature"], str) or " sig:" not in obj["helperSymbolSignature"]: _fail(path + ".helperSymbolSignature", "must identify exact helper")
        if not isinstance(obj["helperCallSites"], list) or not obj["helperCallSites"]: _fail(path + ".helperCallSites", "must be nonempty")
        for index, call in enumerate(obj["helperCallSites"]):
            call = _object(call, f"{path}.helperCallSites[{index}]", {"sourceOrder", "symbolSignature"}, {"sourceOrder", "symbolSignature"})
            _integer(call["sourceOrder"], f"{path}.helperCallSites[{index}].sourceOrder", minimum=0)
            if not isinstance(call["symbolSignature"], str) or " sig:" not in call["symbolSignature"]: _fail(f"{path}.helperCallSites[{index}].symbolSignature", "must identify exact helper call")
        return
    allowed = common | {"sinkSymbolSignature", "sourceOrder", "value", "model", "modelContract", "target", "destination", "selection", "targetProvenance", "force", "memberSymbolSignature"}
    required_by_kind = {
        "attack": {"value", "target", "targetProvenance"},
        "attackHitCount": {"value"}, "applyPower": {"value", "target", "model"},
        "gainBlock": {"value", "target"}, "addStatusCard": {"value", "target", "model"},
        "addGeneratedCard": {"target", "destination", "model"},
        "summon": {"target", "selection", "model"}, "escape": {"target"},
        "heal": {"value", "target"}, "removeCard": {"target"},
        "kill": {"target", "force"}, "removePower": {"target"},
        "stateWrite": {"target", "value", "memberSymbolSignature"},
    }
    obj = _object(node, path, allowed, common | {"sinkSymbolSignature"} | required_by_kind[kind])
    if "value" in obj: validate_expression(obj["value"], path=path + ".value")
    target_kinds = {
        "allOpponentsOfSourceMonster", "sourceMonster", "registeredTargets", "registeredTarget",
        "iteratedCreature", "resolvedMonsterCreature", "awaitedSummonedCreature",
        "sourceMonsterTeammates", "generatedCardCombatPile", "sourceMonsterCombatState",
        "selectedCombatCard", "rngSelectedCombatCard", "runtimeSelectedPowerInstance",
    }
    if "target" in obj and obj["target"] not in target_kinds: _fail(path + ".target", "unsupported evidence-backed target")
    if "model" in obj:
        expected = {"applyPower":"POWER.", "removePower":"POWER.", "addStatusCard":"CARD.", "addGeneratedCard":"CARD.", "summon":"MONSTER."}.get(kind)
        if expected is None or not isinstance(obj["model"], str) or not obj["model"].startswith(expected): _fail(path + ".model", "invalid operation model category")
    if kind == "removePower":
        if ("model" in obj) == ("modelContract" in obj):
            _fail(path, "removePower requires exactly one of model or modelContract")
        if "modelContract" in obj:
            contract = _object(obj["modelContract"], path + ".modelContract",
                               {"classification", "sourceKinds", "sourceSymbolSignature"},
                               {"classification", "sourceKinds", "sourceSymbolSignature"})
            if contract["classification"] != "runtimeSelectedPowerInstance":
                _fail(path + ".modelContract.classification", "unsupported runtime Power contract")
            if not isinstance(contract["sourceKinds"], list) or not contract["sourceKinds"] or any(not isinstance(x, str) or not x for x in contract["sourceKinds"]):
                _fail(path + ".modelContract.sourceKinds", "must be a nonempty string list")
            if not isinstance(contract["sourceSymbolSignature"], str) or "::get_Current sig:" not in contract["sourceSymbolSignature"]:
                _fail(path + ".modelContract.sourceSymbolSignature", "must identify the exact iterator current getter")
    if kind == "kill":
        validate_expression(obj["force"], path=path + ".force", expected_type="boolean")
    if kind == "stateWrite":
        if not isinstance(obj["memberSymbolSignature"], str) or "::set_" not in obj["memberSymbolSignature"] or " sig:" not in obj["memberSymbolSignature"]:
            _fail(path + ".memberSymbolSignature", "must identify an exact source setter")
    if "destination" in obj:
        destination=_object(obj["destination"],path+".destination",{"pileType"},{"pileType"})
        validate_expression(destination["pileType"],path=path+".destination.pileType",expected_type="integer")
    if "selection" in obj:
        selection=_object(obj["selection"],path+".selection",{"slot"},{"slot"})
        if selection["slot"] not in {"automaticCombatSlot","namedCombatSlot","nextOpenCombatSlot","selectedAvailableCombatSlot","selectedCombatSlot","stateCombatSlot"}: _fail(path+".selection.slot","unsupported slot selection")
    if kind == "attack":
        proof=_object(obj["targetProvenance"],path+".targetProvenance",{
            "assemblySha256","cilInstructionsSha256","diagnosticMetadataToken","metadataSignature",
            "methodBodySha256","normalizedInstructionsSha256","symbolSignature","normalizedSliceSha256","semanticWitnessSha256"},
            {"assemblySha256","cilInstructionsSha256","metadataSignature","methodBodySha256","normalizedInstructionsSha256","symbolSignature","normalizedSliceSha256","semanticWitnessSha256"})
        for key in ("assemblySha256","cilInstructionsSha256","methodBodySha256","normalizedInstructionsSha256","normalizedSliceSha256","semanticWitnessSha256"):
            if not isinstance(proof[key],str) or len(proof[key])!=64 or any(c not in "0123456789abcdef" for c in proof[key]): _fail(path+".targetProvenance."+key,"must be SHA-256")


def validate_graph(node: Any, *, known_moves: set[str] | None = None, path: str = "$") -> None:
    obj = _object(node, path, {"canonicalMonster", "graphId", "sourceType", "topology", "provenance", "nodes", "edges", "initial"}, {"canonicalMonster", "graphId", "sourceType", "topology", "provenance"})
    if "nodes" in obj:
        if not isinstance(obj["nodes"], list) or not obj["nodes"]:
            _fail(path + ".nodes", "must be nonempty")
        ids = set()
        for i, item in enumerate(obj["nodes"]):
            n = _object(item, f"{path}.nodes[{i}]", {"kind", "nodeId", "stateId", "moveId", "mustPerformOnce", "provenance"}, {"kind", "nodeId"})
            if n["kind"] not in GRAPH_NODE_KINDS:
                _fail(f"{path}.nodes[{i}].kind", f"unsupported graph node {n['kind']!r}")
            if n["nodeId"] in ids:
                _fail(f"{path}.nodes[{i}].nodeId", "duplicate graph node")
            ids.add(n["nodeId"])
            if known_moves is not None and n["kind"] == "move" and n.get("moveId") not in known_moves:
                _fail(f"{path}.nodes[{i}].moveId", "unresolved move")
        if "initial" in obj:
            initials = obj["initial"] if isinstance(obj["initial"], list) else [obj["initial"]]
            if not initials or any(initial not in ids for initial in initials):
                _fail(path + ".initial", "unresolved initial node")
        if "edges" in obj:
            if not isinstance(obj["edges"], list):
                _fail(path + ".edges", "must be a list")
            repeat_names = {0: "CanRepeatForever", 1: "CanRepeatXTimes", 2: "CannotRepeat", 3: "UseOnlyOnce"}
            def float_expression(value: Any, where: str) -> None:
                if not isinstance(value, dict) or value.get("valueType") != "float":
                    _fail(where, "weight expression must be typed float")
                if value.get("kind") == "constant":
                    if set(value) != {"kind", "value", "valueType"} or not isinstance(value["value"], (int, float)) or isinstance(value["value"], bool):
                        _fail(where, "malformed float constant")
                elif value.get("kind") == "conditional":
                    if set(value) != {"condition", "kind", "valueType", "whenFalse", "whenTrue"}:
                        _fail(where, "malformed float conditional")
                    condition = value["condition"]
                    if not isinstance(condition, dict) or set(condition) != {"kind", "symbolSignature", "valueType"} or condition["kind"] != "methodBoolean" or condition["valueType"] != "boolean":
                        _fail(where + ".condition", "malformed Boolean runtime contract")
                    float_expression(value["whenFalse"], where + ".whenFalse")
                    float_expression(value["whenTrue"], where + ".whenTrue")
                else:
                    _fail(where + ".kind", "unsupported float weight expression")
            for i, item in enumerate(obj["edges"]):
                where = f"{path}.edges[{i}]"
                e = _object(item, where, {"kind", "from", "to", "weight", "predicate", "order", "provenance", "repeat", "cooldown", "overload", "sourceOrder"}, {"kind", "from", "to"})
                if e["kind"] not in {"followUp", "randomBranch", "conditionalBranch"}:
                    _fail(where + ".kind", "unsupported edge")
                if e["from"] not in ids or e["to"] not in ids:
                    _fail(where, "edge refers to unknown node")
                if e["kind"] == "randomBranch":
                    required = {"kind", "from", "to", "weight", "order", "repeat", "cooldown", "overload", "sourceOrder"}
                    if set(e) != required:
                        _fail(where, "random branch fields are incomplete or contain legacy predicate semantics")
                    if type(e["order"]) is not int or e["order"] < 0 or type(e["sourceOrder"]) is not int or e["sourceOrder"] < 0:
                        _fail(where, "random branch order/sourceOrder must be nonnegative integers")
                    if type(e["cooldown"]) is not int or e["cooldown"] < 0:
                        _fail(where + ".cooldown", "must be a nonnegative integer")
                    repeat = _object(e["repeat"], where + ".repeat", {"enumName", "enumValue", "maximumConsecutiveUses"}, {"enumName", "enumValue"})
                    if repeat_names.get(repeat["enumValue"]) != repeat["enumName"]:
                        _fail(where + ".repeat", "MoveRepeatType name/value mismatch")
                    if repeat["enumValue"] == 1:
                        if type(repeat.get("maximumConsecutiveUses")) is not int or repeat["maximumConsecutiveUses"] < 1:
                            _fail(where + ".repeat", "CanRepeatXTimes requires a positive maximum")
                    elif "maximumConsecutiveUses" in repeat:
                        _fail(where + ".repeat", "repeat maximum supplied for wrong enum")
                    overload = _object(e["overload"], where + ".overload", {"metadataSignature", "symbolSignature"}, {"metadataSignature", "symbolSignature"})
                    if not overload["symbolSignature"].startswith("MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine.RandomBranchState::AddBranch sig:") or overload["metadataSignature"] != overload["symbolSignature"].split(" sig:", 1)[1]:
                        _fail(where + ".overload", "AddBranch signature mismatch")
                    weight = e["weight"]
                    if not isinstance(weight, dict) or weight.get("valueType") != "float":
                        _fail(where + ".weight", "must be typed float")
                    if weight.get("kind") == "constant":
                        float_expression(weight, where + ".weight")
                    elif weight.get("kind") == "delegate":
                        allowed = {"expression", "kind", "receiver", "targetMethod", "valueType", "runtimeContract"}
                        required_weight = {"expression", "kind", "receiver", "targetMethod", "valueType"}
                        if set(weight) - allowed or not required_weight <= set(weight):
                            _fail(where + ".weight", "malformed float delegate")
                        target = weight["targetMethod"]
                        if not isinstance(target, dict) or not target.get("symbolSignature", "").endswith(" sig:20000c"):
                            _fail(where + ".weight.targetMethod", "delegate target is not parameterless float")
                        float_expression(weight["expression"], where + ".weight.expression")
                        if ("runtimeContract" in weight) != (weight["expression"].get("kind") == "conditional"):
                            _fail(where + ".weight.runtimeContract", "runtime condition join mismatch")
                    else:
                        _fail(where + ".weight.kind", "unsupported random weight source")
                elif any(key in e for key in {"repeat", "cooldown", "overload", "sourceOrder", "weight"}):
                    _fail(where, "random-only semantic field on non-random edge")
