import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

import { normalizeMonsterWireIdForState } from "./state.mjs";
import { buildEncounterPresentation } from "./source-presentation.mjs";

const DEFAULT_PROJECTION = new URL("../data/encounter-facts-v0.111.0.json", import.meta.url);
const GAME_VERSION = "v0.111.0";
const DLL_SHA256 = "2b40d2df538db1ceb5fa48d958c80ab730ada1e07db88a870aff01a661768b9f";
const SUPPORTED_SCHEMAS = new Set([10, 11]);
const REQUIRED_SOURCE_SECTIONS = [
  "behaviorOwners", "encounters", "eventScripts", "eventTurnBehavior", "graphs", "hpPipeline",
  "initialState", "lifecycle", "models", "monsters", "moves", "observationIdentities",
  "placement", "production", "randomSelection", "scaling", "stateRules", "states",
];
const REQUIRED_JOINS = [
  "encounterToMonster", "stateToModel", "registrationToBehaviorOwner", "graphTopology",
  "operationModel", "legacyToCanonical", "factToEvidence", "encounterPlacement",
  "eventEncounterLinkage", "observationIdentity",
];
const ROSTER_KINDS = new Set(["fixed", "sequence", "uniformChoice", "filteredChoice"]);
const MAX_VIEW_BYTES = 600_000;

export class SourceProjectionError extends Error {
  constructor(message) { super(`source projection unavailable: ${message}`); this.name = "SourceProjectionError"; }
}
function fail(message) { throw new SourceProjectionError(message); }
function object(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(`${label} must be an object`);
  return value;
}
function array(value, label) { if (!Array.isArray(value)) fail(`${label} must be an array`); return value; }
function string(value, label) {
  if (typeof value !== "string" || !value || value.length > 16_384) fail(`${label} must be a non-empty bounded string`);
  return value;
}
function boolean(value, label) { if (typeof value !== "boolean") fail(`${label} must be boolean`); return value; }
function integer(value, label, minimum = 0) {
  if (!Number.isSafeInteger(value) || value < minimum) fail(`${label} must be an integer >= ${minimum}`);
  return value;
}
function strings(value, label, unique = false) {
  const result = array(value, label).map((item, index) => string(item, `${label}[${index}]`));
  if (unique && new Set(result).size !== result.length) fail(`${label} contains a duplicate`);
  return result;
}
function uniqueIndex(rows, key, label) {
  const result = new Map();
  array(rows, label).forEach((row, index) => {
    object(row, `${label}[${index}]`);
    const id = string(row[key], `${label}[${index}].${key}`);
    if (result.has(id)) fail(`duplicate ${label} ${id}`);
    result.set(id, row);
  });
  return result;
}
function expect(index, id, label) { if (!index.has(id)) fail(`missing ${label} join ${id}`); return index.get(id); }
function version(value) { return String(value ?? "").trim().toLowerCase(); }
function sortedJson(value) {
  if (Array.isArray(value)) return value.map(sortedJson);
  if (value && typeof value === "object") return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortedJson(value[key])]));
  return value;
}
function payloadDigest(value) { return createHash("sha256").update(JSON.stringify(sortedJson(value))).digest("hex"); }
function freeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value); for (const child of Object.values(value)) freeze(child);
  }
  return value;
}

/** Validate and clone JSON; returned views never share mutable projection objects. */
function jsonValue(value, label = "value", depth = 0) {
  if (depth > 32) fail(`${label} exceeds maximum depth`);
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "string") { if (value.length > 16_384) fail(`${label} is too long`); return value; }
  if (typeof value === "number") { if (!Number.isFinite(value)) fail(`${label} is not finite`); return value; }
  if (Array.isArray(value)) {
    if (value.length > 10_000) fail(`${label} array is too large`);
    return value.map((item, index) => jsonValue(item, `${label}[${index}]`, depth + 1));
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value); if (entries.length > 1_000) fail(`${label} object is too large`);
    const result = {};
    for (const [key, item] of entries) {
      if (key.length > 256) fail(`${label} has an overlong key`);
      result[key] = jsonValue(item, `${label}.${key}`, depth + 1);
    }
    return result;
  }
  fail(`${label} is not JSON-safe`);
}
const BULK_KEYS = new Set([
  "provenance", "methodBodySha256", "normalizedSliceSha256", "symbolSignature",
  "sinkSymbolSignature", "constructorSymbolSignature", "sourceType", "ownerSourceType",
  "behaviorOwnerSourceType", "eventSourceType", "method", "action",
]);
function compact(value, label = "detail", depth = 0) {
  if (depth > 24) fail(`${label} exceeds maximum depth`);
  if (value === null || typeof value !== "object") return jsonValue(value, label);
  if (Array.isArray(value)) return value.map((item, index) => compact(item, `${label}[${index}]`, depth + 1));
  object(value, label); const result = {};
  for (const [key, item] of Object.entries(value)) if (!BULK_KEYS.has(key)) result[key] = compact(item, `${label}.${key}`, depth + 1);
  return result;
}
function contains(value, wanted) {
  if (typeof value === "string") return wanted.has(value);
  if (Array.isArray(value)) return value.some((item) => contains(item, wanted));
  return !!value && typeof value === "object" && Object.values(value).some((item) => contains(item, wanted));
}

const LIFECYCLE_RELATION_MODEL_FIELDS = ["source", "subscriber", "publisherBody", "target"];
const MONSTER_MODEL_TOKEN = /(?:^|[^A-Z0-9_.])(MONSTER\.[A-Z0-9_]+)(?=$|[^A-Z0-9_.])/g;
const LIFECYCLE_RECORD_FIELDS = new Set([
  "ownerModel", "ownerModels", "canonicalModel", "applicableConcreteModels",
  "canonicalEncounter", "canonicalEvent", "eventId", "power", "producerPower", "listener", "sourceSignals",
  "phaseSystemId", "deathProductionId", "relationshipId", "policyId", "subscriptionId", "cleanupId", "doomContractId",
]);
const LIFECYCLE_OPERATION_GROUPS = ["orderedEffects", "orderedPerPlayer"];
/** Extract only explicit canonical model tokens from schema-defined relationship identity fields. */
function lifecycleRelationModels(row) {
  const result = new Set();
  for (const key of LIFECYCLE_RELATION_MODEL_FIELDS) {
    if (typeof row[key] !== "string") continue;
    for (const match of row[key].matchAll(MONSTER_MODEL_TOKEN)) result.add(match[1]);
  }
  return result;
}

/** Operations are traversed only through schema-typed lifecycle operation collections. */
function lifecycleOperations(row) {
  const result = [];
  for (const key of LIFECYCLE_OPERATION_GROUPS) {
    if (Array.isArray(row?.[key])) result.push(...row[key].filter((operation) => operation && typeof operation === "object" && !Array.isArray(operation)));
  }
  for (const key of ["transitions", "branches"]) if (Array.isArray(row?.[key])) {
    for (const branch of row[key]) if (branch && typeof branch === "object" && !Array.isArray(branch)) {
      if (Array.isArray(branch.orderedEffects)) result.push(...branch.orderedEffects.filter((operation) => operation && typeof operation === "object" && !Array.isArray(operation)));
    }
  }
  return result;
}

/** A record boundary is schema-shaped; condition/expression objects are never candidates. */
function isLifecycleMechanicRecord(row) {
  if (!row || typeof row !== "object" || Array.isArray(row)) return false;
  if ([...LIFECYCLE_RECORD_FIELDS].some((key) => key in row)) return true;
  return [...LIFECYCLE_OPERATION_GROUPS, "transitions", "branches"].some((key) => Array.isArray(row[key]));
}

/**
 * Normalize array and object mechanic families into stable path-tagged records.
 * A selected record is later restored at the same keyed path with its full payload.
 */
