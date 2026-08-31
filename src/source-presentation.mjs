import { compileCalloutCollection } from "./decision-callouts.mjs";

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const TARGETS = Object.freeze({
  allOpponentsOfSourceMonster: "all opponents",
  sourceMonster: "self",
  sourceMonsterCombatState: "enemy side",
  registeredTargets: "registered targets",
  generatedCardCombatPile: "combat card pile",
  rngSelectedCombatCard: "one random combat card",
  ownerSide: "owner side",
  currentSameSideTeammates: "same-side teammates",
  newBody: "new body",
  sameOwnerBody: "same body",
  exactReturnedBody: "added body",
  orderedReturnedBodies: "added bodies",
  allSegments: "all segments",
  runState: "run state",
});
const OPERATORS = Object.freeze({
  add: "+", subtract: "−", multiply: "×", divide: "÷",
  equal: "=", notEqual: "≠", lessThan: "<", lessThanOrEqual: "≤",
  greaterThan: ">", greaterThanOrEqual: "≥",
});

function text(value, fallback = "unknown") {
  return typeof value === "string" && value ? value : fallback;
}
function words(value) {
  return String(value ?? "unknown")
    .replace(/^(MONSTER|POWER|CARD|ENCOUNTER|ACT)\./, "")
    .replace(/_POWER$/, "")
    .replace(/[_./#-]+/g, " ")
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .trim().toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}
function lowerWords(value) {
  const result = words(value);
  return result ? result.toLowerCase() : "unknown";
}
function modelName(model, names) { return names.get(model) ?? words(model); }
function nameOf(body) {
  return body?.name?.kind === "localizedText" ? body.name.text
    : body?.name?.kind === "localizedTemplate" ? `${body.name.template} (runtime name input)`
      : "Unknown body";
}
function rangeReferenceText(reference) {
  if (typeof reference !== "string" || !reference) return null;
  const match = /^(RUNTIME|SOURCE)\.(?:PRODUCTION\.)?(.+)$/.exec(reference);
  return match ? `${match[1].toLowerCase()} ${lowerWords(match[2])}` : lowerWords(reference);
}
function rangeEndpointText(range, endpoint) {
  if (range[endpoint] !== undefined) return String(range[endpoint]);
  return rangeReferenceText(range[`${endpoint}Ref`]);
}
function rangeText(range) {
  if (!range || typeof range !== "object") return "unknown";
  const minimum = rangeEndpointText(range, "minimum"), maximum = rangeEndpointText(range, "maximum");
  if (minimum === null || maximum === null) return "unknown";
  return minimum === maximum ? minimum : `${minimum}–${maximum}`;
}

/** Concise symbolic notation. Exact expression trees stay in the audit expansion. */
export function expressionText(expression, depth = 0) {
  if (depth > 8 || expression == null) return "unknown value";
  if (typeof expression !== "object") return String(expression);
  switch (expression.kind) {
    case "constant": return String(expression.value);
    case "convert": return expressionText(expression.expression, depth + 1);
    case "range": return `${expressionText(expression.minimum, depth + 1)}–${expressionText(expression.maximum, depth + 1)}`;
    case "ascensionSelect": return `A${expression.threshold}+ ${expressionText(expression.atOrAbove, depth + 1)}; below A${expression.threshold} ${expressionText(expression.below, depth + 1)}`;
    case "arithmetic": {
      const operator = OPERATORS[expression.operator] ?? lowerWords(expression.operator);
      return `(${(expression.operands ?? []).map((item) => expressionText(item, depth + 1)).join(` ${operator} `) || "unknown operands"})`;
    }
    case "comparison":
    case "compare": {
      const left = expressionText(expression.left ?? expression.operands?.[0], depth + 1);
      const right = expressionText(expression.right ?? expression.operands?.[1], depth + 1);
      return `${left} ${OPERATORS[expression.operator] ?? lowerWords(expression.operator)} ${right}`;
    }
    case "conditional": return `if ${conditionText(expression.condition, depth + 1)}, ${expressionText(expression.whenTrue, depth + 1)}; otherwise ${expressionText(expression.whenFalse, depth + 1)}`;
    case "allOf": return (expression.operands ?? []).map((item) => conditionText(item, depth + 1)).join(" and ") || "all source conditions";
    case "anyOf": return (expression.operands ?? []).map((item) => conditionText(item, depth + 1)).join(" or ") || "a source condition";
    case "stateVariable": return `state input (${text(expression.name)})`;
    case "runtimeInput": return `runtime input (${text(expression.name).replace(/current/gi, "encounter")})`;
    case "reference": return "source formula";
    case "delegate": return expressionText(expression.expression, depth + 1);
    case "count": return `${lowerWords(expression.collection)} count`;
    case "graphLifetimeOnce": return "unused graph-lifetime opportunity";
    case "methodBoolean": return "runtime source predicate";
    default: return `${lowerWords(expression.kind)} value`;
  }
}
export function conditionText(condition, depth = 0) {
  if (condition?.kind === "unconditional") return "always for this rule";
  return expressionText(condition, depth);
}
function amountText(value) { return value == null ? "unknown amount" : expressionText(value); }
function targetText(target) { return TARGETS[target] ?? lowerWords(target); }
function cardOrPower(model) { return words(model); }
function movePowerIdentity(operation) {
  if (operation.model) return cardOrPower(operation.model);
  if (operation.power) return cardOrPower(operation.power);
  if (operation.modelContract?.classification) return lowerWords(operation.modelContract.classification);
  return "Power with unavailable checked identity";
}

function rosterNode(node, names) {
  if (!node || typeof node !== "object") return "unknown roster branch";
  if (node.kind === "fixed") return modelName(node.model, names);
  if (node.kind === "sequence") {
    const children = (node.children ?? []).map((item) => rosterNode(item, names));
    const grouped = [];
    for (const child of children) {
      const previous = grouped.at(-1);
      if (previous?.label === child) previous.count += 1; else grouped.push({ label: child, count: 1 });
    }
    return grouped.map((item) => `${item.count > 1 ? `${item.count}× ` : ""}${item.label}`).join(" + ") || "empty sequence";
  }
  const choices = (node.choices ?? []).map((item) => rosterNode(item, names)).join(" / ") || "unknown choices";
  if (node.kind === "uniformChoice") return `1 random body from {${choices}}`;
  if (node.kind === "filteredChoice") {
    const draws = node.draws === "withoutReplacement" ? "without replacement" : lowerWords(node.draws);
    return `${node.count} random distinct bodies from {${choices}} · ${draws}`;
  }
  return "unknown roster branch";
}

function initialEffect(fact) {
  const effect = fact.effect ?? {};
  const recipient = targetText(fact.recipient?.kind);
  const amount = amountText(fact.baseValue?.expression);
  const model = effect.model ? cardOrPower(effect.model) : null;
  let line;
  switch (effect.kind) {
    case "applyPower": line = `${recipient} · apply ${amount} ${model}`; break;
    case "gainBlock": line = `${recipient} · gain ${amount} Block`; break;
    case "setMaxAndCurrentHp": line = `${recipient} · set max and starting HP to ${amount}`; break;
    case "setCurrentHp": line = `${recipient} · set starting HP to ${amount}`; break;
    case "setState": line = `${recipient} · set encounter state to ${amount}`; break;
    case "forceMoveState": line = `${recipient} · set initial behavior state`; break;
    case "configurePowerTarget": line = `${recipient} · configure ${model ?? "Power"} target`; break;
    case "afflictCard": line = `${recipient} · apply card affliction`; break;
    case "subscribe": line = `${recipient} · register lifecycle listener`; break;
    case "relationship": line = `${recipient} · establish encounter relationship`; break;
    default: line = `${recipient} · ${lowerWords(effect.kind)} (${amount})`; break;
  }
  return {
    timing: lowerWords(fact.stage), line,
    condition: fact.condition?.kind === "unconditional" ? null : conditionText(fact.condition),
    unresolved: (fact.runtimeInputs ?? []).length ? `${fact.runtimeInputs.length} runtime modifier input${fact.runtimeInputs.length === 1 ? "" : "s"} remain unresolved` : null,
  };
}

function moveEffects(move, names) {
  const operations = move.operations ?? [], consumed = new Set(), effects = [];
  for (let index = 0; index < operations.length; index += 1) {
    if (consumed.has(index)) continue;
    const operation = operations[index], target = targetText(operation.target);
    let line;
    switch (operation.kind) {
      case "attack": {
        const hitIndex = operations[index + 1]?.kind === "attackHitCount" ? index + 1 : -1;
        const hits = hitIndex >= 0 ? amountText(operations[hitIndex].value) : "1";
        if (hitIndex >= 0) consumed.add(hitIndex);
        line = `${target} · ${amountText(operation.value)} damage${hits === "1" ? "" : ` × ${hits} hits`}`;
        break;
      }
      case "attackHitCount": line = `preceding attack · ${amountText(operation.value)} hits`; break;
      case "gainBlock": line = `${target} · gain ${amountText(operation.value)} Block`; break;
      case "heal": line = `${target} · heal ${amountText(operation.value)} HP`; break;
      case "applyPower": line = `${target} · apply ${amountText(operation.value)} ${cardOrPower(operation.model)}`; break;
      case "removePower": line = `${target} · remove ${movePowerIdentity(operation)}`; break;
      case "addStatusCard": line = `${target} · add ${amountText(operation.value)} ${cardOrPower(operation.model)} card${String(operation.value?.value) === "1" ? "" : "s"}`; break;
      case "addGeneratedCard": line = `${target} · add 1 generated ${cardOrPower(operation.model)} card`; break;
      case "removeCard": line = `${target} · remove from combat`; break;
      case "stateWrite": line = `${target} · update internal state to ${amountText(operation.value)}`; break;
      case "summon": line = `${target} · add ${modelName(operation.model, names)} body${operation.selection?.slot ? ` at ${lowerWords(operation.selection.slot)}` : ""}`; break;
      case "escape": line = `${target} · exit through escape lifecycle`; break;
      case "kill": line = `${target} · enter death lifecycle`; break;
      case "transition": line = operation.transition === "noOp" ? "no combat operation" : `behavior transition · ${lowerWords(operation.transition)}`; break;
      case "helperEffect": line = `lifecycle helper · ${lowerWords(operation.helper)}`; break;
      default: line = `${target} · unresolved ${lowerWords(operation.kind)} effect`; break;
    }
    effects.push({ order: effects.length + 1, line });
  }
  if (!effects.length) effects.push({ order: 1, line: "No checked combat operation in this effect state" });
  return effects;
}

function graphPresentation(body, effectLabels) {
  const graph = body.graph;
  if (!graph) return { headline: "Behavior graph unavailable", paths: [], exact: false };
  const labels = new Map(), kindCounts = { random: 0, conditional: 0 };
  for (const node of graph.nodes ?? []) {
    if (node.kind === "move") labels.set(node.nodeId, effectLabels.get(node.stateId) ?? "effect state");
    else {
      kindCounts[node.kind] = (kindCounts[node.kind] ?? 0) + 1;
      labels.set(node.nodeId, `${node.kind} fork ${kindCounts[node.kind]}`);
    }
  }
  const paths = (graph.edges ?? []).map((edge) => {
    const qualifiers = [];
    if (edge.kind === "randomBranch") {
      qualifiers.push("random branch");
      if (edge.repeat?.enumName) qualifiers.push(lowerWords(edge.repeat.enumName));
      if (edge.cooldown) qualifiers.push(`${edge.cooldown}-use cooldown`);
    } else if (edge.kind === "conditionalBranch") {
      qualifiers.push(`when ${conditionText(edge.predicate)}`);
    } else qualifiers.push("follow-up");
    return `${labels.get(edge.from) ?? lowerWords(edge.kind)} → ${labels.get(edge.to) ?? "effect state"} · ${qualifiers.join(" · ")}`;
  });
  const topology = graph.topology ?? {};
  const adjacency = new Map();
  for (const edge of graph.edges ?? []) { const next = adjacency.get(edge.from) ?? []; next.push(edge.to); adjacency.set(edge.from, next); }
  const visiting = new Set(), visited = new Set();
  const cyclicFrom = (node) => {
    if (visiting.has(node)) return true;
    if (visited.has(node)) return false;
    visiting.add(node);
    if ((adjacency.get(node) ?? []).some(cyclicFrom)) return true;
    visiting.delete(node); visited.add(node); return false;
  };
  const hasCycle = [...adjacency.keys()].some(cyclicFrom);
  const initialNodes = Array.isArray(graph.initial) ? graph.initial : graph.initial == null ? [] : [graph.initial];
  const starts = initialNodes.map((nodeId) => labels.get(nodeId)).filter(Boolean);
  const parts = [];
  if (starts.length) parts.push(`starts at ${starts.join(" / ")}`);
  if (hasCycle) parts.push("repeating cycle");
  if (topology.followUpEdges) parts.push(`${topology.followUpEdges} follow-up${topology.followUpEdges === 1 ? "" : "s"}`);
  if (topology.randomBranches) parts.push(`${topology.randomBranches} random branch${topology.randomBranches === 1 ? "" : "es"}`);
  if (topology.conditionalBranches) parts.push(`${topology.conditionalBranches} conditional branch${topology.conditionalBranches === 1 ? "" : "es"}`);
  if (topology.mustOnceFlags) parts.push(`${topology.mustOnceFlags} once-only flag${topology.mustOnceFlags === 1 ? "" : "s"}`);
  return { headline: parts.length ? `Behavior grammar · ${parts.join(" · ")}` : "Behavior grammar · fixed effect state", paths, exact: true };
}

function bodyPresentation(body, index, encounter, names) {
  const effectLabels = new Map();
  (body.moves ?? []).forEach((move, moveIndex) => effectLabels.set(move.stateId, `Effect ${LETTERS[moveIndex] ?? moveIndex + 1}`));
  const initial = encounter.roster.possibleInitialBodies.includes(body.canonicalModel);
  const produced = encounter.production?.producedBodies?.includes(body.canonicalModel) === true;
  const roles = [initial ? "possible initial body" : null, produced ? "produced possibility" : null].filter(Boolean);
  const hp = body.hp?.a8SinglePlayer;
  return {
    bodyIndex: index,
    name: nameOf(body),
    role: roles.join(" · ") || "encounter body",
    hp: hp ? `A8 single-player HP · ${rangeText(hp)}` : "A8 single-player HP · formula only",
    hpHasRuntimeInputs: JSON.stringify(body.hp?.expression ?? {}).includes('"stateVariable"') || JSON.stringify(body.hp?.expression ?? {}).includes('"runtimeInput"'),
    forms: (body.states ?? []).map((state) => ({
      name: state.displayName?.kind === "localizedText" ? state.displayName.text : `${state.displayName?.template ?? "Runtime form name"} (runtime name input)`,
      hp: lowerWords(state.hpState ?? "model HP formula"),
    })),
    initialEffects: (body.initialState ?? []).map(initialEffect),
    effects: (body.moves ?? []).map((move, moveIndex) => ({
      label: `Effect ${LETTERS[moveIndex] ?? moveIndex + 1}`,
      timing: "during this possible behavior resolution",
      moveIndex,
      orderedEffects: moveEffects(move, names),
    })),
    behavior: graphPresentation(body, effectLabels),
  };
}

function productionPresentation(production, names) {
  if (!production) return null;
  const pools = new Map((production.rules?.pools ?? []).map((pool) => [pool.poolId, pool]));
  const rules = (production.rules?.producers ?? []).map((producer) => {
    const cardinality = producer.activationCardinality?.normallyAddedBodies ?? producer.activationCardinality?.bodyAddAttempts;
    const count = rangeText(cardinality);
    const repeat = producer.repeatPolicy?.classification ?? producer.lifetimePolicy?.classification;
    const attempts = (producer.attempts ?? []).map((attempt) => {
      const pool = pools.get(attempt.poolRef);
      const candidates = (pool?.candidateModels ?? []).map((model) => modelName(model, names)).join(" / ") || "unknown body";
      const selection = pool?.selection?.kind === "runtimeRng" ? "runtime-random" : "fixed";
      return `${selection} {${candidates}}`;
    });
    return {
      owner: modelName(producer.ownerModel, names),
      cadence: `${count} added bod${count === "1" ? "y" : "ies"} per eligible trigger`,
      condition: producer.availability?.expression ? conditionText(producer.availability.expression) : "source availability rule",
      repeat: repeat ? lowerWords(repeat) : "repeat policy in exact detail",
      attempts,
    };
  });
  return {
    possibilities: (production.producedBodies ?? []).map((model) => modelName(model, names)),
    caveat: "Produced bodies are possibilities from eligible rules, not initial or co-present bodies.",
    rules,
  };
}

function lifecycleEffect(operation, names) {
  const target = targetText(operation.target);
  switch (operation.kind) {
    case "createBody": return `${target} · create ${modelName(operation.model, names)} body`;
    case "precreateBody": return `${target} · precreate ${modelName(operation.model, names)} body`;
    case "coreAddByRef": {
      if (operation.model) return `${target} · add ${modelName(operation.model, names)} body`;
      if (operation.body) return `${target} · add ${lowerWords(operation.body)}`;
      return `${target} · add the exact created body`;
    }
    case "heal":
    case "reviveHpByRef": return `${target} · restore HP from the checked formula`;
    case "setMaxAndCurrentHp": return `${target} · set max and starting HP from the checked formula`;
    case "forceMove":
    case "configureMove": return `${target} · configure behavior state`;
    case "removePower": return `${target} · remove ${cardOrPower(operation.power)}`;
    case "applyPowerByRef": return `${target} · apply ${cardOrPower(operation.power)} from the checked Power rule`;
    case "applyTargetedPower": return `${target} · apply ${cardOrPower(operation.power)}`;
    case "skipPowerApplication": return `${target} · skip ${cardOrPower(operation.power)} application`;
    case "decrementPower": return `${target} · Countdown · decrement ${cardOrPower(operation.power ?? operation.owner)} by ${operation.amount ?? "the checked amount"}`;
    case "removeSnapshottedPowers": return `${target} · remove snapshotted Powers except ${cardOrPower(operation.retainedPower)}`;
    case "writeState": return `${target} · set ${text(operation.field, "lifecycle state")} = ${String(operation.value ?? "source value")}`;
    case "escape": return `${target} · escape through the checked removal graph${operation.removeCreatureNode === true ? " and remove the creature node" : ""}`;
    case "ordinaryCentralizedVictoryByRef": return `${target} · ordinary centralized victory check`;
    case "incrementState": return `${target} · increment ${text(operation.field, "lifecycle state")}`;
    case "forceMoveConditional": return `${target} · configure ${words(operation.move)} behavior when ${lowerWords(operation.condition ?? "the source condition passes")}`;
    case "setInteraction": return `${target} · set interaction ${operation.enabled === true ? "enabled" : operation.enabled === false ? "disabled" : "state"}`;
    case "repeatAttempts": return `${target} · ${operation.count ?? "formula"} ordered production attempts`;
    case "createMutableBody": return `${target} · create ${modelName(operation.model, names)} body`;
    case "setNodeVisible":
    case "delayedReveal":
    case "presentationFade":
    case "playVfx":
    case "triggerAnimation": return `${target} · presentation lifecycle step`;
    case "awaitMethod": return `${target} · await checked lifecycle handler`;
    default: return `${target} · ${lowerWords(operation.kind)}`;
  }
}
const LIFECYCLE_PRESENTATION_RECORD_FIELDS = new Set([
  "ownerModel", "ownerModels", "canonicalModel", "applicableConcreteModels", "canonicalEncounter", "canonicalEvent", "eventId",
  "power", "producerPower", "listener", "sourceSignals", "phaseSystemId", "deathProductionId", "relationshipId", "policyId",
  "subscriptionId", "cleanupId", "doomContractId",
]);
function isLifecyclePresentationRecord(row) {
  if (!row || typeof row !== "object" || Array.isArray(row)) return false;
  if ([...LIFECYCLE_PRESENTATION_RECORD_FIELDS].some((key) => key in row)) return true;
  return ["orderedEffects", "orderedPerPlayer", "transitions", "branches"].some((key) => Array.isArray(row[key]));
}
/** Flatten selected array/object families without discarding their stable keyed path. */
function lifecyclePresentationRecords(mechanics) {
  const result = [];
  const visit = (value, path) => {
    if (Array.isArray(value)) {
      for (const item of value) {
        if (isLifecyclePresentationRecord(item)) result.push({ path, row: item });
        else if (item && typeof item === "object") visit(item, path);
      }
      return;
    }
    if (!value || typeof value !== "object") return;
    if (isLifecyclePresentationRecord(value)) { result.push({ path, row: value }); return; }
    for (const [key, item] of Object.entries(value)) if (item && typeof item === "object") visit(item, [...path, key]);
  };
  for (const [family, value] of Object.entries(mechanics ?? {})) visit(value, [family]);
  return result;
}
function lifecycleIdentity(row, path) {
  return row.phaseSystemId ?? row.deathProductionId ?? row.relationshipId ?? row.policyId ?? row.subscriptionId
    ?? row.cleanupId ?? row.doomContractId ?? row.branchId ?? row.listener ?? row.canonicalEncounter ?? path.join(".");
}
function lifecyclePresentation(lifecycle, names) {
  const mechanics = [];
  for (const { path, row } of lifecyclePresentationRecords(lifecycle.mechanics ?? {})) {
    const transitions = row.transitions ?? row.branches ?? [row];
    const branches = transitions.map((transition) => {
      const orderedEffects = [...(transition.orderedEffects ?? row.orderedEffects ?? row.orderedPerPlayer ?? [])]
        .filter((effect) => effect && typeof effect === "object")
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
      const effects = [
        ...(row.hook ? [`${cardOrPower(row.power)} · ${words(row.hook)} = ${row.result == null ? "source default" : row.result ? "yes" : "no"}`] : []),
        ...orderedEffects.map((effect) => lifecycleEffect(effect, names)),
        ...(transition.outcome ? [`Outcome · ${words(transition.outcome)}`] : []),
      ];
      const clock = [
        transition.repeatability ? text(transition.repeatability) : null,
        row.trigger ? words(row.trigger) : null,
        row.participantPolicy ? text(row.participantPolicy) : null,
      ].filter(Boolean);
      return {
        condition: transition.condition ? conditionText(transition.condition) : row.condition ? conditionText(row.condition) : null,
        effects,
        repeat: clock.length ? clock.join(" · ") : null,
      };
    });
    if (branches.some((branch) => branch.condition || branch.effects.length || branch.repeat)) {
      mechanics.push({ family: path.map(words).join(" · "), identity: lifecycleIdentity(row, path), branches });
    }
  }
  const removalOrder = lifecycle.removal?.stateRemoval?.order ?? [];
  const external = (lifecycle.runtimeBoundaries ?? []).filter((row) => row.effectStatus === "runtimeDynamicExternalBoundary").length;
  return {
    status: lifecycle.status,
    rules: [
      lifecycle.removal?.deathMoveDeferral ? `Death removal · ${lifecycle.removal.deathMoveDeferral}` : null,
      removalOrder.length ? `State removal order · ${removalOrder.join(" → ")}` : null,
      lifecycle.combatTermination?.victoryPredicate ? "Encounter completion · requires no living primary enemy and no listener that stops ending; completion runs at the centralized check." : null,
      lifecycle.combatTermination?.victoryPredicate?.allEscaped ? `Escape completion · ${lifecycle.combatTermination.victoryPredicate.allEscaped}` : null,
      external ? `${external} run/player lifecycle hook${external === 1 ? "" : "s"} remain runtime-dynamic external boundaries.` : null,
    ].filter(Boolean),
    mechanics,
  };
}

function eventEffect(row) {
  const recipient = lowerWords(row.recipient ?? "event owner");
  let effect;
  switch (row.kind) {
    case "upgradeCard": effect = `upgrade up to ${row.maximum ?? "a source-defined number of"} selected cards`; break;
    case "offerRewards": effect = "offer the constructed reward list"; break;
    default: effect = lowerWords(row.kind); break;
  }
  return `${recipient} · ${effect}${row.condition ? ` · when ${lowerWords(row.condition)}` : ""}`;
}
function eventPresentation(event) {
  if (!event) return null;
  const scripts = event.scripts ?? {};
  return {
    behavior: words(event.turnMachine?.behaviorClassification ?? "checked event behavior"),
    effects: (scripts.effects ?? []).map(eventEffect),
    optionCount: (scripts.options ?? []).length,
    transitionCount: (scripts.transitions ?? []).length,
  };
}

function contextPresentation(encounter) {
  const memberships = encounter.placement?.memberships ?? [];
  const primary = memberships[0];
  return {
    kind: words(encounter.kind),
    summary: primary ? [words(primary.actId), words(primary.tier), words(primary.roomClass)].join(" · ") : words(encounter.kind),
    additionalPlacements: Math.max(0, memberships.length - 1),
  };
}
function validatedCollection(collection) {
  if (!collection || !Array.isArray(collection.all) || !Array.isArray(collection.collapsed)
      || collection.total !== collection.all.length || collection.collapsedCount !== collection.collapsed.length
      || collection.hasMore !== (collection.total > collection.collapsedCount)) {
    throw new TypeError("presentation requires a validated callout collection");
  }
  return collection;
}

/** Pure phone view-model compiler. It formats adapter-validated facts; it derives no combat outcomes. */
export function buildEncounterPresentation(encounter, options = {}) {
  if (!encounter || typeof encounter !== "object") throw new TypeError("encounter presentation requires an encounter object");
  const names = new Map((encounter.monsters ?? []).map((body) => [body.canonicalModel, nameOf(body)]));
  const callouts = options.calloutCollection
    ? validatedCollection(options.calloutCollection)
    : compileCalloutCollection(options.calloutCandidates ?? encounter.callouts ?? [], options.calloutContext ?? {}, { collapsedLimit: options.collapsedLimit ?? 1 });
  const roster = {
    summary: rosterNode(encounter.roster?.grammar, names),
    cardinality: rangeText(encounter.roster?.cardinality),
    caveat: "Random and alternative branches are possibilities. Only one branch is selected; listed possibilities are not all co-present.",
  };
  const unknowns = [
    { headline: "Realized turn state is unavailable", detail: "Live HP, Block, Powers, intent, phase, survivors, hand, and move history are not observed." },
    ...(encounter.knownUnknowns ?? []).map((row) => ({ headline: text(row.detail, words(row.unknownId)), detail: `${words(row.status)} · ${words(row.scope)} · ${words(row.reasonCode)}` })),
  ];
  return {
    context: contextPresentation(encounter), roster,
    bodies: (encounter.monsters ?? []).map((body, index) => bodyPresentation(body, index, encounter, names)),
    production: productionPresentation(encounter.production, names),
    lifecycle: lifecyclePresentation(encounter.lifecycle ?? {}, names),
    event: eventPresentation(encounter.event),
    unknowns, callouts,
  };
}

export const presentationInternals = Object.freeze({
  words, rosterNode, moveEffects, graphPresentation, initialEffect,
  productionPresentation, lifecyclePresentation, lifecyclePresentationRecords, eventPresentation, validatedCollection,
});
