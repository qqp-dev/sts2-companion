/**
 * Phone-facing projection of the adapter-validated closed-source roster grammar.
 *
 * @typedef {{kind:"fixed", name:string}} PracticalFixed
 * @typedef {{kind:"allOf", order:"fixed", relationship:"fixed order"|"independent draws", items:PracticalSelection[]}} PracticalAllOf
 * @typedef {{kind:"uniformAlternatives", selection:"one uniformly", unit:string, choices:PracticalSelection[]}} PracticalUniform
 * @typedef {{kind:"distinctSelection", count:number, poolSize:number, unit:string, constraint:"distinct models", draws:"without replacement", choices:PracticalSelection[]}} PracticalFiltered
 * @typedef {PracticalFixed|PracticalAllOf|PracticalUniform|PracticalFiltered} PracticalSelection
 * @typedef {{name:string, minimum:number, maximum:number, role:string}} PracticalBodyPresence
 * @typedef {{cardinality:string, cardinalityLabel:string, variable:boolean, selection:PracticalSelection, lines:string[], caveat:string|null, bodies:PracticalBodyPresence[]}} PracticalRoster
 */

const KINDS = new Set(["fixed", "sequence", "uniformChoice", "filteredChoice"]);
const MAX_DEPTH = 24;
const MAX_OUTCOMES = 10_000;

export class PracticalRosterError extends TypeError {
  constructor(message) { super(`practical roster unavailable: ${message}`); this.name = "PracticalRosterError"; }
}
function fail(message) { throw new PracticalRosterError(message); }
function plainObject(value, path) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(`${path} must be an object`);
  return value;
}
function nonemptyArray(value, path) {
  if (!Array.isArray(value) || value.length === 0) fail(`${path} must be a non-empty array`);
  return value;
}
function modelName(model, names) {
  const name = names.get(model);
  if (typeof model !== "string" || !model) fail("fixed selection has no model");
  if (typeof name !== "string" || !name) fail(`possible model ${model} has no exact source display name`);
  return name;
}
function boundedPush(target, value, path) {
  if (target.length >= MAX_OUTCOMES) fail(`${path} exceeds the ${MAX_OUTCOMES}-outcome analysis limit`);
  target.push(value);
}
function sameNode(left, right) { return JSON.stringify(left) === JSON.stringify(right); }

/** Expand every ordered possibility. Duplicate arrays from distinct branches are intentionally retained. */
function expandNode(node, path = "grammar", depth = 0) {
  plainObject(node, path);
  if (depth > MAX_DEPTH) fail(`${path} exceeds maximum depth ${MAX_DEPTH}`);
  if (!KINDS.has(node.kind)) fail(`${path} has unsupported kind ${String(node.kind)}`);
  if (node.kind === "fixed") {
    if (typeof node.model !== "string" || !node.model) fail(`${path}.model must be a non-empty string`);
    return [[node.model]];
  }
  if (node.kind === "sequence") {
    if (node.order !== "fixed") fail(`${path}.order must be fixed`);
    const children = nonemptyArray(node.children, `${path}.children`);
    let outcomes = [[]];
    children.forEach((child, childIndex) => {
      const childOutcomes = expandNode(child, `${path}.children[${childIndex}]`, depth + 1);
      const combined = [];
      for (const prefix of outcomes) for (const suffix of childOutcomes)
        boundedPush(combined, [...prefix, ...suffix], path);
      outcomes = combined;
    });
    return outcomes;
  }
  const choices = nonemptyArray(node.choices, `${path}.choices`);
  if (node.kind === "uniformChoice") {
    const outcomes = [];
    choices.forEach((choice, choiceIndex) => {
      for (const outcome of expandNode(choice, `${path}.choices[${choiceIndex}]`, depth + 1))
        boundedPush(outcomes, outcome, path);
    });
    return outcomes;
  }
  if (!Number.isSafeInteger(node.count) || node.count < 1 || node.count > choices.length)
    fail(`${path}.count must select between 1 and the pool size`);
  if (node.constraint !== "modelCountLimit") fail(`${path} has unsupported constraint ${String(node.constraint)}`);
  if (node.draws !== "withoutReplacement") fail(`${path} has unsupported draw semantics ${String(node.draws)}`);
  const models = choices.map((choice, choiceIndex) => {
    const outcomes = expandNode(choice, `${path}.choices[${choiceIndex}]`, depth + 1);
    if (outcomes.length !== 1 || outcomes[0].length !== 1)
      fail(`${path}.choices[${choiceIndex}] is not a single exact model; modelCountLimit cannot be projected honestly`);
    return outcomes[0][0];
  });
  if (new Set(models).size !== models.length) fail(`${path} repeats a model in a distinct pool`);
  const outcomes = [];
  const draw = (prefix, remaining) => {
    if (prefix.length === node.count) { boundedPush(outcomes, prefix, path); return; }
    remaining.forEach((model, index) => draw([...prefix, model], [...remaining.slice(0, index), ...remaining.slice(index + 1)]));
  };
  draw([], models);
  return outcomes;
}

