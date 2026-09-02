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
        self.assertTrue(membership["mysteriousKnight"]["listedInCurrentRetainedBookWikiPages"])
        self.assertTrue(membership["mysteriousKnight"]["listedInRetainedReferences"])
        self.assertFalse(membership["mysteriousKnight"]["listedInCurrentEncounters"])
        self.assertFalse(membership["doormaker"]["listedInCurrentRetainedBookWikiPages"])
        self.assertFalse(membership["doormaker"]["listedInCurrentEncounters"])
        self.assertTrue(membership["doormaker"]["listedInArchive"])

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
            {
                "captured-unreconciled": 3519,
                "final-mapped": 49,
                "policy-reviewed-exclusion": 865,
            },
        )
        self.assertEqual(self.artifact["summary"]["remainingCapturedUnreconciled"], 3519)
        self.assertEqual(
            self.artifact["summary"]["finalDispositionCounts"],
            {
                "conflict": 13,
                "intentionally-excluded": 865,
                "stale/deprecated/version-ambiguous": 36,
            },
        )
        for record in self.records:
            self.assertIn(record["reviewState"], {
                "captured-unreconciled", "policy-reviewed-exclusion", "final-mapped",
            })
            if record["reviewState"] == "captured-unreconciled":
                self.assertNotIn("disposition", record)
            elif record["reviewState"] == "policy-reviewed-exclusion":
                self.assertEqual(record["disposition"], "intentionally-excluded")
                self.assertIn("exclusionPolicyId", record)
            else:
                self.assertIn(record["disposition"], {
                    "conflict", "stale/deprecated/version-ambiguous",
                })
                self.assertTrue(record.get("semanticMapping"))
                self.assertGreaterEqual(len(record.get("rationale", "")), 20)
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

    def test_review_corrections_keep_kin_origin_on_bosses_lua(self):
        corrections = {item["id"]: item for item in self.artifact["reviewCorrections"]}
        self.assertEqual(len(corrections), 3)
        kin_id = corrections["review-correction-kin-follower-type-origin-v1"]["originId"]
        kin = next(record for record in self.records if record["id"] == kin_id)
        self.assertEqual(kin["origin"]["path"], "tools/.wiki/Bosses.lua")
        self.assertEqual(kin["reviewState"], "final-mapped")
        self.assertEqual(kin["disposition"], "conflict")
        self.assertEqual(kin["semanticMapping"]["retainedValue"], "Boss")
        self.assertEqual(kin["semanticMapping"]["sourceValue"], "Minion")
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

    def test_unclassified_patch_enemy_leaf_fails_closed(self):
        policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)
        pages_document = wiki.load_json(REPO_ROOT / "tools/.wiki/pages.json")
        patch_key = pages_document["meta"]["patchPage"]
        patch_page = json.loads(json.dumps(pages_document["pages"][patch_key]))
        next_section = "\n=== Colorless Cards: ==="
        self.assertIn(next_section, patch_page["wikitext"])
        patch_page["wikitext"] = patch_page["wikitext"].replace(
            next_section,
            "\n* Buffed Foo: damage increased from 1 to 2\n" + next_section,
            1,
        )

        with self.assertRaisesRegex(
            wiki.AuditError,
            r"patch enemy bullet 11 lacks reviewed classification: Buffed Foo",
        ):
            wiki._add_patch_atoms(
                wiki.AtomCollector(policy), patch_key, patch_page, policy,
                {"patchEnemyFacts": 0},
            )

    def test_only_exact_patch_enemy_grouping_parent_is_exempt(self):
        policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)
        pages_document = wiki.load_json(REPO_ROOT / "tools/.wiki/pages.json")
        patch_key = pages_document["meta"]["patchPage"]
        patch_page = json.loads(json.dumps(pages_document["pages"][patch_key]))
        patch_page["wikitext"] = patch_page["wikitext"].replace(
            "* Buffed Axebot:", "* Buffed Foo:", 1,
        )

        with self.assertRaisesRegex(
            wiki.AuditError,
            r"patch enemy bullet 1 lacks reviewed classification: Buffed Foo",
        ):
            wiki._add_patch_atoms(
                wiki.AtomCollector(policy), patch_key, patch_page, policy,
                {"patchEnemyFacts": 0},
            )

    def test_malformed_json_fails_with_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"bad":')
            with self.assertRaisesRegex(wiki.AuditError, "malformed JSON"):
                wiki.load_json(path)


class FinalMappingControlPlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = wiki.build_artifact(REPO_ROOT)
        cls.records = {record["id"]: record for record in cls.artifact["records"]}
        cls.policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_POLICY)
        cls.book = wiki.load_json(REPO_ROOT / "data/encounters.json")
        cls.compact = wiki.load_json(REPO_ROOT / "data/encounter-facts-v0.111.0.json")

    def test_known_conflict_groups_and_origin_count(self):
        conflicts = [record for record in self.artifact["records"] if record.get("disposition") == "conflict"]
        self.assertEqual(len(conflicts), 13)
        groups = {record["semanticMapping"]["semanticGroup"] for record in conflicts}
        self.assertEqual(groups, {
            "axebot-a8-hp", "owl-magistrate-a8-hp", "scroll-of-biting-a8-hp", "slimed-berserker-a8-hp",
            "infested-prism-radiate", "terror-eel-terrorize", "kin-follower-type",
        })
        self.assertEqual(sum(record["semanticMapping"]["kind"] == "a8-hp-range" for record in conflicts), 8)
        self.assertEqual(sum(record["semanticMapping"]["kind"] == "move-effect-block" for record in conflicts), 2)
        self.assertEqual(sum(record["semanticMapping"]["kind"] == "move-title" for record in conflicts), 2)
        self.assertEqual(sum(record["semanticMapping"]["kind"] == "identity-type" for record in conflicts), 1)
        for record in conflicts:
            self.assertEqual(record["authorityComparison"]["resolution"], "source-wins")
            self.assertIs(record["authorityComparison"]["silentMerge"], False)
            lanes = {coord.get("comparedLane") for coord in record["representation"]}
            self.assertIn("source", lanes)
            self.assertIn("retained", lanes)

    def test_source_winning_values_and_terror_stun_independence(self):
        axebot = self.book["encounters"]["AXEBOTS_NORMAL"]["lineup"][0]
        self.assertEqual(axebot["hpA8"], [76, 86])
        self.assertEqual(axebot["typedConflicts"][0]["retainedValue"], [78, 86])
        prism = self.book["encounters"]["INFESTED_PRISMS_ELITE"]["lineup"][0]
        radiate = next(move for move in prism["moves"] if move["name"] == "Radiate")
        self.assertEqual(radiate["textA9"], "Deals 13 damage. Gains 13 Block.")
        self.assertEqual(prism["typedConflicts"][0]["retainedValue"]["block"], 18)
        eel = self.book["encounters"]["TERROR_EEL_ELITE"]["lineup"][0]
        self.assertEqual([move["name"] for move in eel["moves"]], ["Crash", "Thrash", "Stun", "Terror"])
        self.assertEqual(eel["typedConflicts"][0]["sourceValue"], "Terrorize")
        unknown_ids = {row["unknownId"] for row in self.compact["payload"]["knownUnknowns"]}
        self.assertIn("UNKNOWN.MOVE_TITLE.MONSTER.TERROR_EEL.STUN_MOVE", unknown_ids)
        terror_maps = [record for record in self.artifact["records"]
                       if record.get("semanticMapping", {}).get("semanticGroup") == "terror-eel-terrorize"]
        self.assertEqual(len(terror_maps), 2)
        self.assertTrue(all(
            record["semanticMapping"]["independentKnownUnknown"] == "UNKNOWN.MOVE_TITLE.MONSTER.TERROR_EEL.STUN_MOVE"
            for record in terror_maps
        ))
        move = next(row for row in self.compact["payload"]["sourceFacts"]["moves"]
                    if row["canonicalId"] == "MONSTER.TERROR_EEL#TERROR_MOVE")
        self.assertEqual(move["title"]["english"], "Terrorize")
        kin = [body for body in self.book["encounters"]["THE_KIN_BOSS"]["lineup"] if body["displayName"] == "Kin Follower"]
        self.assertEqual({body["type"] for body in kin}, {"Minion"})
        self.assertEqual({body["typedConflicts"][0]["retainedValue"] for body in kin}, {"Boss"})

    def test_compact_title_conflicts_are_cross_linked_once(self):
        links = self.artifact["finalMappings"]["compactTitleConflicts"]
        compact_conflicts = self.compact["payload"]["conflicts"]
        self.assertEqual(len(links), 26)
        self.assertEqual(len(compact_conflicts), 26)
        self.assertEqual([row["conflictId"] for row in links], [row["conflictId"] for row in compact_conflicts])
        self.assertEqual(len({row["conflictId"] for row in links}), 26)
        self.assertTrue(all(row["compactLaneResolution"] == "unresolved" for row in links))
        self.assertTrue(all(row["presentationResolution"] == "source-wins" for row in links))
        self.assertTrue(all(row["heroCopyAuthority"] == "source" for row in links))
        self.assertTrue(any(row["conflictId"] == "CONFLICT.MONSTER_TITLE.FOGMOG_NORMAL.1" for row in links))

    def test_mysterious_knight_is_current_reference_not_selector(self):
        self.assertNotIn("MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER", self.book["encounters"])
        reference = self.book["retainedReferences"]["MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER"]
        self.assertEqual(reference["authority"], "retained-wiki-audit-only")
        self.assertTrue(reference["notACurrentSelector"])
        self.assertEqual(reference["sourcePrimary"], "checked-source-only")
        self.assertEqual(reference["lineup"][0]["displayName"], "Mysterious Knight")
        self.assertEqual(reference["lineup"][0]["hpA8"], [108])
        self.assertEqual([move["name"] for move in reference["lineup"][0]["moves"]], ["Breaker", "Flail", "Ram"])

    def test_doormaker_is_archive_only_and_mechanical_origins_are_stale(self):
        self.assertNotIn("DOORMAKER_BOSS", self.book["encounters"])
        door = self.book["archive"]["encounters"]["DOORMAKER_BOSS"]
        self.assertEqual(door["act"], "Glory")
        stale = [record for record in self.artifact["records"]
                 if record.get("disposition") == "stale/deprecated/version-ambiguous"]
        self.assertEqual(len(stale), 36)
        self.assertTrue(all(
            record["origin"].get("pageKey") == "Doormaker" or record["origin"].get("tableKey") == "Doormaker"
            for record in stale
        ))
        excluded_door = [record for record in self.artifact["records"]
                         if (record["origin"].get("pageKey") == "Doormaker" or record["origin"].get("tableKey") == "Doormaker")
                         and record["reviewState"] == "policy-reviewed-exclusion"]
        self.assertEqual(len(excluded_door), 31)

    def test_readiness_stays_false_and_excluded_count_is_stable(self):
        self.assertFalse(self.artifact["readiness"]["semanticReconciliationComplete"])
        self.assertFalse(self.artifact["readiness"]["overallReconciliationReady"])
        self.assertEqual(self.artifact["summary"]["finalDispositionCounts"]["intentionally-excluded"], 865)
        self.assertEqual(self.artifact["researchBaseline"]["aggregateDispositionTotals"]["conflict"], 13)
        self.assertEqual(self.artifact["finalMappings"]["researchCountCorrections"][0]["productionCount"], 13)
        self.assertEqual(self.artifact["finalMappings"]["researchCountCorrections"][1]["productionCount"], 36)

    def _unmapped_records(self):
        records = []
        for record in self.artifact["records"]:
            base = {key: record[key] for key in (
                "id", "claimId", "category", "categoryLabel", "family", "origin",
                "excerpt", "normalized", "membership",
            )}
            if record["reviewState"] == "policy-reviewed-exclusion":
                base.update({
                    "reviewState": "policy-reviewed-exclusion",
                    "disposition": "intentionally-excluded",
                    "exclusionPolicyId": record["exclusionPolicyId"],
                })
            else:
                base["reviewState"] = "captured-unreconciled"
            records.append(base)
        return records

    def _source(self):
        return wiki.load_json(REPO_ROOT / "data/game-v0.111.0-source.json")

    def test_checker_fails_on_stale_claim_guard(self):
        policy = json.loads(json.dumps(self.policy))
        policy["finalMappings"]["records"][0]["claimId"] = "wiki-claim-v1-" + ("0" * 64)
        with self.assertRaisesRegex(wiki.AuditError, "stale claim guard"):
            wiki.apply_final_mappings(
                self._unmapped_records(), policy, book=self.book, compact=self.compact, raw_source=self._source(),
            )

    def test_checker_fails_on_unresolved_pointer(self):
        policy = json.loads(json.dumps(self.policy))
        policy["finalMappings"]["records"][0]["representation"][0]["jsonPointer"] = "/monsters/999/initialHp"
        with self.assertRaisesRegex(wiki.AuditError, "unresolved JSON pointer"):
            wiki.apply_final_mappings(
                self._unmapped_records(), policy, book=self.book, compact=self.compact, raw_source=self._source(),
            )

    def test_checker_fails_when_a_conflict_lane_is_removed(self):
        policy = json.loads(json.dumps(self.policy))
        policy["finalMappings"]["records"][0]["representation"] = [
            coord for coord in policy["finalMappings"]["records"][0]["representation"]
            if coord.get("comparedLane") != "retained"
        ]
        with self.assertRaisesRegex(wiki.AuditError, "lacks both lanes"):
            wiki.apply_final_mappings(
                self._unmapped_records(), policy, book=self.book, compact=self.compact, raw_source=self._source(),
            )

    def test_checker_fails_on_wrong_expected_count(self):
        policy = json.loads(json.dumps(self.policy))
        policy["finalMappings"]["expectedConflictOriginCount"] = 12
        with self.assertRaisesRegex(wiki.AuditError, "explicit conflict mapping count drifted"):
            wiki.apply_final_mappings(
                self._unmapped_records(), policy, book=self.book, compact=self.compact, raw_source=self._source(),
            )

    def test_checker_fails_on_mismatched_normalized_value(self):
        policy = json.loads(json.dumps(self.policy))
        policy["finalMappings"]["records"][0]["semanticMapping"]["sourceValue"] = [1, 2]
        with self.assertRaisesRegex(wiki.AuditError, "source value mismatch"):
            wiki.apply_final_mappings(
                self._unmapped_records(), policy, book=self.book, compact=self.compact, raw_source=self._source(),
            )



if __name__ == "__main__":
    unittest.main()