function lifecycleMechanicUnits(mechanics, excludedFamilies = new Set()) {
  const result = [];
  const visit = (value, path) => {
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        if (isLifecycleMechanicRecord(item)) result.push({ path: [...path, index], row: item });
        else if (item && typeof item === "object") visit(item, [...path, index]);
      });
      return;
    }
    if (!value || typeof value !== "object") return;
    if (isLifecycleMechanicRecord(value)) { result.push({ path, row: value }); return; }
    for (const [key, item] of Object.entries(value)) if (item && typeof item === "object") visit(item, [...path, key]);
  };
  for (const [family, value] of Object.entries(mechanics ?? {})) if (!excludedFamilies.has(family)) visit(value, [family]);
  return result;
}

/** Rebuild only selected records while preserving object keys and compacting array indices. */
function selectedLifecycleMechanicTree(value, selected) {
  if (selected.has(value)) return compact(value);
  if (Array.isArray(value)) {
    const rows = value.map((item) => selectedLifecycleMechanicTree(item, selected)).filter((item) => item !== undefined);
    return rows.length ? rows : undefined;
  }
  if (!value || typeof value !== "object") return undefined;
  const entries = Object.entries(value).map(([key, item]) => [key, selectedLifecycleMechanicTree(item, selected)])
    .filter(([, item]) => item !== undefined);
  return entries.length ? Object.fromEntries(entries) : undefined;
}

function validateReadiness(readiness, metadata) {
  object(readiness, "payload.readiness");
  const scopes = object(readiness.runtimeScopes, "readiness.runtimeScopes");
  const projection = object(scopes.encounterProjection, "readiness.runtimeScopes.encounterProjection");
  if (boolean(projection.ready, "encounterProjection.ready") !== true || string(projection.status, "encounterProjection.status") !== "complete") fail("encounterProjection is not complete and ready");
  const joins = strings(projection.requiredJoins, "encounterProjection.requiredJoins", true);
  for (const join of REQUIRED_JOINS) if (!joins.includes(join)) fail(`encounterProjection omits required join ${join}`);
  const requiredFamilies = new Set(strings(projection.requiredCoverageFamilies, "encounterProjection.requiredCoverageFamilies", true));
  for (const [name, status] of [...Object.entries(scopes), ["global", readiness.global], ["root", readiness.root]]) {
    object(status, `readiness.${name}`);
    boolean(status.ready, `readiness.${name}.ready`);
    const label = string(status.status, `readiness.${name}.status`);
    if (!new Set(["complete", "incomplete"]).has(label)) fail(`malformed component status ${name}`);
    if ((label === "complete") !== status.ready) fail(`component status/ready mismatch ${name}`);
    if ("reasonRefs" in status) strings(status.reasonRefs, `readiness.${name}.reasonRefs`, true);
  }
  for (const [index, row] of array(metadata.requiredCoverage, "metadata.requiredCoverage").entries()) {
    object(row, `requiredCoverage[${index}]`); const family = string(row.family, `coverage[${index}].family`);
    const status = string(row.status, `${family}.status`); const numerator = integer(row.numerator, `${family}.numerator`);
    const denominator = integer(row.denominator, `${family}.denominator`); const unresolved = integer(row.unresolved, `${family}.unresolved`);
    const classifiedTitleGap = family === "moveTitlesEnglish" && status === "classified"
      && numerator + unresolved === denominator && unresolved > 0;
    if (status !== "complete" && !classifiedTitleGap) fail(`malformed coverage status ${family}`);
    if (status === "complete" && (numerator !== denominator || unresolved !== 0)) fail(`claimed-complete-but-unresolved coverage ${family}`);
    if (requiredFamilies.has(family) && status !== "complete" && !classifiedTitleGap) fail(`required coverage ${family} is incomplete`);
  }
}
function validateRoster(selection, label, monsters, result = new Set()) {
  object(selection, label); const kind = string(selection.kind, `${label}.kind`);
  if (!ROSTER_KINDS.has(kind)) fail(`${label} has unsupported kind ${kind}`);
  if (kind === "fixed") { const model = string(selection.model, `${label}.model`); expect(monsters, model, "roster monster"); result.add(model); }
  else if (kind === "sequence") {
    if (string(selection.order, `${label}.order`) !== "fixed") fail(`${label} has unsupported order`);
    array(selection.children, `${label}.children`).forEach((row, index) => validateRoster(row, `${label}.children[${index}]`, monsters, result));
  } else {
    array(selection.choices, `${label}.choices`).forEach((row, index) => validateRoster(row, `${label}.choices[${index}]`, monsters, result));
    if (kind === "filteredChoice") { integer(selection.count, `${label}.count`, 1); string(selection.constraint, `${label}.constraint`); string(selection.draws, `${label}.draws`); }
  }
  return result;
}

