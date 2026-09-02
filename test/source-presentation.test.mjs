import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { compileCalloutCollection } from "../src/decision-callouts.mjs";
import { internals as httpInternals } from "../src/http.mjs";
import { createSourceAdapter, internals as adapterInternals } from "../src/source-adapter.mjs";
import { buildEncounterPresentation, conditionText, presentationInternals } from "../src/source-presentation.mjs";

const artifact = JSON.parse(readFileSync(new URL("../data/encounter-facts-v0.111.0.json", import.meta.url), "utf8"));
const p0aFixtures = JSON.parse(readFileSync(new URL("./fixtures/p0a-guides.json", import.meta.url), "utf8"));
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

test("retained bodies resolve by unique exact keys within their canonical encounter", () => {
  const ruby = encounter("RUBY_RAIDERS_NORMAL");
  const assassinReference = ruby.reference.record.lineup.find((body) => body.displayName === "Assassin Raider");
  const assassinSource = ruby.monsters.find((body) => body.canonicalModel === "MONSTER.ASSASSIN_RUBY_RAIDER");
  assert.ok(assassinReference);
  assert.ok(assassinSource);
  assert.equal(presentationInternals.exactSourceBody(ruby, assassinReference), assassinSource,
    "a unique exact display name joins when the retained monster ID differs");

  assert.equal(presentationInternals.exactSourceBody(ruby, { ...assassinReference, displayName: "assassin raider" }), null,
    "display-name keys remain exact and case-sensitive");
  const duplicateName = structuredClone(assassinSource);
  duplicateName.canonicalModel = "MONSTER.OTHER_ASSASSIN";
  assert.equal(presentationInternals.exactSourceBody(
    { ...ruby, monsters: [...ruby.monsters, duplicateName] }, assassinReference,
  ), null, "an ambiguous display name does not create a join");

  const canonicalSource = { ...structuredClone(assassinSource), canonicalModel: "MONSTER.ASSASSIN_RAIDER" };
  canonicalSource.name = { kind: "localizedText", text: "Different localized name" };
  assert.equal(presentationInternals.exactSourceBody(
    { ...ruby, monsters: [canonicalSource, assassinSource] }, assassinReference,
  ), canonicalSource, "the canonical monster ID remains the primary exact key");
});

test("practical effect signatures are deterministic and exclude move titles and raw IDs", () => {
  assert.equal(adapter.available, true, adapter.error);
  const source = encounter("AXEBOTS_NORMAL");
  assert.deepEqual(buildEncounterPresentation(source), buildEncounterPresentation(source));
  const body = source.presentation.bodies[0];
  assert.equal(body.hp, "76–86 HP · A8 single player");
  assert.match(body.initialEffects[0].line, /Stock amount unresolved/);
  assert.match(body.initialEffects[0].unresolved, /enemy-definition amount.*runtime Power modifiers/);
  assert.match(body.behavior.headline, /opens with sequence 1 \/ sequence 3.*repeating cycle.*follow-ups/);
  assert.deepEqual(body.effects[2].orderedEffects.map((row) => row.line), [
    "all opponents · damage amount unresolved for this behavior",
    "the affected targets · Weak 2",
    "the affected targets · Frail 2",
  ]);
  const collapsed = JSON.stringify(body);
  for (const raw of ["checked amount", "Effect A", "Effect B", "Effect C", "BOOT_UP_MOVE", "HAMMER_UPPERCUT_MOVE", "Boot Up", "Hammer Uppercut", "MONSTER.AXEBOT", "formula"])
    assert.ok(!collapsed.includes(raw), raw);
  assert.equal(source.monsters[0].moves[0].title.text, "Boot Up", "exact title remains in audit data");
});

