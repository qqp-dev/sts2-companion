#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { collapsedDomText, renderGuidePhone } from "./reproduce-ceremonial-guide.mjs";

const FIXTURE = new URL("../test/fixtures/event-primary-guides.json", import.meta.url);
export const EVENT_PRIMARY_IDS = Object.freeze([
  "BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER",
  "BATTLEWORN_DUMMY_EVENT_V2_ENCOUNTER",
  "BATTLEWORN_DUMMY_EVENT_V3_ENCOUNTER",
  "DENSE_VEGETATION_EVENT_ENCOUNTER",
  "FAKE_MERCHANT_EVENT_ENCOUNTER",
  "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER",
  "PUNCH_OFF_EVENT_ENCOUNTER",
  "THE_ARCHITECT_EVENT_ENCOUNTER",
]);
const ORDINARY_ACTIONS = Object.freeze([
  "Nothing", "Nasty Bite", "Wriggle", "Spawned", "Swipe", "Spew Coins", "Throw Relic", "Enrage",
  "War Chant", "Flail", "Ram", "READY", "Strong Punch", "Fast Punch",
]);
const ENCOUNTER_ACTIONS = Object.freeze({
  BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER: ["Nothing"],
  BATTLEWORN_DUMMY_EVENT_V2_ENCOUNTER: ["Nothing"],
  BATTLEWORN_DUMMY_EVENT_V3_ENCOUNTER: ["Nothing"],
  DENSE_VEGETATION_EVENT_ENCOUNTER: ["Nasty Bite", "Wriggle", "Spawned"],
  FAKE_MERCHANT_EVENT_ENCOUNTER: ["Swipe", "Spew Coins", "Throw Relic", "Enrage"],
  MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER: ["War Chant", "Flail", "Ram"],
  PUNCH_OFF_EVENT_ENCOUNTER: ["READY", "Strong Punch", "Fast Punch"],
  THE_ARCHITECT_EVENT_ENCOUNTER: ["Nothing"],
});
const RAW_IDS = /\b(?:MONSTER|POWER|CARD|ENCOUNTER|SOURCE|RUNTIME)\.|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/;
const UNRELATED_EVENT_COPY = /rest-site|heal all players|HP-loss|gain the event's checked gold|construct a relic reward|offer the constructed reward|Injury curse|upgrade selection|dialogue/i;

