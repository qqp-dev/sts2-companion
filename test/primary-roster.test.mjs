import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { internals as httpInternals } from "../src/http.mjs";
import { analyzeRosterGrammar, PracticalRosterError } from "../src/primary-roster.mjs";
import { createSourceAdapter, internals as adapterInternals } from "../src/source-adapter.mjs";
import { rosterGuideFixture, ROSTER_GUIDE_IDS } from "../tools/reproduce-roster-guides.mjs";

const artifact = JSON.parse(readFileSync(new URL("../data/encounter-facts-v0.111.0.json", import.meta.url), "utf8"));
const checkedFixture = JSON.parse(readFileSync(new URL("./fixtures/roster-guides.json", import.meta.url), "utf8"));
const idle = { status: "idle", encounterId: null, monsterIds: [], source: null, releaseInfo: null };
const adapter = createSourceAdapter({ projection: artifact });
const sourceRows = [...artifact.payload.sourceFacts.encounters.ordinary, ...artifact.payload.sourceFacts.encounters.event];
const sourceEncounter = (id) => sourceRows.find((row) => row.canonicalId === id);
const view = (id, state = idle) => adapter.view(state, id).encounter;
const namesFor = (encounter) => new Map(encounter.monsters.map((body) => [body.canonicalModel, body.name.text ?? body.name.template]));

const CASES = Object.freeze({
  FLYCONID_NORMAL: {
    outcomes: 2, unique: 2, cardinality: "2",
    order: ["Flyconid", "Leaf Slime (M)", "Twig Slime (M)"],
    roles: ["always present", "possible body", "possible body"],
  },
  SLIMES_WEAK: {
    outcomes: 4, unique: 4, cardinality: "3",
    order: ["Leaf Slime (S)", "Twig Slime (S)", "Leaf Slime (M)", "Twig Slime (M)"],
    roles: ["always present", "always present", "possible body", "possible body"],
  },
  SLITHERING_STRANGLER_NORMAL: {
    outcomes: 7, unique: 7, cardinality: "2–3",
    order: ["Slithering Strangler", "Snapping Jaxfruit", "Leaf Slime (M)", "Twig Slime (M)", "Leaf Slime (S)", "Twig Slime (S)"],
    roles: ["always present", "possible body", "possible body", "possible body", "possible up to 2 copies", "possible up to 2 copies"],
  },
  RUBY_RAIDERS_NORMAL: {
    outcomes: 60, unique: 60, cardinality: "3",
    order: ["Axe Raider", "Assassin Raider", "Brute Raider", "Crossbow Raider", "Tracker Raider"],
    roles: Array(5).fill("possible body"),
  },
  BOWLBUGS_NORMAL: {
    outcomes: 6, unique: 6, cardinality: "3",
    order: ["Bowlbug (Rock)", "Bowlbug (Egg)", "Bowlbug (Silk)", "Bowlbug (Nectar)"],
    roles: ["always present", "possible body", "possible body", "possible body"],
  },
  BOWLBUGS_WEAK: {
    outcomes: 2, unique: 2, cardinality: "2",
    order: ["Bowlbug (Rock)", "Bowlbug (Egg)", "Bowlbug (Nectar)"],
    roles: ["always present", "possible body", "possible body"],
  },
});

test("exact practical roster analysis is deterministic, ordered, duplicate-safe, and cardinality-checked", () => {
  assert.equal(adapter.available, true, adapter.error);
  for (const [id, expected] of Object.entries(CASES)) {
    const encounter = view(id);
    const first = analyzeRosterGrammar(encounter.roster, namesFor(encounter));
    const second = analyzeRosterGrammar(encounter.roster, namesFor(encounter));
    assert.deepEqual(first, second, `${id}: nondeterministic analysis`);
    assert.equal(first.outcomes.length, expected.outcomes, `${id}: ordered possibilities`);
    assert.equal(new Set(first.outcomes.map((row) => row.join("\0"))).size, expected.unique, `${id}: unique possibilities`);
    assert.equal(first.presentation.cardinality, expected.cardinality);
    assert.deepEqual(first.presentation.bodies.map((row) => row.name), expected.order);
    assert.deepEqual(first.presentation.bodies.map((row) => row.role), expected.roles);
    assert.deepEqual(encounter.presentation.primary.bodies.map((row) => row.name), expected.order);
    assert.deepEqual(encounter.presentation.primary.bodies.map((row) => row.role), expected.roles);
    assert.ok(encounter.presentation.primary.bodies.every((row) => row.sections.length > 0));
  }
  const strangler = analyzeRosterGrammar(view("SLITHERING_STRANGLER_NORMAL").roster, namesFor(view("SLITHERING_STRANGLER_NORMAL")));
  assert.ok(strangler.outcomes.some((row) => row.filter((model) => model === "MONSTER.LEAF_SLIME_S").length === 2));
  assert.ok(strangler.outcomes.some((row) => row.filter((model) => model === "MONSTER.TWIG_SLIME_S").length === 2));
});

