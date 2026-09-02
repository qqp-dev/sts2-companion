#!/usr/bin/env node
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { createSourceAdapter } from "../src/source-adapter.mjs";

const IDLE = Object.freeze({ status: "idle", encounterId: null, monsterIds: [] });
const CEREMONIAL_FORBIDDEN = /Stamp|Break the Plow|Gain 352 Plow|Beast Cry|Stomp|Crush/;

function primary(adapter, id) {
  const encounter = adapter.view(IDLE, id).encounter;
  assert.ok(encounter.presentation.primary, `${id} has no practical primary projection`);
  return { encounter, primary: encounter.presentation.primary };
}
function practicalText(primaryProjection) {
  return JSON.stringify(primaryProjection);
}
function escapedPattern(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function exactMovePattern(moveName) {
  return new RegExp(`(^|[^A-Za-z0-9])${escapedPattern(moveName)}(?=[^A-Za-z0-9]|$)`);
}
function withoutSemanticMoveUses(value, bodyName, moveName) {
  let normalized = String(value);
  for (const entity of [bodyName].filter(Boolean).sort((left, right) => right.length - left.length)) {
    normalized = normalized.replace(
      new RegExp(`(^|[^A-Za-z0-9])${escapedPattern(entity)}(?=[^A-Za-z0-9]|$)`, "g"),
      "$1[entity]",
    );
  }
  return normalized.replace(
    new RegExp(String.raw`(^|[^A-Za-z0-9])${escapedPattern(moveName)}(?=\s+(?:timer|countdown|counter|count|threshold|amount|stacks?|wears? off|expires?)\b)`, "gi"),
    "$1[tracked concept]",
  );
}
function citationPatterns(moveName) {
  const name = escapedPattern(moveName);
  const end = "(?=[^A-Za-z0-9]|$)";
  return [
    new RegExp(`(^|[^A-Za-z0-9])(?:[Uu]se[sd]?|[Uu]sing|[Aa]ctivate[sd]?|[Aa]ctivating|[Ww]ith|[Vv]ia|[Aa]fter|[Tt]o|[Tt]hen|[Uu]sual|(?:[Vv]ersion|[Ii]teration)\\s+of)\\s+(?:the\\s+)?${name}${end}`, "m"),
    new RegExp(`(^|[^A-Za-z0-9])${name}'s${end}`, "m"),
    new RegExp(`^${name}(?=\\s*\\()`, "m"),
    new RegExp(`\\b[Mm]oves?\\s+—[^.]*?(^|[^A-Za-z0-9])${name}${end}`, "m"),
  ];
}
function assertConsequenceRows(primaryProjection) {
  for (const body of primaryProjection.bodies) {
    for (const section of body.sections) {
      for (const row of section.rows) {
        assert.equal(Object.hasOwn(row, "name"), false, `${body.name} projected an ordinary move-name slot`);
        assert.equal(typeof row.detail, "string", `${body.name} consequence is not text`);
        assert.ok(row.detail.length > 0, `${body.name} projected an empty consequence`);
      }
    }
  }
}
function assertCeremonial(players, threshold) {
  const adapter = createSourceAdapter({ players });
  assert.equal(adapter.available, true, adapter.error);
  const { encounter, primary: guide } = primary(adapter, "CEREMONIAL_BEAST_BOSS");
  assertConsequenceRows(guide);
  const practical = practicalText(guide);
  for (const expected of [
    "Force the stun", "First turn", "No attack", "Then each turn", "20 damage", "+2 Strength",
    `At ${threshold} HP or below`, "Immediately Stunned", "loses all Strength", "takes no action",
    "Apply 1 Ringing", "17 damage", "19 damage", "+4 Strength", "↻ repeat 1 → 2 → 3",
  ]) assert.ok(practical.includes(expected), `${players}P guide is missing ${expected}`);
  assert.doesNotMatch(practical, CEREMONIAL_FORBIDDEN);
  assert.doesNotMatch(practical, /Gain 160 Plow|Gain 176 Plow|Gain 352 Plow/);

  const audit = JSON.stringify({
    merge: encounter.presentation.audit,
    reference: encounter.reference,
    checked: encounter.monsters,
  });
  for (const retained of ["Stamp", "Plow", "Beast Cry", "Stomp", "Crush", "PLOW_POWER", "get_PlowAmount", "PlowPower"])
    assert.ok(audit.includes(retained), `Technical audit lost ${retained}`);
}

export function checkConsequenceFirstGuide() {
  assertCeremonial(1, 160);
  assertCeremonial(2, 352);

  const adapter = createSourceAdapter({ players: 2 });
  assert.equal(adapter.available, true, adapter.error);
  for (const id of adapter.canonicalIds) {
    const selected = adapter.view(IDLE, id).encounter;
    const view = selected.presentation.primary;
    if (!view) continue;
    assertConsequenceRows(view);
    const notes = view.notes.join("\n");
    for (const body of view.bodies) {
      const structural = [
        body.role,
        ...body.sections.flatMap((section) => [section.title, section.note, section.repeat]),
      ].filter(Boolean).join("\n");
      const exactReferenceBody = selected.reference?.record.lineup.find((candidate) => candidate.displayName === body.name);
      const moves = body.sourceOnlySupplement
        ? selected.monsters.flatMap((candidate) => candidate.moves.map((move) => ({ name: move.title.text })))
        : exactReferenceBody
          ? exactReferenceBody.moves
          : selected.monsters[body.bodyIndex].moves.map((move) => ({ name: move.title.text }));
      for (const move of moves.filter((candidate) => typeof candidate.name === "string" && candidate.name)) {
        const ordinaryCitations = withoutSemanticMoveUses(structural, body.name, move.name);
        assert.doesNotMatch(ordinaryCitations, exactMovePattern(move.name), `${id}: ${move.name}`);
        for (const pattern of citationPatterns(move.name))
          assert.doesNotMatch(notes, pattern, `${id}: ${move.name}`);
      }
    }
  }

  const terror = primary(adapter, "TERROR_EEL_ELITE");
  const terrorSection = terror.primary.bodies[0].sections[0];
  assert.deepEqual(terrorSection.rows.map((row) => row.detail), ["18 damage", "4×3 damage · +6 Vigor"]);
  assert.equal(terrorSection.marker.label, "At Terror Eel's Shriek threshold · 165 HP");
  assert.equal(terrorSection.marker.detail, "Immediately Stunned · takes no action → Apply 99 Vulnerable → resume at step 1");
  assert.equal(terrorSection.repeat, "↻ repeat 1 → 2");
  assert.doesNotMatch(practicalText(terror.primary), /Crash|Thrash|Terrorize|uses Terror|• Terror applies|\(75\)/);
  const terrorAudit = JSON.stringify(terror.encounter);
  assert.match(terrorAudit, /Crash|Thrash|\"name\":\"Terror\"/);
  assert.match(terrorAudit, /Terrorize|TERROR_MOVE/);

  const egg = primary(adapter, "OVICOPTER_NORMAL");
  const eggPattern = egg.primary.bodies.find((body) => body.name === "Tough Egg").sections[0].note;
  assert.match(eggPattern, /its Hatch timer counts down/);
  assert.match(eggPattern, /uses step 1 to transform into a Hatchling/);
  assert.doesNotMatch(eggPattern, /step 1 timer|uses Hatch to transform/);
  assert.match(JSON.stringify(egg.encounter.reference), /"name":"Hatch"/);

  const fogNotes = primary(adapter, "LIVING_FOG_NORMAL").primary.notes.join(" ");
  assert.match(fogNotes, /Gas Bombs that explode for damage and then die/);
  assert.doesNotMatch(fogNotes, /Gas Bombs that (?:the|“)|step for damage/);

  const eggNotes = primary(adapter, "OVICOPTER_NORMAL").primary.notes.join(" ");
  assert.match(eggNotes, /Tough Eggs that hatch into Hatchlings/);
  assert.match(eggNotes, /its Hatch timer counts down/);
  assert.match(eggNotes, /Hatch timer starts at 2/);
  assert.match(eggNotes, /uses the “Hatches into a Hatchling[^”]+” step to transform/);
  assert.doesNotMatch(eggNotes, /the “[^”]+” step (?:into Hatchlings|timer)/);

  const queenNotes = primary(adapter, "QUEEN_BOSS").primary.notes.join(" ");
  assert.match(queenNotes, /switch intents to the “4×5 damage” step/);
  assert.match(queenNotes, /skipping the usual “\+2 Strength” step\./);
  assert.match(queenNotes, /not use the “\+2 Strength” step/);
  assert.doesNotMatch(queenNotes, /usual the|Off with Your Head|usual Enrage|use Enrage/);

  const soulNotes = primary(adapter, "SOUL_FYSH_BOSS").primary.notes.join(" ");
  assert.match(soulNotes, /The first Intangible from the “2 Intangible” step fades instantly/);
  assert.doesNotMatch(soulNotes, /iteration of .* step|Fade's|step's/);

  const { encounter, primary: fabricator } = primary(adapter, "FABRICATOR_NORMAL");
  const practical = practicalText(fabricator);
  assert.match(practical, /Zapbot/);
  assert.match(practical, /Summons 1 aggressive bot \(Zapbot or Stabbot\)/);
  for (const action of encounter.reference.record.lineup.flatMap((body) => body.moves.map((move) => move.name))) {
    assert.doesNotMatch(practical, new RegExp(`"(?:name|title)":"${action.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}"`, "i"));
  }
  assert.doesNotMatch(practical, /Fabricating Strike|Disintegrate|"Fabricate"|"Guard"|"Zap"|"Stab"|"Noise"/);
}

function main() {
  checkConsequenceFirstGuide();
  process.stdout.write("consequence-first primary guide checks passed\n");
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
