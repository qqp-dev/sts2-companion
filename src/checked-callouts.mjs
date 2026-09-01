const PASSING = Object.freeze({
  playerControllable: true,
  nonObvious: true,
  materiallyUseful: true,
  ordinaryStateRobust: true,
  sourceSupported: true,
  causallyExplainable: true,
  distinct: true,
});

function candidate(record) {
  return Object.freeze({
    language: "static-conditional",
    qualifications: PASSING,
    ...record,
  });
}

// Editorial records are deliberately separate from source extraction. Each one is
// reviewed claim-by-claim against the compact checked projection and names only a
// static conditional consequence. Encounters absent from this registry get no
// filler callout.
const BY_ENCOUNTER = Object.freeze({
  AXEBOTS_NORMAL: Object.freeze([
    candidate({
      id: "CALLOUT.AXEBOT.STOCK_REPLACEMENT",
      distinctnessKey: "MECHANIC.STOCK_REPLACEMENT_SLOT",
      bodyIndex: 0,
      rank: 10,
      headline: "WATCH · Defeating an Axebot with Stock can refill the same slot",
      condition: "An Axebot actually dies, death was not prevented, and Stock is above 0.",
      causalBasis: "Stock creates a replacement body, then adds it in the defeated owner's same slot; the replacement window keeps the fight open.",
      basis: {
        factRefs: ["SOURCE.LIFECYCLE.CORE.E2D2A", "SOURCE.INITIAL.MONSTER.AXEBOT.AFTERADDEDTOROOM.000.APPLYPOWER"],
        conditionRefs: ["LIFECYCLE.DEATH_PRODUCTION.STOCK.condition"],
        causalRefs: ["LIFECYCLE.DEATH_PRODUCTION.STOCK.orderedEffects", "LIFECYCLE.DEATH_PRODUCTION.STOCK.replacementWindowStopsCombatEnding"],
      },
    }),
  ]),
  DECIMILLIPEDE_ELITE: Object.freeze([
    candidate({
      id: "CALLOUT.DECIMILLIPEDE.SHARED_FINISH_WINDOW",
      distinctnessKey: "MECHANIC.DECIMILLIPEDE_SHARED_FINISH",
      bodyIndex: 0,
      rank: 10,
      headline: "TACTIC · Damage allocation controls the shared finish window",
      condition: "A segment dies while another same-side segment is still alive.",
      causalBasis: "That segment enters a temporary dead state and returns through Reattach if another segment is still alive when its behavior resolves; fatal handling opens only after all other segments are dead.",
      basis: {
        factRefs: ["SOURCE.LIFECYCLE.CORE.E2D2A", "SOURCE.MOVE.MONSTER.DECIMILLIPEDE_SEGMENT.REATTACH_MOVE"],
        conditionRefs: ["LIFECYCLE.TRANSITION.DECIMILLIPEDE.DEAD_STATE.condition", "LIFECYCLE.RETENTION.POWER.REATTACH_POWER.SHOULDOWNERDEATHTRIGGERFATAL.condition"],
        causalRefs: ["LIFECYCLE.TRANSITION.DECIMILLIPEDE.DEAD_STATE.orderedEffects", "LIFECYCLE.TRANSITION.DECIMILLIPEDE.REATTACH.orderedEffects"],
      },
    }),
  ]),
});

export function checkedCalloutCandidates(canonicalEncounterId) {
  return BY_ENCOUNTER[canonicalEncounterId] ?? Object.freeze([]);
}

export const checkedCalloutRegistry = BY_ENCOUNTER;
