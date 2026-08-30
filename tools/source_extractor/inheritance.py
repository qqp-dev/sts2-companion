"""Exact metadata inheritance joins for behavior-owner applicability.

The resolver is intentionally independent of dnfile. Production callers pass
TypeDef.Extends relations read by :mod:`metadata`; tests pass synthetic
relations. Names are exact, case-sensitive CLI identities -- no suffix or
lookalike matching is permitted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .canonical import witness_sha256
from .errors import SourceExtractionError


def _chain_to_root(
    source_type: str,
    base_by_type: Mapping[str, str],
    *,
    declared_types: set[str],
    external_roots: set[str],
) -> list[str]:
    """Return ``source_type`` through its terminal base, rejecting bad graphs."""
    chain = [source_type]
    seen = {source_type}
    current = source_type
    while current in base_by_type:
        base = base_by_type[current]
        if not isinstance(base, str) or not base:
            raise SourceExtractionError(f"invalid base type for {current!r}")
        if base in seen:
            raise SourceExtractionError(
                "inheritance cycle: " + " -> ".join(chain + [base])
            )
        if base not in declared_types and base not in external_roots:
            raise SourceExtractionError(
                f"unresolved base type {base!r} referenced by {current!r}"
            )
        chain.append(base)
        seen.add(base)
        current = base
    if current not in external_roots:
        raise SourceExtractionError(
            f"type hierarchy for {source_type!r} terminates at unresolved {current!r}"
        )
    return chain


def resolve_behavior_applicability(
    *,
    base_by_type: Mapping[str, str],
    behavior_owner_types: Sequence[str],
    concrete_models: Sequence[Mapping[str, Any]],
    reachable_models: set[str],
    assembly_sha256: str,
    external_roots: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Join every exact behavior owner to every reachable concrete descendant.

    The denominator comes from the behavior graph owners. A relation is valid
    only through identity-equal TypeDef.Extends edges. Every owner must have at
    least one concrete reachable applicability; duplicate type/model identities
    and unresolved/cyclic hierarchies fail the family.
    """
    roots = set(external_roots or {"System.Object", "System.ValueType"})
    owners = list(behavior_owner_types)
    if any(not isinstance(owner, str) or not owner for owner in owners):
        raise SourceExtractionError("behavior owner type must be a nonempty exact identity")
    if len(set(owners)) != len(owners):
        raise SourceExtractionError("duplicate behavior owner source type")

    type_to_model: dict[str, str] = {}
    model_to_type: dict[str, str] = {}
    for row in concrete_models:
        source_type = row.get("sourceType")
        canonical = row.get("canonicalId")
        if not isinstance(source_type, str) or not source_type:
            raise SourceExtractionError("concrete model missing exact sourceType")
        if not isinstance(canonical, str) or not canonical:
            raise SourceExtractionError(f"concrete model {source_type!r} missing canonicalId")
        model = canonical if canonical.startswith("MONSTER.") else "MONSTER." + canonical
        if source_type in type_to_model:
            raise SourceExtractionError(f"ambiguous concrete source type {source_type!r}")
        if model in model_to_type:
            raise SourceExtractionError(f"duplicate canonical monster model {model!r}")
        type_to_model[source_type] = model
        model_to_type[model] = source_type

    missing_reachable = reachable_models - set(model_to_type)
    if missing_reachable:
        raise SourceExtractionError(
            f"reachable models lack concrete source identities: {sorted(missing_reachable)!r}"
        )

    declared_types = set(base_by_type) | set(type_to_model) | set(owners)
    required_types = set(owners) | {model_to_type[model] for model in reachable_models}
    chains = {
        source_type: _chain_to_root(
            source_type,
            base_by_type,
            declared_types=declared_types,
            external_roots=roots,
        )
        for source_type in sorted(required_types)
    }

    result: list[dict[str, Any]] = []
    for owner in sorted(owners):
        applicable: list[dict[str, Any]] = []
        for model in sorted(reachable_models):
            concrete_type = model_to_type[model]
            path = chains[concrete_type]
            if owner not in path:
                continue
            exact_path = path[: path.index(owner) + 1]
            edges = [
                {"baseType": exact_path[i + 1], "derivedType": exact_path[i]}
                for i in range(len(exact_path) - 1)
            ]
            applicable.append(
                {
                    "canonicalMonster": model,
                    "concreteSourceType": concrete_type,
                    "inheritancePath": exact_path,
                    "provenance": {
                        "assemblySha256": assembly_sha256,
                        "metadataRelation": "TypeDef.Extends",
                        "relationWitnessSha256": witness_sha256(edges),
                    },
                }
            )
        if not applicable:
            raise SourceExtractionError(
                f"behavior owner {owner!r} has no proven reachable concrete applicability"
            )
        result.append(
            {
                "applicableConcreteModels": applicable,
                "behaviorOwnerSourceType": owner,
                "provenance": {
                    "assemblySha256": assembly_sha256,
                    "applicabilityWitnessSha256": witness_sha256(
                        [
                            {
                                "canonicalMonster": row["canonicalMonster"],
                                "inheritancePath": row["inheritancePath"],
                            }
                            for row in applicable
                        ]
                    ),
                    "metadataRelation": "TypeDef.Extends.transitiveClosure",
                },
            }
        )
    return result


def attach_behavior_applicability(
    behavior: dict[str, Any],
    relations: Sequence[Mapping[str, Any]],
) -> None:
    """Attach one-to-many concrete applicability to graphs and registrations."""
    by_owner = {
        row["behaviorOwnerSourceType"]: [
            item["canonicalMonster"] for item in row["applicableConcreteModels"]
        ]
        for row in relations
    }
    if len(by_owner) != len(relations):
        raise SourceExtractionError("duplicate behavior applicability owner")
    for family in ("graphs", "registrations"):
        for row in behavior[family]:
            owner = row.get("sourceType")
            models = by_owner.get(owner)
            if not models:
                raise SourceExtractionError(
                    f"{family} owner {owner!r} has no concrete applicability"
                )
            row["applicableConcreteModels"] = list(models)
    behavior["applicability"] = list(relations)
