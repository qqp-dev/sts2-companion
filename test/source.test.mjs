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
  assert.equal(artifact.schemaVersion, 11);
  assert.equal(artifact.extractorVersion, "11.0.0");
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

test("coverage is denominator-based and current behavior families are complete or honestly classified", () => {
  const complete = {
    architectDependencyRefs: 5,
    architectDialogueLineCensus: 39,
    architectDialogueTemplateCensus: 17,
    architectInvocationClassification: 715,
    architectLineControlEdges: 39,
    architectLineControlNodes: 39,
    architectLocalizationStructuralClosure: 64,
    architectOptionDelegateClosure: 2,
    architectOwnerLinkPlacementApplicability: 1,
    architectPresentationOnlyClosure: 13,
    architectSemanticEffects: 6,
    architectStateRuntimeInputContracts: 8,
    architectTerminalSinkOrder: 1,
    architectVisualOnlyLayoutProof: 1,
    actCensus: 4,
    behaviorGraphApplicability: 105,
    behaviorOwnerApplicability: 105,
    encounterPlacement: 89,
    eventEncounterLinkage: 8,
    eventTurnClassifications: 8,
    eventTurnDependencyClassifications: 4,
    eventTurnDirectOperations: 6,
    eventTurnIntentArguments: 5,
    eventTurnIntentClassification: 6,
    eventTurnInvocationClassification: 103,
    eventTurnNoOpProofs: 4,
    eventTurnOperations: 10,
    eventTurnPhysicalOwners: 5,
    eventTurnPhysicalRegistrations: 8,
    eventTurnPhysicalTitlesEnglish: 8,
    eventTurnReuseInheritanceApplicability: 3,
    eventScriptDependencyRefs: 6,
    eventScriptDisplayScalingArguments: 3,
    eventScriptEdges: 20,
    eventScriptEffectiveMethods: 76,
    eventScriptEncounterLinks: 7,
    eventScriptFrameworkClosure: 53,
    eventScriptInvocationClassification: 1549,
    eventScriptNodes: 25,
    eventScriptOptionDelegates: 12,
    eventScriptOutcomes: 7,
    eventScriptOwnerApplicability: 5,
    eventScriptSemanticEffects: 10,
    eventScriptStateRuntimeContracts: 10,
    eventScriptSupportMethodClosure: 14,
    eventScriptTransitionArguments: 7,
    randomBranchOverloadClosure: 10,
    randomBranchRepeatWeightSemantics: 61,
    randomWeightCallbackClosure: 8,
    randomSelectionRuntimeContract: 3,
    productionAddApiCensus: 14,
    productionOstyApiCensus: 17,
    productionOwnerRootDiscovery: 7,
    productionHelperCallClosure: 5,
    productionDirectSiteDiscovery: 6,
    productionOwnerEncounterApplicability: 6,
    coreAddOverloadClosure: 3,
    coreAddMethodClosure: 6,
    coreAddSemanticFieldClosure: 11,
    moveRegistrationApplicability: 315,
    observableIdentityDomain: 108,
    observableResourceRepresentations: 108,
    observableStateContracts: 8,
    placementMemberships: 90,
    poolCensus: 20,
    poolMemberships: 192,
    encounterIdentities: 89,
    encounterPossibleMembership: 89,
    encounterProductionMembership: 89,
    encounterRosters: 89,
    encounterTitlesEnglish: 89,
    hpInitialConcreteCensus: 120,
    hpInitialCurrentReachable: 108,
    hpMultiplayerScaling: 1,
    hpAssignmentSetterCensus: 11,
    hpBaseSelectionUniqueValueChain: 4,
    hpCapClampPreconditionSemanticFields: 8,
    hpCommandSpecialCallerApplicability: 52,
    hpCompletePipelineSemanticFields: 85,
    hpMultiplayerWrapperHelperCallClosure: 9,
    hpStorageNetworkSerializationJoins: 10,
    hpSpecialStateFormulas: 4,
    monsterIdentitiesCurrentReachable: 108,
    monsterNamesEnglishCurrentReachable: 108,
    monsterNamespaceCensus: 121,
    blockMultiplayerScaling: 1,
    moveActions: 315,
    moveIntentArguments: 316,
    moveIntentClassification: 393,
    moveOperations: 315,
    encounterInitializers: 89,
    initialStateOwners: 108,
    initialStateEffectiveHooks: 108,
    initialStateDirectSinkSites: 57,
    initialStateTransitiveInvocationClassification: 1092,
    initialStatePowerHookClosure: 41,
    initialExternalHookBoundary: 29,
    initialStateSemanticFields: 1554,
    invocationClassification: 6786,
    moveRegistrationCensus: 315,
    moveSelectionGraphs: 105,
    moveTitleClassification: 315,
    operationDirectSinks: 497,
    operationSemanticFields: 1094,
    powerMultiplayerOptIns: 12,
    powerMultiplayerOverrides: 5,
  };
  for (const [family, denominator] of Object.entries(complete)) {
    assert.deepEqual(artifact.coverage[family], { denominator, numerator: denominator, status: "complete", unresolved: 0 }, family);
  }
  assert.deepEqual(artifact.coverage.moveTitlesEnglish, { denominator: 315, numerator: 297, status: "classified", unresolved: 18 });
  assert.equal(artifact.coverage.powerCardReferencedModels.status, "complete");
});


test("E1 source placement is registry-derived, closed, and preserves non-pool encounters", () => {
  assert.deepEqual(artifact.placement.sourceDenominators, {
    acts: 4, currentEncounterMemberships: 90, currentEncounterPlacements: 89,
    eventEncounterLinks: 8, poolRegistryMembers: 192, pools: 20,
  });
  assert.deepEqual(artifact.placement.acts.map((row) => [row.canonicalId, row.actIndex, row.registryOrder]), [
    ["ACT.OVERGROWTH", 0, 0], ["ACT.UNDERDOCKS", 0, 1], ["ACT.HIVE", 1, 2], ["ACT.GLORY", 2, 3],
  ]);
  const placements = new Map(artifact.placement.encounters.map((row) => [row.canonicalEncounter, row]));
  assert.equal(placements.size, 89);
  assert.ok(!placements.has("ENCOUNTER.DOORMAKER_BOSS"));
  assert.deepEqual(placements.get("ENCOUNTER.DECIMILLIPEDE_ELITE").memberships.map((row) => [row.actId, row.roomClass, row.tier]), [["ACT.HIVE", "elite", "elite"]]);
  assert.deepEqual(placements.get("ENCOUNTER.RUBY_RAIDERS_NORMAL").memberships.map((row) => [row.actId, row.roomClass, row.tier]), [["ACT.OVERGROWTH", "monster", "regular"]]);
  assert.equal(placements.get("ENCOUNTER.TUNNELER_NORMAL").nonPoolClassification.kind, "absentFromAllActEncounterRegistries");
  assert.equal(placements.get("ENCOUNTER.THE_ARCHITECT_EVENT_ENCOUNTER").nonPoolClassification.kind, "scriptedRunTransition");
  const fake = placements.get("ENCOUNTER.FAKE_MERCHANT_EVENT_ENCOUNTER");
  assert.deepEqual(fake.memberships.map((row) => row.actId), ["ACT.GLORY", "ACT.HIVE", "ACT.OVERGROWTH", "ACT.UNDERDOCKS"]);
  assert.ok(fake.memberships.every((row) => row.conditions[0].condition.kind === "allOf"));
  const weakPool = artifact.placement.pools.find((row) => row.poolId === "POOL.OVERGROWTH.WEAK");
  assert.equal(weakPool.selection.kind, "weightedDrawSequence");
  assert.deepEqual(weakPool.selection.immediateExclusions, ["sameEncounterInstance", "sharedEncounterTag"]);
  assert.ok(weakPool.canonicalMembers.every((row) => row.weight.value === "1.0"));
  assert.equal(artifact.placement.eventLinkage.length, 8);
});