function validateProjection(root) {
  object(root, "projection"); const schema = integer(root.schemaVersion, "schemaVersion", 1);
  if (!SUPPORTED_SCHEMAS.has(schema)) fail(`unsupported projection schema ${schema}`);
  const authority = object(root.authority, "authority");
  if (authority.sourceFacts !== "rawSource" || authority.observedRuntimeIdentity !== "sourceDerivedAdapterVocabularyNoObservedSamples"
      || authority.legacyAnnotations !== "legacyCommunityAnnotation" || authority.silentMerge !== false
      || authority.conflictPolicy !== "explicitNoPrecedence") fail("authority lanes do not match the checked contract");
  const metadata = object(root.metadata, "metadata"); const generator = object(metadata.generator, "metadata.generator");
  if (string(generator.name, "generator.name") !== "sts2-encounter-facts" || !new RegExp(`^${schema}\\.[0-9]+\\.[0-9]+$`).test(string(generator.version, "generator.version"))) fail("generator major does not correspond to projection schema");
  const game = object(metadata.game, "metadata.game");
  if (version(string(game.version, "game.version")) !== GAME_VERSION || version(string(game.branch, "game.branch")) !== GAME_VERSION) fail("wrong game authority version");
  const dll = array(metadata.embeddedSourceInputManifest, "embeddedSourceInputManifest").find((row) => row?.path === "data_sts2_linuxbsd_x86_64/sts2.dll");
  if (!dll || dll.sha256 !== DLL_SHA256) fail("pinned game DLL authority is missing or wrong");
  const payload = object(root.payload, "payload");
  if (string(metadata.payloadSha256, "metadata.payloadSha256") !== payloadDigest(payload)) fail("canonical payload digest mismatch");
  const source = object(payload.sourceFacts, "payload.sourceFacts");
  for (const section of REQUIRED_SOURCE_SECTIONS) if (!(section in source)) fail(`missing source section ${section}`);
  validateReadiness(object(payload.readiness, "payload.readiness"), metadata);
  const lifecycleStatuses = schema === 10 ? new Set(["sourceCompleteE2d2a"]) : new Set(["sourceCompleteE2d2a", "sourceCompleteE2Lifecycle", "sourceComplete"]);
  if (!lifecycleStatuses.has(string(object(source.lifecycle, "lifecycle").status, "lifecycle.status"))) fail("lifecycle component status is not supported");
  if (string(object(object(source.production, "production").productionSemantics, "production.productionSemantics").status, "production.status") !== "sourceComplete") fail("production component is not source-complete");
  const lifecycleMechanics = source.lifecycle.mechanics == null ? {} : object(source.lifecycle.mechanics, "lifecycle.mechanics");
  if (schema >= 11 && source.lifecycle.mechanics == null) fail("schema 11 lifecycle mechanics are missing");
  for (const [family, value] of Object.entries(lifecycleMechanics)) {
    jsonValue(value, `lifecycle.mechanics.${family}`);
    if (Array.isArray(value)) value.forEach((row, index) => object(row, `lifecycle.mechanics.${family}[${index}]`));
  }
  for (const [label, summary] of [["event scripts", source.eventScripts.invocationSummary], ["event turns", source.eventTurnBehavior.invocationSummary]]) {
    object(summary, `${label}.invocationSummary`); const denominator = integer(summary.denominator, `${label}.denominator`);
    if (integer(summary.resolved, `${label}.resolved`) !== denominator || integer(summary.unresolved, `${label}.unresolved`) !== 0) fail(`claimed-complete-but-unresolved ${label} component`);
  }

  const ordinary = array(object(source.encounters, "encounters").ordinary, "encounters.ordinary");
  const events = array(source.encounters.event, "encounters.event"); const encounters = [...ordinary, ...events];
  const encounterIndex = uniqueIndex(encounters, "canonicalId", "encounters");
  const monsterIndex = uniqueIndex(source.monsters, "canonicalModel", "monsters");
  uniqueIndex(source.monsters, "canonicalId", "monster local IDs");
  const ownerByFact = uniqueIndex(source.behaviorOwners, "factId", "behavior owners");
  const ownerByModel = uniqueIndex(source.behaviorOwners, "canonicalMonster", "behavior owner models");
  const moveIndex = uniqueIndex(source.moves, "canonicalId", "moves");
  const graphIndex = uniqueIndex(source.graphs, "graphId", "graphs");
  const stateIndex = uniqueIndex(source.states, "stateId", "states");
  const cardIndex = uniqueIndex(object(source.models, "models").cards, "canonicalId", "card models");
  const powerIndex = uniqueIndex(source.models.powers, "canonicalId", "power models");
  const factRows = uniqueIndex(payload.factReferences, "factId", "fact references");
  const evidenceIndex = uniqueIndex(payload.evidence, "evidenceId", "evidence");

  const sourceFactIds = new Set();
  (function collect(value) {
    if (Array.isArray(value)) { value.forEach(collect); return; }
    if (!value || typeof value !== "object") return;
    if ("factId" in value) { const id = string(value.factId, "source factId"); if (sourceFactIds.has(id)) fail(`duplicate source fact ID ${id}`); sourceFactIds.add(id); }
    Object.values(value).forEach(collect);
  })(source);
  for (const id of sourceFactIds) expect(factRows, id, "fact reference");
  for (const [id, row] of factRows) {
    if (!new Set(["source", "legacy"]).has(string(row.lane, `${id}.lane`))) fail(`invalid lane ${id}`);
    for (const ref of strings(row.evidenceRefs, `${id}.evidenceRefs`, true)) {
      const evidence = expect(evidenceIndex, ref, "evidence"); if (evidence.lane !== row.lane) fail(`evidence lane mismatch ${id}`);
      for (const pointer of array(evidence.pointers, `${ref}.pointers`)) {
        object(pointer, `${ref}.pointer`); string(pointer.jsonPointer, `${ref}.jsonPointer`);
        if (!/^[0-9a-f]{64}$/.test(string(pointer.valueSha256, `${ref}.valueSha256`))) fail(`invalid evidence digest ${ref}`);
      }
    }
  }

  for (const encounter of encounters) {
    string(encounter.factId, `${encounter.canonicalId}.factId`); string(encounter.title, `${encounter.canonicalId}.title`); string(encounter.sourceType, `${encounter.canonicalId}.sourceType`);
    const expectedKind = events.includes(encounter) ? "event" : "ordinary"; if (encounter.kind !== expectedKind) fail(`${encounter.canonicalId} has wrong kind`);
    const roster = object(encounter.initialRoster, `${encounter.canonicalId}.initialRoster`); const cardinality = object(roster.cardinality, `${encounter.canonicalId}.cardinality`);
    const minimum = integer(cardinality.minimum, `${encounter.canonicalId}.minimum`); const maximum = integer(cardinality.maximum, `${encounter.canonicalId}.maximum`);
    if (minimum > maximum) fail(`${encounter.canonicalId} has inverted cardinality`);
    const initial = validateRoster(roster.selection, `${encounter.canonicalId}.selection`, monsterIndex);
    const possible = new Set(strings(encounter.possibleMonsters, `${encounter.canonicalId}.possibleMonsters`, true));
    const produced = strings(encounter.producedMonsters, `${encounter.canonicalId}.producedMonsters`, true);
    for (const model of [...initial, ...produced]) { expect(monsterIndex, model, "encounter monster"); if (!possible.has(model)) fail(`${encounter.canonicalId} possibleMonsters omits ${model}`); }
    for (const pool of array(encounter.productionPools, `${encounter.canonicalId}.productionPools`)) {
      object(pool, "production pool"); string(pool.poolId, "production pool ID");
      for (const model of strings(pool.members, "production pool members", true)) { expect(monsterIndex, model, "production pool monster"); if (!produced.includes(model)) fail(`${encounter.canonicalId} pool has undeclared body ${model}`); }
    }
  }
  for (const monster of source.monsters) {
    if (monster.canonicalModel !== `MONSTER.${monster.canonicalId}`) fail(`monster ID mismatch ${monster.canonicalModel}`);
    string(monster.factId, `${monster.canonicalModel}.factId`); string(monster.sourceType, `${monster.canonicalModel}.sourceType`); string(monster.reachability, `${monster.canonicalModel}.reachability`);
    const name = object(monster.name, `${monster.canonicalModel}.name`);
    if (name.kind === "localizedText") string(name.text, `${monster.canonicalModel}.name.text`);
    else if (name.kind === "localizedTemplate") { string(name.template, `${monster.canonicalModel}.name.template`); jsonValue(object(name.inputs, `${monster.canonicalModel}.name.inputs`), `${monster.canonicalModel}.name.inputs`); }
    else fail(`unsupported monster name ${monster.canonicalModel}`);
    jsonValue(object(monster.initialHp, `${monster.canonicalModel}.initialHp`), `${monster.canonicalModel}.initialHp`);
  }
  for (const state of source.states) {
    expect(monsterIndex, string(state.canonicalModel, `${state.stateId}.canonicalModel`), "state model"); string(state.hpState, `${state.stateId}.hpState`);
    const display = object(state.displayName, `${state.stateId}.displayName`);
    if (display.kind === "localizedText") string(display.text, `${state.stateId}.displayName.text`);
    else if (display.kind === "localizedTemplate") { string(display.template, `${state.stateId}.displayName.template`); jsonValue(object(display.inputs, `${state.stateId}.displayName.inputs`), `${state.stateId}.displayName.inputs`); }
    else fail(`unsupported state name ${state.stateId}`);
  }
  for (const owner of source.behaviorOwners) {
    const ownerModel = string(owner.canonicalMonster, `${owner.factId}.canonicalMonster`);
    const concrete = strings(owner.applicableConcreteModels, `${owner.factId}.applicableModels`, true);
    if (!monsterIndex.has(ownerModel) && !(owner.classification === "abstractBehavior" && owner.applicabilityKind === "inheritedBehavior")) fail(`unresolved behavior owner ${ownerModel}`);
    if (!concrete.length) fail(`behavior owner has no concrete applicability ${ownerModel}`);
    concrete.forEach((model) => expect(monsterIndex, model, "behavior applicable monster"));
  }
  const operationIds = new Set();
  for (const move of source.moves) {
    const owner = expect(ownerByFact, string(move.ownerRef, `${move.canonicalId}.ownerRef`), "move owner");
    if (owner.canonicalMonster !== move.canonicalMonster) fail(`move owner mismatch ${move.canonicalId}`);
    expect(graphIndex, string(move.graphId, `${move.canonicalId}.graphId`), "move graph");
    if (string(move.canonicalMonster, `${move.canonicalId}.monster`) !== owner.canonicalMonster) fail(`move canonical owner mismatch ${move.canonicalId}`);
    strings(move.applicableConcreteModels, `${move.canonicalId}.applicableModels`, true).forEach((model) => expect(monsterIndex, model, "move applicable monster"));
    object(move.title, `${move.canonicalId}.title`); string(move.title.classification, `${move.canonicalId}.title.classification`);
    array(move.intents, `${move.canonicalId}.intents`).forEach((intent, index) => { object(intent, "intent"); string(intent.kind, `intent[${index}].kind`); jsonValue(intent, "intent"); });
    for (const operation of array(move.operations, `${move.canonicalId}.operations`)) {
      object(operation, "operation"); const id = string(operation.operationId, "operationId"); if (operationIds.has(id)) fail(`duplicate operation ID ${id}`); operationIds.add(id);
      string(operation.kind, `${id}.kind`);
      if ("sourceOrder" in operation) integer(operation.sourceOrder, `${id}.sourceOrder`);
      if (typeof operation.model === "string") {
        const index = operation.model.startsWith("POWER.") ? powerIndex : operation.model.startsWith("CARD.") ? cardIndex : operation.model.startsWith("MONSTER.") ? monsterIndex : null;
        if (index) expect(index, operation.model, "operation model");
      }
      jsonValue(operation, id);
    }
  }
  for (const graph of source.graphs) {
    expect(ownerByModel, string(graph.canonicalMonster, `${graph.graphId}.monster`), "graph owner"); const nodes = uniqueIndex(graph.nodes, "nodeId", `${graph.graphId} nodes`);
    if (typeof graph.initial === "string") expect(nodes, string(graph.initial, `${graph.graphId}.initial`), "initial graph node");
    else for (const initial of strings(graph.initial, `${graph.graphId}.initial`, true)) expect(nodes, initial, "initial graph node");
    for (const node of graph.nodes) if (node.kind === "move" && !source.moves.some((move) => move.graphId === graph.graphId && move.stateId === node.stateId)) fail(`graph move has no registration ${node.nodeId}`);
    const stateCollection = object(graph.stateCollection, `${graph.graphId}.stateCollection`); const orderedNodes = strings(stateCollection.orderedNodes, `${graph.graphId}.stateCollection.orderedNodes`, true);
    orderedNodes.forEach((id) => expect(nodes, id, "state collection node")); if (integer(stateCollection.cardinality, `${graph.graphId}.stateCollection.cardinality`) !== orderedNodes.length) fail(`state collection cardinality mismatch ${graph.graphId}`);
    jsonValue(object(graph.topology, `${graph.graphId}.topology`), `${graph.graphId}.topology`);
    for (const edge of array(graph.edges, `${graph.graphId}.edges`)) { expect(nodes, string(edge.from, "edge.from"), "graph edge source"); expect(nodes, string(edge.to, "edge.to"), "graph edge target"); string(edge.kind, "edge.kind"); jsonValue(edge, "graph edge"); }
  }

  const initialContracts = uniqueIndex(source.initialState.runtimeStateContracts, "contractId", "initial runtime contracts");
  const initialOwnerIndex = uniqueIndex(source.initialState.owners, "ownerModel", "initial owner IDs");
  const powerOwnerIds = new Set();
  for (const power of array(source.initialState.powerHookClosure, "initial Power hooks")) {
    expect(powerIndex, string(power.canonicalPower, "initial Power hook model"), "initial Power hook model"); powerOwnerIds.add(`POWER_OWNER.${power.canonicalPower}`);
    for (const hook of array(power.hooks, `${power.canonicalPower}.hooks`)) strings(hook.effectFactRefs, `${power.canonicalPower}.${hook.hook}.effectFactRefs`, true).forEach((ref) => expect(factRows, ref, "initial Power effect fact"));
  }
  for (const fact of array(source.initialState.facts, "initial state facts")) {
    const owner = string(fact.ownerModel, `${fact.factId}.ownerModel`); if (!initialOwnerIndex.has(owner) && !powerOwnerIds.has(owner)) fail(`missing initial fact owner join ${owner}`);
    strings(fact.applicableModels, `${fact.factId}.applicableModels`, true).forEach((model) => expect(monsterIndex, model, "initial applicable model"));
    const order = object(fact.order, `${fact.factId}.order`); integer(order.stageOrder, `${fact.factId}.stageOrder`); integer(order.sourceOrder, `${fact.factId}.sourceOrder`);
    string(fact.stage, `${fact.factId}.stage`); string(fact.trigger, `${fact.factId}.trigger`); object(fact.effect, `${fact.factId}.effect`); object(fact.condition, `${fact.factId}.condition`); object(fact.baseValue, `${fact.factId}.baseValue`);
    for (const ref of [...strings(fact.sourceStateInputs, `${fact.factId}.sourceStateInputs`, true), ...strings(fact.finalValueContract.runtimeModifierInputs, `${fact.factId}.runtimeModifierInputs`, true)]) expect(initialContracts, ref, "initial runtime input");
    if (typeof fact.effect.model === "string" && fact.effect.model.startsWith("POWER.")) expect(powerIndex, fact.effect.model, "initial Power model");
  }
  for (const owner of array(source.initialState.owners, "initial state owners")) {
    const ownerId = string(owner.ownerModel, `${owner.factId}.ownerModel`);
    if (ownerId.startsWith("MONSTER.")) expect(monsterIndex, ownerId, "initial owner model");
    strings(owner.applicableModels, `${owner.factId}.applicableModels`, true).forEach((model) => expect(monsterIndex, model, "initial owner applicable model"));
    strings(owner.factRefs, `${owner.factId}.factRefs`, true).forEach((ref) => expect(factRows, ref, "initial owner fact"));
  }

  const semantics = object(source.production.productionSemantics, "production semantics");
  const productionPools = uniqueIndex(semantics.pools, "poolId", "production pools");
  for (const pool of semantics.pools) strings(pool.candidateModels, `${pool.poolId}.candidateModels`, true).forEach((model) => expect(monsterIndex, model, "production candidate model"));
  const postAddEffects = uniqueIndex(semantics.postAddEffects, "effectId", "post-add effects");
  for (const effect of semantics.postAddEffects) if (typeof effect.targetRef === "string" && effect.targetRef.startsWith("POWER.")) expect(powerIndex, effect.targetRef, "post-add Power");
  const slotStrategies = uniqueIndex(semantics.slotStrategies, "slotStrategyId", "slot strategies");
  const productionContracts = uniqueIndex(semantics.runtimeStateContracts, "contractId", "production runtime contracts");
  const producers = uniqueIndex(semantics.producers, "producerId", "producers"); const productionAttemptIds = new Set();
  const encounterWorldIds = new Set([...encounterIndex.keys()].map((id) => `ENCOUNTER.${id}`));
  const lifecyclePowerOperationKinds = new Set(["applyPowerByRef", "applyTargetedPower", "removePower", "skipPowerApplication"]);
  const validateLifecycleEffectModels = (effects, label) => array(effects ?? [], label).forEach((effect, index) => {
    object(effect, `${label}[${index}]`);
    const effectLabel = `${label}[${index}]`;
    if (typeof effect.model === "string") {
      const modelIndex = effect.model.startsWith("MONSTER.") ? monsterIndex : effect.model.startsWith("POWER.") ? powerIndex : effect.model.startsWith("CARD.") ? cardIndex : null;
      if (!modelIndex) fail(`${effectLabel} has unsupported model reference ${effect.model}`);
      expect(modelIndex, effect.model, "lifecycle effect model");
    }
    if (schema >= 11 && lifecyclePowerOperationKinds.has(effect.kind)) {
      if (typeof effect.power !== "string" || !effect.power.startsWith("POWER.")) fail(`${effectLabel}.${effect.kind} must use the schema power field`);
      // applyTargetedPower may create a Power outside the compact model seed rows;
      // owner-Power refs/removals must resolve through the checked model vocabulary.
      if (effect.kind !== "applyTargetedPower") expect(powerIndex, effect.power, "lifecycle effect Power");
    } else if (typeof effect.power === "string" && powerIndex.has(effect.power)) {
      expect(powerIndex, effect.power, "lifecycle effect Power");
    }
    if (typeof effect.retainedPower === "string") expect(powerIndex, effect.retainedPower, "lifecycle retained Power");
    for (const key of ["owner", "amountRef", "source"]) {
      if (typeof effect[key] === "string" && effect[key].startsWith("POWER.")) {
        const reference = string(effect[key], `${effectLabel}.${key}`);
        if (!/^POWER\.[A-Z0-9_]+(?:\.[A-Za-z0-9_]+)?$/.test(reference)) fail(`${effectLabel}.${key} has malformed Power reference`);
      }
    }
  });
  for (const { path, row } of lifecycleMechanicUnits(lifecycleMechanics)) {
    const label = `lifecycle.mechanics.${path.map((part, index) => typeof part === "number" ? `[${part}]` : index ? `.${part}` : part).join("")}`;
    if (typeof row.ownerModel === "string") expect(monsterIndex, row.ownerModel, "lifecycle owner model");
    if (typeof row.canonicalModel === "string") expect(monsterIndex, row.canonicalModel, "lifecycle canonical model");
    for (const key of ["ownerModels", "applicableConcreteModels"]) if (key in row) strings(row[key], `${label}.${key}`, true).forEach((model) => expect(monsterIndex, model, "lifecycle model"));
    if (typeof row.canonicalEncounter === "string" && !encounterWorldIds.has(row.canonicalEncounter)) fail(`${label} has unresolved encounter ${row.canonicalEncounter}`);
    if (typeof row.producerPower === "string") expect(powerIndex, row.producerPower, "lifecycle producer Power");
    if (typeof row.listener === "string" && row.listener.startsWith("POWER.")) expect(powerIndex, row.listener, "lifecycle listener Power");
    if ("power" in row) expect(powerIndex, string(row.power, `${label}.power`), "lifecycle Power");
    for (const key of LIFECYCLE_RELATION_MODEL_FIELDS) if (key in row) string(row[key], `${label}.${key}`);
    for (const model of lifecycleRelationModels(row)) expect(monsterIndex, model, "lifecycle relationship model");
    if (Array.isArray(row.sourceSignals)) row.sourceSignals.filter((ref) => typeof ref === "string" && ref.startsWith("POWER.")).forEach((ref) => expect(powerIndex, ref, "lifecycle signal Power"));
    validateLifecycleEffectModels(lifecycleOperations(row), `${label}.operations`);
  }
  for (const producer of semantics.producers) {
    if (!encounterWorldIds.has(string(producer.canonicalEncounter, `${producer.producerId}.canonicalEncounter`))) fail(`producer encounter join ${producer.producerId}`);
    expect(monsterIndex, string(producer.ownerModel, `${producer.producerId}.ownerModel`), "producer owner"); expect(moveIndex, string(producer.moveRef, `${producer.producerId}.moveRef`), "producer move"); expect(graphIndex, string(producer.graphRef, `${producer.producerId}.graphRef`), "producer graph");
    strings(producer.applicableConcreteModels, `${producer.producerId}.applicableModels`, true).forEach((model) => expect(monsterIndex, model, "producer applicable model"));
    for (const attempt of array(producer.attempts, `${producer.producerId}.attempts`)) {
      const attemptId = string(attempt.attemptId, `${producer.producerId}.attemptId`); if (productionAttemptIds.has(attemptId)) fail(`duplicate production attempt ${attemptId}`); productionAttemptIds.add(attemptId);
      expect(productionPools, string(attempt.poolRef, `${attemptId}.poolRef`), "production attempt pool"); expect(slotStrategies, string(attempt.slotStrategyRef, `${attemptId}.slotStrategyRef`), "production attempt slot");
      strings(attempt.postAddEffectRefs, `${attemptId}.postAddEffectRefs`, true).forEach((ref) => expect(postAddEffects, ref, "production post-add effect"));
    }
  }
  for (const dependency of array(semantics.dependencies, "production dependencies")) strings(dependency.affectedProducerRefs, `${dependency.factId}.affectedProducerRefs`, true).forEach((ref) => expect(producers, ref, "production dependency producer"));
  for (const applicability of array(source.production.applicability, "production applicability")) {
    if (!encounterWorldIds.has(string(applicability.canonicalEncounter, "production applicability encounter"))) fail("production applicability encounter join"); expect(monsterIndex, string(applicability.ownerModel, "production applicability owner"), "production applicability owner");
  }
  void productionContracts;

  const identities = object(source.observationIdentities, "observationIdentities"); const policy = object(identities.matchingPolicy, "matchingPolicy");
  if (boolean(policy.caseSensitive, "caseSensitive") !== true || boolean(policy.fuzzyMatching, "fuzzyMatching") !== false || boolean(policy.prefixStripping, "prefixStripping") !== false) fail("observation mapping is not exact");
  const wirePrefixes = array(policy.wirePrefixes, "matchingPolicy.wirePrefixes");
  if (wirePrefixes.length !== 1) fail("observation mapping must declare one monster wire prefix");
  const monsterWire = object(wirePrefixes[0], "matchingPolicy.wirePrefixes[0]");
  if (string(monsterWire.category, "monster wire category") !== "monsterModel" || string(monsterWire.prefix, "monster wire prefix") !== "MONSTER." || string(monsterWire.source, "monster wire source") !== "ModelId.Category") fail("observation mapping has an unsupported monster wire contract");
  if (array(identities.aliases, "identity aliases").length) fail("schema 10/11 observation aliases must be empty");
  const observationIndex = uniqueIndex(identities.entries, "observedId", "observation identities");
  const canonicalObservationIndex = new Map();
  for (const [observedId, row] of observationIndex) {
    const label = `observation identity ${observedId}`;
    const canonicalMonster = string(row.canonicalMonster, `${label}.canonicalMonster`);
    const monster = expect(monsterIndex, canonicalMonster, "observation canonical monster");
    if (string(row.identityKind, `${label}.identityKind`) !== "model") fail(`${label} has wrong kind`);
    if (string(row.factId, `${label}.factId`) !== `SOURCE.OBSERVED_IDENTITY.${canonicalMonster}`) fail(`${label} has wrong fact reference`);
    if (string(row.sourceType, `${label}.sourceType`) !== monster.sourceType) fail(`${label} has wrong source type`);
    if (!observedId.startsWith(monsterWire.prefix) || observedId.length === monsterWire.prefix.length) fail(`${label} is not an exact monster ModelId wire identity`);
    if (canonicalObservationIndex.has(canonicalMonster)) fail(`duplicate checked observation identity for ${canonicalMonster}`);
    canonicalObservationIndex.set(canonicalMonster, row);
  }
  for (const model of monsterIndex.keys()) expect(canonicalObservationIndex, model, "resolved observation identity");
  // prefixStripping:false governs matching in the checked source identity domain. The
  // reader has already normalized saved IDs; this separate bridge applies that same
  // exact reader conversion to validated projection rows and never changes policy.
  const stateModelObservationIndex = buildStateModelObservationIndex(observationIndex);
  for (const state of source.states) if (!array(identities.stateObservationContracts, "state observation contracts").some((row) => row.stateId === state.stateId && row.canonicalMonster === state.canonicalModel)) fail(`missing state observation contract ${state.stateId}`);

  const actIndex = uniqueIndex(source.placement.acts, "canonicalId", "acts"); const poolIndex = uniqueIndex(source.placement.pools, "poolId", "placement pools");
  for (const pool of source.placement.pools) expect(actIndex, string(pool.actId, `${pool.poolId}.actId`), "pool act");
  const placementFacts = uniqueIndex(source.placement.encounters, "factId", "encounter placements"); const placementByEncounter = new Map();
  for (const encounter of encounters) {
    const row = expect(placementFacts, `SOURCE.PLACEMENT.${encounter.canonicalId}`, "encounter placement");
    if (row.canonicalEncounter !== `ENCOUNTER.${encounter.canonicalId}`) fail(`placement join mismatch ${encounter.canonicalId}`);
    array(row.memberships, `${row.factId}.memberships`).forEach((membership) => {
      object(membership, "placement membership"); expect(actIndex, string(membership.actId, `${row.factId}.membership.actId`), "placement act"); expect(poolIndex, string(membership.poolId, `${row.factId}.membership.poolId`), "placement pool"); jsonValue(membership, "placement membership");
    }); placementByEncounter.set(encounter.canonicalId, row);
  }
  const eventTurns = uniqueIndex(source.eventTurnBehavior.encounters, "canonicalEncounter", "event turn encounters");
  const eventLinks = uniqueIndex(source.placement.eventLinkage, "canonicalEncounter", "event linkage");
  for (const encounter of events) {
    const turn = expect(eventTurns, encounter.canonicalId, "event turn"); if (turn.encounterRef !== encounter.factId) fail(`event turn join mismatch ${encounter.canonicalId}`);
    expect(graphIndex, string(turn.graphId, `${turn.factId}.graphId`), "event graph"); strings(turn.registrationRefs, `${turn.factId}.registrations`, true).forEach((ref) => expect(factRows, ref, "event registration"));
    const link = expect(eventLinks, `ENCOUNTER.${encounter.canonicalId}`, "event linkage"); if (turn.eventLinkRef !== link.factId || turn.canonicalEvent !== link.canonicalEvent) fail(`event linkage mismatch ${encounter.canonicalId}`);
  }
  for (const row of array(payload.knownUnknowns, "knownUnknowns")) {
    object(row, "known unknown"); string(row.unknownId, "unknownId"); if (string(row.status, `${row.unknownId}.status`) !== "unresolved") fail(`unsupported unknown status ${row.unknownId}`);
    string(row.scope, `${row.unknownId}.scope`); string(row.reasonCode, `${row.unknownId}.reasonCode`); string(row.detail, `${row.unknownId}.detail`); strings(row.affectedFactIds, `${row.unknownId}.affectedFactIds`);
  }
  const conflicts = uniqueIndex(payload.conflicts, "conflictId", "conflicts");
  for (const [id, row] of conflicts) {
    string(row.family, `${id}.family`); if (string(row.resolution, `${id}.resolution`) !== "unresolved") fail(`unsupported conflict resolution ${id}`);
    const left = object(row.left, `${id}.left`), right = object(row.right, `${id}.right`);
    if (left.lane !== "source" || right.lane !== "legacy") fail(`conflict lane mismatch ${id}`);
    expect(factRows, string(left.factId, `${id}.left.factId`), "conflict source fact"); expect(factRows, string(right.factId, `${id}.right.factId`), "conflict legacy fact"); jsonValue(left.value, `${id}.left.value`); jsonValue(right.value, `${id}.right.value`);
  }
  const comparisons = uniqueIndex(payload.laneComparisons, "comparisonId", "lane comparisons");
  for (const [id, row] of comparisons) {
    string(row.family, `${id}.family`); string(row.status, `${id}.status`); const left = object(row.left, `${id}.left`), right = object(row.right, `${id}.right`);
    if (left.lane !== "source" || right.lane !== "legacy") fail(`comparison lane mismatch ${id}`);
    expect(factRows, string(left.factId, `${id}.left.factId`), "comparison source fact"); expect(factRows, string(right.factId, `${id}.right.factId`), "comparison legacy fact"); jsonValue(left.value, `${id}.left.value`); jsonValue(right.value, `${id}.right.value`);
  }
  jsonValue(payload.legacyAnnotations, "legacyAnnotations");
  for (const key of ["archive", "current"]) for (const [index, row] of array(payload.legacyAnnotations[key], `legacyAnnotations.${key}`).entries()) {
    object(row, `legacyAnnotations.${key}[${index}]`); string(row.factId, `legacyAnnotations.${key}[${index}].factId`); expect(factRows, row.factId, "legacy annotation fact");
  }
  return { schema, metadata, payload, source, encounters, encounterIndex, monsterIndex, moveIndex, graphIndex, stateIndex, factRows, evidenceIndex, observationIndex, stateModelObservationIndex, placementByEncounter, eventTurns };
}

