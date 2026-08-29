import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";

import { encounterFor, encounterIds } from "../src/book.mjs";

const artifactBytes = readFileSync(new URL("../data/game-v0.111.0-source.json", import.meta.url));
const artifact = JSON.parse(artifactBytes);
const oldBookBytes = readFileSync(new URL("../data/encounters.json", import.meta.url));
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const sortedValue = (value) => {
  if (Array.isArray(value)) return value.map(sortedValue);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedValue(value[key])]));
  return value;
};
const monster = (id) => artifact.monsters.find((record) => record.canonicalId === id);
const encounter = (id) => [...artifact.encounters.ordinary, ...artifact.encounters.event].find((record) => record.canonicalId === id);
const members = (node, output = new Set()) => {
  if (node.model) output.add(node.model);
  for (const key of ["children", "choices"]) for (const child of node[key] ?? []) members(child, output);
  if (node.selection) members(node.selection, output);
  return output;
};

const exactManifest = [
  { path: "SlayTheSpire2.pck", sha256: "42443027622a6a82de8ab21e81ed5b68e522c0f5647fb6a26a74c4a0970a0d34", size: 1990363992 },
  { path: "data_sts2_linuxbsd_x86_64/sts2.dll", sha256: "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f", size: 9756160 },
  { path: "data_sts2_linuxbsd_x86_64/sts2.xml", sha256: "a88331870d38cdb84d8fc371ab3d7fb619afa25c8c7249a47aaa77e1c7bf4286", size: 5650972 },
  { path: "release_info.json", sha256: "9e5dbce5bcd8ff3b7b432291200220642408e31b8bae7bba14f39aeb6914cd51", size: 150 },
];

test("source artifact is canonical, exactly pinned, partial, and raw-only", () => {
  assert.equal(artifactBytes.toString("utf8"), `${JSON.stringify(sortedValue(artifact), null, 2)}\n`);
  assert.equal(artifact.schemaVersion, 4);
  assert.equal(artifact.extractorVersion, "4.0.0");
  assert.equal(artifact.runtimeReady, false);
  assert.equal(artifact.status, "incomplete");
  assert.deepEqual(artifact.inputs, exactManifest);
  assert.deepEqual(artifact.game, { branch: "v0.111.0", commit: "41cef1ea", mainAssemblyHash: 1579942752, version: "v0.111.0" });
  assert.deepEqual(artifact.safety, {
    assemblyExecution: false,
    cilExecution: false,
    godotInitialization: false,
    mode: "metadataAndBoundedCilAnalysis",
    pckAccess: "readOnlySelective",
    reflectionLoading: false,
  });
  assert.equal(artifact.authority.artifactTier, "rawSource");
  assert.equal(artifact.authority.fallbackPolicy.silentMerge, false);
  assert.doesNotMatch(artifactBytes.toString("utf8"), /(?:generated|extracted|created)(?:At|_at)|timestamp/i);
});

test("coverage is denominator-based and Wave B combat families are complete or honestly classified", () => {
  const complete = {
    encounterIdentities: 89,
    encounterPossibleMembership: 89,
    encounterProductionMembership: 89,
    encounterRosters: 89,
    encounterTitlesEnglish: 89,
    hpInitialConcreteCensus: 120,
    hpInitialCurrentReachable: 108,
    hpMultiplayerScaling: 1,
    hpSpecialStateFormulas: 4,
    monsterIdentitiesCurrentReachable: 108,
    monsterNamesEnglishCurrentReachable: 108,
    monsterNamespaceCensus: 121,
    blockMultiplayerScaling: 1,
    moveActions: 307,
    moveIntentArguments: 311,
    moveIntentClassification: 387,
    moveOperations: 307,
    invocationClassification: 6683,
    moveRegistrationCensus: 307,
    moveSelectionGraphs: 100,
    moveTitleClassification: 307,
    operationDirectSinks: 491,
    operationSemanticFields: 1081,
    powerMultiplayerOptIns: 12,
    powerMultiplayerOverrides: 5,
  };
  for (const [family, denominator] of Object.entries(complete)) {
    assert.deepEqual(artifact.coverage[family], { denominator, numerator: denominator, status: "complete", unresolved: 0 }, family);
  }
  assert.deepEqual(artifact.coverage.moveTitlesEnglish, { denominator: 307, numerator: 289, status: "classified", unresolved: 18 });
  assert.equal(artifact.coverage.powerCardReferencedModels.status, "complete");
});

