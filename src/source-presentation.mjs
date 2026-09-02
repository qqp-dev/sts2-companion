import { checkedCalloutCandidates } from "./checked-callouts.mjs";
import { compileCalloutCollection } from "./decision-callouts.mjs";
import { scaleMechanicsText, scaleRange } from "./book.mjs";
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
    case "reference": return "unresolved source reference";
    case "delegate": return expressionText(expression.expression, depth + 1);
    case "count": return "checked body count";
    case "graphLifetimeOnce": return "unused once-per-fight opportunity";
    case "methodBoolean": return "checked runtime condition";
    case "stateVariable": return "state-dependent value";
    case "runtimeInput": return "runtime-defined value";
    default: return "unsupported expression kind";
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
  if (value == null || typeof value !== "object") return value == null ? null : String(value);
  if (value.kind === "runtimeInput") {
    const labels = Object.freeze({
      "monster.Respawns": "completed respawns",
      "power.amount": "the Power amount",
      "targetPower.typeRawValue": "the affected Power's removal type",
    });
    return labels[value.name] ?? null;
  }
  switch (value.kind) {
    case "constant": return String(value.value);
    case "convert":
    case "delegate": return practicalAmountText(value.expression);
    case "range": {
      const minimum = practicalAmountText(value.minimum), maximum = practicalAmountText(value.maximum);
      return minimum === null || maximum === null ? null : `${minimum}–${maximum}`;
    }
    case "ascensionSelect": {
      const above = practicalAmountText(value.atOrAbove), below = practicalAmountText(value.below);
      return above === null || below === null ? null : `A${value.threshold}+ ${above}; below A${value.threshold} ${below}`;
    }
    case "arithmetic": {
      const operator = OPERATORS[value.operator];
      const operands = (value.operands ?? []).map(practicalAmountText);
      return !operator || !operands.length || operands.includes(null) ? null : operands.join(` ${operator} `);
    }
    case "conditional": {
      const whenTrue = practicalAmountText(value.whenTrue), whenFalse = practicalAmountText(value.whenFalse);
      if (whenTrue === null || whenFalse === null) return null;
      if (whenTrue === whenFalse) return whenTrue;
      return `${whenTrue} when ${conditionText(value.condition)}; otherwise ${whenFalse}`;
    }
    case "count": return "body count at resolution";
    case "stateVariable": {
      const labels = Object.freeze({
        axebotRespawnCount: "completed respawns",
        "combat.currentSide": "combat side",
        "initial.decimillipedeSharedMaxHp": "the encounter's shared starting HP roll",
        "initial.toughEggHatchHp": "the stored hatched-form HP",
      });
      return labels[value.name] ?? "the named state value";
    }
    case "reference": return null;
    default: return null;
  }
}
function amountText(value, unresolved) { return practicalAmountText(value) ?? unresolved; }
function runtimeInputDetail(reference) {
  if (typeof reference !== "string") return "named runtime input";
  if (reference === "RUNTIME.COMBAT.CURRENT_SIDE") return "combat-side selection";
  if (reference === "RUNTIME.INITIAL.DECIMILLIPEDE_SHARED_MAX_HP") return "shared starting-HP roll";
  if (reference === "RUNTIME.INITIAL.TOUGH_EGG_HATCH_HP") return "stored hatched-form HP";
  if (reference === "RUNTIME.EXTERNAL.POWER_AMOUNT_HOOKS") return "runtime Power modifiers";
  if (reference.startsWith("RUNTIME.EXPRESSION.")) return "enemy-definition amount";
  if (reference.includes("MULTIPLAYER")) return "player-count scaling input";
  return "named runtime modifier";
}
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
  const model = effect.model ? cardOrPower(effect.model) : null;
  const amount = amountText(fact.baseValue?.expression, "amount unresolved");
  let line;
  switch (effect.kind) {
    case "applyPower": line = `${recipient} · ${model} ${amount}`; break;
    case "gainBlock": line = `${recipient} · ${amount === "amount unresolved" ? "Block amount unresolved" : `${amount} Block`}`; break;
    case "setMaxAndCurrentHp": line = `${recipient} · ${amount === "amount unresolved" ? "starting HP amount unresolved" : `set max and starting HP to ${amount}`}`; break;
    case "setCurrentHp": line = `${recipient} · ${amount === "amount unresolved" ? "starting HP amount unresolved" : `set starting HP to ${amount}`}`; break;
    case "setState": line = `${recipient} · ${amount === "amount unresolved" ? "initial encounter-state value unresolved" : `encounter state ${amount}`}`; break;
    case "forceMoveState": line = `${recipient} · initial behavior state`; break;
    case "configurePowerTarget": line = `${recipient} · configure ${model ?? "Power"} target`; break;
    case "afflictCard": line = `${recipient} · card affliction`; break;
    case "subscribe": line = `${recipient} · listen for the named fight trigger`; break;
    case "relationship": line = `${recipient} · establish the named body relationship`; break;
    default: line = `${recipient} · initial effect type unresolved`; break;
  }
  const unresolvedInputs = [...new Set((fact.runtimeInputs ?? []).map(runtimeInputDetail))];
  if (effect.kind === "applyPower" && amount !== "amount unresolved" && unresolvedInputs.length) {
    line = `${recipient} · ${model} base ${amount}`;
  }
  return {
    timing: lowerWords(fact.stage), line,
    condition: fact.condition?.kind === "unconditional" ? null : conditionText(fact.condition),
    unresolved: unresolvedInputs.length ? unresolvedInputs.join(" · ") : null,
  };
}
function moveEffects(move, names) {
  const operations = move.operations ?? [], consumed = new Set(), effects = [];
  const helperText = Object.freeze({
    reattach: "reattach through the named revive rule",
    fabricate: "produce a possible bot body",
    chooseCurse: "choose the defined curse",
    hatch: "perform the defined hatch",
    pressureState: "update the pressure state",
  });
  for (let index = 0; index < operations.length; index += 1) {
    if (consumed.has(index)) continue;
    const operation = operations[index], target = targetText(operation.target);
    let line;
    switch (operation.kind) {
      case "attack": {
        const hitIndex = operations[index + 1]?.kind === "attackHitCount" ? index + 1 : -1;
        const hits = hitIndex >= 0 ? amountText(operations[hitIndex].value, "hit count unresolved") : "1";
        if (hitIndex >= 0) consumed.add(hitIndex);
        const amount = practicalAmountText(operation.value);
        line = `${target} · ${amount === null ? "damage amount unresolved for this behavior" : `${amount} damage`}${hits === "1" ? "" : ` × ${hits} hits`}`;
        break;
      }
      case "attackHitCount": line = `the preceding attack · ${amountText(operation.value, "hit count unresolved")} hits`; break;
      case "gainBlock": {
        const amount = practicalAmountText(operation.value);
        line = `${target} · ${amount === null ? "Block amount unresolved for this behavior" : `${amount} Block`}`;
        break;
      }
      case "heal": {
        const amount = practicalAmountText(operation.value);
        line = `${target} · ${amount === null ? "healing amount unresolved for this behavior" : `heal ${amount} HP`}`;
        break;
      }
      case "applyPower": {
        const power = cardOrPower(operation.model), amount = practicalAmountText(operation.value);
        line = `${target} · ${power} ${amount ?? "amount unresolved for this behavior"}`;
        break;
      }
      case "removePower": line = `${target} · remove ${movePowerIdentity(operation)}`; break;
      case "addStatusCard": {
        const amount = practicalAmountText(operation.value);
        line = `${target} · ${amount === null ? `${cardOrPower(operation.model)} card count unresolved` : `add ${amount} ${cardOrPower(operation.model)} card${amount === "1" ? "" : "s"}`}`;
        break;
      }
      case "addGeneratedCard": line = `${target} · add 1 generated ${cardOrPower(operation.model)} card`; break;
      case "removeCard": line = `${target} · remove that card from combat`; break;
      case "stateWrite": line = `${target} · update this behavior's counter or state`; break;
      case "summon": line = `${target} · add ${modelName(operation.model, names)} in the defined slot`; break;
      case "escape": line = `${target} · escape through the defined fight rule`; break;
      case "kill": line = `${target} · enter the defined death rule`; break;
      case "transition": line = operation.transition === "noOp" ? "no combat effect" : "advance behavior state"; break;
      case "helperEffect": line = helperText[operation.helper] ?? "linked effect consequence unresolved"; break;
      default: line = `${target} · effect type unresolved`; break;
    }
    effects.push({ order: effects.length + 1, line });
  }
  if (!effects.length) effects.push({ order: 1, line: "No combat consequence in this behavior" });
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
  if (starts.length) parts.push(`opens with ${starts.join(" / ")}`);
  if (hasCycle) parts.push("repeating cycle");
  if (topology.followUpEdges) parts.push(`${topology.followUpEdges} follow-up${topology.followUpEdges === 1 ? "" : "s"}`);
  if (topology.randomBranches) parts.push(`${topology.randomBranches} random branch${topology.randomBranches === 1 ? "" : "es"}`);
  if (topology.conditionalBranches) parts.push(`${topology.conditionalBranches} conditional branch${topology.conditionalBranches === 1 ? "" : "es"}`);
  if (topology.mustOnceFlags) parts.push(`${topology.mustOnceFlags} once-only flag${topology.mustOnceFlags === 1 ? "" : "s"}`);
  return { headline: parts.length ? parts.join(" · ") : "fixed behavior sequence", paths, exact: true };
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
  (body.moves ?? []).forEach((move, moveIndex) => effectLabels.set(move.stateId, `sequence ${moveIndex + 1}`));
  const initial = encounter.roster.possibleInitialBodies.includes(body.canonicalModel);
  const produced = encounter.production?.producedBodies?.includes(body.canonicalModel) === true;
  const roles = [initial ? "possible initial body" : null, produced ? "produced possibility" : null].filter(Boolean);
  const hp = body.hp?.a8SinglePlayer;
  return {
    bodyIndex: index,
    name: nameOf(body),
    role: roles.join(" · ") || "encounter body",
    hp: hp ? `${rangeText(hp)} HP · A8 single player` : "HP is runtime-defined",
    hpNote: body.canonicalModel === "MONSTER.AXEBOT" ? "Respawns · +10 Max HP per completed respawn (0–2)" : null,
    forms: (body.states ?? []).map((state, stateIndex) => ({
      name: /^phase\d+$/.test(state.hpState ?? "") ? `Phase ${String(state.hpState).slice(5)} — ${localizedName(state.displayName)}` : localizedName(state.displayName),
      hp: formHpText(state, stateIndex, body, encounter),
    })),
    initialEffects: (body.initialState ?? []).map(initialEffect),
    effects: (body.moves ?? []).map((move, moveIndex) => ({
      marker: moveIndex + 1,
      timing: "possible behavior sequence",
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
      ownerIndex: names.has(producer.ownerModel) ? [...names.keys()].indexOf(producer.ownerModel) : null,
      cadence: `${count} added bod${count === "1" ? "y" : "ies"} per eligible trigger`,
      condition: producer.availability?.expression ? conditionText(producer.availability.expression) : "production availability condition unresolved",
      repeat: repeatText ?? "production repeat boundary unresolved",
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
    return `${target} · deal ${amountText(operation.amount ?? operation.formula, "damage amount unresolved for this lifecycle rule")} damage`;
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
    case "heal": return `${target} · restore HP by the named Power's amount`;
    case "reviveHpByRef": return `${target} · restore maximum and revived HP to ${operation.baseHp ? hpBranchText(operation.baseHp) : "the checked revive amount"}`;
    case "setMaxAndCurrentHp": return operation.value === 999999999
      ? `${target} · set HP to 999,999,999 for the explosion phase`
      : `${target} · max and current HP amount unresolved for this phase`;
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
    case "decrementPower": return `${target} · reduce ${cardOrPower(operation.power ?? operation.owner)} by ${operation.amount ?? "an amount defined by that Power"}`;
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
function lifecycleBodyIndexes(row, bodyIndexes, powerBodyIndexes) {
  const models = new Set();
  // Some checked relationship operations wrap a canonical owner in quantified prose.
  // Extract only exact IDs already joined to this encounter; never infer a new model.
  const addKnownModels = (value) => {
    if (typeof value !== "string") return;
    for (const model of bodyIndexes.keys()) {
      const start = value.indexOf(model);
      if (start < 0) continue;
      const before = value[start - 1], after = value[start + model.length];
      if ((!before || !/[A-Z0-9_.]/.test(before)) && (!after || !/[A-Z0-9_.]/.test(after))) models.add(model);
    }
  };
  for (const key of ["ownerModel", "canonicalModel"]) addKnownModels(row[key]);
  for (const key of ["ownerModels", "applicableConcreteModels"]) for (const model of row[key] ?? []) addKnownModels(model);
  const operations = (row.transitions ?? row.branches ?? [row]).flatMap((branch) => branch.orderedEffects ?? row.orderedEffects ?? row.orderedPerPlayer ?? []);
  for (const operation of operations) for (const key of ["owner", "model"]) addKnownModels(operation?.[key]);
  const indexes = new Set([...models].map((model) => bodyIndexes.get(model)).filter((index) => index !== undefined));
  for (const power of [row.power, row.producerPower, row.listener]) for (const index of powerBodyIndexes.get(power) ?? []) indexes.add(index);
  return [...indexes].sort((a, b) => a - b);
}
function lifecyclePresentation(lifecycle, names, bodyIndexes = new Map(), powerBodyIndexes = new Map()) {
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
      mechanics.push({ family: LIFECYCLE_FAMILIES[path.join(".")] ?? "Other checked lifecycle rule", bodyIndexes: lifecycleBodyIndexes(row, bodyIndexes, powerBodyIndexes), branches: practicalBranches });
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


const COMBAT_STATS = new Set(["strength", "dexterity", "vigor"]);

function sentenceParts(value) {
  return String(value ?? "").split(/(?<=\.)\s+/).map((part) => part.trim().replace(/\.$/, "")).filter(Boolean);
}
function signedGainText(amount, subject) {
  return `${/^[+−-]/.test(amount) ? "" : "+"}${amount} ${subject}`;
}
function mechanicAtom(sentence) {
  const value = String(sentence ?? "").trim().replace(/\.$/, "");
  let match = /^Deals?\s+(.+?)\s+damage$/i.exec(value);
  if (match) return {
    kind: "attack", amount: match[1], subject: "damage", text: `${match[1]} damage`, sentence: value,
    operationTarget: "allOpponentsOfSourceMonster", amountPolarity: operationAmountPolarity(match[1]),
  };
  match = /^Gains?\s+(.+)$/i.exec(value);
  if (match) {
    const payload = match[1];
    const amountFirst = /^(\S+)\s+(.+)$/.exec(payload);
    if (amountFirst && COMBAT_STATS.has(amountFirst[2].toLowerCase())) {
      return {
        kind: "power", amount: amountFirst[1], subject: amountFirst[2], text: signedGainText(amountFirst[1], amountFirst[2]), sentence: value,
        operationTarget: "sourceMonster", amountPolarity: operationAmountPolarity(amountFirst[1]),
      };
    }
    const amountLast = /^(.+?)\s+(\S+)$/.exec(payload);
    if (amountLast && /^\d+(?:[–\-/]\d+)*$/.test(amountLast[2])) {
      return {
        kind: "power", amount: amountLast[2], subject: amountLast[1], text: payload, sentence: value,
        operationTarget: "sourceMonster", amountPolarity: operationAmountPolarity(amountLast[2]),
      };
    }
    if (amountFirst && /^\d+(?:[–×\-/]\d+)*$/.test(amountFirst[1])) {
      const kind = /\bBlock\b/i.test(amountFirst[2]) ? "block" : "power";
      return {
        kind, amount: amountFirst[1], subject: amountFirst[2], text: payload, sentence: value,
        operationTarget: "sourceMonster", amountPolarity: operationAmountPolarity(amountFirst[1]),
      };
    }
    return {
      kind: "power", amount: null, subject: payload, text: `gain ${payload}`, sentence: value,
      operationTarget: "sourceMonster", amountPolarity: null,
    };
  }
  match = /^Applies?\s+(.+)$/i.exec(value);
  if (match) {
    const amountFirst = /^(\S+)\s+(.+)$/.exec(match[1]);
    return {
      kind: "power", amount: amountFirst?.[1] ?? null, subject: amountFirst?.[2] ?? match[1], text: match[1], sentence: value,
      operationTarget: "registeredTargets", amountPolarity: operationAmountPolarity(amountFirst?.[1]),
    };
  }
  if (/^Stunned$/i.test(value)) return { kind: "state", amount: null, subject: "Stunned", text: "STUNNED", sentence: value };
  if (/^Does nothing$/i.test(value)) return { kind: "action", amount: null, subject: "action", text: "takes no action", sentence: value };
  if (/^When\b/i.test(value)) return { kind: "condition", amount: null, subject: "condition", text: value, sentence: value };
  return { kind: "effect", amount: null, subject: "effect", text: value, sentence: value };
}
function mechanicAtoms(value) { return sentenceParts(value).map(mechanicAtom); }
function exactMonsterId(canonicalModel) {
  return typeof canonicalModel === "string" && canonicalModel.startsWith("MONSTER.") ? canonicalModel.slice(8) : null;
}
function formatPracticalRange(values) {
  if (!Array.isArray(values) || !values.length) return null;
  return values.length === 1 || values[0] === values.at(-1) ? String(values[0]) : `${values[0]}–${values.at(-1)}`;
}
function exactSourceBody(encounter, referenceBody) {
  const matches = (encounter.monsters ?? []).filter((body) => exactMonsterId(body.canonicalModel) === referenceBody.monsterId);
  return matches.length === 1 ? matches[0] : null;
}
function exactSourceMove(sourceBody, referenceMove) {
  const matches = (sourceBody?.moves ?? []).filter((move) => move.title?.text === referenceMove.name);
  return matches.length === 1 ? matches[0] : null;
}
function sharedAmountPolarity(values) {
  const polarities = values.map(operationAmountPolarity);
  return polarities[0] && polarities.every((value) => value === polarities[0]) ? polarities[0] : null;
}
function operationAmountPolarity(value) {
  if (typeof value === "string") {
    const components = value.split(/(?<=\d)[–×\/-](?=[+-]?\d)/);
    if (components.length > 1 && components.every((component) => /^[+-]?\d+(?:\.\d+)?$/.test(component))) {
      return sharedAmountPolarity(components);
    }
  }
  if (typeof value === "number" || (typeof value === "string" && /^[+-]?\d+(?:\.\d+)?$/.test(value))) {
    const number = Number(value);
    return number < 0 ? "negative" : number > 0 ? "positive" : "zero";
  }
  if (!value || typeof value !== "object") return null;
  switch (value.kind) {
    case "constant": return operationAmountPolarity(value.value);
    case "convert":
    case "delegate": return operationAmountPolarity(value.expression);
    case "range": return sharedAmountPolarity([value.minimum, value.maximum]);
    case "ascensionSelect": return sharedAmountPolarity([value.atOrAbove, value.below]);
    case "conditional": return sharedAmountPolarity([value.whenTrue, value.whenFalse]);
    default: return null;
  }
}
function operationForAtom(atom, operations, used) {
  const expectedKind = atom.kind === "attack" ? "attack" : atom.kind === "block" ? "gainBlock" : atom.kind === "power" ? "applyPower" : null;
  if (!expectedKind) return null;
  for (let index = 0; index < operations.length; index += 1) {
    const operation = operations[index];
    if (used.has(index) || operation?.kind !== expectedKind) continue;
    if (atom.operationTarget && operation.target !== atom.operationTarget) continue;
    if (expectedKind === "applyPower" && cardOrPower(operation.model).toLowerCase() !== atom.subject.toLowerCase()) continue;
    if (atom.amountPolarity && operationAmountPolarity(operation.value) !== atom.amountPolarity) continue;
    used.add(index); return operation;
  }
  return null;
}
function sourceMergedAtom(rawAtom, scaledAtom, operation, scaling) {
  const amount = practicalAmountText(operation?.value);
  if (amount === null || rawAtom.amount === null) return null;
  const sourceSentence = rawAtom.sentence.replace(rawAtom.amount, amount);
  const scaledSentence = scaleMechanicsText(`${sourceSentence}.`, scaling ?? {}).replace(/\.$/, "");
  const replacement = mechanicAtom(scaledSentence);
  return replacement.kind === scaledAtom.kind ? { ...replacement, authority: "checked-source" } : null;
}
function bestMove(referenceMove, sourceBody, scaling, bodyIndex, provenanceValues) {
  const sourceMove = exactSourceMove(sourceBody, referenceMove);
  const rawAtoms = mechanicAtoms(referenceMove.sourceA9);
  const scaledAtoms = mechanicAtoms(referenceMove.text);
  const used = new Set();
  const atoms = scaledAtoms.map((scaledAtom, index) => {
    const rawAtom = rawAtoms[index] ?? scaledAtom;
    const operation = sourceMove ? operationForAtom(rawAtom, sourceMove.operations ?? [], used) : null;
    const closed = operation ? sourceMergedAtom(rawAtom, scaledAtom, operation, scaling) : null;
    const authority = closed ? "checked-source" : "wiki-reference";
    provenanceValues.push({
      path: `body ${bodyIndex + 1} · ${referenceMove.name} · effect ${index + 1}`,
      authority,
      presentedValue: closed?.text ?? scaledAtom.text,
      retainedReferenceValue: scaledAtom.text,
      conflict: closed ? closed.text !== scaledAtom.text : false,
      reason: closed ? "projected checked value is closed"
        : operation ? "matched projected source value remains symbolic; retained exact reference value"
          : sourceMove ? "no exact projected source operation coordinate; retained exact reference value"
            : "no exact localized source move join; retained exact reference value",
    });
    return closed ?? { ...scaledAtom, authority };
  });
  return { name: referenceMove.name, atoms, sourceMatchedExactly: sourceMove !== null };
}
function moveRow(move, cue = null, atoms = move.atoms) {
  return {
    cue,
    detail: atoms.map((atom) => atom.text).filter(Boolean).join(" · "),
    authorities: [...new Set(atoms.map((atom) => atom.authority))],
  };
}
function numberedRows(moves, transform = (move) => move.atoms) {
  return moves.map((move, index) => moveRow(move, String(index + 1), transform(move, index)));
}
function escapedPattern(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
function exactPhraseSpans(value, phrases) {
  const spans = [];
  for (const phrase of phrases.filter(Boolean)) {
    const expression = new RegExp(`(^|[^A-Za-z0-9])(${escapedPattern(phrase)})(?=[^A-Za-z0-9]|$)`, "g");
    for (const match of value.matchAll(expression)) {
      const start = match.index + match[1].length;
      spans.push([start, start + match[2].length]);
    }
  }
  return spans;
}
function isConsequencePatternCitation(value, start, end, protectedSpans) {
  if (protectedSpans.some(([left, right]) => start >= left && end <= right)) return false;
  const before = value.slice(0, start);
  const after = value.slice(end);

  // These nouns expose a value the player tracks. A label collision in this
  // grammatical role is a concept, not a citation of the same-named action.
  if (/^(?:'s)?\s+(?:timer|countdown|counter|count|threshold|amount|stacks?)\b/i.test(after)) return false;
  if (/^\s+(?:wears? off|expires?|remains?|is (?:active|inactive))\b/i.test(after)) return false;

  // Bullets, arrows, and positional dashes are explicit move-sequence syntax
  // in retained patterns. A probability prefix may sit between a bullet and name.
  if (/(?:•|→|—)\s*$/.test(before) || /^\s*→/.test(after)) return true;

  const boundary = Math.max(before.lastIndexOf("."), before.lastIndexOf("!"), before.lastIndexOf("?"), before.lastIndexOf("•"), before.lastIndexOf("→"));
  const clause = before.slice(boundary + 1);
  const actionCue = /(?:\b(?:use[sd]?|using|used|opens?|openers?|starts?|resumes?|repeat(?:s|ed)?|pick(?:s|ed)?|select(?:s|ed)?|choose[sd]?|switch(?:es|ed)?|activate[sd]?|enter(?:s|ed)?|follow(?:s|ed)?\s+up|alternates?|alternate|cycles?)\b|\b(?:after|before|between|with|then|via|at|to|from)\s+|\bchance\s+of\s+|\b(?:cycle|sequence|moves?|pattern|order|chance)\s*:)[^.!?•→]*$/i;
  if (actionCue.test(clause)) return true;

  // Some patterns put the move citation in subject position and describe its
  // consequence or usage immediately afterward.
  return /^(?:'s\s+(?:damage|Block|effect|hits?)\b|\s+(?:opener\s+slot|appl(?:y|ies)|deals?|gains?|summons?|does|wakes?|starts?\s+at|has\s+been\s+used|cannot\s+be\s+used|can\s+only\s+be\s+used|every\s+turn|it\s+repeats?)\b)/i.test(after);
}
function consequencePattern(value, moves, protectedPhrases = []) {
  const source = String(value ?? "");
  const numbered = new Map(moves.map((move, index) => [move.name, index + 1]));
  const names = [...numbered.keys()].filter(Boolean).sort((left, right) => right.length - left.length);
  if (!names.length) return source;
  const protectedSpans = exactPhraseSpans(source, protectedPhrases);
  const expression = new RegExp(`(^|[^A-Za-z0-9])(${names.map(escapedPattern).join("|")})(?=[^A-Za-z0-9]|$)`, "g");
  return source.replace(expression, (matched, prefix, name, offset) => {
    const start = offset + prefix.length;
    return isConsequencePatternCitation(source, start, start + name.length, protectedSpans)
      ? `${prefix}step ${numbered.get(name)}` : matched;
  });
}
function exactMoveMap(moves) {
  const map = new Map();
  for (const move of moves) {
    if (map.has(move.name)) return null;
    map.set(move.name, move);
  }
  return map;
}
function ceremonialSections(referenceBody, moves, scaling = {}) {
  if (referenceBody.monsterId !== "CEREMONIAL_BEAST") return null;
  const byName = exactMoveMap(moves);
  if (!byName || !["Stamp", "Plow", "Stun", "Beast Cry", "Stomp", "Crush"].every((name) => byName.has(name))) return null;
  const stampRecord = referenceBody.moves.find((move) => move.name === "Stamp");
  const stamp = byName.get("Stamp");
  const scaledThreshold = stamp.atoms.find((atom) => atom.subject?.toLowerCase() === "plow" && atom.amount !== null);
  const rawThreshold = mechanicAtoms(stampRecord?.sourceA9).find((atom) => atom.subject?.toLowerCase() === "plow" && atom.amount !== null);
  const threshold = Number(scaling.players ?? 2) === 1 ? rawThreshold?.amount : scaledThreshold?.amount;
  if (!threshold) return null;
  const stun = byName.get("Stun");
  const stunState = stun.atoms.find((atom) => atom.kind === "state")?.text ?? "Stunned";
  const noAction = stun.atoms.find((atom) => atom.kind === "action")?.text ?? "takes no action";
  const phaseOne = {
    number: "01", title: "Force the stun",
    rows: [
      { cue: "First turn", detail: "No attack", authorities: [...new Set(stamp.atoms.map((atom) => atom.authority))] },
      moveRow(byName.get("Plow"), "Then each turn"),
    ],
    marker: {
      label: `At ${threshold} HP or below`,
      detail: `Immediately ${stunState.replace(/^STUNNED$/i, "Stunned")} · loses all Strength · ${noAction}`,
    },
    transitionAfter: true, repeat: null,
  };
  const phaseTwoMoves = [byName.get("Beast Cry"), byName.get("Stomp"), byName.get("Crush")];
  const phaseTwo = {
    number: "02", title: "Three-turn loop",
    rows: numberedRows(phaseTwoMoves, (move, index) => index === 0
      ? move.atoms.map((atom) => ({ ...atom, text: `Apply ${atom.text}` }))
      : move.atoms),
    marker: null, transitionAfter: false,
    repeat: "↻ repeat 1 → 2 → 3",
  };
  return [phaseOne, phaseTwo];
}
function exactGraphContract(sourceBody, expected) {
  const graph = sourceBody?.graph;
  if (!graph || graph.graphId !== expected.graphId) return false;
  const nodeStates = new Map((graph.nodes ?? []).map((node) => [node.nodeId, node.stateId]));
  if (nodeStates.size !== expected.states.length
      || expected.states.some((stateId) => ![...nodeStates.values()].includes(stateId))) return false;
  const initialIds = Array.isArray(graph.initial) ? graph.initial : graph.initial == null ? [] : [graph.initial];
  const initial = initialIds.map((nodeId) => nodeStates.get(nodeId)).sort();
  if (initial.includes(undefined) || initial.join("\0") !== [...expected.initial].sort().join("\0")) return false;
  const edges = (graph.edges ?? []).map((edge) => (
    edge.kind === "followUp" && nodeStates.has(edge.from) && nodeStates.has(edge.to)
      ? `${nodeStates.get(edge.from)}>${nodeStates.get(edge.to)}` : null
  )).sort();
  return !edges.includes(null) && edges.join("\0") === [...expected.edges].sort().join("\0");
}
function stateIncrement(expression, stateName) {
  const increments = [], domains = [];
  const visit = (node) => {
    if (!node || typeof node !== "object") return;
    if (node.kind === "stateVariable" && node.name === stateName) domains.push(node.domain);
    if (node.kind === "arithmetic" && node.operator === "multiply" && node.operands?.length === 2) {
      const state = node.operands.find((operand) => operand?.kind === "stateVariable" && operand.name === stateName);
      const constant = node.operands.find((operand) => operand?.kind === "constant" && Number.isSafeInteger(Number(operand.value)));
      if (state && constant) increments.push(Number(constant.value));
    }
    for (const value of Array.isArray(node) ? node : Object.values(node)) visit(value);
  };
  visit(expression);
  const unique = [...new Set(increments)];
  const maximums = [...new Set(domains.map((domain) => Number(domain?.maximum)).filter(Number.isSafeInteger))];
  return unique.length === 1 && unique[0] > 0 && maximums.length === 1
    ? { amount: unique[0], maximum: maximums[0] } : null;
}
function exactReplacementValues(move, sourceBody) {
  const match = /^(\d+) Block and (\d+)\/(\d+) Strength$/.exec(move?.atoms?.map((atom) => atom.text).join(" · ") ?? "");
  const hp = stateIncrement(sourceBody?.hp?.expression, "axebotRespawnCount");
  if (!match || !hp || hp.maximum !== 2) return null;
  const values = {
    block: Number(match[1]), strengths: [Number(match[2]), Number(match[3])],
    maxHp: [hp.amount, hp.amount * 2],
  };
  return Object.values(values).flat().every((value) => Number.isSafeInteger(value) && value > 0) ? values : null;
}
function axebotSections(referenceBody, sourceBody, moves) {
  if (referenceBody.monsterId !== "AXEBOT") return undefined;
  const byName = exactMoveMap(moves);
  const graphClosed = exactGraphContract(sourceBody, {
    graphId: "GRAPH.AXEBOT",
    states: ["BOOT_UP_MOVE", "HAMMER_UPPERCUT_MOVE", "ONE_TWO_MOVE"],
    initial: ["BOOT_UP_MOVE", "HAMMER_UPPERCUT_MOVE"],
    edges: ["BOOT_UP_MOVE>HAMMER_UPPERCUT_MOVE", "HAMMER_UPPERCUT_MOVE>ONE_TWO_MOVE", "ONE_TWO_MOVE>HAMMER_UPPERCUT_MOVE"],
  });
  if (!byName || !graphClosed || !["Boot Up", "The One-Two", "Hammer Uppercut"].every((name) => byName.has(name))) return [];
  const replacement = exactReplacementValues(byName.get("Boot Up"), sourceBody);
  if (!replacement) return [];
  const replacementAuthorities = [...new Set([
    ...byName.get("Boot Up").atoms.map((atom) => atom.authority), "checked-source",
  ])];
  return [
    {
      number: null, title: "Initial Axebot opener", rows: [moveRow(byName.get("Hammer Uppercut"), "Turn 1")],
      marker: null, transitionAfter: true, repeat: null,
    },
    {
      number: null, title: "Ordinary repeating cycle",
      rows: [moveRow(byName.get("The One-Two"), "1"), moveRow(byName.get("Hammer Uppercut"), "2")],
      marker: null, transitionAfter: false, repeat: "↻ repeat 1 → 2",
    },
    {
      number: null, title: "Stock replacement opener", note: "Only when Stock replaces a defeated Axebot.",
      rows: [
        {
          cue: "First replacement",
          detail: `${replacement.block} Block · +${replacement.strengths[0]} Strength · +${replacement.maxHp[0]} Max HP cumulative`,
          authorities: replacementAuthorities,
        },
        {
          cue: "Second replacement",
          detail: `${replacement.block} Block · +${replacement.strengths[1]} Strength · +${replacement.maxHp[1]} Max HP cumulative`,
          authorities: replacementAuthorities,
        },
        { cue: "Then", detail: "enter the ordinary cycle at step 2", authorities: ["checked-source"] },
      ],
      marker: null, transitionAfter: false, repeat: null,
    },
  ];
}
function trackedPowerValue(value, power) {
  const match = new RegExp(`^${escapedPattern(power)} (\\d+)$`).exec(String(value ?? ""));
  return match && Number.isSafeInteger(Number(match[1])) ? Number(match[1]) : null;
}
function terrorEelSections(referenceBody, sourceBody, moves, thresholdValue) {
  if (referenceBody.monsterId !== "TERROR_EEL") return undefined;
  const byName = exactMoveMap(moves);
  const graphClosed = exactGraphContract(sourceBody, {
    graphId: "GRAPH.TERROR_EEL",
    states: ["CRASH_MOVE", "THRASH_MOVE", "STUN_MOVE", "TERROR_MOVE"],
    initial: ["CRASH_MOVE"],
    edges: ["CRASH_MOVE>THRASH_MOVE", "THRASH_MOVE>CRASH_MOVE", "STUN_MOVE>TERROR_MOVE", "TERROR_MOVE>CRASH_MOVE"],
  });
  if (!byName || !graphClosed || !["Crash", "Thrash", "Stun", "Terror"].every((name) => byName.has(name))) return [];
  const threshold = trackedPowerValue(thresholdValue, "Shriek");
  const stun = byName.get("Stun");
  const stunned = stun.atoms.find((atom) => atom.kind === "state")?.text;
  const noAction = stun.atoms.find((atom) => atom.kind === "action")?.text;
  const vulnerable = byName.get("Terror").atoms.find((atom) => atom.subject?.toLowerCase() === "vulnerable")?.text;
  if (!threshold || !stunned || !noAction || !vulnerable) return [];
  return [{
    number: null, title: "Two-step cycle",
    rows: [moveRow(byName.get("Crash"), "1"), moveRow(byName.get("Thrash"), "2")],
    marker: {
      label: `At Terror Eel's Shriek threshold · ${threshold} HP`,
      detail: `Immediately ${stunned.replace(/^STUNNED$/i, "Stunned")} · ${noAction} → Apply ${vulnerable} → resume at step 1`,
    },
    transitionAfter: false, repeat: "↻ repeat 1 → 2",
  }];
}
function focusedSections(referenceBody, sourceBody, moves, thresholdValue) {
  return axebotSections(referenceBody, sourceBody, moves)
    ?? terrorEelSections(referenceBody, sourceBody, moves, thresholdValue);
}
function namesInExactText(moves, value) {
  const source = String(value ?? "");
  return moves.filter((move) => source.includes(move.name));
}
function genericSections(referenceBody, moves) {
  const pattern = referenceBody.pattern?.text ?? "";
  const phaseChunks = [...pattern.matchAll(/Phase\s+(\d+):([\s\S]*?)(?=Phase\s+\d+:|$)/g)];
  if (phaseChunks.length) {
    const used = new Set();
    const sections = phaseChunks.map((match, index) => {
      const selected = namesInExactText(moves, match[2]).filter((move) => !used.has(move.name));
      selected.forEach((move) => used.add(move.name));
      return {
        number: String(index + 1).padStart(2, "0"), title: `Phase ${match[1]}`,
        rows: numberedRows(selected), marker: null,
        transitionAfter: index < phaseChunks.length - 1,
        repeat: /repeat|cycle/i.test(match[2]) ? "↻ repeat" : null,
      };
    });
    const remaining = moves.filter((move) => !used.has(move.name));
    if (remaining.length) sections.at(-1).rows.push(...numberedRows(remaining));
    return sections;
  }
  const openerMatch = /Opener\s*\(turn 1\):\s*([^.]+)\./i.exec(pattern);
  if (openerMatch) {
    const openers = namesInExactText(moves, openerMatch[1]);
    const sections = [];
    if (openers.length) sections.push({ number: null, title: "Opener", rows: openers.map((move) => moveRow(move, "Turn 1")), marker: null, transitionAfter: true, repeat: null });
    sections.push({ number: null, title: "Cycle", rows: numberedRows(moves), marker: null, transitionAfter: false, repeat: /repeat|cycle/i.test(pattern) ? "↻ repeat" : null });
    return sections;
  }
  const title = referenceBody.pattern?.type === "random-with-constraint" || /\b(?:if|random|either)\b/i.test(pattern) ? "Branch"
    : /\brespond|after being|when\b/i.test(pattern) ? "Response" : "Cycle";
  return [{
    number: null, title, rows: numberedRows(moves), marker: null, transitionAfter: false,
    repeat: /repeat|cycle|every turn/i.test(pattern) ? "↻ repeat" : null,
    note: pattern ? consequencePattern(pattern, moves, [referenceBody.displayName]) : null,
  }];
}
function referencePhaseNumber(referenceBody) {
  const match = /^phase\s+(\d+)$/i.exec(referenceBody.role ?? "");
  return match ? Number(match[1]) : null;
}
function roleNumberedSections(referenceBody, sections, maximumPhase) {
  const phase = referencePhaseNumber(referenceBody);
  if (phase === null || !sections.length) return sections;
  return sections.map((section, index) => ({
    ...section,
    number: index === 0 ? String(phase).padStart(2, "0") : section.number,
    title: index === 0 ? `Phase ${phase} · ${section.title}` : section.title,
    transitionAfter: index === sections.length - 1 && phase < maximumPhase ? true : section.transitionAfter,
  }));
}
function practicalHp(sourceBody, referenceBody, scaling, bodyIndex, provenanceValues) {
  const range = sourceBody?.hp?.a8SinglePlayer;
  if (Number.isSafeInteger(range?.minimum) && Number.isSafeInteger(range?.maximum)) {
    const base = range.minimum === range.maximum ? [range.minimum] : [range.minimum, range.maximum];
    const rendered = scaleRange(base, scaling ?? {});
    provenanceValues.push({ path: `body ${bodyIndex + 1} · HP`, authority: "checked-source", reason: "projected A8 HP is closed; configured multiplayer scaling applied" });
    return formatPracticalRange(rendered);
  }
  provenanceValues.push({ path: `body ${bodyIndex + 1} · HP`, authority: "wiki-reference", reason: "projected checked HP remains symbolic; retained exact configured reference value" });
  return formatPracticalRange(referenceBody.hp);
}
function isPracticalInitial(encounter, sourceBody, referenceBody) {
  const phase = referencePhaseNumber(referenceBody);
  if (phase !== null) return phase === 1;
  if (sourceBody) return encounter.roster?.possibleInitialBodies?.includes(sourceBody.canonicalModel) === true;
  return referenceBody.role !== "summoned";
}
function practicalRole(encounter, sourceBody, referenceBody, moves = []) {
  const initial = isPracticalInitial(encounter, sourceBody, referenceBody);
  if (referenceBody.role) return consequencePattern(referenceBody.role, moves, [referenceBody.displayName]);
  return initial ? "initial body" : "encounter body";
}
function consequenceNote(value, moves) {
  const citations = moves.map((move) => {
    const consequence = move.atoms.map((atom) => atom.text).filter(Boolean).join(" · ")
      .replace(new RegExp(`^${escapedPattern(move.name)}(?:\\s*·\\s*|$)`, "i"), "");
    const bare = consequence ? `“${consequence}” step` : "listed step";
    return {
      name: move.name,
      bare,
      definite: `the ${bare}`,
      standalone: consequence || "Listed step",
    };
  }).sort((left, right) => right.name.length - left.name.length);
  let rendered = String(value ?? "");
  if (!citations.length) return rendered;

  // A capitalized move title is rewritten only where the sentence identifies it
  // as an action. The same token can also be an ordinary verb, status, or tracked
  // noun (for example, "bombs that explode" and "Hatch timer"). Replacing those
  // lexical uses globally loses meaning and often breaks the surrounding grammar.
  const replaceExactName = (source, citation, replacement) => source.replace(
    new RegExp(`(^|[^A-Za-z0-9])(${escapedPattern(citation.name)})(?=[^A-Za-z0-9]|$)`, "gi"),
    (matched, prefix, name) => name === citation.name ? `${prefix}${replacement}` : matched,
  );

  // Lists explicitly introduced as moves are citations even though later items
  // are separated only by commas or conjunctions.
  rendered = rendered.replace(/\bmoves?\s+—\s*[^.—]*(?=\s+—|[.;]|$)/gi, (list) => {
    let rewritten = list;
    for (const citation of citations) rewritten = replaceExactName(rewritten, citation, citation.bare);
    return rewritten;
  });

  for (const citation of citations) {
    const name = escapedPattern(citation.name);
    const exactName = `(${name})(?=[^A-Za-z0-9]|$)`;

    // Preserve the noun owned by a move citation: "Fade's Intangible" becomes
    // "Intangible from the … step", rather than an ungrammatical step possessive.
    rendered = rendered.replace(
      new RegExp(`(^|[^A-Za-z0-9])((?:the)\\s+first\\s+iteration\\s+of\\s+)${exactName}'s\\s+([A-Za-z][A-Za-z-]*)`, "gi"),
      (matched, prefix, lead, found, noun) => found === citation.name
        ? `${prefix}${lead[0] === "T" ? "The" : "the"} first ${noun} from ${citation.definite}` : matched,
    );
    rendered = rendered.replace(
      new RegExp(`(^|[^A-Za-z0-9])${exactName}'s\\s+([A-Za-z][A-Za-z-]*)`, "gi"),
      (matched, prefix, found, noun) => found === citation.name
        ? `${prefix}${noun} from ${citation.definite}` : matched,
    );

    // The source phrase already supplies its article, so use a bare descriptor.
    rendered = rendered.replace(
      new RegExp(`(^|[^A-Za-z0-9])((?:the\\s+)?usual\\s+)${exactName}`, "gi"),
      (matched, prefix, lead, found) => found === citation.name
        ? `${prefix}${lead}${citation.bare}` : matched,
    );

    // These grammatical cues identify an actual move citation. Supply an article
    // with a consequence label, but never splice it into an arbitrary token match.
    rendered = rendered.replace(
      new RegExp(`(^|[^A-Za-z0-9])((?:use[sd]?|using|activate[sd]?|activating|with|via|after|to|then|(?:version|iteration)\\s+of)\\s+)${exactName}`, "gi"),
      (matched, prefix, lead, found) => found === citation.name
        ? `${prefix}${lead}${citation.definite}` : matched,
    );

    // A title followed by a parenthetical at the start of a rule is a label, not
    // sentence prose. Render its consequence directly instead of retaining a slot.
    rendered = rendered.replace(
      new RegExp(`^(${name})(?=\\s*\\()`, "i"),
      (matched, found) => found === citation.name ? citation.standalone : matched,
    );
  }
  return rendered.replace(/\s+([.,;:])/g, "$1");
}
function uniqueReferenceNotes(reference, moves) {
  const seen = new Set(), notes = [];
  for (const line of [...(reference.rules ?? []), ...(reference.timing ?? [])]) {
    const normalized = consequenceNote(String(line).trim(), moves);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized); notes.push(normalized);
  }
  return notes;
}
function primaryReferenceMove(referenceBody, referenceMove, scaling) {
  // Axebot's replacement-only values are one typed A9 reference. They are not an
  // invitation to scale arbitrary numerals in retained prose.
  if (referenceBody.monsterId === "AXEBOT" && referenceMove.name === "Boot Up") {
    return { ...referenceMove, text: referenceMove.sourceA9 };
  }
  // Plow is an HP threshold rather than a displayed stack amount. In the active
  // fixture its one-player value remains the raw A9 threshold; multiplayer uses
  // the checked opt-in scaling already applied to referenceMove.text.
  if (referenceBody.monsterId === "CEREMONIAL_BEAST" && referenceMove.name === "Stamp"
      && Number(scaling?.players ?? 2) === 1) {
    return { ...referenceMove, text: referenceMove.sourceA9 };
  }
  return referenceMove;
}
const EVENT_PRIMARY_IDS = new Set([
  "BATTLEWORN_DUMMY_EVENT_V1_ENCOUNTER",
  "BATTLEWORN_DUMMY_EVENT_V2_ENCOUNTER",
  "BATTLEWORN_DUMMY_EVENT_V3_ENCOUNTER",
  "DENSE_VEGETATION_EVENT_ENCOUNTER",
  "FAKE_MERCHANT_EVENT_ENCOUNTER",
  "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER",
  "PUNCH_OFF_EVENT_ENCOUNTER",
  "THE_ARCHITECT_EVENT_ENCOUNTER",
]);
const ACT_HP_FACTOR = Object.freeze({
  "ACT.OVERGROWTH": "act1", "ACT.UNDERDOCKS": "act1", "ACT.HIVE": "act2", "ACT.GLORY": "act3NonBoss",
});
function exactConstant(expression) {
  if (expression?.kind === "constant") return expression.value;
  if (expression?.kind === "convert" && expression.mode === "exact") return exactConstant(expression.expression);
  return null;
}
function sourceRow(detail, cue = null) {
  return { cue, detail, authorities: ["checked-source"] };
}
function sourceSection(title, rows, options = {}) {
  return {
    number: null, title, rows, marker: null, transitionAfter: options.transitionAfter ?? false,
    repeat: options.repeat ?? null, note: options.note ?? null,
  };
}
function sourceMoveMap(body) {
  return new Map((body?.moves ?? []).map((move) => [move.stateId, move]));
}
function typedExpressionValue(expression, state) {
  if (!expression || typeof expression !== "object") return null;
  if (expression.kind === "constant") return Number(expression.value);
  if (expression.kind === "stateVariable") {
    if (!Object.hasOwn(state, expression.name)) return null;
    if (expression.valueType === "boolean") return typeof state[expression.name] === "boolean" ? state[expression.name] : null;
    const value = Number(state[expression.name]);
    return Number.isFinite(value) ? value : null;
  }
  if (expression.kind === "convert") return typedExpressionValue(expression.expression, state);
  if (expression.kind === "actRoomFactor") {
    const key = state.actIndex === 0 ? "act1" : state.actIndex === 1 ? "act2"
      : state.actIndex === 2 ? state.bossRoom ? "act3Boss" : "act3NonBoss" : null;
    return key ? Number(expression.factors?.[key]) : null;
  }
  if (expression.kind === "compare") {
    const left = typedExpressionValue(expression.left, state), right = typedExpressionValue(expression.right, state);
    if (left === null || right === null) return null;
    return ({ lessOrEqual: left <= right, lessThan: left < right, equal: left === right,
      greaterThan: left > right, greaterThanOrEqual: left >= right, notEqual: left !== right })[expression.operator] ?? null;
  }
  if (expression.kind === "conditional") {
    const condition = typedExpressionValue(expression.condition, state);
    return condition === null ? null : typedExpressionValue(condition ? expression.whenTrue : expression.whenFalse, state);
  }
  if (expression.kind === "arithmetic" && Array.isArray(expression.operands) && expression.operands.length) {
    const values = expression.operands.map((operand) => typedExpressionValue(operand, state));
    if (values.some((value) => value === null || !Number.isFinite(value))) return null;
    if (expression.operator === "add") return values.reduce((left, right) => left + right);
    if (expression.operator === "subtract") return values.slice(1).reduce((left, right) => left - right, values[0]);
    if (expression.operator === "multiply") return values.reduce((left, right) => left * right, 1);
    if (expression.operator === "divide" && values.slice(1).every((value) => value !== 0)) return values.slice(1).reduce((left, right) => left / right, values[0]);
  }
  return null;
}
function sourceActIndexes(encounter) {
  const indexes = { "ACT.OVERGROWTH": 0, "ACT.UNDERDOCKS": 0, "ACT.HIVE": 1, "ACT.GLORY": 2 };
  const memberships = encounter.placement?.memberships ?? [];
  const values = memberships.length ? memberships.map((row) => indexes[row.actId]) : [0, 1, 2];
  return values.every(Number.isSafeInteger) ? [...new Set(values)] : [];
}
function displayNumbers(values) {
  const normalized = [...new Set(values.map((value) => Number(value.toFixed(8))))].sort((left, right) => left - right);
  return formatPracticalRange(normalized);
}
function fixtureExpressionMatches(expression, fixtures, resultKey) {
  return Array.isArray(fixtures) && fixtures.every((fixture) => {
    const expected = Number(fixture[resultKey]);
    const actual = typedExpressionValue(expression, fixture.inputs ?? {});
    return Number.isFinite(expected) && actual !== null && Math.abs(actual - expected) < 1e-8;
  });
}
function powerScalingContractClosed(encounter) {
  const scaling = encounter?.sourceScaling?.power, rule = scaling?.rule;
  if (scaling?.factId !== "SOURCE.SCALING.POWER" || rule?.inheritedDefault?.activeByDefault !== false
      || rule.summary?.optIns !== 12 || rule.summary.activeOverrides !== 4 || rule.summary.formulaOverrides !== 5) return false;
  const optIns = rule.optIns ?? [], optInIds = new Set(optIns.filter((row) => row.shouldScale === true).map((row) => row.canonicalPower));
  if (optIns.length !== 12 || optInIds.size !== 12
      || !optInIds.has("POWER.ARTIFACT_POWER") || !optInIds.has("POWER.PLATING_POWER")
      || ["POWER.STRENGTH_POWER", "POWER.FRAIL_POWER", "POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER"].some((id) => optInIds.has(id))) return false;
  const signatures = new Map([
    ["POWER.ARTIFACT_POWER", ["2", "3", "4"]],
    ["POWER.PLATING_POWER", ["2", "6", "10"]],
  ]);
  for (const [model, expected] of signatures) {
    const override = rule.overrides?.find((row) => row.canonicalPower === model);
    if (!override || override.active !== true || override.override !== true
        || override.fixtures?.map((row) => row.result).join("\0") !== expected.join("\0")
        || !fixtureExpressionMatches(override.expression, override.fixtures, "result")) return false;
  }
  return true;
}
function eventScalingContractsClosed(encounter) {
  const attack = encounter?.sourceScaling?.ordinaryMonsterAttack;
  const block = encounter?.sourceScaling?.block;
  return attack?.factId === "SOURCE.SCALING.ORDINARYMONSTERATTACK"
    && attack.rule?.scalesInMultiplayer === false
    && block?.factId === "SOURCE.SCALING.BLOCK"
    && block.rule?.ruleId === "monsterBlockMultiplayerScaling.v0.111.0"
    && block.rule.rounding === "none"
    && block.rule.fixtures?.map((row) => row.multiplier).join("\0") === ["1", "2", "3.9", "1"].join("\0")
    && fixtureExpressionMatches(block.rule.expression, block.rule.fixtures, "multiplier")
    && powerScalingContractClosed(encounter);
}
function scaledSourceBlock(value, encounter, players) {
  const amount = practicalAmountText(value), number = Number(amount);
  const scaling = encounter?.sourceScaling?.block;
  if (amount === null || !Number.isFinite(number) || !eventScalingContractsClosed(encounter)) return null;
  const multipliers = sourceActIndexes(encounter).map((actIndex) => typedExpressionValue(scaling.rule.expression, {
    sourceIsPrimaryOrSecondaryEnemy: true, isPoweredCardOrMonsterMoveBlock: true,
    playerCount: players, actIndex, bossRoom: false,
  }));
  return multipliers.length && multipliers.every((result) => result !== null)
    ? displayNumbers(multipliers.map((multiplier) => number * multiplier)) : amount;
}
function scaledInitialPower(body, model, encounter, players) {
  const base = initialBase(body, model), amount = Number(base);
  if (base === null || !Number.isFinite(amount)) return base;
  const scaling = encounter?.sourceScaling?.power;
  if (!powerScalingContractClosed(encounter)) return null;
  const optedIn = scaling.rule.optIns.some((row) => row.shouldScale === true && row.canonicalPower === model);
  if (!optedIn) return base;
  const override = scaling.rule.overrides?.find((row) => row.active === true && row.canonicalPower === model);
  if (!override) return null;
  const result = typedExpressionValue(override.expression, { amount, playerCount: players });
  return result === null ? base : String(Number(result.toFixed(8)));
}
function sourceOperationDetail(move, context = {}) {
  const operations = move?.operations ?? [];
  const effects = [];
  for (let index = 0; index < operations.length; index += 1) {
    const operation = operations[index];
    if (operation.kind === "attack") {
      const hit = operations.slice(index + 1).find((candidate) => candidate.kind === "attackHitCount");
      const amount = practicalAmountText(operation.value);
      const hitCount = practicalAmountText(hit?.value);
      const damage = hit
        ? `${amount ?? "runtime-set"} damage × ${hitCount ?? "runtime-set hits"}`
        : amount ? `${amount} damage` : "damage amount set at runtime";
      effects.push(`${damage} to ${targetText(operation.target)}`);
    } else if (operation.kind === "attackHitCount") {
      continue;
    } else if (operation.kind === "gainBlock") {
      const amount = scaledSourceBlock(operation.value, context.encounter, context.players ?? 1);
      effects.push(`${amount ?? "runtime-set"} Block${operation.target === "sourceMonster" ? " to self" : ` to ${targetText(operation.target)}`}`);
    } else if (operation.kind === "applyPower") {
      const amount = practicalAmountText(operation.value);
      const power = words(operation.model);
      effects.push(operation.target === "sourceMonster"
        ? `${amount === null ? "runtime-set" : `+${amount}`} ${power} to self`
        : `Apply ${amount ?? "a runtime-set amount of"} ${power} to ${targetText(operation.target)}`);
    } else if (operation.kind === "addStatusCard") {
      const amount = practicalAmountText(operation.value);
      effects.push(`Add ${amount ?? "a runtime-set number of"} ${words(operation.model)} to ${targetText(operation.target)}`);
    } else if (operation.kind === "transition" && operation.transition === "noOp") {
      effects.push("takes no action");
    }
  }
  return effects.join(" · ");
}
function graphState(graph, nodeId) {
  return graph?.nodes?.find((node) => node.nodeId === nodeId)?.stateId ?? null;
}
function graphInitialStates(graph) {
  const initial = Array.isArray(graph?.initial) ? graph.initial : graph?.initial ? [graph.initial] : [];
  return initial.map((nodeId) => graphState(graph, nodeId));
}
function hasEventGraph(body, expected) {
  const graph = body?.graph;
  if (!graph || graph.graphId !== expected.graphId) return false;
  const states = new Set((graph.nodes ?? []).map((node) => node.stateId));
  if (states.size !== expected.states.length || expected.states.some((state) => !states.has(state))) return false;
  if (graphInitialStates(graph).sort().join("\0") !== [...expected.initial].sort().join("\0")) return false;
  const nodes = new Map((graph.nodes ?? []).map((node) => [node.nodeId, node.stateId]));
  const edges = new Set((graph.edges ?? []).map((edge) => `${nodes.get(edge.from)}>${nodes.get(edge.to)}:${edge.kind}`));
  return expected.edges.every((edge) => edges.has(edge));
}
function checkedEventHp(encounter, body, players) {
  const hp = body?.hp?.a8SinglePlayer;
  if (!hp || !Number.isSafeInteger(hp.minimum) || !Number.isSafeInteger(hp.maximum) || hp.minimum > hp.maximum) return null;
  if (players === 1) return [hp.minimum, hp.maximum];
  const scaling = encounter.hpContract?.multiplayerScaling;
  const factors = scaling?.rule?.expression?.whenFalse?.operands?.find((operand) => operand?.kind === "actRoomFactor")?.factors;
  const assignment = encounter.hpContract?.assignment?.conversion;
  if (scaling?.factId !== "SOURCE.SCALING.HP" || scaling.rule?.ruleId !== "hpMultiplayerScaling.v0.111.0"
      || assignment?.mode !== "truncateTowardZero" || !factors
      || scaling.rule.regressionWitnesses?.map((row) => row.result).join("\0") !== ["100", "220.0", "240.0", "240.0", "260.0"].join("\0")
      || !fixtureExpressionMatches(scaling.rule.expression, scaling.rule.regressionWitnesses, "result")) return null;
  const memberships = encounter.placement?.memberships ?? [];
  const factorKeys = memberships.length
    ? memberships.map((membership) => ACT_HP_FACTOR[membership.actId])
    : ["act1", "act2", "act3NonBoss"];
  if (factorKeys.some((key) => !key || !/^\d+\.\d+$/.test(factors[key]))) return null;
  const results = [];
  for (const key of new Set(factorKeys)) {
    const [whole, fraction] = factors[key].split(".");
    const denominator = 10 ** fraction.length;
    const numerator = Number(whole) * denominator + Number(fraction);
    for (const value of [hp.minimum, hp.maximum]) results.push(Math.trunc(value * players * numerator / denominator));
  }
  return [Math.min(...results), Math.max(...results)];
}
function eventPlacement(encounter) {
  const acts = (encounter.placement?.memberships ?? []).map((row) => words(row.actId));
  if (!acts.length) return "Source-proven non-pool event combat";
  return `${[...new Set(acts)].join(" / ")} event${new Set(acts).size === 1 ? "" : "s"}`;
}
function punchReduction(encounter, body, maximumHp) {
  const rows = (body.initialState ?? []).filter((fact) => fact.effect?.kind === "setState" && /::set_StartingHpReduction\b/.test(fact.effect.member ?? ""));
  const hpWrite = (body.initialState ?? []).find((fact) => fact.effect?.kind === "setCurrentHp");
  if (rows.length !== 2 || !hpWrite || !encounterRngContract(encounter, body)) return null;
  const bounds = rows.map((row) => row.baseValue?.expression).map((expression) => {
    if (expression?.kind !== "reference" || !/Random\.Rng::NextInt\b/.test(expression.reference ?? "")) return null;
    const values = expression.arguments?.map(exactConstant);
    return values?.length === 2 && values.every(Number.isSafeInteger) ? values : null;
  });
  if (bounds.some((value) => value === null) || bounds.some((value) => value[0] !== bounds[0][0] || value[1] !== bounds[0][1])) return null;
  const [minimum, maximumExclusive] = bounds[0];
  if (minimum < 0 || maximumExclusive <= minimum) return null;
  return {
    minimum, maximumExclusive,
    startingHp: [Math.max(1, maximumHp - (maximumExclusive - 1)), Math.max(1, maximumHp - minimum)],
  };
}
function encounterRngContract(encounter, body) {
  // The checked compact HP contract names NextInt's second bound as exclusive.
  return body?.hp?.assignmentContract === "source HP expression; runtime inputs and multiplayer scaling remain explicit"
    && encounter.hpContract?.baseSelection?.selection?.includes("NextInt(minInclusive,maxExclusive)");
}
function initialBase(body, model) {
  const rows = (body.initialState ?? []).filter((fact) => fact.effect?.kind === "applyPower" && fact.effect.model === model);
  return rows.length === 1 ? exactConstant(rows[0].baseValue?.expression) : null;
}
function eventBodyBase(encounter, body, players, count) {
  const values = checkedEventHp(encounter, body, players);
  if (!values) return null;
  const hp = formatPracticalRange(values);
  return {
    bodyIndex: 0, name: nameOf(body), initial: true, hp,
    role: count === 1 ? "initial event-combat body" : `${count === 2 ? "two" : count === 4 ? "four" : count} simultaneous initial bodies`,
    setup: null, sections: [], watch: [], sourceMatchedExactly: true,
  };
}
function battleFriendPrimary(encounter, body, primaryBody) {
  const match = /^BATTLEWORN_DUMMY_EVENT_V([123])_ENCOUNTER$/.exec(encounter.canonicalId);
  const expectedState = "NOTHING_MOVE";
  const graphClosed = match && hasEventGraph(body, {
    graphId: `GRAPH.BATTLE_FRIEND_V${match[1]}`, states: [expectedState], initial: [expectedState],
    edges: [`${expectedState}>${expectedState}:followUp`],
  });
  const timeLimit = initialBase(body, "POWER.BATTLEWORN_DUMMY_TIME_LIMIT_POWER");
  const lifecycle = encounter.lifecycle?.mechanics?.eventCombat?.battleTimeLimit;
  const timeout = lifecycle?.branches?.find((branch) => (branch.orderedEffects ?? []).some((effect) => effect.kind === "escape"));
  const effects = timeout?.orderedEffects ?? [];
  const lifecycleClosed = lifecycle?.trigger === "AfterSideTurnEnd" && lifecycle.participantPolicy === "only when participants contains exact Power owner"
    && effects.some((effect) => effect.kind === "writeState" && effect.field === "RanOutOfTime" && effect.value === true)
    && effects.some((effect) => effect.kind === "escape" && effect.target === "exactOwnerBody");
  if (!graphClosed || timeLimit !== 3 || !lifecycleClosed) return null;
  primaryBody.setup = `${nameOf(body)} · Starts with Time Limit 3 · three-step clock: 3 → 2 → 1 → timeout.`;
  primaryBody.sections = [
    sourceSection("Behavior", [sourceRow("takes no combat action", "Each participating side turn")], { repeat: "↻ while Time Limit remains" }),
    sourceSection("Time Limit", [
      sourceRow(`After a side turn including ${nameOf(body)} · Time Limit 3 → 2`, "Step 1"),
      sourceRow(`After the next included side turn · Time Limit 2 → 1`, "Step 2"),
      sourceRow(`After the third included side turn · record that the event fight ran out of time → ${nameOf(body)}: escape and leave the fight`, "Step 3 · expiry"),
    ]),
  ];
  return primaryBody;
}
function densePrimary(body, primaryBody) {
  const moves = sourceMoveMap(body);
  const graphClosed = hasEventGraph(body, {
    graphId: "GRAPH.WRIGGLER", states: ["INIT_MOVE", "NASTY_BITE_MOVE", "WRIGGLE_MOVE", "SPAWNED_MOVE"],
    initial: ["INIT_MOVE", "SPAWNED_MOVE"],
    edges: ["NASTY_BITE_MOVE>WRIGGLE_MOVE:followUp", "WRIGGLE_MOVE>NASTY_BITE_MOVE:followUp", "SPAWNED_MOVE>INIT_MOVE:followUp"],
  });
  const start = body.initialState?.find((fact) => /::set_StartStunned\b/.test(fact.effect?.member ?? ""));
  const branches = (body.graph?.edges ?? []).filter((edge) => edge.kind === "conditionalBranch" && graphState(body.graph, edge.from) === "INIT_MOVE");
  const branchTargets = branches.map((edge) => graphState(body.graph, edge.to));
  const conditionsClosed = branches.length === 4
    && branchTargets.filter((state) => state === "NASTY_BITE_MOVE").length === 2
    && branchTargets.filter((state) => state === "WRIGGLE_MOVE").length === 2
    && branches.every((edge, index) => edge.order === index && edge.predicate?.kind === "reference");
  if (!graphClosed || !conditionsClosed || exactConstant(start?.baseValue?.expression) !== false) return null;
  primaryBody.setup = "4 Wrigglers · four simultaneous initial bodies · not Stunned at encounter start.";
  primaryBody.sections = [
    sourceSection("Branch · cycle offset", [
      sourceRow(sourceOperationDetail(moves.get("NASTY_BITE_MOVE")), "Damage offset"),
      sourceRow(sourceOperationDetail(moves.get("WRIGGLE_MOVE")), "Status + scaling offset"),
    ], {
      note: "Each Wriggler follows one of these two initial offsets; the branches do not occur simultaneously.",
      repeat: "↻ then alternate the two offsets",
    }),
    sourceSection("Alternate entry response", [sourceRow(`${sourceOperationDetail(moves.get("SPAWNED_MOVE"))} → enter one of the two cycle offsets`, "Alternate entry")], {
      note: "Not used by this encounter's initial four-body setup.",
    }),
  ];
  return primaryBody;
}
function fakeMerchantPrimary(body, primaryBody) {
  const moves = sourceMoveMap(body), graph = body.graph;
  const graphClosed = hasEventGraph(body, {
    graphId: "GRAPH.FAKE_MERCHANT_MONSTER",
    states: ["SWIPE_MOVE", "SPEW_COINS_MOVE", "THROW_RELIC_MOVE", "ENRAGE_MOVE", "RAND_MOVE", "RAND_ATTACK_MOVE"],
    initial: ["SWIPE_MOVE"],
    edges: ["SWIPE_MOVE>RAND_MOVE:followUp", "SPEW_COINS_MOVE>RAND_MOVE:followUp", "THROW_RELIC_MOVE>RAND_ATTACK_MOVE:followUp", "ENRAGE_MOVE>RAND_MOVE:followUp"],
  });
  const random = (graph?.edges ?? []).filter((edge) => edge.kind === "randomBranch");
  const full = random.filter((edge) => graphState(graph, edge.from) === "RAND_MOVE");
  const attackOnly = random.filter((edge) => graphState(graph, edge.from) === "RAND_ATTACK_MOVE");
  const fullTargets = new Set(full.map((edge) => graphState(graph, edge.to)));
  const attackTargets = new Set(attackOnly.map((edge) => graphState(graph, edge.to)));
  const constraintClosed = graphClosed && full.length === 4 && fullTargets.size === 4
    && ["SWIPE_MOVE", "SPEW_COINS_MOVE", "THROW_RELIC_MOVE", "ENRAGE_MOVE"].every((state) => fullTargets.has(state))
    && attackOnly.length === 3 && attackTargets.size === 3
    && ["SWIPE_MOVE", "SPEW_COINS_MOVE", "THROW_RELIC_MOVE"].every((state) => attackTargets.has(state))
    && random.every((edge) => edge.repeat?.enumName === "CannotRepeat")
    && full.find((edge) => graphState(graph, edge.to) === "ENRAGE_MOVE")?.cooldown === 3;
  if (!constraintClosed) return null;
  primaryBody.sections = [
    sourceSection("Opener", [sourceRow(sourceOperationDetail(moves.get("SWIPE_MOVE")), "Turn 1")], { transitionAfter: true }),
    sourceSection("Branch", [
      sourceRow(sourceOperationDetail(moves.get("SWIPE_MOVE")), "Single hit"),
      sourceRow(sourceOperationDetail(moves.get("SPEW_COINS_MOVE")), "Eight hits"),
      sourceRow(sourceOperationDetail(moves.get("THROW_RELIC_MOVE")), "Hit + status"),
      sourceRow(sourceOperationDetail(moves.get("ENRAGE_MOVE")), "Self-scaling"),
    ], {
      note: "Randomly choose one eligible row. A row cannot repeat immediately. The +2 Strength row has a cooldown of 3. After the damage + 1 Frail row, the next branch is attack-only.",
      repeat: "↻ return to the eligible random branch",
    }),
  ];
  return primaryBody;
}
function mysteriousKnightPrimary(encounter, body, primaryBody, players) {
  const moves = sourceMoveMap(body), graph = body.graph;
  const graphClosed = hasEventGraph(body, {
    graphId: "GRAPH.FLAIL_KNIGHT", states: ["WAR_CHANT", "FLAIL_MOVE", "RAM_MOVE", "RAND"], initial: ["RAM_MOVE"],
    edges: ["WAR_CHANT>RAND:followUp", "FLAIL_MOVE>RAND:followUp", "RAM_MOVE>RAND:followUp"],
  });
  const random = (graph?.edges ?? []).filter((edge) => edge.kind === "randomBranch" && graphState(graph, edge.from) === "RAND");
  const strength = scaledInitialPower(body, "POWER.STRENGTH_POWER", encounter, players);
  const plating = scaledInitialPower(body, "POWER.PLATING_POWER", encounter, players);
  const randomTargets = new Set(random.map((edge) => graphState(graph, edge.to)));
  const constraintClosed = graphClosed && random.length === 3 && randomTargets.size === 3
    && ["WAR_CHANT", "FLAIL_MOVE", "RAM_MOVE"].every((state) => randomTargets.has(state))
    && random.every((edge) => exactConstant(edge.weight) === 1)
    && random.find((edge) => graphState(graph, edge.to) === "WAR_CHANT")?.repeat?.enumName === "CannotRepeat"
    && random.filter((edge) => ["FLAIL_MOVE", "RAM_MOVE"].includes(graphState(graph, edge.to)))
      .every((edge) => edge.repeat?.enumName === "CanRepeatXTimes" && edge.repeat.maximumConsecutiveUses === 2);
  if (!constraintClosed || (strength !== 6 && strength !== "6") || plating === null) return null;
  primaryBody.setup = `Starts with · Strength base ${strength} · Plating base ${plating} after configured ${players}P scaling.`;
  primaryBody.sections = [
    sourceSection("Opener", [sourceRow(sourceOperationDetail(moves.get("RAM_MOVE")), "Turn 1")], { transitionAfter: true }),
    sourceSection("Branch", [
      sourceRow(sourceOperationDetail(moves.get("WAR_CHANT")), "Self-scaling"),
      sourceRow(sourceOperationDetail(moves.get("FLAIL_MOVE")), "Two hits"),
      sourceRow(sourceOperationDetail(moves.get("RAM_MOVE")), "Single hit"),
    ], {
      note: "Then randomly choose one of three equally weighted rows. The Strength row cannot repeat immediately; either attack can occur no more than twice consecutively.",
      repeat: "↻ return to the weighted random branch",
    }),
  ];
  return primaryBody;
}
function punchPrimary(encounter, body, primaryBody, maximumHp, players) {
  const moves = sourceMoveMap(body);
  const graphClosed = hasEventGraph(body, {
    graphId: "GRAPH.PUNCH_CONSTRUCT", states: ["READY_MOVE", "FAST_PUNCH_MOVE", "STRONG_PUNCH_MOVE"],
    initial: ["READY_MOVE", "FAST_PUNCH_MOVE"],
    edges: ["READY_MOVE>FAST_PUNCH_MOVE:followUp", "FAST_PUNCH_MOVE>STRONG_PUNCH_MOVE:followUp", "STRONG_PUNCH_MOVE>READY_MOVE:followUp"],
  });
  const fast = body.initialState?.find((fact) => /::set_StartsWithFastPunch\b/.test(fact.effect?.member ?? ""));
  const reduction = punchReduction(encounter, body, maximumHp);
  const artifact = scaledInitialPower(body, "POWER.ARTIFACT_POWER", encounter, players);
  if (!graphClosed || exactConstant(fast?.baseValue?.expression) !== true || !reduction || artifact === null) return null;
  const starting = formatPracticalRange(reduction.startingHp);
  primaryBody.setup = `2 Punch Constructs · two simultaneous initial bodies · ${maximumHp} max HP each; each starts at ${starting} HP after its own runtime-random starting HP reduction of ${reduction.minimum}–${reduction.maximumExclusive - 1} HP · Artifact base ${artifact} after configured ${players}P scaling · both begin at step 1 below.`;
  primaryBody.sections = [sourceSection("Cycle", [
    sourceRow(sourceOperationDetail(moves.get("FAST_PUNCH_MOVE")), "1"),
    sourceRow(sourceOperationDetail(moves.get("STRONG_PUNCH_MOVE")), "2"),
    sourceRow(sourceOperationDetail(moves.get("READY_MOVE"), { encounter, players }), "3"),
  ], { repeat: "↻ repeat 1 → 2 → 3" })];
  return { body: primaryBody, starting };
}
function architectPrimary(body, primaryBody) {
  const moves = sourceMoveMap(body);
  const graphClosed = hasEventGraph(body, {
    graphId: "GRAPH.ARCHITECT", states: ["NOTHING"], initial: ["NOTHING"], edges: ["NOTHING>NOTHING:followUp"],
  });
  if (!graphClosed || sourceOperationDetail(moves.get("NOTHING")) !== "takes no action") return null;
  primaryBody.setup = "Scripted non-turn combat.";
  primaryBody.sections = [sourceSection("Behavior", [sourceRow("takes no combat action", "Registered behavior")], {
    note: "No combat effect is registered for this action.",
  })];
  return primaryBody;
}
function eventPrimaryPresentation(encounter, options) {
  if (!EVENT_PRIMARY_IDS.has(encounter.canonicalId) || encounter.kind !== "event" || encounter.reference !== null) return null;
  const players = Number(options.players ?? 2);
  if (!Number.isSafeInteger(players) || players < 1 || players > 4) return null;
  const expectedCount = encounter.canonicalId === "DENSE_VEGETATION_EVENT_ENCOUNTER" ? 4
    : encounter.canonicalId === "PUNCH_OFF_EVENT_ENCOUNTER" ? 2 : 1;
  const count = encounter.roster?.cardinality;
  const body = encounter.monsters?.[0];
  const children = encounter.roster?.grammar?.kind === "sequence" ? encounter.roster.grammar.children : null;
  if (!body || encounter.monsters.length !== 1 || count?.minimum !== expectedCount || count.maximum !== expectedCount
      || !children || children.length !== expectedCount || children.some((child) => child.kind !== "fixed" || child.model !== body.canonicalModel)
      || !eventScalingContractsClosed(encounter)) return null;
  const primaryBody = eventBodyBase(encounter, body, players, expectedCount);
  if (!primaryBody) return null;
  let compiled = null, starting = null;
  if (encounter.canonicalId.startsWith("BATTLEWORN_DUMMY_EVENT_V")) compiled = battleFriendPrimary(encounter, body, primaryBody);
  else if (encounter.canonicalId === "DENSE_VEGETATION_EVENT_ENCOUNTER") compiled = densePrimary(body, primaryBody);
  else if (encounter.canonicalId === "FAKE_MERCHANT_EVENT_ENCOUNTER") compiled = fakeMerchantPrimary(body, primaryBody);
  else if (encounter.canonicalId === "MYSTERIOUS_KNIGHT_EVENT_ENCOUNTER") compiled = mysteriousKnightPrimary(encounter, body, primaryBody, players);
  else if (encounter.canonicalId === "PUNCH_OFF_EVENT_ENCOUNTER") {
    const punch = punchPrimary(encounter, body, primaryBody, checkedEventHp(encounter, body, players)?.[1], players);
    compiled = punch?.body ?? null; starting = punch?.starting ?? null;
  } else if (encounter.canonicalId === "THE_ARCHITECT_EVENT_ENCOUNTER") compiled = architectPrimary(body, primaryBody);
  if (!compiled) return null;
  const hp = compiled.hp;
  const stats = expectedCount === 4 ? `${hp} HP each · EVENT FIGHT`
    : expectedCount === 2 ? `${hp} max HP each${starting ? ` · starts at ${starting} HP each` : ""} · EVENT FIGHT`
      : `${hp} HP · EVENT FIGHT`;
  return {
    header: { stats, placement: eventPlacement(encounter), kind: "EVENT FIGHT" },
    bodies: [compiled], notes: [], showBodyHeaders: true,
    provenance: {
      label: `checked source values · A8 / ${players}P presentation`, authority: "checked-source-only",
      matching: "exact source encounter, roster, model, graph, operation, initialization, and lifecycle joins only",
      mergePolicy: "source-only event combat card; no retained reference merge",
      values: [],
    },
  };
}

function primaryPresentation(encounter, options) {
  const reference = options.reference;
  if (!reference) return eventPrimaryPresentation(encounter, options);
  const provenanceValues = [];
  const maximumPhase = Math.max(0, ...reference.lineup.map((body) => referencePhaseNumber(body) ?? 0));
  const practicalMoves = [];
  const bodies = reference.lineup.map((referenceBody, bodyIndex) => {
    const sourceBody = exactSourceBody(encounter, referenceBody);
    const moves = referenceBody.moves.map((move) => bestMove(
      primaryReferenceMove(referenceBody, move, options.scaling), sourceBody, options.scaling, bodyIndex, provenanceValues,
    ));
    practicalMoves.push(...moves);
    const players = Number(options.scaling?.players ?? 2);
    const thresholdValue = referenceBody.monsterId === "TERROR_EEL" && players === 1
      ? referenceBody.startsWithA9 : referenceBody.startsWith;
    const focused = focusedSections(referenceBody, sourceBody, moves, thresholdValue);
    const sections = focused !== undefined
      ? focused : ceremonialSections(referenceBody, moves, options.scaling) ?? genericSections(referenceBody, moves);
    return {
      bodyIndex,
      name: referenceBody.displayName,
      role: practicalRole(encounter, sourceBody, referenceBody, moves),
      initial: isPracticalInitial(encounter, sourceBody, referenceBody),
      hp: practicalHp(sourceBody, referenceBody, options.scaling, bodyIndex, provenanceValues),
      setup: referenceBody.monsterId === "TERROR_EEL"
        ? null : referenceBody.startsWith ? `Starts with · ${referenceBody.startsWith}` : null,
      sections: roleNumberedSections(referenceBody, sections, maximumPhase),
      watch: referenceBody.monsterId === "CEREMONIAL_BEAST"
        ? ["crossing the phase threshold clears accumulated Strength."] : [],
      sourceMatchedExactly: sourceBody !== null,
    };
  });
  let possibleInitial = bodies.filter((body) => body.initial);
  if (!possibleInitial.length) possibleInitial = bodies.filter((body) => reference.lineup[body.bodyIndex].role !== "summoned");
  const single = possibleInitial.length === 1 ? possibleInitial[0] : null;
  const kind = ({ boss: "BOSS", elite: "ELITE", hallway: "ORDINARY" })[reference.kind] ?? String(reference.kind ?? "ENCOUNTER").toUpperCase();
  const players = options.scaling?.players ?? options.referenceMeta?.players ?? 2;
  return {
    header: {
      stats: single?.hp ? `${single.hp} HP · ${kind}` : kind,
      placement: reference.act,
      kind,
    },
    bodies,
    notes: encounter.canonicalId === "TERROR_EEL_ELITE" ? []
      : encounter.canonicalId === "AXEBOTS_NORMAL"
        ? uniqueReferenceNotes(reference, practicalMoves).filter((note) => /\bFatal\b/.test(note))
        : uniqueReferenceNotes(reference, practicalMoves),
    provenance: {
      label: `wiki/reference values · A9 / ${players}P presentation`,
      matching: "exact canonical encounter and monster IDs only",
      mergePolicy: "checked source when closed; otherwise retained exact reference",
      values: provenanceValues,
    },
  };
}

function contextPresentation(encounter) {
  const memberships = encounter.placement?.memberships ?? [];
  const primary = memberships[0];
  const practicalKind = primary ? words(primary.tier ?? primary.roomClass) : words(encounter.kind);
  return {
    kind: practicalKind,
    summary: primary ? words(primary.actId) : practicalKind,
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
  const bodyIndexes = new Map((encounter.monsters ?? []).map((body, index) => [body.canonicalModel, index]));
  const powerBodyIndexes = new Map();
  const indexPower = (power, index) => {
    if (typeof power !== "string" || !power.startsWith("POWER.")) return;
    const indexes = powerBodyIndexes.get(power) ?? [];
    if (!indexes.includes(index)) indexes.push(index);
    powerBodyIndexes.set(power, indexes);
  };
  (encounter.monsters ?? []).forEach((body, index) => (body.initialState ?? []).forEach((fact) => indexPower(fact.effect?.model, index)));
  // Retention policies name their Power but not its body. A body-anchored lifecycle
  // operation on sameOwnerBody supplies that ownership edge without guessing targets.
  for (const { row } of lifecyclePresentationRecords(encounter.lifecycle?.mechanics ?? {})) {
    const ownerModels = [row.ownerModel, ...(row.ownerModels ?? []), row.canonicalModel, ...(row.applicableConcreteModels ?? [])];
    const ownerIndexes = ownerModels.map((model) => bodyIndexes.get(model)).filter((index) => index !== undefined);
    if (!ownerIndexes.length) continue;
    for (const branch of row.transitions ?? row.branches ?? [row]) {
      for (const operation of branch.orderedEffects ?? row.orderedEffects ?? row.orderedPerPlayer ?? []) {
        if (operation?.target !== "sameOwnerBody") continue;
        for (const power of [operation.power, operation.model, operation.owner, operation.retainedPower]) {
          for (const index of ownerIndexes) indexPower(power, index);
        }
      }
    }
  }
  const candidates = options.calloutCandidates ?? checkedCalloutCandidates(encounter.canonicalId);
  const callouts = options.calloutCollection
    ? validatedCollection(options.calloutCollection)
    : compileCalloutCollection(candidates, options.calloutContext ?? {}, { collapsedLimit: options.collapsedLimit ?? 1 });
  const production = productionPresentation(encounter.production, names);
  const lifecycle = lifecyclePresentation(encounter.lifecycle ?? {}, names, bodyIndexes, powerBodyIndexes);
  const roster = {
    summary: rosterNode(encounter.roster?.grammar, names),
    cardinality: rangeText(encounter.roster?.cardinality),
    caveat: "Random and alternative branches are possibilities. Only one branch is selected; listed possibilities are not all co-present.",
  };
  const unknowns = (encounter.knownUnknowns ?? []).map((row) => ({
    headline: text(row.detail, words(row.unknownId)),
    detail: `${words(row.status)} · ${words(row.scope)} · ${words(row.reasonCode)}`,
  }));
  const projectedPrimary = primaryPresentation(encounter, options);
  const mergeProvenance = projectedPrimary?.provenance?.authority === "checked-source-only" ? null : projectedPrimary?.provenance ?? null;
  const primary = projectedPrimary ? {
    ...projectedPrimary,
    provenance: projectedPrimary.provenance.authority
      ? { label: projectedPrimary.provenance.label, authority: projectedPrimary.provenance.authority }
      : { label: projectedPrimary.provenance.label },
  } : null;
  return {
    primary,
    audit: { mergeProvenance },
    context: contextPresentation(encounter), roster,
    bodies: (encounter.monsters ?? []).map((body, index) => bodyPresentation(body, index, encounter, names)),
    production, lifecycle,
    event: eventPresentation(encounter.event),
    unknowns, callouts,
  };
}

export const presentationInternals = Object.freeze({
  words, rosterNode, moveEffects, graphPresentation, initialEffect, targetText,
  productionPresentation, lifecyclePresentation, lifecyclePresentationRecords, lifecycleEffect,
  retentionPolicyText, lifecycleWriteText, eventPresentation, eventEffect, validatedCollection,
  mechanicAtom, mechanicAtoms, primaryPresentation, eventPrimaryPresentation, genericSections, ceremonialSections, roleNumberedSections,
  exactGraphContract, stateIncrement, axebotSections, terrorEelSections,
  BOOLEAN_CONDITIONS, EVENT_EFFECT_KINDS, LIFECYCLE_WRITES, TARGETS,
});
