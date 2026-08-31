import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { compileCalloutCollection } from "../src/decision-callouts.mjs";
import { internals as httpInternals } from "../src/http.mjs";
import { createSourceAdapter, internals as adapterInternals } from "../src/source-adapter.mjs";
import { buildEncounterPresentation } from "../src/source-presentation.mjs";

const artifact = JSON.parse(readFileSync(new URL("../data/encounter-facts-v0.111.0.json", import.meta.url), "utf8"));
const adapter = createSourceAdapter({ projection: artifact });
const idle = { status: "idle", encounterId: null, monsterIds: [], source: null, releaseInfo: null };
const encounter = (id) => adapter.view(idle, id).encounter;
const qualifications = Object.freeze({
  playerControllable: true, nonObvious: true, materiallyUseful: true,
  ordinaryStateRobust: true, sourceSupported: true, causallyExplainable: true, distinct: true,
});
function candidate(id, rank) {
  return {
    id, distinctnessKey: `MECHANIC.${id}`, language: "static-conditional", rank, qualifications,
    headline: `${id}: when the checked condition applies, the controlled choice changes the effect`,
    causalBasis: "The controlled branch changes the cited ordered consequence.",
    condition: "When the checked source condition applies.",
    basis: { factRefs: [`FACT.${id}`], conditionRefs: [`CONDITION.${id}`], causalRefs: [`CAUSE.${id}`] },
  };
}
function strings(value, result = []) {
  if (typeof value === "string") result.push(value);
  else if (Array.isArray(value)) value.forEach((item) => strings(item, result));
  else if (value && typeof value === "object") Object.values(value).forEach((item) => strings(item, result));
  return result;
}

test("phone presentation is deterministic and keeps effect signatures separate from move audit metadata", () => {
  assert.equal(adapter.available, true, adapter.error);
  const axebot = encounter("AXEBOTS_NORMAL");
  assert.deepEqual(buildEncounterPresentation(axebot), buildEncounterPresentation(axebot));
  const body = axebot.presentation.bodies[0];
  assert.match(body.hp, /76–86/);
  assert.match(body.initialEffects[0].line, /apply source formula Stock/);
  assert.match(body.behavior.headline, /starts at Effect A.*repeating cycle.*follow-ups/);
  assert.deepEqual(body.effects[2].orderedEffects.map((row) => row.line), [
    "all opponents · source formula damage",
    "registered targets · apply 2 Weak",
    "registered targets · apply 2 Frail",
  ]);
  const collapsed = JSON.stringify({ hp: body.hp, initial: body.initialEffects, effects: body.effects, behavior: body.behavior });
  for (const audit of ["BOOT_UP_MOVE", "HAMMER_UPPERCUT_MOVE", "Boot Up", "Hammer Uppercut", "MONSTER.AXEBOT#"]) assert.ok(!collapsed.includes(audit), audit);
  assert.equal(axebot.monsters[0].moves[0].title.text, "Boot Up");
  assert.match(axebot.monsters[0].moves[0].canonicalId, /BOOT_UP_MOVE/);
});

test("roster fixtures preserve random alternatives, duplicate bodies, and no co-presence claim", () => {
  const branching = encounter("BOWLBUGS_NORMAL").presentation;
  assert.equal(branching.roster.cardinality, "3");
  assert.match(branching.roster.summary, /2 random distinct bodies.*Egg.*Silk.*Nectar.*without replacement/);
  assert.match(branching.roster.caveat, /not all co-present/);
  assert.ok(branching.bodies.some((body) => /conditional branches/.test(body.behavior.headline)));

  const multi = encounter("DECIMILLIPEDE_ELITE").presentation;
  assert.equal(multi.roster.summary, "3× Decimillipede");
  assert.equal(multi.bodies.length, 3);
  assert.ok(multi.bodies.some((body) => /random branch/.test(body.behavior.headline)));
  assert.ok(multi.lifecycle.mechanics.some((row) => row.family === "Phase Systems"));
  const phaseText = strings(multi.lifecycle.mechanics).join(" ");
  assert.match(phaseText, /anyOtherSegmentAlive/);
  assert.match(phaseText, /same body · restore HP from the checked formula/);
});