test("monster census, identities, reachability, and exclusions are exact", () => {
  assert.equal(artifact.monsters.length, 120);
  assert.deepEqual(artifact.monsterCensus.counts, {
    abstract: 1, concrete: 120, eventOnlyReachable: 6, excludedConcrete: 12,
    namespaceTotal: 121, ordinaryReachable: 102, totalReachable: 108,
  });
  assert.deepEqual(artifact.monsterCensus.abstractTypes, ["MegaCrit.Sts2.Core.Models.Monsters.DecimillipedeSegment"]);
  assert.equal(artifact.monsterCensus.hpGetterCensus.length, 120);
  assert.equal(artifact.reachability.ordinaryReachableModels.length, 102);
  assert.equal(artifact.reachability.eventOnlyModels.length, 6);
  assert.equal(artifact.reachability.reachableModels.length, 108);
  assert.deepEqual(artifact.reachability.eventOnlyModels, [
    "MONSTER.ARCHITECT", "MONSTER.BATTLE_FRIEND_V1", "MONSTER.BATTLE_FRIEND_V2",
    "MONSTER.BATTLE_FRIEND_V3", "MONSTER.FAKE_MERCHANT_MONSTER", "MONSTER.MYSTERIOUS_KNIGHT",
  ]);
  assert.equal(artifact.monsterCensus.excludedConcrete.length, 12);
  assert.equal(artifact.monsterCensus.excludedConcrete.find((row) => row.canonicalId === "DEPRECATED_MONSTER").classification, "deprecatedPlaceholder");
  assert.equal(new Set(artifact.monsters.map((row) => row.canonicalId)).size, 120);
});

test("all reachable names are shipped joins and special title states stay model-distinct", () => {
  const reachable = artifact.monsters.filter((row) => ["ordinaryReachable", "eventOnly"].includes(row.reachability.classification));
  assert.equal(reachable.length, 108);
  assert.ok(reachable.every((row) => row.name && row.provenance.name.localization.authority === "rawSource"));
  assert.equal(monster("FLYCONID").name.text, "Flyconid");
  assert.equal(monster("DECIMILLIPEDE_SEGMENT_FRONT").name.text, "Decimillipede");
  assert.equal(monster("DECIMILLIPEDE_SEGMENT_FRONT").provenance.name.localization.localizationKey, "DECIMILLIPEDE_SEGMENT.name");
  assert.equal(monster("TEST_SUBJECT").name.kind, "localizedTemplate");
  assert.equal(monster("TEST_SUBJECT").name.template, "Test Subject #C{Count}");
  assert.equal(monster("TEST_SUBJECT").name.inputs.Count.operator, "add");
  assert.equal(artifact.states.hatchlingName.text, "Hatchling");
  assert.ok(artifact.states.stateIdentities.some((row) => row.stateId === "MONSTER.TOUGH_EGG#HATCHED" && row.canonicalModel === "MONSTER.TOUGH_EGG"));
  assert.ok(artifact.states.stateIdentities.some((row) => row.stateId === "MONSTER.TEST_SUBJECT#PHASE_3" && row.canonicalModel === "MONSTER.TEST_SUBJECT"));
});

test("initial and special HP expressions retain source branches and exact A8 pins", () => {
  assert.deepEqual(monster("FLYCONID").initialHp.a8SinglePlayer, { maximum: 53, minimum: 51 });
  assert.equal(monster("FLYCONID").initialHp.provenance.minimum.diagnosticMetadataToken, "0x06002ed2");
  assert.deepEqual(monster("AXEBOT").initialHp.a8SinglePlayer, { maximum: 86, minimum: 76 });
  assert.equal(monster("AXEBOT").initialHp.expression.minimum.kind, "arithmetic");
  assert.deepEqual(monster("TEST_SUBJECT").initialHp.a8SinglePlayer, { maximum: 111, minimum: 111 });
  assert.deepEqual(artifact.states.toughEggHatch.a8SinglePlayer, { maximum: 23, minimum: 20 });
  assert.deepEqual(artifact.states.testSubjectPhases.phases.map((row) => row.a8SinglePlayer), [111, 212, 313]);
  assert.equal(artifact.states.axebotRespawn.preMultiplayerScaling, true);
  assert.equal(artifact.states.decimillipedeReattach.operation, "healCurrentHp");
  assert.deepEqual(artifact.states.decimillipedeReattach.amountExpression, { kind: "constant", value: "25", valueType: "decimal" });
  for (const row of artifact.monsters) {
    assert.equal(row.initialHp.expression.kind, "range");
    assert.ok(row.initialHp.a8SinglePlayer.minimum <= row.initialHp.a8SinglePlayer.maximum);
    for (const side of ["minimum", "maximum"]) {
      const proof = row.initialHp.provenance[side];
      assert.match(proof.symbolSignature, /::get_(?:Min|Max|First)/);
      assert.match(proof.methodBodySha256, /^[0-9a-f]{64}$/);
      assert.match(proof.normalizedExpressionSha256, /^[0-9a-f]{64}$/);
    }
  }
});

