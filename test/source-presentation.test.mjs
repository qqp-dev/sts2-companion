import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { compileCalloutCollection } from "../src/decision-callouts.mjs";
import { internals as httpInternals } from "../src/http.mjs";
import { createSourceAdapter, internals as adapterInternals } from "../src/source-adapter.mjs";
import { buildEncounterPresentation, conditionText, presentationInternals } from "../src/source-presentation.mjs";

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
    condition: "When the checked condition applies.",
    basis: { factRefs: [`FACT.${id}`], conditionRefs: [`CONDITION.${id}`], causalRefs: [`CAUSE.${id}`] },
  };
}
function strings(value, result = []) {
  if (typeof value === "string") result.push(value);
  else if (Array.isArray(value)) value.forEach((item) => strings(item, result));
  else if (value && typeof value === "object") Object.values(value).forEach((item) => strings(item, result));
  return result;
}
function lifecycleRows(source) {
  return presentationInternals.lifecyclePresentationRecords(source.lifecycle.mechanics ?? {});
}
function lifecycleOperations(source) {
  const result = [];
  for (const { path, row } of lifecycleRows(source)) {
    for (const branch of row.transitions ?? row.branches ?? [row]) {
      const operations = branch.orderedEffects ?? row.orderedEffects ?? row.orderedPerPlayer ?? [];
      operations.forEach((operation, index) => result.push({ path, row, branch, operation, index, operations }));
    }
  }
  return result;
}
function walkConditions(value, visit) {
  if (!value || typeof value !== "object") return;
  visit(value);
  if (Array.isArray(value)) value.forEach((item) => walkConditions(item, visit));
  else Object.values(value).forEach((item) => walkConditions(item, visit));
}

function calloutProjection(count) {
  const collection = compileCalloutCollection(
    Array.from({ length: count }, (_, index) => candidate(`C${index + 1}`, index + 1)),
    {}, { collapsedLimit: 1 },
  );
  return buildEncounterPresentation(encounter("AXEBOTS_NORMAL"), { calloutCollection: collection });
}

test("practical effect signatures are deterministic and exclude move titles and raw IDs", () => {
  assert.equal(adapter.available, true, adapter.error);
  const source = encounter("AXEBOTS_NORMAL");
  assert.deepEqual(buildEncounterPresentation(source), buildEncounterPresentation(source));
  const body = source.presentation.bodies[0];
  assert.equal(body.hp, "76–86 HP · A8 single player");
  assert.match(body.initialEffects[0].line, /apply checked amount Stock/);
  assert.match(body.behavior.headline, /starts at Block \+ Strength.*repeating cycle.*follow-ups/);
  assert.doesNotMatch(body.behavior.headline, /Effect [A-Z]/);
  assert.deepEqual(body.effects[2].orderedEffects.map((row) => row.line), [
    "all opponents · checked amount damage",
    "the affected targets · apply 2 Weak",
    "the affected targets · apply 2 Frail",
  ]);
  const collapsed = JSON.stringify(body);
  for (const raw of ["BOOT_UP_MOVE", "HAMMER_UPPERCUT_MOVE", "Boot Up", "Hammer Uppercut", "MONSTER.AXEBOT", "formula"])
    assert.ok(!collapsed.includes(raw), raw);
  assert.equal(source.monsters[0].moves[0].title.text, "Boot Up", "exact title remains in audit data");
});

test("roster alternatives and produced bodies never become a co-presence claim", () => {
  const branching = encounter("BOWLBUGS_NORMAL").presentation;
  assert.equal(branching.roster.cardinality, "3");
  assert.match(branching.roster.summary, /2 random distinct bodies.*Egg.*Silk.*Nectar.*without replacement/);
  assert.match(branching.roster.caveat, /not all co-present/);
  const segments = encounter("DECIMILLIPEDE_ELITE").presentation;
  assert.equal(segments.roster.summary, "3× Decimillipede");
  assert.equal(segments.bodies.length, 3);
  const production = encounter("FABRICATOR_NORMAL").presentation.production;
  assert.match(production.caveat, /not initial or co-present bodies/);
  assert.deepEqual(production.possibilities, ["Guardbot", "Noisebot", "Stabbot", "Zapbot"]);
});