function rosterRecord(selection) {
  if (selection.kind === "fixed") return { kind: "fixed", model: selection.model };
  if (selection.kind === "sequence") return { kind: "sequence", order: selection.order, children: selection.children.map(rosterRecord) };
  const result = { kind: selection.kind, choices: selection.choices.map(rosterRecord) };
  if (selection.kind === "filteredChoice") Object.assign(result, { count: selection.count, constraint: selection.constraint, draws: selection.draws });
  return result;
}
function rosterModels(selection, result = new Set()) {
  if (selection.kind === "fixed") result.add(selection.model);
  for (const child of selection.children ?? selection.choices ?? []) rosterModels(child, result);
  return result;
}
function buildStateModelObservationIndex(observations) {
  const result = new Map();
  for (const [observedWireId, row] of observations) {
    const stateModelId = normalizeMonsterWireIdForState(observedWireId);
    if (typeof stateModelId !== "string" || !stateModelId) fail(`observation identity ${observedWireId} cannot be normalized for the state reader`);
    if (result.has(stateModelId)) fail(`observation reader-ID normalization collision ${stateModelId}`);
    result.set(stateModelId, row);
  }
  return result;
}

function observedRecord(state, exactObservations, stateModelObservations, selected, manual) {
  const status = state?.status === "combat" ? "combat" : state?.status === "last" ? "last" : "idle";
  const encounterId = typeof state?.encounterId === "string" ? state.encounterId : null; const bodies = [];
  if (!manual && encounterId === selected && Array.isArray(state?.monsterIds)) for (const observedId of state.monsterIds) {
    if (typeof observedId !== "string") continue;
    // State-reader IDs resolve through the shared normalization bridge. Exact wire
    // input remains supported only for explicit projection fixtures; neither path guesses.
    const identity = stateModelObservations.get(observedId) ?? exactObservations.get(observedId);
    bodies.push(identity
      ? { observedId, observedWireId: identity.observedId, canonicalModel: identity.canonicalMonster, resolved: true }
      : { observedId, observedWireId: null, canonicalModel: null, resolved: false });
  }
  const release = state?.releaseInfo && typeof state.releaseInfo === "object" ? {
    version: typeof state.releaseInfo.version === "string" ? state.releaseInfo.version : null,
    branch: typeof state.releaseInfo.branch === "string" ? state.releaseInfo.branch : null,
    commit: typeof state.releaseInfo.commit === "string" ? state.releaseInfo.commit : null,
  } : null;
  return { status, source: typeof state?.source === "string" ? state.source : null, freshness: "read-at-request", encounterId, observedBodies: bodies, installedVersion: release, versionMatches: release?.version ? version(release.version) === GAME_VERSION : null };
}