test("HP multiplayer scaling preserves Decimal identity/factors and no invented rounding", () => {
  const hp = artifact.multiplayerScaling.hp;
  assert.equal(hp.expression.kind, "conditional");
  assert.deepEqual(hp.expression.whenFalse.operands[2].factors, { act1: "1.1", act2: "1.2", act3Boss: "1.3", act3NonBoss: "1.2" });
  assert.deepEqual(hp.numericSemantics, {
    factorType: "System.Decimal", outputType: "System.Decimal",
    playerCountConversion: "System.Decimal.op_Implicit(System.Int32)",
    rounding: "none", sourceHpType: "System.Decimal", truncation: "none",
  });
  assert.deepEqual(hp.regressionWitnesses.map((row) => row.result), ["100", "220.0", "240.0", "240.0", "260.0"]);
});

test("all 89 roster ASTs are joined, cardinality-safe, and referentially complete", () => {
  const all = [...artifact.encounters.ordinary, ...artifact.encounters.event];
  const known = new Set(artifact.monsters.map((row) => `MONSTER.${row.canonicalId}`));
  assert.equal(all.length, 89);
  assert.equal(new Set(all.map((row) => row.canonicalId)).size, 89);
  for (const row of all) {
    assert.ok(row.initialRoster.cardinality.minimum > 0);
    assert.ok(row.initialRoster.cardinality.maximum >= row.initialRoster.cardinality.minimum);
    assert.match(row.initialRoster.provenance.semanticWitnessSha256, /^[0-9a-f]{64}$/);
    const selected = members(row.initialRoster.selection);
    for (const model of selected) assert.ok(known.has(model), `${row.canonicalId}: ${model}`);
    for (const model of [...row.possibleMonsters, ...row.producedMonsters]) assert.ok(known.has(model), `${row.canonicalId}: ${model}`);
    assert.ok([...selected].every((model) => row.possibleMonsters.includes(model)));
    assert.ok(row.producedMonsters.every((model) => row.possibleMonsters.includes(model) && !selected.has(model)));
  }
});

