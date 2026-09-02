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

    def test_starting_powers_split_top_level_commas_and_adjacent_templates(self):
        self.assertEqual(
            wiki.split_power_claims("{{BD2|Adaptable}}, {{BD2|Enrage}} 2 ({{Asc2|9|3}})"),
            ["{{BD2|Adaptable}}", "{{BD2|Enrage}} 2 ({{Asc2|9|3}})"],
        )
        self.assertEqual(
            wiki.split_power_claims("{{BD2|Minion}} {{BD2|Hatch}} 2"),
            ["{{BD2|Minion}}", "{{BD2|Hatch}} 2"],
        )

    def test_starting_power_normalization_preserves_identity_and_amount_forms(self):
        self.assertEqual(
            wiki.normalized_starting_power("25 {{BD2|Reattach}}", kind="starting-power", owner="Decimillipede"),
            {"kind": "starting-power", "owner": "Decimillipede", "value": "25 Reattach",
             "power": "Reattach", "baseAmount": 25, "amountAtA9": 25, "parseStatus": "typed"},
        )
        asc2 = wiki.normalized_starting_power(
            "{{BD2|Enrage}} 2 ({{Asc2|9|3}})", kind="starting-power", owner="Test Subject")
        self.assertEqual((asc2["baseAmount"], asc2["amountAtA9"], asc2["ascensionAmounts"]),
                         (2, 3, [{"threshold": 9, "amount": 3}]))
        # StS1 Asc has a trailing player selector; it is not the ascended amount.
        asc = wiki.normalized_starting_power(
            "{{BD2|Ravenous}} 4 ({{Asc|9|5|2}})", kind="starting-power", owner="Corpse Slug")
        self.assertEqual((asc["baseAmount"], asc["amountAtA9"]), (4, 5))

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
        self.assertEqual(denominators["overallRetainedOriginAtoms"], 4438)
        self.assertEqual(denominators["articleMoveRows"], 293)
        self.assertEqual(denominators["moduleMoveRows"], 301)
        self.assertEqual(denominators["retainedMoveRowOrigins"], 594)
        self.assertEqual(denominators["normalizedPatternClauses"], 355)
        self.assertEqual(denominators["powerPassiveAtoms"], 77)
        self.assertEqual(denominators["startingPowerAtoms"], 117)
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
                "captured-unreconciled": 2179,
                "final-mapped": 1394,
                "policy-reviewed-exclusion": 865,
            },
        )
        self.assertEqual(self.artifact["summary"]["remainingCapturedUnreconciled"], 2179)
        self.assertEqual(
            self.artifact["summary"]["finalDispositionCounts"],
            {
                "audit-present": 539,
                "conflict": 24,
                "intentionally-excluded": 865,
                "missing/unparsed": 8,
                "primary-present": 787,
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
                self.assertIn(record["disposition"], wiki.FINAL_DISPOSITIONS - {"intentionally-excluded"})
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
        self.assertEqual((totals["primary-present"], totals["missing/unparsed"], totals["total"]), (2172, 103, 4438))

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
        p1b0_ids = {item["originId"] for item in self.policy["finalMappings"]["records"]}
        conflicts = [record for record in self.artifact["records"]
                     if record["id"] in p1b0_ids and record.get("disposition") == "conflict"]
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
        links = self.artifact["finalMappings"]["p1b0"]["compactTitleConflicts"]
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
        self.assertEqual(self.artifact["finalMappings"]["p1b0"]["researchCountCorrections"][0]["productionCount"], 13)
        self.assertEqual(self.artifact["finalMappings"]["p1b0"]["researchCountCorrections"][1]["productionCount"], 36)

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



class P1b1SemanticMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = wiki.build_artifact(REPO_ROOT)
        cls.records = cls.artifact["records"]
        cls.by_id = {record["id"]: record for record in cls.records}
        cls.policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_P1B1_POLICY)
        cls.compact = wiki.load_json(REPO_ROOT / "data/encounter-facts-v0.111.0.json")
        cls.raw_source = wiki.load_json(REPO_ROOT / "data/game-v0.111.0-source.json")
        cls.surface = wiki.load_json(REPO_ROOT / wiki.PRIMARY_SEMANTIC_SURFACE)

    def find(self, *, owner=None, family=None, field=None, value=None, disposition=None):
        result = []
        for record in self.records:
            if owner is not None and record.get("normalized", {}).get("owner") != owner:
                continue
            if family is not None and record["family"] != family:
                continue
            if field is not None and record.get("normalized", {}).get("field") != field:
                continue
            if value is not None and record.get("normalized", {}).get("value") != value:
                continue
            if disposition is not None and record.get("disposition") != disposition:
                continue
            result.append(record)
        return result

    def source_roster(self, encounter_id):
        mappings = []
        for record in self.records:
            semantic = record.get("semanticMapping", {})
            for row in semantic.get("sourceSemantics", []):
                if row.get("encounterId") == encounter_id:
                    mappings.append((record, row))
        self.assertTrue(mappings, encounter_id)
        return mappings[0][1]["roster"]

    def test_corrected_target_counts_and_boundaries(self):
        target = [record for record in self.records if record["category"] in wiki.P1B1_TARGET_CATEGORIES]
        self.assertEqual(len(self.policy["expectedOrigins"]), 1271)
        self.assertEqual(self.artifact["finalMappings"]["p1b1"]["mappedOriginCount"], 1271)
        self.assertEqual(self.artifact["summary"]["remainingCapturedUnreconciled"], 2179)
        self.assertNotIn("captured-unreconciled", {record["reviewState"] for record in target})
        unrelated = [record for record in self.records
                     if record["category"] not in wiki.P1B1_TARGET_CATEGORIES
                     and record["reviewState"] == "captured-unreconciled"]
        self.assertEqual(len(unrelated), 2179)
        self.assertEqual({record["category"] for record in unrelated}, {
            "move-name-intent-effect", "pattern-sequence", "objective-note-patch-lifecycle",
        })
        self.assertEqual(self.artifact["summary"]["recordCount"], 4438)
        correction = self.artifact["finalMappings"]["p1b1"]["atomizationCorrection"]
        self.assertEqual((correction["priorSnapshotOriginCount"], correction["addedStartingPowerOrigins"]), (4433, 5))
        self.assertFalse(self.artifact["readiness"]["semanticReconciliationComplete"])
        self.assertFalse(self.artifact["readiness"]["overallReconciliationReady"])
        self.assertFalse(self.artifact["readiness"]["snapshotComplete"])

    def test_identity_state_and_body_ownership_hard_cases(self):
        tough = self.find(owner="Tough Egg", family="article-identity-field", field="Name")[0]
        hatch = self.find(owner="Hatchling", family="article-identity-field", field="Name")[0]
        self.assertEqual(tough["semanticMapping"]["actorModels"], ["MONSTER.TOUGH_EGG"])
        self.assertEqual(hatch["semanticMapping"]["actorModels"], ["MONSTER.TOUGH_EGG"])
        self.assertEqual(hatch["semanticMapping"]["stateIds"], ["MONSTER.TOUGH_EGG#HATCHED"])

        phase2 = self.find(owner="Test Subject (Phase 2)", family="article-identity-field", field="Name")[0]
        phase3 = self.find(owner="Test Subject (Phase 3)", family="article-identity-field", field="Name")[0]
        self.assertEqual(phase2["semanticMapping"]["actorModels"], ["MONSTER.TEST_SUBJECT"])
        self.assertEqual(phase2["semanticMapping"]["stateIds"], ["MONSTER.TEST_SUBJECT#PHASE_2"])
        self.assertEqual(phase3["semanticMapping"]["stateIds"], ["MONSTER.TEST_SUBJECT#PHASE_3"])

        deci = self.find(owner="Decimillipede", family="article-identity-field", field="title")[0]
        self.assertEqual(set(deci["semanticMapping"]["actorModels"]), {
            "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
            "MONSTER.DECIMILLIPEDE_SEGMENT_BACK",
        })
        for owner, model in (("Bowlbug (Egg)", "MONSTER.BOWLBUG_EGG"),
                             ("Bowlbug (Nectar)", "MONSTER.BOWLBUG_NECTAR"),
                             ("Bowlbug (Silk)", "MONSTER.BOWLBUG_SILK")):
            row = self.find(owner=owner, family="article-identity-field", field="Name")[0]
            self.assertEqual(row["semanticMapping"]["actorModels"], [model])

        eye = self.find(owner="Eye With Teeth", family="article-identity-field", field="Name")[0]
        self.assertEqual((eye["disposition"], eye["semanticMapping"]["retainedValue"], eye["semanticMapping"]["sourceValue"]),
                         ("conflict", "Eye With Teeth", "Eye with Teeth"))
        self.assertEqual({coord.get("comparedLane") for coord in eye["representation"]}, {"source", "retained"})

        mysterious = self.find(owner="Mysterious Knight", family="article-identity-field", field="Name")[0]
        self.assertEqual(mysterious["disposition"], "primary-present")
        self.assertEqual(mysterious["semanticMapping"]["actorModels"], ["MONSTER.MYSTERIOUS_KNIGHT"])
        debut = self.find(owner="Mysterious Knight", family="article-identity-field", field="Debut")[0]
        self.assertEqual((debut["disposition"], debut["normalized"]["value"]), ("audit-present", "The Lantern Key"))

        kin = self.find(owner="Kin Follower", family="module-identity-field", field="Type", value="Boss")[0]
        self.assertEqual((kin["disposition"], kin["origin"]["path"]), ("conflict", "tools/.wiki/Bosses.lua"))
        doors = [record for record in self.records if record["membership"] == "deprecated" and record["category"] in wiki.P1B1_TARGET_CATEGORIES]
        self.assertTrue(doors)
        self.assertEqual({record["disposition"] for record in doors}, {"stale/deprecated/version-ambiguous"})
        self.assertFalse(any(record["id"] in set(self.artifact["finalMappings"]["p1b1"].get("mappedOriginIds", [])) for record in doors))

    def test_roster_grammars_and_produced_roles(self):
        fly = self.source_roster("FLYCONID_NORMAL")
        self.assertEqual(fly["cardinality"], {"minimum": 2, "maximum": 2})
        self.assertEqual(fly["grammar"]["kind"], "sequence")
        self.assertEqual(fly["grammar"]["children"][0]["kind"], "uniformChoice")
        self.assertEqual(fly["grammar"]["children"][1], {"kind": "fixed", "model": "MONSTER.FLYCONID"})

        weak = self.source_roster("SLIMES_WEAK")["grammar"]
        self.assertEqual(weak["kind"], "uniformChoice")
        self.assertEqual({branch["children"][0]["model"] for branch in weak["choices"]},
                         {"MONSTER.LEAF_SLIME_S", "MONSTER.TWIG_SLIME_S"})
        for branch in weak["choices"]:
            self.assertEqual(branch["children"][1]["kind"], "uniformChoice")

        strangler = self.source_roster("SLITHERING_STRANGLER_NORMAL")["grammar"]
        small = strangler["children"][0]["choices"][2]
        self.assertEqual([child["kind"] for child in small["children"]], ["uniformChoice", "uniformChoice"])
        conflict = self.find(family="module-roster", disposition="conflict")
        self.assertEqual(len(conflict), 1)
        self.assertIn("duplicatesPossible", conflict[0]["semanticMapping"]["retainedValue"]["smallBranch"])

        ruby = self.source_roster("RUBY_RAIDERS_NORMAL")["grammar"]
        self.assertEqual((ruby["kind"], ruby["count"], ruby["draws"], len(ruby["choices"])),
                         ("filteredChoice", 3, "withoutReplacement", 5))
        bowl_normal = self.source_roster("BOWLBUGS_NORMAL")["grammar"]["children"][1]
        bowl_weak = self.source_roster("BOWLBUGS_WEAK")["grammar"]["children"][1]
        self.assertEqual((bowl_normal["kind"], bowl_normal["count"], bowl_normal["draws"]),
                         ("filteredChoice", 2, "withoutReplacement"))
        self.assertEqual(bowl_weak["kind"], "uniformChoice")

        fabricator = next(row for record in self.records for row in record.get("semanticMapping", {}).get("sourceSemantics", [])
                          if row["encounterId"] == "FABRICATOR_NORMAL" and row["production"])
        self.assertEqual(fabricator["roster"]["possibleInitialBodies"], ["MONSTER.FABRICATOR"])
        self.assertEqual(set(fabricator["production"]["producedBodies"]), {
            "MONSTER.GUARDBOT", "MONSTER.NOISEBOT", "MONSTER.STABBOT", "MONSTER.ZAPBOT",
        })
        event = self.source_roster("DENSE_VEGETATION_EVENT_ENCOUNTER")
        self.assertEqual(event["cardinality"], {"minimum": 4, "maximum": 4})
        self.assertEqual([child["model"] for child in event["grammar"]["children"]], ["MONSTER.WRIGGLER"] * 4)
        phase_lead = next(record for record in self.records
                          if record["family"] == "article-lead" and record["origin"]["pageKey"] == "Test Subject"
                          and "three phases" in record["normalized"]["value"])
        self.assertEqual((phase_lead["disposition"], phase_lead["semanticMapping"]["claimKind"]),
                         ("primary-present", "initial-state-context"))

    def test_hp_fixed_range_conflicts_forms_scaling_and_runtime_reduction(self):
        beast = self.find(owner="Ceremonial Beast", family="article-hp-field", field="AscHP")[0]
        self.assertEqual(beast["semanticMapping"]["sourceOrFallbackValue"], {"minimum": 262, "maximum": 262})
        primary_hp = [wiki.resolve_json_pointer(self.surface, coord["jsonPointer"].replace("/a8SinglePlayer", "/configured"))
                      for coord in beast["representation"] if coord["layer"] == "primary-presentation"]
        self.assertEqual(primary_hp, [{"minimum": 288, "maximum": 288}, {"minimum": 576, "maximum": 576}])
        fly = self.find(owner="Flyconid", family="article-hp-field", field="AscHP")[0]
        self.assertEqual(fly["semanticMapping"]["sourceOrFallbackValue"], {"minimum": 51, "maximum": 53})

        axebot = self.find(owner="Axebot", family="article-hp-field", field="AscHP")[0]
        self.assertEqual((axebot["disposition"], axebot["semanticMapping"]["sourceValue"]),
                         ("conflict", [76, 86]))
        axebot_base = self.find(owner="Axebot", family="article-hp-field", field="HP")[0]
        self.assertEqual((axebot_base["authorityComparison"]["closure"],
                          axebot_base["semanticMapping"]["retainedFallbackSuppliesAuditValue"]),
                         ("knownUnknown", True))

        egg = self.find(owner="Tough Egg", family="article-hp-field", field="AscHP")[0]
        hatch = self.find(owner="Hatchling", family="article-hp-field", field="AscHP")[0]
        self.assertEqual(egg["semanticMapping"]["sourceOrFallbackValue"], {"minimum": 15, "maximum": 19})
        self.assertEqual(hatch["semanticMapping"]["stateIds"], ["MONSTER.TOUGH_EGG#HATCHED"])
        self.assertIn("retained-fallback", hatch["semanticMapping"]["primaryAuthority"])

        phase2 = self.find(owner="Test Subject (Phase 2)", family="article-hp-field", field="AscHP")[0]
        self.assertEqual((phase2["semanticMapping"]["sourceOrFallbackValue"], phase2["semanticMapping"]["stateIds"]),
                         ({"minimum": 212, "maximum": 212}, ["MONSTER.TEST_SUBJECT#PHASE_2"]))
        deci = self.find(owner="Decimillipede", family="article-hp-field", field="HP")[0]
        self.assertEqual((deci["semanticMapping"]["normalValue"], deci["semanticMapping"]["a8Value"]),
                         ({"minimum": 40, "maximum": 46}, {"minimum": 46, "maximum": 52}))
        self.assertEqual(len(deci["semanticMapping"]["actorModels"]), 3)

        punch = self.find(owner="Punch Construct", family="article-hp-field", field="HP")[0]
        effects = punch["semanticMapping"]["runtimeStartingHpEffects"]
        self.assertEqual({effect["effect"]["kind"] for effect in effects}, {"setState", "setCurrentHp"})
        self.assertEqual(punch["semanticMapping"]["scope"].find("runtime starting reduction") >= 0, True)

        patch = [record for record in self.records if record["family"] == "patch-hp-fact"]
        self.assertEqual(len(patch), 2)
        self.assertEqual({record["disposition"] for record in patch}, {"missing/unparsed"})
        mysterious = self.find(owner="Mysterious Knight", family="article-hp-field", field="AscHP")[0]
        self.assertEqual((mysterious["disposition"], mysterious["semanticMapping"]["sourceOrFallbackValue"]),
                         ("primary-present", {"minimum": 108, "maximum": 108}))
        mysterious_hp = [wiki.resolve_json_pointer(self.surface, coord["jsonPointer"].replace("/a8SinglePlayer", "/configured"))
                         for coord in mysterious["representation"] if coord["layer"] == "primary-presentation"]
        self.assertEqual(mysterious_hp, [{"minimum": 108, "maximum": 108}, {"minimum": 259, "maximum": 259}])
        door_hp = self.find(owner="Doormaker", family="article-hp-field")
        self.assertTrue(door_hp)
        self.assertEqual({record["disposition"] for record in door_hp}, {"stale/deprecated/version-ambiguous"})

    def test_starting_power_identity_amount_scaling_and_boundaries(self):
        stock = self.find(owner="Axebot", family="article-starting-power", value="Stock 2")[0]
        self.assertEqual((stock["semanticMapping"]["powerIds"], stock["semanticMapping"]["amountAtA9"],
                          stock["semanticMapping"]["retainedFallbackSuppliesPrimaryAmount"]),
                         (["POWER.STOCK_POWER"], 2, True))
        knight_strength = self.find(owner="Mysterious Knight", family="article-starting-power", value="Strength 6")[0]
        knight_plating = self.find(owner="Mysterious Knight", family="article-starting-power", value="Plating 6")[0]
        self.assertEqual(knight_strength["semanticMapping"]["powerIds"], ["POWER.STRENGTH_POWER"])
        self.assertEqual(knight_plating["semanticMapping"]["powerIds"], ["POWER.PLATING_POWER"])
        event = next(row for row in self.surface["encounters"] if row["canonicalId"] == "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER")
        configured = event["retainedBodies"][0]["startingPowerTokens"]["configuredByPlayers"]
        self.assertEqual(configured, [
            {"players": 1, "tokens": [{"title": "Strength", "amount": 6}, {"title": "Plating", "amount": 6}]},
            {"players": 2, "tokens": [{"title": "Strength", "amount": 6}, {"title": "Plating", "amount": 18}]},
        ])

        ovicopter = next(row for row in self.surface["encounters"] if row["canonicalId"] == "OVICOPTER_NORMAL")
        egg_surface = next(row for row in ovicopter["retainedBodies"] if row["displayName"] == "Tough Egg")
        expected_egg_tokens = [{"title": "Minion"}, {"title": "Hatch", "amount": 2}]
        self.assertEqual(egg_surface["startingPowerTokens"]["atA9"], expected_egg_tokens)
        self.assertEqual(egg_surface["startingPowerTokens"]["configuredByPlayers"], [
            {"players": 1, "tokens": expected_egg_tokens},
            {"players": 2, "tokens": expected_egg_tokens},
        ])

        egg = self.find(owner="Tough Egg", family="article-starting-power")
        self.assertEqual([(row["normalized"]["power"], row["normalized"].get("amountAtA9")) for row in egg],
                         [("Minion", None), ("Hatch", 2)])
        self.assertEqual(len(self.find(owner="Hatchling", family="article-starting-power", value="Minion")), 1)
        test_subject = self.find(owner="Test Subject", family="article-starting-power")
        self.assertEqual({row["normalized"]["power"] for row in test_subject}, {"Adaptable", "Enrage"})
        self.assertEqual(next(row for row in test_subject if row["normalized"]["power"] == "Enrage")["normalized"]["amountAtA9"], 3)

        # A state ID proves which retained form owns the token, not that source
        # initialState applies the Power. Keep those facts out of source closure.
        egg_minion = self.find(owner="Tough Egg", family="article-starting-power", value="Minion")[0]
        hatchling_minion = self.find(owner="Hatchling", family="article-starting-power", value="Minion")[0]
        self.assertEqual(
            (egg_minion["disposition"], egg_minion["authorityComparison"]["closure"],
             egg_minion["authorityComparison"]["sourceFactRefs"],
             egg_minion["semanticMapping"]["ownershipFactRefs"]),
            ("primary-present", "knownUnknown", ["SOURCE.POWER.MINION_POWER"], []),
        )
        self.assertEqual(
            (hatchling_minion["disposition"], hatchling_minion["authorityComparison"]["closure"],
             hatchling_minion["authorityComparison"]["sourceFactRefs"],
             hatchling_minion["semanticMapping"]["ownershipFactRefs"]),
            ("primary-present", "knownUnknown", ["SOURCE.POWER.MINION_POWER"],
             ["SOURCE.STATE.MONSTER.TOUGH_EGG.HATCHED"]),
        )

        ownership_only_phases = [
            ("Test Subject (Phase 2)", "Painful Stabs", "POWER.PAINFUL_STABS_POWER",
             "SOURCE.STATE.MONSTER.TEST_SUBJECT.PHASE_2"),
            ("Test Subject (Phase 3)", "Nemesis", "POWER.NEMESIS_POWER",
             "SOURCE.STATE.MONSTER.TEST_SUBJECT.PHASE_3"),
        ]
        for owner, power, power_id, state_fact_id in ownership_only_phases:
            rows = [row for family in ("article-starting-power", "module-starting-power")
                    for row in self.find(owner=owner, family=family, value=power)]
            self.assertEqual(len(rows), 2)
            for row in rows:
                self.assertEqual((row["disposition"], row["authorityComparison"]["closure"]),
                                 ("primary-present", "knownUnknown"))
                self.assertEqual(row["authorityComparison"]["sourceFactRefs"],
                                 [f"SOURCE.{power_id}"])
                self.assertEqual(row["semanticMapping"]["ownershipFactRefs"], [state_fact_id])
                self.assertEqual(row["semanticMapping"]["sourceValueExpressions"], [])

        # The same Phase 2 ownership is source-closed for Adaptable because the
        # actor model has a matching initialState applyPower fact.
        phase2_adaptable = [row for family in ("article-starting-power", "module-starting-power")
                            for row in self.find(owner="Test Subject (Phase 2)", family=family,
                                                 value="Adaptable")]
        self.assertEqual(len(phase2_adaptable), 2)
        for row in phase2_adaptable:
            self.assertEqual(row["authorityComparison"]["closure"], "closed")
            self.assertEqual(row["authorityComparison"]["sourceFactRefs"], [
                "SOURCE.INITIAL.MONSTER.TEST_SUBJECT.AFTERADDEDTOROOM.000.APPLYPOWER",
                "SOURCE.POWER.ADAPTABLE_POWER",
            ])
            self.assertEqual(row["semanticMapping"]["ownershipFactRefs"],
                             ["SOURCE.STATE.MONSTER.TEST_SUBJECT.PHASE_2"])
        for row in egg:
            expected_token = {"title": row["normalized"]["power"]}
            if row["normalized"].get("amountAtA9") is not None:
                expected_token["amount"] = row["normalized"]["amountAtA9"]
            token_coordinates = [coord for coord in row["representation"]
                                 if "/startingPowerTokens/" in coord.get("jsonPointer", "")]
            self.assertEqual(len(token_coordinates), 3)
            self.assertTrue(all(coord["expectedValue"] == expected_token for coord in token_coordinates))

        back_attack = self.find(family="article-starting-power", value="Back Attack")
        self.assertEqual({tuple(row["semanticMapping"]["powerIds"]) for row in back_attack}, {
            ("POWER.BACK_ATTACK_LEFT_POWER",), ("POWER.BACK_ATTACK_RIGHT_POWER",),
        })
        self.assertEqual({row["semanticMapping"]["powerTitle"] for row in back_attack}, {"Back Attack"})
        missing_descriptions = {row["canonicalId"] for row in self.raw_source["powers"]
                                if row.get("smartDescription", {}).get("classification") == "missingLocalization"}
        self.assertTrue({"POWER.BACK_ATTACK_LEFT_POWER", "POWER.BACK_ATTACK_RIGHT_POWER"} <= missing_descriptions)
        globe_module = self.find(owner="Globe Head", family="module-starting-power")[0]
        globe_article = self.find(owner="Globe Head", family="article-starting-power")[0]
        self.assertEqual(globe_article["disposition"], "primary-present")
        self.assertEqual((globe_module["disposition"], globe_module["semanticMapping"]["retainedValue"],
                          globe_module["semanticMapping"]["sourceValue"]),
                         ("conflict", {"title": "Galvanic", "amount": 6},
                          {"title": "Galvanic", "amount": 8}))
        self.assertEqual((globe_module["authorityComparison"]["resolution"],
                          globe_module["authorityComparison"]["closure"],
                          globe_module["semanticMapping"]["currentReferenceFallbackSuppliesPrimaryAmount"],
                          globe_module["semanticMapping"]["retainedFallbackSuppliesPrimaryAmount"]),
                         ("source-wins", "knownUnknown", True, False))
        self.assertEqual({coord.get("comparedLane") for coord in globe_module["representation"]},
                         {"source", "retained"})
        globe_source_coordinates = [coord for coord in globe_module["representation"]
                                    if coord.get("comparedLane") == "source"]
        self.assertEqual([coord.get("players") for coord in globe_source_coordinates], [None, 1, 2])
        self.assertTrue(all(coord["expectedValue"] == {"title": "Galvanic", "amount": 8}
                            for coord in globe_source_coordinates))
        self.assertTrue(all(wiki.resolve_json_pointer(self.surface, coord["jsonPointer"]) == coord["expectedValue"]
                            for coord in globe_source_coordinates))

        galvanic = [record for record in self.records if record["family"] == "patch-starting-power"]
        self.assertEqual((len(galvanic), galvanic[0]["disposition"]), (1, "missing/unparsed"))
        self.assertEqual(self.find(owner="Ceremonial Beast", family="article-starting-power"), [],
                         "Plow is gained by an opener and must not be classified as starting state")
        chompers = self.find(owner="Chomper", family="article-starting-power")
        self.assertTrue(chompers)
        for row in chompers:
            primary_pointers = [coord["jsonPointer"] for coord in row["representation"]
                                if coord["layer"] == "primary-presentation"]
            self.assertTrue(any("/bodies/0/" in pointer for pointer in primary_pointers))
            self.assertTrue(any("/bodies/1/" in pointer for pointer in primary_pointers))

    def test_starting_power_source_evidence_invariant_for_entire_family(self):
        starting_records = [
            record for record in self.records
            if record["family"] in {"article-starting-power", "module-starting-power"}
            and record.get("finalMappingId", "").startswith("final-map-p1b1-")
        ]
        self.assertEqual(len(starting_records), 112)
        for record in starting_records:
            source_refs = record["authorityComparison"]["sourceFactRefs"]
            ownership_refs = record["semanticMapping"]["ownershipFactRefs"]
            direct_refs = [ref for ref in source_refs
                           if ref.startswith("SOURCE.INITIAL.") and ref.endswith(".APPLYPOWER")]
            self.assertFalse(any(ref.startswith("SOURCE.STATE.") for ref in source_refs), record["id"])
            self.assertTrue(all(ref.startswith("SOURCE.STATE.") for ref in ownership_refs), record["id"])
            self.assertTrue(set(source_refs).isdisjoint(ownership_refs), record["id"])
            self.assertEqual(bool(record["semanticMapping"]["sourceValueExpressions"]),
                             bool(direct_refs), record["id"])
            if record["authorityComparison"]["closure"] == "closed":
                self.assertTrue(direct_refs, record["id"])
            if not direct_refs:
                self.assertEqual(record["authorityComparison"]["closure"],
                                 "knownUnknown", record["id"])

    def test_hp_exact_value_evidence_invariant_and_state_matrices(self):
        documents = wiki._mapping_documents({}, self.compact, {}, self.surface)
        hp_records = [record for record in self.records
                      if record["category"] == "hp-ascension-scaling"
                      and record.get("finalMappingId", "").startswith("final-map-p1b1-")]
        self.assertEqual(len(hp_records), 403)
        for record in hp_records:
            mapping = {
                "id": record["finalMappingId"], "disposition": record["disposition"],
                "semanticMapping": record["semanticMapping"],
                "authorityComparison": record["authorityComparison"],
                "representation": record["representation"],
            }
            wiki._validate_hp_value_evidence(mapping, documents)

        def exact_values(record, role):
            coordinates = [row for row in record["representation"] if row.get("evidenceRole") == role]
            return [wiki.resolve_json_pointer(self.surface, row["jsonPointer"]) for row in coordinates]

        # Exact form ownership: neither A8 nor the owning model's other state may prove base HP.
        form_matrix = [
            ("Tough Egg", {"minimum": 14, "maximum": 18}, {"minimum": 15, "maximum": 19}, [], "closed"),
            ("Hatchling", {"minimum": 19, "maximum": 22}, {"minimum": 20, "maximum": 23},
             ["MONSTER.TOUGH_EGG#HATCHED"], "knownUnknown"),
            ("Test Subject", {"minimum": 100, "maximum": 100}, {"minimum": 111, "maximum": 111}, [], "closed"),
            ("Test Subject (Phase 2)", {"minimum": 200, "maximum": 200}, {"minimum": 212, "maximum": 212},
             ["MONSTER.TEST_SUBJECT#PHASE_2"], "knownUnknown"),
            ("Test Subject (Phase 3)", {"minimum": 300, "maximum": 300}, {"minimum": 313, "maximum": 313},
             ["MONSTER.TEST_SUBJECT#PHASE_3"], "knownUnknown"),
        ]
        for owner, base, a8, states, base_closure in form_matrix:
            with self.subTest(owner=owner):
                normal = self.find(owner=owner, family="article-hp-field", field="HP")[0]
                ascended = self.find(owner=owner, family="article-hp-field", field="AscHP")[0]
                self.assertEqual(normal["semanticMapping"]["retainedValue"], base)
                self.assertTrue(exact_values(normal, "retained-normal-value"))
                self.assertEqual(set(map(json.dumps, exact_values(normal, "retained-normal-value"))), {json.dumps(base)})
                self.assertEqual(normal["semanticMapping"]["stateIds"], states)
                self.assertEqual(normal["authorityComparison"]["closure"], base_closure)
                self.assertTrue(all(row["jsonPointer"].endswith("/hpBelowA8")
                                    for row in normal["representation"]
                                    if row.get("evidenceRole") == "retained-normal-value"))
                self.assertEqual(ascended["semanticMapping"]["sourceOrFallbackValue"], a8)
                self.assertEqual(ascended["semanticMapping"]["stateIds"], states)
                primary = [row for row in ascended["representation"]
                           if row.get("evidenceRole") == "primary-a8-single-player-value"]
                self.assertEqual({row["players"] for row in primary}, {1, 2})
                self.assertEqual({json.dumps(wiki.resolve_json_pointer(self.surface, row["jsonPointer"]))
                                  for row in primary}, {json.dumps(a8)})
                self.assertFalse(any("hpBelowA8" in row.get("jsonPointer", "") for row in primary))

        hatch_base = self.find(owner="Hatchling", family="article-hp-field", field="HP")[0]
        self.assertEqual(hatch_base["semanticMapping"]["sourceCandidateValues"], [{
            "actorModel": "MONSTER.TOUGH_EGG", "belowA8": {"minimum": 14, "maximum": 18},
            "scopeRelation": "different-state-ownership-model",
        }])
        for owner, candidate in (("Test Subject (Phase 2)", 100), ("Test Subject (Phase 3)", 100)):
            row = self.find(owner=owner, family="article-hp-field", field="HP")[0]
            self.assertEqual(row["semanticMapping"]["sourceCandidateValues"][0]["belowA8"],
                             {"minimum": candidate, "maximum": candidate})
            self.assertEqual(row["authorityComparison"]["sourceFactRefs"], [])

        # Ordinary fixed/range, source-winning conflict, and symbolic retained fallback.
        fixed = self.find(owner="Ceremonial Beast", family="article-hp-field", field="HP")[0]
        ranged = self.find(owner="Tracker Raider", family="article-hp-field", field="HP")[0]
        conflict = self.find(owner="Scroll of Biting", family="article-hp-field", field="HP")[0]
        symbolic = self.find(owner="Axebot", family="article-hp-field", field="HP")[0]
        self.assertEqual((fixed["semanticMapping"]["retainedValue"], fixed["authorityComparison"]["closure"]),
                         ({"minimum": 252, "maximum": 252}, "closed"))
        self.assertEqual((ranged["semanticMapping"]["retainedValue"], ranged["authorityComparison"]["closure"]),
                         ({"minimum": 21, "maximum": 25}, "closed"))
        self.assertEqual((conflict["disposition"], conflict["semanticMapping"]["retainedValue"],
                          conflict["semanticMapping"]["sourceValue"]),
                         ("conflict", {"minimum": 31, "maximum": 38}, {"minimum": 30, "maximum": 37}))
        self.assertEqual({row.get("comparedLane") for row in conflict["representation"]
                          if row.get("comparedLane")}, {"source", "retained"})
        self.assertEqual((symbolic["authorityComparison"]["closure"],
                          symbolic["semanticMapping"]["authorityStatus"],
                          symbolic["semanticMapping"]["sourceCandidateValues"][0]["belowA8"]),
                         ("knownUnknown", "retained-reference-only", None))

    def test_negative_hp_exact_value_mutations_preserve_ownership_ids(self):
        def encounter(surface, canonical_id):
            return next(row for row in surface["encounters"] if row["canonicalId"] == canonical_id)

        mutations = []
        surface = json.loads(json.dumps(self.surface))
        hatch = next(row for row in encounter(surface, "OVICOPTER_NORMAL")["retainedBodies"]
                     if row["displayName"] == "Hatchling")
        hatch_state = hatch["stateId"]
        hatch["hpBelowA8"] = {"minimum": 20, "maximum": 23}
        self.assertEqual(hatch["stateId"], hatch_state)
        mutations.append(("Hatchling base replaced by A8", surface, "exact retained value evidence mismatch"))

        surface = json.loads(json.dumps(self.surface))
        hatch = next(row for row in encounter(surface, "OVICOPTER_NORMAL")["retainedBodies"]
                     if row["displayName"] == "Hatchling")
        hatch_state = hatch["stateId"]
        del hatch["hpBelowA8"]
        self.assertEqual(hatch["stateId"], hatch_state)
        mutations.append(("Hatchling exact base removed", surface, "exact retained value evidence mismatch"))

        surface = json.loads(json.dumps(self.surface))
        subject = encounter(surface, "TEST_SUBJECT_BOSS")
        phase2 = next(row for row in subject["retainedBodies"] if row["displayName"].endswith("Phase 2)"))
        phase2_state = phase2["stateId"]
        phase2["hpBelowA8"] = {"minimum": 100, "maximum": 100}
        self.assertEqual(phase2["stateId"], phase2_state)
        mutations.append(("Phase 2 base replaced by Phase 1", surface, "exact retained value evidence mismatch"))

        surface = json.loads(json.dumps(self.surface))
        subject = encounter(surface, "TEST_SUBJECT_BOSS")
        phase2 = next(row for row in subject["retainedBodies"] if row["displayName"].endswith("Phase 2)"))
        phase3 = next(row for row in subject["retainedBodies"] if row["displayName"].endswith("Phase 3)"))
        states = (phase2["stateId"], phase3["stateId"])
        phase2["hpBelowA8"], phase3["hpBelowA8"] = phase3["hpBelowA8"], phase2["hpBelowA8"]
        self.assertEqual((phase2["stateId"], phase3["stateId"]), states)
        mutations.append(("Phase 2/3 base values cross-state swapped", surface, "exact retained value evidence mismatch"))

        surface = json.loads(json.dumps(self.surface))
        subject = encounter(surface, "TEST_SUBJECT_BOSS")
        phase3 = next(row for row in subject["retainedBodies"] if row["displayName"].endswith("Phase 3)"))
        phase3_state = phase3["stateId"]
        phase3["hpA8SinglePlayer"] = {"minimum": 300, "maximum": 300}
        self.assertEqual(phase3["stateId"], phase3_state)
        mutations.append(("Phase 3 A8 replaced by base", surface, "A8 body/source value scope mismatch"))

        surface = json.loads(json.dumps(self.surface))
        tracker = self.find(owner="Tracker Raider", family="article-hp-field", field="HP")[0]
        source_coord = next(row for row in tracker["representation"]
                            if row.get("evidenceRole") == "same-scope-source-value")
        tokens = source_coord["jsonPointer"].strip("/").split("/")
        parent = surface
        for token in tokens[:-1]:
            parent = parent[int(token)] if isinstance(parent, list) else parent[token]
        parent[tokens[-1]] = {"minimum": 21, "maximum": 24}
        mutations.append(("ordinary range source endpoint changed", surface, "expectedValue mismatch"))

        for label, mutated, error in mutations:
            with self.subTest(label=label):
                with self.assertRaisesRegex(wiki.AuditError, error):
                    self.apply_mutation(surface=mutated)

    def _unmapped_p1b1_records(self):
        target_ids = {row["originId"] for row in self.policy["expectedOrigins"]}
        result = []
        for record in self.records:
            copied = json.loads(json.dumps(record))
            if record["id"] in target_ids:
                for key in ("disposition", "semanticMapping", "authorityComparison", "representation",
                            "rationale", "owner", "severity", "reviewedForVersion", "finalMappingId"):
                    copied.pop(key, None)
                copied["reviewState"] = "captured-unreconciled"
            result.append(copied)
        return result

    def apply_mutation(self, *, policy=None, surface=None, records=None):
        return wiki.apply_p1b1_mappings(
            records or self._unmapped_p1b1_records(), policy or json.loads(json.dumps(self.policy)),
            compact=self.compact, primary_surface=surface or json.loads(json.dumps(self.surface)),
        )

    def test_negative_stale_guard_missing_future_and_family_count(self):
        policy = json.loads(json.dumps(self.policy))
        policy["expectedOrigins"][0]["claimId"] = "wiki-claim-v1-" + "0" * 64
        with self.assertRaisesRegex(wiki.AuditError, "guards are stale"):
            self.apply_mutation(policy=policy)
        records = self._unmapped_p1b1_records()
        records.pop(next(i for i, row in enumerate(records) if row["id"] == self.policy["expectedOrigins"][0]["originId"]))
        with self.assertRaisesRegex(wiki.AuditError, "guards are stale"):
            self.apply_mutation(records=records)
        records = self._unmapped_p1b1_records()
        future = json.loads(json.dumps(next(row for row in records if row["category"] == "hp-ascension-scaling"
                                              and row["reviewState"] == "captured-unreconciled")))
        future["id"] = "wiki-origin-v1-" + "f" * 64
        future["claimId"] = "wiki-claim-v1-" + "f" * 64
        records.append(future)
        with self.assertRaisesRegex(wiki.AuditError, "guards are stale"):
            self.apply_mutation(records=records)
        policy = json.loads(json.dumps(self.policy))
        policy["expectedFamilyCounts"]["article-hp-field"] -= 1
        with self.assertRaisesRegex(wiki.AuditError, "family counts drifted"):
            self.apply_mutation(policy=policy)

    def test_starting_power_source_closure_requires_direct_apply_power(self):
        surface = json.loads(json.dumps(self.surface))
        subject = next(row for row in surface["encounters"]
                       if row["canonicalId"] == "TEST_SUBJECT_BOSS")
        model = next(row for row in subject["sourceModels"]
                     if row["canonicalModel"] == "MONSTER.TEST_SUBJECT")
        model["initialState"] = [
            fact for fact in model["initialState"]
            if fact["effect"].get("model") != "POWER.ADAPTABLE_POWER"
        ]

        records = self._unmapped_p1b1_records()
        self.apply_mutation(surface=surface, records=records)
        phase2_adaptable = [
            row for row in records
            if row.get("normalized", {}).get("owner") == "Test Subject (Phase 2)"
            and row.get("normalized", {}).get("power") == "Adaptable"
        ]
        self.assertEqual(len(phase2_adaptable), 2)
        for row in phase2_adaptable:
            self.assertEqual(row["semanticMapping"]["stateIds"],
                             ["MONSTER.TEST_SUBJECT#PHASE_2"])
            self.assertEqual(row["semanticMapping"]["ownershipFactRefs"],
                             ["SOURCE.STATE.MONSTER.TEST_SUBJECT.PHASE_2"])
            self.assertEqual(row["authorityComparison"]["closure"], "knownUnknown")
            self.assertEqual(row["authorityComparison"]["sourceFactRefs"],
                             ["SOURCE.POWER.ADAPTABLE_POWER"])
            self.assertEqual(row["semanticMapping"]["sourceValueExpressions"], [])

    def test_negative_starting_power_token_and_reviewed_value_mutations(self):
        surface = json.loads(json.dumps(self.surface))
        ovicopter = next(row for row in surface["encounters"] if row["canonicalId"] == "OVICOPTER_NORMAL")
        egg = next(row for row in ovicopter["retainedBodies"] if row["displayName"] == "Tough Egg")
        egg["startingPowerTokens"]["atA9"] = [{"title": "Minion Hatch", "amount": 2}]
        with self.assertRaisesRegex(wiki.AuditError, "no unique exact body token"):
            self.apply_mutation(surface=surface)

        surface = json.loads(json.dumps(self.surface))
        ovicopter = next(row for row in surface["encounters"] if row["canonicalId"] == "OVICOPTER_NORMAL")
        egg = next(row for row in ovicopter["retainedBodies"] if row["displayName"] == "Tough Egg")
        egg["startingPowerTokens"]["configuredByPlayers"][0]["tokens"][1]["title"] = "Minion Hatch"
        with self.assertRaisesRegex(wiki.AuditError, "no exact configured token"):
            self.apply_mutation(surface=surface)

        surface = json.loads(json.dumps(self.surface))
        globe = next(row for row in surface["encounters"] if row["canonicalId"] == "GLOBE_HEAD_NORMAL")
        globe["retainedBodies"][0]["startingPowerTokens"]["atA9"][0]["amount"] = 6
        with self.assertRaisesRegex(wiki.AuditError, "conflict review drifted"):
            self.apply_mutation(surface=surface)

        surface = json.loads(json.dumps(self.surface))
        globe = next(row for row in surface["encounters"] if row["canonicalId"] == "GLOBE_HEAD_NORMAL")
        globe["retainedBodies"][0]["startingPowerTokens"]["configuredByPlayers"][1]["tokens"][0]["amount"] = 6
        with self.assertRaisesRegex(wiki.AuditError, "conflict value guard drifted"):
            self.apply_mutation(surface=surface)

    def test_negative_pointer_actor_duplicate_and_conflict_mutations(self):
        surface = json.loads(json.dumps(self.surface))
        # Exact provenance mutation strands all Aeonglass origins instead of falling back by name.
        aeon = next(row for row in surface["encounters"] if row["canonicalId"] == "AEONGLASS_BOSS")
        aeon["retainedBodies"][0]["provenance"]["article"]["templateOrdinal"] = 99
        with self.assertRaisesRegex(wiki.AuditError, "lacks exact provenance join"):
            self.apply_mutation(surface=surface)
        surface = json.loads(json.dumps(self.surface))
        aeon = next(row for row in surface["encounters"] if row["canonicalId"] == "AEONGLASS_BOSS")
        aeon["primaryByPlayers"][0]["bodies"][0]["displayName"] = "Wrong actor"
        with self.assertRaisesRegex(wiki.AuditError, "expectedValue mismatch"):
            self.apply_mutation(surface=surface)
        policy = json.loads(json.dumps(self.policy))
        policy["aggregateOwnerAliases"].append(json.loads(json.dumps(policy["aggregateOwnerAliases"][0])))
        with self.assertRaisesRegex(wiki.AuditError, "duplicate/unresolved"):
            self.apply_mutation(policy=policy)
        policy = json.loads(json.dumps(self.policy))
        conflict = next(row for row in policy["proseReviews"] if row["disposition"] == "conflict")
        conflict["disposition"] = "primary-present"
        with self.assertRaisesRegex(wiki.AuditError, "conflict relation/disposition mismatch"):
            self.apply_mutation(policy=policy)


class P1cPowerPassiveMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = wiki.build_artifact(REPO_ROOT)
        cls.policy = wiki.load_json(REPO_ROOT / wiki.DEFAULT_P1C_POLICY)
        cls.compact = wiki.load_json(REPO_ROOT / "data/encounter-facts-v0.111.0.json")
        cls.power_records = [row for row in cls.artifact["records"] if row["category"] == "power-passive"]

    def pre_p1c_records(self):
        records = json.loads(json.dumps(self.artifact["records"]))
        attached = {"disposition", "finalMappingId", "semanticMapping", "authorityComparison", "representation",
                    "rationale", "owner", "severity", "reviewedForVersion"}
        for record in records:
            if str(record.get("finalMappingId", "")).startswith("final-map-p1c-"):
                for key in attached: record.pop(key, None)
                record["reviewState"] = "captured-unreconciled"
        return records

    def apply_mutation(self, *, policy=None, compact=None):
        return wiki.apply_p1c_mappings(
            self.pre_p1c_records(), policy or json.loads(json.dumps(self.policy)),
            compact=compact or json.loads(json.dumps(self.compact)),
        )

    def test_all_74_origins_are_exactly_guarded_and_final_mapped(self):
        summary = self.artifact["finalMappings"]["p1c"]
        self.assertEqual(summary["mappedOriginCount"], 74)
        self.assertEqual(summary["targetFamilyCounts"], {"article-power-inline-field": 6, "article-power-invocation": 68})
        self.assertEqual(summary["dispositionCounts"], {"audit-present": 69, "missing/unparsed": 5})
        self.assertEqual(len(self.power_records), 77)
        self.assertEqual({row["reviewState"] for row in self.power_records}, {"final-mapped"})
        p1c = [row for row in self.power_records if str(row["finalMappingId"]).startswith("final-map-p1c-")]
        self.assertEqual(len(p1c), 74)
        for row in p1c:
            semantic = row["semanticMapping"]
            self.assertTrue(semantic["canonicalPower"].startswith("POWER."))
            self.assertEqual(semantic["identity"], semantic["sourceEnglishTitle"])
            self.assertFalse(row["authorityComparison"]["silentMerge"])
            self.assertTrue(any(rep.get("evidenceRole") == "reviewed-canonical-power-identity" for rep in row["representation"]))
            if row["disposition"] == "audit-present":
                self.assertTrue(any(rep.get("evidenceRole") == "exact-page-body-actor-applicability" for rep in row["representation"]))
                self.assertTrue(any(rep.get("evidenceRole") == "exact-typed-actor-Power-reference" for rep in row["representation"]))

    def test_back_attack_is_owner_disambiguated_and_missing_localization_stays_null(self):
        back = [row for row in self.power_records if row["normalized"].get("identity") == "Back Attack"]
        self.assertEqual(len(back), 2)
        by_owner = {row["origin"]["sectionPath"][-1]["title"]: row["semanticMapping"] for row in back}
        self.assertEqual(by_owner["Crusher"]["canonicalPower"], "POWER.BACK_ATTACK_LEFT_POWER")
        self.assertEqual(by_owner["Crusher"]["ownerModels"], ["MONSTER.CRUSHER"])
        self.assertEqual(by_owner["Rocket"]["canonicalPower"], "POWER.BACK_ATTACK_RIGHT_POWER")
        self.assertEqual(by_owner["Rocket"]["ownerModels"], ["MONSTER.ROCKET"])
        for row in self.power_records:
            semantic = row.get("semanticMapping", {})
            if semantic.get("sourceLocalizationClassification") == "missingLocalization":
                self.assertIsNone(semantic["sourceTemplate"])
                self.assertNotEqual(semantic.get("sourceDescriptionAuthority"), "wiki")
        self.assertEqual(self.artifact["finalMappings"]["p1c"]["knownMissingLocalizationIds"], [
            "POWER.BACK_ATTACK_LEFT_POWER", "POWER.BACK_ATTACK_RIGHT_POWER", "POWER.DAMPEN_POWER",
            "POWER.HEX_POWER", "POWER.STOCK_POWER", "POWER.SURROUNDED_POWER", "POWER.SWIPE_POWER",
        ])

    def test_inline_values_are_mapped_by_field_not_identity_only(self):
        inline = [row for row in self.power_records if row["family"] == "article-power-inline-field"]
        self.assertEqual(len(inline), 6)
        descriptions = [row for row in inline if row["normalized"]["field"] == "Description"]
        unresolved = [row for row in inline if row["normalized"]["field"] in {"Type", "Stacks"}]
        self.assertEqual({row["disposition"] for row in descriptions}, {"audit-present"})
        self.assertEqual({row["semanticMapping"]["relation"] for row in descriptions}, {"reviewed-equivalent-source-template"})
        self.assertEqual({row["disposition"] for row in unresolved}, {"missing/unparsed"})
        self.assertEqual({row["semanticMapping"]["relation"] for row in unresolved}, {"unresolved-source-field"})
        fossil = next(row for row in self.power_records if row["origin"].get("pageKey") == "Fossil Stalker" and row["normalized"].get("identity") == "Strength")
        self.assertEqual((fossil["disposition"], fossil["authorityComparison"]["closure"]), ("missing/unparsed", "unjoined"))

    def test_claim_identity_owner_and_pointer_mutations_fail(self):
        policy = json.loads(json.dumps(self.policy)); policy["reviews"][0]["claimId"] = "wiki-claim-v1-stale"
        with self.assertRaisesRegex(wiki.AuditError, "stale claim"):
            self.apply_mutation(policy=policy)
        policy = json.loads(json.dumps(self.policy)); policy["reviews"][0]["canonicalPower"] = "POWER.ARTIFACT_POWER"
        with self.assertRaisesRegex(wiki.AuditError, "canonical Power identity"):
            self.apply_mutation(policy=policy)
        policy = json.loads(json.dumps(self.policy)); row = next(item for item in policy["reviews"] if item["ownership"] is not None)
        row["ownerModels"] = ["MONSTER.UNRELATED"]
        with self.assertRaisesRegex(wiki.AuditError, "owner pointer/alias"):
            self.apply_mutation(policy=policy)
        policy = json.loads(json.dumps(self.policy)); row = next(item for item in policy["reviews"] if item["ownership"] is not None)
        row["ownership"]["powerPointer"] = row["ownership"]["ownerPointer"]
        with self.assertRaisesRegex(wiki.AuditError, "Power ownership pointer"):
            self.apply_mutation(policy=policy)
        compact = json.loads(json.dumps(self.compact)); row = next(item for item in self.policy["reviews"] if item["ownership"] is not None)
        tokens = row["ownership"]["ownerPointer"].split("/")[1:]; value = compact
        for token in tokens[:-1]: value = value[int(token)] if isinstance(value, list) else value[token]
        value[int(tokens[-1])] = "MONSTER.UNRELATED" if isinstance(value, list) else None
        if not isinstance(value, list): value[tokens[-1]] = "MONSTER.UNRELATED"
        with self.assertRaisesRegex(wiki.AuditError, "owner pointer/alias"):
            self.apply_mutation(compact=compact)


if __name__ == "__main__":
    unittest.main()