test("production and lifecycle fixtures expose cadence, conditions, pools, and replacement rules", () => {
  const production = encounter("FABRICATOR_NORMAL").presentation.production;
  assert.ok(production);
  assert.match(production.caveat, /not initial or co-present bodies/);
  assert.deepEqual(production.possibilities, ["Guardbot", "Noisebot", "Stabbot", "Zapbot"]);
  assert.ok(production.rules.some((rule) => /0–2 added bodies per eligible trigger/.test(rule.cadence)));
  assert.ok(production.rules.some((rule) => /same side creatures including owner count/.test(rule.condition)));
  assert.ok(production.rules.some((rule) => rule.attempts.some((attempt) => /runtime-random.*Guardbot.*Noisebot/.test(attempt))));

  const axebot = encounter("AXEBOTS_NORMAL").presentation.lifecycle;
  const replacement = axebot.mechanics.find((row) => row.family === "Death Production");
  assert.ok(replacement);
  assert.match(strings(replacement).join(" "), /create Axebot body.*add the exact created body/);
  assert.ok(axebot.rules.some((rule) => /State removal order/.test(rule)));
  assert.ok(axebot.rules.some((rule) => /centralized check/.test(rule)));
});

test("relationship and initial-Power lifecycle mechanics reach the phone capsule", () => {
  const queen = encounter("QUEEN_BOSS");
  assert.ok(queen.lifecycle.mechanics.relationships.some((row) => row.relationshipId === "LIFECYCLE.RELATIONSHIP.QUEEN_AMALGAM_DEATH"));
  const queenRelationship = queen.presentation.lifecycle.mechanics.find((row) => row.identity === "LIFECYCLE.RELATIONSHIP.QUEEN_AMALGAM_DEATH");
  assert.match(strings(queenRelationship).join(" "), /HasAmalgamDied = true.*Enraged behavior/);

  const kin = encounter("THE_KIN_BOSS");
  assert.ok(kin.lifecycle.mechanics.relationships.some((row) => row.relationshipId === "LIFECYCLE.RELATIONSHIP.KIN_FOLLOWER_PRIESTS"));
  const kinRelationship = kin.presentation.lifecycle.mechanics.find((row) => row.identity === "LIFECYCLE.RELATIONSHIP.KIN_FOLLOWER_PRIESTS");
  assert.match(strings(kinRelationship).join(" "), /all follower death response/);
  assert.doesNotMatch(strings(kinRelationship).join(" "), /\bcurrent\b/i);

  const policyFixtures = [
    ["AXEBOTS_NORMAL", "POWER.STOCK_POWER", 1, /Stock · Should Stop Combat From Ending = yes/],
    ["TEST_SUBJECT_BOSS", "POWER.ADAPTABLE_POWER", 3, /Adaptable · Should Stop Combat From Ending = yes/],
    ["DECIMILLIPEDE_ELITE", "POWER.REATTACH_POWER", 3, /Reattach · Should (Creature Be Removed|Power Be Removed|Owner Death Trigger Fatal)/],
  ];
  for (const [encounterId, power, count, signature] of policyFixtures) {
    const capsule = encounter(encounterId);
    const policies = capsule.lifecycle.mechanics.powerRetentionPolicies;
    assert.equal(policies.filter((row) => row.power === power).length, count);
    assert.match(strings(capsule.presentation.lifecycle.mechanics.filter((row) => row.family === "Power Retention Policies")).join(" "), signature);
  }
});