test("named random roster and production regressions retain exact structure", () => {
  const fly = encounter("FLYCONID_NORMAL");
  assert.deepEqual(fly.initialRoster.cardinality, { maximum: 2, minimum: 2 });
  assert.equal(fly.initialRoster.selection.children[0].kind, "uniformChoice");
  assert.deepEqual([...members(fly.initialRoster.selection.children[0])].sort(), ["MONSTER.LEAF_SLIME_M", "MONSTER.TWIG_SLIME_M"]);
  assert.equal(fly.initialRoster.selection.children[1].model, "MONSTER.FLYCONID");

  assert.deepEqual(encounter("SLIMES_WEAK").initialRoster.cardinality, { maximum: 3, minimum: 3 });
  assert.equal(encounter("SLIMES_WEAK").initialRoster.selection.kind, "uniformChoice");
  assert.deepEqual(encounter("SLIMES_NORMAL").initialRoster.cardinality, { maximum: 4, minimum: 4 });
  assert.equal(encounter("SLIMES_NORMAL").initialRoster.selection.children[2].kind, "uniformChoice");
  assert.deepEqual(encounter("SLITHERING_STRANGLER_NORMAL").initialRoster.cardinality, { maximum: 3, minimum: 2 });
  assert.equal(encounter("RUBY_RAIDERS_NORMAL").initialRoster.selection.kind, "filteredChoice");
  assert.equal(encounter("RUBY_RAIDERS_NORMAL").initialRoster.selection.count, 3);
  assert.equal(encounter("BOWLBUGS_NORMAL").initialRoster.selection.children[1].draws, "withoutReplacement");
  assert.deepEqual([...members(encounter("BOWLBUGS_WEAK").initialRoster.selection.children[1])].sort(), ["MONSTER.BOWLBUG_EGG", "MONSTER.BOWLBUG_NECTAR"]);

  const vegetation = encounter("DENSE_VEGETATION_EVENT_ENCOUNTER");
  assert.equal(vegetation.title, "Wrigglers");
  assert.deepEqual(vegetation.initialRoster.cardinality, { maximum: 4, minimum: 4 });
  assert.deepEqual(vegetation.initialRoster.selection.children.map((child) => child.model), Array(4).fill("MONSTER.WRIGGLER"));
  assert.ok(vegetation.initialRoster.provenance.methods.some((method) => method.symbolSignature.includes("::get_Slots ")));

  const fabricator = encounter("FABRICATOR_NORMAL");
  assert.deepEqual([...members(fabricator.initialRoster.selection)], ["MONSTER.FABRICATOR"]);
  assert.deepEqual(fabricator.producedMonsters, ["MONSTER.GUARDBOT", "MONSTER.NOISEBOT", "MONSTER.STABBOT", "MONSTER.ZAPBOT"]);
  assert.deepEqual(fabricator.productionPools.map((pool) => [pool.poolId, pool.members]), [
    ["aggressive", ["MONSTER.ZAPBOT", "MONSTER.STABBOT"]],
    ["defensive", ["MONSTER.GUARDBOT", "MONSTER.NOISEBOT"]],
  ]);
});

test("source artifact is not consumed and runtime wiki book remains byte-identical", () => {
  assert.equal(sha256(oldBookBytes), "0c01dd0b851c501acea59fb41b10a828030ad2c3e63f9fc624f98b6e403e0103");
  assert.equal(encounterIds.length, 82);
  assert.ok(encounterFor("DOORMAKER_BOSS"));
  assert.equal(encounterFor("BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER"), null);
  assert.equal(encounterFor("AEONGLASS_BOSS").name, "Aeonglass");
  for (const file of ["../src/book.mjs", "../src/client.js", "../src/http.mjs", "../src/plugin.mjs", "../src/state.mjs"]) {
    assert.doesNotMatch(readFileSync(new URL(file, import.meta.url), "utf8"), /game-v0\.111\.0-source/);
  }
});

const move = (id) => artifact.behavior.registrations.find((row) => row.canonicalId === id);
const graph = (id) => artifact.behavior.graphs.find((row) => row.graphId === id);