test("independent draw nodes stay distinct from one shared category draw", () => {
  const fixed = (model) => ({ kind: "fixed", model });
  const choice = () => ({ kind: "uniformChoice", choices: [fixed("MONSTER.LEAF"), fixed("MONSTER.TWIG")] });
  const names = new Map([["MONSTER.LEAF", "Leaf"], ["MONSTER.TWIG", "Twig"]]);
  const independent = analyzeRosterGrammar({
    cardinality: { minimum: 2, maximum: 2 },
    grammar: { kind: "sequence", order: "fixed", children: [choice(), choice()] },
  }, names);
  assert.equal(independent.presentation.selection.relationship, "independent draws");
  assert.deepEqual(independent.outcomes, [
    ["MONSTER.LEAF", "MONSTER.LEAF"], ["MONSTER.LEAF", "MONSTER.TWIG"],
    ["MONSTER.TWIG", "MONSTER.LEAF"], ["MONSTER.TWIG", "MONSTER.TWIG"],
  ]);
  const shared = analyzeRosterGrammar({
    cardinality: { minimum: 2, maximum: 2 },
    grammar: { kind: "uniformChoice", choices: [
      { kind: "sequence", order: "fixed", children: [fixed("MONSTER.LEAF"), fixed("MONSTER.LEAF")] },
      { kind: "sequence", order: "fixed", children: [fixed("MONSTER.TWIG"), fixed("MONSTER.TWIG")] },
    ] },
  }, names);
  assert.deepEqual(shared.outcomes, [["MONSTER.LEAF", "MONSTER.LEAF"], ["MONSTER.TWIG", "MONSTER.TWIG"]]);
  assert.match(shared.presentation.lines.join(" "), /equiprobable support categories/);
  assert.doesNotMatch(shared.presentation.lines.join(" "), /orders|independent draws/);
});

test("six roster phone fixtures and DOM assertions stay exact at the 390px contract", async () => {
  assert.deepEqual(await rosterGuideFixture(), checkedFixture);
  const css = httpInternals.GUIDE_CSS;
  for (const fragment of [
    ".primary-roster{padding:.62rem .05rem}", "overflow-wrap:anywhere",
    ".primary-roster .roster-line", "grid-template-columns:minmax(0,1fr) auto",
    "@media(max-width:21rem)", "@media(min-width:44rem)",
  ]) assert.ok(css.includes(fragment), fragment);
  assert.doesNotMatch(css, /\.primary-roster\{[^}]*white-space:\s*nowrap/);
});

test("checked roster AST/proofs and possible, observed, and produced lanes remain separate", () => {
  for (const id of ROSTER_GUIDE_IDS) {
    const source = sourceEncounter(id);
    const manual = view(id);
    assert.deepEqual(manual.roster.grammar, source.initialRoster.selection, `${id}: source AST changed`);
    assert.deepEqual(manual.roster.cardinality, source.initialRoster.cardinality, `${id}: cardinality changed`);
    assert.ok(manual.proof.some((proof) => proof.factId === source.factId), `${id}: encounter proof missing`);
    assert.deepEqual(manual.observedBodies, []);
    assert.deepEqual(manual.production, null);
    assert.deepEqual(new Set(manual.roster.possibleInitialBodies), new Set(source.possibleMonsters));
    assert.ok(manual.reference?.record, `${id}: retained lane missing`);
  }
  const observedState = {
    status: "combat", encounterId: "FLYCONID_NORMAL", monsterIds: ["MONSTER.FLYCONID", "MONSTER.TWIG_SLIME_M"],
    source: "test", releaseInfo: { version: "v0.111.0", branch: "public-beta" },
  };
  const observed = adapter.view(observedState).encounter;
  assert.deepEqual(observed.observedBodies.map((row) => row.canonicalModel), ["MONSTER.FLYCONID", "MONSTER.TWIG_SLIME_M"]);
  assert.deepEqual(observed.presentation.primary.roster, view("FLYCONID_NORMAL").presentation.primary.roster,
    "one observation must not replace static grammar");
  assert.equal(observed.presentation.primary.bodies.length, 3, "observed bodies do not narrow possible cards");
});

test("unsupported and malformed roster semantics fail closed before rendering", () => {
  const mutations = [
    [(row) => { row.initialRoster.selection.kind = "weightedChoice"; }, /unsupported kind/],
    [(row) => { row.initialRoster.selection.count = 6; }, /count exceeds/],
    [(row) => { row.initialRoster.selection.constraint = "unknownLimit"; }, /unsupported constraint/],
    [(row) => { row.initialRoster.selection.draws = "withReplacement"; }, /unsupported draw semantics/],
    [(row) => { row.initialRoster.cardinality.maximum = 4; }, /declared cardinality does not match/],
  ];
  for (const [mutate, expected] of mutations) {
    const malformed = structuredClone(artifact);
    const row = malformed.payload.sourceFacts.encounters.ordinary.find((candidate) => candidate.canonicalId === "RUBY_RAIDERS_NORMAL");
    mutate(row);
    malformed.metadata.payloadSha256 = adapterInternals.payloadDigest(malformed.payload);
    const rejected = createSourceAdapter({ projection: malformed });
    assert.equal(rejected.available, false);
    assert.match(rejected.error, expected);
  }
  const fly = view("FLYCONID_NORMAL");
  const malformedGrammar = structuredClone(fly.roster);
  malformedGrammar.grammar.kind = "futureChoice";
  assert.throws(() => analyzeRosterGrammar(malformedGrammar, namesFor(fly)), PracticalRosterError);
});

test("all 81 ordinary and eight event source encounters retain non-null primary guides", () => {
  assert.equal(artifact.payload.sourceFacts.encounters.ordinary.length, 81);
  assert.equal(artifact.payload.sourceFacts.encounters.event.length, 8);
  for (const row of sourceRows) assert.ok(view(row.canonicalId).presentation.primary, row.canonicalId);
});