test("schema-11 lifecycle family census covers array and object mechanic shapes", () => {
  const mechanics = artifact.payload.sourceFacts.lifecycle.mechanics;
  const census = Object.fromEntries(Object.entries(mechanics).map(([family, value]) => [family,
    Array.isArray(value) ? { shape: "array", count: value.length } : { shape: "object", keys: Object.keys(value).sort() },
  ]));
  assert.deepEqual(census, {
    cleanup: { shape: "array", count: 11 },
    deathProduction: { shape: "array", count: 3 },
    doom: { shape: "object", keys: ["doomContractId", "failureContract", "inputCardinality", "listIdentity", "orderedEffects"] },
    eventCombat: { shape: "object", keys: ["battleTimeLimit", "ranOutOfTime", "registrations", "routing"] },
    phaseSystems: { shape: "array", count: 6 },
    powerRetentionPolicies: { shape: "array", count: 18 },
    relationships: { shape: "array", count: 6 },
    runTermination: { shape: "object", keys: ["architectVisualBoundary", "guaranteeKillAllPlayers", "onEnded", "winRun"] },
    subscriptions: { shape: "array", count: 3 },
  });

  const record = { listener: "POWER.FIXTURE_POWER", branches: [{ orderedEffects: [{ kind: "decrementPower", owner: "POWER.FIXTURE_POWER" }] }] };
  const nested = { futureObjectFamily: { wrapper: { checkedClock: record } } };
  const units = adapterInternals.lifecycleMechanicUnits(nested);
  assert.deepEqual(units.map((unit) => unit.path), [["futureObjectFamily", "wrapper", "checkedClock"]]);
  assert.deepEqual(adapterInternals.selectedLifecycleMechanicTree(nested.futureObjectFamily, new Set([record])), {
    wrapper: { checkedClock: record },
  });
});

test("Battleworn object-family countdown is exact, human-readable, and encounter-scoped", () => {
  const capsule = encounter("BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER");
  const checked = artifact.payload.sourceFacts.lifecycle.mechanics.eventCombat.battleTimeLimit;
  assert.deepEqual(capsule.lifecycle.mechanics.eventCombat.battleTimeLimit, checked);
  assert.deepEqual(Object.keys(capsule.lifecycle.mechanics), ["eventCombat"]);
  assert.deepEqual(Object.keys(capsule.lifecycle.mechanics.eventCombat), ["battleTimeLimit", "registrations"]);
  assert.deepEqual(capsule.lifecycle.mechanics.eventCombat.registrations.map((row) => row.canonicalEncounter), [
    "ENCOUNTER.BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER",
  ]);
  const exact = JSON.stringify(capsule.lifecycle.mechanics);
  for (const unrelated of ["BATTLEWORN_DUMMY_EVENT_V2_ENCOUNTER", "BATTLEWORN_DUMMY_EVENT_V3_ENCOUNTER", "DENSE_VEGETATION", "runTermination", "POWER.DOOM_POWER"]) {
    assert.ok(!exact.includes(unrelated), unrelated);
  }

  const clock = capsule.presentation.lifecycle.mechanics.find((row) => row.family === "Event Combat · Battle Time Limit");
  assert.ok(clock);
  assert.equal(clock.identity, "POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER");
  assert.equal(clock.branches.length, 4);
  const visible = strings(clock).join(" ");
  for (const pattern of [
    /After Side Turn End/, /participants contains exact Power owner/, /power\.amount.*> 1/,
    /Countdown · decrement Battleworn Dummy Time Limit by 1/, /power\.amount.*≤ 1/, /set RanOutOfTime = true/,
    /escape through the checked removal graph and remove the creature node/, /ordinary centralized victory check/,
  ]) assert.match(visible, pattern);
  assert.doesNotMatch(visible, /\b(current|this turn|will|now)\b/i);
});

test("object-shaped lifecycle records receive strict identity and operation validation", () => {
  const mutations = [
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.eventCombat.battleTimeLimit.listener = "POWER.NOT_CHECKED"; }, /lifecycle listener Power join/],
    [(value) => {
      value.payload.sourceFacts.lifecycle.mechanics.eventCombat.battleTimeLimit.branches[3].orderedEffects[1].owner = "POWER.bad";
    }, /owner has malformed Power reference/],
    [(value) => {
      value.payload.sourceFacts.lifecycle.mechanics.eventCombat.registrations[0].canonicalEncounter = "ENCOUNTER.NOT_CHECKED";
    }, /has unresolved encounter/],
  ];
  for (const [mutate, expected] of mutations) {
    const malformed = structuredClone(artifact); mutate(malformed);
    malformed.metadata.payloadSha256 = adapterInternals.payloadDigest(malformed.payload);
    const failed = createSourceAdapter({ projection: malformed });
    assert.equal(failed.available, false);
    assert.match(failed.error, expected);
  }
});

