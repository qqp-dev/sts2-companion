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
            if operator not in {"add", "subtract", "multiply", "divide"}:
                _fail(where + ".operator", "unsupported arithmetic operator")
            operands = obj["operands"]
            if not isinstance(operands, list) or len(operands) < 2 or (operator in {"subtract", "divide"} and len(operands) != 2):
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
            if values[1] == 0: raise SourceExtractionError("division by zero")
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
