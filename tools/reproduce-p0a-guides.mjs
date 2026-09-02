#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { collapsedDomText, renderGuidePhone } from "./reproduce-ceremonial-guide.mjs";

const FIXTURE = new URL("../test/fixtures/p0a-guides.json", import.meta.url);
const IDS = ["AXEBOTS_NORMAL", "TERROR_EEL_ELITE"];
const ORDINARY_ACTIONS = Object.freeze({
  AXEBOTS_NORMAL: ["Boot Up", "The One-Two", "Hammer Uppercut"],
  TERROR_EEL_ELITE: ["Crash", "Thrash", "Terrorize"],
});

function ordered(haystack, values, label) {
  let cursor = -1;
  for (const value of values) {
    const next = haystack.indexOf(value, cursor + 1);
    assert.ok(next > cursor, `${label}: ${value} is missing or out of order`);
    cursor = next;
  }
}

export function assertP0aPrimary(id, players, payload, collapsed) {
  const primary = payload.encounter.presentation.primary;
  assert.ok(primary, `${id} ${players}P primary missing`);
  const practical = JSON.stringify(primary);
  const audit = JSON.stringify(payload.encounter);
  for (const action of ORDINARY_ACTIONS[id]) assert.doesNotMatch(practical, new RegExp(action), `${id}: ${action} leaked into primary`);
  assert.doesNotMatch(collapsed, /BOOT_UP_MOVE|HAMMER_UPPERCUT_MOVE|CRASH_MOVE|THRASH_MOVE|TERROR_MOVE/);

  if (id === "AXEBOTS_NORMAL") {
    const [opener, cycle, replacement] = primary.bodies[0].sections;
    assert.equal(primary.bodies[0].name, "Axebot");
    assert.deepEqual(opener.rows.map((row) => [row.cue, row.detail]), [
      ["Turn 1", "18 damage · 2 Weak and 2 Frail"],
    ]);
    assert.deepEqual(cycle.rows.map((row) => [row.cue, row.detail]), [
      ["1", "11×2 damage"], ["2", "18 damage · 2 Weak and 2 Frail"],
    ]);
    assert.equal(cycle.repeat, "↻ repeat 1 → 2");
    assert.deepEqual(replacement.rows.map((row) => [row.cue, row.detail]), [
      ["First replacement", "15 Block · +4 Strength · +10 Max HP cumulative"],
      ["Second replacement", "15 Block · +8 Strength · +20 Max HP cumulative"],
      ["Then", "enter the ordinary cycle at step 2"],
    ]);
    assert.match(replacement.note, /Stock.*Axebot/);
    assert.doesNotMatch(JSON.stringify(cycle), /Block|Strength|Max HP|replacement/i);
    assert.doesNotMatch(practical, /\+24|30 Block/);
    for (const concept of ["Axebot", "Stock", "Weak", "Frail", "Strength", "Block", "Fatal"])
      assert.match(practical, new RegExp(concept), `${id}: ${concept}`);
    for (const retained of ["Boot Up", "The One-Two", "Hammer Uppercut", "BOOT_UP_MOVE", "Fatal", "Stock"])
      assert.match(audit, new RegExp(retained), `${id} audit: ${retained}`);
    ordered(collapsed, [
      "AXEBOT", "Stock 2", "Initial Axebot opener", "Turn 1", "18 damage", "Ordinary repeating cycle",
      "11×2 damage", "repeat 1 → 2", "Stock replacement opener", "First replacement", "+4 Strength",
      "+10 Max HP", "Second replacement", "+8 Strength", "+20 Max HP", "enter the ordinary cycle at step 2",
    ], `${id} ${players}P DOM`);
  } else {
    const section = primary.bodies[0].sections[0];
    const expectedThreshold = players === 1 ? 75 : 165;
    const otherThreshold = players === 1 ? 165 : 75;
    assert.equal(primary.bodies[0].name, "Terror Eel");
    assert.equal(primary.bodies[0].setup, null);
    assert.deepEqual(section.rows.map((row) => [row.cue, row.detail]), [
      ["1", "18 damage"], ["2", "4×3 damage · +6 Vigor"],
    ]);
    assert.equal(section.marker.label, `At Terror Eel's Shriek threshold · ${expectedThreshold} HP`);
    assert.equal(section.marker.detail, "Immediately Stunned · takes no action → Apply 99 Vulnerable → resume at step 1");
    assert.equal(section.repeat, "↻ repeat 1 → 2");
    const sequence = JSON.stringify(section);
    assert.equal((sequence.match(/Shriek threshold/g) ?? []).length, 1);
    assert.doesNotMatch(sequence, new RegExp(`threshold[^.]*\\b${otherThreshold}\\b`, "i"));
    for (const concept of ["Terror Eel", "Shriek", "Stunned", "Vulnerable", "Vigor"])
      assert.match(practical, new RegExp(concept), `${id}: ${concept}`);
    assert.doesNotMatch(practical, /Crash|Thrash|Terrorize|uses Terror|\(75\)/);
    for (const retained of ["Crash", "Thrash", "\"name\":\"Terror\"", "Terrorize", "TERROR_MOVE", "Shriek"])
      assert.match(audit, new RegExp(retained), `${id} audit: ${retained}`);
    ordered(collapsed, [
      "TERROR EEL", "Two-step cycle", "1", "18 damage", "2", "4×3 damage", "+6 Vigor",
      `Shriek threshold · ${expectedThreshold} HP`, "Immediately Stunned", "takes no action",
      "Apply 99 Vulnerable", "resume at step 1", "repeat 1 → 2",
    ], `${id} ${players}P DOM`);
  }
}

export async function p0aFixture() {
  const fixture = {};
  for (const players of [1, 2]) {
    fixture[`${players}P`] = {};
    for (const id of IDS) {
      const { root, payload } = await renderGuidePhone(id, players);
      const collapsed = collapsedDomText(root);
      assertP0aPrimary(id, players, payload, collapsed);
      fixture[`${players}P`][id] = payload.encounter.presentation.primary;
    }
  }
  return fixture;
}

async function main() {
  const fixture = await p0aFixture();
  const rendered = `${JSON.stringify(fixture, null, 2)}\n`;
  if (process.argv.includes("--write")) writeFileSync(FIXTURE, rendered);
  else if (process.argv.includes("--check")) assert.equal(rendered, readFileSync(FIXTURE, "utf8"), "P0a presentation fixtures drifted");
  else process.stdout.write(rendered);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
