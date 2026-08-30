"""Source-owned act, encounter-pool, and event-combat placement extraction."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .canonical import slugify_ascii_type_name, witness_sha256
from .errors import SourceExtractionError

_ACT_BASE = "MegaCrit.Sts2.Core.Models.ActModel"
_EVENT_BASE = "MegaCrit.Sts2.Core.Models.EventModel"
_MODEL_DB = "MegaCrit.Sts2.Core.Models.ModelDb"
_ENCOUNTER_FACTORY = "MegaCrit.Sts2.Core.Models.ModelDb::Encounter "
_EVENT_FACTORY = "MegaCrit.Sts2.Core.Models.ModelDb::Event "
_ACT_FACTORY = "MegaCrit.Sts2.Core.Models.ModelDb::Act "
_ROOM_CLASSES = {1: "monster", 2: "elite", 3: "boss"}


def _method(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "assemblySha256", "cilInstructionsSha256", "metadataSignature",
            "methodBodySha256", "normalizedInstructionsSha256", "symbolSignature",
        )
    }


def _int_constant(opcode: str, operand: Any) -> int | None:
    fixed = {
        "ldc.i4.m1": -1, "ldc.i4.0": 0, "ldc.i4.1": 1,
        "ldc.i4.2": 2, "ldc.i4.3": 3, "ldc.i4.4": 4,
        "ldc.i4.5": 5, "ldc.i4.6": 6, "ldc.i4.7": 7,
        "ldc.i4.8": 8,
    }
    if opcode in fixed:
        return fixed[opcode]
    if opcode in {"ldc.i4", "ldc.i4.s"} and type(operand) is int:
        return operand
    return None


def _single_record(assembly: Any, owner: str, name: str, assembly_sha256: str) -> dict[str, Any]:
    matches = assembly.find_methods(owner, name)
    if len(matches) != 1:
        raise SourceExtractionError(f"ambiguous required method {owner}::{name}: {len(matches)}")
    return assembly.method_record(matches[0], assembly_sha256)


def _nearest_record(assembly: Any, owner: str, name: str, assembly_sha256: str) -> dict[str, Any]:
    seen: set[str] = set()
    current = owner
    while current:
        if current in seen:
            raise SourceExtractionError(f"inheritance cycle resolving {owner}::{name}")
        seen.add(current)
        matches = assembly.find_methods(current, name)
        if matches:
            if len(matches) != 1:
                raise SourceExtractionError(f"ambiguous inherited method {current}::{name}")
            return assembly.method_record(matches[0], assembly_sha256)
        current = assembly.base_by_type.get(current)
    raise SourceExtractionError(f"unresolved inherited method {owner}::{name}")


def _generic_type(operand: Any, factory: str) -> str | None:
    if not isinstance(operand, str) or factory not in operand or "generic:" not in operand:
        return None
    value = operand.split("generic:", 1)[1]
    if not value or " " in value:
        raise SourceExtractionError(f"ambiguous generic factory target {operand!r}")
    return value


def _declared_count(instructions: Sequence[Mapping[str, Any]], element_type: str) -> int:
    """Decode the source collection cardinality, not an expected fixture count."""
    for index, item in enumerate(instructions):
        if item.get("opcode") == "newarr" and item.get("operand") == element_type:
            if index == 0:
                break
            value = _int_constant(
                str(instructions[index - 1].get("opcode")),
                instructions[index - 1].get("operand"),
            )
            if value is not None and value >= 0:
                return value
    # .NET's optimized list literal stores the count in a local, then passes it
    # through CollectionsMarshal.SetCount. The first integer in this reviewed
    # shape is the source-declared list size.
    if any("CollectionsMarshal::SetCount" in str(row.get("operand")) for row in instructions):
        for item in instructions:
            value = _int_constant(str(item.get("opcode")), item.get("operand"))
            if value is not None and value >= 0:
                return value
    # A one-element collection can compile directly to List<T>(item).
    calls = [row for row in instructions if str(row.get("opcode")) == "call"]
    if len(calls) == 1 and any("::.ctor" in str(row.get("operand")) for row in instructions):
        return 1
    raise SourceExtractionError(f"cannot decode source collection size for {element_type}")


def decode_factory_collection(
    record: Mapping[str, Any], *, factory: str, element_type: str,
) -> list[str]:
    """Decode a literal source registry and fail on cardinality/identity drift."""
    instructions = record.get("instructions")
    if not isinstance(instructions, list):
        raise SourceExtractionError("registry method has no normalized instructions")
    targets = [
        target
        for row in instructions
        if (target := _generic_type(row.get("operand"), factory)) is not None
    ]
    count = _declared_count(instructions, element_type)
    if len(targets) != count:
        raise SourceExtractionError(
            f"registry cardinality mismatch in {record.get('symbolSignature')}: "
            f"resolved {len(targets)}/{count}"
        )
    if len(set(targets)) != len(targets):
        raise SourceExtractionError(f"duplicate registry member in {record.get('symbolSignature')}")
    return targets


def _constant_getter(record: Mapping[str, Any], *, boolean: bool = False) -> int | bool:
    instructions = record["instructions"]
    if len(instructions) != 2 or instructions[1].get("opcode") != "ret":
        raise SourceExtractionError(f"non-constant required getter {record['symbolSignature']}")
    value = _int_constant(str(instructions[0].get("opcode")), instructions[0].get("operand"))
    if value is None:
        raise SourceExtractionError(f"unknown constant getter {record['symbolSignature']}")
    if boolean:
        if value not in {0, 1}:
            raise SourceExtractionError(f"invalid boolean getter {record['symbolSignature']}")
        return bool(value)
    return value


def _canonical(category: str, source_type: str) -> str:
    simple = source_type.rsplit(".", 1)[-1]
    if "+" in simple:
        raise SourceExtractionError(f"nested type cannot be a canonical {category}: {source_type}")
    return category + "." + slugify_ascii_type_name(simple)


def _source_predicate(assembly: Any, event_type: str, assembly_sha256: str) -> dict[str, Any]:
    record = _nearest_record(assembly, event_type, "IsAllowed", assembly_sha256)
    return {"kind": "sourcePredicate", "method": _method(record)}


def _decoded_event_condition(assembly: Any, event_type: str, assembly_sha256: str) -> dict[str, Any]:
    """Normalize the closed predicate vocabulary needed by linked encounters."""
    record = _nearest_record(assembly, event_type, "IsAllowed", assembly_sha256)
    digest = record["methodBodySha256"]
    condition: dict[str, Any]
    if digest == "b067e5b062baca1d4308a7becd68a73068d1754d05d78bd9a9c43492da8fca4a":
        condition = {"kind": "always"}
    elif digest == "19c43a06518595ece63e8080bbe01a1bb770d6db7d975beaa899bf027d348b26":
        condition = {"kind": "compare", "left": "run.totalFloor", "operator": "greaterThanOrEqual", "right": 6}
    elif digest == "db20e930bc536b4a98aac2d7a54dbc2f7b41a9f23d91e41a40170cf1f2971f00":
        condition = {
            "conditions": [
                {"kind": "compare", "left": "run.playerCount", "operator": "equal", "right": 1},
                {
                    "condition": {
                        "kind": "compare", "left": "player.currentHp", "operator": "greaterThan",
                        "right": "event.dynamicVars.HpLoss.baseValue",
                    },
                    "kind": "allPlayers",
                },
            ],
            "kind": "anyOf",
        }
    elif digest == "0c9e99afacb34cb5a26affe921864b10995c3289f58bde43beecf0888453c1be":
        every = _single_record(
            assembly, event_type + "+<>c", "<IsAllowed>b__20_0", assembly_sha256
        )
        potion = _single_record(
            assembly, event_type + "+<>c", "<IsAllowed>b__20_1", assembly_sha256
        )
        if every["methodBodySha256"] != "dc732772197e77fd096f6dc1b8cfb45bd3c254a63acce6a3a6a849421e7f54b4" or potion["methodBodySha256"] != "c0575a0faff5986aaf0180b981a399e6fbb5f5d09823180afe572c71fe239ec2":
            raise SourceExtractionError("Fake Merchant nested availability predicates changed")
        condition = {
            "conditions": [
                {"kind": "compare", "left": "run.currentActIndex", "operator": "greaterThanOrEqual", "right": 1},
                {"kind": "compare", "left": "run.playerCount", "operator": "lessThanOrEqual", "right": 1},
                {
                    "condition": {
                        "conditions": [
                            {"kind": "compare", "left": "player.gold", "operator": "greaterThanOrEqual", "right": 100},
                            {"kind": "hasPotionModelType", "sourceType": "MegaCrit.Sts2.Core.Models.Potions.FoulPotion"},
                        ],
                        "kind": "anyOf",
                    },
                    "kind": "allPlayers",
                },
            ],
            "kind": "allOf",
        }
        return {
            "condition": condition,
            "kind": "decodedSourcePredicate",
            "provenance": {"methods": [_method(record), _method(every), _method(potion)]},
        }
    else:
        raise SourceExtractionError(
            f"unknown availability predicate for linked event {event_type}: "
            f"{record['symbolSignature']} {digest}"
        )
    return {
        "condition": condition,
        "kind": "decodedSourcePredicate",
        "provenance": {"methods": [_method(record)]},
    }


def _event_links(
    assembly: Any,
    event_encounters: Sequence[Mapping[str, Any]],
    assembly_sha256: str,
) -> list[dict[str, Any]]:
    targets = {row["sourceType"]: "ENCOUNTER." + row["canonicalId"] for row in event_encounters}
    links: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for type_index, owner in assembly.type_names.items():
        if not owner.startswith("MegaCrit.Sts2.Core.Models.Events."):
            continue
        host = owner.split("+", 1)[0]
        if not assembly.derives_from(host, _EVENT_BASE):
            continue
        for method_index in assembly.md.TypeDef.rows[type_index - 1].MethodList:
            if not method_index.row.Rva:
                continue
            record = assembly.method_record(method_index.row_index, assembly_sha256)
            instructions = record["instructions"]
            for index, item in enumerate(instructions):
                operand = str(item.get("operand") or "")
                direct = None
                if "EventModel::EnterCombatWithoutExitingEvent" in operand and "generic:" in operand:
                    direct = operand.split("generic:", 1)[1]
                elif "EventModel::EnterCombatWithoutExitingEvent" in operand:
                    previous = [
                        _generic_type(row.get("operand"), _ENCOUNTER_FACTORY)
                        for row in instructions[:index]
                    ]
                    previous = [row for row in previous if row in targets]
                    if len(previous) == 1:
                        direct = previous[0]
                    elif previous:
                        raise SourceExtractionError(f"ambiguous event encounter argument in {record['symbolSignature']}")
                if direct in targets:
                    links[direct][host].append({"kind": "eventCombatTransition", "method": _method(record)})
            if str(method_index.row.Name) == "get_CanonicalEncounter":
                returned = [
                    _generic_type(row.get("operand"), _ENCOUNTER_FACTORY)
                    for row in instructions
                ]
                returned = [row for row in returned if row is not None]
                if returned:
                    if len(returned) != 1 or len(instructions) != 2 or instructions[-1].get("opcode") != "ret":
                        raise SourceExtractionError(f"ambiguous canonical event encounter in {record['symbolSignature']}")
                    if returned[0] in targets:
                        links[returned[0]][host].append({"kind": "canonicalCombatLayout", "method": _method(record)})

    output = []
    for source_type, encounter_id in sorted(targets.items(), key=lambda row: row[1]):
        hosts = links.get(source_type, {})
        if len(hosts) != 1:
            raise SourceExtractionError(
                f"event encounter {encounter_id} has {len(hosts)} exact event owners"
            )
        host_type, mechanisms = next(iter(hosts.items()))
        unique = {(row["kind"], row["method"]["symbolSignature"]): row for row in mechanisms}
        output.append({
            "canonicalEncounter": encounter_id,
            "canonicalEvent": _canonical("EVENT", host_type),
            "eventSourceType": host_type,
            "linkMechanisms": [unique[key] for key in sorted(unique)],
        })
    return output


def _find_scripted_event_entry(assembly: Any, event_type: str, assembly_sha256: str) -> dict[str, Any] | None:
    for type_index, owner in assembly.type_names.items():
        if not owner.startswith("MegaCrit.Sts2.Core.Runs.RunManager"):
            continue
        for method_index in assembly.md.TypeDef.rows[type_index - 1].MethodList:
            if not method_index.row.Rva:
                continue
            record = assembly.method_record(method_index.row_index, assembly_sha256)
            operands = [str(row.get("operand") or "") for row in record["instructions"]]
            if (
                any(_generic_type(value, _EVENT_FACTORY) == event_type for value in operands)
                and any("MegaCrit.Sts2.Core.Rooms.EventRoom::.ctor" in value for value in operands)
            ):
                return {
                    "kind": "scriptedRunTransition",
                    "method": _method(record),
                    "selectionStructure": "directEventRoomConstruction",
                }
    return None


def extract_placement(
    assembly: Any,
    assembly_sha256: str,
    encounter_census: Mapping[str, Any],
) -> dict[str, Any]:
    """Extract placement from owning source registries and exact event links."""
    acts_record = _single_record(assembly, _MODEL_DB, "get_Acts", assembly_sha256)
    act_types = decode_factory_collection(
        acts_record, factory=_ACT_FACTORY, element_type="MegaCrit.Sts2.Core.Models.ActModel"
    )
    if any(not assembly.derives_from(row, _ACT_BASE) for row in act_types):
        raise SourceExtractionError("ModelDb act registry contains a non-ActModel")

    ordinary_by_type = {row["sourceType"]: row for row in encounter_census["ordinary"]}
    all_ordinary_members: list[str] = []
    ordinary_registry_methods: list[dict[str, Any]] = []
    pools: list[dict[str, Any]] = []
    acts: list[dict[str, Any]] = []
    encounter_memberships: dict[str, list[dict[str, Any]]] = defaultdict(list)

    shared_record = _single_record(assembly, _MODEL_DB, "get_AllSharedEvents", assembly_sha256)
    shared_event_types = decode_factory_collection(
        shared_record, factory=_EVENT_FACTORY, element_type="MegaCrit.Sts2.Core.Models.EventModel"
    )
    shared_set = set(shared_event_types)

    event_pool_hosts: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for act_registry_ordinal, act_type in enumerate(act_types):
        act_id = _canonical("ACT", act_type)
        index_record = _single_record(assembly, act_type, "get_Index", assembly_sha256)
        weak_count_record = _single_record(assembly, act_type, "get_NumberOfWeakEncounters", assembly_sha256)
        act_index = int(_constant_getter(index_record))
        weak_draws = int(_constant_getter(weak_count_record))

        encounters_record = _single_record(assembly, act_type, "GenerateAllEncounters", assembly_sha256)
        encounter_types = decode_factory_collection(
            encounters_record, factory=_ENCOUNTER_FACTORY,
            element_type="MegaCrit.Sts2.Core.Models.EncounterModel",
        )
        ordinary_registry_methods.append(_method(encounters_record))
        unknown = set(encounter_types) - set(ordinary_by_type)
        if unknown:
            raise SourceExtractionError(f"act registry has non-current ordinary encounters: {sorted(unknown)!r}")
        all_ordinary_members.extend(encounter_types)
        partitioned: dict[str, list[tuple[str, int, dict[str, Any]]]] = defaultdict(list)
        for source_order, encounter_type in enumerate(encounter_types):
            room_record = _nearest_record(assembly, encounter_type, "get_RoomType", assembly_sha256)
            room_value = int(_constant_getter(room_record))
            room_class = _ROOM_CLASSES.get(room_value)
            if room_class is None:
                raise SourceExtractionError(f"unknown encounter RoomType {room_value} for {encounter_type}")
            weak_record = _nearest_record(assembly, encounter_type, "get_IsWeak", assembly_sha256)
            is_weak = bool(_constant_getter(weak_record, boolean=True))
            if room_class == "monster":
                tier = "weak" if is_weak else "regular"
            else:
                if is_weak:
                    raise SourceExtractionError(f"non-monster encounter marked weak: {encounter_type}")
                tier = room_class
            partitioned[tier].append((encounter_type, source_order, {"roomType": _method(room_record), "weak": _method(weak_record)}))

        if len(partitioned["weak"]) < 1 or weak_draws < 1:
            raise SourceExtractionError(f"act {act_id} has no usable weak encounter pool")
        for tier in ("weak", "regular", "elite", "boss"):
            members = partitioned[tier]
            if not members:
                raise SourceExtractionError(f"act {act_id} has empty required {tier} pool")
            pool_id = f"POOL.{act_id.removeprefix('ACT.')}.{tier.upper()}"
            if tier in {"weak", "regular", "elite"}:
                weight = {"kind": "constant", "value": "1.0", "valueType": "decimal"}
                draw = (
                    {"kind": "constant", "value": weak_draws}
                    if tier == "weak"
                    else {"kind": "constant", "value": 15}
                    if tier == "elite"
                    else {
                        "kind": "sourceExpression",
                        "operator": "subtract",
                        "operands": ["act.GetNumberOfRooms(isMultiplayer)", "act.NumberOfWeakEncounters"],
                    }
                )
                selection = {
                    "draws": draw,
                    "fallback": "retryWithoutImmediateExclusion",
                    "immediateExclusions": ["sameEncounterInstance", "sharedEncounterTag"],
                    "kind": "weightedDrawSequence",
                    "removalScope": "singleDrawCandidateSet",
                }
            else:
                weight = {"kind": "uniform"}
                selection = {"draws": {"kind": "constant", "value": 1}, "kind": "uniformSingle"}
            pool_members = []
            for pool_order, (encounter_type, source_order, member_proof) in enumerate(members):
                encounter_id = "ENCOUNTER." + ordinary_by_type[encounter_type]["canonicalId"]
                member = {
                    "canonicalEncounter": encounter_id,
                    "conditions": [],
                    "poolOrder": pool_order,
                    "sourceRegistryOrder": source_order,
                    "weight": weight,
                }
                pool_members.append(member)
                encounter_memberships[encounter_id].append({
                    "actId": act_id, "conditions": [], "poolId": pool_id,
                    "poolOrder": pool_order, "roomClass": "monster" if tier in {"weak", "regular"} else tier,
                    "sourceRegistryOrder": source_order, "tier": tier, "weight": weight,
                    "provenance": member_proof,
                })
            pools.append({
                "actId": act_id, "canonicalMembers": pool_members, "membershipKind": "encounter",
                "poolId": pool_id, "roomClass": "monster" if tier in {"weak", "regular"} else tier,
                "selection": selection, "tier": tier,
                "provenance": {"registryMethod": _method(encounters_record)},
            })

        events_record = _single_record(assembly, act_type, "get_AllEvents", assembly_sha256)
        local_event_types = decode_factory_collection(
            events_record, factory=_EVENT_FACTORY, element_type="MegaCrit.Sts2.Core.Models.EventModel"
        )
        overlap = set(local_event_types) & shared_set
        if overlap:
            raise SourceExtractionError(f"event is both act-local and shared: {sorted(overlap)!r}")
        event_members = []
        ordered_events = [(row, "actLocal") for row in local_event_types] + [(row, "shared") for row in shared_event_types]
        for pool_order, (event_type, origin) in enumerate(ordered_events):
            condition = _source_predicate(assembly, event_type, assembly_sha256)
            event_id = _canonical("EVENT", event_type)
            event_members.append({
                "canonicalEvent": event_id, "conditions": [condition], "origin": origin,
                "poolOrderBeforeShuffle": pool_order, "weight": {"kind": "none"},
            })
            event_pool_hosts[event_type].append((act_id, pool_order, origin))
        event_pool_id = f"POOL.{act_id.removeprefix('ACT.')}.EVENT"
        pools.append({
            "actId": act_id, "canonicalMembers": event_members, "membershipKind": "eventModel",
            "poolId": event_pool_id, "roomClass": "event", "tier": "event",
            "selection": {
                "eligibility": ["event.IsAllowed(runState)", "notAlreadyVisitedUntilAllUniqueEventsExhausted"],
                "initialOrdering": ["actLocalRegistry", "sharedRegistry"],
                "kind": "shuffleThenCyclicEligible",
                "repetition": "allowedAfterAllUniqueEventsExhausted",
            },
            "provenance": {
                "actRegistryMethod": _method(events_record),
                "sharedRegistryMethod": _method(shared_record),
            },
        })
        acts.append({
            "actIndex": act_index, "canonicalId": act_id,
            "poolRefs": [f"POOL.{act_id.removeprefix('ACT.')}.{tier}" for tier in ("WEAK", "REGULAR", "ELITE", "BOSS", "EVENT")],
            "registryOrder": act_registry_ordinal, "sourceType": act_type,
            "provenance": {"actRegistryMethod": _method(acts_record), "indexMethod": _method(index_record)},
        })

    duplicate_count = len(all_ordinary_members) - len(set(all_ordinary_members))
    unknown_members = set(all_ordinary_members) - set(ordinary_by_type)
    if duplicate_count or unknown_members:
        raise SourceExtractionError(
            f"ordinary act registries do not close: unknown={sorted(unknown_members)!r}, "
            f"duplicates={duplicate_count}"
        )
    ordinary_nonpool = set(ordinary_by_type) - set(all_ordinary_members)
    nonpool_details: dict[str, dict[str, Any]] = {
        "ENCOUNTER." + ordinary_by_type[source_type]["canonicalId"]: {
            "kind": "absentFromAllActEncounterRegistries",
            "sourceType": source_type,
            "provenance": {
                "actRegistryMethods": ordinary_registry_methods,
                "negativeMembershipWitnessSha256": witness_sha256({
                    "actRegistryMembers": sorted(all_ordinary_members),
                    "queriedSourceType": source_type,
                }),
            },
        }
        for source_type in sorted(ordinary_nonpool)
    }

    event_links = _event_links(assembly, encounter_census["event"], assembly_sha256)
    for link in event_links:
        host = link["eventSourceType"]
        event_id = link["canonicalEvent"]
        if host in event_pool_hosts:
            decoded = _decoded_event_condition(assembly, host, assembly_sha256)
            for act_id, pool_order, origin in event_pool_hosts[host]:
                pool_id = f"POOL.{act_id.removeprefix('ACT.')}.EVENT"
                encounter_memberships[link["canonicalEncounter"]].append({
                    "actId": act_id, "conditions": [decoded], "eventModel": event_id,
                    "eventPoolOrigin": origin, "poolId": pool_id, "poolOrderBeforeShuffle": pool_order,
                    "roomClass": "event", "tier": "event", "weight": {"kind": "none"},
                })
            link["availabilityClassification"] = "eventPool"
        else:
            special = _find_scripted_event_entry(assembly, host, assembly_sha256)
            if special is None:
                raise SourceExtractionError(f"linked event {event_id} has no source placement")
            link["availabilityClassification"] = "sourceProvenNonPool"
            link["nonPoolPlacement"] = special
            nonpool_details[link["canonicalEncounter"]] = special

    encounter_rows = []
    current_ids = {
        "ENCOUNTER." + row["canonicalId"]
        for kind in ("ordinary", "event") for row in encounter_census[kind]
    }
    linked_ids = {row["canonicalEncounter"] for row in event_links}
    for encounter_id in sorted(current_ids):
        memberships = sorted(
            encounter_memberships.get(encounter_id, []),
            key=lambda row: (row["actId"], row["poolId"], row.get("poolOrder", row.get("poolOrderBeforeShuffle", -1))),
        )
        if memberships:
            classification = "poolMember"
        elif encounter_id in nonpool_details:
            classification = "sourceProvenNonPool"
        else:
            raise SourceExtractionError(f"current encounter lacks placement classification: {encounter_id}")
        row = {
            "canonicalEncounter": encounter_id, "classification": classification,
            "memberships": memberships,
        }
        if classification == "sourceProvenNonPool":
            row["nonPoolClassification"] = nonpool_details[encounter_id]
        encounter_rows.append(row)

    result = {
        "acts": sorted(acts, key=lambda row: row["registryOrder"]),
        "encounters": encounter_rows,
        "eventLinkage": event_links,
        "pools": sorted(pools, key=lambda row: row["poolId"]),
        "sourceDenominators": {
            "acts": len(act_types),
            "currentEncounterPlacements": len(current_ids),
            "eventEncounterLinks": len(event_links),
            "pools": len(pools),
            "poolRegistryMembers": sum(len(row["canonicalMembers"]) for row in pools),
            "currentEncounterMemberships": sum(len(row["memberships"]) for row in encounter_rows),
        },
    }
    validate_placement(result)
    return result


_CONDITION_KINDS = {
    "allOf", "allPlayers", "always", "anyOf", "compare", "hasPotionModelType",
}
_SELECTION_KINDS = {"shuffleThenCyclicEligible", "uniformSingle", "weightedDrawSequence"}
_WEIGHT_KINDS = {"constant", "none", "uniform"}


def _validate_condition(node: Any, path: str, depth: int = 0) -> None:
    if depth > 16 or not isinstance(node, dict):
        raise SourceExtractionError(f"invalid placement condition at {path}")
    kind = node.get("kind")
    if kind not in _CONDITION_KINDS:
        raise SourceExtractionError(f"unknown placement condition kind {kind!r} at {path}")
    allowed = {
        "always": {"kind"},
        "compare": {"kind", "left", "operator", "right"},
        "hasPotionModelType": {"kind", "sourceType"},
        "allPlayers": {"kind", "condition"},
        "allOf": {"kind", "conditions"},
        "anyOf": {"kind", "conditions"},
    }[kind]
    if set(node) != allowed:
        raise SourceExtractionError(f"malformed placement condition fields at {path}")
    if kind in {"allOf", "anyOf"}:
        if not isinstance(node["conditions"], list) or not node["conditions"]:
            raise SourceExtractionError(f"empty placement condition at {path}")
        for index, child in enumerate(node["conditions"]):
            _validate_condition(child, f"{path}.conditions[{index}]", depth + 1)
    elif kind == "allPlayers":
        _validate_condition(node["condition"], path + ".condition", depth + 1)


def validate_placement(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"acts", "encounters", "eventLinkage", "pools", "sourceDenominators"}:
        raise SourceExtractionError("malformed placement root")
    acts = value["acts"]
    pools = value["pools"]
    encounters = value["encounters"]
    links = value["eventLinkage"]
    if not all(isinstance(rows, list) for rows in (acts, pools, encounters, links)):
        raise SourceExtractionError("placement families must be lists")
    act_ids = {row.get("canonicalId") for row in acts}
    if len(act_ids) != len(acts) or None in act_ids:
        raise SourceExtractionError("duplicate or missing placement act identity")
    pool_ids = {row.get("poolId") for row in pools}
    if len(pool_ids) != len(pools) or None in pool_ids:
        raise SourceExtractionError("duplicate or missing placement pool identity")
    for row in pools:
        if row.get("actId") not in act_ids:
            raise SourceExtractionError(f"placement pool has unknown act: {row.get('poolId')}")
        selection = row.get("selection")
        if not isinstance(selection, dict) or selection.get("kind") not in _SELECTION_KINDS:
            raise SourceExtractionError(f"unknown placement selection kind in {row.get('poolId')}")
        for member in row.get("canonicalMembers", []):
            weight = member.get("weight")
            if not isinstance(weight, dict) or weight.get("kind") not in _WEIGHT_KINDS:
                raise SourceExtractionError(f"unknown placement weight in {row.get('poolId')}")
    encounter_ids = {row.get("canonicalEncounter") for row in encounters}
    if len(encounter_ids) != len(encounters) or None in encounter_ids:
        raise SourceExtractionError("duplicate or missing encounter placement")
    for row in encounters:
        if set(row) not in ({"canonicalEncounter", "classification", "memberships"}, {"canonicalEncounter", "classification", "memberships", "nonPoolClassification"}):
            raise SourceExtractionError("malformed encounter placement fields")
        if row.get("classification") not in {"poolMember", "sourceProvenNonPool"}:
            raise SourceExtractionError("unknown encounter placement classification")
        memberships = row.get("memberships")
        if not isinstance(memberships, list):
            raise SourceExtractionError("encounter memberships must be a list")
        if row["classification"] == "poolMember" and (not memberships or "nonPoolClassification" in row):
            raise SourceExtractionError("pool encounter has no membership or carries non-pool data")
        if row["classification"] == "sourceProvenNonPool" and (memberships or "nonPoolClassification" not in row):
            raise SourceExtractionError("non-pool encounter classification is not explicit")
        for member in memberships:
            if member.get("poolId") not in pool_ids or member.get("actId") not in act_ids:
                raise SourceExtractionError("broken encounter placement reference")
            for condition in member.get("conditions", []):
                if condition.get("kind") != "decodedSourcePredicate" or set(condition) not in ({"condition", "kind", "provenance"}, {"condition", "kind"}):
                    raise SourceExtractionError("unresolved current encounter availability condition")
                _validate_condition(condition["condition"], "encounter.membership.condition")
    if {row.get("canonicalEncounter") for row in links} - encounter_ids:
        raise SourceExtractionError("event linkage refers to unknown encounter")
    denominators = value["sourceDenominators"]
    expected = {
        "acts": len(acts), "currentEncounterPlacements": len(encounters),
        "eventEncounterLinks": len(links), "pools": len(pools),
        "poolRegistryMembers": sum(len(row["canonicalMembers"]) for row in pools),
        "currentEncounterMemberships": sum(len(row["memberships"]) for row in encounters),
    }
    if denominators != expected:
        raise SourceExtractionError("placement source denominator accounting mismatch")