test("Wave B registrations, async split, titles, and intents are exact", () => {
  assert.equal(artifact.behavior.registrations.length, 307);
  assert.equal(artifact.behavior.summary.asyncActions, 301);
  assert.equal(artifact.behavior.summary.synchronousNoOpActions, 6);
  assert.equal(artifact.behavior.summary.localizedTitles, 289);
  assert.equal(artifact.behavior.summary.missingOrInternalTitles, 18);
  assert.equal(artifact.behavior.graphs.length, 100);
  const missing = artifact.behavior.registrations.filter((row) => row.title.classification !== "localized");
  assert.equal(missing.length, 18);
  for (const row of missing) {
    assert.equal(row.title.classification, "missingLocalization");
    assert.match(row.title.requestedLocalizationKey, /\.title$/);
  }
  const ebb = move("MONSTER.AEONGLASS#EBB_MOVE");
  assert.equal(ebb.title.english, "Ebb");
  assert.equal(ebb.execution.kind, "asyncStateMachine");
  assert.equal(ebb.intents[0].kind, "attack");
  assert.equal(ebb.intents[1].kind, "block");
  assert.equal(move("MONSTER.WRIGGLER#SPAWNED_MOVE").execution.kind, "synchronousNoOp");

  assert.equal(artifact.behavior.summary.intentConstructorSites, 387);
  assert.equal(artifact.behavior.summary.resolvedIntentConstructorSites, 387);
  assert.equal(artifact.behavior.summary.requiredIntentArguments, 311);
  assert.equal(artifact.behavior.summary.resolvedIntentArguments, 311);
  const delegateArgument = (moveId) => move(moveId).intents.flatMap((intent) => intent.arguments)
    .find((argument) => argument.kind === "sourceDelegate");
  const multiClaw = move("MONSTER.TEST_SUBJECT#MULTI_CLAW_MOVE").intents[0];
  assert.match(multiClaw.constructorSymbolSignature, /MultiAttackIntent::\.ctor sig:20020108151281bd0108$/);
  assert.match(multiClaw.arguments[0].reference, /get_MultiClawDamage/);
  assert.match(multiClaw.arguments[1].resultExpression.reference, /get_MultiClawTotalCount/);
  assert.deepEqual(multiClaw.arguments[1].binding, { argumentIndex: 0, kind: "methodArgument" });
  assert.doesNotMatch(JSON.stringify(multiClaw.arguments), /"value":0/);

  for (const [moveId, callback, getter] of [
    ["MONSTER.THE_FORGOTTEN#DREAD", "b__11_0", "get_DreadDamage"],
    ["MONSTER.WATERFALL_GIANT#PRESSURE_GUN_MOVE", "b__68_0", "get_CurrentPressureGunDamage"],
    ["MONSTER.GAS_BOMB#EXPLODE_MOVE", "b__19_0", "get_ExplodeDamage"],
    ["MONSTER.WATERFALL_GIANT#EXPLODE_MOVE", "b__68_1", "get_SteamEruptionDamage"],
  ]) {
    const argument = delegateArgument(moveId);
    assert.ok(argument, moveId);
    assert.match(argument.targetMethod.symbolSignature, new RegExp(`${callback} sig:`));
    assert.match(argument.resultExpression.expression.reference, new RegExp(`${getter} sig:`));
    assert.match(argument.targetMethod.methodBodySha256, /^[0-9a-f]{64}$/);
    assert.match(argument.targetMethod.normalizedSliceSha256, /^[0-9a-f]{64}$/);
  }
});