test("briefing compiler prioritizes and compresses without losing disclosure reachability", () => {
  for (const id of adapter.canonicalIds) {
    const presentation = encounter(id).presentation;
    assert.match(presentation.briefing.fightShape, /\S/, `${id}: fight shape`);
    assert.ok(presentation.briefing.highlights.length >= 1 && presentation.briefing.highlights.length <= 3, `${id}: bounded highlights`);
    assert.ok(presentation.bodies.every((body) => body.keyMechanics.length <= 2), `${id}: compact enemy mechanics`);

    const refs = presentation.briefing.reachability.map((row) => row.detailRef);
    assert.equal(new Set(refs).size, refs.length, `${id}: stable unique disclosure refs`);
    const expected = [
      presentation.roster.detailRef,
      ...presentation.bodies.map((body) => body.detailRef),
      ...(presentation.production ? [presentation.production.detailRef] : []),
      ...(presentation.event ? ["event-consequences"] : []),
      ...(presentation.lifecycle.rules.length || presentation.lifecycle.mechanics.length ? ["lifecycle-overview"] : []),
      ...presentation.lifecycle.mechanics.map((mechanic) => mechanic.detailRef),
      "limitations", "technical-audit",
    ];
    assert.deepEqual([...refs].sort(), [...expected].sort(), `${id}: every retained family has a disclosure target`);
    for (const highlight of presentation.briefing.highlights) {
      assert.match(highlight.headline, /\S/, `${id}: highlight headline`);
      assert.match(highlight.effect, /\S/, `${id}: highlight effect`);
      assert.ok(highlight.effect.length <= 160, `${id}: compressed highlight effect line`);
      assert.ok(refs.includes(highlight.detailRef), `${id}: highlight reaches detail`);
    }
  }
});

test("briefing selection is mechanic-salient rather than a move-list prefix", () => {
  const axebot = encounter("AXEBOTS_NORMAL").presentation.briefing;
  assert.deepEqual(axebot.highlights.slice(0, 2).map((row) => row.headline), ["On-death production", "Death and Power retention"]);
  const bowlbugs = encounter("BOWLBUGS_NORMAL").presentation.briefing;
  assert.match(bowlbugs.lineupCondition, /not all co-present/);
  assert.ok(bowlbugs.highlights.every((row) => row.kind !== "lineup"));
  assert.ok(bowlbugs.highlights.every((row) => row.effect !== encounter("BOWLBUGS_NORMAL").presentation.roster.summary));
  const fabricator = encounter("FABRICATOR_NORMAL").presentation.briefing;
  assert.equal(fabricator.highlights[0].headline, "Bodies can be added");
  const testSubject = encounter("TEST_SUBJECT_BOSS").presentation.briefing;
  assert.equal(testSubject.highlights[0].headline, "Phases, revive and hatch");
  const event = encounter("DENSE_VEGETATION_EVENT_ENCOUNTER").presentation.briefing;
  assert.equal(event.highlights[0].headline, "Event-fight consequences");
  const battleworn = encounter("BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER").presentation.briefing.highlights[0];
  assert.equal(battleworn.headline, "Event fight clock");
  assert.match(battleworn.effect, /escape and leave the fight/);
  assert.doesNotMatch(battleworn.effect, /^this event fight · record/);
  assert.match(battleworn.condition, /Power amount ≤ 1/);
  const ovicopter = encounter("OVICOPTER_NORMAL").presentation.briefing.highlights[0];
  assert.equal(ovicopter.headline, "Phases, revive and hatch");
  assert.match(ovicopter.effect, /hatch with 19–22 HP below A8; 20–23 HP at A8\+/);
  const linkedQueen = encounter("QUEEN_BOSS").presentation.briefing.highlights.find((row) => row.headline === "Linked bodies");
  assert.match(linkedQueen.effect, /enter the enraged behavior/);
  assert.doesNotMatch(linkedQueen.effect, /^the same Queen · record/);
});

