"""Source-faithful encounter roster, candidate, and production extraction."""

from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import re
from typing import Any

from .ast import validate_selection
from .canonical import witness_sha256
from .errors import SourceExtractionError
from .metadata import AssemblyMetadata

ENCOUNTER_NAMESPACE = "MegaCrit.Sts2.Core.Models.Encounters"
_MONSTER_GENERIC = re.compile(r" generic:MegaCrit\.Sts2\.Core\.Models\.Monsters\.([A-Za-z0-9]+)$")


def ref(simple: str) -> str:
    # ModelDb uses the same reviewed Slugify rule; import avoided to keep this
    # module's grammar-facing API compact.
    from .metadata import _slugify_ascii_type_name
    return "MONSTER." + _slugify_ascii_type_name(simple)


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

# Semantic recognizers for the seven reviewed roster-selection shapes.  These
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


def _required_special_methods(assembly: AssemblyMetadata, source_type: str, canonical_id: str, assembly_sha256: str) -> list[dict[str, Any]]:
    names: list[tuple[str, str]] = []
    if canonical_id in {"BOWLBUGS_NORMAL", "RUBY_RAIDERS_NORMAL", "SLIMES_WEAK", "SLITHERING_STRANGLER_NORMAL"}:
        names.append((source_type, ".cctor"))
    if canonical_id == "BOWLBUGS_WEAK":
        names.append((source_type, "get_Bugs"))
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
                direct = _model_calls(generate)
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
                else:
                    if not direct:
                        raise SourceExtractionError(f"no initial models resolved for {canonical_id}")
                    selection = sequence(*(fixed(item) for item in direct))
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