test("Ceremonial Beast consequence-first guide keeps exact canonical source audit", () => {
  const beast = encounter("CEREMONIAL_BEAST_BOSS");
  const primary = beast.presentation.primary;
  assert.equal(primary.header.stats, "576 HP · BOSS");
  assert.equal(primary.header.placement, "Overgrowth");
  assert.deepEqual(primary.bodies[0].sections.map((section) => [section.number, section.title]), [
    ["01", "Force the stun"], ["02", "Three-turn loop"],
  ]);
  const scan = strings(primary).join(" ");
  for (const expected of [
    "First turn", "No attack", "Then each turn", "20 damage", "+2 Strength", "At 352 HP or below",
    "Immediately Stunned", "loses all Strength", "takes no action", "Apply 1 Ringing", "17 damage",
    "19 damage", "+4 Strength", "repeat 1 → 2 → 3",
  ]) assert.match(scan, new RegExp(expected.replace(/[+]/g, "\\+"), "i"), expected);
  for (const forbidden of ["Stamp", "Break the Plow", "Gain 352 Plow", "Beast Cry", "Stomp", "Crush"])
    assert.doesNotMatch(scan, new RegExp(forbidden, "i"), forbidden);
  assert.match(primary.provenance.label, /wiki\/reference values · A9 \/ 2P presentation/);
  assert.deepEqual(Object.keys(primary.provenance), ["label"]);
  assert.doesNotMatch(scan, /unresolved|Death removal|Fight completion|all enemies escape/i);

  const audit = JSON.stringify(beast);
  for (const retained of ["Stamp", "Plow", "Beast Cry", "Stomp", "Crush", "PlowPower", "get_PlowAmount"])
    assert.match(audit, new RegExp(retained), retained);
  assert.match(audit, /"kind":"reference"/);
  assert.match(audit, /rawSource/);
  assert.ok(beast.presentation.audit.mergeProvenance.values.some((row) => row.authority === "wiki-reference"));
});

test("pattern projection preserves actor identities and tracked timers while suppressing action citations", () => {
  const eel = encounter("TERROR_EEL_ELITE");
  const eelSection = eel.presentation.primary.bodies[0].sections[0];
  assert.equal(eel.presentation.primary.bodies[0].name, "Terror Eel");
  assert.deepEqual(eelSection.rows.map((row) => row.detail), ["18 damage", "4×3 damage · +6 Vigor"]);
  assert.equal(eelSection.marker.label, "At Terror Eel's Shriek threshold · 165 HP");
  assert.equal(eelSection.marker.detail, "Immediately Stunned · takes no action → Apply 99 Vulnerable → resume at step 1");
  assert.doesNotMatch(JSON.stringify(eel.presentation.primary), /between Crash and Thrash|uses Terror|• Terror applies|\(75\)/);
  assert.match(JSON.stringify(eel.reference), /Crash|Thrash|Terror/);

  const ovicopter = encounter("OVICOPTER_NORMAL");
  const egg = ovicopter.presentation.primary.bodies.find((body) => body.name === "Tough Egg");
  const eggPattern = egg.sections[0].note;
  assert.match(eggPattern, /its Hatch timer counts down/);
  assert.match(eggPattern, /uses step 1 to transform into a Hatchling/);
  assert.doesNotMatch(eggPattern, /step 1 timer|uses Hatch to transform/);
  assert.match(JSON.stringify(ovicopter.reference), /"name":"Hatch"/);
});