test("schema-11 lifecycle Power identities remain lossless in adapter records and phone text", () => {
  const fixtures = [
    {
      encounterId: "WATERFALL_GIANT_BOSS",
      operationPowers: ["POWER.STEAM_ERUPTION_POWER"],
      policyCounts: { "POWER.STEAM_ERUPTION_POWER": 3 },
      text: [/remove Steam Eruption/, /Steam Eruption · Should Stop Combat From Ending = yes/],
    },
    {
      encounterId: "TEST_SUBJECT_BOSS",
      operationPowers: ["POWER.PAINFUL_STABS_POWER", "POWER.NEMESIS_POWER", "POWER.ADAPTABLE_POWER", "POWER.PAINFUL_STABS_POWER"],
      policyCounts: { "POWER.ADAPTABLE_POWER": 3, "POWER.PAINFUL_STABS_POWER": 2 },
      text: [/apply Painful Stabs/, /apply Nemesis/, /remove Adaptable/, /remove Painful Stabs/],
    },
    {
      encounterId: "OVICOPTER_NORMAL",
      operationPowers: ["POWER.HATCH_POWER"],
      policyCounts: { "POWER.MINION_POWER": 2 },
      text: [/remove Hatch/, /Minion · Should Owner Death Trigger Fatal = no/],
    },
  ];
  for (const fixture of fixtures) {
    const capsule = encounter(fixture.encounterId);
    const phaseOperations = (capsule.lifecycle.mechanics.phaseSystems ?? [])
      .flatMap((row) => [...(row.orderedEffects ?? []), ...(row.transitions ?? []).flatMap((transition) => transition.orderedEffects ?? [])])
      .filter((operation) => ["applyPowerByRef", "removePower"].includes(operation.kind));
    assert.deepEqual(phaseOperations.map((operation) => operation.power), fixture.operationPowers);
    assert.ok(phaseOperations.every((operation) => operation.model === undefined), "lifecycle operations use schema-11 power, not move-operation model");

    const policyCounts = Object.create(null);
    for (const policy of capsule.lifecycle.mechanics.powerRetentionPolicies ?? []) policyCounts[policy.power] = (policyCounts[policy.power] ?? 0) + 1;
    assert.deepEqual({ ...policyCounts }, fixture.policyCounts);
    const visible = strings(capsule.presentation.lifecycle.mechanics).join(" ");
    for (const pattern of fixture.text) assert.match(visible, pattern);
    assert.doesNotMatch(visible, /remove Unknown/);
  }
});

test("Tough Egg move removal renders its checked runtime-selected Power contract", () => {
  const capsule = encounter("OVICOPTER_NORMAL");
  const egg = capsule.monsters.find((body) => body.canonicalModel === "MONSTER.TOUGH_EGG");
  const hatch = egg.moves.find((move) => move.canonicalId === "MONSTER.TOUGH_EGG#HATCH_MOVE");
  const runtimeRemoval = hatch.operations.find((operation) => operation.kind === "removePower" && operation.model === undefined);
  assert.equal(runtimeRemoval.target, "runtimeSelectedPowerInstance");
  assert.equal(runtimeRemoval.modelContract.classification, "runtimeSelectedPowerInstance");

  const hatchLines = capsule.presentation.bodies.find((body) => body.name === "Tough Egg")
    .effects.find((effect) => effect.label === "Effect A").orderedEffects.map((effect) => effect.line);
  assert.deepEqual(hatchLines, [
    "self · update internal state to true",
    "self · remove Hatch",
    "runtime selected power instance · remove runtime selected power instance",
    "lifecycle helper · hatch",
  ]);
  assert.doesNotMatch(hatchLines.join(" "), /Unknown/);
});