test("briefing and compact cards share absolute combat-signature priority", () => {
  const presentation = encounter("CONSTRUCT_MENAGERIE_NORMAL").presentation;
  const expected = [
    ["Cubex Construct", "Strength + Counter or state shift"],
    ["Punch Construct", "Damage + Multi-hit + Frail"],
  ];
  for (const [bodyName, mechanicHeadline] of expected) {
    const body = presentation.bodies.find((row) => row.name === bodyName);
    const compact = body.keyMechanics.find((row) => row.headline === mechanicHeadline);
    assert.ok(compact, `${bodyName}: decision-relevant mechanic is selected on its compact card`);
    const briefing = presentation.briefing.highlights.find(
      (row) => row.headline === `${bodyName} · ${mechanicHeadline}`,
    );
    assert.ok(briefing, `${bodyName}: decision-relevant mechanic outranks routine opening setup`);
    assert.equal(briefing.effect, compact.effect, `${bodyName}: briefing and compact card use one signature`);
  }
  assert.ok(presentation.briefing.highlights.some((row) => row.kind === "signature"));
  assert.notDeepEqual(
    presentation.briefing.highlights.map((row) => row.effect),
    ["self · apply 1 Artifact", "self · apply 1 Artifact", "self · gain 13 Block"],
  );
});

test("event briefing presents checked branch outcomes as alternatives, never an execution trace", () => {
  for (const id of ["DENSE_VEGETATION_EVENT_ENCOUNTER", "PUNCH_OFF_EVENT_ENCOUNTER"]) {
    const presentation = encounter(id).presentation;
    const event = presentation.briefing.highlights.find((row) => row.kind === "event");
    assert.ok(event, `${id}: event consequences remain prominent`);
    assert.match(event.effect, / · or · /, `${id}: alternatives use non-ordering language`);
    assert.match(event.effect, /\+1 possible outcome in details$/, `${id}: hidden branch is named as an outcome`);
    assert.doesNotMatch(event.effect, /→|ordered effects?/, `${id}: no predicted ordered trace`);
    assert.equal(presentation.event.effects.length, 3, `${id}: every checked event outcome remains reachable`);
  }
});

