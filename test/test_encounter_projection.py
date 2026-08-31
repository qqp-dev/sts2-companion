from __future__ import annotations

from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import encounter_projection.builder as projection_builder
from encounter_projection.builder import build_artifact, regenerate
from encounter_projection.validator import validate_artifact
from source_extractor.canonical import canonical_json_bytes, witness_sha256
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
        self.assertNotIn("invocationCensus", self.artifact["payload"]["sourceFacts"]["lifecycle"])
        self.assertNotIn(b'"instructions"', first)
        self.assertNotIn(b'"diagnosticMetadataToken"', first)
        self.assertEqual(hashlib.sha256(self.legacy_bytes).hexdigest(), LEGACY_SHA256)
        self.assertNotIn("generatedAt", self.artifact["metadata"])

    def test_counts_lanes_archive_and_readiness(self):
        payload = self.artifact["payload"]
        source = payload["sourceFacts"]
        legacy = payload["legacyAnnotations"]
        self.assertEqual((len(source["encounters"]["ordinary"]), len(source["encounters"]["event"])), (81, 8))
        self.assertEqual((len(source["monsters"]), len(source["moves"]), len(source["graphs"])), (108, 315, 105))
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
        self.assertFalse(any(row["reasonCode"] == "SOURCE_VS_STABLE_HP_ROUNDING_CONFLICT" for row in unknowns))
        audit = next(row for row in payload["resolvedAudits"] if row["auditId"] == "AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING")
        self.assertEqual(audit["auditId"], "AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING")
        self.assertEqual([row["lane"] for row in audit["lanes"]], ["rawSourceHelper", "rawSourceAssignment", "stableLegacyConsumer"])
        self.assertEqual(audit["resolution"]["classification"], "agreementForNonNegativeFinalAssignedHp")
        self.assertFalse(audit["resolution"]["precedenceSelected"])


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
        self.assertEqual(len(owners), 105)
        self.assertTrue(all(row["applicableConcreteModels"] for row in owners.values()))
        self.assertEqual(len(sf["graphs"]), 105)
        self.assertEqual(len(sf["moves"]), 315)
        for row in sf["graphs"] + sf["moves"]:
            self.assertEqual(row["applicableConcreteModels"], owners[row["canonicalMonster"]]["applicableConcreteModels"])
        decimilli_moves = [row for row in sf["moves"] if row["canonicalMonster"] == "MONSTER.DECIMILLIPEDE_SEGMENT"]
        self.assertEqual(len(decimilli_moves), 5)
        self.assertTrue(all(len(row["applicableConcreteModels"]) == 3 for row in decimilli_moves))
        flail = owners["MONSTER.FLAIL_KNIGHT"]
        self.assertEqual(flail["applicabilityKind"], "directModelWithInheritedApplicability")
        self.assertEqual(flail["applicableConcreteModels"], ["MONSTER.FLAIL_KNIGHT", "MONSTER.MYSTERIOUS_KNIGHT"])
        self.assertNotIn("MONSTER.MYSTERIOUS_KNIGHT", owners)

    def test_e2c1_compact_event_turn_facts_and_boundaries(self):
        sf = self.artifact["payload"]["sourceFacts"]
        event = sf["eventTurnBehavior"]
        rows = {row["canonicalEncounter"]: row for row in event["encounters"]}
        self.assertEqual(len(rows), 8)
        self.assertEqual(event["sourceDenominators"], {
            "classifications": 8, "eventIntentArguments": 5, "eventIntentConstructorSites": 6,
            "eventTurnDirectOperations": 6, "eventTurnOperationsIncludingNoOpProofs": 10,
            "noOpProofs": 4, "physicalOwners": 5, "physicalRegistrations": 8,
            "physicalTitles": 8, "reuseOrInheritanceApplicability": 3,
        })
        for version in (1, 2, 3):
            row = rows[f"BATTLEWORN_DUMMY_EVENT_V{version}_ENCOUNTER"]
            self.assertEqual(row["behaviorClassification"], "noOpTurnMachineWithLifecycle")
            self.assertEqual((len(row["dependencyRefs"]), len(row["initialStateFactRefs"])), (1, 1))
            graph = next(item for item in sf["graphs"] if item["factId"] == row["graphRef"])
            self.assertEqual(graph["stateCollection"]["kind"], "readOnlySingle")
            move = next(item for item in sf["moves"] if item["factId"] == row["registrationRefs"][0])
            self.assertEqual((move["action"]["executionKind"], move["operations"][0]["transition"]), ("synchronousNoOp", "noOp"))
        fake = rows["FAKE_MERCHANT_EVENT_ENCOUNTER"]
        self.assertEqual(fake["behaviorClassification"], "normalTurnMachine")
        self.assertEqual(len(fake["registrationRefs"]), 4)
        fake_moves = [next(item for item in sf["moves"] if item["factId"] == ref) for ref in fake["registrationRefs"]]
        self.assertEqual(sum(len(item["intents"]) for item in fake_moves), 5)
        self.assertEqual([op["kind"] for item in fake_moves for op in item["operations"]], ["attack", "attack", "attackHitCount", "attack", "applyPower", "applyPower"])
        mysterious = rows["MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"]
        self.assertEqual((mysterious["behaviorClassification"], mysterious["behaviorOwner"], mysterious["applicability"]), ("inheritedTurnMachine", "MONSTER.FLAIL_KNIGHT", "inherited"))
        self.assertEqual([item["title"]["localizationRoot"] for item in mysterious["titles"]], ["MYSTERIOUS_KNIGHT"] * 3)
        self.assertEqual(rows["DENSE_VEGETATION_EVENT_ENCOUNTER"]["graphId"], "GRAPH.WRIGGLER")
        self.assertEqual(rows["PUNCH_OFF_EVENT_ENCOUNTER"]["graphId"], "GRAPH.PUNCH_CONSTRUCT")
        architect = rows["THE_ARCHITECT_EVENT_ENCOUNTER"]
        self.assertEqual(architect["behaviorClassification"], "scriptedNonTurnCombat")
        self.assertEqual(len(architect["dependencyRefs"]), 1)
        unknowns = {row["unknownId"]: row for row in self.artifact["payload"]["knownUnknowns"]}
        self.assertNotIn("UNKNOWN.EVENT_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_SCRIPTED_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_LIFECYCLE", unknowns)
        audit = next(row for row in self.artifact["payload"]["resolvedAudits"] if row["auditId"] == "AUDIT.RESOLVED.EVENT_TURN_MACHINES")
        self.assertEqual((len(audit["classificationFactRefs"]), len(audit["dependencyFactRefs"])), (8, 4))
        self.assertIn("separately source-complete", audit["boundary"])
        serialized = json.dumps(event)
        self.assertNotIn("decisionRefs", serialized)
        self.assertNotIn("eventTurnInvocationCensus", serialized)
        self.assertNotIn("sourceRoots", serialized)

    def test_e2c1_event_mutations_fail_closed(self):
        def event(a): return a["payload"]["sourceFacts"]["eventTurnBehavior"]
        def row(a, encounter): return next(item for item in event(a)["encounters"] if item["canonicalEncounter"] == encounter)
        cases = [
            (lambda a: row(a, "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER").__setitem__("applicability", "direct"), "inherited applicability"),
            (lambda a: row(a, "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER")["titles"][0]["title"].__setitem__("localizationRoot", "FLAIL_KNIGHT"), "title-root"),
            (lambda a: row(a, "THE_ARCHITECT_EVENT_ENCOUNTER").__setitem__("behaviorClassification", "normalTurnMachine"), "dependency cardinality"),
            (lambda a: row(a, "THE_ARCHITECT_EVENT_ENCOUNTER")["dependencyRefs"].clear(), "dependency cardinality"),
            (lambda a: row(a, "BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER").__setitem__("behaviorClassification", "normalTurnMachine"), "dependency cardinality"),
            (lambda a: row(a, "FAKE_MERCHANT_EVENT_ENCOUNTER")["registrationRefs"].pop(), "title/registration"),
            (lambda a: row(a, "DENSE_VEGETATION_EVENT_ENCOUNTER").__setitem__("graphRef", "SOURCE.GRAPH.FAKE_MERCHANT_MONSTER"), "join mismatch|applicability"),
            (lambda a: event(a)["sourceDenominators"].__setitem__("physicalRegistrations", 7), "denominator"),
            (lambda a: event(a)["dependencies"].pop(), "four dependency"),
            (lambda a: next(item for item in a["payload"]["sourceFacts"]["graphs"] if item["graphId"] == "GRAPH.BATTLE_FRIEND_V1")["stateCollection"].__setitem__("cardinality", 2), "cardinality"),
            (lambda a: next(item for item in a["payload"]["sourceFacts"]["graphs"] if item["graphId"] == "GRAPH.BATTLE_FRIEND_V1")["stateCollection"].__setitem__("elementType", "NamedLikeMoveState"), "element type"),
            (lambda a: next(item for item in a["payload"]["sourceFacts"]["moves"] if item["canonicalId"] == "MONSTER.BATTLE_FRIEND_V1#NOTHING_MOVE")["operations"][0].__setitem__("transition", "nonnumericOrStateUpdate"), "source-inspected"),
            (lambda a: next(item for item in a["payload"]["sourceFacts"]["graphs"] if item["graphId"] == "GRAPH.FAKE_MERCHANT_MONSTER")["stateCollection"]["orderedNodes"].reverse(), "deterministic two-lane derivation|evidence value digest"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_e2c1_raw_event_mutations_fail_closed(self):
        def assert_bad(change, pattern):
            source = deepcopy(self.source)
            change(source)
            with self.assertRaisesRegex(SourceExtractionError, pattern):
                validate_artifact(self.artifact, source=source, legacy=self.legacy)
        def fake_registration(source, state="SWIPE_MOVE"):
            return next(row for row in source["behavior"]["registrations"] if row["canonicalId"] == f"MONSTER.FAKE_MERCHANT_MONSTER#{state}")
        def mysterious(source):
            return next(row for row in source["behavior"]["eventTurnMachines"] if row["canonicalEncounter"] == "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER")
        cases = [
            (lambda source: source["behavior"]["eventTurnMachines"].pop(), "one classification for every event"),
            (lambda source: source["behavior"]["eventDependencies"].pop(), "four explicit"),
            (lambda source: source["behavior"]["registrations"].pop(), "315 registrations"),
            (lambda source: fake_registration(source)["intents"].pop(), "intent/action/title denominator"),
            (lambda source: fake_registration(source)["operations"].clear(), "operation closure|sink denominator"),
            (lambda source: source["behavior"]["invocationCensus"]["decisions"].pop(), "closed invocation denominator"),
            (lambda source: source["behavior"]["eventTurnInvocationCensus"]["decisionRefs"].pop(), "event helper invocation"),
            (lambda source: mysterious(source)["titles"][0]["title"].__setitem__("localizationRoot", "FLAIL_KNIGHT"), "localization root"),
            (lambda source: next(row for row in source["behavior"]["applicability"] if row["behaviorOwnerSourceType"].endswith(".FlailKnight"))["applicableConcreteModels"].pop(), "applicability"),
            (lambda source: next(row for row in source["behavior"]["graphs"] if row["graphId"] == "GRAPH.BATTLE_FRIEND_V1")["stateCollection"].__setitem__("constructor", "<TypeSpec:bad>::.ctor sig:2001011300"), "constructor/overload"),
            (lambda source: source["behavior"]["eventDependencies"][0]["sourceRoots"].clear(), "source roots"),
            (lambda source: source["coverage"]["eventTurnClassifications"].__setitem__("denominator", 7), "eventTurnClassifications"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                assert_bad(change, pattern)

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
        self.assertNotIn("UNKNOWN.LIFECYCLE_COVERAGE", unknowns)
        self.assertIn("UNKNOWN.FORMULA_RUNTIME_CONTRACTS", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_SCRIPTED_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_LIFECYCLE", unknowns)
        self.assertNotIn("UNKNOWN.HP_ROUNDING_CONFLICT", unknowns)
        companion = payload["readiness"]["runtimeScopes"]["encounterCompanion"]
        self.assertEqual((companion["ready"], companion["status"]), (False, "incomplete"))
        self.assertEqual(companion["reasonRefs"], ["UNKNOWN.FORMULA_RUNTIME_CONTRACTS"])

    def test_e2_lifecycle_closeout_and_readiness_boundary(self):
        lifecycle=self.artifact["payload"]["sourceFacts"]["lifecycle"]
        self.assertEqual((lifecycle["componentId"],lifecycle["status"],lifecycle["factId"]),
                         ("LIFECYCLE.CORE.E2D2A","sourceCompleteE2Lifecycle","SOURCE.LIFECYCLE.CORE.E2D2A"))
        self.assertEqual([row["parameters"] for row in lifecycle["api"]["commandDeclarations"]],
                         [["creature","force"],["creatures","force"],["creature","force","recursion"],["creature","removeCreatureNode"]])
        expected_core={
            "centralizedCheckCallSites":14,"commandDeclarations":4,"commandPhysicalBodies":4,
            "dependencies":7,"dispatchMethods":6,"escapeCallSites":3,"invocations":707,"killCallSites":21,
            "listenerRegistryLogicalMethods":3,"listenerRegistryPhysicalBodies":3,"removalMethods":4,
            "runtimeBoundaries":7,"semanticNodes":59,"terminationDeclarations":4,
            "terminationPhysicalBodies":4,"terminationSupportMethods":3}
        self.assertEqual({key:value for key,value in lifecycle["sourceDenominators"].items()
                          if not key.startswith("closeout.")}, expected_core)
        self.assertEqual({key:value for key,value in lifecycle["sourceDenominators"].items()
                          if key.startswith("closeout.")}, {
            "closeout.beforeRemovedCleanup":11,"closeout.deathAddPhysicalSites":4,
            "closeout.deathProductionSystems":3,"closeout.effectiveListenerApplications":1861,
            "closeout.eventCombatRegistrations":7,"closeout.fixedPointPowerTypes":71,
            "closeout.invocationDecisions":1265,"closeout.listenerImplementations":80,
            "closeout.monsterOwnerTypes":108,"closeout.phaseSystems":6,"closeout.powerSeedTypes":69,
            "closeout.relationships":6,"closeout.runTerminationSystems":1,"closeout.subscriptions":3})
        self.assertFalse(lifecycle["core"]["innerDeathGraph"]["directCheckWinCondition"])
        self.assertFalse(lifecycle["core"]["innerDeathGraph"]["deadBodyEntryShortCircuit"])
        list_graph=lifecycle["core"]["listKillGraph"]
        self.assertEqual([row["nodeId"].rsplit(".",1)[-1] for row in list_graph["nodes"]],
                         ["emptyReturn","snapshotRun","snapshotBodies","sequentialInner","managerGuard",
                          "allPlayersDead","liveCombatLoss","testModeGate","gameOver","endKilledTurns"])
        list_edges={row["edgeId"]:row for row in list_graph["edges"]}
        self.assertEqual(list_edges["LIFECYCLE.KILL.LIST.EDGE.LIVE_COMBAT_LOSS"]["to"],"LIFECYCLE.KILL.LIST.06.liveCombatLoss")
        self.assertEqual(list_edges["LIFECYCLE.KILL.LIST.EDGE.LOSS_FALLTHROUGH"]["to"],"LIFECYCLE.KILL.LIST.07.testModeGate")
        self.assertEqual(list_edges["LIFECYCLE.KILL.LIST.EDGE.NON_LIVE_ALL_DEAD"]["to"],"LIFECYCLE.KILL.LIST.07.testModeGate")
        self.assertEqual(list_edges["LIFECYCLE.KILL.LIST.EDGE.TEST_OFF"]["to"],"LIFECYCLE.KILL.LIST.08.gameOver")
        self.assertEqual(list_edges["LIFECYCLE.KILL.LIST.EDGE.TEST_ON"]["to"],"LIFECYCLE.KILL.LIST.OUTCOME.TEST_MODE_SKIPPED")
        inner=lifecycle["core"]["innerDeathGraph"]
        inner_edges={row["edgeId"]:row for row in inner["edges"]}
        guard_outcomes=[inner_edges[edge_id]["to"] for edge_id in (
            "LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED",
            "LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED")]
        self.assertEqual(guard_outcomes,["LIFECYCLE.KILL.INNER.OUTCOME.DETACHED_NON_PLAYER_COMPLETED",
                                        "LIFECYCLE.KILL.INNER.OUTCOME.ATTACHED_NON_LIVE_COMPLETED"])
        self.assertFalse(any(row["from"] in guard_outcomes for row in inner["edges"]))
        self.assertEqual(lifecycle["dispatch"]["awaitedDispatch"]["parallelism"],"none")
        self.assertEqual([row["source"] for row in lifecycle["listenerRegistry"]["combatOrder"]],
                         ["allies then enemies","each creature","active player contents","combat globals","mod combat subscribers"])
        self.assertEqual(lifecycle["removal"]["escapeDeathHooks"],[])
        self.assertIsNone(lifecycle["removal"]["escapeResultEnum"])
        self.assertFalse(lifecycle["combatTermination"]["victoryPredicate"]["secondaryOnlyEnemiesBlock"])
        self.assertEqual(lifecycle["combatTermination"]["victoryPredicate"]["allEscaped"],"ordinary victory at the next centralized check")
        self.assertEqual({row["status"] for row in lifecycle["dependencies"]},{"sourceComplete"})
        self.assertEqual(len(lifecycle["runtimeBoundaries"]),7)
        serialized=json.dumps(lifecycle)
        for forbidden in ("playDeathEffects","diagnosticMetadataToken","cilInstructionsSha256","methodBodySha256","commandCallSites"):
            self.assertNotIn(forbidden,serialized)
        audit=next(row for row in self.artifact["payload"]["resolvedAudits"] if row["auditId"]=="AUDIT.RESOLVED.CORE_LIFECYCLE")
        self.assertEqual(audit["classificationFactRefs"],[lifecycle["factId"]])
        self.assertEqual(set(audit["dependencyFactRefs"]),{row["factId"] for row in lifecycle["dependencies"]})
        unknown_ids={row["unknownId"] for row in self.artifact["payload"]["knownUnknowns"]}
        self.assertNotIn("UNKNOWN.LIFECYCLE_COVERAGE",unknown_ids)
        self.assertNotIn("UNKNOWN.EVENT_LIFECYCLE",unknown_ids)
        self.assertNotIn("UNKNOWN.EVENT_BEHAVIOR",unknown_ids)
        self.assertEqual(lifecycle["listenerCensus"]["effectiveApplications"],1861)
        mechanics=lifecycle["mechanics"]
        self.assertEqual([len(mechanics[key]) for key in ("cleanup","deathProduction","phaseSystems","powerRetentionPolicies","relationships","subscriptions")],[11,3,6,18,6,3])
        minion_fatal=next(row for row in mechanics["powerRetentionPolicies"]
                          if row["policyId"]=="LIFECYCLE.RETENTION.POWER.MINION_POWER.SHOULDOWNERDEATHTRIGGERFATAL")
        self.assertIs(minion_fatal["result"],False)
        self.assertEqual(minion_fatal["condition"],{"kind":"constant","value":True,"valueType":"boolean"})
        self.assertNotIn("targetIsPowerOwner",json.dumps(minion_fatal))
        self.assertEqual([row["kind"] for row in mechanics["doom"]["orderedEffects"]],["doomVfx","kill","afterDiedToDoom"])
        self.assertFalse(mechanics["doom"]["orderedEffects"][2]["perBody"])
        subject=next(row for row in mechanics["phaseSystems"] if row["phaseSystemId"]=="LIFECYCLE.PHASE.TEST_SUBJECT_ADAPTABLE")
        self.assertEqual(subject["derivedCompletedReviveCount"],2)
        self.assertIsNone(subject["capField"])
        egg=next(row for row in mechanics["phaseSystems"] if row["phaseSystemId"]=="LIFECYCLE.PHASE.TOUGH_EGG_HATCH")
        self.assertEqual(egg["titleContract"],{"getterField":"_hatched","hatchWritesTitle":False,"isHatchedField":"_isHatched"})
        self.assertEqual([row["transitionId"] for row in egg["transitions"]],[
            "LIFECYCLE.TRANSITION.TOUGH_EGG.HATCH_COUNTDOWN",
            "LIFECYCLE.TRANSITION.TOUGH_EGG.NORMAL_HATCH",
            "LIFECYCLE.TRANSITION.TOUGH_EGG.RESTORED_HATCH"])
        countdown=egg["transitions"][0]
        self.assertEqual(countdown["condition"],{
            "kind":"comparison","left":{"kind":"runtimeInput","name":"sideTurn.participantsContainsOwner","valueType":"boolean"},
            "operator":"equal","right":{"kind":"constant","value":True,"valueType":"boolean"},"valueType":"boolean"})
        self.assertEqual(countdown["orderedEffects"],[{
            "amount":1,"execution":"awaited","kind":"decrementPower","order":0,
            "owner":"POWER.HATCH_POWER","target":"sameOwnerBody"}])
        self.assertEqual(Counter(row["shouldResumeParentEventAfterCombat"] for row in mechanics["eventCombat"]["registrations"]),Counter({False:4,True:3}))
        self.assertFalse(self.artifact["payload"]["readiness"]["runtimeScopes"]["encounterCompanion"]["ready"])
        self.assertTrue(self.artifact["payload"]["readiness"]["runtimeScopes"]["encounterProjection"]["ready"])

    def test_e2d2a_compact_mutations_fail_closed(self):
        def lifecycle(a):return a["payload"]["sourceFacts"]["lifecycle"]
        cases=[
            (lambda a:lifecycle(a)["api"]["commandDeclarations"][0]["parameters"].__setitem__(1,"playDeathEffects"),"legacy kill Boolean|force/removeCreatureNode"),
            (lambda a:lifecycle(a)["core"]["innerDeathGraph"].__setitem__("forceContract","force skips all hooks"),"force/entry-guard/dead-body/direct-win"),
            (lambda a:lifecycle(a)["core"]["innerDeathGraph"].__setitem__("directCheckWinCondition",True),"force/entry-guard/dead-body/direct-win"),
            (lambda a:lifecycle(a)["core"]["innerDeathGraph"].__setitem__("deadBodyEntryShortCircuit",True),"force/entry-guard/dead-body/direct-win"),
            (lambda a:next(row for row in lifecycle(a)["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.INNER_FAILED").__setitem__("kind","sourceOrder"),"loss/test-mode fallthrough"),
            (lambda a:next(row for row in lifecycle(a)["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.GAME_OVER").__setitem__("kind","awaitSuccess"),"loss/test-mode fallthrough"),
            (lambda a:next(row for row in lifecycle(a)["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.LOSS_FALLTHROUGH").__setitem__("to","LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER"),"loss/test-mode fallthrough"),
            (lambda a:next(row for row in lifecycle(a)["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.NON_LIVE_ALL_DEAD").__setitem__("to","LIFECYCLE.KILL.LIST.08.gameOver"),"loss/test-mode fallthrough"),
            (lambda a:next(row for row in lifecycle(a)["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.FAIL.02").__setitem__("kind","awaitSuccess"),"entry guards or safety Heal"),
            (lambda a:next(row for row in lifecycle(a)["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED").__setitem__("to","LIFECYCLE.KILL.INNER.04.zeroHp"),"entry guards or safety Heal"),
            (lambda a:next(row for row in lifecycle(a)["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED").__setitem__("to","LIFECYCLE.KILL.INNER.04.zeroHp"),"entry guards or safety Heal"),
            (lambda a:next(row for row in lifecycle(a)["combatTermination"]["victoryGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.COMBAT.VICTORY.EDGE.REVIVE_FAIL").__setitem__("kind","sourceOrder"),"player revive success/failure"),
            (lambda a:lifecycle(a)["dispatch"]["awaitedDispatch"].__setitem__("parallelism","Task.WhenAll"),"ordered awaited dispatch"),
            (lambda a:lifecycle(a)["listenerRegistry"]["combatOrder"].reverse(),"source lifecycle semantic join"),
            (lambda a:lifecycle(a)["removal"]["escapeDeathHooks"].append("BeforeDeath"),"escape death/result/node"),
            (lambda a:lifecycle(a)["removal"]["escapeGraph"]["nodes"][2].__setitem__("condition","force == true"),"source lifecycle semantic join"),
            (lambda a:lifecycle(a)["combatTermination"].__setitem__("resultEnum","Victory"),"result enum invented"),
            (lambda a:lifecycle(a)["combatTermination"]["victoryPredicate"].__setitem__("secondaryOnlyEnemiesBlock",True),"secondary/all-escape"),
            (lambda a:lifecycle(a)["combatTermination"]["victoryPredicate"].__setitem__("allEscaped","special escape result"),"secondary/all-escape"),
            (lambda a:lifecycle(a)["combatTermination"]["actionExecutorEdges"][2].__setitem__("result","success"),"source lifecycle semantic join"),
            (lambda a:lifecycle(a)["dependencies"].pop(),"dependency closure"),
            (lambda a:lifecycle(a)["runtimeBoundaries"].pop(),"runtime boundaries"),
            (lambda a:lifecycle(a)["digests"].__setitem__("coreSemanticsSha256","0"*64),"digest join"),
            (lambda a:lifecycle(a).__setitem__("commandCallSites",[]),"unknown fields"),
            (lambda a:a["payload"]["resolvedAudits"].pop(next(i for i,row in enumerate(a["payload"]["resolvedAudits"]) if row["auditId"]=="AUDIT.RESOLVED.CORE_LIFECYCLE")),"expected HP, production, lifecycle"),
            (lambda a:a["payload"]["readiness"]["runtimeScopes"]["encounterCompanion"].__setitem__("ready",True),"sole hard-false companion gate"),
            (lambda a:lifecycle(a)["listenerCensus"].__setitem__("fixedPointPowerTypes",70),"fixed-point listener census"),
            (lambda a:lifecycle(a)["mechanics"]["phaseSystems"].pop(),"mechanics cardinality"),
            (lambda a:lifecycle(a)["mechanics"]["doom"]["orderedEffects"][2].__setitem__("perBody",True),"payload differs|deterministic two-lane"),
            (lambda a:lifecycle(a)["semanticPipelineAudit"].__setitem__("duplicateDeathEvaluator",True),"duplicate semantic pipeline"),
        ]
        for change,pattern in cases:
            with self.subTest(pattern=pattern):self.assert_invalid(self.mutated(change),pattern)

    def test_e2d2a_raw_source_mutations_fail_closed(self):
        def assert_bad(change,pattern):
            source=deepcopy(self.source);change(source)
            with self.assertRaisesRegex(SourceExtractionError,pattern):
                validate_artifact(self.artifact,source=source,legacy=self.legacy)
        kill=next(op for move in self.source["behavior"]["registrations"] for op in move["operations"] if op.get("kind")=="kill")
        move_index=next(i for i,move in enumerate(self.source["behavior"]["registrations"]) if kill in move["operations"])
        op_index=self.source["behavior"]["registrations"][move_index]["operations"].index(kill)
        cases=[
            (lambda s:(s["behavior"]["registrations"][move_index]["operations"][op_index].__setitem__("playDeathEffects",s["behavior"]["registrations"][move_index]["operations"][op_index].pop("force"))),"unknown fields"),
            (lambda s:s["lifecycle"]["api"]["commandDeclarations"][0]["parameters"][1].__setitem__("name","playDeathEffects"),"parameter names/order|legacy playDeathEffects"),
            (lambda s:s["lifecycle"]["core"]["innerDeathGraph"].__setitem__("forceContract","force skips hooks"),"force bypass/entry-guard boundary"),
            (lambda s:s["lifecycle"]["core"]["innerDeathGraph"].__setitem__("directCheckWinCondition",True),"invented a win check"),
            (lambda s:s["lifecycle"]["core"]["innerDeathGraph"].__setitem__("deadBodyEntryShortCircuit",True),"dead-body short circuit"),
            (lambda s:next(row for row in s["lifecycle"]["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.INNER_FAILED").__setitem__("kind","sourceOrder"),"loss/test-mode fallthrough"),
            (lambda s:next(row for row in s["lifecycle"]["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.GAME_OVER").__setitem__("kind","awaitSuccess"),"loss/test-mode fallthrough"),
            (lambda s:next(row for row in s["lifecycle"]["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.LOSS_FALLTHROUGH").__setitem__("to","LIFECYCLE.KILL.LIST.OUTCOME.GAME_OVER"),"loss/test-mode fallthrough"),
            (lambda s:next(row for row in s["lifecycle"]["core"]["listKillGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.LIST.EDGE.NON_LIVE_ALL_DEAD").__setitem__("to","LIFECYCLE.KILL.LIST.08.gameOver"),"loss/test-mode fallthrough"),
            (lambda s:next(row for row in s["lifecycle"]["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.FAIL.02").__setitem__("kind","awaitSuccess"),"completed guards or safety Heal"),
            (lambda s:(
                next(row for row in s["lifecycle"]["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.DETACHED_NON_PLAYER_COMPLETED").__setitem__("to","LIFECYCLE.KILL.INNER.04.zeroHp"),
                next(row for row in s["lifecycle"]["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.GUARDS_PASSED").__setitem__("to","LIFECYCLE.KILL.INNER.OUTCOME.DETACHED_NON_PLAYER_COMPLETED")),"completed guards or safety Heal"),
            (lambda s:(
                next(row for row in s["lifecycle"]["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.ATTACHED_NON_LIVE_COMPLETED").__setitem__("to","LIFECYCLE.KILL.INNER.04.zeroHp"),
                next(row for row in s["lifecycle"]["core"]["innerDeathGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.KILL.INNER.EDGE.GUARDS_PASSED").__setitem__("to","LIFECYCLE.KILL.INNER.OUTCOME.ATTACHED_NON_LIVE_COMPLETED")),"completed guards or safety Heal"),
            (lambda s:next(row for row in s["lifecycle"]["combatTermination"]["victoryGraph"]["edges"] if row["edgeId"]=="LIFECYCLE.COMBAT.VICTORY.EDGE.REVIVE_FAIL").__setitem__("kind","sourceOrder"),"player-revive success/failure"),
            (lambda s:s["lifecycle"]["combatTermination"]["pendingLoss"].__setitem__("representation","CombatResult.Win"),"invented CombatResult"),
            (lambda s:s["lifecycle"]["dispatch"]["awaitedDispatch"].__setitem__("parallelism","Task.WhenAll"),"canonical digest"),
            (lambda s:s["lifecycle"]["removal"]["escapeDeathHooks"].append("Died"),"escape invented death hooks"),
            (lambda s:s["lifecycle"]["combatTermination"].__setitem__("resultEnum","Victory"),"result enum"),
            (lambda s:s["lifecycle"]["runtimeBoundaries"][0].__setitem__("classification","ignored"),"broad ignored"),
            (lambda s:s["lifecycle"]["dependencies"].pop(),"dependencies|canonical digest"),
            (lambda s:s["lifecycle"]["digests"].__setitem__("methodClosureSha256","f"*64),"canonical digest"),
        ]
        for change,pattern in cases:
            with self.subTest(pattern=pattern):assert_bad(change,pattern)

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
            (lambda a: a["payload"]["readiness"]["runtimeScopes"]["encounterCompanion"].__setitem__("ready", True), "sole hard-false companion gate"),
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

    def test_e2b_pipeline_projection_and_mutations_fail_closed(self):
        hp = self.artifact["payload"]["sourceFacts"]["hpPipeline"]
        self.assertNotIn("callCensus", hp)
        self.assertNotIn("provenance", hp)
        self.assertEqual(hp["factId"], "SOURCE.HP_ASSIGNMENT_PIPELINE")
        self.assertEqual(hp["assignment"]["numericContract"]["arithmeticRounding"], "none")
        self.assertEqual(hp["assignment"]["conversion"]["mode"], "truncateTowardZero")
        self.assertEqual(hp["assignment"]["max"]["cap"], 999999999)
        self.assertEqual(hp["networkStorage"]["wireBits"], 32)
        self.assertEqual([row["pathId"] for row in hp["specialCallPaths"]], ["DECIMILLIPEDE", "TEST_SUBJECT", "TOUGH_EGG"])

        def projected(change):
            return lambda artifact: change(artifact["payload"]["sourceFacts"]["hpPipeline"])
        cases = [
            (projected(lambda row: row["assignment"]["conversion"].__setitem__("mode", "floor")), "conversion|deterministic"),
            (projected(lambda row: row["assignment"]["max"].__setitem__("cap", 999999998)), "deterministic"),
            (projected(lambda row: row["assignment"]["max"].__setitem__("capOrder", "beforeDecimalToInt32Conversion")), "deterministic"),
            (projected(lambda row: row["assignment"]["max"].__setitem__("negativeInput", "accepted")), "deterministic"),
            (projected(lambda row: row["networkStorage"]["fields"]["currentHp"].__setitem__("cliType", "Decimal")), "deterministic"),
            (projected(lambda row: row["commandWrappers"][3]["joins"].reverse()), "deterministic"),
            (projected(lambda row: row["specialCallPaths"].pop()), "deterministic"),
            (projected(lambda row: row["baseSelection"].__setitem__("fallback", "none")), "deterministic"),
            (lambda a: next(row for row in a["payload"]["resolvedAudits"] if row["auditId"] == "AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING")["resolution"].__setitem__("precedenceSelected", True), "without precedence"),
            (lambda a: next(row for row in a["payload"]["resolvedAudits"] if row["auditId"] == "AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING")["lanes"].pop(), "authority lanes"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_e2b_raw_pipeline_mutations_fail_closed(self):
        def assert_bad(change, pattern):
            source = deepcopy(self.source)
            change(source["hpPipeline"])
            with self.assertRaisesRegex(SourceExtractionError, pattern):
                validate_artifact(self.artifact, source=source, legacy=self.legacy)
        cases = [
            (lambda hp: hp["assignment"]["conversion"].__setitem__("mode", "floor"), "conversion"),
            (lambda hp: hp["assignment"]["max"].__setitem__("cap", 10), "cap"),
            (lambda hp: hp["assignment"]["max"].__setitem__("negativeInput", "none"), "guard|order|drift"),
            (lambda hp: hp["networkStorage"]["fields"]["maxHp"].__setitem__("cliType", "Decimal"), "wire fields"),
            (lambda hp: hp["commandWrappers"][3]["joins"].reverse(), "assignment order"),
            (lambda hp: hp["commandWrappers"].append({"command": "UnknownSetter", "joins": ["SetMaxHpInternal"]}), "unknown setter overload|assignment order"),
            (lambda hp: hp["specialCallPaths"].pop(), "special caller"),
            (lambda hp: hp["baseSelection"].__setitem__("fallback", "none"), "unique-selection"),
            (lambda hp: hp["sourceDenominators"].__setitem__("completePipelineSemanticFields", 82), "Denominators|denominators"),
            (lambda hp: hp["provenance"]["setMax"].pop("methodBodySha256"), "methodBodySha256"),
            (lambda hp: hp["callCensus"]["targetSites"].pop(), "target call closure"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                assert_bad(change, pattern)

    def test_e2c2a_compact_scripts_and_mutation_gates(self):
        scripts = self.artifact["payload"]["sourceFacts"]["eventScripts"]
        self.assertEqual(scripts["sourceDenominators"], {
            "dependencies": 6, "displayScalingCalls": 3, "edges": 20, "effects": 10,
            "encounterScripts": 7, "frameworkMethods": 53, "invocations": 1549,
            "methods": 76, "nodes": 25, "options": 12, "outcomes": 7,
            "owners": 5, "stateContracts": 10, "supportMethods": 14,
        })
        serialized = json.dumps(scripts)
        self.assertNotIn('"invocationCensus"', serialized)
        self.assertNotIn('"decisions"', serialized)
        self.assertNotIn('"instructions"', serialized)
        unknowns = {row["unknownId"]: row for row in self.artifact["payload"]["knownUnknowns"]}
        self.assertNotIn("UNKNOWN.EVENT_SCRIPTED_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_LIFECYCLE", unknowns)
        self.assertFalse(self.artifact["payload"]["readiness"]["runtimeScopes"]["encounterCompanion"]["ready"])

        cases = [
            (lambda e: e["transitions"][0].__setitem__("canonicalEncounter", "ENCOUNTER.SWAPPED"), "transition/E1"),
            (lambda e: e["transitions"][0]["resume"].__setitem__("shouldResume", "true"), "decoded Boolean"),
            (lambda e: e["transitions"][4]["addedRewards"][0].__setitem__("rewardType", "UnknownReward"), "unknown reward constructor"),
            (lambda e: e["options"][0]["callback"].__setitem__("target", "ambiguous"), "delegate receiver"),
            (lambda e: e["owners"][1]["availability"].__setitem__("expression", {"kind": "constant", "value": 8}), "HpLoss was flattened"),
            (lambda e: e["outcomes"].pop(), "expected 7"),
            (lambda e: e["dependencies"].pop(), "expected 6"),
            (lambda e: e["sourceDenominators"].__setitem__("edges", 19), "stale edges"),
            (lambda e: e.__setitem__("invocationCensus", {"decisions": []}), "keys differ|unknown fields"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                artifact = self.mutated(lambda a: change(a["payload"]["sourceFacts"]["eventScripts"]))
                self.assert_invalid(artifact, pattern)

    def test_e2c2b_architect_compact_facts_and_mutation_gates(self):
        scripts = self.artifact["payload"]["sourceFacts"]["eventScripts"]
        architect = scripts["architect"]
        self.assertEqual(architect["sourceDenominators"], {
            "dependencies": 5, "edges": 39, "invocations": 715, "lines": 39,
            "localizationKeys": 64, "methods": 96, "nodes": 39, "options": 2,
            "presentationMethods": 13, "runtimeContracts": 8, "semanticEffects": 6,
            "templates": 17,
        })
        self.assertEqual((len(architect["dialogue"]["templates"]),
                          sum(len(row["lines"]) for row in architect["dialogue"]["templates"])), (17, 39))
        serialized = json.dumps(architect)
        self.assertNotIn("methods", architect)
        self.assertNotIn('"invocationCensus"', serialized)
        self.assertNotIn('"decisions"', serialized)
        self.assertNotIn('"instructions"', serialized)
        self.assertNotRegex(serialized, r'"(?:value|text|prose|template)":')
        self.assertEqual(architect["visualOnlyCombat"]["classification"], "notActiveCombat")
        self.assertEqual(architect["visualOnlyCombat"]["roomMode"], "VisualOnly")
        self.assertFalse(architect["presentation"]["completeSliceHasGameplayDamage"])
        self.assertEqual(architect["roomEntry"]["scoreReference"]["arguments"], ["event.owner.runState", True])
        self.assertTrue(architect["terminal"]["localOwnerGuarded"])
        self.assertFalse(architect["terminal"]["eventCombatTransition"])
        unknowns = {row["unknownId"]: row for row in self.artifact["payload"]["knownUnknowns"]}
        self.assertNotIn("UNKNOWN.EVENT_SCRIPTED_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_BEHAVIOR", unknowns)
        self.assertNotIn("UNKNOWN.EVENT_LIFECYCLE", unknowns)
        audit = next(row for row in self.artifact["payload"]["resolvedAudits"]
                     if row["auditId"] == "AUDIT.RESOLVED.ARCHITECT_SCRIPT")
        self.assertEqual(audit["historicalStatus"], "sourceComplete")
        self.assertEqual(audit["sourceDenominators"], architect["sourceDenominators"])

        cases = [
            (lambda a: a["dialogue"]["selection"].__setitem__("concreteTemplate", {"kind": "constant", "valueType": "AncientDialogue"}), "dynamic template"),
            (lambda a: a["dialogue"]["selection"].__setitem__("rngInput", "none"), "RNG input"),
            (lambda a: a["dialogue"]["templates"][0]["lines"][0].__setitem__("speaker", "Wrong"), "speaker"),
            (lambda a: a["dialogue"]["templates"][0]["lines"].reverse(), "line count/order"),
            (lambda a: a["localization"].__setitem__("prose", "copied"), "prose"),
            (lambda a: a["localization"]["keyValueWitnesses"][0].__setitem__("valueSha256", "0" * 64), "digests"),
            (lambda a: a["initialState"].__setitem__("lineIndexInitialization", 1), "line-zero"),
            (lambda a: a["initialState"]["options"][0]["callback"].__setitem__("target", "ambiguous"), "option target"),
            (lambda a: a["visualOnlyCombat"].__setitem__("roomMode", "Normal"), "active-combat"),
            (lambda a: a["visualOnlyCombat"].__setitem__("classification", "activeCombat"), "active-combat"),
            (lambda a: a["visualOnlyCombat"].__setitem__("hiddenTurnFactRole", "sufficient"), "hidden-no-op"),
            (lambda a: a["presentation"].__setitem__("completeSliceHasGameplayDamage", True), "damage"),
            (lambda a: a["presentation"]["scoreSplit"].__setitem__("renderDeterministically", True), "score split"),
            (lambda a: a["roomEntry"]["scoreReference"]["arguments"].__setitem__(1, False), "score overload/argument"),
            (lambda a: a["terminal"]["orderedControl"].reverse(), "WinRun order"),
            (lambda a: a["terminal"].__setitem__("localOwnerGuarded", False), "local-owner"),
            (lambda a: a["terminal"]["runManagerBoundary"].__setitem__("onEndedArgument", False), "lifecycle dependency"),
            (lambda a: a["lineControl"]["edges"].pop(), "graph closure"),
            (lambda a: a["dependencies"].pop(), "dependency refs"),
            (lambda a: a["sourceDenominators"].__setitem__("templates", 16), "denominator"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                artifact = self.mutated(lambda root: change(root["payload"]["sourceFacts"]["eventScripts"]["architect"]))
                self.assert_invalid(artifact, pattern)

    def test_e2c2b_raw_architect_mutations_fail(self):
        cases = [
            (lambda a: a["presentation"].__setitem__("completeSliceHasGameplayDamage", True), "presentation/gameplay"),
            (lambda a: a["visualOnlyCombat"].__setitem__("classification", "activeCombat"), "visual-only|active combat"),
            (lambda a: a["terminal"]["orderedControl"].reverse(), "reordered"),
            (lambda a: a["terminal"]["runManagerBoundary"].__setitem__("onEndedArgument", False), "lifecycle"),
            (lambda a: a["invocationCensus"]["decisions"][0].__setitem__("symbolSignature", "MegaCrit.Sts2.Core.Commands.CreatureCmd::Damage sig:bad"), "damage/attack"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                source = deepcopy(self.source); change(source["eventScripts"]["architect"])
                with self.assertRaisesRegex(SourceExtractionError, pattern):
                    validate_artifact(self.artifact, source=source, legacy=self.legacy)

    def test_e2c2a_raw_source_mutations_fail(self):
        cases = [
            (lambda e: e["sourceDenominators"].__setitem__("invocations", 1), "invocation denominator"),
            (lambda e: e["transitions"][0]["resume"].__setitem__("shouldResume", None), "transition semantic arguments"),
            (lambda e: e["owners"][1]["availability"].__setitem__("expression", {"kind": "constant", "value": 8}), "Dense HpLoss"),
            (lambda e: e["outcomes"].pop(), "denominator outcomes|outcome closure"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                source=deepcopy(self.source);change(source["eventScripts"])
                with self.assertRaisesRegex(SourceExtractionError, pattern):
                    validate_artifact(self.artifact, source=source, legacy=self.legacy)

    def test_e2d1a_compact_random_and_production_contracts(self):
        source = self.artifact["payload"]["sourceFacts"]
        random = source["randomSelection"]
        self.assertEqual(random["summary"], {
            "branches": 61, "floatCallbacks": 8, "graphs": 21, "overloads": 10,
            "repeatTypeDistribution": {"CanRepeatForever": 4, "CanRepeatXTimes": 10, "CannotRepeat": 45, "UseOnlyOnce": 2},
        })
        self.assertIn("Rng.NextFloat", random["algorithm"]["selection"])
        branches = [(graph, edge) for graph in source["graphs"] for edge in graph["edges"] if edge["kind"] == "randomBranch"]
        self.assertEqual((len(branches), sum(edge["weight"]["kind"] == "delegate" for _, edge in branches)), (61, 8))
        self.assertTrue(all("repeat" in edge and edge["weight"]["valueType"] == "float" and "predicate" not in edge for _, edge in branches))
        rat = [(edge["to"].rsplit("/", 1)[-1], edge["repeat"]["enumName"], edge["cooldown"])
               for graph, edge in branches if graph["graphId"] == "GRAPH.TWO_TAILED_RAT"]
        self.assertEqual(rat, [("SCRATCH_MOVE", "CannotRepeat", 0), ("DISEASE_BITE_MOVE", "CannotRepeat", 0),
                               ("SCREECH_MOVE", "CannotRepeat", 3), ("CALL_FOR_BACKUP_MOVE", "UseOnlyOnce", 0)])
        production = source["production"]
        self.assertEqual((len(production["addApiCensus"]), len(production["ostySummonCensus"]),
                          len(production["producerRoots"]), len(production["helperCallSites"]), len(production["directSites"])),
                         (14, 17, 7, 5, 6))
        self.assertEqual(len({row["calleeSymbolSignature"] for row in production["helperCallSites"]}), 3)
        self.assertTrue(all(row["candidateMembership"]["canonicalModels"] for row in production["directSites"]))
        self.assertEqual(production["ostySummonContract"]["afterSummon"], "awaitedAfterOstyAddOrReviveHistory")
        self.assertEqual(production["coreAddContract"]["hookBoundary"], {
            "afterCreatureAddedToCombat": "awaited", "afterSummon": "absentSeparateOstyApi"})
        self.assertEqual(production["coreAddContract"]["semanticBoundaries"]["coreSlotValidation"], "absent")
        unknowns = {row["unknownId"] for row in self.artifact["payload"]["knownUnknowns"]}
        self.assertNotIn("UNKNOWN.PRODUCTION_SEMANTICS", unknowns)
        self.assertNotIn("UNKNOWN.LIFECYCLE_COVERAGE", unknowns)
        semantics = production["productionSemantics"]
        self.assertEqual(semantics["status"], "sourceComplete")
        self.assertEqual(semantics["sourceDenominators"], {
            "candidateEntries": 9, "candidateRngSelections": 1, "dependencyRefs": 4,
            "pools": 7, "postAddEffects": 4, "producers": 7,
            "runtimeStateContracts": 12, "slotStrategies": 6,
        })
        self.assertEqual([row["semanticKind"] for row in semantics["producers"]], [
            "orderedHelperBatch", "orderedHelperBatch", "fixedGraphOnce",
            "runtimeCardinalityRepeating", "fixedThreeAttemptBatch",
            "fixedGraphOnceWithStatePostAdd", "groupCounterBounded",
        ])
        self.assertEqual([
            (row["producerId"], row["activationCardinality"]["normallyAddedBodies"]["maximum"],
             row["concurrentPolicy"]["preActivationAliveSameSideMaximum"],
             row["concurrentPolicy"]["possiblePostActivationAliveSameSideMaximum"])
            for row in semantics["producers"] if row["ownerModel"] == "MONSTER.FABRICATOR"
        ], [
            ("PRODUCTION.MONSTER.FABRICATOR.FABRICATE_MOVE", 2, 3, 5),
            ("PRODUCTION.MONSTER.FABRICATOR.FABRICATING_STRIKE_MOVE", 1, 3, 4),
        ])
        audit = next(row for row in self.artifact["payload"]["resolvedAudits"]
                     if row["auditId"] == "AUDIT.RESOLVED.PRODUCTION_SEMANTICS")
        self.assertEqual((audit["family"], audit["historicalStatus"]), ("enemyBodyProduction", "sourceComplete"))

    def test_e2d1b_compact_mutations_fail_closed(self):
        def random_edge(a):
            return next(edge for graph in a["payload"]["sourceFacts"]["graphs"] for edge in graph["edges"] if edge["kind"] == "randomBranch")
        def delegate_edge(a):
            return next(edge for graph in a["payload"]["sourceFacts"]["graphs"] for edge in graph["edges"] if edge["kind"] == "randomBranch" and edge["weight"]["kind"] == "delegate")
        def production(a): return a["payload"]["sourceFacts"]["production"]
        def legacy_weight(a): random_edge(a).__setitem__("weight", random_edge(a)["repeat"]["enumValue"])
        def callback_predicate(a): random_edge(a).__setitem__("predicate", {"kind": "reference", "reference": "X::Weight sig:20000c", "valueType": "boolean"})
        def repeat_swap(a): random_edge(a)["repeat"].__setitem__("enumValue", 3)
        def callback_type(a): delegate_edge(a)["weight"]["expression"].__setitem__("valueType", "boolean")
        def rng_rule(a): a["payload"]["sourceFacts"]["randomSelection"]["algorithm"]["selection"] = "guessed uniform probability"
        def overload_order(a): a["payload"]["sourceFacts"]["randomSelection"]["overloads"][0]["parameters"].reverse()
        def add_missing(a): production(a)["addApiCensus"].pop()
        def add_reclassified(a): production(a)["addApiCensus"][0]["classification"] = "currentEnemyEncounterProduction"
        def helper_duplicate(a): production(a)["helperCallSites"][1]["callSiteId"] = production(a)["helperCallSites"][0]["callSiteId"]
        def root_missing(a): production(a)["producerRoots"].pop()
        def body_identity(a): production(a)["directSites"][0]["awaitedResult"] = "newUnjoinedBody"
        def side_changed(a): production(a)["directSites"][0]["side"] = {"enumName": "Player", "enumValue": 1}
        def core_order(a): production(a)["coreAddContract"]["callOrder"][0:2] = reversed(production(a)["coreAddContract"]["callOrder"][0:2])
        def after_summon(a): production(a)["coreAddContract"]["hookBoundary"]["afterSummon"] = "awaited"
        def missing_dependency(a): production(a)["coreAddContract"]["dependencies"].pop("initialStateComponentRef")
        def false_complete(a): production(a)["productionSemantics"]["status"] = "pendingE2d1b"
        def missing_candidates(a): production(a)["directSites"][0]["candidateMembership"]["canonicalModels"] = []
        def osty_conflation(a): production(a)["ostySummonContract"]["afterSummon"] = "partOfCreatureCmdAdd"
        def pool_order(a): production(a)["productionSemantics"]["pools"][0]["candidateModels"].reverse()
        def no_slot(a): production(a)["productionSemantics"]["slotStrategies"][0]["noSlotBehavior"] = "skipAttempt"
        def post_add_order(a): production(a)["productionSemantics"]["postAddEffects"][0]["ordering"] = "beforeAdd"
        def ovi_cardinality(a):
            next(row for row in production(a)["productionSemantics"]["producers"]
                 if row["semanticKind"] == "fixedThreeAttemptBatch")["activationCardinality"]["bodyAddAttempts"]["exact"] = 2
        def fabricating_strike_post_maximum(a):
            next(row for row in production(a)["productionSemantics"]["producers"]
                 if row["producerId"].endswith("FABRICATING_STRIKE_MOVE"))["concurrentPolicy"]["possiblePostActivationAliveSameSideMaximum"] = 5
        def rat_cap(a):
            next(row for row in production(a)["productionSemantics"]["producers"]
                 if row["semanticKind"] == "groupCounterBounded")["lifetimePolicy"]["completedCallPathMaximum"] = 5
        def state_default(a):
            next(row for row in production(a)["productionSemantics"]["runtimeStateContracts"]
                 if row["contractId"].endswith("RAT_TURNS_UNTIL_SUMMONABLE"))["default"] = 0
        def semantic_dependency(a): production(a)["productionSemantics"]["dependencies"][0]["sourceRefs"] = []
        cases = [
            (legacy_weight, "typed float"), (callback_predicate, "legacy predicate"),
            (repeat_swap, "name/value mismatch"), (callback_type, "typed float"),
            (rng_rule, "state-log/RNG rule differs"), (overload_order, "parameter/type/order differs"),
            (add_missing, "denominator drift"), (add_reclassified, "classification/Osty separation"),
            (helper_duplicate, "duplicate"), (root_missing, "denominator drift"),
            (body_identity, "target/side/awaited"), (side_changed, "target/side/awaited"),
            (core_order, "order/dependency/history differs"), (after_summon, "core Add boundary"),
            (missing_dependency, "order/dependency/history differs"), (false_complete, "not source-complete"),
            (missing_candidates, "candidate membership"), (osty_conflation, "Osty AfterSummon"),
            (pool_order, "Fabricator reusable"), (no_slot, "slot/no-slot"),
            (post_add_order, "moved before Add"), (ovi_cardinality, "Ovicopter"),
            (fabricating_strike_post_maximum, "Fabricator availability/batch/concurrent/lifetime"),
            (rat_cap, "Rat availability/repeat/group-counter"), (state_default, "state default"),
            (semantic_dependency, "dependency is not exactly resolved"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern):
                self.assert_invalid(self.mutated(change), pattern)

    def test_e2d1b_raw_source_mutations_fail_closed(self):
        def validate(change, pattern):
            source = deepcopy(self.source); change(source)
            with self.assertRaisesRegex(SourceExtractionError, pattern):
                validate_artifact(self.artifact, source=source, legacy=self.legacy)
        def raw_edge(source):
            return next(edge for graph in source["behavior"]["graphs"] for edge in graph["edges"] if edge["kind"] == "randomBranch")
        cases = [
            (lambda source: raw_edge(source).__setitem__("weight", raw_edge(source)["repeat"]["enumValue"]), "typed float"),
            (lambda source: raw_edge(source)["repeat"].__setitem__("enumName", "UseOnlyOnce"), "name/value mismatch"),
            (lambda source: source["behavior"]["randomSelectionContract"]["algorithm"].__setitem__("selection", "missing RNG"), "state-log/effective-weight/RNG"),
            (lambda source: source["production"]["addApiCensus"].pop(), "Add/Osty census"),
            (lambda source: source["production"]["coreAddContract"]["callOrder"].reverse(), "core Add order"),
            (lambda source: source["production"]["coreAddContract"]["dependencies"].pop("hpAssignmentComponentRef"), "E2a/E2b/E2d1b/E2d2"),
            (lambda source: source["production"]["coreAddContract"]["hookBoundary"].__setitem__("afterSummon", "awaited"), "hook closure"),
            (lambda source: source["production"]["productionSemantics"]["pools"][0]["candidateModels"].reverse(), "Fabricator reusable"),
            (lambda source: source["production"]["productionSemantics"]["slotStrategies"][0].__setitem__("noSlotBehavior", "skipAttempt"), "slot/no-slot"),
            (lambda source: source["production"]["productionSemantics"]["postAddEffects"][0].__setitem__("ordering", "beforeAdd"), "moved before Add"),
            (lambda source: next(row for row in source["production"]["productionSemantics"]["producers"] if row["producerId"].endswith("FABRICATING_STRIKE_MOVE"))["concurrentPolicy"].__setitem__("possiblePostActivationAliveSameSideMaximum", 5), "Fabricator availability/batch/concurrent/lifetime"),
            (lambda source: next(row for row in source["production"]["productionSemantics"]["runtimeStateContracts"] if row["contractId"].endswith("LIVING_FOG_BLOAT_AMOUNT")).__setitem__("default", 2), "state default"),
        ]
        for change, pattern in cases:
            with self.subTest(pattern=pattern): validate(change, pattern)

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
            (lambda s: s["coverage"]["hpCompletePipelineSemanticFields"].__setitem__("numerator", 82), "hpCompletePipelineSemanticFields"),
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

            semantic_source = deepcopy(self.source)
            semantic_source["behavior"]["eventTurnSummary"]["physicalOwners"] = 4
            semantic_bytes = canonical_json_bytes(semantic_source)
            bad_source.write_bytes(semantic_bytes)
            authorized = {**projection_builder.SOURCE_ARTIFACT,
                          "sha256": hashlib.sha256(semantic_bytes).hexdigest(), "size": len(semantic_bytes)}
            with patch.object(projection_builder, "SOURCE_ARTIFACT", authorized):
                with self.assertRaisesRegex(SourceExtractionError, "event turn source denominator"):
                    regenerate(bad_source, LEGACY_PATH, output)
            self.assertEqual(output.read_bytes(), b"KEEP")

            regenerate(SOURCE_PATH, LEGACY_PATH, output)
            self.assertEqual(output.read_bytes(), self.projection_bytes)
            regenerate(SOURCE_PATH, LEGACY_PATH, output, check=True)
            output.write_bytes(b"DIFFERENT")
            with self.assertRaisesRegex(SourceExtractionError, "checked projection differs"):
                regenerate(SOURCE_PATH, LEGACY_PATH, output, check=True)
            self.assertEqual(output.read_bytes(), b"DIFFERENT")

    def test_cli_check_and_single_compact_runtime_adapter(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/generate-encounter-facts.py"), "--check"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified byte-identical", result.stdout)
        compact_consumers = []
        for path in (ROOT / "src").glob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("game-v0.111.0-source.json", text, str(path))
            if "encounter-facts-v0.111.0" in text:
                compact_consumers.append(path.name)
        self.assertEqual(compact_consumers, ["source-adapter.mjs"])


if __name__ == "__main__":
    unittest.main()