test("schema-11 death production and restored-Hatch effects retain checked body and Power identities", () => {
  const merc = encounter("GREMLIN_MERC_NORMAL");
  const surprise = merc.lifecycle.mechanics.deathProduction
    .find((row) => row.deathProductionId === "LIFECYCLE.DEATH_PRODUCTION.SURPRISE");
  const precreate = surprise.orderedEffects.find((operation) => operation.kind === "precreateBody");
  const targetedPower = surprise.orderedEffects.find((operation) => operation.kind === "applyTargetedPower");
  const coreAdds = surprise.orderedEffects.filter((operation) => operation.kind === "coreAddByRef");
  assert.equal(precreate.model, "MONSTER.FAT_GREMLIN");
  assert.equal(targetedPower.power, "POWER.HEIST_POWER");
  assert.equal(targetedPower.model, undefined);
  assert.deepEqual(coreAdds.map((operation) => operation.model ?? operation.body), [
    "MONSTER.SNEAKY_GREMLIN", "exact precreated fatBody",
  ]);

  const surpriseLines = merc.presentation.lifecycle.mechanics
    .find((row) => row.identity === "LIFECYCLE.DEATH_PRODUCTION.SURPRISE").branches[0].effects;
  assert.deepEqual(surpriseLines, [
    "fat body · precreate Fat Gremlin body",
    "runtime accumulator · accumulate runtime gold",
    "exact precreated fat body · apply Heist",
    "owner side · add Sneaky Gremlin body",
    "owner side · add exact precreated fat body",
    "encounter · mark gold stolen",
  ]);

  const ovicopter = encounter("OVICOPTER_NORMAL");
  const hatch = ovicopter.lifecycle.mechanics.phaseSystems
    .find((row) => row.phaseSystemId === "LIFECYCLE.PHASE.TOUGH_EGG_HATCH");
  const skip = hatch.transitions.flatMap((transition) => transition.orderedEffects)
    .find((operation) => operation.kind === "skipPowerApplication");
  assert.equal(skip.power, "POWER.HATCH_POWER");
  assert.match(strings(ovicopter.presentation.lifecycle.mechanics).join(" "), /skip Hatch application/);
});

test("runtime production cardinality references render as explicit clock bounds", () => {
  const livingFog = encounter("LIVING_FOG_NORMAL");
  const producer = livingFog.production.rules.producers
    .find((row) => row.producerId === "PRODUCTION.MONSTER.LIVING_FOG.BLOAT_MOVE");
  assert.deepEqual(producer.activationCardinality.normallyAddedBodies, {
    maximumRef: "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT", minimum: 0,
  });
  assert.deepEqual(producer.activationCardinality.bodyAddAttempts, {
    kind: "runtimeStateValue", runtimeStateRef: "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT",
  });
  const cadence = livingFog.presentation.production.rules
    .find((row) => row.owner === "Living Fog").cadence;
  assert.equal(cadence, "0–runtime living fog bloat amount added bodies per eligible trigger");
  assert.doesNotMatch(cadence, /unknown/i);
});

test("schema-11 lifecycle Power operation field regressions fail closed", () => {
  const fixtures = [
    ["phaseSystems", "LIFECYCLE.PHASE.WATERFALL_GIANT_STEAM_ERUPTION", "removePower"],
    ["phaseSystems", "LIFECYCLE.PHASE.TEST_SUBJECT_ADAPTABLE", "applyPowerByRef"],
    ["phaseSystems", "LIFECYCLE.PHASE.TOUGH_EGG_HATCH", "skipPowerApplication"],
    ["deathProduction", "LIFECYCLE.DEATH_PRODUCTION.SURPRISE", "applyTargetedPower"],
  ];
  for (const [family, identity, kind] of fixtures) {
    const malformed = structuredClone(artifact);
    const row = malformed.payload.sourceFacts.lifecycle.mechanics[family]
      .find((candidate) => candidate.phaseSystemId === identity || candidate.deathProductionId === identity);
    const operation = [...(row.orderedEffects ?? []), ...(row.transitions ?? []).flatMap((transition) => transition.orderedEffects ?? [])]
      .find((candidate) => candidate.kind === kind);
    operation.model = operation.power;
    delete operation.power;
    malformed.metadata.payloadSha256 = adapterInternals.payloadDigest(malformed.payload);
    const failed = createSourceAdapter({ projection: malformed });
    assert.equal(failed.available, false);
    const expectedError = kind === "applyTargetedPower"
      ? /missing lifecycle effect model join POWER\.HEIST_POWER/
      : new RegExp(`${kind} must use the schema power field`);
    assert.match(failed.error, expectedError);
  }
});

