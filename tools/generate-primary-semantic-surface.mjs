#!/usr/bin/env node
/** Build/check the deterministic typed semantic surface emitted by the real primary compiler. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { createSourceAdapter } from "../src/source-adapter.mjs";
import { retainedReferenceFor, scaleRange, scaledEncounter } from "../src/book.mjs";

const ROOT = new URL("../", import.meta.url);
const PROJECTION_PATH = new URL("data/encounter-facts-v0.111.0.json", ROOT);
const ALIASES_PATH = new URL("tools/primary-semantic-aliases-v0.111.0.json", ROOT);
const OUTPUT_PATH = new URL("data/primary-semantic-surface-v0.111.0.json", ROOT);
const IDLE = Object.freeze({ status: "idle", encounterId: null, monsterIds: [], source: null, releaseInfo: null });

function sha256(bytes) { return createHash("sha256").update(bytes).digest("hex"); }
function canonicalModelId(monsterId) {
  return typeof monsterId === "string" && monsterId ? `MONSTER.${monsterId}` : null;
}
function nameOf(body) {
  if (body?.name?.kind === "localizedText") return body.name.text;
  if (body?.name?.kind === "localizedTemplate") return body.name.template;
  return null;
}
function typedRange(range) {
  return Number.isSafeInteger(range?.minimum) && Number.isSafeInteger(range?.maximum)
    ? { minimum: range.minimum, maximum: range.maximum } : null;
}
function integerAtAscension(expression, ascension) {
  if (expression?.kind === "constant" && Number.isSafeInteger(expression.value)) return expression.value;
  if (expression?.kind === "convert") return integerAtAscension(expression.expression, ascension);
  if (expression?.kind === "ascensionSelect") {
    return integerAtAscension(ascension >= expression.threshold ? expression.atOrAbove : expression.below, ascension);
  }
  return null;
}
function belowA8Range(hp) {
  const expression = hp?.expression;
  if (expression?.kind !== "range") return null;
  const minimum = integerAtAscension(expression.minimum, 0), maximum = integerAtAscension(expression.maximum, 0);
  return Number.isSafeInteger(minimum) && Number.isSafeInteger(maximum) ? { minimum, maximum } : null;
}
function formatRange(range) {
  return range && (range.minimum === range.maximum ? String(range.minimum) : `${range.minimum}–${range.maximum}`);
}
function exactSourceModels(encounter, referenceBody) {
  const explicit = canonicalModelId(referenceBody.monsterId);
  const byId = encounter.monsters.filter((body) => body.canonicalModel === explicit);
  if (byId.length === 1) return [byId[0].canonicalModel];
  if (byId.length > 1) throw new Error(`${encounter.canonicalId}/${referenceBody.displayName}: duplicate canonical model join`);
  const byName = encounter.monsters.filter((body) => nameOf(body) === referenceBody.displayName);
  if (byName.length === 1) return [byName[0].canonicalModel];
  return [];
}
function checkedAliasIndex(aliasDocument) {
  assert.equal(aliasDocument.schemaVersion, 1, "primary semantic alias schema drift");
  assert.equal(aliasDocument.reviewedForVersion, "v0.111.0", "primary semantic aliases are stale");
  assert.equal(aliasDocument.aliases.length, 6, "primary semantic alias count drift");
  const result = new Map();
  for (const row of aliasDocument.aliases) {
    assert.ok(row.rationale.length >= 20, "semantic alias lacks review rationale");
    const key = `${row.encounterId}\0${row.retainedMonsterId}\0${row.retainedDisplayName}`;
    assert.ok(!result.has(key), `duplicate semantic alias ${key}`);
    result.set(key, row);
  }
  return result;
}
function checkedAlias(aliases, encounterId, referenceBody) {
  return aliases.get(`${encounterId}\0${referenceBody.monsterId}\0${referenceBody.displayName}`) ?? null;
}
function legacyRows(payload) {
  const result = new Map();
  for (const lane of ["current", "archive"]) for (const encounter of payload.legacyAnnotations[lane]) {
    for (const body of encounter.presentationBodies) result.set(body.factId, body);
  }
  return result;
}
function startingPowerTokens(value, canonicalTitles) {
  if (value === null || value === undefined) return [];
  const result = [];
  for (const rawToken of String(value).split(/[;,]/)) {
    const token = rawToken.trim();
    if (!token) continue;
    const amountMatch = /^(.*\S)\s+(-?\d+)$/.exec(token);
    const titleText = amountMatch ? amountMatch[1] : token;
    const amount = amountMatch ? Number(amountMatch[2]) : null;
    const segmentations = [];
    function segment(remaining, titles) {
      if (!remaining) {
        segmentations.push(titles);
        return;
      }
      for (const title of canonicalTitles) {
        if (remaining === title) segment("", [...titles, title]);
        else if (remaining.startsWith(`${title} `)) segment(remaining.slice(title.length + 1), [...titles, title]);
        if (segmentations.length > 1) return;
      }
    }
    segment(titleText, []);
    assert.equal(segmentations.length, 1,
      `starting Power token has no unique exact canonical-title segmentation: ${JSON.stringify(token)}`);
    const titles = segmentations[0];
    for (const [index, title] of titles.entries()) {
      const row = { title };
      if (amount !== null && index === titles.length - 1) row.amount = amount;
      result.push(row);
    }
  }
  return result;
}
function comparisonIndex(payload) {
  const result = new Map();
  for (const row of payload.laneComparisons) {
    for (const side of [row.left, row.right]) {
      const rows = result.get(side.factId) ?? [];
      rows.push(row.comparisonId);
      result.set(side.factId, rows);
    }
  }
  return result;
}
function retainedBodyRows(encounter, otherEncounter, primary, legacyByFact, comparisons, aliases, usedAliases, players, canonicalPowerTitles) {
  const retainedRaw = retainedReferenceFor(encounter.canonicalId);
  const reference = encounter.reference?.record ?? scaledEncounter(retainedRaw, { players });
  const otherReference = otherEncounter.reference?.record ?? scaledEncounter(retainedRaw, { players: 2 });
  if (!reference) return [];
  return reference.lineup.map((body, bodyOrdinal) => {
    const legacyFactId = `LEGACY.BODY.${encounter.canonicalId}.${bodyOrdinal}`;
    const legacy = legacyByFact.get(legacyFactId) ?? { annotations: body };
    const rawRetainedBody = retainedRaw?.lineup?.[bodyOrdinal] ?? null;
    const retainedBelowA8 = legacy.annotations.hpBelowA8 ?? rawRetainedBody?.hpBelowA8 ?? null;
    assert.ok(Array.isArray(retainedBelowA8) && [1, 2].includes(retainedBelowA8.length)
      && retainedBelowA8.every((value) => Number.isSafeInteger(value) && value > 0),
    `${legacyFactId} has no exact retained below-A8 HP range`);
    if (Array.isArray(rawRetainedBody?.hpBelowA8)) {
      assert.deepEqual(retainedBelowA8, rawRetainedBody.hpBelowA8, `${legacyFactId} retained below-A8 HP drift`);
    }
    assert.ok(body.retainedProvenance, `${legacyFactId} has no retained generator provenance`);
    if (legacyByFact.has(legacyFactId)) {
      assert.deepEqual(legacy.annotations.retainedProvenance, body.retainedProvenance, `${legacyFactId} provenance drift`);
    }
    const alias = checkedAlias(aliases, encounter.canonicalId, body);
    const exactModels = exactSourceModels(encounter, body);
    if (alias && exactModels.length) throw new Error(`${legacyFactId} has a redundant reviewed alias`);
    if (alias) usedAliases.add(`${alias.encounterId}\0${alias.retainedMonsterId}\0${alias.retainedDisplayName}`);
    const sourceModels = exactModels.length ? exactModels : alias ? [alias.canonicalModel] : [];
    if (!sourceModels.length) throw new Error(`${legacyFactId} has no exact source model or reviewed alias`);
    if (!encounter.monsters.some((candidate) => candidate.canonicalModel === sourceModels[0])) {
      throw new Error(`${legacyFactId} reviewed alias source model is outside its exact encounter`);
    }
    const exactOrdinalCard = primary.bodies[bodyOrdinal]?.name === body.displayName
      ? [{ card: primary.bodies[bodyOrdinal], primaryBodyOrdinal: bodyOrdinal }] : [];
    const cards = exactOrdinalCard.length ? exactOrdinalCard : primary.bodies
      .map((card, primaryBodyOrdinal) => ({ card, primaryBodyOrdinal }))
      .filter(({ card }) => card.name === body.displayName);
    if (!cards.length) throw new Error(`${legacyFactId} has no exact-name primary card`);
    if (!exactOrdinalCard.length && cards.length > 1) throw new Error(`${legacyFactId} has ambiguous variable primary cards`);
    return {
      retainedBodyOrdinal: bodyOrdinal,
      legacyFactId,
      comparisonIds: [...(comparisons.get(legacyFactId) ?? [])].sort(),
      displayName: body.displayName,
      type: legacy.annotations.type ?? body.type ?? null,
      hpBelowA8: { minimum: retainedBelowA8[0], maximum: retainedBelowA8.at(-1) },
      hpBelowA8Authority: "retained-wiki-reference",
      hpA8SinglePlayer: Array.isArray(body.hpA8)
        ? { minimum: body.hpA8[0], maximum: body.hpA8.at(-1) } : null,
      startsWithA9: body.startsWithA9 ?? null,
      startingPowerTokens: {
        atA9: startingPowerTokens(body.startsWithA9, canonicalPowerTitles),
        configuredByPlayers: [
          { players: 1, tokens: startingPowerTokens(body.startsWith, canonicalPowerTitles) },
          { players: 2, tokens: startingPowerTokens(otherReference?.lineup?.[bodyOrdinal]?.startsWith, canonicalPowerTitles) },
        ],
      },
      count: body.count,
      role: body.role ?? "encounter-body",
      initialRole: cards.some(({ card }) => card.initial === true) ? "initial-or-possible" : "non-initial",
      sourceModels,
      stateId: alias?.stateId ?? null,
      provenance: body.retainedProvenance,
      primaryBodyOrdinals: cards.map(({ primaryBodyOrdinal }) => primaryBodyOrdinal),
    };
  });
}
function primaryRows(encounter, players) {
  const primary = encounter.presentation.primary;
  assert.ok(primary, `${encounter.canonicalId}/${players}P has null primary`);
  const reference = encounter.reference?.record;
  return {
    players,
    header: primary.header,
    roster: primary.roster ?? null,
    bodies: primary.bodies.map((card, primaryBodyOrdinal) => {
      const retainedBody = reference?.lineup?.[card.bodyIndex] ?? null;
      const namedMatches = encounter.monsters.filter((body) => nameOf(body) === card.name);
      const idMatches = retainedBody
        ? encounter.monsters.filter((body) => body.canonicalModel === canonicalModelId(retainedBody.monsterId)) : [];
      const sourceBody = namedMatches.length === 1 ? namedMatches[0] : idMatches.length === 1 ? idMatches[0] : null;
      const sourceBase = typedRange(sourceBody?.hp?.a8SinglePlayer);
      const retainedBase = Array.isArray(retainedBody?.hpA8)
        ? { minimum: retainedBody.hpA8[0], maximum: retainedBody.hpA8.at(-1) } : null;
      const base = sourceBase ?? retainedBase;
      const configuredValues = base && reference
        ? scaleRange(base.minimum === base.maximum ? [base.minimum] : [base.minimum, base.maximum], {
            players, act: reference.actNumber, kind: reference.kind,
          }) : null;
      let configured = configuredValues
        ? { minimum: configuredValues[0], maximum: configuredValues.at(-1) } : null;
      if (!configured && encounter.kind === "event" && /^\d+$/.test(card.hp)) {
        const eventHp = Number(card.hp);
        assert.ok(Number.isSafeInteger(eventHp) && eventHp > 0, `${encounter.canonicalId}/${players}P event HP is invalid`);
        configured = { minimum: eventHp, maximum: eventHp };
      }
      if (configured) {
        assert.equal(card.hp, formatRange(configured), `${encounter.canonicalId}/${players}P/${card.name} typed HP does not match primary`);
      }
      return {
        primaryBodyOrdinal,
        bodyIndex: card.bodyIndex,
        displayName: card.name,
        role: card.role,
        initial: card.initial,
        sourceMatchedExactly: card.sourceMatchedExactly,
        sourceOnlySupplement: card.sourceOnlySupplement === true,
        sourceModel: sourceBody?.canonicalModel ?? null,
        hp: { a8SinglePlayer: base, configured, authority: sourceBase ? "checked-source" : "retained-fallback" },
        startingStateShown: typeof card.setup === "string" && card.setup.startsWith("Starts with"),
      };
    }),
  };
}

export function buildSurface(projection, projectionBytes, aliasDocument, aliasBytes) {
  const payload = projection.payload;
  const canonicalPowerTitles = [...new Set(payload.sourceFacts.models.powers.map((row) => row.englishTitle))].sort();
  assert.ok(canonicalPowerTitles.length > 0 && canonicalPowerTitles.every((title) => typeof title === "string" && title),
    "canonical Power title inventory is empty or malformed");
  const legacyByFact = legacyRows(payload), comparisons = comparisonIndex(payload);
  const aliases = checkedAliasIndex(aliasDocument), usedAliases = new Set();
  const adapters = new Map([1, 2].map((players) => [players, createSourceAdapter({ projection, players })]));
  for (const [players, adapter] of adapters) assert.equal(adapter.available, true, `${players}P adapter: ${adapter.error}`);
  const canonicalIds = adapters.get(1).canonicalIds;
  assert.deepEqual(adapters.get(2).canonicalIds, canonicalIds, "1P/2P encounter census drift");
  assert.equal(canonicalIds.length, 89, "primary semantic encounter census drift");
  const encounters = canonicalIds.map((canonicalId) => {
    const views = new Map([...adapters].map(([players, adapter]) => [players, adapter.view(IDLE, canonicalId).encounter]));
    const encounter = views.get(1);
    const sourceModels = encounter.monsters.map((body, sourceBodyOrdinal) => ({
      sourceBodyOrdinal,
      canonicalModel: body.canonicalModel,
      factId: body.factId,
      displayName: nameOf(body),
      hp: { ...body.hp, belowA8: belowA8Range(body.hp) },
      states: body.states,
      initialState: body.initialState.map((fact) => ({ factId: fact.factId, effect: fact.effect, baseValue: fact.baseValue, runtimeInputs: fact.runtimeInputs })),
      rosterRole: encounter.roster.possibleInitialBodies.includes(body.canonicalModel) ? "possible-initial"
        : encounter.production?.producedBodies?.includes(body.canonicalModel) ? "produced" : "encounter-related",
    }));
    const primaryByPlayers = [...views].map(([players, row]) => primaryRows(row, players));
    return {
      canonicalId,
      factId: encounter.factId,
      title: encounter.title,
      kind: encounter.kind,
      placement: encounter.placement,
      roster: encounter.roster,
      production: encounter.production,
      sourceModels,
      retainedBodies: retainedBodyRows(encounter, views.get(2), encounter.presentation.primary, legacyByFact, comparisons, aliases, usedAliases, 1, canonicalPowerTitles),
      primaryByPlayers,
    };
  });
  assert.deepEqual([...usedAliases].sort(), [...aliases.keys()].sort(), "reviewed semantic aliases are unused");
  return {
    schemaVersion: 1,
    target: { version: "v0.111.0", branch: "public-beta" },
    authority: {
      status: "typed-primary-compiler-semantic-surface",
      rendererTextMatching: false,
      statement: "Generated through the checked adapter and real primary compiler; typed source/reference coordinates are retained without substring classification.",
    },
    inputs: [
      { path: "data/encounter-facts-v0.111.0.json", bytes: projectionBytes.length, sha256: sha256(projectionBytes) },
      { path: "tools/primary-semantic-aliases-v0.111.0.json", bytes: aliasBytes.length, sha256: sha256(aliasBytes) },
    ],
    summary: {
      encounterCount: encounters.length,
      ordinaryCount: encounters.filter((row) => row.kind === "ordinary").length,
      eventCount: encounters.filter((row) => row.kind === "event").length,
      nonNullOnePlayerPrimaries: encounters.filter((row) => row.primaryByPlayers[0]).length,
      nonNullTwoPlayerPrimaries: encounters.filter((row) => row.primaryByPlayers[1]).length,
    },
    encounters,
  };
}

function main() {
  const projectionBytes = readFileSync(PROJECTION_PATH);
  const projection = JSON.parse(projectionBytes);
  const aliasBytes = readFileSync(ALIASES_PATH);
  const aliases = JSON.parse(aliasBytes);
  const actual = `${JSON.stringify(buildSurface(projection, projectionBytes, aliases, aliasBytes), null, 2)}\n`;
  if (process.argv.includes("--check")) assert.equal(readFileSync(OUTPUT_PATH, "utf8"), actual, "primary semantic surface drifted");
  else writeFileSync(OUTPUT_PATH, actual);
  console.log(`${process.argv.includes("--check") ? "verified byte-identical" : "wrote"} data/primary-semantic-surface-v0.111.0.json (${Buffer.byteLength(actual)} bytes)`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