function firstModelOrder(node, result = []) {
  if (node.kind === "fixed") { if (!result.includes(node.model)) result.push(node.model); return result; }
  for (const child of node.children ?? node.choices ?? []) firstModelOrder(child, result);
  return result;
}
function countModels(outcome) {
  const counts = new Map();
  for (const model of outcome) counts.set(model, (counts.get(model) ?? 0) + 1);
  return counts;
}
function roleFor(minimum, maximum) {
  if (minimum === maximum) {
    if (minimum === 1) return "always present";
    return `always ${minimum} copies`;
  }
  if (minimum === 0) return maximum === 1 ? "possible body" : `possible up to ${maximum} copies`;
  return `always present · possible up to ${maximum} copies`;
}
function rangeLabel(minimum, maximum) { return minimum === maximum ? String(minimum) : `${minimum}–${maximum}`; }
function choiceUnit(node, names) {
  const projected = (node.choices ?? []).map((choice) => choice.kind === "fixed" ? names.get(choice.model) : null);
  if (projected.every((name) => typeof name === "string" && / Slime \(M\)$/.test(name))) return "medium slime";
  if (projected.every((name) => typeof name === "string" && / Slime \(S\)$/.test(name))) return "small slime";
  if (projected.every((name) => typeof name === "string" && / Raider$/.test(name))) return "raider";
  if (projected.every((name) => typeof name === "string" && /^Bowlbug \((?:Egg|Silk|Nectar)\)$/.test(name))) return "worker";
  return "body";
}
function isRepeatedIndependentDraws(node) {
  return node.kind === "sequence" && node.children.length > 1
    && node.children.every((child) => child.kind === "uniformChoice" && sameNode(child, node.children[0]));
}
function projectNode(node, names) {
  if (node.kind === "fixed") return { kind: "fixed", name: modelName(node.model, names) };
  if (node.kind === "sequence") return {
    kind: "allOf", order: "fixed",
    relationship: isRepeatedIndependentDraws(node) ? "independent draws" : "fixed order",
    items: node.children.map((child) => projectNode(child, names)),
  };
  if (node.kind === "uniformChoice") return {
    kind: "uniformAlternatives", selection: "one uniformly", unit: choiceUnit(node, names),
    choices: node.choices.map((choice) => projectNode(choice, names)),
  };
  return {
    kind: "distinctSelection", count: node.count, poolSize: node.choices.length,
    unit: choiceUnit(node, names), constraint: "distinct models", draws: "without replacement",
    choices: node.choices.map((choice) => projectNode(choice, names)),
  };
}
function shortSelection(node) {
  if (node.kind === "fixed") return node.name;
  if (node.kind === "distinctSelection") return describeSelection(node).replace(/\.$/, "");
  if (node.kind === "uniformAlternatives") return describeSelection(node).replace(/\.$/, "");
  if (node.relationship === "independent draws") return independentDescription(node).replace(/\.$/, "");
  return node.items.map(shortSelection).join(" → ");
}
function independentDescription(node) {
  const draw = node.items[0];
  const labels = draw.choices.map(shortSelection);
  const examples = labels.length > 1 ? `${labels[0]} + ${labels[0]} or ${labels.at(-1)} + ${labels.at(-1)}` : `${labels[0]} + ${labels[0]}`;
  return `${node.items.length} independent draws; each uniformly chooses exactly one ${draw.unit}: ${labels.join(" or ")}; duplicates are possible: ${examples}.`;
}
function sameMembersInDifferentOrder(choices) {
  if (!choices.length || choices.some((choice) => choice.kind !== "allOf")) return false;
  const signature = (choice) => choice.items.map((item) => JSON.stringify(item)).sort().join("\0");
  return choices.every((choice) => signature(choice) === signature(choices[0]));
}
function describeSelection(node) {
  if (node.kind === "fixed") return node.name;
  if (node.kind === "allOf") {
    if (node.relationship === "independent draws") return independentDescription(node);
    const ordered = node.items.map((item) => item.kind === "fixed" ? shortSelection(item) : `(${shortSelection(item)})`);
    return `Fixed order: ${ordered.join(" → ")}.`;
  }
  if (node.kind === "distinctSelection") {
    const unit = node.count === 1 ? node.unit : node.unit === "body" ? "bodies" : `${node.unit}s`;
    return `Choose exactly ${node.count} distinct ${unit} without replacement from ${node.poolSize}: ${node.choices.map(shortSelection).join(", ")}.`;
  }
  const allFixed = node.choices.every((choice) => choice.kind === "fixed");
  const alternativeOrders = sameMembersInDifferentOrder(node.choices);
  if (allFixed) return `Choose exactly one ${node.unit} uniformly: ${node.choices.map(shortSelection).join(" or ")}.`;
  if (alternativeOrders) return `Choose one of ${node.choices.length} orders uniformly: ${node.choices.map(shortSelection).join(" OR ")}.`;
  return `Choose one of ${node.choices.length} equiprobable support categories: ${node.choices.map(shortSelection).join(" OR ")}.`;
}