test("Axebot and Terror Eel one- and two-player practical fixtures remain exact", () => {
  for (const players of [1, 2]) {
    const configured = createSourceAdapter({ projection: artifact, players });
    assert.equal(configured.available, true, configured.error);
    for (const id of ["AXEBOTS_NORMAL", "TERROR_EEL_ELITE"]) {
      const selected = configured.view(idle, id).encounter;
      assert.deepEqual(selected.presentation.primary, p0aFixtures[`${players}P`][id], `${id} ${players}P fixture`);
      const practical = JSON.stringify(selected.presentation.primary);
      const audit = JSON.stringify(selected);
      if (id === "AXEBOTS_NORMAL") {
        const [, cycle, replacement] = selected.presentation.primary.bodies[0].sections;
        assert.deepEqual(cycle.rows.map((row) => row.detail), ["11×2 damage", "18 damage · 2 Weak and 2 Frail"]);
        assert.deepEqual(replacement.rows.slice(0, 2).map((row) => row.detail), [
          "15 Block · +4 Strength · +10 Max HP cumulative",
          "15 Block · +8 Strength · +20 Max HP cumulative",
        ]);
        assert.doesNotMatch(JSON.stringify(cycle), /Block|Strength|replacement/i);
        assert.doesNotMatch(practical, /Boot Up|The One-Two|Hammer Uppercut|\+24|30 Block/);
        assert.match(audit, /Boot Up|The One-Two|Hammer Uppercut|BOOT_UP_MOVE/);
      } else {
        const section = selected.presentation.primary.bodies[0].sections[0];
        const threshold = players === 1 ? 75 : 165;
        const opposite = players === 1 ? 165 : 75;
        assert.equal(section.marker.label, `At Terror Eel's Shriek threshold · ${threshold} HP`);
        assert.equal((JSON.stringify(section).match(/Shriek threshold/g) ?? []).length, 1);
        assert.doesNotMatch(JSON.stringify(section), new RegExp(`threshold[^.]*\\b${opposite}\\b`, "i"));
        assert.doesNotMatch(practical, /Crash|Thrash|Terrorize|uses Terror|\(75\)/);
        assert.match(audit, /\"name\":\"Terror\"/);
        assert.match(audit, /Terrorize|TERROR_MOVE/);
      }
    }
  }
});

test("focused sequence compilers fail closed instead of restoring a generic all-move cycle", () => {
  for (const [id, from, to] of [
    ["AXEBOTS_NORMAL", "GRAPH.AXEBOT/BOOT_UP_MOVE", "GRAPH.AXEBOT/ONE_TWO_MOVE"],
    ["TERROR_EEL_ELITE", "GRAPH.TERROR_EEL/STUN_MOVE", "GRAPH.TERROR_EEL/CRASH_MOVE"],
  ]) {
    const changed = structuredClone(encounter(id));
    const edge = changed.monsters[0].graph.edges.find((row) => row.from === from);
    assert.ok(edge); edge.to = to;
    const reference = changed.reference.record;
    const projected = buildEncounterPresentation(changed, {
      reference,
      scaling: { players: 2, act: reference.actNumber, kind: reference.kind },
      referenceMeta: reference.configuration,
    });
    assert.deepEqual(projected.primary.bodies[0].sections, [], `${id} must not use generic fallback`);
  }
});

test("best-available merge obeys one- and two-player threshold scaling and exact-only fallback boundaries", () => {
  const singlePlayer = createSourceAdapter({ projection: artifact, players: 1 });
  assert.equal(singlePlayer.available, true, singlePlayer.error);
  const beast = singlePlayer.view(idle, "CEREMONIAL_BEAST_BOSS").encounter;
  const primary = beast.presentation.primary;
  assert.equal(primary.header.stats, "288 HP · BOSS");
  assert.match(strings(primary).join(" "), /At 160 HP or below/);
  assert.doesNotMatch(strings(primary).join(" "), /Plow 160|Plow 176/);
  assert.match(strings(primary).join(" "), /20 damage/);
  assert.equal(primary.provenance.label, "wiki/reference values · A9 / 1P presentation");
  assert.equal(beast.presentation.audit.mergeProvenance.values[0].presentedValue, "Plow 160");

  for (const players of [0, 1.5, 5, "many"])
    assert.match(createSourceAdapter({ projection: artifact, players }).error, /configured players/);

  const sourceOnly = encounter("BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER");
  assert.equal(sourceOnly.reference, null);
  assert.ok(sourceOnly.presentation.primary);
  assert.equal(sourceOnly.presentation.primary.provenance.authority, "checked-source-only");
  assert.equal(sourceOnly.presentation.audit.mergeProvenance, null);
});

test("a closed checked source disagreement wins visibly while both values remain auditable", () => {
  const changed = structuredClone(artifact);
  const ringing = changed.payload.sourceFacts.moves.find((move) => move.canonicalId === "MONSTER.CEREMONIAL_BEAST#BEAST_CRY_MOVE");
  assert.ok(ringing);
  ringing.operations.find((operation) => operation.kind === "applyPower").value = { kind: "constant", value: "2", valueType: "decimal" };
  changed.metadata.payloadSha256 = adapterInternals.payloadDigest(changed.payload);
  const changedAdapter = createSourceAdapter({ projection: changed });
  assert.equal(changedAdapter.available, true, changedAdapter.error);
  const beast = changedAdapter.view(idle, "CEREMONIAL_BEAST_BOSS").encounter;
  const cry = beast.presentation.primary.bodies[0].sections[1].rows.find((row) => row.cue === "1");
  assert.equal(cry.detail, "Apply 2 Ringing");
  assert.equal(Object.hasOwn(cry, "name"), false);
  const merge = beast.presentation.audit.mergeProvenance.values.find((row) => row.path.includes("Beast Cry"));
  assert.deepEqual({ authority: merge.authority, presented: merge.presentedValue, retained: merge.retainedReferenceValue, conflict: merge.conflict }, {
    authority: "checked-source", presented: "2 Ringing", retained: "1 Ringing", conflict: true,
  });
  assert.equal(beast.reference.record.lineup[0].moves.find((move) => move.name === "Beast Cry").text, "Applies 1 Ringing.");
});

test("best-available move merge requires the exact power target and amount sign", () => {
  assert.equal(presentationInternals.mechanicAtom("Gains -2 Strength.").text, "-2 Strength");
  assert.equal(presentationInternals.mechanicAtom("Gains 2/4 Strength.").amountPolarity, "positive");
  const lagavulin = encounter("LAGAVULIN_MATRIARCH_BOSS");
  const soulSiphon = lagavulin.presentation.primary.bodies[0].sections
    .flatMap((section) => section.rows).find((row) => row.cue === "5");
  assert.equal(soulSiphon.detail, "Removes 2 Strength and 2 Dexterity from the player · +2 Strength");
  assert.equal(Object.hasOwn(soulSiphon, "name"), false);
  const provenance = lagavulin.presentation.audit.mergeProvenance.values;
  const retainedDebuff = provenance.find((row) => row.path.endsWith("Soul Siphon · effect 1"));
  const closedSelfBuff = provenance.find((row) => row.path.endsWith("Soul Siphon · effect 2"));
  assert.equal(retainedDebuff.authority, "wiki-reference");
  assert.deepEqual({ authority: closedSelfBuff.authority, presented: closedSelfBuff.presentedValue, conflict: closedSelfBuff.conflict }, {
    authority: "checked-source", presented: "+2 Strength", conflict: false,
  });

  const changed = structuredClone(artifact);
  const sourceMove = changed.payload.sourceFacts.moves.find((move) => move.canonicalId === "MONSTER.LAGAVULIN_MATRIARCH#SOUL_SIPHON_MOVE");
  const selfStrength = sourceMove.operations.find((operation) => operation.kind === "applyPower"
    && operation.model === "POWER.STRENGTH_POWER" && operation.target === "sourceMonster");
  selfStrength.value.expression.value = -3;
  changed.metadata.payloadSha256 = adapterInternals.payloadDigest(changed.payload);
  const changedAdapter = createSourceAdapter({ projection: changed });
  assert.equal(changedAdapter.available, true, changedAdapter.error);
  const changedLagavulin = changedAdapter.view(idle, "LAGAVULIN_MATRIARCH_BOSS").encounter;
  const changedSoulSiphon = changedLagavulin.presentation.primary.bodies[0].sections
    .flatMap((section) => section.rows).find((row) => row.cue === "5");
  assert.equal(changedSoulSiphon.detail, "Removes 2 Strength and 2 Dexterity from the player · +2 Strength");
  const retainedSelfBuff = changedLagavulin.presentation.audit.mergeProvenance.values.find((row) => row.path.endsWith("Soul Siphon · effect 2"));
  assert.match(retainedSelfBuff.reason, /no exact projected source operation coordinate/);
  assert.equal(retainedSelfBuff.authority, "wiki-reference");
});

test("explicit reference phase roles use numbered phase structure without inventing initial bodies", () => {
  const subject = encounter("TEST_SUBJECT_BOSS").presentation.primary;
  assert.equal(subject.header.stats, "288 HP · BOSS");
  assert.deepEqual(subject.bodies.map((body) => [body.initial, body.sections[0].number, body.sections[0].title]), [
    [true, "01", "Phase 1 · Response"],
    [false, "02", "Phase 2 · Response"],
    [false, "03", "Phase 3 · Cycle"],
  ]);
  assert.equal(subject.bodies[0].sections.at(-1).transitionAfter, true);
  assert.equal(subject.bodies[1].sections.at(-1).transitionAfter, true);
  assert.equal(subject.bodies[2].sections.at(-1).transitionAfter, false);
});

test("checked editorial candidates are static, independently qualified, and body-addressable", () => {
  const axebot = encounter("AXEBOTS_NORMAL").presentation.callouts;
  assert.equal(axebot.total, 1);
  assert.equal(axebot.all[0].language, "static-conditional");
  assert.equal(axebot.all[0].bodyIndex, 0);
  assert.match(axebot.all[0].headline, /WATCH/);
  assert.match(axebot.all[0].causalBasis, /replacement body.*same slot/i);
  assert.ok(Object.values(axebot.all[0].qualifications).every(Boolean));
  for (const refs of Object.values(axebot.all[0].basis)) assert.ok(refs.length > 0);
  const axebotProof = new Set(encounter("AXEBOTS_NORMAL").proof.map((row) => row.factId));
  axebot.all[0].basis.factRefs.forEach((ref) => assert.ok(axebotProof.has(ref), ref));
  const axebotLifecycle = JSON.stringify(encounter("AXEBOTS_NORMAL").lifecycle);
  [...axebot.all[0].basis.conditionRefs, ...axebot.all[0].basis.causalRefs]
    .forEach((ref) => assert.ok(axebotLifecycle.includes(ref.replace(/\.(?:condition|orderedEffects|replacementWindowStopsCombatEnding)$/, "")), ref));
  assert.doesNotMatch(JSON.stringify(axebot.all[0]), /do this now|next move|current HP/i);

  const decimillipede = encounter("DECIMILLIPEDE_ELITE").presentation.callouts;
  assert.equal(decimillipede.total, 1);
  assert.match(decimillipede.all[0].headline, /TACTIC/);
  assert.match(decimillipede.all[0].causalBasis, /other segment.*alive.*returns|returns.*other segment.*alive/i);
  const decimillipedeProof = new Set(encounter("DECIMILLIPEDE_ELITE").proof.map((row) => row.factId));
  decimillipede.all[0].basis.factRefs.forEach((ref) => assert.ok(decimillipedeProof.has(ref), ref));
  const decimillipedeLifecycle = JSON.stringify(encounter("DECIMILLIPEDE_ELITE").lifecycle);
  [...decimillipede.all[0].basis.conditionRefs, ...decimillipede.all[0].basis.causalRefs]
    .forEach((ref) => assert.ok(decimillipedeLifecycle.includes(ref.replace(/\.(?:condition|orderedEffects)$/, "")), ref));
  assert.equal(encounter("BOWLBUGS_NORMAL").presentation.callouts.total, 0, "no generic filler");
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
  assert.match(obscura, /teammates · Strength 3/);
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
  assert.match(steam, /remember Steam Eruption's current amount/);
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

test("closed conditional and named state amounts remain practical", () => {
  const egg = encounter("OVICOPTER_NORMAL").presentation.bodies.find((body) => body.name === "Tough Egg");
  assert.match(egg.initialEffects[0].line, /Hatch base 2 when combat side = 2; otherwise 1/);
  assert.doesNotMatch(egg.initialEffects[0].line, /amount unresolved/);
  assert.equal(egg.initialEffects[0].unresolved, "combat-side selection · runtime Power modifiers");
  assert.match(egg.initialEffects[2].line, /set max and starting HP to the stored hatched-form HP/);
  assert.equal(egg.initialEffects[2].unresolved, "stored hatched-form HP");

  for (const body of encounter("DECIMILLIPEDE_ELITE").presentation.bodies) {
    assert.equal(body.hp, "46–52 HP · A8 single player");
    const startingHp = body.initialEffects.filter((fact) => /starting HP/.test(fact.line));
    assert.ok(startingHp.length > 0);
    startingHp.forEach((fact) => assert.match(fact.line, /set max and starting HP to the encounter's shared starting HP roll/));
    startingHp.forEach((fact) => assert.doesNotMatch(fact.line, /amount unresolved/));
    startingHp.forEach((fact) => assert.equal(fact.unresolved, "shared starting-HP roll"));
  }
});

test("body-owned lifecycle rules stay adjacent to the relevant enemy card", () => {
  const kin = encounter("THE_KIN_BOSS").presentation;
  const kinLinkedBodies = kin.lifecycle.mechanics.find((mechanic) => mechanic.branches.some((branch) => strings(branch).join(" ").includes("same Kin Priest")));
  assert.deepEqual(kinLinkedBodies.bodyIndexes, [kin.bodies.findIndex((body) => body.name === "Kin Priest")]);

  const waterfall = encounter("WATERFALL_GIANT_BOSS").presentation;
  const steamRetention = waterfall.lifecycle.mechanics.filter((mechanic) => strings(mechanic).join(" ").includes("Steam Eruption") && mechanic.family === "Death and Power retention");
  assert.equal(steamRetention.length, 3);
  steamRetention.forEach((mechanic) => assert.deepEqual(mechanic.bodyIndexes, [0]));

  const subject = encounter("TEST_SUBJECT_BOSS").presentation;
  const painfulStabsRetention = subject.lifecycle.mechanics.filter((mechanic) => strings(mechanic).join(" ").includes("Painful Stabs") && mechanic.family === "Death and Power retention");
  assert.equal(painfulStabsRetention.length, 2);
  painfulStabsRetention.forEach((mechanic) => assert.deepEqual(mechanic.bodyIndexes, [0]));

  const ovicopter = encounter("OVICOPTER_NORMAL").presentation;
  const eggIndex = ovicopter.bodies.findIndex((body) => body.name === "Tough Egg");
  const minionRetention = ovicopter.lifecycle.mechanics.filter((mechanic) => mechanic.family === "Death and Power retention");
  assert.equal(minionRetention.length, 2);
  minionRetention.forEach((mechanic) => assert.deepEqual(mechanic.bodyIndexes, [eggIndex]));

  const boundary = presentationInternals.lifecyclePresentation({ mechanics: { relationships: [{
    relationshipId: "test", orderedEffects: [{ kind: "kill", owner: "MONSTER.KIN_PRIESTESS", target: "sameOwnerBody" }],
  }] } }, new Map(), new Map([["MONSTER.KIN_PRIEST", 0]]), new Map());
  assert.deepEqual(boundary.mechanics[0].bodyIndexes, [], "canonical model prefixes do not route");
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
    const visiblePresentation = structuredClone(encounter(id).presentation);
    delete visiblePresentation.callouts; // IDs and basis refs are audit-only; the renderer is tested separately.
    delete visiblePresentation.audit; // Exact merge paths and reasons render only inside Technical audit.
    const visible = strings(visiblePresentation).join("\n");
    assert.doesNotMatch(visible, rawIdentity, id);
    assert.doesNotMatch(visible, rawLifecycle, id);
    assert.doesNotMatch(visible, sourceDump, id);
    assert.doesNotMatch(visible, /checked amount/i, id);
    assert.doesNotMatch(visible, /\b(?:current HP|current intent|survivors are|you should|do this now)\b/i, id);
  }
});

test("primary rule prose preserves lexical meaning while rewriting canonical move citations", () => {
  const livingFog = encounter("LIVING_FOG_NORMAL");
  const fogNotes = livingFog.presentation.primary.notes.join(" ");
  assert.match(fogNotes, /Gas Bombs that explode for damage and then die/);
  assert.doesNotMatch(fogNotes, /Gas Bombs that (?:the|“)|step for damage/);

  const ovicopter = encounter("OVICOPTER_NORMAL");
  const eggNotes = ovicopter.presentation.primary.notes.join(" ");
  assert.match(eggNotes, /Tough Eggs that hatch into Hatchlings/);
  assert.match(eggNotes, /its Hatch timer counts down/);
  assert.match(eggNotes, /Hatch timer starts at 2/);
  assert.match(eggNotes, /uses the “Hatches into a Hatchling[^”]+” step to transform/);
  assert.doesNotMatch(eggNotes, /the “[^”]+” step (?:into Hatchlings|timer)/);

  const queen = encounter("QUEEN_BOSS");
  const queenNotes = queen.presentation.primary.notes.join(" ");
  assert.match(queenNotes, /switch intents to the “4×5 damage” step/);
  assert.match(queenNotes, /skipping the usual “\+2 Strength” step/);
  assert.match(queenNotes, /not use the “\+2 Strength” step/);
  assert.doesNotMatch(queenNotes, /usual the|Off with Your Head|usual Enrage|use Enrage/);

  const soulNotes = encounter("SOUL_FYSH_BOSS").presentation.primary.notes.join(" ");
  assert.match(soulNotes, /The first Intangible from the “2 Intangible” step fades instantly/);
  assert.doesNotMatch(soulNotes, /iteration of .* step|Fade's|step's/);

  assert.ok(livingFog.reference.record.lineup.some((body) => body.moves.some((move) => move.name === "Explode")));
  assert.ok(ovicopter.reference.record.lineup.some((body) => body.moves.some((move) => move.name === "Hatch")));
  assert.ok(queen.reference.record.lineup.some((body) => body.moves.some((move) => move.name === "Enrage")));
});

test("all practical rows and structural prose suppress labels while rule prose suppresses move citations", () => {
  const escaped = (label) => label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const boundaryPattern = (label) => new RegExp(`(^|[^A-Za-z0-9])${escaped(label)}(?=[^A-Za-z0-9]|$)`);
  const withoutSemanticMoveUses = (value, bodyName, moveName) => {
    const withoutEntity = String(value).replace(
      new RegExp(`(^|[^A-Za-z0-9])${escaped(bodyName)}(?=[^A-Za-z0-9]|$)`, "g"),
      "$1[entity]",
    );
    return withoutEntity.replace(
      new RegExp(String.raw`(^|[^A-Za-z0-9])${escaped(moveName)}(?=\s+(?:timer|countdown|counter|count|threshold|amount|stacks?|wears? off|expires?)\b)`, "gi"),
      "$1[tracked concept]",
    );
  };
  const citationPatterns = (label) => {
    const name = escaped(label);
    const end = "(?=[^A-Za-z0-9]|$)";
    return [
      new RegExp(`(^|[^A-Za-z0-9])(?:[Uu]se[sd]?|[Uu]sing|[Aa]ctivate[sd]?|[Aa]ctivating|[Ww]ith|[Vv]ia|[Aa]fter|[Tt]o|[Tt]hen|[Uu]sual|(?:[Vv]ersion|[Ii]teration)\\s+of)\\s+(?:the\\s+)?${name}${end}`, "m"),
      new RegExp(`(^|[^A-Za-z0-9])${name}'s${end}`, "m"),
      new RegExp(`^${name}(?=\\s*\\()`, "m"),
      new RegExp(`\\b[Mm]oves?\\s+—[^.]*?(^|[^A-Za-z0-9])${name}${end}`, "m"),
    ];
  };
  for (const id of adapter.canonicalIds) {
    const selected = encounter(id);
    const primary = selected.presentation.primary;
    if (!primary) continue;
    const allMoveNames = selected.reference
      ? selected.reference.record.lineup.flatMap((body) => body.moves.map((move) => move.name))
      : selected.monsters.flatMap((body) => body.moves.map((move) => move.title.text));
    const notes = primary.notes.join("\n");
    for (const moveName of allMoveNames) for (const pattern of citationPatterns(moveName))
      assert.doesNotMatch(notes, pattern, `${id}: ${moveName}`);
    for (const body of primary.bodies) {
      const structural = [
        body.role,
        ...body.sections.flatMap((section) => [section.title, section.note, section.repeat]),
      ].filter(Boolean).join("\n");
      const exactReferenceBody = selected.reference?.record.lineup.find((candidate) => candidate.displayName === body.name);
      const bodyMoves = body.sourceOnlySupplement
        ? selected.monsters.flatMap((candidate) => candidate.moves.map((move) => move.title.text)).filter((title) => typeof title === "string" && title)
        : exactReferenceBody
          ? exactReferenceBody.moves.map((move) => move.name)
          : selected.monsters[body.bodyIndex].moves.map((move) => move.title.text);
      for (const moveName of bodyMoves) {
        const ordinaryCitations = withoutSemanticMoveUses(structural, body.name, moveName);
        assert.doesNotMatch(ordinaryCitations, boundaryPattern(moveName), `${id}: ${moveName}`);
      }
      for (const section of body.sections) for (const row of section.rows) {
        assert.equal(Object.hasOwn(row, "name"), false, `${id} projected a move-name slot`);
        assert.ok(row.cue, `${id} projected a consequence without a structural cue`);
        assert.ok(row.detail, `${id} projected an empty consequence`);
      }
    }
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

test("one guide page has flat phone and desktop width contracts plus accessibility safeguards", () => {
  const html = httpInternals.guidePage("/sts2");
  assert.match(html, /name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/);
  const httpSource = readFileSync(new URL("../src/http.mjs", import.meta.url), "utf8");
  assert.match(httpSource, /Local qq-like design tokens/);
  assert.match(httpSource, /qq-ui does not publish a shared token contract/);
  for (const characteristic of [
    '--qq-bg:#000', '--qq-surface:#000', '--qq-text:#e8e8e8', '--qq-muted:#8a8a8a',
    '--qq-line:#1a1a1a', 'font-family:"Geist UI",Geist,ui-sans-serif,system-ui',
    'min-height:3.5rem', 'summary:focus-visible{outline:2px solid var(--qq-focus)',
    '@media(min-width:44rem)', 'grid-template-columns:repeat(auto-fit,minmax(20rem,1fr))',
    '@media(max-width:21rem)', '@media(prefers-reduced-motion:reduce)', 'border-radius:0',
    'overflow-x:hidden', 'word-break:break-word', '.sequence-row{display:grid', '.phase-transition',
  ]) assert.ok(html.includes(characteristic), characteristic);
  assert.doesNotMatch(html, /white-space:\s*nowrap|overflow-x:\s*auto|box-shadow|(?:linear|radial)-gradient/);
  const css = httpInternals.GUIDE_CSS;
  assert.match(css, /\.sequence-row-uncued \.sequence-detail\{grid-column:2\}/);
  assert.match(css, /\.version-warning\{[^}]*border:1px[^}]*background:/);
  assert.equal((css.match(/border:1px/g) ?? []).length, 1, "version warning is the only enclosing border");
  for (const selector of ["primary-body", "phase-section", "sequence-row", "threshold-line", "selection-context", "body-card", "rule-card", "unknown-row", "callout-card", "technical-audit"])
    assert.doesNotMatch(css, new RegExp(`\\.${selector}\\{[^}]*\\bborder:`, "s"), `${selector} has no enclosing border`);
  for (const selector of ["primary-body", "phase-section", "sequence-row", "threshold-line", "selection-context", "body-card", "rule-card", "unknown-row", "callout-card", "technical-audit"])
    assert.doesNotMatch(css, new RegExp(`\\.${selector}\\{[^}]*background:(?!transparent)`, "s"), `${selector} has no card background`);
  const client = readFileSync(new URL("../src/client.js", import.meta.url), "utf8");
  assert.doesNotMatch(client, /\x08/, "regexes contain no literal backspace characters");
  assert.match(client, /\/\\b\(\?:formula\|AST\)\\b/);
  const order = ["renderPrimaryHero(root", "renderVersionBoundary(state, root", "renderPrimaryBodies(root", "renderPrimaryNotes(root", "renderGlobalCallouts(root", "renderPrimaryFooter(root", "renderAudit(root"];
  let cursor = -1;
  for (const marker of order) { const next = client.indexOf(marker); assert.ok(next > cursor, marker); cursor = next; }
});