test("compact effect lines rank player-visible mechanics above setup writes", () => {
  const cubex = encounter("CUBEX_CONSTRUCT_NORMAL").presentation;
  const cubexStrength = cubex.briefing.highlights.find((row) => row.headline.includes("Strength + Counter"));
  assert.match(cubexStrength.effect, /^self · apply 2 Strength;/);
  assert.match(cubexStrength.effect, /update this behavior's checked counter or state/);
  assert.equal(cubex.bodies[0].keyMechanics[0].effect, cubexStrength.effect);

  const tunneler = encounter("TUNNELER_WEAK").presentation.briefing.highlights
    .find((row) => row.headline.includes("Burrowed + Block"));
  assert.match(tunneler.effect, /^self · apply 1 Burrowed; self · gain checked amount Block/);
  assert.match(tunneler.effect, /\+1 ordered effect in details$/);

  const hopper = encounter("THIEVING_HOPPER_WEAK").presentation.briefing.highlights
    .find((row) => row.headline.includes("Escape + Counter"));
  assert.match(hopper.effect, /^self · escape through the checked fight rule;/);

  const forms = encounter("TEST_SUBJECT_BOSS").presentation.briefing.highlights
    .find((row) => row.kind === "forms");
  assert.match(forms.effect, /Phase 3 · 300 HP below A8; 313 HP at A8\+$/);
  assert.doesNotMatch(forms.effect, /ordered effect/);
  assert.equal(
    presentationInternals.compactSequence(["A", "B", "C", "D"], 2, { remainderLabel: "possible form" }),
    "A → B · +2 possible forms in details",
  );
});

test("runtime modifier gaps remain unresolved observations rather than conditions", () => {
  for (const id of ["BOWLBUGS_NORMAL", "CUBEX_CONSTRUCT_NORMAL"]) {
    const presentation = encounter(id).presentation;
    const highlight = presentation.briefing.highlights.find((row) => row.kind === "opening" && row.unresolved);
    assert.ok(highlight, `${id}: unresolved opening remains visible`);
    assert.equal(highlight.condition, null, `${id}: unresolved input is not a trigger`);
    assert.match(highlight.unresolved, /^1 runtime modifier input remains unresolved$/);
    if (id === "BOWLBUGS_NORMAL") {
      const compact = presentation.bodies.flatMap((body) => body.keyMechanics).find((row) => row.unresolved);
      assert.ok(compact, `${id}: selected compact opening retains the unresolved input`);
      assert.equal(compact.condition, null);
    }
  }
});

test("compact enemy mechanics deduplicate setup and reserve slots for salient combat signatures", () => {
  const segments = encounter("DECIMILLIPEDE_ELITE").presentation.bodies;
  const repeatedOpenings = segments[0].initialEffects
    .filter((fact) => fact.primaryEligible && fact.line === "self · apply 25 Reattach")
    .map((fact) => fact.line);
  assert.ok(repeatedOpenings.length >= 2);
  assert.equal(new Set(repeatedOpenings).size, 1, "fixture contains the duplicate opening that previously filled both slots");
  for (const segment of segments) {
    assert.ok(segment.keyMechanics.filter((row) => row.headline.includes("Opening setup")).length <= 1);
    assert.ok(segment.keyMechanics.some((row) => row.headline === "Revive"));
    const distinct = new Set(segment.keyMechanics.map((row) => JSON.stringify([row.headline, row.effect, row.condition, row.unresolved])));
    assert.equal(distinct.size, segment.keyMechanics.length);
  }
  const subject = encounter("TEST_SUBJECT_BOSS").presentation.bodies[0].keyMechanics;
  assert.ok(subject.some((row) => row.headline === "Burn cards + Strength"));
  assert.ok(subject.some((row) => row.headline.includes("Adaptable removal")));
  assert.ok(subject.every((row) => !row.headline.includes("Opening setup")));
});

test("representative briefing hierarchy matches the reviewed golden fixture", () => {
  const golden = JSON.parse(readFileSync(new URL("./fixtures/briefing-golden.json", import.meta.url), "utf8"));
  const actual = {};
  for (const id of Object.keys(golden)) {
    const source = encounter(id), presentation = source.presentation;
    actual[id] = {
      title: source.title,
      fightShape: presentation.briefing.fightShape,
      lineupCondition: presentation.briefing.lineupCondition,
      highlights: presentation.briefing.highlights,
      enemies: presentation.bodies.map((body) => ({
        name: body.name, hp: body.hp,
        forms: body.forms.map((form) => ({ name: form.name, hp: form.hp })),
        keyMechanics: body.keyMechanics,
      })),
    };
  }
  assert.deepEqual(actual, golden);
});

test("all primary and compact surfaces remain static, conditional, and effect-signature based", () => {
  const unsupportedLive = /\b(?:now|current HP|current intent|this turn|will attack|you should|do this now|survivors? (?:are|is))\b/i;
  const rawIdentity = /\b(?:MONSTER|POWER|CARD|ENCOUNTER|SOURCE|RUNTIME)\.|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/;
  for (const id of adapter.canonicalIds) {
    const presentation = encounter(id).presentation;
    const primary = strings({ briefing: presentation.briefing, compact: presentation.bodies.map((body) => ({
      name: body.name, role: body.role, hp: body.hp, forms: body.forms, keyMechanics: body.keyMechanics,
    })) }).join("\n");
    assert.doesNotMatch(primary, unsupportedLive, id);
    assert.doesNotMatch(primary, rawIdentity, id);
    assert.doesNotMatch(primary, /\bEffect [A-Z]\b/, id);
    assert.doesNotMatch(primary, /\b(?:formula|AST|graph)\b/i, id);
    assert.doesNotMatch(primary, /set (?:encounter state|initial behavior state)|listen for the checked fight trigger|configure .* target/i, id);
  }
});

test("projection-wide target census has deliberate side, plurality, and iterator semantics", () => {
  const used = new Set();
  for (const id of adapter.canonicalIds) {
    const source = encounter(id);
    for (const body of source.monsters) {
      for (const fact of body.initialState) used.add(fact.recipient.kind);
      for (const move of body.moves) for (const operation of move.operations) if (operation.target) used.add(operation.target);
    }
    for (const { operation } of lifecycleOperations(source)) if (operation.target) used.add(operation.target);
  }
  assert.deepEqual([...used].sort(), Object.keys(presentationInternals.TARGETS).sort());
  for (const target of used) {
    const rendered = presentationInternals.targetText(target);
    assert.notEqual(rendered, "recipient unresolved", target);
    assert.notEqual(rendered, target, target);
    assert.doesNotMatch(rendered, /[a-z][A-Z]/, target);
  }
  assert.equal(presentationInternals.targetText("futureUncheckedTarget"), "recipient unresolved");

  const obscura = strings(encounter("THE_OBSCURA_NORMAL").presentation.bodies).join(" ");
  assert.match(obscura, /teammates · apply 3 Strength/);
  const kaiser = strings(encounter("KAISER_CRAB_BOSS").presentation.bodies).join(" ");
  assert.match(kaiser, /opponent side/);
  for (const id of ["QUEEN_BOSS", "FABRICATOR_NORMAL", "KNIGHTS_ELITE"])
    assert.match(strings(encounter(id).presentation.bodies).join(" "), /each selected creature/, id);
});

test("every checked boolean condition has grammatical positive and negative semantics", () => {
  const used = new Set();
  for (const id of adapter.canonicalIds) {
    const source = encounter(id);
    const conditions = [];
    for (const body of source.monsters) for (const fact of body.initialState) conditions.push(fact.condition);
    for (const { row, branch } of lifecycleOperations(source)) conditions.push(branch.condition ?? row.condition);
    for (const { row } of lifecycleRows(source)) conditions.push(row.condition);
    for (const condition of conditions) walkConditions(condition, (value) => {
      if ((value.kind === "comparison" || value.kind === "compare")
          && value.left?.kind === "runtimeInput" && value.right?.kind === "constant"
          && typeof value.right.value === "boolean") used.add(value.left.name);
    });
  }
  assert.deepEqual([...used].sort(), Object.keys(presentationInternals.BOOLEAN_CONDITIONS).sort());
  for (const key of used) {
    const [positive, negative] = presentationInternals.BOOLEAN_CONDITIONS[key];
    assert.ok(positive && negative, key);
    assert.doesNotMatch(negative, /^not\b/i, key);
  }
  const kin = strings(encounter("THE_KIN_BOSS").presentation.lifecycle).join(" ");
  assert.match(kin, /no follower on the same side is alive/);
  assert.doesNotMatch(kin, /not a follower on the same side is alive/);
  assert.equal(conditionText({ kind: "comparison", left: { kind: "runtimeInput", name: "new.boolean", valueType: "boolean" }, operator: "equal", right: { kind: "constant", value: false, valueType: "boolean" } }), "the checked runtime condition is resolved");
});

test("lifecycle writes and retention policies are semantic in guide and exact in audit", () => {
  const writes = new Set(), hooks = new Set();
  for (const id of adapter.canonicalIds) {
    const source = encounter(id);
    lifecycleOperations(source).forEach(({ operation }) => {
      if (operation.kind === "writeState") writes.add(`${operation.field}:${String(operation.value)}`);
    });
    lifecycleRows(source).forEach(({ row }) => { if (row.hook) hooks.add(row.hook); });
  }
  assert.deepEqual([...writes].sort(), Object.keys(presentationInternals.LIFECYCLE_WRITES).sort());
  assert.deepEqual([...hooks].sort(), [
    "ShouldCreatureBeRemovedFromCombatAfterDeath", "ShouldOwnerDeathTriggerFatal",
    "ShouldPowerBeRemovedAfterOwnerDeath", "ShouldPowerBeRemovedOnDeath", "ShouldStopCombatFromEnding",
  ]);
  const collapsed = adapter.canonicalIds.flatMap((id) => strings(encounter(id).presentation)).join("\n");
  for (const raw of [...writes].map((value) => value.split(":")[0]).concat([...hooks])) assert.ok(!collapsed.includes(raw), raw);
  assert.doesNotMatch(collapsed, /\b\w+\s*=\s*(?:true|false)\b/i);
  assert.match(collapsed, /record that the Amalgam has died/);
  assert.match(collapsed, /Illusion is removed when its owner dies/);
  assert.match(collapsed, /owner death triggers fatal handling for Reattach/);
  assert.ok(JSON.stringify(encounter("QUEEN_BOSS").lifecycle).includes("HasAmalgamDied"));
  assert.ok(JSON.stringify(encounter("DECIMILLIPEDE_ELITE").lifecycle).includes("ShouldOwnerDeathTriggerFatal"));
});

test("lifecycle attack census distinguishes snapshots, move references, and unresolved amounts", () => {
  const attacks = [];
  for (const id of adapter.canonicalIds) for (const row of lifecycleOperations(encounter(id))) {
    if (row.operation.kind === "attack") attacks.push({ id, ...row });
  }
  assert.deepEqual(attacks.map(({ id, operation }) => [id, operation.amountRef ?? null, operation.sourceRef ?? null]), [
    ["LIVING_FOG_NORMAL", null, "behavior.operations.attack"],
    ["WATERFALL_GIANT_BOSS", "snapshotted Steam amount", null],
  ]);
  const fog = strings(encounter("LIVING_FOG_NORMAL").presentation.lifecycle).join(" ");
  assert.match(fog, /perform Gas Bomb's checked attack/);
  assert.doesNotMatch(fog, /captured|snapshotted/);
  const steam = strings(encounter("WATERFALL_GIANT_BOSS").presentation.lifecycle).join(" ");
  assert.match(steam, /remember Steam Eruption's amount at that trigger/);
  assert.match(steam, /deal the snapshotted Steam Eruption amount/);
  const unresolved = presentationInternals.lifecycleEffect({ kind: "attack", target: "players" }, new Map(), [], 0);
  assert.match(unresolved, /damage amount is defined by that attack/);
  assert.doesNotMatch(unresolved, /captured|snapshotted/);
});

test("all checked event effect kinds have deliberate practical consequences", () => {
  const kinds = new Set();
  for (const id of adapter.canonicalIds) for (const row of encounter(id).event?.scripts?.effects ?? []) {
    kinds.add(row.kind);
    assert.ok(presentationInternals.eventEffect(row), `${id}: ${row.kind}`);
  }
  assert.deepEqual([...kinds].sort(), [...presentationInternals.EVENT_EFFECT_KINDS].sort());
  assert.equal(presentationInternals.eventEffect({ kind: "futureStructuralEffect" }), null);
  const dense = strings(encounter("DENSE_VEGETATION_EVENT_ENCOUNTER").presentation.event).join(" ");
  assert.match(dense, /rest-site amount/);
  assert.match(dense, /HP-loss amount/);
  assert.match(dense, /gain the event's checked gold amount/);
  const punch = strings(encounter("PUNCH_OFF_EVENT_ENCOUNTER").presentation.event).join(" ");
  assert.match(punch, /Injury curse/);
  assert.match(punch, /construct a relic reward/);
  assert.match(punch, /offer the constructed reward list/);
});

test("representative clocks, revive, hatch, production, and phase rules remain practical", () => {
  const battleworn = strings(encounter("BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER").presentation.lifecycle).join(" ");
  assert.match(battleworn, /Event fight clock/);
  assert.match(battleworn, /Power amount > 1/);
  assert.match(battleworn, /record that the event fight ran out of time/);
  assert.match(battleworn, /escape and leave the fight/);
  const subject = strings(encounter("TEST_SUBJECT_BOSS").presentation.lifecycle).join(" ");
  assert.match(subject, /completed respawns = 1/);
  assert.match(subject, /record another Test Subject death/);
  assert.match(subject, /Adaptable revival/);
  const hatch = strings(encounter("OVICOPTER_NORMAL").presentation.lifecycle).join(" ");
  assert.match(hatch, /reduce Hatch by 1/);
  assert.match(hatch, /hatch with 19–22 HP below A8; 20–23 HP at A8\+/);
  const eggForms = encounter("OVICOPTER_NORMAL").presentation.bodies.find((body) => body.name === "Tough Egg").forms;
  assert.deepEqual(eggForms.map((form) => form.hp), ["15–19 HP · A8 single player", "19–22 HP below A8; 20–23 HP at A8+"]);
  const subjectForms = encounter("TEST_SUBJECT_BOSS").presentation.bodies[0].forms;
  assert.deepEqual(subjectForms.map((form) => [form.name, form.hp]), [
    ["Phase 1 — Test Subject (runtime number)", "111 HP · A8 single player"],
    ["Phase 2 — Test Subject (runtime number)", "200 HP below A8; 212 HP at A8+"],
    ["Phase 3 — Test Subject (runtime number)", "300 HP below A8; 313 HP at A8+"],
  ]);
  const livingFog = encounter("LIVING_FOG_NORMAL").presentation.production;
  assert.equal(livingFog.rules[0].cadence, "0–Bloat's runtime summon count added bodies per eligible trigger");
});

test("all 105 checked collapsed presentations reject source-identifier leakage", () => {
  const rawLifecycle = /Should(?:Power|Owner|Creature)|HasAmalgamDied|isReviving|RanOutOfTime|IsHatched|_hatched/;
  const rawIdentity = /\b(?:MONSTER|POWER|CARD|ENCOUNTER|SOURCE|RUNTIME)\.|\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/;
  const sourceDump = /\b(?:formula|AST|graph)\b/i;
  for (const id of adapter.canonicalIds) {
    const visible = strings(encounter(id).presentation).join("\n");
    assert.doesNotMatch(visible, rawIdentity, id);
    assert.doesNotMatch(visible, rawLifecycle, id);
    assert.doesNotMatch(visible, sourceDump, id);
    assert.doesNotMatch(visible, /\b(?:current HP|current intent|survivors are|you should|do this now)\b/i, id);
  }
});

test("callout contract preserves honest 0, 1, and 3 internal collections", () => {
  for (const count of [0, 1, 3]) {
    const projected = calloutProjection(count);
    assert.equal(projected.callouts.total, count);
    assert.equal(projected.callouts.all.length, count);
    assert.equal(projected.callouts.collapsedCount, Math.min(count, 1));
    assert.equal(projected.callouts.hasMore, count > 1);
  }
});

test("presentation-consumed lifecycle identity references still fail the adapter closed", () => {
  const mutations = [
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.phaseSystems[0].ownerModel = "MONSTER.NOT_CHECKED"; }, /lifecycle owner model join/],
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.relationships[0].source = "MONSTER.NOT_CHECKED"; }, /lifecycle relationship model join/],
    [(value) => { value.payload.sourceFacts.lifecycle.mechanics.powerRetentionPolicies[0].power = "POWER.NOT_CHECKED"; }, /lifecycle Power join/],
  ];
  for (const [mutate, expected] of mutations) {
    const malformed = structuredClone(artifact);
    mutate(malformed);
    malformed.metadata.payloadSha256 = adapterInternals.payloadDigest(malformed.payload);
    const failed = createSourceAdapter({ projection: malformed });
    assert.equal(failed.available, false);
    assert.match(failed.error, expected);
  }
});