function escapedPattern(value) { return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
function allText(value, result = []) {
  if (typeof value === "string") result.push(value);
  else if (Array.isArray(value)) value.forEach((item) => allText(item, result));
  else if (value && typeof value === "object") Object.values(value).forEach((item) => allText(item, result));
  return result.join(" ");
}

export function assertEventPrimary(id, players, payload, collapsed, fullDom = "") {
  assert.equal(payload.status, "selected", `${id} selector was not accepted`);
  const encounter = payload.encounter;
  const primary = encounter.presentation.primary;
  assert.ok(primary, `${id} ${players}P primary missing`);
  assert.equal(encounter.kind, "event");
  assert.equal(encounter.reference, null, `${id} manufactured a retained reference`);
  assert.equal(primary.header.kind, "EVENT FIGHT");
  assert.ok(primary.header.placement);
  assert.ok(primary.bodies.length > 0);
  assert.equal(primary.provenance.label, `checked source values · A8 / ${players}P presentation`);
  assert.equal(primary.provenance.authority, "checked-source-only");
  assert.doesNotMatch(primary.provenance.label, /wiki|reference/i);

  const practical = JSON.stringify(primary);
  const practicalText = allText(primary);
  const audit = JSON.stringify(encounter);
  assert.match(practicalText, /HP/);
  assert.match(practicalText, /(?:damage|Block|Strength|Frail|Artifact|Time Limit|takes no (?:combat )?action)/i);
  assert.doesNotMatch(practical, RAW_IDS);
  assert.doesNotMatch(collapsed, RAW_IDS);
  assert.doesNotMatch(practical, UNRELATED_EVENT_COPY);
  assert.doesNotMatch(collapsed, UNRELATED_EVENT_COPY);
  for (const action of ORDINARY_ACTIONS) {
    const exactAction = new RegExp(`\b${escapedPattern(action)}\b`);
    assert.doesNotMatch(practical, exactAction, `${id}: ordinary action label ${action} leaked into primary`);
    assert.doesNotMatch(collapsed, exactAction, `${id}: ordinary action label ${action} leaked into collapsed DOM`);
  }
  assert.match(audit, /GRAPH\.|SOURCE\.MOVE|canonicalId/);
  assert.match(audit, /SOURCE\.SCALING\.(?:BLOCK|POWER)/);
  for (const action of ENCOUNTER_ACTIONS[id]) {
    assert.ok(audit.includes(action), `${id}: ${action} missing from source audit`);
    if (fullDom) assert.ok(fullDom.includes(action), `${id}: ${action} missing from Technical DOM`);
  }

  if (id.startsWith("BATTLEWORN_DUMMY_EVENT_V")) {
    assert.match(practicalText, /Battle Friend V[123]\.0/);
    assert.match(practicalText, /Time Limit 3/);
    assert.match(practicalText, /3 → 2 → 1/);
    assert.match(practicalText, /ran out of time/i);
    assert.match(practicalText, /escape and leave the fight/i);
    assert.match(collapsed, /Time Limit 3/);
  } else if (id === "DENSE_VEGETATION_EVENT_ENCOUNTER") {
    assert.match(practicalText, /4 Wrigglers|Wriggler ×4/);
    assert.match(practicalText, /four simultaneous initial bodies/i);
    assert.match(practicalText, /Infection/);
    assert.match(practicalText, /\+2 Strength/);
  } else if (id === "PUNCH_OFF_EVENT_ENCOUNTER") {
    assert.match(practicalText, /2 Punch Constructs|Punch Construct ×2/);
    assert.match(practicalText, /two simultaneous initial bodies/i);
    assert.match(practicalText, /runtime-random starting HP reduction/i);
    assert.match(practicalText, new RegExp(`${players === 1 ? 10 : 20} Block`));
    assert.match(practicalText, new RegExp(`Artifact base ${players === 1 ? 1 : 2}`));
    assert.match(practicalText, /1 Frail/);
  } else if (id === "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER") {
    assert.match(practicalText, /Strength base 6/);
    assert.match(practicalText, new RegExp(`Plating base ${players === 1 ? 6 : 18}`));
    assert.match(practicalText, /no more than twice consecutively/i);
    assert.match(practicalText, /cannot repeat immediately/i);
  } else if (id === "FAKE_MERCHANT_EVENT_ENCOUNTER") {
    assert.match(practicalText, /2 damage × 8/);
    assert.match(practicalText, /1 Frail/);
    assert.match(practicalText, /\+2 Strength/);
    assert.match(practicalText, /cooldown of 3/i);
    assert.match(practicalText, /cannot repeat immediately/i);
    assert.match(practicalText, /next branch is attack-only/i);
  } else if (id === "THE_ARCHITECT_EVENT_ENCOUNTER") {
    assert.match(practicalText, /scripted non-turn combat/i);
    assert.match(practicalText, /takes no combat action/i);
    assert.doesNotMatch(practicalText, /damage|event choice|choose|reward/i);
  }
}

export async function eventPrimaryFixture() {
  const fixture = {};
  for (const players of [1, 2]) {
    fixture[`${players}P`] = {};
    for (const id of EVENT_PRIMARY_IDS) {
      const { root, payload } = await renderGuidePhone(id, players);
      const collapsed = collapsedDomText(root).replace(/\s+/g, " ").trim();
      assertEventPrimary(id, players, payload, collapsed, root.textContent);
      fixture[`${players}P`][id] = { primary: payload.encounter.presentation.primary, collapsed };
    }
  }
  const hp = (players, id) => fixture[`${players}P`][id].primary.bodies[0].hp;
  assert.deepEqual(EVENT_PRIMARY_IDS.slice(0, 3).map((id) => hp(1, id)), ["75", "150", "300"]);
  assert.deepEqual(EVENT_PRIMARY_IDS.slice(0, 3).map((id) => hp(2, id)), ["180", "360", "720"]);
  assert.equal(hp(1, "DENSE_VEGETATION_EVENT_ENCOUNTER"), "18–22");
  assert.equal(hp(2, "DENSE_VEGETATION_EVENT_ENCOUNTER"), "39–48");
  assert.equal(hp(1, "PUNCH_OFF_EVENT_ENCOUNTER"), "60");
  assert.equal(hp(2, "PUNCH_OFF_EVENT_ENCOUNTER"), "132");
  return fixture;
}

async function main() {
  const actual = `${JSON.stringify(await eventPrimaryFixture(), null, 2)}\n`;
  if (process.argv.includes("--write")) writeFileSync(FIXTURE, actual);
  else if (process.argv.includes("--check")) assert.equal(actual, readFileSync(FIXTURE, "utf8"), "event primary fixture drifted");
  else process.stdout.write(actual);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
