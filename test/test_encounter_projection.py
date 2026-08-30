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
        self.assertNotIn(b"cilInstructionsSha256", first)
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
        self.assertTrue(any(row["reasonCode"] == "ABSTRACT_BEHAVIOR_INHERITANCE_JOIN_ABSENT" for row in unknowns))
        self.assertEqual(sum(row["reasonCode"] == "SOURCE_MOVE_TITLE_MISSING_OR_INTERNAL" for row in unknowns), 18)
        candidates = payload["legacyAnnotations"]["moveTitleFallbackCandidates"]
        self.assertEqual(len(candidates), 18)
        self.assertTrue(all(row["status"] == "unjoinedCandidateSet" for row in candidates))
        self.assertEqual(len(payload["conflicts"]), 26)
        self.assertTrue(all(row["resolution"] == "unresolved" for row in payload["conflicts"]))
        self.assertTrue(any(row["conflictId"] == "CONFLICT.MONSTER_TITLE.FOGMOG_NORMAL.1" for row in payload["conflicts"]))
        self.assertTrue(any(row["reasonCode"] == "SOURCE_VS_STABLE_HP_ROUNDING_CONFLICT" for row in unknowns))

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
            (lambda a: a.__setitem__("schemaVersion", 2), "schemaVersion"),
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
            (lambda s: s.__setitem__("schemaVersion", 5), "source.schemaVersion"),
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