function makeCompiler(v) {
  const { schema, metadata, payload, source, encounterIndex, monsterIndex, factRows, evidenceIndex, observationIndex, stateModelObservationIndex, placementByEncounter, eventTurns } = v;
  const movesByModel = new Map(), statesByModel = new Map(), initialByModel = new Map(), graphByModel = new Map();
  for (const move of source.moves) for (const model of move.applicableConcreteModels) { const rows = movesByModel.get(model) ?? []; rows.push(move); movesByModel.set(model, rows); }
  for (const rows of movesByModel.values()) rows.sort((a, b) => a.ordinal - b.ordinal || a.canonicalId.localeCompare(b.canonicalId));
  for (const state of source.states) { const rows = statesByModel.get(state.canonicalModel) ?? []; rows.push(state); statesByModel.set(state.canonicalModel, rows); }
  for (const fact of source.initialState.facts) for (const model of fact.applicableModels) { const rows = initialByModel.get(model) ?? []; rows.push(fact); initialByModel.set(model, rows); }
  for (const rows of initialByModel.values()) rows.sort((a, b) => a.order.stageOrder - b.order.stageOrder || a.order.sourceOrder - b.order.sourceOrder || a.factId.localeCompare(b.factId));
  for (const graph of source.graphs) for (const model of graph.applicableConcreteModels) graphByModel.set(model, graph);
  function proofFor(id) {
    const row = expect(factRows, id, "proof"); return { factId: id, lane: row.lane, evidence: row.evidenceRefs.map((ref) => {
      const evidence = expect(evidenceIndex, ref, "proof evidence"); return { evidenceId: ref, artifactInput: evidence.artifactInput, lane: evidence.lane, pointers: evidence.pointers.map((pointer) => ({ ...pointer })) };
    }) };
  }
  function monsterRecord(model, closure) {
    const monster = monsterIndex.get(model); closure.add(monster.factId);
    const states = (statesByModel.get(model) ?? []).map((state) => { closure.add(state.factId); return { stateId: state.stateId, displayName: state.displayName.kind === "localizedText" ? { kind: "localizedText", text: state.displayName.text } : { kind: "localizedTemplate", template: state.displayName.template, inputs: compact(state.displayName.inputs) }, hpState: state.hpState, factId: state.factId, observation: "not-distinguishable-from-model-id-alone" }; });
    const initialState = (initialByModel.get(model) ?? []).map((fact) => { closure.add(fact.factId); return {
      factId: fact.factId, stage: fact.stage, trigger: fact.trigger, order: { ...fact.order }, recipient: compact(fact.recipient), condition: compact(fact.condition), effect: compact(fact.effect), baseValue: compact(fact.baseValue), runtimeInputs: [...fact.sourceStateInputs, ...fact.finalValueContract.runtimeModifierInputs],
    }; });
    const moves = (movesByModel.get(model) ?? []).map((move) => { closure.add(move.factId); return {
      canonicalId: move.canonicalId, factId: move.factId, stateId: move.stateId,
      title: { classification: move.title.classification, text: typeof move.title.english === "string" ? move.title.english : null, localizationKey: typeof move.title.localizationKey === "string" ? move.title.localizationKey : null },
      intents: move.intents.map((row) => compact(row)), operations: move.operations.map((row, order) => ({ order, ...compact(row) })),
    }; });
    const graph = graphByModel.get(model); if (graph) closure.add(graph.factId);
    const name = monster.name.kind === "localizedText"
      ? { kind: "localizedText", text: monster.name.text }
      : { kind: "localizedTemplate", template: monster.name.template, inputs: compact(monster.name.inputs) };
    return { canonicalModel: model, sourceIdentity: monster.canonicalId, factId: monster.factId, name, reachability: monster.reachability,
      hp: { expression: compact(monster.initialHp.expression), a8SinglePlayer: compact(monster.initialHp.a8SinglePlayer), assignmentContract: "source HP expression; runtime inputs and multiplayer scaling remain explicit" }, states, initialState, moves,
      graph: graph ? { graphId: graph.graphId, factId: graph.factId, initial: graph.initial, stateCollection: compact(graph.stateCollection), nodes: compact(graph.nodes), edges: compact(graph.edges), topology: compact(graph.topology) } : null,
    };
  }
  function productionRecord(encounter, models, closure) {
    if (!encounter.producedMonsters.length) return null; const ids = new Set([encounter.canonicalId, `ENCOUNTER.${encounter.canonicalId}`, ...models]); const rules = {};
    const semantics = object(source.production.productionSemantics, "productionSemantics");
    for (let pass = 0; pass < 2; pass++) for (const [key, rows] of Object.entries(semantics)) if (Array.isArray(rows)) {
      const selected = rows.filter((row) => contains(row, ids)); if (!selected.length) continue; rules[key] = compact(selected);
      for (const row of selected) { if (typeof row.factId === "string") closure.add(row.factId); if (typeof row.producerId === "string") ids.add(row.producerId); }
    }
    return { producedBodies: [...encounter.producedMonsters], pools: compact(encounter.productionPools), rules, status: semantics.status };
  }
  function lifecycleMechanicsRecord(encounter, models, monsterRows, production) {
    const modelIds = new Set(models);
    const knownPowerIds = new Set(source.models.powers.map((row) => row.canonicalId));
    const powerIds = new Set();
    const addPower = (reference) => {
      if (typeof reference !== "string") return;
      if (knownPowerIds.has(reference)) { powerIds.add(reference); return; }
      // Member refs are accepted only when their exact canonical Power prefix is validated.
      for (const id of knownPowerIds) if (reference.startsWith(`${id}.`)) { powerIds.add(id); return; }
    };
    const operationPowers = (operation) => {
      if (!operation || typeof operation !== "object") return;
      // Move/initial operations use model. Schema-11 lifecycle operations use
      // power/retainedPower and Power-valued owner/member refs.
      for (const key of ["model", "power", "retainedPower", "owner", "amountRef", "source"]) addPower(operation[key]);
    };

    for (const body of monsterRows) {
      for (const fact of body.initialState) operationPowers(fact.effect);
      for (const move of body.moves) for (const operation of move.operations) operationPowers(operation);
    }
    for (const effect of production?.rules?.postAddEffects ?? []) {
      operationPowers(effect);
      if (effect.kind === "applyPower") addPower(effect.targetRef);
    }

    const encounterIds = new Set([encounter.canonicalId, `ENCOUNTER.${encounter.canonicalId}`]);
    const eventIds = new Set(encounter.kind === "event" ? [eventTurns.get(encounter.canonicalId)?.canonicalEvent] : []);
    const rowPowerReferences = (row) => {
      const result = new Set();
      const collect = (reference) => {
        if (typeof reference !== "string") return;
        if (knownPowerIds.has(reference)) { result.add(reference); return; }
        for (const id of knownPowerIds) if (reference.startsWith(`${id}.`)) { result.add(id); return; }
      };
      for (const key of ["power", "producerPower", "listener"]) collect(row[key]);
      for (const signal of row.sourceSignals ?? []) collect(signal);
      for (const operation of lifecycleOperations(row)) {
        for (const key of ["model", "power", "retainedPower", "owner", "amountRef", "source"]) collect(operation[key]);
      }
      return result;
    };
    const relevantRecord = (row) => {
      // An encounter-specific row must match that encounter exactly; a shared
      // event identity cannot pull sibling encounter registrations into the view.
      if (typeof row.canonicalEncounter === "string") return encounterIds.has(row.canonicalEncounter);
      if (modelIds.has(row.ownerModel) || (Array.isArray(row.ownerModels) && row.ownerModels.some((id) => modelIds.has(id)))
          || modelIds.has(row.canonicalModel) || (Array.isArray(row.applicableConcreteModels) && row.applicableConcreteModels.some((id) => modelIds.has(id)))
          || [...lifecycleRelationModels(row)].some((id) => modelIds.has(id))) return true;
      if (eventIds.has(row.canonicalEvent) || eventIds.has(row.eventId)) return true;
      if ([...rowPowerReferences(row)].some((id) => powerIds.has(id))) return true;
      return Array.isArray(row.sourceSignals) && row.sourceSignals.some((id) => modelIds.has(id));
    };
    const harvestRecordPowers = (row) => {
      for (const id of rowPowerReferences(row)) powerIds.add(id);
    };

    const mechanics = source.lifecycle.mechanics ?? {};
    const candidates = lifecycleMechanicUnits(mechanics, new Set(["powerRetentionPolicies"]));
    const selected = new Set();
    let changed = true;
    while (changed) {
      changed = false;
      for (const { row } of candidates) {
        if (selected.has(row) || !relevantRecord(row)) continue;
        selected.add(row); harvestRecordPowers(row); changed = true;
      }
    }

    const result = {};
    for (const [family, value] of Object.entries(mechanics)) {
      if (family === "powerRetentionPolicies") continue;
      const selectedValue = selectedLifecycleMechanicTree(value, selected);
      if (selectedValue !== undefined) result[family] = selectedValue;
    }
    const policies = (mechanics.powerRetentionPolicies ?? []).filter((row) => powerIds.has(row.power));
    if (policies.length) result.powerRetentionPolicies = compact(policies);
    return result;
  }
  function eventRecord(encounter, closure) {
    if (encounter.kind !== "event") return null; const turn = eventTurns.get(encounter.canonicalId); closure.add(turn.factId); const scripts = {};
    const ids = new Set([turn.canonicalEvent, encounter.canonicalId, `ENCOUNTER.${encounter.canonicalId}`]);
    for (const [key, rows] of Object.entries(source.eventScripts)) if (Array.isArray(rows)) {
      const selected = rows.filter((row) => contains(row, ids)); if (!selected.length) continue; scripts[key] = compact(selected); for (const row of selected) if (typeof row.factId === "string") closure.add(row.factId);
    }
    return { canonicalEvent: turn.canonicalEvent, turnMachine: compact(turn), scripts };
  }
  function legacyRecord(encounter) {
    const result = [];
    for (const rows of Object.values(payload.legacyAnnotations)) if (Array.isArray(rows)) for (const row of rows) {
      if (row?.legacyEncounterId === encounter.canonicalId && row?.canonicalEncounterRef === encounter.factId) result.push({ lane: "LEGACY / COMMUNITY", factId: row.factId, provenanceStatus: compact(row.provenanceStatus), annotations: compact(row.annotations) });
    }
    return result;
  }
  return function compile(id, state, mode) {
    const encounter = encounterIndex.get(id); if (!encounter) return null; const closure = new Set([encounter.factId]);
    const placement = placementByEncounter.get(id); closure.add(placement.factId); const initialModels = [...rosterModels(encounter.initialRoster.selection)].sort();
    const allModels = [...new Set([...initialModels, ...encounter.producedMonsters])].sort(); const monsters = allModels.map((model) => monsterRecord(model, closure));
    const production = productionRecord(encounter, allModels, closure); const event = eventRecord(encounter, closure);
    const observation = observedRecord(state, observationIndex, stateModelObservationIndex, id, mode === "manual-reference");
    closure.add(source.lifecycle.factId); closure.add(source.hpPipeline.factId); closure.add(source.stateRules.factId);
    const lifecycle = { componentId: source.lifecycle.componentId, factId: source.lifecycle.factId, status: source.lifecycle.status, dependencies: compact(source.lifecycle.dependencies), core: compact(source.lifecycle.core), dispatch: compact(source.lifecycle.dispatch), listenerRegistry: compact(source.lifecycle.listenerRegistry), removal: compact(source.lifecycle.removal), combatTermination: compact(source.lifecycle.combatTermination), runtimeBoundaries: compact(source.lifecycle.runtimeBoundaries), mechanics: lifecycleMechanicsRecord(encounter, allModels, monsters, production) };
    const encounterView = {
      canonicalId: id, sourceIdentity: encounter.sourceType, factId: encounter.factId, title: encounter.title, kind: encounter.kind,
      placement: { classification: placement.classification, factId: placement.factId, memberships: compact(placement.memberships) },
      roster: { cardinality: { ...encounter.initialRoster.cardinality }, grammar: rosterRecord(encounter.initialRoster.selection), possibleInitialBodies: initialModels },
      observedBodies: observation.observedBodies, production, monsters, event,
      hpContract: {
        lane: "SOURCE", scope: "global checked HP/state contract; rule-to-model applicability is not inferred",
        pipelineFactId: source.hpPipeline.factId, assignment: compact(source.hpPipeline.assignment),
        baseSelection: compact(source.hpPipeline.baseSelection), specialCallPaths: compact(source.hpPipeline.specialCallPaths),
        multiplayerScaling: compact(source.scaling.hp),
        stateRuleRegistry: { factId: source.stateRules.factId, rules: compact(source.stateRules.rules) },
      },
      lifecycle, callouts: [],
      conflicts: payload.conflicts.filter((row) => closure.has(row.left?.factId) || closure.has(row.right?.factId)).map((row) => compact(row)),
      comparisons: payload.laneComparisons.filter((row) => closure.has(row.left?.factId) || closure.has(row.right?.factId)).map((row) => compact(row)),
      knownUnknowns: payload.knownUnknowns.filter((row) => row.affectedFactIds.some((factId) => closure.has(factId))).map((row) => ({ unknownId: row.unknownId, status: row.status, scope: row.scope, reasonCode: row.reasonCode, detail: row.detail, affectedFactIds: [...new Set(row.affectedFactIds.filter((factId) => closure.has(factId)))] })),
      legacyAnnotations: legacyRecord(encounter), proof: [...closure].sort().map(proofFor),
    };
    encounterView.presentation = buildEncounterPresentation(encounterView);
    const result = {
      status: "selected", mode,
      authority: { lane: "SOURCE", gameVersion: metadata.game.version, branch: metadata.game.branch, sourceSchemaVersion: metadata.sourceSchemaVersion, sourceExtractorVersion: metadata.sourceExtractorVersion, projectionSchemaVersion: schema, generatorVersion: metadata.generator.version, dllSha256: DLL_SHA256, conflictPolicy: "explicit-no-precedence", staticOnly: true },
      observation, encounter: encounterView,
      notices: ["Static source mechanics and possibilities; not a next-move prediction.", "Live HP, Block, Powers, intent, turn, phase, and hand are not observed.", "Possible initial bodies, observed body IDs, and produced bodies are separate sets.", "No source-qualified tactical callouts are published in the checked artifact; [] is not a quota."],
    };
    if (Buffer.byteLength(JSON.stringify(result)) > MAX_VIEW_BYTES) fail(`compiled view exceeds ${MAX_VIEW_BYTES} bytes`);
    return freeze(result);
  };
}