test("direct sinks, helpers, and dynamic fixtures remain formulas", () => {
  assert.deepEqual(artifact.behavior.summary.directSinkCounts, {
    addGeneratedCard: 6, addStatusCard: 14, applyPower: 126, attack: 204,
    attackHitCount: 49, escape: 2, gainBlock: 23, heal: 2, kill: 2,
    removeCard: 1, removePower: 6, stateWrite: 51, summon: 5,
  });
  assert.equal(artifact.behavior.summary.directSinkSites, 491);
  assert.equal(artifact.behavior.summary.requiredSemanticFields, 1081);
  assert.equal(artifact.behavior.summary.resolvedSemanticFields, 1081);
  assert.deepEqual(artifact.behavior.invocationCensus.summary, {
    classificationCounts: {
      normalizedGameplayOperation: 508,
      provenNonGameplayPlumbing: 5095,
      traversedGameplayHelper: 1080,
    },
    denominator: 6683, directDenominator: 6332, helperDenominator: 351,
    resolved: 6683, unresolved: 0, vocabularySize: 1156, directVocabularySize: 1041,
  });
  assert.equal(artifact.behavior.invocationCensus.decisions.length, 6683);
  assert.equal(new Set(artifact.behavior.invocationCensus.decisions.map((row) => row.invocationId)).size, 6683);
  assert.equal(artifact.behavior.invocationCensus.decisions.filter((row) => row.invocationId.startsWith("HELPER.")).length, 351);
  for (const [kind, count] of Object.entries(artifact.behavior.summary.directSinkCounts)) {
    assert.deepEqual(artifact.coverage.operationDirectSinksByKind[kind], { denominator: count, numerator: count, status: "complete", unresolved: 0 });
  }
  const lasers = move("MONSTER.AEONGLASS#EYE_LASERS_MOVE");
  assert.equal(lasers.operations[0].kind, "attack");
  assert.equal(lasers.operations[0].value.kind, "convert");
  assert.equal(lasers.operations[0].value.mode, "exact");
  assert.match(lasers.operations[0].value.expression.reference, /get_EyeLasersDamage/);
  assert.equal(lasers.operations[0].target, "allOpponentsOfSourceMonster");
  assert.match(lasers.operations[0].targetProvenance.normalizedSliceSha256, /^[0-9a-f]{64}$/);
  assert.equal(lasers.operations[1].kind, "attackHitCount");
  const oneTwo = move("MONSTER.AXEBOT#ONE_TWO_MOVE");
  assert.equal(oneTwo.operations.find((op) => op.kind === "attackHitCount").value.value, 2);
  const bootStrength = move("MONSTER.AXEBOT#BOOT_UP_MOVE").operations.find((op) => op.kind === "applyPower");
  assert.equal(bootStrength.value.expression.operator, "multiply");
  assert.deepEqual(bootStrength.value.expression.operands.map((row) => row.reference.match(/::(get_[^ ]+)/)[1]), ["get_BootUpStrGain", "get_RespawnCount"]);
  const queenStrength = move("MONSTER.QUEEN#BURN_BRIGHT_FOR_ME_MOVE").operations.find((op) => op.kind === "applyPower");
  assert.deepEqual(queenStrength.value.expression, {
    atOrAbove: { kind: "constant", value: 1, valueType: "integer" },
    below: { kind: "constant", value: 1, valueType: "integer" },
    kind: "ascensionSelect", threshold: 9, valueType: "integer",
  });
  const gardenerScale = move("MONSTER.PHANTASMAL_GARDENER#ENLARGE_MOVE").operations
    .find((op) => op.kind === "stateWrite" && op.memberSymbolSignature.includes("::set_CurrentScale sig:"));
  const logarithm = gardenerScale.value.operands[1].operands[1];
  assert.match(logarithm.reference, /^Godot\.Mathf::Log sig:00010c0c$/);
  assert.equal(logarithm.arguments.length, 1);
  assert.equal(logarithm.arguments[0].operator, "add");
  assert.match(logarithm.arguments[0].operands[0].expression.reference, /::get_EnlargeTriggers sig:/);
  assert.deepEqual(logarithm.arguments[0].operands[1], { kind: "constant", value: "1.0", valueType: "decimal" });
  const wake = move("MONSTER.BYGONE_EFFIGY#WAKE_MOVE").operations.find((op) => op.kind === "applyPower");
  assert.equal(wake.value.expression.value, 10);
  const shrink = move("MONSTER.SHRINKER_BEETLE#SHRINKER_MOVE").operations.find((op) => op.kind === "applyPower");
  assert.deepEqual(shrink.value, { kind: "constant", value: "-1", valueType: "decimal" });
  const goop = move("MONSTER.LEAF_SLIME_S#GOOP_MOVE").operations.find((op) => op.kind === "addStatusCard");
  assert.equal(goop.value.value, 1);
  const guard = move("MONSTER.GUARDBOT#GUARD_MOVE").operations.find((op) => op.kind === "gainBlock");
  assert.equal(guard.target, "iteratedCreature");
  assert.equal(guard.value.expression.value, 15);
  const bloat = move("MONSTER.LIVING_FOG#BLOAT_MOVE").operations.find((op) => op.kind === "summon");
  assert.equal(bloat.selection.slot, "nextOpenCombatSlot");
  assert.ok(!("value" in bloat));
  const remove = move("MONSTER.THIEVING_HOPPER#THIEVERY_MOVE").operations.find((op) => op.kind === "removeCard");
  assert.equal(remove.target, "rngSelectedCombatCard");
  assert.ok(!("value" in remove));
  for (const moveId of ["MONSTER.GAS_BOMB#EXPLODE_MOVE", "MONSTER.WATERFALL_GIANT#EXPLODE_MOVE"]) {
    const kill = move(moveId).operations.find((op) => op.kind === "kill");
    assert.equal(kill.target, "sourceMonster");
    assert.deepEqual(kill.playDeathEffects, { kind: "constant", value: false, valueType: "boolean" });
  }
  assert.equal(move("MONSTER.OWL_MAGISTRATE#VERDICT").operations.find((op) => op.kind === "removePower").model, "POWER.SOAR_POWER");
  assert.deepEqual(move("MONSTER.TEST_SUBJECT#RESPAWN_MOVE").operations.filter((op) => op.kind === "removePower").map((op) => op.model), ["POWER.ADAPTABLE_POWER", "POWER.PAINFUL_STABS_POWER"]);
  const dynamicPowerRemoval = move("MONSTER.TOUGH_EGG#HATCH_MOVE").operations.find((op) => op.kind === "removePower" && op.modelContract);
  assert.equal(dynamicPowerRemoval.target, "runtimeSelectedPowerInstance");
  assert.match(dynamicPowerRemoval.modelContract.sourceSymbolSignature, /::get_Current sig:/);
  const allOperations = artifact.behavior.registrations.flatMap((row) => row.operations);
  assert.ok(allOperations.every((op) => /^[0-9a-f]{64}$/.test(op.provenance.normalizedSliceSha256)));
  assert.ok(allOperations.filter((op) => ["summon", "removeCard", "escape"].includes(op.kind)).every((op) => !("value" in op)));
  const serializedOperations = JSON.stringify(allOperations);
  assert.ok(!serializedOperations.includes("AscensionHelper::GetValueIfAscension"));
  for (const forbidden of ["resolvedStackValue", '"target":"allPlayers"', "NRunMusicController::get_Instance", "NCombatRoom::get_Instance", "MonsterModel::get_AttackSfx"]) {
    assert.ok(!serializedOperations.includes(forbidden), forbidden);
  }
  const helpers = artifact.behavior.registrations.filter((row) => row.operations.some((op) => op.kind === "helperEffect"));
  const helperKinds = new Set(helpers.flatMap((row) => row.operations.filter((op) => op.kind === "helperEffect").map((op) => op.helper)));
  for (const helper of ["reattach", "fabricate", "chooseCurse", "hatch", "pressureState"]) {
    assert.ok(helperKinds.has(helper), helper);
  }
});

