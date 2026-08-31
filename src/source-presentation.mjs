import { compileCalloutCollection } from "./decision-callouts.mjs";

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const TARGETS = Object.freeze({
  // Move recipients.
  allOpponentsOfSourceMonster: "all opponents",
  awaitedSummonedCreature: "the summoned creature",
  generatedCardCombatPile: "the generated combat-card pile",
  iteratedCreature: "each selected creature",
  registeredTargets: "the affected targets",
  rngSelectedCombatCard: "one random combat card",
  runtimeSelectedPowerInstance: "the selected Power",
  sourceMonster: "self",
  sourceMonsterCombatState: "the enemy side",
  sourceMonsterOpponents: "the opponent side",
  sourceMonsterTeammates: "teammates",
  // Initial-state recipients.
  constructedMonsterModel: "this enemy's base values",
  customPowerInstance: "the configured Power",
  sourceMonsterLifecycle: "this enemy's lifecycle",
  sourceMonsterModel: "this enemy's base values",
  sourceMonsterMoveState: "this enemy's behavior",
  // Lifecycle recipients.
  allSegments: "all segments",
  currentSameSideTeammates: "same-side teammates",
  combat: "the fight",
  encounter: "the encounter",
  exactEncounter: "this event fight",
  exactOwnerBody: "the exact owner body",
  "exact precreated fatBody": "the precreated replacement body",
  exactAmalgamBody: "the exact Amalgam body",
  exactReturnedBody: "the added body",
  fatBody: "the replacement body",
  newBody: "the new body",
  orderedReturnedBodies: "the added bodies",
  ownerSide: "the owner's side",
  players: "all players",
  presentation: "the fight presentation",
  runState: "the run record",
  runtimeAccumulator: "the checked running total",
  runtimeState: "the checked fight state",
  sameOwnerBody: "the same body",
  samePriestBody: "the same Kin Priest",
  sameQueenBody: "the same Queen",
});
const BOOLEAN_CONDITIONS = Object.freeze({
  "death.targetIsPowerOwner": ["the dying body owns this Power", "the dying body does not own this Power"],
  "death.wasRemovalPrevented": ["death removal was prevented", "death removal was not prevented"],
  "monster.IsHatched": ["this body has hatched", "this body has not hatched"],
  "orderedCurrentTeammates.anyLivingFollower": ["a follower on the same side is alive", "no follower on the same side is alive"],
  "participants.containsOwner": ["this body participates in the side's turn", "this body does not participate in the side's turn"],
  "owner.encounterExactCastSucceeds": ["this is the matching event fight", "this is not the matching event fight"],
  "owner.hasAdaptablePower": ["this body still has Adaptable", "this body no longer has Adaptable"],
  "owner.isDead": ["this body is dead", "this body is alive"],
  "queen.isAlive": ["the Queen is alive", "the Queen is dead"],
  "sameSide.allOtherSegmentsDead": ["all other segments on the same side are dead", "another segment on the same side is alive"],
  "sameSide.anyOtherSegmentAlive": ["another segment on the same side is alive", "no other segment on the same side is alive"],
  "sameSide.anyOtherSegmentAliveAtMove": ["another segment is alive when this behavior resolves", "no other segment is alive when this behavior resolves"],
  "sideTurn.participantsContainsOwner": ["this body is included in the side's turn", "this body is not included in the side's turn"],
  "target.isKinFollower": ["the dying body is a Kin follower", "the dying body is not a Kin follower"],
  "target.isTorchHeadAmalgam": ["the dying body is the Torch Head Amalgam", "the dying body is not the Torch Head Amalgam"],
  targetIsPowerOwner: ["the affected body owns this Power", "the affected body does not own this Power"],
  targetIsQueenOwner: ["the affected body is the Queen linked to this rule", "the affected body is not the linked Queen"],
  "targetPower.isITemporaryPower": ["the affected Power is temporary", "the affected Power is not temporary"],
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
function localizedName(name) {
  if (name?.kind === "localizedText") return name.text;
  if (name?.kind === "localizedTemplate") {
    const base = text(name.template, "Runtime-named body").replace(/#C\{[^}]+\}/g, "").trim();
    return `${base} (runtime number)`;
  }
  return "Unknown body";
}
function nameOf(body) { return localizedName(body?.name); }
function rangeReferenceText(reference) {
  if (reference === "RUNTIME.PRODUCTION.LIVING_FOG_BLOAT_AMOUNT") return "Bloat's runtime summon count";
  return typeof reference === "string" && reference ? "runtime-defined count" : null;
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

/** Concise symbolic notation for explicit callers; raw trees remain in Technical audit. */
export function expressionText(expression, depth = 0) {
  if (depth > 8 || expression == null) return "unknown value";
  if (typeof expression !== "object") return String(expression);
  switch (expression.kind) {
    case "constant": return String(expression.value);
    case "convert": return expressionText(expression.expression, depth + 1);
    case "range": return `${expressionText(expression.minimum, depth + 1)}–${expressionText(expression.maximum, depth + 1)}`;
    case "ascensionSelect": return `A${expression.threshold}+ ${expressionText(expression.atOrAbove, depth + 1)}; below A${expression.threshold} ${expressionText(expression.below, depth + 1)}`;
    case "arithmetic": {
      const operator = OPERATORS[expression.operator] ?? "?";
      return `(${(expression.operands ?? []).map((item) => expressionText(item, depth + 1)).join(` ${operator} `) || "unknown operands"})`;
    }
    case "comparison":
    case "compare": return conditionText(expression, depth + 1);
    case "conditional": return `if ${conditionText(expression.condition, depth + 1)}, ${expressionText(expression.whenTrue, depth + 1)}; otherwise ${expressionText(expression.whenFalse, depth + 1)}`;
    case "allOf": return (expression.operands ?? []).map((item) => conditionText(item, depth + 1)).join(" and ") || "all checked conditions";
    case "anyOf": return (expression.operands ?? []).map((item) => conditionText(item, depth + 1)).join(" or ") || "a checked condition";
    case "reference": return "checked amount";
    case "delegate": return expressionText(expression.expression, depth + 1);
    case "count": return "checked body count";
    case "graphLifetimeOnce": return "unused once-per-fight opportunity";
    case "methodBoolean": return "checked runtime condition";
    case "stateVariable": return "state-dependent value";
    case "runtimeInput": return "runtime-defined value";
    default: return "checked value";
  }
}
function booleanConditionText(condition) {
  if (!(condition?.kind === "comparison" || condition?.kind === "compare")) return null;
  const left = condition.left ?? condition.operands?.[0];
  const right = condition.right ?? condition.operands?.[1];
  if (left?.kind !== "runtimeInput" || right?.kind !== "constant" || typeof right.value !== "boolean") return null;
  const meanings = BOOLEAN_CONDITIONS[left.name];
  if (!meanings) return "the checked runtime condition is resolved";
  const equal = condition.operator === "equal";
  const positive = equal ? right.value : !right.value;
  return meanings[positive ? 0 : 1];
}
export function conditionText(condition, depth = 0) {
  if (depth > 8 || !condition || typeof condition !== "object") return "the checked condition applies";
  if (condition.kind === "unconditional") return "always for this rule";
  const boolean = booleanConditionText(condition);
  if (boolean) return boolean;
  switch (condition.kind) {
    case "constant": return condition.value === true ? "always" : condition.value === false ? "never" : "the checked condition applies";
    case "allOf": return (condition.operands ?? []).map((item) => conditionText(item, depth + 1)).join(" and ") || "all checked conditions apply";
    case "anyOf": return (condition.operands ?? []).map((item) => conditionText(item, depth + 1)).join(" or ") || "a checked condition applies";
    case "graphLifetimeOnce": return "this once-per-fight opportunity has not been used";
    case "methodBoolean": return "the checked runtime condition passes";
    case "comparison":
    case "compare": {
      const leftValue = condition.left ?? condition.operands?.[0];
      const rightValue = condition.right ?? condition.operands?.[1];
      if (leftValue?.kind === "runtimeInput" && leftValue.name === "targetPower.typeRawValue"
          && condition.operator === "equal" && rightValue?.kind === "constant" && rightValue.value === 2) {
        return "the affected Power has the checked removable type";
      }
      const left = practicalAmountText(leftValue);
      const right = practicalAmountText(rightValue);
      const operator = OPERATORS[condition.operator];
      return operator ? `${left} ${operator} ${right}` : "the checked comparison passes";
    }
    default: return "the checked condition applies";
  }
}
function practicalAmountText(value) {
  if (value == null || typeof value !== "object") return value == null ? "checked amount" : String(value);
  if (value.kind === "runtimeInput") {
    const labels = Object.freeze({
      "monster.Respawns": "completed respawns",
      "power.amount": "the Power amount",
      "targetPower.typeRawValue": "the affected Power's checked removal type",
    });
    return labels[value.name] ?? "runtime-defined amount";
  }
  switch (value.kind) {
    case "constant": return String(value.value);
    case "convert": return practicalAmountText(value.expression);
    case "range": return `${practicalAmountText(value.minimum)}–${practicalAmountText(value.maximum)}`;
    case "ascensionSelect": return `A${value.threshold}+ ${practicalAmountText(value.atOrAbove)}; below A${value.threshold} ${practicalAmountText(value.below)}`;
    case "count": return "checked body count";
    case "stateVariable": return "state-dependent amount";
    default: return "checked amount";
  }
}
function amountText(value) { return practicalAmountText(value); }
function targetText(target) { return TARGETS[target] ?? "recipient unresolved"; }
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
    case "subscribe": line = `${recipient} · listen for the checked fight trigger`; break;
    case "relationship": line = `${recipient} · establish the checked body relationship`; break;
    default: line = `${recipient} · checked initial effect unresolved`; break;
  }
  return {
    timing: lowerWords(fact.stage), line,
    condition: fact.condition?.kind === "unconditional" ? null : conditionText(fact.condition),
    unresolved: (fact.runtimeInputs ?? []).length ? `${fact.runtimeInputs.length} runtime modifier input${fact.runtimeInputs.length === 1 ? "" : "s"} remain unresolved` : null,
  };
}

function moveEffects(move, names) {
  const operations = move.operations ?? [], consumed = new Set(), effects = [];
  const helperText = Object.freeze({
    reattach: "reattach through the checked revive rule",
    fabricate: "produce the checked bot body",
    chooseCurse: "choose the checked curse",
    hatch: "perform the checked hatch",
    pressureState: "update the checked pressure state",
  });
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
      case "attackHitCount": line = `the preceding attack · ${amountText(operation.value)} hits`; break;
      case "gainBlock": line = `${target} · gain ${amountText(operation.value)} Block`; break;
      case "heal": line = `${target} · heal ${amountText(operation.value)} HP`; break;
      case "applyPower": line = `${target} · apply ${amountText(operation.value)} ${cardOrPower(operation.model)}`; break;
      case "removePower": line = `${target} · remove ${movePowerIdentity(operation)}`; break;
      case "addStatusCard": line = `${target} · add ${amountText(operation.value)} ${cardOrPower(operation.model)} card${String(operation.value?.value) === "1" ? "" : "s"}`; break;
      case "addGeneratedCard": line = `${target} · add 1 generated ${cardOrPower(operation.model)} card`; break;
      case "removeCard": line = `${target} · remove that card from combat`; break;
      case "stateWrite": line = `${target} · update this behavior's checked counter or state`; break;
      case "summon": line = `${target} · add ${modelName(operation.model, names)} in the checked slot`; break;
      case "escape": line = `${target} · escape through the checked fight rule`; break;
      case "kill": line = `${target} · enter the checked death rule`; break;
      case "transition": line = operation.transition === "noOp" ? "no combat effect" : "advance the checked behavior state"; break;
      case "helperEffect": line = helperText[operation.helper] ?? "checked linked effect; exact consequence unresolved"; break;
      default: line = `${target} · checked effect details unresolved`; break;
    }
    effects.push({ order: effects.length + 1, line });
  }
  if (!effects.length) effects.push({ order: 1, line: "No checked combat effect in this behavior" });
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

function lifecycleOperationsForBody(encounter, ownerModel, kind) {
  const result = [];
  for (const { row } of lifecyclePresentationRecords(encounter.lifecycle?.mechanics ?? {})) {
    for (const branch of row.transitions ?? row.branches ?? [row]) {
      const operations = branch.orderedEffects ?? row.orderedEffects ?? row.orderedPerPlayer ?? [];
      for (const operation of operations) if (operation?.kind === kind && operation.owner === ownerModel) result.push({ branch, operation });
    }
  }
  return result;
}
function hpBranchText(branch) {
  if (!branch || typeof branch !== "object") return "checked HP range";
  const below = branch.belowA8, above = branch.atOrAboveA8;
  const render = (value) => Array.isArray(value) ? value.join("–") : String(value);
  if (below !== undefined && above !== undefined) return `${render(below)} HP below A8; ${render(above)} HP at A8+`;
  return "checked HP range";
}
function formHpText(state, stateIndex, body, encounter) {
  const base = body.hp?.a8SinglePlayer;
  if (state.hpState === "initial" || state.hpState === "phase1") return base ? `${rangeText(base)} HP · A8 single player` : "HP is runtime-defined";
  if (state.hpState === "hatched") {
    const hatch = lifecycleOperationsForBody(encounter, body.canonicalModel, "hatch")
      .find(({ operation }) => operation.hpInclusiveRange)?.operation;
    return hatch ? hpBranchText({ belowA8: hatch.hpInclusiveRange.belowA8, atOrAboveA8: hatch.hpInclusiveRange.atOrAboveA8 }) : "Hatch HP is defined by the checked hatch rule";
  }
  const phase = /^phase(\d+)$/.exec(state.hpState ?? "");
  if (phase && Number(phase[1]) > 1) {
    const revive = lifecycleOperationsForBody(encounter, body.canonicalModel, "reviveHpByRef")[Number(phase[1]) - 2]?.operation;
    return revive?.baseHp ? hpBranchText(revive.baseHp) : "Revive HP is defined by the checked phase rule";
  }
  return "HP is defined by the checked form rule";
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
    hp: hp ? `${rangeText(hp)} HP · A8 single player` : "HP is runtime-defined",
    hpHasRuntimeInputs: JSON.stringify(body.hp?.expression ?? {}).includes('"stateVariable"') || JSON.stringify(body.hp?.expression ?? {}).includes('"runtimeInput"'),
    forms: (body.states ?? []).map((state, stateIndex) => ({
      name: /^phase\d+$/.test(state.hpState ?? "") ? `Phase ${String(state.hpState).slice(5)} — ${localizedName(state.displayName)}` : localizedName(state.displayName),
      hp: formHpText(state, stateIndex, body, encounter),
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
    const repeatText = Object.freeze({
      graphRepeatWhileAvailable: "repeat while production remains available",
      graphLifetimeOnce: "one production opportunity during this fight",
      graphCycleRepeat: "repeat on the checked behavior cycle",
    })[repeat];
    const attempts = (producer.attempts ?? []).map((attempt) => {
      const pool = pools.get(attempt.poolRef);
      const candidates = (pool?.candidateModels ?? []).map((model) => modelName(model, names)).join(" / ") || "unknown body";
      const selection = pool?.selection?.kind === "runtimeRng" ? "runtime-random" : "fixed";
      return `${selection} {${candidates}}`;
    });
    return {
      owner: modelName(producer.ownerModel, names),
      cadence: `${count} added bod${count === "1" ? "y" : "ies"} per eligible trigger`,
      condition: producer.availability?.expression ? conditionText(producer.availability.expression) : "checked availability rule",
      repeat: repeatText ?? "checked repeat rule",
      attempts,
    };
  });
  return {
    possibilities: (production.producedBodies ?? []).map((model) => modelName(model, names)),
    caveat: "Produced bodies are possibilities from eligible rules, not initial or co-present bodies.",
    rules,
  };
}

const LIFECYCLE_WRITES = Object.freeze({
  "_hatched:true": "mark this body as hatched",
  "IsHatched/_isHatched:true": "mark this body as hatched",
  "Data.isReviving:true": "begin this body's revival",
  "Data.isReviving:false": "finish this body's revival",
  "AdaptablePower.Data.isReviving:true": "begin this body's Adaptable revival",
  "AdaptablePower.Data.isReviving:false": "finish this body's Adaptable revival",
  "HasAmalgamDied:true": "record that the Amalgam has died",
  "IsAboutToBlow:true": "enter the about-to-explode phase",
  "RanOutOfTime:true": "record that the event fight ran out of time",
});
const LIFECYCLE_FAMILIES = Object.freeze({
  cleanup: "Fight cleanup",
  deathProduction: "On-death production",
  "eventCombat.battleTimeLimit": "Event fight clock",
  "eventCombat.registrations": "Event fight triggers",
  phaseSystems: "Phases, revive and hatch",
  powerRetentionPolicies: "Death and Power retention",
  relationships: "Linked bodies",
  subscriptions: "Triggered rules",
});
const LIFECYCLE_TRIGGERS = Object.freeze({
  AfterSideTurnEnd: "after that side's turn ends",
  BeforeDeath: "before death",
  BeforeRemovedFromRoom: "before removal from the room",
  actualNonPreventedOwnerDeath: "after the owner actually dies",
  fourArgumentAfterDeath: "after a body dies",
});
function retentionPolicyText(row) {
  const power = cardOrPower(row.power);
  if (row.result !== true && row.result !== false) return null;
  switch (row.hook) {
    case "ShouldCreatureBeRemovedFromCombatAfterDeath":
      return row.result ? `${power} allows its body to be removed after death` : `${power} keeps its body present for checked post-death handling`;
    case "ShouldOwnerDeathTriggerFatal":
      return row.result ? `owner death triggers fatal handling for ${power}` : `owner death does not trigger fatal handling for ${power}`;
    case "ShouldPowerBeRemovedAfterOwnerDeath":
      return row.result ? `${power} is removed after its owner dies` : `${power} stays through its owner's death`;
    case "ShouldPowerBeRemovedOnDeath":
      return row.result ? `${power} is removed when its owner dies` : `${power} remains when its owner dies`;
    case "ShouldStopCombatFromEnding":
      return row.result ? `${power} keeps the fight from ending while it remains` : `${power} does not keep the fight from ending`;
    default: return null;
  }
}
function lifecycleWriteText(operation) {
  return LIFECYCLE_WRITES[`${operation.field}:${String(operation.value)}`] ?? null;
}
function lifecycleIncrementText(operation) {
  if (operation.field === "ExtraRunFields.TestSubjectKills") return "record another Test Subject death for the run";
  if (operation.field === "Respawns") return "increase this Test Subject's respawn count";
  return null;
}
function behaviorPhaseText(move) {
  const phases = Object.freeze({
    AboutToBlow: "prepare the about-to-explode behavior",
    DeadState: "enter the temporary dead state",
    Enraged: "enter the enraged behavior",
    REVIVE_MOVE: "prepare the revive behavior",
  });
  return phases[move] ?? "enter the checked next behavior";
}
function lifecycleAttackText(operation, names, sequence, index) {
  const target = targetText(operation.target);
  const hasPriorSnapshot = sequence.slice(0, index).some((row) => row?.kind === "snapshotDamage");
  if (operation.amountRef && hasPriorSnapshot) return `${target} · deal the snapshotted Steam Eruption amount`;
  if (operation.sourceRef === "behavior.operations.attack") {
    const owner = modelName(operation.owner, names);
    return `${target} · perform ${owner}'s checked attack`;
  }
  if (operation.amount !== undefined || operation.formula !== undefined) {
    return `${target} · deal ${amountText(operation.amount ?? operation.formula)} damage`;
  }
  return `${target} · perform the checked attack; its damage amount is defined by that attack`;
}
function lifecycleEffect(operation, names, sequence = [], index = 0) {
  const target = targetText(operation.target);
  switch (operation.kind) {
    case "attack": return lifecycleAttackText(operation, names, sequence, index);
    case "snapshotDamage": return `${target} · remember Steam Eruption's current amount for the coming attack`;
    case "createBody": return `${target} · create ${modelName(operation.model, names)}`;
    case "createMutableBody": return `${target} · create ${modelName(operation.model, names)} with its checked starting state`;
    case "precreateBody": return `${target} · prepare ${modelName(operation.model, names)} before adding it`;
    case "coreAddByRef": return `${target} · add ${operation.model ? modelName(operation.model, names) : "the exact created body"}`;
    case "coreDeathByRef": return `${target} · run this body's checked death handling`;
    case "heal": return `${target} · restore HP by the named Power's checked amount`;
    case "reviveHpByRef": return `${target} · restore maximum and revived HP to ${operation.baseHp ? hpBranchText(operation.baseHp) : "the checked revive amount"}`;
    case "setMaxAndCurrentHp": return operation.value === 999999999
      ? `${target} · set HP to 999,999,999 for the explosion phase`
      : `${target} · set max and current HP to the checked amount`;
    case "hatch": {
      const hp = operation.hpInclusiveRange?.atOrAboveA8;
      const below = operation.hpInclusiveRange?.belowA8;
      return `${target} · hatch${Array.isArray(hp) && Array.isArray(below) ? ` with ${below.join("–")} HP below A8; ${hp.join("–")} HP at A8+` : " with the checked HP range"}`;
    }
    case "forceMove":
    case "configureMove": return `${target} · ${behaviorPhaseText(operation.move)}`;
    case "forceMoveConditional": return `${target} · enter the enraged behavior if the checked next behavior is pending`;
    case "removePower": return `${target} · remove ${cardOrPower(operation.power)}`;
    case "applyPowerByRef": return `${target} · apply ${cardOrPower(operation.power)} by its checked rule`;
    case "applyTargetedPower": return `${target} · apply ${cardOrPower(operation.power)}`;
    case "skipPowerApplication": return `${target} · skip ${cardOrPower(operation.power)} application`;
    case "decrementPower": return `${target} · reduce ${cardOrPower(operation.power ?? operation.owner)} by ${operation.amount ?? "the checked amount"}`;
    case "snapshotPowers": return `${target} · remember current Powers except Minion for hatch cleanup`;
    case "removeSnapshottedPowers": return `${target} · remove the remembered Powers except ${cardOrPower(operation.retainedPower)}`;
    case "writeState": {
      const meaning = lifecycleWriteText(operation);
      return meaning ? `${target} · ${meaning}` : null;
    }
    case "incrementState": {
      const meaning = lifecycleIncrementText(operation);
      return meaning ? `${target} · ${meaning}` : null;
    }
    case "escape": return `${target} · escape${operation.removeCreatureNode === true ? " and leave the fight" : " through the checked fight rule"}`;
    case "ordinaryCentralizedVictoryByRef": return "check ordinary fight completion";
    case "setInteraction": return `${target} · become ${operation.enabled === true ? "targetable" : operation.enabled === false ? "untargetable" : "subject to the checked targeting state"}`;
    case "repeatAttempts": return `${target} · make ${operation.count ?? "the checked number of"} ordered production attempts`;
    case "kill": return `${target} · die through the checked death rule`;
    case "clearRelationship": return "clear the Queen's link to the dead Amalgam";
    case "accumulateRuntimeGold": return "total the gold held by the checked Thievery effects";
    case "markGoldStolen": return "record the nonzero stolen-gold total for this encounter";
    case "orderedTeammateQuery": return "check same-side followers in order";
    case "allFollowerDeathResponse": return `${target} · respond after no same-side follower remains`;
    case "unsubscribeSelf": return `${target} · stop this one-time trigger`;
    // These are audiovisual, display-only, or await-boundary records. Their exact
    // records remain in Technical audit and do not masquerade as combat effects.
    case "ambientAndMusicCleanup":
    case "awaitMethod":
    case "backgroundAnimation":
    case "changeHpDisplay":
    case "delayedReveal":
    case "musicAndSfx":
    case "musicAndTalk":
    case "playHpChangeSfx":
    case "playSfx":
    case "playVfx":
    case "presentationCleanup":
    case "presentationFade":
    case "setNodeVisible":
    case "triggerAnimation": return null;
    default: return null;
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
function lifecyclePresentation(lifecycle, names) {
  const mechanics = [];
  for (const { path, row } of lifecyclePresentationRecords(lifecycle.mechanics ?? {})) {
    const transitions = row.transitions ?? row.branches ?? [row];
    const branches = transitions.map((transition) => {
      const sourceEffects = transition.orderedEffects ?? row.orderedEffects ?? row.orderedPerPlayer ?? [];
      const orderedEffects = [...sourceEffects]
        .filter((effect) => effect && typeof effect === "object")
        .sort((left, right) => (left.order ?? 0) - (right.order ?? 0));
      const policy = row.hook ? retentionPolicyText(row) : null;
      const effects = [
        policy,
        ...orderedEffects.map((effect, index) => lifecycleEffect(effect, names, orderedEffects, index)),
        transition.outcome === "completedNoOp" ? "complete with no combat effect"
          : transition.outcome === "completedWithoutWriteOrEscape" ? "complete without changing the clock or escaping" : null,
      ].filter(Boolean);
      const trigger = row.trigger ? LIFECYCLE_TRIGGERS[row.trigger] ?? "at the checked fight trigger" : null;
      const participant = row.participantPolicy === "only when participants contains exact Power owner"
        ? "only when that Power's owner takes part in the side turn" : row.participantPolicy ? "under the checked participant rule" : null;
      const repeat = transition.repeatability === "oneShot" ? "once"
        : transition.repeatability === "untilRemoval" ? "until this rule is removed" : transition.repeatability;
      const clock = [repeat ? text(repeat) : null, trigger, participant].filter(Boolean);
      return {
        condition: transition.condition ? conditionText(transition.condition) : row.condition ? conditionText(row.condition) : null,
        effects,
        repeat: clock.length ? clock.join(" · ") : null,
      };
    });
    const practicalBranches = branches.filter((branch) => branch.effects.length > 0);
    if (practicalBranches.length) {
      mechanics.push({ family: LIFECYCLE_FAMILIES[path.join(".")] ?? "Other checked lifecycle rule", branches: practicalBranches });
    }
  }
  return {
    rules: [
      lifecycle.removal?.deathMoveDeferral ? "Death removal · a dying enemy remains until its queued death behavior finishes." : null,
      lifecycle.combatTermination?.victoryPredicate ? "Fight completion · no living primary enemy and no remaining effect that keeps combat open." : null,
      lifecycle.combatTermination?.victoryPredicate?.allEscaped ? `If all enemies escape · ${lifecycle.combatTermination.victoryPredicate.allEscaped}.` : null,
    ].filter(Boolean),
    mechanics,
  };
}

const EVENT_EFFECT_KINDS = Object.freeze(new Set([
  "addCurseToDeck", "constructReward", "damage", "gainGold",
  "offerRewards", "restSiteHeal", "stateWrite", "upgradeCard",
]));
function eventEffect(row) {
  let effect;
  switch (row.kind) {
    case "addCurseToDeck": effect = `add an ${cardOrPower(row.model)} curse to the deck`; break;
    case "constructReward": effect = "construct a relic reward for the reward list"; break;
    case "damage": effect = "lose HP equal to the event's checked HP-loss amount"; break;
    case "gainGold": effect = "gain the event's checked gold amount"; break;
    case "offerRewards": effect = "offer the constructed reward list"; break;
    case "restSiteHeal": effect = "heal by the checked rest-site amount"; break;
    case "stateWrite": effect = row.value === true ? "record that this event fight has started" : "update the checked event state"; break;
    case "upgradeCard": effect = `upgrade up to ${row.maximum ?? "the checked number of"} selected cards`; break;
    default: return null;
  }
  const condition = row.condition === "rewardListNonEmpty"
    ? " · if the constructed reward list is not empty"
    : row.condition ? " · when the checked event condition applies" : "";
  return `${effect}${condition}`;
}
function eventPresentation(event) {
  if (!event) return null;
  const scripts = event.scripts ?? {};
  return {
    behavior: event.turnMachine?.behaviorClassification ? "checked event-fight turn behavior" : "event-fight behavior unavailable",
    effects: (scripts.effects ?? []).map(eventEffect).filter(Boolean),
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
  words, rosterNode, moveEffects, graphPresentation, initialEffect, targetText,
  productionPresentation, lifecyclePresentation, lifecyclePresentationRecords, lifecycleEffect,
  retentionPolicyText, lifecycleWriteText, eventPresentation, eventEffect, validatedCollection,
  BOOLEAN_CONDITIONS, EVENT_EFFECT_KINDS, LIFECYCLE_WRITES, TARGETS,
});