test("one guide page has explicit local qq-like tokens and narrow accessibility safeguards", () => {
  const html = httpInternals.guidePage("/sts2");
  assert.match(html, /name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/);
  const httpSource = readFileSync(new URL("../src/http.mjs", import.meta.url), "utf8");
  assert.match(httpSource, /Local qq-like compatibility tokens/);
  assert.match(httpSource, /qq-ui does not publish a shared token contract/);
  for (const characteristic of [
    '--qq-bg:#000', '--qq-surface:#0a0a0a', '--qq-text:#e8e8e8', '--qq-muted:#8a8a8a',
    '--qq-line:#1a1a1a', 'font-family:"Geist UI",Geist,ui-sans-serif,system-ui',
    'min-height:3.5rem', 'summary:focus-visible{outline:2px solid var(--qq-focus)',
    '@media(prefers-reduced-motion:reduce)', 'overflow-x:hidden', 'word-break:break-word',
  ]) assert.ok(html.includes(characteristic), characteristic);
  assert.doesNotMatch(html, /white-space:\s*nowrap|overflow-x:\s*auto/);
  const client = readFileSync(new URL("../src/client.js", import.meta.url), "utf8");
  assert.doesNotMatch(client, /\x08/, "regexes contain no literal backspace characters");
  assert.match(client, /\/\\b\(\?:formula\|AST\)\\b/);
  const order = ["renderBriefing(root", "renderCallouts(root", "renderCompactBodies(root", "renderFightDetails(root", "renderAudit(root"];
  let cursor = -1;
  for (const marker of order) { const next = client.indexOf(marker); assert.ok(next > cursor, marker); cursor = next; }
  assert.doesNotMatch(client, /renderRoster\(root|What is not observed|Checked editorial callouts/);
  assert.match(client, /Fight details/);
  assert.match(client, /What changes the fight/);
  assert.match(client, /Static guide · encounter identity only, not a live turn/);
});
