import { readFileSync } from "node:fs";

const DATA = JSON.parse(readFileSync(new URL("../data/encounters.json", import.meta.url), "utf8"));
const ACT_NUMBER = Object.freeze({ Overgrowth: 1, Underdocks: 1, Hive: 2, Glory: 3 });

export const encounterIds = Object.freeze(Object.keys(DATA.encounters));
export const bookMeta = Object.freeze(DATA.meta);

export function encounterFor(id) {
  const key = String(id ?? "").replace(/^ENCOUNTER\./, "");
  return DATA.encounters[key] ?? null;
}

export function actScale({ act, kind } = {}) {
  const number = typeof act === "number" ? act : ACT_NUMBER[act] ?? 1;
  if (number === 1) return 1.1;
  if (number === 3 && kind === "boss") return 1.3;
  return 1.2;
}

export function scaleRange(range, options = {}) {
  if (!Array.isArray(range)) return null;
  const factor = Number(options.players ?? 2) * actScale(options);
  return range.map((value) => Math.floor(Number(value) * factor));
}

function scaleToken(token, factor) {
  // Hyphen ranges (4-8) and slash alternatives (first-spawn/improved 4/8)
  // each scale independently. Hyphens render as en-dash; slashes stay slashes.
  return String(token)
    .split("/")
    .map((alt) => alt.split("-").map((part) => String(Math.floor(Number(part) * factor))).join("–"))
    .join("/");
}

// A9 already supplies attacks, combat stats, and powers that do not opt in
// to multiplayer scaling. Opt-in powers use their v0.111.0 PowerAmount formula;
// Block and produced HP are separate mechanics with their own formulas.
export const scalingCategories = Object.freeze({
  combatStats: Object.freeze(["Strength", "Dexterity", "Vigor"]),
  block: Object.freeze(["Block"]),
  defaultPowers: Object.freeze(["Curl Up", "Flutter", "Hardened Shell", "Plow", "Rampart", "Reattach", "Regen", "Shriek"]),
  artifact: Object.freeze(["Artifact"]),
  plating: Object.freeze(["Plating"]),
  skittish: Object.freeze(["Skittish"]),
  slippery: Object.freeze(["Slippery"]),
});
const BLOCK = scalingCategories.block.join("|");
const MULTIPLAYER_POWERS = [
  ...scalingCategories.defaultPowers,
  ...scalingCategories.artifact,
  ...scalingCategories.plating,
  ...scalingCategories.skittish,
  ...scalingCategories.slippery,
];
const MULTIPLAYER_POWER_PATTERN = MULTIPLAYER_POWERS.join("|");

function powerFactor(power, options) {
  const name = String(power).toLowerCase();
  const inCategory = (category) => scalingCategories[category].some((candidate) => candidate.toLowerCase() === name);
  if (inCategory("block")) {
    const players = Number(options.players ?? 2);
    return players <= 2 ? players : players * actScale(options);
  }
  if (inCategory("defaultPowers")) return Number(options.players ?? 2) * actScale(options);
  if (inCategory("plating")) return 2 * (Number(options.players ?? 2) - 1) + 1;
  if (inCategory("skittish")) return 1 + 0.5 * (Number(options.players ?? 2) - 1);
  if (inCategory("slippery")) return Number(options.players ?? 2);
  return null;
}

function scalePowerToken(value, power, options) {
  const name = String(power).toLowerCase();
  if (scalingCategories.artifact.some((candidate) => candidate.toLowerCase() === name)) {
    const delta = Number(options.players ?? 2) - 1;
    return String(value)
      .split("/")
      .map((alt) => alt.split("-").map((part) => String(Number(part) + delta)).join("–"))
      .join("/");
  }
  const factor = powerFactor(power, options);
  return factor == null ? String(value) : scaleToken(value, factor);
}

function scaleNamedMultiplayerPowers(text, options) {
  return String(text).replace(
    new RegExp(String.raw`\b(${MULTIPLAYER_POWER_PATTERN})\s+(\d+(?:[-/]\d+)*)\b`, "gi"),
    (_, power, value) => `${power} ${scalePowerToken(value, power, options)}`,
  );
}

/**
 * Convert source A9 mechanics prose into its multiplayer rendering. Attack,
 * debuff-duration, summon/card-count, combat-stat, and non-opt-in power amounts
 * stay source-true. Block uses player count; produced HP and default opt-in
 * powers use players × actScale; special powers use their class formulas.
 */
