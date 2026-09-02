#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { collapsedDomText, renderGuidePhone } from "./reproduce-ceremonial-guide.mjs";

const FIXTURE = new URL("../test/fixtures/roster-guides.json", import.meta.url);
export const ROSTER_GUIDE_IDS = Object.freeze([
  "FLYCONID_NORMAL",
  "SLIMES_WEAK",
  "SLITHERING_STRANGLER_NORMAL",
  "RUBY_RAIDERS_NORMAL",
  "BOWLBUGS_NORMAL",
  "BOWLBUGS_WEAK",
]);
const EXPECTED = Object.freeze({
  FLYCONID_NORMAL: {
    cardinality: "2", names: ["Flyconid", "Leaf Slime (M)", "Twig Slime (M)"],
    roles: ["always present", "possible body", "possible body"],
    primaryTerms: ["2 initial bodies", "Always: Flyconid", "uniformly", "Leaf Slime (M)", "Twig Slime (M)", "not all co-present"],
  },
  SLIMES_WEAK: {
    cardinality: "3", names: ["Leaf Slime (S)", "Twig Slime (S)", "Leaf Slime (M)", "Twig Slime (M)"],
    roles: ["always present", "always present", "possible body", "possible body"],
    primaryTerms: ["3 initial bodies", "Leaf Slime (S)", "Twig Slime (S)", "Leaf Slime (M)", "Twig Slime (M)", "order", "uniformly"],
  },
  SLITHERING_STRANGLER_NORMAL: {
    cardinality: "2–3", names: ["Slithering Strangler", "Snapping Jaxfruit", "Leaf Slime (M)", "Twig Slime (M)", "Leaf Slime (S)", "Twig Slime (S)"],
    roles: ["always present", "possible body", "possible body", "possible body", "possible up to 2 copies", "possible up to 2 copies"],
    primaryTerms: ["2–3 initial bodies", "3 equiprobable support categories", "Snapping Jaxfruit", "independent draws", "duplicates", "Leaf Slime (S) + Leaf Slime (S)", "Twig Slime (S) + Twig Slime (S)"],
  },
  RUBY_RAIDERS_NORMAL: {
    cardinality: "3", names: ["Axe Raider", "Assassin Raider", "Brute Raider", "Crossbow Raider", "Tracker Raider"],
    roles: Array(5).fill("possible body"),
    primaryTerms: ["3 initial bodies", "exactly 3 distinct", "raiders", "without replacement", "from 5", "Axe Raider", "Assassin Raider", "Brute Raider", "Crossbow Raider", "Tracker Raider"],
  },
  BOWLBUGS_NORMAL: {
    cardinality: "3", names: ["Bowlbug (Rock)", "Bowlbug (Egg)", "Bowlbug (Silk)", "Bowlbug (Nectar)"],
    roles: ["always present", "possible body", "possible body", "possible body"],
    primaryTerms: ["3 initial bodies", "Bowlbug (Rock)", "exactly 2 distinct", "workers", "without replacement", "from 3", "Bowlbug (Egg)", "Bowlbug (Silk)", "Bowlbug (Nectar)"],
  },
  BOWLBUGS_WEAK: {
    cardinality: "2", names: ["Bowlbug (Rock)", "Bowlbug (Egg)", "Bowlbug (Nectar)"],
    roles: ["always present", "possible body", "possible body"],
    primaryTerms: ["2 initial bodies", "Bowlbug (Rock)", "exactly one worker", "uniformly", "Bowlbug (Egg)", "Bowlbug (Nectar)"],
  },
});
const ACTION_LABELS = Object.freeze([
  "Sticky Shot", "Corrosive Spit", "Tackle", "Killshot", "Headbutt", "Toxic Spit",
]);

function allStrings(value, result = []) {
  if (typeof value === "string") result.push(value);
  else if (Array.isArray(value)) value.forEach((item) => allStrings(item, result));
  else if (value && typeof value === "object") Object.values(value).forEach((item) => allStrings(item, result));
  return result;
}

export function assertRosterGuide(id, payload, collapsed, fullDom) {
  const expected = EXPECTED[id];
  const encounter = payload.encounter;
  const primary = encounter.presentation.primary;
  assert.ok(primary, `${id}: primary missing`);
  assert.ok(primary.roster, `${id}: typed primary roster missing`);
  assert.equal(primary.roster.cardinality, expected.cardinality);
  assert.equal(primary.roster.variable, true);
  assert.ok(primary.roster.selection && typeof primary.roster.selection === "object");
  assert.deepEqual(primary.bodies.map((body) => body.name), expected.names);
  assert.deepEqual(primary.bodies.map((body) => body.role), expected.roles);
  assert.equal(new Set(primary.bodies.map((body) => body.name)).size, primary.bodies.length, `${id}: one card per body type`);
  assert.ok(primary.bodies.every((body) => body.sections.length > 0), `${id}: every possible body has mechanics`);
  for (const term of expected.primaryTerms) assert.ok(collapsed.includes(term), `${id}: missing ${term}`);
  assert.match(collapsed, /Body cards cover every possible type/);
  assert.doesNotMatch(collapsed, /\d+ possible initial|random bodies|MONSTER\.|\{[^}]*\}/);
  const practical = allStrings(primary).join("\n");
  for (const action of ACTION_LABELS) assert.ok(!practical.includes(action), `${id}: action label leaked: ${action}`);
  assert.doesNotMatch(practical, /\b(?:MONSTER|POWER|ENCOUNTER|SOURCE)\./);
  assert.match(fullDom, /Exact checked source encounter record/);
  assert.match(fullDom, /Exact retained wiki\/reference record/);
  assert.ok(fullDom.includes(JSON.stringify(encounter.roster.cardinality.minimum)));
  assert.ok(fullDom.includes(encounter.roster.grammar.kind));
  for (const model of encounter.roster.possibleInitialBodies) assert.ok(fullDom.includes(model), `${id}: audit lost ${model}`);
}

export async function rosterGuideFixture() {
  const fixture = {};
  for (const id of ROSTER_GUIDE_IDS) {
    const { root, payload } = await renderGuidePhone(id, 2);
    const collapsed = collapsedDomText(root).replace(/\s+/g, " ").trim();
    assertRosterGuide(id, payload, collapsed, root.textContent);
    fixture[id] = { roster: payload.encounter.presentation.primary.roster, bodies: payload.encounter.presentation.primary.bodies, collapsed };
  }
  const strangler = fixture.SLITHERING_STRANGLER_NORMAL.collapsed;
  assert.doesNotMatch(strangler, /one of each/i);
  assert.doesNotMatch(fixture.RUBY_RAIDERS_NORMAL.collapsed, /5 (?:simultaneous )?initial bodies/i);
  assert.doesNotMatch(fixture.FLYCONID_NORMAL.collapsed, /Leaf Slime \(M\).*(?:and|\+) Twig Slime \(M\).*initial/i);
  return fixture;
}

async function main() {
  const actual = `${JSON.stringify(await rosterGuideFixture(), null, 2)}\n`;
  if (process.argv.includes("--write")) writeFileSync(FIXTURE, actual);
  else if (process.argv.includes("--check")) assert.equal(actual, readFileSync(FIXTURE, "utf8"), "roster guide fixture drifted");
  else process.stdout.write(actual);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
