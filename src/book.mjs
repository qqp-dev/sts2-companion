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

// HP and general-buff magnitudes (Reattach, Hardened Shell, Curl Up, Plating, …).
// Durations (Asleep, Slumber) and non-buff counts (Artifact, Thievery) stay stored.
const GENERAL_BUFF = "Vital Spark|Hardened Shell|Personal Hive|Steam Eruption|Curl Up|Reattach|Plating|Shriek|Enrage|Strength|Ritual|Intangible|Thorns|Vigor|Dexterity|Plow";

function scaleNamedBuffs(text, factor) {
  return String(text).replace(
    new RegExp(String.raw`\b(${GENERAL_BUFF})\s+(\d+(?:[-/]\d+)*)\b`, "gi"),
    (_, power, value) => `${power} ${scaleToken(value, factor)}`,
  );
}

/**
 * Convert the source A9 mechanics sentence into its multiplayer rendering.
 * Attack clauses and applied debuff durations remain unchanged. Enemy block
 * scales only by players; gained powers and revive HP use players × actScale.
 * HP-threshold powers written as "Gains PowerName N" (Plow, Vital Spark) scale too.
 */
export function scaleMechanicsText(text, options = {}) {
  const players = Number(options.players ?? 2);
  const general = players * actScale(options);
  const numericPower = new RegExp(
    String.raw`\b(\d+(?:[-/]\d+)*)(\s*(?:\+\s*X\s*)?)\s+(Block|${GENERAL_BUFF})\b`,
    "gi",
  );
  let rendered = String(text ?? "").split(/(?<=\.)\s+/).map((sentence) => {
    const scaleAt = sentence.search(/\b(?:gains?|gained|gaining|gives?|gave|given|adds?|added|adding|starts?|begins?|opens?)\b/i);
    if (scaleAt < 0) return sentence;
    const prefix = sentence.slice(0, scaleAt);
    let mechanics = sentence.slice(scaleAt).replace(numericPower, (_, value, addition, power) => {
      const factor = power.toLowerCase() === "block" ? players : general;
      return `${scaleToken(value, factor)}${addition} ${power}`;
    });
    mechanics = scaleNamedBuffs(mechanics, general);
    return prefix + mechanics;
  }).join(" ");

  // Reattach/revive and explicit produced HP are HP scaling, not attacks.
  rendered = rendered.replace(/\b(Revives? with|Reattaches? with|Hatches? into[^.]*? with)\s+(\d+(?:[-/]\d+)*)\s+HP\b/gi,
    (_, lead, value) => `${lead} ${scaleToken(value, general)} HP`);
  return rendered;
}

function scaledStartsWith(text, options) {
  if (!text) return null;
  const general = Number(options.players ?? 2) * actScale(options);
  return scaleNamedBuffs(text, general);
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
      hpAndBuff: scaling.players * actScale(scaling),
      block: scaling.players,
      attacks: 1,
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
