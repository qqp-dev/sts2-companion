const CRITERIA = Object.freeze([
  "playerControllable", "nonObvious", "materiallyUseful", "ordinaryStateRobust",
  "sourceSupported", "causallyExplainable", "distinct",
]);
const LANGUAGES = new Set(["static-conditional", "live-imperative"]);

export class CalloutContractError extends Error {
  constructor(message) { super(`invalid callout collection: ${message}`); this.name = "CalloutContractError"; }
}
function fail(message) { throw new CalloutContractError(message); }
function object(value, label) { if (!value || typeof value !== "object" || Array.isArray(value)) fail(`${label} must be an object`); return value; }
function string(value, label) { if (typeof value !== "string" || !value || value.length > 500) fail(`${label} must be a non-empty bounded string`); return value; }
function refs(value, label) {
  if (!Array.isArray(value) || value.length === 0) fail(`${label} must contain at least one reference`);
  const result = value.map((item, index) => string(item, `${label}[${index}]`));
  if (new Set(result).size !== result.length) fail(`${label} contains a duplicate`);
  return result;
}
function freeze(value) { if (value && typeof value === "object" && !Object.isFrozen(value)) { Object.freeze(value); Object.values(value).forEach(freeze); } return value; }

function validateCandidate(candidate, index) {
  const label = `candidate[${index}]`; object(candidate, label);
  const id = string(candidate.id, `${label}.id`); const distinctnessKey = string(candidate.distinctnessKey, `${label}.distinctnessKey`);
  const language = string(candidate.language, `${label}.language`); if (!LANGUAGES.has(language)) fail(`${id} has unsupported language ${language}`);
  const qualifications = object(candidate.qualifications, `${id}.qualifications`);
  const evaluated = {};
  for (const criterion of CRITERIA) {
    if (typeof qualifications[criterion] !== "boolean") fail(`${id}.qualifications.${criterion} must be boolean`);
    evaluated[criterion] = qualifications[criterion];
  }
  const basis = object(candidate.basis, `${id}.basis`);
  const factRefs = refs(basis.factRefs, `${id}.basis.factRefs`);
  const conditionRefs = refs(basis.conditionRefs, `${id}.basis.conditionRefs`);
  const causalRefs = refs(basis.causalRefs, `${id}.basis.causalRefs`);
  if (!Number.isSafeInteger(candidate.rank) || candidate.rank < 0) fail(`${id}.rank must be a non-negative integer`);
  const mechanic = candidate.mechanic == null ? null : string(candidate.mechanic, `${id}.mechanic`);
  let phaseControl = null;
  if (mechanic === "phase-control") {
    const causal = object(candidate.phaseControl, `${id}.phaseControl`);
    phaseControl = {
      controllableChoice: string(causal.controllableChoice, `${id}.phaseControl.controllableChoice`),
      staggeredEffect: string(causal.staggeredEffect, `${id}.phaseControl.staggeredEffect`),
      synchronizedSpikeAvoided: string(causal.synchronizedSpikeAvoided, `${id}.phaseControl.synchronizedSpikeAvoided`),
      mechanismRefs: refs(causal.mechanismRefs, `${id}.phaseControl.mechanismRefs`),
    };
  }
  return {
    id, distinctnessKey, language, mechanic,
    headline: string(candidate.headline, `${id}.headline`),
    condition: string(candidate.condition, `${id}.condition`),
    causalBasis: string(candidate.causalBasis, `${id}.causalBasis`),
    qualifications: evaluated, basis: { factRefs, conditionRefs, causalRefs },
    phaseControl, rank: candidate.rank,
  };
}

/**
 * Editorially neutral collection reducer. It validates/evaluates every candidate,
 * keeps all distinct passing records, and only limits the collapsed view. It does
 * not derive tactics from source facts.
 */
export function compileCalloutCollection(candidates, context = {}, options = {}) {
  if (!Array.isArray(candidates)) fail("candidates must be an array");
  const collapsedLimit = options.collapsedLimit ?? 1;
  if (!Number.isSafeInteger(collapsedLimit) || collapsedLimit < 0 || collapsedLimit > 20) fail("collapsedLimit must be an integer from 0 to 20");
  const observationRefs = context.observationRefs == null ? [] : (() => {
    if (!Array.isArray(context.observationRefs)) fail("context.observationRefs must be an array");
    if (context.observationRefs.length === 0) return [];
    return refs(context.observationRefs, "context.observationRefs");
  })();
  const hasCurrentObservation = context.hasCurrentObservation === true && observationRefs.length > 0;
  const ids = new Set(); const evaluated = [];
  candidates.forEach((raw, index) => {
    const candidate = validateCandidate(raw, index);
    if (ids.has(candidate.id)) fail(`duplicate candidate ID ${candidate.id}`); ids.add(candidate.id);
    const failedCriteria = CRITERIA.filter((criterion) => !candidate.qualifications[criterion]);
    let rejection = failedCriteria.length ? `failed evidence gate: ${failedCriteria.join(", ")}` : null;
    if (!rejection && candidate.language === "live-imperative" && !hasCurrentObservation) rejection = "live imperative requires a current observed-state basis";
    evaluated.push({ candidate, rejection });
  });
  const passing = evaluated.filter((row) => row.rejection === null).map((row) => row.candidate)
    .sort((a, b) => a.rank - b.rank || a.id.localeCompare(b.id));
  const byDistinctness = new Map(), duplicates = [];
  for (const candidate of passing) {
    if (byDistinctness.has(candidate.distinctnessKey)) duplicates.push({ id: candidate.id, duplicateOf: byDistinctness.get(candidate.distinctnessKey).id, distinctnessKey: candidate.distinctnessKey });
    else byDistinctness.set(candidate.distinctnessKey, candidate);
  }
  const all = [...byDistinctness.values()].map((candidate) => freeze({ ...candidate }));
  const collapsed = all.slice(0, collapsedLimit);
  const rejected = evaluated.filter((row) => row.rejection !== null).map((row) => ({ id: row.candidate.id, reason: row.rejection }));
  const result = {
    total: all.length,
    passingBeforeDistinctness: passing.length,
    collapsedCount: collapsed.length,
    collapsed,
    all,
    hasMore: all.length > collapsed.length,
    expandPathRequired: all.length > collapsed.length,
    rejected,
    deduplicated: duplicates,
    observationBasis: hasCurrentObservation ? { current: true, refs: [...observationRefs] } : { current: false, refs: [] },
    emptyReason: all.length === 0 ? "0 source-qualified distinct callouts passed the evidence and observation gates" : null,
  };
  return freeze(result);
}

export const calloutContract = Object.freeze({ criteria: CRITERIA, languages: Object.freeze([...LANGUAGES]), cardinality: "0..N", ranking: "rank ascending, then stable candidate ID", extractorRole: "editorially neutral" });
