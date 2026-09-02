from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import retained_wiki as wiki


class BalancedWikiParserTests(unittest.TestCase):
    def test_nested_templates_pipes_and_commas_remain_balanced(self):
        raw = "{{Row|Name=Duplicate|Intent=Attack, {{Nested|a,b|x=y}}|Effect=Deals 3 damage, then {{X|a|b}}.}}"
        parsed = wiki.parse_template(wiki.wiki_balanced(raw, 0))
        self.assertEqual(parsed.name, "Row")
        self.assertEqual(parsed.named["Name"], "Duplicate")
        self.assertEqual(
            wiki.split_top_level(parsed.named["Intent"], ","),
            ["Attack", " {{Nested|a,b|x=y}}"],
        )
        self.assertEqual(parsed.named["Effect"], "Deals 3 damage, then {{X|a|b}}.")

    def test_top_level_power_break_does_not_split_nested_break(self):
        value = "{{BD2|Withering Presence|Withering<br>Presence}}<br>{{BD2|Artifact}} 3"
        self.assertEqual(
            wiki.split_power_claims(value),
            ["{{BD2|Withering Presence|Withering<br>Presence}}", "{{BD2|Artifact}} 3"],
        )

    def test_malformed_templates_links_and_lua_fail_closed(self):
        with self.assertRaisesRegex(wiki.AuditError, "unbalanced wiki template"):
            wiki.wiki_balanced("{{Outer|{{Inner}}", 0)
        with self.assertRaisesRegex(wiki.AuditError, "unbalanced nested"):
            wiki.split_top_level("[[open|label", ",")
        with self.assertRaisesRegex(wiki.AuditError, "unbalanced Lua"):
            wiki.lua_balanced('{ Name = "x"', 0)

    def test_html_comments_are_never_template_input(self):
        text = "<!-- {{Enemy Infobox|Name=Ghost}} -->\n{{Enemy Infobox|Name=Real}}"
        calls = list(wiki.iter_templates(text, "Enemy Infobox"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][3].named["Name"], "Real")

    def test_multi_body_section_paths_do_not_leak(self):
        text = "== Body A ==\n=== Pattern ===\nA\n== Body B ==\n=== Pattern ===\nB\n"
        sections = wiki.parse_sections(text)
        body_b_offset = text.index("B\n")
        path = wiki.section_path_at(sections, body_b_offset)
        self.assertEqual([item["title"] for item in path], ["Body B", "Pattern"])
        self.assertNotIn("Body A", [item["title"] for item in path])

    def test_pattern_clause_continuations_are_structural_and_deterministic(self):
        raw = "Opens with A. After that, uses B. The move cannot repeat.\n# C\n"
        self.assertEqual(
            [wiki.plain(item) for item in wiki.pattern_clauses(raw)],
            ["Opens with A.", "After that, uses B. The move cannot repeat.", "C"],
        )


class StableOriginIdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)

    def _record(self, ordinal: int):
        collector = wiki.AtomCollector(self.policy)
        return collector.add(
            category="move-name-intent-effect",
            family="article-move-name",
            origin={
                "kind": "page", "path": "tools/.wiki/pages.json", "pageKey": "Fixture",
                "pageId": 1, "revisionId": 2, "sectionPath": [], "rowOrdinal": ordinal,
            },
            excerpt="Duplicate",
            normalized={"kind": "move-name", "value": "Duplicate"},
        )

    def test_same_coordinate_has_same_stable_origin_and_claim_ids(self):
        first = self._record(1)
        second = self._record(1)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["claimId"], second["claimId"])

    def test_duplicate_labels_at_different_ordinals_have_distinct_ids(self):
        self.assertNotEqual(self._record(1)["id"], self._record(2)["id"])

    def test_claim_text_changes_claim_id_not_module_origin_id(self):
        collector_a = wiki.AtomCollector(self.policy)
        collector_b = wiki.AtomCollector(self.policy)
        kwargs = dict(
            category="move-name-intent-effect", family="module-move-effect",
            origin={"kind": "module", "path": "tools/.wiki/X.lua", "tableKey": "X", "recordOrdinal": 1,
                    "moveOrdinal": 1, "claimOrdinal": 1},
            normalized={"kind": "effect"},
        )
        first = collector_a.add(excerpt="Old.", **kwargs)
        second = collector_b.add(excerpt="New.", **kwargs)
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["claimId"], second["claimId"])


class RepositoryInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = wiki.build_artifact(REPO_ROOT)
        cls.records = cls.artifact["records"]

    def test_exact_derived_denominators(self):
        denominators = self.artifact["denominators"]
        self.assertEqual(denominators["overallRetainedOriginAtoms"], 4433)
        self.assertEqual(denominators["articleMoveRows"], 293)
        self.assertEqual(denominators["moduleMoveRows"], 301)
        self.assertEqual(denominators["retainedMoveRowOrigins"], 594)
        self.assertEqual(denominators["normalizedPatternClauses"], 355)
        self.assertEqual(denominators["powerPassiveAtoms"], 77)
        self.assertEqual(denominators["startingPowerAtoms"], 112)
        self.assertEqual(denominators["noteUnitsIncludingCommentFragments"], 109)
        self.assertEqual(denominators["tactics"], 76)
        self.assertEqual(denominators["trivia"], 52)
        self.assertEqual(denominators["patchEnemyMechanicFacts"], 9)
        self.assertEqual(
            denominators["byCategory"],
            wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)["expectedCategoryCounts"],
        )

    def test_missing_events_is_exact_gap_not_fabricated_module(self):
        modules = self.artifact["snapshotManifest"]["modules"]
        self.assertEqual((modules["listedCount"], modules["presentCount"], modules["missingCount"]), (7, 6, 1))
        gap = modules["missing"][0]
        self.assertEqual(gap["expectedPath"], "tools/.wiki/Events.lua")
        self.assertEqual(gap["snapshotGap"]["id"], "snapshot-gap-events-module-v0.111.0-v1")
        self.assertFalse(gap["snapshotGap"]["fabricatedEmptyModule"])
        self.assertFalse(self.artifact["readiness"]["snapshotComplete"])

    def test_doormaker_is_deprecated_and_mysterious_knight_is_current(self):
        door = [r for r in self.records if r["origin"].get("pageKey") == "Doormaker"
                or r["origin"].get("tableKey") == "Doormaker"]
        knight = [r for r in self.records if r["origin"].get("pageKey") == "Mysterious Knight"
                  or r["origin"].get("tableKey") == "Mysterious Knight"]
        self.assertTrue(door and knight)
        self.assertEqual({r["membership"] for r in door}, {"deprecated"})
        self.assertEqual({r["membership"] for r in knight}, {"current"})
        membership = self.artifact["snapshotLimitations"]["retainedBookMembership"]
        self.assertFalse(membership["mysteriousKnight"]["listedInRetainedBookWikiPages"])
        self.assertTrue(membership["doormaker"]["listedInRetainedBookWikiPages"])

    def test_comments_are_three_excluded_fragments_never_mechanics(self):
        comments = [r for r in self.records if r["family"] == "html-comment-fragment"]
        self.assertEqual(len(comments), 3)
        self.assertEqual({r["reviewState"] for r in comments}, {"policy-reviewed-exclusion"})
        phrase = "Confirm this is all correct"
        mechanics = [r for r in self.records if r["reviewState"] == "captured-unreconciled" and phrase in r["excerpt"]]
        self.assertEqual(mechanics, [])

    def test_every_atom_has_one_honest_review_state(self):
        self.assertEqual(
            self.artifact["summary"]["reviewStateCounts"],
            {"captured-unreconciled": 3568, "policy-reviewed-exclusion": 865},
        )
        for record in self.records:
            self.assertIn(record["reviewState"], {"captured-unreconciled", "policy-reviewed-exclusion"})
            if record["reviewState"] == "captured-unreconciled":
                self.assertNotIn("disposition", record)
            else:
                self.assertEqual(record["disposition"], "intentionally-excluded")
                self.assertIn("exclusionPolicyId", record)
        self.assertFalse(self.artifact["readiness"]["semanticReconciliationComplete"])
        self.assertFalse(self.artifact["readiness"]["overallReconciliationReady"])

    def test_sorted_order_and_hashes_are_reproducible(self):
        ids = [record["id"] for record in self.records]
        self.assertEqual(ids, sorted(ids))
        origin_digest = hashlib.sha256("".join(value + "\n" for value in ids).encode()).hexdigest()
        claim_digest = hashlib.sha256(
            "".join(record["id"] + "\0" + record["claimId"] + "\n" for record in self.records).encode()
        ).hexdigest()
        self.assertEqual(origin_digest, self.artifact["summary"]["sortedOriginIdsSha256"])
        self.assertEqual(claim_digest, self.artifact["summary"]["sortedClaimOriginIdsSha256"])
        self.assertEqual(wiki.canonical_json_bytes(self.artifact), wiki.artifact_bytes(REPO_ROOT))

    def test_review_corrections_are_origin_checked_without_p1b_dispositions(self):
        corrections = {item["id"]: item for item in self.artifact["reviewCorrections"]}
        self.assertEqual(len(corrections), 3)
        kin_id = corrections["review-correction-kin-follower-type-origin-v1"]["originId"]
        kin = next(record for record in self.records if record["id"] == kin_id)
        self.assertEqual(kin["origin"]["path"], "tools/.wiki/Bosses.lua")
        self.assertEqual(kin["reviewState"], "captured-unreconciled")
        self.assertNotIn("disposition", kin)
        self.assertEqual(self.artifact["researchBaseline"]["objectiveNoteGaps"], 79)
        totals = self.artifact["researchBaseline"]["aggregateDispositionTotals"]
        self.assertEqual((totals["primary-present"], totals["missing/unparsed"], totals["total"]), (2167, 103, 4433))

    def test_shorthand_invocations_are_known_snapshot_limitations(self):
        limitation = self.artifact["snapshotLimitations"]["unexpandedTemplateBodies"]
        self.assertEqual(limitation["powerInfoboxShorthandInvocations"], 69)
        self.assertEqual(limitation["intentsInvocations"], 2)
        calls = [r for r in self.records if r["family"] == "article-power-invocation"]
        self.assertEqual(sum(r["normalized"]["unexpandedTemplateBody"] for r in calls), 69)