/** Read the compact checked projection exactly once; failure never prevents stable startup. */
export function createSourceAdapter(options = {}) {
  try {
    const root = "projection" in options ? jsonValue(options.projection, "projection input") : JSON.parse(readFileSync(options.projectionPath ?? DEFAULT_PROJECTION, "utf8"));
    const validated = validateProjection(root); const compile = makeCompiler(validated); const { metadata } = validated;
    const adapter = {
      available: true, error: null, schemaVersion: validated.schema, canonicalIds: [...validated.encounterIndex.keys()].sort(),
      resolveObserved(state) {
        const id = typeof state?.encounterId === "string" ? state.encounterId : null;
        if (id === null) return freeze({ kind: "no-encounter", encounterId: null });
        if (!validated.encounterIndex.has(id)) return freeze({ kind: "unresolved-observation", encounterId: id });
        return freeze({ kind: state?.status === "combat" ? "current-combat" : "last-completed-room", encounterId: id });
      },
      view(state, manualId = null) {
        if (manualId !== null) {
          if (typeof manualId !== "string" || !manualId || manualId.length > 160) return freeze({ status: "invalid-selector", error: "encounter must be one exact bounded canonical ID" });
          if (!validated.encounterIndex.has(manualId)) return freeze({ status: "unknown-selector", error: `unknown canonical encounter: ${manualId}` });
          return compile(manualId, state, "manual-reference");
        }
        const resolved = adapter.resolveObserved(state);
        if (resolved.kind === "no-encounter") return freeze({ status: "no-encounter", mode: "no-encounter", authority: { lane: "SOURCE", gameVersion: metadata.game.version, projectionSchemaVersion: validated.schema, staticOnly: true }, observation: observedRecord(state, validated.observationIndex, validated.stateModelObservationIndex, null, false), encounter: null, notices: ["No current combat or last completed room is available. Select an exact canonical encounter for a manual static reference."] });
        if (resolved.kind === "unresolved-observation") return freeze({ status: "unresolved-observation", mode: "no-encounter", authority: { lane: "SOURCE", gameVersion: metadata.game.version, projectionSchemaVersion: validated.schema, staticOnly: true }, observation: observedRecord(state, validated.observationIndex, validated.stateModelObservationIndex, null, false), encounter: null, error: `observed encounter ID has no checked source identity: ${resolved.encounterId}` });
        return compile(resolved.encounterId, state, resolved.kind);
      },
    };
    return freeze(adapter);
  } catch (error) {
    const message = error instanceof SourceProjectionError ? error.message : error instanceof SyntaxError ? "source projection unavailable: corrupt JSON" : "source projection unavailable: validation failed";
    return freeze({ available: false, error: message, schemaVersion: null, canonicalIds: [], resolveObserved: () => ({ kind: "unavailable" }), view: () => null });
  }
}

export const internals = Object.freeze({
  validateProjection, buildStateModelObservationIndex, rosterRecord, rosterModels, jsonValue, compact, payloadDigest,
  lifecycleOperations, lifecycleMechanicUnits, selectedLifecycleMechanicTree, MAX_VIEW_BYTES, SUPPORTED_SCHEMAS,
});
