from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from encounter_projection.builder import build_artifact, regenerate
from encounter_projection.validator import validate_artifact
from source_extractor.canonical import witness_sha256
from source_extractor.errors import SourceExtractionError

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "data/game-v0.111.0-source.json"
LEGACY_PATH = ROOT / "data/encounters.json"
PROJECTION_PATH = ROOT / "data/encounter-facts-v0.111.0.json"
LEGACY_SHA256 = "0c01dd0b851c501acea59fb41b10a828030ad2c3e63f9fc624f98b6e403e0103"


class EncounterProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_bytes = SOURCE_PATH.read_bytes()
        cls.legacy_bytes = LEGACY_PATH.read_bytes()
        cls.projection_bytes = PROJECTION_PATH.read_bytes()
        cls.source = json.loads(cls.source_bytes)
        cls.legacy = json.loads(cls.legacy_bytes)
        cls.artifact = json.loads(cls.projection_bytes)

    def mutated(self, change):
        artifact = deepcopy(self.artifact)
        change(artifact)
        artifact["metadata"]["payloadSha256"] = witness_sha256(artifact["payload"])
        return artifact

    def assert_invalid(self, artifact, pattern):
        with self.assertRaisesRegex(SourceExtractionError, pattern):
            validate_artifact(artifact, source=self.source, legacy=self.legacy)

    def test_checked_build_is_deterministic_canonical_and_compact(self):
        first = build_artifact(self.source_bytes, self.legacy_bytes)
        second = build_artifact(self.source_bytes, self.legacy_bytes)
        self.assertEqual(first, second)
        self.assertEqual(first, self.projection_bytes)
        self.assertLess(len(first), len(self.source_bytes) // 2)
        self.assertNotIn(b"invocationCensus", first)
        self.assertNotIn(b'"instructions"', first)
        self.assertNotIn(b'"diagnosticMetadataToken"', first)
        self.assertEqual(hashlib.sha256(self.legacy_bytes).hexdigest(), LEGACY_SHA256)
        self.assertNotIn("generatedAt", self.artifact["metadata"])

    def test_counts_lanes_archive_and_readiness(self):
        payload = self.artifact["payload"]
        source = payload["sourceFacts"]
        legacy = payload["legacyAnnotations"]
        self.assertEqual((len(source["encounters"]["ordinary"]), len(source["encounters"]["event"])), (81, 8))
        self.assertEqual((len(source["monsters"]), len(source["moves"]), len(source["graphs"])), (108, 307, 100))
        self.assertEqual(len(legacy["current"]), 81)
        event_ids = {row["canonicalId"] for row in source["encounters"]["event"]}
        legacy_current_ids = {row["legacyEncounterId"] for row in legacy["current"]}
        self.assertTrue(event_ids.isdisjoint(legacy_current_ids))
        all_legacy = legacy["current"] + legacy["archive"]
        self.assertEqual(sum(len(row["presentationBodies"]) for row in all_legacy), 133)
        self.assertEqual(sum(len(body["annotations"]["moves"]) for row in all_legacy for body in row["presentationBodies"]), 373)
        self.assertEqual([row["legacyEncounterId"] for row in legacy["archive"]], ["DOORMAKER_BOSS"])
        self.assertNotIn("DOORMAKER_BOSS", {row["canonicalId"] for row in source["encounters"]["ordinary"]})
        self.assertNotIn("DOORMAKER_BOSS", {row["legacyEncounterId"] for row in legacy["current"]})
        readiness = payload["readiness"]
        self.assertEqual(readiness["root"]["ready"], False)
        self.assertEqual(readiness["global"]["status"], "incomplete")
        self.assertEqual(readiness["runtimeScopes"]["encounterCompanion"]["ready"], False)
        self.assertEqual(readiness["runtimeScopes"]["encounterProjection"]["ready"], True)

    def test_roster_production_and_state_regressions(self):
        source = self.artifact["payload"]["sourceFacts"]
        encounters = {row["canonicalId"]: row for row in source["encounters"]["ordinary"]}
        fabricator = encounters["FABRICATOR_NORMAL"]
        self.assertEqual(fabricator["initialRoster"]["cardinality"], {"minimum": 1, "maximum": 1})
        self.assertEqual(fabricator["producedMonsters"], ["MONSTER.GUARDBOT", "MONSTER.NOISEBOT", "MONSTER.STABBOT", "MONSTER.ZAPBOT"])
        self.assertEqual(
            {row["poolId"]: row["members"] for row in fabricator["productionPools"]},
            {"aggressive": ["MONSTER.ZAPBOT", "MONSTER.STABBOT"], "defensive": ["MONSTER.GUARDBOT", "MONSTER.NOISEBOT"]},
        )
        flyconid = encounters["FLYCONID_NORMAL"]
        self.assertEqual(flyconid["initialRoster"]["cardinality"], {"minimum": 2, "maximum": 2})
        self.assertEqual(flyconid["initialRoster"]["selection"]["children"][0]["kind"], "uniformChoice")
        self.assertEqual(len(flyconid["possibleMonsters"]), 3)
        raiders = encounters["RUBY_RAIDERS_NORMAL"]
        self.assertEqual(raiders["initialRoster"]["cardinality"], {"minimum": 3, "maximum": 3})
        self.assertEqual(raiders["initialRoster"]["selection"]["kind"], "filteredChoice")
        self.assertEqual(raiders["initialRoster"]["selection"]["draws"], "withoutReplacement")
        states = {row["stateId"]: row for row in source["states"]}
        self.assertEqual(states["MONSTER.TOUGH_EGG#HATCHED"]["canonicalModel"], "MONSTER.TOUGH_EGG")
        self.assertEqual(states["MONSTER.TOUGH_EGG#HATCHED"]["displayName"]["text"], "Hatchling")
        self.assertEqual(len([key for key in states if key.startswith("MONSTER.TEST_SUBJECT#PHASE_")]), 3)
        self.assertNotIn("MONSTER.HATCHLING", {row["canonicalModel"] for row in source["monsters"]})

    def test_decimillipede_titles_conflicts_and_unknowns(self):
        payload = self.artifact["payload"]
        owners = [row for row in payload["sourceFacts"]["behaviorOwners"] if row["classification"] == "abstractBehavior"]
        self.assertEqual([row["canonicalMonster"] for row in owners], ["MONSTER.DECIMILLIPEDE_SEGMENT"])
        self.assertNotIn("modelRef", owners[0])
        unknowns = payload["knownUnknowns"]
        self.assertEqual(owners[0]["applicabilityKind"], "inheritedBehavior")
        self.assertEqual(owners[0]["applicableConcreteModels"], [
            "MONSTER.DECIMILLIPEDE_SEGMENT_BACK",
            "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT",
            "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
        ])
        retired = {
            "SOURCE_ACT_PLACEMENT_ABSENT", "SOURCE_ROOM_CLASS_PLACEMENT_ABSENT",
            "OBSERVED_IDENTITY_ALIAS_JOIN_ABSENT", "ABSTRACT_BEHAVIOR_INHERITANCE_JOIN_ABSENT",
        }
        self.assertTrue(retired.isdisjoint({row["reasonCode"] for row in unknowns}))
        self.assertEqual(sum(row["reasonCode"] == "SOURCE_MOVE_TITLE_MISSING_OR_INTERNAL" for row in unknowns), 18)
        candidates = payload["legacyAnnotations"]["moveTitleFallbackCandidates"]
        self.assertEqual(len(candidates), 18)
        self.assertTrue(all(row["status"] == "unjoinedCandidateSet" for row in candidates))
        self.assertEqual(len(payload["conflicts"]), 26)
        self.assertTrue(all(row["resolution"] == "unresolved" for row in payload["conflicts"]))
        self.assertTrue(any(row["conflictId"] == "CONFLICT.MONSTER_TITLE.FOGMOG_NORMAL.1" for row in payload["conflicts"]))
        self.assertTrue(any(row["reasonCode"] == "SOURCE_VS_STABLE_HP_ROUNDING_CONFLICT" for row in unknowns))


    def test_e1_placement_census_pools_conditions_and_nonpool_records(self):
        sf = self.artifact["payload"]["sourceFacts"]
        placement = sf["placement"]
        self.assertEqual(placement["sourceDenominators"], {
            "acts": 4, "currentEncounterMemberships": 90,
            "currentEncounterPlacements": 89, "eventEncounterLinks": 8,
            "poolRegistryMembers": 192, "pools": 20,
        })
        self.assertEqual(
            [(row["canonicalId"], row["actIndex"], row["registryOrder"]) for row in placement["acts"]],
            [("ACT.OVERGROWTH", 0, 0), ("ACT.UNDERDOCKS", 0, 1), ("ACT.HIVE", 1, 2), ("ACT.GLORY", 2, 3)],
        )
        encounters = {row["canonicalEncounter"]: row for row in placement["encounters"]}
        self.assertEqual(len(encounters), 89)
        self.assertNotIn("ENCOUNTER.DOORMAKER_BOSS", encounters)
        self.assertEqual(encounters["ENCOUNTER.DECIMILLIPEDE_ELITE"]["memberships"][0]["actId"], "ACT.HIVE")
        self.assertEqual(encounters["ENCOUNTER.DECIMILLIPEDE_ELITE"]["memberships"][0]["roomClass"], "elite")
        self.assertEqual(encounters["ENCOUNTER.RUBY_RAIDERS_NORMAL"]["memberships"][0]["tier"], "regular")
        fake = encounters["ENCOUNTER.FAKE_MERCHANT_EVENT_ENCOUNTER"]
        self.assertEqual([row["actId"] for row in fake["memberships"]], ["ACT.GLORY", "ACT.HIVE", "ACT.OVERGROWTH", "ACT.UNDERDOCKS"])
        self.assertTrue(all(row["eventPoolOrigin"] == "shared" for row in fake["memberships"]))
        fake_condition = fake["memberships"][0]["conditions"][0]["condition"]
        self.assertEqual(fake_condition["kind"], "allOf")
        self.assertEqual(fake_condition["conditions"][0], {"kind": "compare", "left": "run.currentActIndex", "operator": "greaterThanOrEqual", "right": 1})
        tunneler = encounters["ENCOUNTER.TUNNELER_NORMAL"]
        self.assertEqual(tunneler["classification"], "sourceProvenNonPool")
        self.assertEqual(tunneler["nonPoolClassification"]["kind"], "absentFromAllActEncounterRegistries")
        architect = encounters["ENCOUNTER.THE_ARCHITECT_EVENT_ENCOUNTER"]
        self.assertEqual(architect["nonPoolClassification"]["kind"], "scriptedRunTransition")
        pools = {row["poolId"]: row for row in placement["pools"]}
        weak = pools["POOL.OVERGROWTH.WEAK"]
        self.assertEqual(weak["selection"]["kind"], "weightedDrawSequence")
        self.assertEqual(weak["selection"]["draws"], {"kind": "constant", "value": 3})
        self.assertTrue(all(row["weight"] == {"kind": "constant", "value": "1.0", "valueType": "decimal"} for row in weak["canonicalMembers"]))
        self.assertEqual(pools["POOL.OVERGROWTH.EVENT"]["selection"]["initialOrdering"], ["actLocalRegistry", "sharedRegistry"])
        self.assertEqual(len(placement["eventLinkage"]), 8)

    def test_e1_exact_identity_domain_states_and_adversarial_lookalikes(self):
        identities = self.artifact["payload"]["sourceFacts"]["observationIdentities"]
        entries = {row["observedId"]: row for row in identities["entries"]}
        self.assertEqual(len(entries), 108)
        self.assertEqual(len(identities["resourceRepresentations"]), 108)
        resources = {row["resourceId"]: row for row in identities["resourceRepresentations"]}
        self.assertEqual(resources["res://scenes/creature_visuals/decimillipede_segment_front.tscn"]["canonicalMonster"], "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT")
        self.assertNotIn("res://scenes/creature_visuals/tough_egg.tscn", entries)
        self.assertEqual(identities["aliases"], [])
        self.assertEqual(identities["matchingPolicy"]["fuzzyMatching"], False)
        for model in (
            "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
            "MONSTER.DECIMILLIPEDE_SEGMENT_BACK", "MONSTER.ASSASSIN_RUBY_RAIDER",
            "MONSTER.AXE_RUBY_RAIDER", "MONSTER.BRUTE_RUBY_RAIDER",
            "MONSTER.CROSSBOW_RUBY_RAIDER", "MONSTER.TRACKER_RUBY_RAIDER",
            "MONSTER.TOUGH_EGG", "MONSTER.TEST_SUBJECT",
        ):
            self.assertEqual(entries[model]["canonicalMonster"], model)
            self.assertEqual(entries[model]["identityKind"], "model")
        for lookalike in (
            "MONSTER.DECIMILLIPEDE_FRONT", "MONSTER.ASSASSIN_RAIDER", "MONSTER.HATCHLING",
            "MONSTER.TEST_SUBJECT_PHASE_2", "monster.tough_egg", "TOUGH_EGG",
        ):
            self.assertNotIn(lookalike, entries)
        states = {row["stateId"]: row for row in identities["stateObservationContracts"]}
        self.assertEqual(len(states), 8)
        for state_id, model in (
            ("MONSTER.TOUGH_EGG#HATCHED", "MONSTER.TOUGH_EGG"),
            ("MONSTER.TEST_SUBJECT#PHASE_2", "MONSTER.TEST_SUBJECT"),
            ("MONSTER.DECIMILLIPEDE_SEGMENT_FRONT#BODY", "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT"),
        ):
            self.assertEqual(states[state_id]["observation"]["emittedModelId"], model)
            self.assertEqual(states[state_id]["observation"]["separateStateIdEmitted"], False)
        comparisons = {row["comparisonId"]: row for row in self.artifact["payload"]["laneComparisons"]}
        self.assertEqual(comparisons["OBSERVED_IDENTITY.DECIMILLIPEDE_ELITE.0"]["reasonCode"], "NO_EXACT_SOURCE_OBSERVATION_ID")
        self.assertEqual(comparisons["OBSERVED_IDENTITY.RUBY_RAIDERS_NORMAL.0"]["status"], "notStaticallyComparable")

    def test_e1_all_graphs_and_registrations_have_concrete_applicability(self):
        sf = self.artifact["payload"]["sourceFacts"]
        owners = {row["canonicalMonster"]: row for row in sf["behaviorOwners"]}
        self.assertEqual(len(owners), 100)
        self.assertTrue(all(row["applicableConcreteModels"] for row in owners.values()))
        self.assertEqual(len(sf["graphs"]), 100)
        self.assertEqual(len(sf["moves"]), 307)
        for row in sf["graphs"] + sf["moves"]:
            self.assertEqual(row["applicableConcreteModels"], owners[row["canonicalMonster"]]["applicableConcreteModels"])
        decimilli_moves = [row for row in sf["moves"] if row["canonicalMonster"] == "MONSTER.DECIMILLIPEDE_SEGMENT"]
        self.assertEqual(len(decimilli_moves), 5)
        self.assertTrue(all(len(row["applicableConcreteModels"]) == 3 for row in decimilli_moves))

    def test_e1_placement_identity_and_applicability_mutations_fail(self):
        def unknown_pool(a):
            a["payload"]["sourceFacts"]["placement"]["pools"][0]["selection"]["kind"] = "guessedPool"

        def unknown_condition(a):
            placement = a["payload"]["sourceFacts"]["placement"]
            member = next(m for row in placement["encounters"] for m in row["memberships"] if m["conditions"])
            member["conditions"][0]["condition"]["kind"] = "guessedCondition"

        def alias_injection(a):
            a["payload"]["sourceFacts"]["observationIdentities"]["aliases"].append({"observedId": "MONSTER.EGG", "target": "MONSTER.TOUGH_EGG"})

        def identity_collision(a):
            rows = a["payload"]["sourceFacts"]["observationIdentities"]["entries"]
            rows[1]["observedId"] = rows[0]["observedId"]

        def missing_state_target(a):
            a["payload"]["sourceFacts"]["observationIdentities"]["stateObservationContracts"][0]["canonicalMonster"] = "MONSTER.MISSING"

        def bad_resource_representation(a):
            a["payload"]["sourceFacts"]["observationIdentities"]["resourceRepresentations"][0]["resourceId"] = "monster.aeonglass"

        def broken_owner_applicability(a):
            a["payload"]["sourceFacts"]["behaviorOwners"][0]["applicableConcreteModels"] = ["MONSTER.MISSING"]

        def broken_move_applicability(a):
            a["payload"]["sourceFacts"]["moves"][0]["applicableConcreteModels"] = []

        for change, pattern in (
            (unknown_pool, "unknown placement selection"),
            (unknown_condition, "unknown placement condition"),
            (alias_injection, "no source-declared aliases"),
            (identity_collision, "collision"),
            (missing_state_target, "missing target|domain"),
            (bad_resource_representation, "resource identity representation"),
            (broken_owner_applicability, "concrete applicability"),
            (broken_move_applicability, "applicability differs"),
        ):
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_e2a_initial_state_projection_comparisons_and_blockers(self):
        payload = self.artifact["payload"]
        initial = payload["sourceFacts"]["initialState"]
        self.assertEqual(initial["summary"], {
            "encounterRoots": 89, "facts": 111, "invocationDecisions": 1092,
            "modelOwners": 108, "powerModels": 41, "runtimeContracts": 47,
        })
        self.assertEqual((len(initial["owners"]), len(initial["facts"]), len(initial["runtimeStateContracts"])), (108, 111, 47))
        self.assertEqual(len(initial["powerHookClosure"]), 41)
        self.assertEqual(sum(len(row["declarations"]) for row in initial["externalHookBoundary"]), 29)
        hatch = next(
            row for row in initial["facts"]
            if row["factId"] == "SOURCE.INITIAL.MONSTER.TOUGH_EGG.AFTERADDEDTOROOM.000.APPLYPOWER"
        )["baseValue"]["expression"]
        self.assertEqual(hatch["condition"]["operator"], "equal")
        self.assertEqual(hatch["condition"]["right"], {"kind": "constant", "value": 2, "valueType": "integer"})
        self.assertEqual(hatch["condition"]["left"]["domain"], {"minimum": 0, "maximum": 2})
        self.assertEqual(hatch["whenTrue"]["expression"]["value"], 2)
        self.assertEqual(hatch["whenFalse"]["expression"]["value"], 1)
        current_side = next(
            row for row in initial["runtimeStateContracts"]
            if row["contractId"] == "RUNTIME.COMBAT.CURRENT_SIDE"
        )
        self.assertEqual(current_side["domain"], {"minimum": 0, "maximum": 2})
        self.assertNotIn("invocationDecisions", initial)
        self.assertNotIn("constructorDecisions", initial)
        self.assertNotIn("encounterInitializerDecisions", initial)
        comparisons = [row for row in payload["laneComparisons"] if row["family"] == "initialStateLegacyAnnotation"]
        self.assertEqual(len(comparisons), 57)
        statuses = {row["status"] for row in comparisons}
        self.assertEqual(statuses, {"agrees", "sourceSuperset", "dynamicNotComparable", "stateNotModel", "unmatchedLegacyIdentity"})
        decim = [row for row in comparisons if "DECIMILLIPEDE_ELITE" in row["comparisonId"]]
        self.assertEqual([row["left"]["value"]["candidateCanonicalModel"] for row in decim], [
            "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE", "MONSTER.DECIMILLIPEDE_SEGMENT_BACK",
        ])
        self.assertTrue(all(row["left"]["value"]["identityJoin"] == "none" for row in decim))
        tough = next(row for row in comparisons if row["comparisonId"] == "COMPARE.INITIAL.OVICOPTER_NORMAL.1")
        self.assertEqual(tough["status"], "dynamicNotComparable")
        hatchling = next(row for row in comparisons if row["comparisonId"] == "COMPARE.INITIAL.OVICOPTER_NORMAL.2")
        self.assertEqual((hatchling["status"], hatchling["left"]["value"]["stateId"]), ("stateNotModel", "MONSTER.TOUGH_EGG#HATCHED"))
        cubex = next(row for row in comparisons if row["comparisonId"] == "COMPARE.INITIAL.CUBEX_CONSTRUCT_NORMAL.0")
        self.assertEqual(cubex["status"], "sourceSuperset")
        self.assertTrue(any("GAINBLOCK" in ref for ref in cubex["left"]["value"]["additionalSourceFactRefs"]))
        illusion = next(row for row in comparisons if row["comparisonId"] == "COMPARE.INITIAL.FOGMOG_NORMAL.1")
        self.assertEqual(illusion["status"], "sourceSuperset")
        self.assertTrue(any("POWER.ILLUSION_POWER" in ref and "APPLYPOWER" in ref for ref in illusion["left"]["value"]["additionalSourceFactRefs"]))
        plating = next(row for row in comparisons if row["comparisonId"] == "COMPARE.INITIAL.FROG_KNIGHT_NORMAL.0")
        self.assertEqual(plating["status"], "dynamicNotComparable")
        self.assertTrue(any("POWER.PLATING_POWER" in ref for ref in plating["left"]["value"]["additionalSourceFactRefs"]))
        self.assertEqual(payload["sourceFacts"]["observationIdentities"]["aliases"], [])
        unknowns = {row["unknownId"]: row for row in payload["knownUnknowns"]}
        self.assertNotIn("UNKNOWN.INITIAL_STATES", unknowns)
        self.assertIn("UNKNOWN.LIFECYCLE_COVERAGE", unknowns)
        self.assertIn("UNKNOWN.FORMULA_RUNTIME_CONTRACTS", unknowns)
        self.assertIn("UNKNOWN.EVENT_BEHAVIOR", unknowns)
        self.assertIn("UNKNOWN.HP_ROUNDING_CONFLICT", unknowns)
        companion = payload["readiness"]["runtimeScopes"]["encounterCompanion"]
        self.assertEqual((companion["ready"], companion["status"]), (False, "incomplete"))
        self.assertEqual(set(companion["reasonRefs"]), {
            "UNKNOWN.LIFECYCLE_COVERAGE", "UNKNOWN.FORMULA_RUNTIME_CONTRACTS",
            "UNKNOWN.EVENT_BEHAVIOR", "UNKNOWN.HP_ROUNDING_CONFLICT",
        })

    def test_e2a_compact_mutations_fail_closed(self):
        def initial(a): return a["payload"]["sourceFacts"]["initialState"]
        def tough_hatch(a):
            return next(
                row for row in initial(a)["facts"]
                if row["factId"] == "SOURCE.INITIAL.MONSTER.TOUGH_EGG.AFTERADDEDTOROOM.000.APPLYPOWER"
            )["baseValue"]["expression"]
        cases = [
            (lambda a: initial(a)["owners"].pop(), "all 108 owners"),
            (lambda a: initial(a)["facts"].pop(), "111 compact facts"),
            (lambda a: initial(a)["owners"][0].__setitem__("applicableModels", []), "applicability"),
            (lambda a: initial(a)["runtimeStateContracts"][0].pop("domain"), "domain"),
            (lambda a: initial(a)["runtimeStateContracts"][0].pop("sourceInputs"), "source-input inventory"),
            (lambda a: initial(a)["facts"][0]["finalValueContract"]["runtimeModifierInputs"].append("RUNTIME.MISSING"), "unregistered compact runtime input"),
            (lambda a: initial(a)["powerHookClosure"][0]["hooks"].pop(), "hook omitted"),
            (lambda a: initial(a)["legacyComparisonFacts"].pop(), "all 57|expected all 57"),
            (lambda a: initial(a)["facts"][0].__setitem__("condition", {"kind": "guessedCondition"}), "unsupported initial condition"),
            (lambda a: initial(a).__setitem__("invocationDecisions", []), "unknown fields|proof bulk"),
            (lambda a: tough_hatch(a)["condition"]["right"].__setitem__("value", 0), "evidence value digest|deterministic two-lane derivation"),
            (lambda a: tough_hatch(a)["condition"]["left"]["domain"].__setitem__("maximum", 1), "evidence value digest|deterministic two-lane derivation"),
            (lambda a: tough_hatch(a)["whenTrue"]["expression"].__setitem__("value", 1), "evidence value digest|deterministic two-lane derivation"),
        ]
        base_noop = next(i for i, row in enumerate(self.artifact["payload"]["sourceFacts"]["initialState"]["owners"])
                         if row["classification"] == "sourceProvenNoOp")
        visual = next(i for i, row in enumerate(self.artifact["payload"]["sourceFacts"]["initialState"]["owners"])
                      if row["classification"] == "sourceProvenNonGameplayOnly")
        cases.extend([
            (lambda a: initial(a)["owners"][base_noop].__setitem__("classification", "sourceProvenNonGameplayOnly"), "base no-op"),
            (lambda a: initial(a)["owners"][visual].__setitem__("classification", "orderedGameplayEffects"), "effects/classification"),
            (lambda a: a["payload"]["laneComparisons"].pop(next(i for i, row in enumerate(a["payload"]["laneComparisons"]) if row["family"] == "initialStateLegacyAnnotation")), "57 initial-state comparisons"),
            (lambda a: a["payload"]["readiness"]["runtimeScopes"]["encounterCompanion"].__setitem__("ready", True), "cannot be ready"),
        ])
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_e2a_raw_source_mutations_fail_closed(self):
        def unregistered_field(source):
            fact = next(row for row in source["initialState"]["initialStateFacts"] if row["baseValue"]["valueType"] == "integer")
            fact["baseValue"]["expression"] = {"kind": "stateVariable", "name": "initial.unregistered", "valueType": "integer", "domain": {"minimum": 0}}

        def assert_bad(change, pattern):
            source = deepcopy(self.source)
            change(source)
            with self.assertRaisesRegex(SourceExtractionError, pattern):
                validate_artifact(self.artifact, source=source, legacy=self.legacy)
        cases = [
            (lambda s: s["initialState"]["encounterInitializers"].pop(), "89 exact generator roots"),
            (lambda s: s["initialState"]["initialStateOwners"].pop(), "108 exact reachable owners"),
            (lambda s: s["initialState"]["initialStateFacts"].pop(), "111 ordered initial facts"),
            (lambda s: s["initialState"]["invocationDecisions"].pop(), "1092-call census"),
            (lambda s: s["initialState"]["constructorDecisions"].pop(), "five explicit constructor writes"),
            (lambda s: s["initialState"]["runtimeStateContracts"][0].pop("domain"), "domain"),
            (lambda s: s["initialState"]["runtimeStateContracts"][0]["readSites"].clear(), "read site"),
            (unregistered_field, "unregistered source field"),
            (lambda s: s["initialState"]["powerHookClosure"][0]["hooks"].pop(), "hook family omitted"),
            (lambda s: s["initialState"]["initialStateFacts"][0]["provenance"].pop("methodBodySha256"), "methodBodySha256"),
            (lambda s: s["initialState"]["initialStateFacts"][0].__setitem__("condition", {"kind": "guessed"}), "unsupported initial condition"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern): assert_bad(change, pattern)

    def test_evidence_is_compact_stable_and_complete(self):
        payload = self.artifact["payload"]
        evidence = payload["evidence"]
        refs = payload["factReferences"]
        evidence_ids = {row["evidenceId"] for row in evidence}
        self.assertEqual(len(evidence_ids), len(evidence))
        self.assertTrue(all(row["pointers"] and row["pointers"][0]["jsonPointer"].startswith("/") for row in evidence))
        self.assertTrue(all(set(row["evidenceRefs"]) <= evidence_ids for row in refs))
        move = next(row for row in payload["sourceFacts"]["moves"] if row["canonicalId"] == "MONSTER.AEONGLASS#EBB_MOVE")
        move_ref = next(row for row in refs if row["factId"] == move["factId"])
        proof = next(row for row in evidence if row["evidenceId"] == move_ref["evidenceRefs"][0])
        self.assertEqual(proof["pointers"][0]["jsonPointer"], "/behavior/registrations/0")

    def test_metadata_manifest_payload_and_coverage_mutations_fail(self):
        cases = [
            (lambda a: a.__setitem__("schemaVersion", 999), "schemaVersion"),
            (lambda a: a["metadata"]["generator"].__setitem__("version", "bad"), "generator"),
            (lambda a: a["metadata"]["game"].__setitem__("commit", "bad"), "game"),
            (lambda a: a["metadata"]["projectionInputs"][0].__setitem__("sha256", "0" * 64), "projectionInputs"),
            (lambda a: a["metadata"].__setitem__("embeddedSourceInputManifestSha256", "0" * 64), "manifest digest mismatch"),
            (lambda a: a["metadata"]["requiredCoverage"][0].__setitem__("denominator", 2), "coverage"),
            (lambda a: a["metadata"].__setitem__("payloadSha256", "0" * 64), "payload digest mismatch"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                artifact = deepcopy(self.artifact)
                change(artifact)
                self.assert_invalid(artifact, pattern)

    def test_source_metadata_and_coverage_mutations_fail(self):
        cases = [
            (lambda s: s.__setitem__("schemaVersion", 999), "source.schemaVersion"),
            (lambda s: s.__setitem__("extractorVersion", "bad"), "source.extractorVersion"),
            (lambda s: s["game"].__setitem__("mainAssemblyHash", 0), "source.game"),
            (lambda s: s["inputs"][0].__setitem__("path", "wrong"), "source.inputs"),
            (lambda s: s["authority"].__setitem__("artifactTier", "patched"), "source.authority"),
            (lambda s: s["coverage"]["moveOperations"].__setitem__("unresolved", 1), "moveOperations"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                source = deepcopy(self.source)
                change(source)
                with self.assertRaisesRegex(SourceExtractionError, pattern):
                    validate_artifact(self.artifact, source=source, legacy=self.legacy)

    def test_unknown_fields_ast_kinds_operators_types_and_depth_fail(self):
        def unknown_field(a):
            a["payload"]["sourceFacts"]["moves"][0]["invented"] = True

        def unknown_roster(a):
            a["payload"]["sourceFacts"]["encounters"]["ordinary"][0]["initialRoster"]["selection"]["kind"] = "flattenCandidates"

        def unknown_operator(a):
            expression = a["payload"]["sourceFacts"]["monsters"][0]["initialHp"]["expression"]["minimum"]
            expression["kind"] = "arithmetic"
            expression["operator"] = "guess"
            expression["operands"] = [expression.pop("below"), expression.pop("atOrAbove")]
            expression.pop("threshold")

        def unknown_type(a):
            expression = a["payload"]["sourceFacts"]["monsters"][0]["initialHp"]["expression"]["minimum"]["below"]
            expression["valueType"] = "float"

        def unknown_operation(a):
            a["payload"]["sourceFacts"]["moves"][0]["operations"][0]["kind"] = "inventEffect"

        def unknown_graph_node(a):
            a["payload"]["sourceFacts"]["graphs"][0]["nodes"][0]["kind"] = "guessed"

        def excessive_depth(a):
            leaf = {"kind": "constant", "value": 1, "valueType": "integer"}
            expression = leaf
            for _ in range(35):
                expression = {"kind": "arithmetic", "operands": [expression, leaf], "operator": "add", "valueType": "integer"}
            a["payload"]["sourceFacts"]["monsters"][0]["initialHp"]["expression"]["minimum"] = expression

        for change, pattern in [
            (unknown_field, "unknown fields"), (unknown_roster, "malformed AST"),
            (unknown_operator, "operator"), (unknown_type, "type"),
            (unknown_operation, "unsupported operation kind"), (unknown_graph_node, "unsupported graph node"),
            (excessive_depth, "depth limit"),
        ]:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_duplicates_bad_joins_refs_and_lane_collisions_fail(self):
        def bad_operation_model(a):
            operation = next(
                op for move in a["payload"]["sourceFacts"]["moves"] for op in move["operations"]
                if op.get("model", "").startswith("POWER.")
            )
            operation["model"] = "POWER.UNKNOWN"

        def cross_lane_ref(a):
            row = a["payload"]["factReferences"][0]
            row["lane"] = "source" if row["lane"] == "legacy" else "legacy"

        def duplicate_monster(a):
            first = a["payload"]["sourceFacts"]["monsters"][0]
            second = a["payload"]["sourceFacts"]["monsters"][1]
            second["canonicalId"] = first["canonicalId"]
            second["canonicalModel"] = first["canonicalModel"]

        cases = [
            (duplicate_monster, "duplicate monster model"),
            (lambda a: a["payload"]["sourceFacts"]["encounters"]["ordinary"][0]["possibleMonsters"].append("MONSTER.UNKNOWN"), "encounter-to-monster"),
            (lambda a: a["payload"]["sourceFacts"]["states"][0].__setitem__("canonicalModel", "MONSTER.UNKNOWN"), "state refers"),
            (lambda a: a["payload"]["sourceFacts"]["moves"][0].__setitem__("ownerRef", "SOURCE.BEHAVIOR_OWNER.MONSTER.UNKNOWN"), "registration-to-owner"),
            (lambda a: a["payload"]["sourceFacts"]["graphs"][0]["edges"][0].__setitem__("to", "GRAPH.AEONGLASS/NOPE"), "edge refers"),
            (bad_operation_model, "operation-model"),
            (lambda a: a["payload"]["legacyAnnotations"]["current"][0].__setitem__("canonicalEncounterRef", "SOURCE.ENCOUNTER.UNKNOWN"), "legacy-to-canonical"),
            (lambda a: a["payload"]["factReferences"][0]["evidenceRefs"].__setitem__(0, "EVIDENCE.UNKNOWN"), "fact-to-evidence"),
            (cross_lane_ref, "fact lane mismatch"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_provenance_lane_policy_and_conflict_mutations_fail(self):
        def bad_evidence(a):
            a["payload"]["evidence"][0]["pointers"][0]["valueSha256"] = "0" * 64

        def missing_conflict(a):
            a["payload"]["conflicts"].pop()

        for change, pattern in [(bad_evidence, "evidence value digest"), (missing_conflict, "missing explicit conflict|unclassified")]:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)
        artifact = deepcopy(self.artifact)
        artifact["authority"]["silentMerge"] = True
        self.assert_invalid(artifact, "silent merge")

    def test_atomic_refusal_normal_build_and_check_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "facts.json"
            output.write_bytes(b"KEEP")
            bad_source = root / "source.json"
            damaged = bytearray(self.source_bytes)
            damaged[-2] = ord(" ") if damaged[-2] != ord(" ") else ord("\t")
            bad_source.write_bytes(damaged)
            with self.assertRaisesRegex(SourceExtractionError, "SHA-256 mismatch"):
                regenerate(bad_source, LEGACY_PATH, output)
            self.assertEqual(output.read_bytes(), b"KEEP")

            regenerate(SOURCE_PATH, LEGACY_PATH, output)
            self.assertEqual(output.read_bytes(), self.projection_bytes)
            regenerate(SOURCE_PATH, LEGACY_PATH, output, check=True)
            output.write_bytes(b"DIFFERENT")
            with self.assertRaisesRegex(SourceExtractionError, "checked projection differs"):
                regenerate(SOURCE_PATH, LEGACY_PATH, output, check=True)
            self.assertEqual(output.read_bytes(), b"DIFFERENT")

    def test_cli_check_and_no_runtime_consumer(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate-encounter-facts.py"), "--check"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified byte-identical", result.stdout)
        for path in (ROOT / "src").glob("*"):
            if path.is_file():
                self.assertNotIn("encounter-facts-v0.111.0", path.read_text(encoding="utf-8"), str(path))


if __name__ == "__main__":
    unittest.main()