test("E1 observation IDs are exact canonical models and states do not invent aliases", () => {
  const identity = artifact.observationIdentities;
  assert.deepEqual(identity.sourceDenominators, {
    currentReachableModels: 108, observableIds: 108, resourceRepresentations: 108,
    sourceDeclaredCurrentAliases: 0, stateObservationContracts: 8,
  });
  assert.deepEqual(identity.aliases, []);
  assert.deepEqual(identity.matchingPolicy, {
    caseSensitive: true, fuzzyMatching: false, prefixStripping: false,
    wirePrefixes: [{ category: "monsterModel", prefix: "MONSTER.", source: "ModelId.Category" }],
  });
  const entries = new Map(identity.entries.map((row) => [row.observedId, row]));
  for (const id of [
    "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
    "MONSTER.DECIMILLIPEDE_SEGMENT_BACK", "MONSTER.ASSASSIN_RUBY_RAIDER",
    "MONSTER.AXE_RUBY_RAIDER", "MONSTER.BRUTE_RUBY_RAIDER",
    "MONSTER.CROSSBOW_RUBY_RAIDER", "MONSTER.TRACKER_RUBY_RAIDER",
    "MONSTER.TOUGH_EGG", "MONSTER.TEST_SUBJECT",
  ]) {
    assert.equal(entries.get(id).canonicalMonster, id);
    assert.equal(entries.get(id).identityKind, "model");
  }
  for (const lookalike of ["MONSTER.DECIMILLIPEDE_FRONT", "MONSTER.ASSASSIN_RAIDER", "MONSTER.HATCHLING", "MONSTER.TEST_SUBJECT_PHASE_2", "monster.tough_egg"]) {
    assert.ok(!entries.has(lookalike), lookalike);
  }
  const resources = new Map(identity.resourceRepresentations.map((row) => [row.resourceId, row]));
  assert.equal(resources.size, 108);
  assert.equal(resources.get("res://scenes/creature_visuals/decimillipede_segment_front.tscn").canonicalMonster, "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT");
  assert.equal(resources.get("res://scenes/creature_visuals/assassin_ruby_raider.tscn").identityKind, "resourceRepresentationOfModel");
  assert.ok(!entries.has("res://scenes/creature_visuals/tough_egg.tscn"));
  const stateContracts = new Map(identity.stateObservationContracts.map((row) => [row.stateId, row]));
  assert.equal(stateContracts.get("MONSTER.TOUGH_EGG#HATCHED").observation.emittedModelId, "MONSTER.TOUGH_EGG");
  assert.equal(stateContracts.get("MONSTER.TEST_SUBJECT#PHASE_2").observation.separateStateIdEmitted, false);
});