test("selection graphs preserve topology, Flyconid/Fabricator/Decimillipede fixtures, and referential integrity", () => {
  const topo = artifact.behavior.summary.topology;
  assert.deepEqual(topo, {
    behaviorClasses: 100, bothBranchKinds: 2, conditionalClasses: 16, conditionalNodes: 17,
    followUpAssignments: 309, moveConstructors: 307, mustOnceFlags: 4, randomClasses: 20, randomNodes: 22,
  });
  const fly = graph("GRAPH.FLYCONID");
  assert.equal(fly.initial, "GRAPH.FLYCONID/INITIAL");
  assert.equal(fly.topology.randomNodes, 2);
  assert.equal(fly.edges.filter((edge) => edge.kind === "randomBranch").length, 5);
  assert.ok(fly.edges.every((edge) => edge.kind !== "randomBranch" || edge.weight === 2));
  const fabricator = graph("GRAPH.FABRICATOR");
  assert.ok(fabricator.topology.randomNodes > 0 && fabricator.topology.conditionalNodes > 0);
  const decim = graph("GRAPH.DECIMILLIPEDE_SEGMENT");
  assert.ok(Array.isArray(decim.initial));
  assert.equal(decim.initial.length, 3);
  const moveIds = new Set(artifact.behavior.registrations.map((row) => row.canonicalId));
  for (const row of artifact.behavior.graphs) {
    assert.match(row.provenance.semanticWitnessSha256, /^[0-9a-f]{64}$/);
    for (const node of row.nodes) {
      if (node.kind === "move") {
        assert.ok(moveIds.has(`${row.canonicalMonster}#${node.stateId}`), node.nodeId);
      }
    }
  }
});

test("Block and Power multiplayer formulas are distinct from ordinary attacks", () => {
  const block = artifact.multiplayerScaling.block;
  assert.equal(block.expression.kind, "conditional");
  assert.deepEqual(block.fixtures.map((row) => row.multiplier), ["1", "2", "3.9", "1"]);
  const power = artifact.multiplayerScaling.power;
  assert.equal(power.optIns.length, 12);
  assert.equal(power.overrides.length, 5);
  assert.equal(power.overrides.find((row) => row.canonicalPower === "POWER.BUFFER_POWER").active, false);
  assert.equal(power.overrides.find((row) => row.canonicalPower === "POWER.PLATING_POWER").active, true);
  assert.equal(artifact.multiplayerScaling.ordinaryMonsterAttack.scalesInMultiplayer, false);
  assert.equal(artifact.powers.length, 43);
  for (const removedPower of ["POWER.ADAPTABLE_POWER", "POWER.HATCH_POWER"]) {
    assert.ok(artifact.powers.some((row) => row.canonicalId === removedPower), removedPower);
  }
  assert.equal(artifact.cards.length, 9);
});