class BuildAndFailureContractTests(unittest.TestCase):
    def test_checked_artifact_is_exact_generated_bytes(self):
        checked = (REPO_ROOT / wiki.DEFAULT_ARTIFACT).read_bytes()
        self.assertEqual(checked, wiki.artifact_bytes(REPO_ROOT))

    def test_build_then_check_byte_equality(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "artifact.json"
            _, built = wiki.write_or_check(REPO_ROOT, output, check=False)
            _, checked = wiki.write_or_check(REPO_ROOT, output, check=True)
            self.assertEqual(output.read_bytes(), built)
            self.assertEqual(checked, built)

    def test_disappeared_origin_requires_tombstone_or_reclassification(self):
        policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)
        existing = {"records": [{"id": "gone"}, {"id": "kept"}]}
        generated = {"records": [{"id": "kept"}]}
        with self.assertRaisesRegex(wiki.AuditError, "disappeared"):
            wiki._validate_disappearances(existing, generated, policy)
        reviewed = json.loads(json.dumps(policy))
        reviewed["tombstones"] = [{
            "id": "fixture-tombstone", "originId": "gone",
            "rationale": "Fixture records an explicit reviewed origin removal.",
            "reviewer": "unit test", "reviewedForVersion": wiki.TARGET_VERSION,
        }]
        wiki._validate_policy(reviewed)
        wiki._validate_disappearances(existing, generated, reviewed)

    def test_index_missing_without_exact_waiver_fails(self):
        policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)
        policy["snapshotGapWaivers"] = []
        index = wiki.load_json(REPO_ROOT / "tools/.wiki/index.json")
        with self.assertRaisesRegex(wiki.AuditError, "absent without exact approved snapshot gap"):
            wiki._module_manifest(REPO_ROOT, index, policy)

    def test_malformed_json_fails_with_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"bad":')
            with self.assertRaisesRegex(wiki.AuditError, "malformed JSON"):
                wiki.load_json(path)


if __name__ == "__main__":
    unittest.main()