test("E1 behavior applicability closes all owners, graphs, and registrations", () => {
  assert.equal(artifact.behavior.applicability.length, 105);
  const byOwner = new Map(artifact.behavior.applicability.map((row) => [row.behaviorOwnerSourceType, row.applicableConcreteModels.map((item) => item.canonicalMonster)]));
  for (const row of [...artifact.behavior.graphs, ...artifact.behavior.registrations]) {
    assert.deepEqual(row.applicableConcreteModels, byOwner.get(row.sourceType), row.sourceType);
  }
  const decimilli = artifact.behavior.applicability.find((row) => row.behaviorOwnerSourceType.endsWith(".DecimillipedeSegment"));
  assert.deepEqual(decimilli.applicableConcreteModels.map((row) => row.canonicalMonster), [
    "MONSTER.DECIMILLIPEDE_SEGMENT_BACK", "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT", "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
  ]);
  assert.equal(artifact.behavior.registrations.filter((row) => row.sourceType.endsWith(".DecimillipedeSegment") && row.applicableConcreteModels.length === 3).length, 5);
  assert.deepEqual(byOwner.get("MegaCrit.Sts2.Core.Models.Monsters.FlailKnight"), ["MONSTER.FLAIL_KNIGHT", "MONSTER.MYSTERIOUS_KNIGHT"]);
  assert.equal(artifact.behavior.graphs.filter((row) => row.canonicalMonster === "MONSTER.MYSTERIOUS_KNIGHT").length, 0);
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

test("E2b HP assignment pipeline separates arithmetic, conversion, storage, and wire semantics", () => {
  const hp = artifact.hpPipeline;
  assert.deepEqual(hp.sourceDenominators, {
    baseSelectionChainMethods: 4,
    capClampPreconditionSemanticFields: 8,
    commandAndSpecialCallerApplicability: 52,
    completePipelineSemanticFields: 85,
    multiplayerWrapperHelperCallSites: 9,
    setterMethodsAndDirectCallSites: 11,
    storageAndNetworkSerializationJoins: 10,
  });
  assert.equal(artifact.multiplayerScaling.hp.numericSemantics.rounding, "none");
  assert.deepEqual(hp.assignment.conversion, {
    expression: { domain: { minimum: "0" }, kind: "stateVariable", name: "assignedHpDecimal", valueType: "decimal" },
    fromType: "decimal", kind: "convert", mode: "truncateTowardZero", toType: "integer", valueType: "integer",
  });
  assert.deepEqual(hp.assignment.max, {
    cap: 999999999,
    capOrder: "afterDecimalToInt32Conversion",
    currentInteraction: "storeMaxThenStoreMin(previousCurrent,newMax)",
    negativeInput: "ArgumentExceptionBeforeConversion",
    storageType: "Int32",
  });
  assert.equal(hp.assignment.current.clamp, "DecimalMin(requestedCurrent,Decimal(maxHp))BeforeConversion");
  assert.equal(hp.assignment.current.lowerClamp, "none");
  assert.equal(hp.assignment.numericContract.nonNegativeEquivalence, "floor");
  assert.equal(hp.assignment.numericContract.negativeEquivalenceClaimed, false);
  assert.deepEqual(hp.storage, {
    currentHp: { cliType: "Int32", metadataSignature: "0608", symbol: "MegaCrit.Sts2.Core.Entities.Creatures.Creature::_currentHp" },
    maxHp: { cliType: "Int32", metadataSignature: "0608", symbol: "MegaCrit.Sts2.Core.Entities.Creatures.Creature::_maxHp" },
  });
  assert.deepEqual(hp.networkStorage.serializationOrder, ["currentHp:Int32/32", "maxHp:Int32/32"]);
  assert.deepEqual(hp.networkStorage.deserializationOrder, ["currentHp", "maxHp"]);
  assert.equal(hp.networkStorage.wireBits, 32);
  assert.deepEqual(hp.callCensus.targetDistribution, {
    ScaleHpForMultiplayer: 8, ScaleMonsterHpForMultiplayer: 1, SetCurrentHpInternal: 6,
    SetMaxHpInternal: 3, SetUniqueMonsterHpValue: 1,
  });
  assert.deepEqual(hp.callCensus.commandTargetDistribution, {
    GainMaxHp: 22, LoseMaxHp: 10, SetCurrentHp: 3, SetMaxAndCurrentHp: 4, SetMaxHp: 5,
  });
  assert.deepEqual(hp.specialCallPaths, [
    { joins: ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"], pathId: "DECIMILLIPEDE" },
    { joins: ["ScaleHpForMultiplayer", "SetMaxHp", "Heal", "HealInternal", "SetCurrentHpInternal"], pathId: "TEST_SUBJECT" },
    { joins: ["ScaleHpForMultiplayer", "SetMaxAndCurrentHp"], pathId: "TOUGH_EGG" },
  ]);
  const cases = Object.fromEntries(hp.regressionWitnesses.map((row) => [row.case, row]));
  assert.deepEqual([cases.fractionalAct1TwoPlayer.decimalProduct, cases.fractionalAct1TwoPlayer.storedHp], ["101.2", 101]);
  assert.deepEqual([cases.exactIntegerProduct.decimalProduct, cases.exactIntegerProduct.storedHp], ["110.0", 110]);
  assert.deepEqual([cases.act3Boss.decimalProduct, cases.act3Boss.storedHp], ["119.6", 119]);
  assert.deepEqual([cases.onePlayerBypass.decimalProduct, cases.onePlayerBypass.storedHp], ["46", 46]);
  assert.deepEqual(cases.inclusiveBaseRange.selectionDomain, [46, 47, 48, 49, 50, 51, 52]);
  assert.deepEqual(cases.teammateAvoidance.selectionDomain, [47]);
  assert.deepEqual(cases.teammateFallback.selectionDomain, [46]);
  assert.equal(cases.capExact.storedHp, 999999999);
  assert.equal(cases.capAbove.storedHp, 999999999);
  assert.equal(cases.negativeMaxRejected.result, "ArgumentExceptionBeforeConversion");
  assert.equal(cases.currentClamp.storedHp, 101);
  assert.equal(cases.currentFractionalConversion.storedHp, 100);
  assert.equal(cases.checkedOverflowBeforeCap.result, "OverflowExceptionBeforeCap");
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
    assert.doesNotMatch(readFileSync(new URL(file, import.meta.url), "utf8"), /game-v0\.111\.0-source|encounter-facts-v0\.111\.0/);
  }
});

const move = (id) => artifact.behavior.registrations.find((row) => row.canonicalId === id);
const graph = (id) => artifact.behavior.graphs.find((row) => row.graphId === id);

test("event-inclusive registrations, async split, titles, and intents are exact", () => {
  assert.equal(artifact.behavior.registrations.length, 315);
  assert.equal(artifact.behavior.summary.asyncActions, 305);
  assert.equal(artifact.behavior.summary.synchronousNoOpActions, 10);
  assert.equal(artifact.behavior.summary.localizedTitles, 297);
  assert.equal(artifact.behavior.summary.missingOrInternalTitles, 18);
  assert.equal(artifact.behavior.graphs.length, 105);
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

  assert.equal(artifact.behavior.summary.intentConstructorSites, 393);
  assert.equal(artifact.behavior.summary.resolvedIntentConstructorSites, 393);
  assert.equal(artifact.behavior.summary.requiredIntentArguments, 316);
  assert.equal(artifact.behavior.summary.resolvedIntentArguments, 316);
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
    addGeneratedCard: 6, addStatusCard: 14, applyPower: 128, attack: 207,
    attackHitCount: 50, escape: 2, gainBlock: 23, heal: 2, kill: 2,
    removeCard: 1, removePower: 6, stateWrite: 51, summon: 5,
  });
  assert.equal(artifact.behavior.summary.directSinkSites, 497);
  assert.equal(artifact.behavior.summary.requiredSemanticFields, 1094);
  assert.equal(artifact.behavior.summary.resolvedSemanticFields, 1094);
  assert.deepEqual(artifact.behavior.invocationCensus.summary, {
    classificationCounts: {
      normalizedGameplayOperation: 514,
      provenNonGameplayPlumbing: 5171,
      traversedGameplayHelper: 1101,
    },
    denominator: 6786, directDenominator: 6418, helperDenominator: 368,
    resolved: 6786, unresolved: 0, vocabularySize: 1172, directVocabularySize: 1049,
  });
  assert.equal(artifact.behavior.invocationCensus.decisions.length, 6786);
  assert.equal(new Set(artifact.behavior.invocationCensus.decisions.map((row) => row.invocationId)).size, 6786);
  assert.equal(artifact.behavior.invocationCensus.decisions.filter((row) => row.invocationId.startsWith("HELPER.")).length, 368);
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

test("E2c1 event turn machines close all eight links without claiming script or lifecycle", () => {
  const eventRows = new Map(artifact.behavior.eventTurnMachines.map((row) => [row.canonicalEncounter, row]));
  assert.equal(eventRows.size, 8);
  assert.deepEqual([...eventRows.values()].map((row) => row.behaviorClassification).sort(), [
    "inheritedTurnMachine", "noOpTurnMachineWithLifecycle", "noOpTurnMachineWithLifecycle",
    "noOpTurnMachineWithLifecycle", "normalTurnMachine", "normalTurnMachine", "normalTurnMachine",
    "scriptedNonTurnCombat",
  ]);
  for (const version of [1, 2, 3]) {
    const row = eventRows.get(`BATTLEWORN_DUMMY_EVENT_V${version}_ENCOUNTER`);
    assert.equal(row.behaviorClassification, "noOpTurnMachineWithLifecycle");
    assert.deepEqual(row.registrationIds, [`MONSTER.BATTLE_FRIEND_V${version}#NOTHING_MOVE`]);
    assert.equal(move(row.registrationIds[0]).operations[0].transition, "noOp");
    assert.deepEqual(graph(row.graphId).stateCollection, {
      cardinality: 1,
      constructor: "<TypeSpec:1512b75001128848>::.ctor sig:2001011300",
      elementType: "MoveState", kind: "readOnlySingle",
      orderedNodes: [`GRAPH.BATTLE_FRIEND_V${version}/NOTHING_MOVE`],
    });
    assert.equal(row.dependencyRefs.length, 1);
    assert.equal(row.initialStateFactRefs.length, 1);
  }
  const fake = eventRows.get("FAKE_MERCHANT_EVENT_ENCOUNTER");
  assert.equal(fake.behaviorClassification, "normalTurnMachine");
  assert.deepEqual(fake.registrationIds.map((id) => id.split("#")[1]), ["SWIPE_MOVE", "SPEW_COINS_MOVE", "THROW_RELIC_MOVE", "ENRAGE_MOVE"]);
  assert.deepEqual(fake.titles.map((row) => row.title.english), ["Swipe", "Spew Coins", "Throw Relic", "Enrage"]);
  const fakeGraph = graph(fake.graphId);
  assert.deepEqual(fakeGraph.topology, { conditionalBranches: 0, conditionalNodes: 0, followUpEdges: 4, moveNodes: 4, mustOnceFlags: 0, randomBranches: 7, randomNodes: 2 });
  assert.deepEqual(fakeGraph.stateCollection.orderedNodes.map((id) => id.split("/")[1]), ["SWIPE_MOVE", "SPEW_COINS_MOVE", "THROW_RELIC_MOVE", "ENRAGE_MOVE", "RAND_MOVE", "RAND_ATTACK_MOVE"]);
  assert.equal(fakeGraph.edges.filter((edge) => edge.kind === "randomBranch").length, 7);
  const fakeMoves = fake.registrationIds.map(move);
  assert.equal(fakeMoves.flatMap((row) => row.intents).length, 5);
  assert.deepEqual(fakeMoves.flatMap((row) => row.operations).map((op) => op.kind), ["attack", "attack", "attackHitCount", "attack", "applyPower", "applyPower"]);
  assert.deepEqual(fakeMoves.flatMap((row) => row.operations).filter((op) => op.kind === "applyPower").map((op) => op.model), ["POWER.FRAIL_POWER", "POWER.STRENGTH_POWER"]);
  const concat = artifact.behavior.invocationCensus.decisions.find((row) => row.evidence.symbolSignature.startsWith("System.String::Concat"));
  assert.equal(concat.role, "dialogueLocalizationKeyConstruction");
  assert.match(concat.sourceMethod, /FakeMerchantMonster::GetLinesForMove/);

  const mysterious = eventRows.get("MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER");
  assert.equal(mysterious.behaviorClassification, "inheritedTurnMachine");
  assert.equal(mysterious.behaviorOwner, "MONSTER.FLAIL_KNIGHT");
  assert.equal(artifact.behavior.graphs.filter((row) => row.canonicalMonster === "MONSTER.MYSTERIOUS_KNIGHT").length, 0);
  assert.deepEqual(mysterious.titles.map((row) => row.title.localizationRoot), Array(3).fill("MYSTERIOUS_KNIGHT"));
  assert.ok(graph("GRAPH.FLAIL_KNIGHT").applicableConcreteModels.includes("MONSTER.MYSTERIOUS_KNIGHT"));
  assert.equal(eventRows.get("DENSE_VEGETATION_EVENT_ENCOUNTER").graphId, "GRAPH.WRIGGLER");
  assert.equal(eventRows.get("PUNCH_OFF_EVENT_ENCOUNTER").graphId, "GRAPH.PUNCH_CONSTRUCT");
  const architect = eventRows.get("THE_ARCHITECT_EVENT_ENCOUNTER");
  assert.equal(architect.behaviorClassification, "scriptedNonTurnCombat");
  assert.equal(move(architect.registrationIds[0]).intents[0].kind, "hidden");
  assert.equal(move(architect.registrationIds[0]).operations[0].transition, "noOp");
  assert.equal(architect.dependencyRefs.length, 1);
  assert.deepEqual(artifact.behavior.eventTurnSummary, {
    classifications: 8, eventIntentArguments: 5, eventIntentConstructorSites: 6,
    eventTurnDirectOperations: 6, eventTurnOperationsIncludingNoOpProofs: 10,
    noOpProofs: 4, physicalOwners: 5, physicalRegistrations: 8,
    physicalTitles: 8, reuseOrInheritanceApplicability: 3,
  });
  assert.deepEqual(artifact.behavior.eventTurnInvocationCensus.summary, {
    classificationCounts: { normalizedGameplayOperation: 6, provenNonGameplayPlumbing: 76, traversedGameplayHelper: 21 },
    denominator: 103, resolved: 103, unresolved: 0,
  });
});

test("E2c2a linked event scripts preserve exact options, transition stacks, outcomes, and dependencies", () => {
  const scripts = artifact.eventScripts;
  assert.deepEqual(scripts.sourceDenominators, {
    dependencies: 6, displayScalingCalls: 3, edges: 20, effects: 10,
    encounterScripts: 7, frameworkMethods: 53, invocations: 1549,
    methods: 76, nodes: 25, options: 12, outcomes: 7, owners: 5,
    stateContracts: 10, supportMethods: 14,
  });
  assert.deepEqual(scripts.invocationCensus.summary, { denominator: 1549, resolved: 1549, unresolved: 0 });
  assert.equal(scripts.owners.some((row) => row.canonicalEvent === "EVENT.THE_ARCHITECT"), false);
  assert.deepEqual(scripts.owners.map((row) => row.canonicalEvent), [
    "EVENT.BATTLEWORN_DUMMY", "EVENT.DENSE_VEGETATION", "EVENT.FAKE_MERCHANT",
    "EVENT.PUNCH_OFF", "EVENT.THE_LANTERN_KEY",
  ]);
  const transitions = new Map(scripts.transitions.map((row) => [row.canonicalEncounter, row]));
  assert.deepEqual([...transitions.keys()].sort(), [
    "ENCOUNTER.BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER", "ENCOUNTER.BATTLEWORN_DUMMY_EVENT_V2_ENCOUNTER",
    "ENCOUNTER.BATTLEWORN_DUMMY_EVENT_V3_ENCOUNTER", "ENCOUNTER.DENSE_VEGETATION_EVENT_ENCOUNTER",
    "ENCOUNTER.FAKE_MERCHANT_EVENT_ENCOUNTER", "ENCOUNTER.MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER",
    "ENCOUNTER.PUNCH_OFF_EVENT_ENCOUNTER",
  ]);
  for (const version of [1, 2, 3]) {
    const row = transitions.get(`ENCOUNTER.BATTLEWORN_DUMMY_EVENT_V${version}_ENCOUNTER`);
    assert.equal(row.resume.shouldResume, true);
    assert.deepEqual(row.addedRewards, []);
    assert.equal(row.overload.genericEncounter, false);
  }
  for (const id of ["DENSE_VEGETATION_EVENT_ENCOUNTER", "FAKE_MERCHANT_EVENT_ENCOUNTER", "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER", "PUNCH_OFF_EVENT_ENCOUNTER"])
    assert.equal(transitions.get(`ENCOUNTER.${id}`).resume.shouldResume, false);
  assert.deepEqual(transitions.get("ENCOUNTER.MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER").addedRewards.map((x) => [x.rewardType, x.model.sourceType]),
    [["SpecialCardReward", "MegaCrit.Sts2.Core.Models.Cards.LanternKey"]]);
  assert.deepEqual(transitions.get("ENCOUNTER.PUNCH_OFF_EVENT_ENCOUNTER").addedRewards.map((x) => x.rewardType), ["RelicReward", "PotionReward"]);
  const fakeRewards = transitions.get("ENCOUNTER.FAKE_MERCHANT_EVENT_ENCOUNTER").addedRewards;
  assert.equal(fakeRewards[0].model.sourceType, "MegaCrit.Sts2.Core.Models.Relics.FakeMerchantsRug");
  assert.equal(fakeRewards[1].model.name, "event.inventory.unstockedRelic.model");
  assert.equal(scripts.foulPotionDispatch.classification, "potionDrivenEventInstanceFanOut");
  assert.equal(scripts.foulPotionDispatch.taskJoin, "Task.WhenAll");

  const dense = scripts.owners.find((row) => row.canonicalEvent === "EVENT.DENSE_VEGETATION");
  assert.match(JSON.stringify(dense.availability.expression), /event\.dynamicVars\.HpLoss\.baseValue/);
  assert.equal(JSON.stringify(dense.availability.expression).includes('"value":8'), false);
  const denseDamage = scripts.effects.find((row) => row.eventId === "EVENT.DENSE_VEGETATION" && row.kind === "damage");
  assert.equal(denseDamage.amount.name, "event.dynamicVars.HpLoss.baseValue");
  const edge = (from, to) => scripts.edges.some((row) => row.from === from && row.to === to);
  assert.ok(edge("EVENT_NODE.DENSE_VEGETATION/REST", "EVENT_NODE.DENSE_VEGETATION/FIGHT"));
  assert.ok(edge("EVENT_NODE.THE_LANTERN_KEY/KEEP_THE_KEY", "EVENT_NODE.THE_LANTERN_KEY/FIGHT"));
  assert.ok(edge("EVENT_NODE.PUNCH_OFF/I_CAN_TAKE_THEM", "EVENT_NODE.PUNCH_OFF/FIGHT"));
  assert.ok(edge("EVENT_NODE.FAKE_MERCHANT/FOUL_POTION_USE", "EVENT_NODE.FAKE_MERCHANT/FAKE_MERCHANT_EVENT_ENCOUNTER"));
  const nabReward = scripts.effects.find((row) => row.eventId === "EVENT.PUNCH_OFF" && row.kind === "constructReward");
  assert.equal(nabReward.reward.rewardType, "RelicReward");
  assert.equal(nabReward.reward.model.kind, "runtimePull");

  const battleOutcomes = scripts.outcomes.filter((row) => row.classification === "customRanOutOfTimeBranch");
  assert.equal(battleOutcomes.length, 3);
  assert.ok(battleOutcomes.every((row) => row.stateRead.name === "encounter.RanOutOfTime"));
  assert.deepEqual(battleOutcomes.map((row) => row.success.versionEffect.kind), ["dynamicPotionReward", "upgradeCards", "dynamicRelicReward"]);
  assert.deepEqual(scripts.displayScaling.map((row) => row.sourceMonsterType.split(".").at(-1)), ["BattleFriendV1", "BattleFriendV2", "BattleFriendV3"]);
  assert.deepEqual(scripts.displayScaling.map((row) => row.sourceEncounterType.split(".").at(-1)),
    ["BattlewornDummyEventV1Encounter", "BattlewornDummyEventV1Encounter", "BattlewornDummyEventV1Encounter"]);
  assert.deepEqual(scripts.dependencies.filter((row) => row.kind === "lifecycle").map((row) => row.dependencyId), [
    "LIFECYCLE.POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER.AFTER_SIDE_TURN_END",
    "LIFECYCLE.COMMAND.CREATURE_ESCAPE/BATTLE_FRIEND_OWNER", "LIFECYCLE.COMBAT.EVENT_TERMINAL_RESULT",
    "LIFECYCLE.RUN.ARCHITECT_TERMINAL",
  ]);
});

test("E2c2b Architect terminal script is source-derived, dynamic, visual-only, and prose-free", () => {
  const architect = artifact.eventScripts.architect;
  assert.deepEqual(architect.sourceDenominators, {
    dependencies: 5, edges: 39, invocations: 715, lines: 39, localizationKeys: 64,
    methods: 96, nodes: 39, options: 2, presentationMethods: 13,
    runtimeContracts: 8, semanticEffects: 6, templates: 17,
  });
  const templates = architect.dialogue.templates;
  assert.equal(templates.length, 17);
  assert.equal(templates.reduce((sum, row) => sum + row.lineCount, 0), 39);
  assert.deepEqual([...new Set(templates.map((row) => row.characterKey))].sort(),
    ["DEFECT", "IRONCLAD", "NECROBINDER", "REGENT", "SILENT"]);
  assert.deepEqual(new Set(templates.flatMap((row) => [row.startAttackers, row.endAttackers])),
    new Set(["None", "Player", "Architect", "Both"]));
  assert.equal(templates.filter((row) => row.repeating).length, 15);
  assert.deepEqual(templates.flatMap((row) => row.lines).reduce((counts, line) =>
    ({ ...counts, [line.speaker]: (counts[line.speaker] ?? 0) + 1 }), {}), { Ancient: 22, Character: 17 });
  assert.deepEqual(architect.dialogue.selection.candidateOrder,
    ["exactNullableVisitEqualsCharacterWins", "repeatingVisitAtMostCharacterWinsWhenNoExact"]);
  assert.equal(architect.dialogue.selection.agnosticCandidatesIncluded, false);
  assert.equal(architect.dialogue.selection.concreteTemplate.kind, "runtimeSelection");
  assert.match(architect.dialogue.selection.rngInput, /event\.rng\.nextItem/);
  assert.equal(architect.initialState.lineIndexInitialization, 0);
  assert.deepEqual(architect.initialState.options.map((row) => row.callback.target).sort(), [
    "MegaCrit.Sts2.Core.Models.Events.TheArchitect::AdvanceDialogue sig:2000128121",
    "MegaCrit.Sts2.Core.Models.Events.TheArchitect::WinRun sig:2000128121",
  ]);
  assert.equal(architect.visualOnlyCombat.roomMode, "VisualOnly");
  assert.equal(architect.visualOnlyCombat.classification, "notActiveCombat");
  assert.equal(architect.roomEntry.scoreReference.arguments[1], true);
  assert.match(architect.roomEntry.scoreReference.symbolSignature, /sig:00020812841c02$/);
  assert.equal(architect.presentation.completeSliceHasGameplayDamage, false);
  assert.equal(architect.presentation.apparentDamageClassification, "damageNumberVfxNotHpDamage");
  assert.equal(architect.presentation.scoreSplit.renderDeterministically, false);
  assert.deepEqual(architect.terminal.orderedControl,
    ["animatePlayerEndAttackers", "animateArchitectEndAttackers", "localOwnerRunManagerWinRun", "awaitWinRun", "setEmptyOptionsFinishedState"]);
  assert.equal(architect.terminal.localOwnerGuarded, true);
  assert.equal(architect.terminal.eventCombatTransition, false);
  assert.equal(architect.terminal.noResume, true);
  assert.equal(architect.terminal.noRewardPage, true);
  assert.deepEqual(architect.terminal.runManagerBoundary.order, ["OnEnded(true)", "GuaranteeKillAllPlayers"]);
  assert.equal(architect.terminal.runManagerBoundary.missingRunState, "returnWithoutOnEndedOrForcedKills");
  assert.equal(architect.localization.proseEmitted, false);
  assert.equal(architect.localization.provenance.entrySha256, "cd0d1c321f5c42db844b22178abf88297ba3942d557402537bef7437c9c41593");
  assert.equal(architect.localization.keyValueWitnesses.length, 64);
  assert.doesNotMatch(JSON.stringify(architect.localization), /"(?:value|text|prose|template)":/);
  assert.deepEqual(architect.invocationCensus.summary, { denominator: 715, resolved: 715, unresolved: 0 });
  assert.deepEqual(architect.invocationCensus.residualVocabulary,
    { sha256: "7aac765fd42a8282414bed67181b4a066deff87a9cef9fc322aaf3037011df7a", size: 174 });
  assert.ok(architect.dependencies.some((row) => row.dependencyId === "FORMULA.SCORE_UTILITY.CALCULATE_SCORE"));
  assert.equal(architect.dependencies.filter((row) => row.kind === "lifecycle").length, 4);
  const scripted = artifact.behavior.eventDependencies.find((row) => row.kind === "scriptedEventSemantics");
  assert.equal(scripted.status, "sourceComplete");
  assert.equal(scripted.resolvedComponentRef, "EVENT_SCRIPT_COMPONENT.THE_ARCHITECT");
});

test("selection graphs preserve topology, Flyconid/Fabricator/Decimillipede fixtures, and referential integrity", () => {
  const topo = artifact.behavior.summary.topology;
  assert.deepEqual(topo, {
    behaviorClasses: 105, bothBranchKinds: 2, conditionalClasses: 16, conditionalNodes: 17,
    followUpAssignments: 317, moveConstructors: 315, mustOnceFlags: 4, randomClasses: 21, randomNodes: 24,
  });
  const fly = graph("GRAPH.FLYCONID");
  assert.equal(fly.initial, "GRAPH.FLYCONID/INITIAL");
  assert.equal(fly.topology.randomNodes, 2);
  assert.equal(fly.edges.filter((edge) => edge.kind === "randomBranch").length, 5);
  const allRandom = artifact.behavior.graphs.flatMap((row) => row.edges.filter((edge) => edge.kind === "randomBranch"));
  assert.equal(allRandom.length, 61);
  assert.ok(allRandom.every((edge) => typeof edge.repeat.enumValue === "number" && typeof edge.repeat.enumName === "string"));
  assert.ok(allRandom.every((edge) => edge.weight.valueType === "float" && !Object.hasOwn(edge, "predicate")));
  assert.deepEqual(artifact.behavior.randomSelectionContract.summary, {
    branches: 61, floatCallbacks: 8, graphs: 21, overloads: 10,
    repeatTypeDistribution: { CanRepeatForever: 4, CanRepeatXTimes: 10, CannotRepeat: 45, UseOnlyOnce: 2 },
  });
  const flyBranches = fly.edges.filter((edge) => edge.kind === "randomBranch");
  assert.ok(flyBranches.every((edge) => edge.repeat.enumName === "CannotRepeat"));
  assert.ok(flyBranches.every((edge) => edge.weight.kind === "constant" && edge.weight.value === 1));
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

test("E2d1a random callbacks, Rat repeat policy, and production/core Add contracts are source-closed", () => {
  const random = artifact.behavior.randomSelectionContract;
  assert.deepEqual(random.enum.values, [
    { name: "CanRepeatForever", value: 0 }, { name: "CanRepeatXTimes", value: 1 },
    { name: "CannotRepeat", value: 2 }, { name: "UseOnlyOnce", value: 3 },
  ]);
  const callbackEdges = artifact.behavior.graphs.flatMap((row) => row.edges).filter((edge) => edge.kind === "randomBranch" && edge.weight.kind === "delegate");
  assert.equal(callbackEdges.length, 8);
  assert.ok(callbackEdges.every((edge) => edge.weight.valueType === "float" && edge.weight.targetMethod.symbolSignature.endsWith(" sig:20000c")));
  const fog = graph("GRAPH.FOGMOG").edges.filter((edge) => edge.kind === "randomBranch");
  assert.deepEqual(fog.map((edge) => edge.weight.expression.value), [0.4000000059604645, 0.6000000238418579]);
  const rat = graph("GRAPH.TWO_TAILED_RAT").edges.filter((edge) => edge.kind === "randomBranch");
  assert.deepEqual(rat.map((edge) => [edge.to.split("/").at(-1), edge.repeat.enumName, edge.cooldown]), [
    ["SCRATCH_MOVE", "CannotRepeat", 0], ["DISEASE_BITE_MOVE", "CannotRepeat", 0],
    ["SCREECH_MOVE", "CannotRepeat", 3], ["CALL_FOR_BACKUP_MOVE", "UseOnlyOnce", 0],
  ]);
  assert.deepEqual(rat.at(-1).weight.expression, {
    condition: { kind: "methodBoolean", symbolSignature: "MegaCrit.Sts2.Core.Models.Monsters.TwoTailedRat::CanSummon sig:200002", valueType: "boolean" },
    kind: "conditional", valueType: "float",
    whenFalse: { kind: "constant", value: 0, valueType: "float" },
    whenTrue: { kind: "constant", value: 0.75, valueType: "float" },
  });

  const production = artifact.production;
  assert.deepEqual(production.summary, {
    addAssemblySites: 14, currentDirectSites: 6, helperCallEdges: 5, helperMethods: 3,
    ostyAssemblySites: 17, ownerEncounterApplicability: 6, producerOwners: 6, producerRoots: 7,
    siteClassifications: { coreAddForwarding: 2, currentEnemyEncounterProduction: 6,
      outOfScopeDeathPower: 4, outOfScopeMock: 1, outOfScopePlayerPet: 1 },
  });
  assert.equal(new Set(production.helperCallSites.map((row) => row.callSiteId)).size, 5);
  assert.equal(new Set(production.helperCallSites.map((row) => row.calleeSymbolSignature)).size, 3);
  assert.deepEqual(production.producerRoots.filter((row) => row.ownerModel === "MONSTER.FABRICATOR").map((row) => row.moveId), [
    "MONSTER.FABRICATOR#FABRICATE_MOVE", "MONSTER.FABRICATOR#FABRICATING_STRIKE_MOVE",
  ]);
  assert.equal(production.directSites.length, 6);
  assert.ok(production.directSites.every((row) => row.candidateMembership.canonicalModels.length > 0));
  assert.equal(production.productionSemantics.status, "pendingE2d1b");
  assert.equal(production.ostySummonContract.afterSummon, "awaitedAfterOstyAddOrReviveHistory");
  assert.equal(production.ostySummonContract.classification, "separateFromCreatureCmdAddEnemyProduction");
  const core = production.coreAddContract;
  assert.deepEqual(core.callOrder, ["createBody", "encounterOnCreatureSpawned", "coreLiveCheck", "combatBodyListInsertion",
    "combatManagerNodeInsertion", "roomNodeInsertion", "awaitInitialStateDispatch", "prepareForNextTurn",
    "uniqueRoomMonsterIdHistory", "awaitAfterCreatureAddedToCombat", "returnCreatedBody"]);
  assert.equal(core.overloads.length, 3);
  assert.equal(core.resultIdentity, "generic and explicit-model wrappers return the exact body created before awaiting core Add");
  assert.equal(core.semanticBoundaries.coreSlotValidation, "absent");
  assert.deepEqual(core.history.not, ["bodyCount", "productionCap", "poolDepletion"]);
  assert.deepEqual(core.hookBoundary, { afterCreatureAddedToCombat: "awaited", afterSummon: "absentSeparateOstyApi" });
  assert.equal(core.dependencies.initialStateOwnerModels.length, 9);
  assert.equal(core.dependencies.initialStateFactRefs.length, 7);
  assert.equal(core.dependencies.initialStateNoGameplayFactModels.length, 4);
  assert.equal(core.dependencies.hpAssignmentComponentRef, "hpPipeline.assignment");
  assert.ok(production.ostySummonCensus.every((row) => row.classification !== "currentEnemyEncounterProduction"));
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
  assert.equal(artifact.powers.length, 69);
  for (const removedPower of ["POWER.ADAPTABLE_POWER", "POWER.HATCH_POWER"]) {
    assert.ok(artifact.powers.some((row) => row.canonicalId === removedPower), removedPower);
  }
  assert.equal(artifact.cards.length, 9);
});


test("E2a initial-state denominators, stage ordering, and hook boundaries are closed", () => {
  const initial = artifact.initialState;
  assert.deepEqual(initial.summary, {
    encounterRoots: 89, facts: 111, invocationDecisions: 1092,
    modelOwners: 108, powerModels: 41, runtimeContracts: 47,
  });
  assert.deepEqual(initial.sourceDenominators, {
    constructorExplicitWrites: 5, constructorOwners: 4,
    directSinkSitesByKind: { applyPower: 54, gainBlock: 1, setCurrentHp: 1, setMaxAndCurrentHp: 1 },
    effectiveHookImplementations: 59, encounterGenerationOwners: 89,
    generatorConstructionSites: 137, generatorRngSites: 38,
    generatorSetterOwners: 13, generatorSetterSites: 25,
    initialStateModels: 108, nonRosterInitializationRngRoots: 5, powerModels: 41,
  });
  assert.equal(initial.encounterInitializers.length, 89);
  assert.equal(new Set(initial.encounterInitializers.map((row) => row.canonicalEncounter)).size, 89);
  assert.equal(initial.initialStateOwners.length, 108);
  assert.equal(new Set(initial.initialStateOwners.map((row) => row.effectiveHook)).size, 59);
  assert.equal(initial.initialStateOwners.filter((row) => row.classification === "sourceProvenNoOp").length, 48);
  assert.deepEqual(initial.initializationChain.map((row) => row.stage), [
    "creatureCreation", "encounterSpawnRegistration", "combatStart", "creatureAdded",
    "modelAdditionHookDispatch", "effectiveMonsterAdditionHook", "beforeCombatStartDispatch",
  ]);
  const boundary = new Map(initial.externalHookBoundary.map((row) => [row.family, row]));
  assert.equal(boundary.get("BeforeCombatStart").declarations.length, 23);
  assert.equal(boundary.get("BeforeCombatStart").declarations.filter((row) => row.classification === "externalRuntimeOwned").length, 19);
  assert.equal(boundary.get("AfterCreatureAddedToCombat").declarations.length, 6);
  assert.ok(initial.initialStateFacts.every((row) => row.provenance.methodBodySha256.length === 64));
  assert.ok(initial.initialStateFacts.every((row) => row.finalValueContract.classification === "intrinsicRequestedBaseline"));
});

test("E2a generator and constructor facts retain exact temporal state", () => {
  const facts = artifact.initialState.initialStateFacts;
  const inEncounter = (id) => facts.filter((row) => row.encounterApplicability === `ENCOUNTER.${id}`);
  const dense = inEncounter("DENSE_VEGETATION_EVENT_ENCOUNTER");
  assert.equal(dense.length, 1);
  assert.equal(dense[0].ownerModel, "MONSTER.WRIGGLER");
  assert.match(dense[0].effect.member, /::set_StartStunned /);
  // Exact source CIL writes false; Wriggler's graph selects SPAWNED_MOVE only
  // for true. Keep this investigated source result instead of forcing the audit expectation.
  assert.deepEqual(dense[0].baseValue.expression, { kind: "constant", value: false, valueType: "boolean" });

  const deci = inEncounter("DECIMILLIPEDE_ELITE");
  assert.equal(deci.length, 3);
  assert.deepEqual(deci.map((row) => row.ownerModel).sort(), [
    "MONSTER.DECIMILLIPEDE_SEGMENT_BACK", "MONSTER.DECIMILLIPEDE_SEGMENT_FRONT",
    "MONSTER.DECIMILLIPEDE_SEGMENT_MIDDLE",
  ]);
  assert.equal(deci.filter((row) => row.baseValue.expression.operator === "remainder").length, 2);
  assert.equal(inEncounter("SCROLLS_OF_BITING_NORMAL").length, 4);
  assert.equal(inEncounter("TWO_TAILED_RATS_NORMAL").length, 3);
  const punch = inEncounter("PUNCH_OFF_EVENT_ENCOUNTER");
  assert.equal(punch.length, 3);
  assert.ok(punch.some((row) => row.baseValue.expression.kind === "reference"));

  const constructors = facts.filter((row) => row.stage === "constructorDefault");
  assert.equal(constructors.length, 5);
  assert.deepEqual(constructors.filter((row) => row.ownerModel === "MONSTER.TWO_TAILED_RAT").map((row) => row.baseValue.expression.value), [-1, 2]);
  assert.equal(constructors.find((row) => row.ownerModel === "MONSTER.PHANTASMAL_GARDENER").baseValue.expression.value, "1.0");
});

test("E2a addition effects, helpers, relationships, and restored branches stay ordered", () => {
  const initial = artifact.initialState;
  const factsFor = (model) => initial.initialStateFacts.filter((row) => row.ownerModel === model);
  const kinds = (model) => factsFor(model).map((row) => row.effect.kind);
  const owner = (model) => initial.initialStateOwners.find((row) => row.ownerModel === model);

  assert.deepEqual(kinds("MONSTER.AEONGLASS"), ["configurePowerTarget", "applyPower", "applyPower"]);
  assert.deepEqual(factsFor("MONSTER.AEONGLASS").filter((row) => row.effect.kind === "applyPower").map((row) => row.effect.model), [
    "POWER.WITHERING_PRESENCE_POWER", "POWER.ARTIFACT_POWER",
  ]);
  assert.deepEqual(kinds("MONSTER.CUBEX_CONSTRUCT"), ["gainBlock", "applyPower", "subscribe", "setState"]);
  assert.equal(factsFor("MONSTER.CUBEX_CONSTRUCT")[0].baseValue.expression.expression.value, 13);
  assert.deepEqual(kinds("MONSTER.LAGAVULIN_MATRIARCH"), ["setState", "applyPower", "applyPower"]);
  assert.deepEqual(factsFor("MONSTER.LAGAVULIN_MATRIARCH").filter((row) => row.effect.kind === "applyPower").map((row) => row.effect.model), [
    "POWER.PLATING_POWER", "POWER.ASLEEP_POWER",
  ]);
  assert.equal(owner("MONSTER.LAGAVULIN_MATRIARCH").classification, "orderedGameplayEffects");

  const segments = ["FRONT", "MIDDLE", "BACK"].map((side) => owner(`MONSTER.DECIMILLIPEDE_SEGMENT_${side}`));
  assert.equal(new Set(segments.map((row) => row.effectiveHook)).size, 1);
  assert.ok(segments.every((row) => row.applicableModels.length === 3));
  assert.ok(factsFor("MONSTER.DECIMILLIPEDE_SEGMENT_FRONT").some((row) => row.effect.kind === "setMaxAndCurrentHp"));
  assert.ok(factsFor("MONSTER.QUEEN").some((row) => row.effect.kind === "relationship" && row.effect.targetModel === "MONSTER.TORCH_HEAD_AMALGAM"));
  assert.ok(factsFor("MONSTER.PUNCH_CONSTRUCT").some((row) => row.effect.kind === "setCurrentHp"));

  const tough = factsFor("MONSTER.TOUGH_EGG");
  const hatch = tough.find((row) => row.effect.model === "POWER.HATCH_POWER");
  assert.equal(hatch.baseValue.expression.kind, "conditional");
  assert.deepEqual(hatch.baseValue.expression.condition, {
    kind: "compare",
    left: {
      domain: { maximum: 2, minimum: 0 },
      kind: "stateVariable", name: "combat.currentSide", valueType: "integer",
    },
    operator: "equal",
    right: { kind: "constant", value: 2, valueType: "integer" },
    valueType: "boolean",
  });
  const branchLiteral = (branch) => branch.kind === "convert" ? branch.expression.value : branch.value;
  assert.equal(branchLiteral(hatch.baseValue.expression.whenTrue), 2);
  assert.equal(branchLiteral(hatch.baseValue.expression.whenFalse), 1);
  assert.ok(tough.some((row) => row.condition.classification === "restoredHatchedState" && row.effect.kind === "setMaxAndCurrentHp"));
  assert.ok(tough.some((row) => row.condition.classification === "restoredHatchedState" && row.effect.kind === "forceMoveState"));

  assert.deepEqual(kinds("MONSTER.MYSTERIOUS_KNIGHT"), ["applyPower", "applyPower"]);
  for (const version of [1, 2, 3]) {
    const battle = factsFor(`MONSTER.BATTLE_FRIEND_V${version}`);
    assert.equal(battle.length, 1);
    assert.equal(battle[0].effect.model, "POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER");
  }
  assert.equal(owner("MONSTER.ARCHITECT").classification, "sourceProvenNoOp");
  assert.equal(owner("MONSTER.BOWLBUG_EGG").classification, "sourceProvenNonGameplayOnly");
  assert.equal(owner("MONSTER.TWO_TAILED_RAT").classification, "sourceProvenNonGameplayOnly");
});

test("E2a selected Power hooks and runtime contracts are explicit", () => {
  const initial = artifact.initialState;
  const byPower = new Map(initial.powerHookClosure.map((row) => [row.canonicalPower, row]));
  const hook = (power, name) => byPower.get(power).hooks.find((row) => row.hook === name);
  assert.equal(hook("POWER.ILLUSION_POWER", "AfterApplied").classification, "orderedGameplayEffects");
  assert.equal(hook("POWER.PLATING_POWER", "AfterApplied").classification, "orderedGameplayEffects");
  assert.equal(hook("POWER.GALVANIC_POWER", "BeforeCombatStart").classification, "orderedGameplayEffects");
  assert.equal(hook("POWER.VITAL_SPARK_POWER", "BeforeCombatStart").classification, "orderedGameplayEffects");
  for (const power of byPower.values()) assert.deepEqual(power.hooks.map((row) => row.hook), ["BeforeApplied", "AfterApplied", "BeforeCombatStart"]);
  const byFact = new Map(initial.initialStateFacts.map((row) => [row.factId, row]));
  assert.equal(byFact.get(hook("POWER.ILLUSION_POWER", "AfterApplied").effectFactRefs[0]).effect.model, "POWER.MINION_POWER");
  assert.ok(byFact.get(hook("POWER.PLATING_POWER", "AfterApplied").effectFactRefs[0]).sourceStateInputs.includes("RUNTIME.RUN.PLAYER_COUNT"));
  assert.equal(byFact.get(hook("POWER.GALVANIC_POWER", "BeforeCombatStart").effectFactRefs[0]).effect.model, "AFFLICTION.GALVANIZED");
  assert.equal(byFact.get(hook("POWER.VITAL_SPARK_POWER", "BeforeCombatStart").effectFactRefs[0]).effect.model, "AFFLICTION.TAINTED");
  const contracts = new Map(initial.runtimeStateContracts.map((row) => [row.contractId, row]));
  for (const id of ["RUNTIME.COMBAT.CURRENT_SIDE", "RUNTIME.RUN.PLAYER_COUNT", "RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP", "RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP", "RUNTIME.EXTERNAL.POWER_AMOUNT_HOOKS"]) {
    assert.ok(contracts.has(id), id);
    assert.ok(contracts.get(id).domain);
    assert.ok(contracts.get(id).readSites.length > 0);
  }
  assert.deepEqual(contracts.get("RUNTIME.COMBAT.CURRENT_SIDE").domain,
    { maximum: 2, minimum: 0 });
  assert.deepEqual(artifact.observationIdentities.aliases, []);
});

test("README and world-model census claims match schema 11 summary and coverage", () => {
  const markdown = (url) => readFileSync(new URL(url, import.meta.url), "utf8").replace(/\s+/g, " ").trim();
  const readme = markdown("../README.md");
  const worldModel = markdown("../docs/source-world-model.md");
  const has = (document, claim) => assert.ok(document.includes(claim.replace(/\s+/g, " ").trim()), claim);
  const count = (value) => value.toLocaleString("en-US");
  const word = (value) => ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"][value] ?? String(value);

  const behavior = artifact.behavior;
  const summary = behavior.summary;
  const topology = summary.topology;
  const invocations = behavior.invocationCensus.summary;
  const eventSummary = behavior.eventTurnSummary;
  const eventInvocations = behavior.eventTurnInvocationCensus.summary;
  const coverage = artifact.coverage;

  // Bind every documented E2c1 family to both the source summary and its coverage denominator.
  assert.equal(coverage.moveRegistrationCensus.denominator, topology.moveConstructors);
  assert.equal(coverage.moveRegistrationCensus.denominator, behavior.registrations.length);
  assert.equal(coverage.moveSelectionGraphs.denominator, topology.behaviorClasses);
  assert.equal(coverage.moveSelectionGraphs.denominator, behavior.graphs.length);
  assert.equal(coverage.moveIntentClassification.denominator, summary.intentConstructorSites);
  assert.equal(coverage.moveIntentArguments.denominator, summary.requiredIntentArguments);
  assert.equal(coverage.invocationClassification.denominator, invocations.denominator);
  assert.equal(coverage.operationDirectSinks.denominator, summary.directSinkSites);
  assert.equal(coverage.operationSemanticFields.denominator, summary.requiredSemanticFields);
  assert.equal(coverage.moveTitlesEnglish.denominator, topology.moveConstructors);
  assert.equal(coverage.moveTitlesEnglish.numerator, summary.localizedTitles);
  assert.equal(coverage.moveTitlesEnglish.unresolved, summary.missingOrInternalTitles);
  assert.equal(coverage.eventTurnClassifications.denominator, behavior.eventTurnMachines.length);
  assert.equal(coverage.eventTurnPhysicalOwners.denominator, eventSummary.physicalOwners);
  assert.equal(coverage.eventTurnPhysicalRegistrations.denominator, eventSummary.physicalRegistrations);
  assert.equal(coverage.eventTurnInvocationClassification.denominator, eventInvocations.denominator);
  assert.equal(coverage.eventTurnDirectOperations.denominator, eventSummary.eventTurnDirectOperations);
  assert.equal(coverage.eventTurnNoOpProofs.denominator, eventSummary.noOpProofs);

  const registrations = new Map(behavior.registrations.map((row) => [row.canonicalId, row]));
  const graphs = new Map(behavior.graphs.map((row) => [row.graphId, row]));
  const fake = behavior.eventTurnMachines.find((row) => row.canonicalEncounter === "FAKE_MERCHANT_EVENT_ENCOUNTER");
  const fakeMoves = fake.registrationIds.map((id) => registrations.get(id));
  const fakeOperations = fakeMoves.flatMap((row) => row.operations);
  const operationCount = (kind) => fakeOperations.filter((row) => row.kind === kind).length;
  const fakePowers = fakeOperations.filter((row) => row.kind === "applyPower").map((row) => row.model);
  const fakeGraph = graphs.get(fake.graphId);
  assert.deepEqual(fakePowers, ["POWER.FRAIL_POWER", "POWER.STRENGTH_POWER"]);

  const priorDirectSites = summary.directSinkSites - eventSummary.eventTurnDirectOperations;
  const originalDirectSites = priorDirectSites
    - summary.directSinkCounts.kill
    - summary.directSinkCounts.removePower
    - summary.directSinkCounts.stateWrite;
  assert.equal(summary.directSinkSites, Object.values(summary.directSinkCounts).reduce((total, value) => total + value, 0));

  has(readme, `Schema ${artifact.schemaVersion} remains deliberately`);
  has(readme, `Title localization is classified ${summary.localizedTitles}/${topology.moveConstructors} with ${summary.missingOrInternalTitles} explicit missing/internal keys`);
  has(readme, `${topology.moveConstructors} current move registrations from all reachable behavior classes plus the abstract Decimillipede segment implementation (${summary.asyncActions} async via \`AsyncStateMachineAttribute\`, ${word(summary.synchronousNoOpActions)} exact \`Task.CompletedTask\` no-ops)`);
  has(readme, `${summary.localizedTitles} shipped English titles joined by localization root/state`);
  has(readme, `${summary.intentConstructorSites} constructed intent sites across all ${topology.moveConstructors} moves and all ${summary.requiredIntentArguments} constructor arguments`);
  has(readme, `a closed census of ${count(invocations.denominator)} invocations: ${count(invocations.directDenominator)} direct sites in the ${summary.asyncActions} generated move bodies plus ${invocations.helperDenominator} unique recursively traversed helper sites`);
  has(readme, `the combined ${count(invocations.vocabularySize)}-symbol census contains ${invocations.classificationCounts.normalizedGameplayOperation} normalized gameplay operations/effects, ${count(invocations.classificationCounts.traversedGameplayHelper)} traversed gameplay/support helpers, and ${count(invocations.classificationCounts.provenNonGameplayPlumbing)} source-proven compiler, async, collection, formula, wait, or presentation calls`);
  has(readme, `${summary.directSinkSites} direct normalized sites: the prior ${priorDirectSites} (the original ${originalDirectSites} sinks plus ${summary.directSinkCounts.kill} self-kills, ${summary.directSinkCounts.removePower} Power removals, and ${summary.directSinkCounts.stateWrite} typed monster state writes) plus ${word(eventSummary.eventTurnDirectOperations)} Fake Merchant sites (${operationCount("attack")} attacks, ${operationCount("attackHitCount")} hit-count site, Frail \`applyPower\`, and Strength \`applyPower\`)`);
  has(readme, `with all ${count(summary.requiredSemanticFields)} required semantic fields resolved`);
  has(readme, `${topology.behaviorClasses} selection graphs with ${topology.moveConstructors} move constructors, ${topology.followUpAssignments} follow-up assignments, ${topology.randomNodes} random nodes, ${topology.conditionalNodes} conditional nodes, ${word(topology.mustOnceFlags)} must-once flags`);
  has(readme, `${topology.behaviorClasses} behavior owners/graphs and all ${topology.moveConstructors} registrations to reachable concrete models`);
  has(readme, `Source enumeration yields ${topology.behaviorClasses} physical graph owners and ${topology.moveConstructors} registrations. ${word(eventSummary.physicalOwners)[0].toUpperCase()}${word(eventSummary.physicalOwners).slice(1)} physical graphs and ${word(eventSummary.physicalRegistrations)} registrations are newly included`);
  has(readme, `Fake Merchant | \`normalTurnMachine\` | ${word(fake.registrationIds.length)[0].toUpperCase()}${word(fake.registrationIds.length).slice(1)} localized moves, ${word(fakeGraph.topology.randomNodes)} random nodes, ${word(fakeMoves.flatMap((row) => row.intents).length)} intent constructors, ${word(operationCount("attack"))} attacks, ${word(operationCount("attackHitCount"))} hit count, Frail, and Strength are closed.`);
  has(readme, `The event slice closes ${eventInvocations.denominator} invocation sites, ${word(eventSummary.eventTurnDirectOperations)} direct gameplay operations, and ${word(eventSummary.noOpProofs)} explicit no-op proofs with zero unresolved.`);
  has(readme, `deterministic schema ${JSON.parse(readFileSync(new URL("../data/encounter-facts-v0.111.0.json", import.meta.url))).schemaVersion} compact projection`);
  has(readme, `(schema ${artifact.schemaVersion} raw source facts)`);

  has(worldModel, `Schema ${artifact.schemaVersion} is the E2d1a boundary`);
  has(worldModel, `exact metadata inheritance closure for all ${topology.behaviorClasses} behavior graph owners`);
  has(worldModel, `The ${summary.intentConstructorSites} constructor sites contain ${summary.requiredIntentArguments} required arguments`);
  has(worldModel, `separately count ${summary.intentConstructorSites} classified constructors and ${summary.requiredIntentArguments} resolved arguments`);
  has(worldModel, `Every one of the ${count(invocations.directDenominator)} direct \`call\`, \`callvirt\`, and \`newobj\` sites in the ${summary.asyncActions} current \`MoveNext\` bodies, plus ${invocations.helperDenominator} unique recursively reached helper sites`);
  has(worldModel, `The combined ${count(invocations.denominator)}-site census contains ${count(invocations.vocabularySize)} exact source symbols and resolves ${invocations.classificationCounts.normalizedGameplayOperation} / ${count(invocations.classificationCounts.traversedGameplayHelper)} / ${count(invocations.classificationCounts.provenNonGameplayPlumbing)} sites respectively`);
  has(worldModel, `The ${count(invocations.denominator)}-site combined invocation census (${count(invocations.directDenominator)} direct plus ${invocations.helperDenominator} helper), ${summary.directSinkSites} direct-operation census`);
  has(worldModel, `separately from ${count(summary.requiredSemanticFields)}/${count(summary.resolvedSemanticFields)} required semantic fields`);
  has(worldModel, `The physical domain is ${topology.behaviorClasses} owners/graphs and ${topology.moveConstructors} registrations. ${word(eventSummary.physicalOwners)[0].toUpperCase()}${word(eventSummary.physicalOwners).slice(1)} owners and ${word(eventSummary.physicalRegistrations)} registrations are event additions`);
  has(worldModel, `Fake Merchant contributes ${word(fake.registrationIds.length)} localized moves, ${word(fakeGraph.topology.randomNodes)} random nodes/${word(fakeGraph.topology.randomBranches)} random branches, ${word(fakeMoves.flatMap((row) => row.intents).length)} intent sites/${word(eventSummary.eventIntentArguments)} arguments, ${word(operationCount("attack"))} attacks, ${word(operationCount("attackHitCount"))} attack hit-count, Frail, and Strength.`);
  has(worldModel, `The event subset classifies ${eventInvocations.denominator} calls (${word(eventInvocations.classificationCounts.normalizedGameplayOperation)} gameplay, ${eventInvocations.classificationCounts.traversedGameplayHelper} traversed helpers, ${eventInvocations.classificationCounts.provenNonGameplayPlumbing} narrow non-gameplay plumbing)`);
  has(worldModel, `projects ${word(eventSummary.classifications)} classification facts, ${word(behavior.eventDependencies.filter((row) => row.status === "unresolved").length)} unresolved lifecycle dependency facts`);
  has(worldModel, `the ${count(invocations.denominator)}-invocation census`);
});