/**
 * Analyze exact source grammar. Internal model IDs are returned only for the
 * compiler join; the practical view model contains display names only.
 */
export function analyzeRosterGrammar(roster, names) {
  plainObject(roster, "roster");
  plainObject(roster.cardinality, "roster.cardinality");
  if (!Number.isSafeInteger(roster.cardinality.minimum) || roster.cardinality.minimum < 0
      || !Number.isSafeInteger(roster.cardinality.maximum) || roster.cardinality.maximum < roster.cardinality.minimum)
    fail("declared cardinality is malformed");
  if (!(names instanceof Map)) fail("exact source name index is unavailable");
  const outcomes = expandNode(roster.grammar);
  if (!outcomes.length) fail("grammar has no outcomes");
  const lengths = outcomes.map((outcome) => outcome.length);
  const actualMinimum = Math.min(...lengths), actualMaximum = Math.max(...lengths);
  if (actualMinimum !== roster.cardinality.minimum || actualMaximum !== roster.cardinality.maximum)
    fail(`declared cardinality ${rangeLabel(roster.cardinality.minimum, roster.cardinality.maximum)} does not match exact grammar ${rangeLabel(actualMinimum, actualMaximum)}`);
  const traversalOrder = firstModelOrder(roster.grammar);
  const counts = outcomes.map(countModels);
  const bounds = new Map(traversalOrder.map((model) => {
    modelName(model, names);
    const values = counts.map((row) => row.get(model) ?? 0);
    return [model, { minimum: Math.min(...values), maximum: Math.max(...values) }];
  }));
  const cardModels = [...traversalOrder].sort((left, right) => {
    const required = Number(bounds.get(right).minimum > 0) - Number(bounds.get(left).minimum > 0);
    return required || traversalOrder.indexOf(left) - traversalOrder.indexOf(right);
  });
  const uniqueOutcomes = new Set(outcomes.map((outcome) => outcome.join("\0")));
  const variable = uniqueOutcomes.size > 1 || (function hasSelection(node) {
    return node.kind === "uniformChoice" || node.kind === "filteredChoice"
      || (node.children ?? []).some(hasSelection);
  })(roster.grammar);
  const selection = projectNode(roster.grammar, names);
  const bodies = cardModels.map((model) => {
    const bound = bounds.get(model);
    return { name: names.get(model), ...bound, role: roleFor(bound.minimum, bound.maximum) };
  });
  const required = bodies.filter((body) => body.minimum > 0);
  const lines = [];
  if (required.length) lines.push(`Always: ${required.map((body) => body.minimum === 1 ? body.name : `${body.minimum}× ${body.name}`).join(" + ")}.`);
  lines.push(describeSelection(selection));
  const cardinality = rangeLabel(actualMinimum, actualMaximum);
  /** @type {PracticalRoster} */
  const presentation = {
    cardinality,
    cardinalityLabel: `${cardinality} initial ${actualMaximum === 1 ? "body" : "bodies"}`,
    variable,
    selection,
    lines,
    caveat: variable ? "Body cards cover every possible type. Alternatives are not all co-present; encounter identity alone does not reveal the selected lineup." : null,
    bodies,
  };
  return { presentation, outcomes, bounds, cardModels };
}

export const rosterInternals = Object.freeze({ expandNode, projectNode, describeSelection, sameMembersInDifferentOrder, roleFor, rangeLabel });