test("event and explicit-unknown fixtures retain static effects and named gaps", () => {
  const event = encounter("PUNCH_OFF_EVENT_ENCOUNTER").presentation.event;
  assert.ok(event);
  assert.match(event.behavior, /Normal Turn Machine/);
  assert.equal(event.optionCount, 3);
  assert.equal(event.transitionCount, 1);
  assert.ok(event.effects.some((line) => /offer the constructed reward list/.test(line)));

  const source = structuredClone(encounter("AXEBOTS_NORMAL"));
  source.knownUnknowns.push({
    unknownId: "UNKNOWN.FIXTURE", status: "unresolved", scope: "fixtureRule",
    reasonCode: "runtimeInputMissing", detail: "A checked fixture input remains unavailable", affectedFactIds: [source.factId],
  });
  const projected = buildEncounterPresentation(source);
  assert.equal(projected.unknowns.length, 2);
  assert.match(projected.unknowns[1].headline, /fixture input remains unavailable/);
  assert.match(projected.unknowns[1].detail, /Unresolved.*Fixture Rule.*Runtime Input Missing/);
});

test("every checked presentation remains static and callout fixtures preserve 0, 1, and 3 records", () => {
  const prohibited = /\b(NOW|IN)\b|\b(current|this turn|will)\b/i;
  for (const id of adapter.canonicalIds) {
    const visible = strings(encounter(id).presentation);
    for (const value of visible) assert.doesNotMatch(value, prohibited, `${id}: ${value}`);
  }
  const encounterCandidates = structuredClone(encounter("AXEBOTS_NORMAL"));
  encounterCandidates.callouts = [candidate("FROM_ENCOUNTER", 1)];
  assert.equal(buildEncounterPresentation(encounterCandidates).callouts.all[0].id, "FROM_ENCOUNTER");

  for (const count of [0, 1, 3]) {
    const candidates = Array.from({ length: count }, (_, index) => candidate(`C${index + 1}`, index + 1));
    const collection = compileCalloutCollection(candidates, {}, { collapsedLimit: 1 });
    const projected = buildEncounterPresentation(encounter("AXEBOTS_NORMAL"), { calloutCollection: collection });
    assert.equal(projected.callouts.total, count);
    assert.equal(projected.callouts.all.length, count);
    assert.equal(projected.callouts.collapsedCount, Math.min(count, 1));
    assert.equal(projected.callouts.hasMore, count > 1);
    assert.equal(projected.callouts.expandPathRequired, count > 1);
  }
});

test("presentation-consumed lifecycle identity references fail the strict adapter closed", () => {
  const mutations = [
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.phaseSystems[0].ownerModel = "MONSTER.NOT_CHECKED"; }, /lifecycle owner model join/],
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.relationships[0].source = "MONSTER.NOT_CHECKED"; }, /lifecycle relationship model join/],
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.powerRetentionPolicies[0].power = "POWER.NOT_CHECKED"; }, /lifecycle Power join/],
  ];
  for (const [mutate, error] of mutations) {
    const malformed = structuredClone(artifact); mutate(malformed);
    malformed.metadata.payloadSha256 = adapterInternals.payloadDigest(malformed.payload);
    const failed = createSourceAdapter({ projection: malformed });
    assert.equal(failed.available, false);
    assert.match(failed.error, error);
  }
});

test("source page locks the phone-first hierarchy and horizontal-overflow safeguards", () => {
  const html = httpInternals.sourcePage("/sts2");
  assert.match(html, /name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/);
  assert.match(html, /html,body\{width:100%;max-width:100%;overflow-x:hidden\}/);
  assert.match(html, /\*\{box-sizing:border-box;min-width:0\}/);
  assert.match(html, /\.source-shell\{width:100%;max-width:48rem/);
  assert.match(html, /word-break:break-word/);
  assert.match(html, /summary\{[^}]*min-height:44px/);
  assert.match(html, /summary:focus-visible\{outline:3px/);
  assert.match(html, /@media \(max-width:23rem\)/);
  assert.doesNotMatch(html, /white-space:\s*nowrap|overflow-x:\s*auto/);

  const client = readFileSync(new URL("../src/source-client.js", import.meta.url), "utf8");
  const order = ["renderRoster(root", "renderBodies(root", "renderProduction(root", "renderEvent(root", "renderLifecycle(root", "renderUnknowns(root", "renderCallouts(root", "renderAudit(root"];
  let cursor = -1;
  for (const marker of order) { const next = client.indexOf(marker); assert.ok(next > cursor, marker); cursor = next; }
});