export function scaleMechanicsText(text, options = {}) {
  const players = Number(options.players ?? 2);
  const hpFactor = players * actScale(options);
  const numericPower = new RegExp(
    String.raw`\b(\d+(?:[-/]\d+)*)(\s*(?:\+\s*X\s*)?)\s+(${BLOCK}|${MULTIPLAYER_POWER_PATTERN})\b`,
    "gi",
  );
  let rendered = String(text ?? "").split(/(?<=\.)\s+/).map((sentence) => {
    const scaleAt = sentence.search(/\b(?:gains?|gained|gaining|gives?|gave|given|adds?|added|adding|starts?|begins?|opens?)\b/i);
    if (scaleAt < 0) return sentence;
    const prefix = sentence.slice(0, scaleAt);
    let mechanics = sentence.slice(scaleAt).replace(numericPower, (_, value, addition, power) => (
      `${scalePowerToken(value, power, options)}${addition} ${power}`
    ));
    mechanics = scaleNamedMultiplayerPowers(mechanics, options);
    return prefix + mechanics;
  }).join(" ");

  // Reattach/revive, explicit produced HP, and Axebot's pre-scaling Max-HP
  // increment use HP scaling rather than a named-power formula.
  rendered = rendered.replace(/\b(Revives? with|Reattaches? with|Hatches? into[^.]*? with)\s+(\d+(?:[-/]\d+)*)\s+HP\b/gi,
    (_, lead, value) => `${lead} ${scaleToken(value, hpFactor)} HP`);
  rendered = rendered.replace(/\+(\d+(?:[-/]\d+)*)\s+Max HP\b/gi,
    (_, value) => `+${scaleToken(value, hpFactor)} Max HP`);

  // Flutter stores the number of hits in descriptive prose rather than the
  // usual "Power N" form. Limit this to sentences that explicitly name it.
  rendered = rendered.split(/(?<=\.)\s+/).map((sentence) => {
    if (!/\bFlutter\b/i.test(sentence)) return sentence;
    return sentence.replace(/\b((?:must be\s+)?hit\s+)(\d+(?:[-/]\d+)*)(\s+times?\b)/gi,
      (_, lead, value, tail) => `${lead}${scaleToken(value, hpFactor)}${tail}`);
  }).join(" ");
  return rendered;
}

function scaledStartsWith(text, options) {
  if (!text) return null;
  const block = new RegExp(String.raw`\b(${BLOCK})\s+(\d+(?:[-/]\d+)*)\b`, "gi");
  return scaleNamedMultiplayerPowers(
    String(text).replace(block, (_, power, value) => `${power} ${scalePowerToken(value, power, options)}`),
    options,
  );
}

function scaledPattern(pattern, options) {
  const source = pattern ?? { type: "unknown", text: "Pattern data is missing from the local book." };
  return { ...source, text: scaleMechanicsText(source.text, options) };
}

export function scaledEncounter(encounter, options = {}) {
  if (!encounter) return null;
  const act = ACT_NUMBER[encounter.act] ?? 1;
  const scaling = { players: Number(options.players ?? 2), act, kind: encounter.kind };
  return {
    known: true,
    name: encounter.name,
    act: encounter.act,
    actNumber: act,
    kind: encounter.kind,
    lineup: encounter.lineup.map((body) => ({
      monsterId: body.monsterId,
      displayName: body.displayName,
      count: body.count,
      role: body.role ?? null,
      pack: body.pack ?? null,
      hpA8: body.hpA8 ?? null,
      hp: scaleRange(body.hpA8, scaling),
      startsWithA9: body.startsWithA9 ?? null,
      startsWith: scaledStartsWith(body.startsWithA9, scaling),
      pattern: scaledPattern(body.pattern, scaling),
      sourcePage: body.sourcePage ?? null,
      sourceFlags: body.sourceFlags ?? [],
      patchChecked: body.patchChecked ?? null,
      moves: (body.moves ?? []).map((move) => ({
        name: move.name,
        intent: move.intent ?? null,
        sourceA9: move.textA9,
        text: scaleMechanicsText(move.textA9, scaling),
      })),
    })),
    rules: (encounter.rules ?? []).map((rule) => scaleMechanicsText(rule, scaling)),
    timing: (encounter.timing ?? []).map((line) => scaleMechanicsText(line, scaling)),
    scale: {
      players: scaling.players,
      hp: scaling.players * actScale(scaling),
      block: scaling.players <= 2 ? scaling.players : scaling.players * actScale(scaling),
      plating: 2 * (scaling.players - 1) + 1,
      artifactDelta: scaling.players - 1,
      skittish: 1 + 0.5 * (scaling.players - 1),
      slippery: scaling.players,
      defaultPowers: scaling.players * actScale(scaling),
      attacks: 1,
      combatStats: 1,
    },
  };
}

export function bookForState(state, options = {}) {
  if (!state?.encounterId) return null;
  const encounter = encounterFor(state.encounterId);
  if (!encounter) {
    return {
      known: false,
      name: state.encounterId,
      act: state.actId ?? null,
      kind: state.roomType ?? null,
      lineup: (state.monsterIds ?? []).map((monsterId) => ({ monsterId, displayName: monsterId, count: 1 })),
      rules: [],
      timing: [],
      scale: null,
    };
  }
  return scaledEncounter(encounter, options);
}
