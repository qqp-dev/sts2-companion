# Decision projection contract

> **Status:** reconciled contract for the single practical phone guide, shipped
> static editorial callouts, and future live frames. `/sts2` consumes the checked compact projection
> through one validated adapter. Its collapsed surface renders
> effect-first static combat mechanics; exact technical records remain in native
> disclosure. Current observation has encounter lifecycle/identity only, plus the
> final completed-room encounter/model IDs. It does **not** observe a live turn,
> HP, Block, Powers, intents, move history, counters, hand/deck, target, model
> state/phase, realized lineup, timer, or survivors. Two independently qualified
> static-conditional editorial records currently ship; other encounters honestly
> retain zero records and create no empty callout section.

This contract defines a practical static combat guide as the primary projection
of an authoritative decoded combat blueprint, with an additive evidence-gated
collection of useful human **thinking windows**. Normative words apply to the
current practical guide where implemented and to future callout/live-frame work as
labeled. Examples are fixtures, not captured gameplay or observed outcomes.

## 1. Problem and non-goals

The E1 compact projection is compact for storage and audit. It still asks a
reader to interpret roster ASTs, typed expressions, move operations, behavior
graphs, applicability, evidence, and authority machinery. A decision surface has
a different job: expose the few consequences and counterfactual breakpoints that
can change a choice within a declared horizon.

A practical static combat guide can honestly explain rules and conditions, but
cannot by itself justify a present-tense imperative. Whether a fact matters
depends on the realized lineup and state, current HP/Block/Powers, move history,
ordered hooks, hidden/random branches, available interventions, and the horizon.
For example, an on-death replacement rule may dominate a lethal-damage decision
but be irrelevant to a pure Block threshold; a Frail application matters before
a later defense window but not after the fight ends. Listing every move is too
large, while choosing one move without state turns possibility into prediction.
Static material supplies encounter grammar and source-backed conditional
mechanics; it never supplies a missing current temporal cut.

This design therefore separates:

1. a safe **practical encounter guide** when only static authority is available; and
2. a future live **decision frame** when authoritative rules can be joined to a
   sufficiently complete, time-stamped observation.

### Non-goals

The projection is not:

- a card-line recommendation, optimizer, autoplay API, static enemy role label,
  or context-free target tier list. It MAY compare target-removal scenarios,
  prove horizon-qualified mechanical dominance, or apply an explicit
  user-selected policy; that is useful tactical analysis, not permission to hide
  preference weights or claim a universal best target;
- a claim that live turn prediction is implementable from current observations;
- a new source extractor or a replacement for the checked source/evidence
  artifacts;
- permission to flatten formulas, operation order, conditions, random branches,
  follow-ups, must-once flags, targets, runtime inputs, or lifecycle rules;
- permission to merge `sourceFacts`, time-stamped `observedFacts`, and
  `legacyAnnotations`, or to pick a winner in an unresolved conflict;
- a probability estimator when exact choice weights, eligibility, and relevant
  history are not all known;
- a static time-to-kill estimate. Fight-level race output requires an explicit
  player policy and closed production/lifecycle semantics; otherwise expanded
  detail retains clocks, windows, and removal deltas instead; or
- a change to `/sts2`, its state reader, source migration artifacts, or the
  C1/C2/C3 cutover plan.

## 2. Cognitive budget and information hierarchy

The game screen is external memory. The HUD SHOULD NOT repeat visible HP, hand,
energy, Block, intent, or Power rows merely to look complete. `NOW` repeats an
observed value only when the value is needed to understand a derived threshold,
resolve ambiguity, establish freshness, or identify a less-visible state.

### Tactical callout collection and individual-card budget

The practical static combat guide is the primary product. Tactical callouts are
an additive **evidence-gated collection with cardinality `0..N`**. The reducer
MUST independently evaluate every candidate and MUST retain every distinct
candidate that passes. It MUST NOT use scarcity, a per-fight quota, enemy count,
lack of live observation, or available screen rows as an eligibility gate.

Each candidate is evaluated on all seven gates:

1. the player can control the named choice;
2. the mechanic is non-obvious enough to merit a callout;
3. the consequence is materially useful;
4. the claim is robust across ordinary states covered by its condition;
5. checked source facts support it;
6. its causal chain can be explained from cited facts; and
7. it is distinct from other passing candidates.

A callout MUST carry `factRefs`, `conditionRefs`, and `causalRefs`. A
`static-conditional` callout may say “if/when X, choosing Y causes Z” without a
live observation. A `live-imperative` such as “do Y now” additionally requires a
fresh current-state observation and exact observation refs. Missing runtime
inputs suppress only unsupported present-tense imperatives or affected clauses;
they do not suppress a source-backed conditional mechanic.

Source-confirmed phase control is eligible when the record names the
player-controllable choice, the exact phase/turn mechanism, how that choice keeps
multi-enemy attacks staggered, and the synchronized spike it avoids. It MUST NOT
guess the encounter, phase, or mechanism. The extractor remains editorially
neutral and does not manufacture these records.

A collapsed phone view MAY rank and show a subset. It MUST show the total passing
count and provide one expansion path to all passing records. Ranking is stable
and presentation-only; it MUST NOT delete or demote a passing record out of the
collection. Distinctness deduplication may combine records only when they declare
the same semantic `distinctnessKey`; the retained/duplicate IDs remain auditable.

Each **individual card**, not the collection, has this cognitive budget:

1. one headline or conditional mechanic;
2. one short causal/effect line; and
3. optionally one short condition/flip line.

Thus each individual card has at most three visible text rows, one primary
horizon, two consequence coordinates, one alternative, and one visible
condition. Additional conditions, frontier rows, operations, and proof stay in
that card's expansion. These per-card limits never cap the number of candidate
cards. Enemy move titles/IDs, full operation lists, audit refs, and repeated HUD
state stay out of collapsed cards but remain in exact detail.

An empty collection is honest only when zero distinct candidates pass the seven
evidence gates (or all otherwise-passing live imperatives lack their required
observation). It is not a target count and MUST NOT cause filler. Conversely,
lack of live turn observation alone never suppresses source-backed static
conditional callouts.

### Deterministic independent evaluation, deduplication, and ranking

The reducer performs these operations without a collection quota:

1. **Validate support.** Reject malformed records, lane conflation, absent basis
   refs, and unsupported present-tense language.
2. **Evaluate independently.** Record pass/fail for each of the seven gates. One
   candidate's score or presence cannot make another candidate fail.
3. **Apply observation language.** Preserve static conditional records without
   live state. Reject a live imperative unless all required current observation
   refs are present and fresh.
4. **Deduplicate by declared semantics.** Group only exact
   `distinctnessKey` duplicates and retain an audit mapping.
5. **Rank stably.** Sort passing distinct records by declared rank and stable ID.
   Rank determines collapsed order, not collection membership.
6. **Render transparently.** Return all passing records, `total`, the collapsed
   subset/count, and `hasMore`/expand state.

Safety-critical contradictions remain explicit `UNKNOWN` callouts when their own
record passes the gates and cites the contradiction. A multi-enemy encounter does
not itself imply `FOCUS`; a focus or phase-control callout must establish its
actual causal mechanism and conditions.

### Internal query taxonomy and expanded model

The six questions remain the internal reducer taxonomy and tap-through expansion
model. They describe what the rigorous frame can answer, not what must render at
once:

| Query | Question answered | Expanded content |
|---|---|---|
| `NOW` | What observation cut makes these claims valid? | Required observation context, parameters, freshness, and state ambiguity. Absent in a static guide. |
| `IN` | What happens before I can decide again under the baseline? | Source-ordered raw/net threat and non-damage consequences, including cards, Powers, summons, state, and lifecycle. |
| `BREAK` | Which counterfactual boundary changes that result? | Kill, Block, strip, or interrupt thresholds and consequence deltas; decision-sensitive multi-enemy states may supply a `FOCUS` removal frontier. These are mechanical levers and scenarios, not presumed card lines. |
| `OUT/NEXT` | Where does the baseline leave the fight, and what follows? | Post-turn deltas and the next consequence envelope, expressed as effect signatures with conditions or branch structure. |
| `CLOCK` | Which timer/window changes the fight? | Escalation, phase, spawn, escape, revive, recurrence, and expiring opportunity clocks. |
| `?` | What unresolved fact could change a decision? | Hidden, stale, random, conflicting, unsupported, or unobserved inputs, named rather than guessed. |

The unit of human thought is an **effect signature**, not a move name. An effect
signature states the target, amount and hit structure, ordered status/card/Power/
state/lifecycle effects, and their timing and conditions. It is the canonical
human projection for both current and future enemy consequences.

The collapsed guide MUST NOT display raw move IDs. Localized move names MAY and
normally SHOULD appear when they are useful recognition anchors, but the effect
signature remains the practical content; a name never substitutes for missing
semantics. If a checked numeric getter remains symbolic, the renderer uses the
exact retained encounter/body/move value when one exists, labels it as
wiki/reference-backed, and keeps the symbolic expression in Technical audit. It
MUST NOT label that fallback as source-closed or obtain it through fuzzy matching.

Information is progressively disclosed:

1. **Primary practical combat guide:** compact practical placement, configured
   HP/kind, recognized move/effect rows, explicit numbered phases or honest
   opener/cycle/branch/response labels, transitions, repeat cues, and only
   encounter-distinct actionable rules. Exact retained values fill symbolic
   checked coordinates with quiet provenance.
2. **Collapsed tactical collection:** a ranked subset of passing callouts with an
   explicit total count and expansion path. It may be empty but is never the
   primary guide surface.
3. **Expanded decision/fight view:** every passing callout plus the six query
   families, complete frontiers, clocks, conditions, and persistent costs.
4. **Exact detail and audit:** ordered operations, formulas, missing inputs,
   rule/input refs, untouched lane facts, conflicts, and evidence pointers.

Suppression at a higher level is view compression only. Every displayed callout
MUST link to exact support, and every passing callout MUST remain reachable.
Omission MUST NOT delete, rewrite, or silently discard a lower-level record.

## 3. The current guide and future decision projection

### 3.1 Practical combat guide: honest static degradation

An `EncounterCapsule` is parameterized encounter grammar. It may contain:

- initial roster structure and cardinality, retaining dependent/random choices;
- possible and produced membership as separate concepts;
- proven behavior cycles, forks, follow-ups, and conditional starts;
- known spawn, death, revive, escape, recurrence, and phase rules;
- escalation formulas or clocks whose static inputs close; and
- explicit live inputs and source families still required for prediction.

A capsule MUST NOT use `NOW`, `IN`, “current,” “this turn,” “will,” or any other
wording that implies a realized temporal state. A model identity is not a
state/phase; roster possibility is not a realized lineup; produced is not
co-present; a summon operation is not a complete summon lifecycle. Static
conditions remain conditions and static branches remain sets.

The checked adapter record is useful now because E1 can support identity,
placement, roster structure, applicability, move operations, and behavior paths
within its declared coverage. The guide must still state affected gaps plainly,
including initial-state/Power coverage, event behavior, HP rounding conflict, and
broader lifecycle families. Exact authority annotations remain inside Technical
audit and may not close an authoritative gap. The canonical `/sts2` document is a
practical static combat guide, not a live `DecisionFrame` or present-tense
tactical observer.

### 3.2 Decision frame: future live product

A `DecisionFrame` is a temporal, horizon-bounded reduction of:

- authoritative rules for an exact game build and parameter context;
- time-stamped observations at a declared observation cut; and
- the complete belief set of states consistent with both.

The compiler simulates bounded traces from that belief set, groups traces only
when their player-relevant consequences are equivalent, compares them with an
explicit baseline, and renders only decision-sensitive differences. A frame is
valid only for its observation cut, authority manifest, parameters, and horizon.
It is replaced—not patched by assumption—when any of those change.

The turn baseline is named **END NOW** and means: **take no further player
actions after the observation cut**. Already observed actions and effects remain
in state. END NOW is a counterfactual reference point, not advice to end the
turn. This definition avoids an implicit “typical play” policy and makes every
`BREAK` delta auditable.

If an observation cannot identify a required state, affected results remain a
set, conditional, range, or unknown. Unsupported “do it now” language is
suppressed. The primary practical guide and any independently qualifying
source-backed static conditional callouts remain available and are labeled
`STATIC`, never made to look current. Safety-critical observation failures may
produce their own evidence-backed `UNKNOWN` callout.

## 4. What matters at each horizon

### Turn horizon

The default turn horizon ends at the **next player decision**. It includes every
closed, ordered consequence between the observation cut and that point:

- attacks and HP loss, preserving hit count and target;
- Block gain/loss and mitigation in source order;
- Power application/removal and duration;
- card creation, draw, discard, Exhaust, deck mutation, and hand constraints;
- spawn, death, transform, revive, escape, phase, and encounter completion;
- automatic hooks before, between, or after move operations; and
- branch eligibility/history that changes any of the above.

`raw threat` is incoming damage at the authority-defined pre-mitigation boundary;
`net threat` is predicted HP loss after all closed observed mitigation and hooks
in source order. If the source boundary/order or an input is unresolved, the
compiler MUST show a conditional/set/range/unknown shape rather than invent a
number.

END NOW is simulated first. `BREAK` then reports minimal counterfactual state or
effect boundaries that change the consequence vector, for example:

- deal at least *N* effective damage before an acting body resolves its move;
- gain at least *N* effective Block to cross a net-HP-loss boundary;
- remove/strip a specific Power before its relevant hook; or
- trigger a source-defined interrupt/phase boundary before an operation.

A threshold is “actionable” only as a mechanical lever. If hand, energy, target
legality, or action timing is not observed, `availability` is `unknown`; the
surface MUST NOT imply the player can reach it. It reports deltas (“net HP loss
18 → 0”), never normative text (“play a Block card”). A lethal threshold is not
allowed to say “cancels the intent” until removal, death hooks, replacement,
phase transition, survivor, and encounter-completion consequences are closed.

### Fight horizon

The fight expansion answers questions that can change planning across turns:

- escalation race and caps;
- phase, spawn, escape, revive, and recurrence clocks;
- windows to interrupt, strip, split, or safely remove a body;
- removal consequences, including replacement bodies and encounter completion;
- persistent or irreversible HP, deck, card, gold, Power, or resource costs; and
- conditions under which the next consequence envelope changes.

It prefers clocks/windows/removal deltas to a speculative TTK. A TTK or race in
turn counts is permitted only when a named player policy, its input observations,
and all relevant enemy production/lifecycle behavior are explicit. “Assume
average damage” and hidden default inputs are forbidden.

### Multi-enemy focus: counterfactual removal frontier

In a realized multi-enemy state, the highest-utility question is often “who, if
anyone, should be removed first?” The projection answers with a
**counterfactual removal frontier**, never a static role label or context-free
priority. It compares auditable scenario consequences from the same belief state
and observation cut. `remove A first`, `remove B first`, `do not split`, and
`no-focus` are scenario names, not presumed card recommendations.

A focus analysis exists only when all of the following hold:

- at least two targetable enemy bodies or removable states are realized, not
  merely possible or produced by the encounter grammar;
- at least two removal/non-removal scenarios are legal or their feasibility is a
  decision-changing unknown; and
- their consequence deltas, costs, windows, feasibility, or truth gaps differ
  under the relevance predicate.

Otherwise `FOCUS` is omitted. Omission means “not decision-sensitive at this
cut,” not “all targets are equivalent.”

#### Baseline and horizons

Every frontier starts from the frame's exact belief state and **END NOW**
baseline. It declares each boundary, rather than relying on a bare turn number:

- `H1` normally ends at the next player decision and supplies **NOW**, the
  current-turn consequence removed or triggered by the earliest cut;
- `H2` and `H3` may mean end of enemy turn 2/3, but only when that boundary and
  turn owner are explicit; and
- `HN` names an explicit ordinal/boundary, encounter completion, or the next
  forced event. It never means “eventually.”

For horizons beyond the next decision, the baseline and every counterfactual use
the same declared continuation/intervention policy and player-throughput inputs.
`END NOW at every player decision` is a legal, explicit causal baseline;
“typical play” and assumed average damage are not. If future player choices or
throughput can change a delta and no policy closes them, affected `H2/H3/HN`
coordinates remain a branch set or unknown. Optional utility profiles such as
`survival-first` or `minimize deck pollution` must be user-selected, named, and
shown; there is no hidden default profile.

#### A removal cut is a lifecycle cut

Removal MUST NOT be modeled as `HP = 0` or as naïve subtraction. A legal
`RemovalCut` identifies:

1. the exact candidate body/state and intervention class;
2. the earliest source-legal insertion boundary, such as before a creature's
   operation, after an atomic hit, or after an interrupt;
3. the lethal, control, state-exit, or encounter-completion operation;
4. every ordered on-damage, between-hit, death, revive, replacement, phase,
   survivor, summon, cross-body, and encounter-completion hook it triggers; and
5. the settled boundary after those hooks at which the body/state is actually
   absent, transformed, replaced, revived, or the encounter has completed.

“Before act” is valid only if the declared intervention can reach a legal cut
before that operation. A source-atomic multi-hit cannot be interrupted between
hits unless authoritative rules permit it. A revive or replacement may require
more than one removal event; invulnerability, Block, forced overkill, control
immunity, and replacement bodies contribute to the cut's cost rather than
silently disappearing. When any affected lifecycle edge, timing rule, or current
state is unresolved, the row says `removal delta unknown`; it does not infer that
a lethal threshold cancels an effect or ends the encounter.

#### Scenario deltas and row vocabulary

For each candidate first-removal order/cut and each declared non-removal policy,
the compiler pairs a counterfactual trace with the same baseline branch and
reports **deltas**, not raw totals. The full vector contains at least:

- per-player cumulative HP loss, lethal margin, and hostile damage prevented by
  each horizon, retaining target and hit structure;
- Block, healing, buffs/debuffs, scaling, and Power changes for every enemy;
- generated/status cards by card identity, destination zone, count, and rotation,
  plus draw/hand/discard/Exhaust/deck mutation;
- summons, body count, revive/replacement/transform/phase state, and encounter
  completion;
- cross-enemy control and state transitions such as one death stunning,
  enraging, healing, transforming, or summoning another body;
- persistent/irreversible HP, deck, resource, and production costs; and
- the effective damage, control, timing, and resource requirements of reaching
  the settled removal cut.

A tap-through target row is a projection of that vector and answers:

- **NOW:** what current-turn consequence disappears or is triggered at the cut;
- **H2/H3/HN:** cumulative typed deltas by each selected horizon;
- **LINK:** effects on other bodies and encounter completion;
- **COST:** the full removal requirement, including Block, invulnerability,
  revive/replacement, control immunity, overkill, and resource use;
- **WINDOW:** how the delta or cost expires, grows, or changes when the cut is
  delayed to later legal boundaries; and
- **TRUTH:** the observation, RNG, lifecycle, formula, player-throughput, or
  source gap that could change the comparison.

This vocabulary belongs to the expanded frontier. The collapsed card selects at
most one horizon and two consequence coordinates from it; it never renders these
columns or one row per target.

“Effective HP” may be rendered as a scalar only when all cost components reduce
to closed damage under the declared cut. Otherwise the cost remains a typed
vector. Impact and feasibility are separate: a large hypothetical delta is not
an actionable focus conclusion when its cut is unreachable. Such a row is
marked `unreachable` or `feasibility unknown` and excluded from a feasible
frontier, while its impact may remain visible when that distinction matters.

#### Dominance, Pareto tradeoffs, and no focus

The frame declares the horizon set, feasible scenario set, and a partial outcome
ordering (for example, minimize per-player HP loss and hostile status cards;
maximize lethal margin). It assigns no cross-coordinate scalar weights.
Scenario A **mechanically dominates** B only when lifecycle and inputs are closed
enough to prove, for every retained correlated branch through those horizons,
that A is no worse on every declared coordinate (including cost) and better on
at least one. Incomparable state transitions, an unresolved coordinate, an
unpaired branch, or an unknown feasibility result blocks a dominance claim.
Dominance is therefore horizon- and assumption-qualified, never a universal
“best enemy” label. A static `threat / HP`, role, or additive priority scalar is
forbidden: deadlines and removal thresholds are discontinuous, while death
links, survivor rules, branch correlations, and lifecycle transitions are
non-additive.

When no scenario dominates, expanded detail preserves the complete **Pareto
frontier**. The collapsed card may show only the selected pair as `A ↔ B`, with
one differentiating coordinate per candidate; all other rows and policy details
remain behind the tap. An expanded view may explain “survival-first favors A” or
“clean deck favors B” only after applying the visibly named user-selected
policy. Without that policy it says `no strict winner`, not `best target`.

A `no-focus` result is also first-class. It is emitted when a declared feasible
AoE, setup, defense, split-damage, or waiting scenario mechanically dominates
all immediate first-removal scenarios through the selected horizons, or when no
removal cut is reachable. A nondominated non-removal scenario may instead appear
as a tradeoff row; its presence alone does not justify the stronger `no-focus`
conclusion. `do not split` is likewise an explicit allocation scenario whose
cost and throughput are declared, not generic advice.

### Relevance predicate

A fact or trace distinction becomes eligible for collapsed-card selection only
when, before the declared horizon, it:

1. changes a player-relevant consequence;
2. crosses a relevant HP, Block, lethal, hand-size, energy, or other mechanical
   threshold;
3. creates, advances, expires, or changes an important clock/window;
4. creates a persistent or irreversible cost; or
5. changes what removal of a body/state does.

The consequence vector is ordered and at minimum spans effect target, amount
and hit count, per-creature HP/Block, Powers, card zones/deck mutation,
summons/bodies, model state/phase, timing/conditions, and lifecycle/encounter
status. Implementations may add typed coordinates, but MUST NOT merge traces that
differ on any relevant coordinate. Distinct moves may coalesce only when their
full relevant consequence vectors are equivalent through the declared horizon.
Equal names or intents never justify coalescing, and different names do not
prevent coalescing when that complete equivalence actually holds.

## 5. Future typed `DecisionFrame` contract

This is a small logical JSON contract, not a claim about a current endpoint. A
production schema may split objects for transport, but MUST retain these
semantics.

### Core types

```text
Label = "observed" | "source-certain" | "source-conditional" |
        "source-random" | "derived" | "unknown"

Lane = "sourceFacts" | "observedFacts" | "legacyAnnotations"

Value<T> =
  { "shape": "exact",       "value": T } |
  { "shape": "range",       "minimum": T, "maximum": T } |
  { "shape": "set",         "values": T[] } |
  { "shape": "conditional", "cases": Case<T>[] } |
  { "shape": "unknown",     "missingInputs": string[] }

Support = {
  "ruleRefs": string[],      // source/legacy rules used
  "inputRefs": string[],     // time-stamped observation/parameter facts used
  "laneRefs": { "lane": Lane, "refs": string[] }[]
}

Claim<T> = {
  "claimId": string,
  "labels": Label[],
  "value": Value<T>,
  "support": Support         // mandatory when labels contains "derived"
}

Target = { "side": "player" | "enemy", "selection": string,
           "entityId": string | null }
Timing = { "relativeToDecision": string, "phase": string }
Condition = { "expression": string, "missingInputs": string[] }
EffectNumber = Value<number>  // exact, range, set, conditional, or unknown

OrderedEffect =
  { "kind": "damage", "target": Target,
    "amountPerHit": EffectNumber, "hitCount": Value<integer>,
    "timing": Timing, "condition": Condition | null } |
  { "kind": "block", "target": Target, "amount": EffectNumber,
    "timing": Timing, "condition": Condition | null } |
  { "kind": "power", "operation": "apply" | "remove" | "modify",
    "target": Target, "powerId": string, "stacks": EffectNumber | null,
    "duration": EffectNumber | null,
    "timing": Timing, "condition": Condition | null } |
  { "kind": "card", "operation": string, "target": Target,
    "cardId": string | null, "count": Value<integer>,
    "fromZone": string | null, "toZone": string | null,
    "timing": Timing, "condition": Condition | null } |
  { "kind": "state" | "lifecycle", "operation": string, "target": Target,
    "stateId": string | null, "count": Value<integer> | null,
    "timing": Timing, "condition": Condition | null }

EffectSignature = {
  "orderedEffects": OrderedEffect[]
}

ConsequenceEnvelope = {
  "branches": { "condition": Condition | null,
                "signature": EffectSignature }[]
}

HorizonSpec = {
  "horizonId": "H1" | "H2" | "H3" | "HN" | string,
  "boundary": string,         // exact phase/event boundary, never "eventually"
  "ordinal": integer | null
}

EntityStateRef = { "entityId": string, "stateId": string | null }

PolicySpec = {
  "policyId": string,
  "description": string,
  "selectedBy": "mechanical-baseline" | "user",
  "throughput": Value<Throughput>,
  "assumptions": string[]
}

RemovalCut = {
  "candidate": EntityStateRef,
  "interventionClass": string,
  "interventionBoundary": Timing,
  "triggeringOperation": string,
  "settledBoundary": Timing,
  "orderedLifecycleEffects": EffectSignature,
  "result": "absent" | "state-exited" | "transformed" | "replaced" |
            "revived" | "encounter-complete",
  "orderingConstraints": string[]
}

// Unless named otherwise, each *Delta is scenario minus paired END NOW baseline.
FocusDelta = {
  "playerHpLossDelta": { "playerId": string, "value": EffectNumber }[],
  "lethalMarginDelta": { "playerId": string, "value": EffectNumber }[],
  "hostileDamagePrevented": EffectNumber, // baseline minus scenario; positive prevents
  "enemyStateDeltas": { "entityId": string, "coordinate":
      "block" | "heal" | "buff" | "debuff" | "scaling" | "power",
      "effect": OrderedEffect }[],
  "cardDeltas": { "cardId": string | null, "zone": string,
      "countDelta": Value<integer>, "perRotationDelta": Value<number> | null }[],
  "bodyAndLifecycleDeltas": { "coordinate":
      "summons" | "body-count" | "revives" | "replacements" |
      "transforms" | "phase" | "encounter-completion",
      "value": Value<number | string | boolean> }[],
  "crossEnemyEffects": OrderedEffect[],
  "persistentCostDeltas": { "resource": string, "zone": string | null,
                             "value": EffectNumber }[]
}

RemovalCost = {
  "effectiveDamageRequired": EffectNumber,
  "absorbedByBlock": EffectNumber,
  "forcedOverkill": EffectNumber,
  "invulnerabilityWindows": Value<integer>,
  "controlRequired": OrderedEffect[],
  "resourceRequirements": { "resource": string, "value": EffectNumber }[],
  "removalEventsRequired": Value<integer> // includes revive/replacement chain
}

Feasibility = {
  "status": "reachable" | "unreachable" | "unknown",
  "byBoundary": Timing,
  "throughputPolicyRef": string,
  "missingInputs": string[]
}

RemovalWindow = {
  "earliestCut": Timing,
  "delayedCuts": { "boundary": Timing,
                    "deltaFromEarliest": Value<FocusDelta> }[],
  "expiresAt": Timing | null,
  "trend": "grows" | "shrinks" | "mixed" | "flat" | "unknown"
}

RemovalScenario = {
  "scenarioId": string,
  "kind": "remove-first" | "do-not-split" | "aoe" | "setup" |
          "defense" | "split-damage" | "wait",
  "removalOrder": EntityStateRef[],
  "cut": Claim<RemovalCut> | null,
  "deltas": { "horizonId": string, "delta": Claim<FocusDelta> }[],
  "links": Claim<OrderedEffect[]>[],
  "cost": Claim<RemovalCost>,
  "window": Claim<RemovalWindow>,
  "feasibility": Claim<Feasibility>,
  "truth": Claim<string>[]
}

OutcomeOrdering = {
  "coordinate": string,
  "direction": "minimize" | "maximize" | "partial-order",
  "rule": string
}

FocusComparison = {
  "kind": "dominance" | "pareto" | "no-focus" | "unknown",
  "horizonIds": string[],
  "feasibleScenarioIds": string[],
  "dominanceEdges": { "dominant": string, "dominated": string }[],
  "nondominatedScenarioIds": string[],
  "policyConclusion": null | {
    "policyId": string, "selectedBy": "user", "scenarioId": string
  },
  "reason": string
}

FocusFrontier = {
  "baselineClaimIds": string[],
  "horizons": HorizonSpec[],
  "continuationPolicy": PolicySpec,
  "outcomeOrdering": OutcomeOrdering[], // partial order; no scalar weights
  "scenarios": RemovalScenario[],
  "comparison": Claim<FocusComparison>
}

DecisionFrame = {
  "schemaVersion": integer,
  "kind": "decision-frame",
  "context": {
    "authorityVersion": string,
    "encounterId": string,
    "parameters": { "ascension": integer, "playerCount": integer,
                    "actId": string, "roomClass": string },
    "observedAt": RFC3339 timestamp,
    "observationSequence": integer,
    "horizon": "next-player-decision"
  },
  "observation": { "facts": ObservedFact[],
                   "auditMetadata": AuditMetadata[],
                   "omittedVisibleFacts": string[] },
  "belief": { "shape": "singleton" | "finite-set" | "symbolic",
              "unresolved": string[] },
  "baseline": Claim<ConsequenceVector>,
  "breakpoints": Breakpoint[],
  "focus": FocusFrontier | null, // only for decision-sensitive realized lineups
  "next": Claim<ConsequenceEnvelope>,
  "clocks": Claim<Clock>[],
  "unknowns": Claim<string>[]
}
```

Ranges may be used only when intermediate values are all possible and
correlation does not matter. Otherwise a set of tuples or conditional cases is
required. This applies especially to a `FocusDelta`: correlated HP loss, card,
body, and cross-enemy results stay together in the outer `Claim` branch rather
than becoming independent coordinate ranges. `probability` is intentionally
absent from the base branch type; a
probability field is legal only in the closed-weight case described in
[Uncertainty and provenance](#8-uncertainty-provenance-and-fail-closed-rules).

### Small illustrative JSON

The following is a **fictional future fixture**. No current reader emits these
observations. Its exact A9 damage is deliberately supported by
`legacyAnnotations`, not relabeled as source authority; E2 formula and Stock
lifecycle closure would be required for an authoritative equivalent.

```json
{
  "schemaVersion": 1,
  "kind": "decision-frame",
  "context": {
    "authorityVersion": "v0.111.0",
    "encounterId": "ENCOUNTER.AXEBOTS_NORMAL",
    "parameters": {
      "ascension": 9,
      "playerCount": 1,
      "actId": "ACT.GLORY",
      "roomClass": "monster"
    },
    "observedAt": "2030-01-01T00:00:00.000Z",
    "observationSequence": 42,
    "horizon": "next-player-decision"
  },
  "observation": {
    "facts": [
      { "ref": "OBS.FIXTURE.PLAYER.HP", "path": "player.hp", "value": 50 },
      { "ref": "OBS.FIXTURE.PLAYER.BLOCK", "path": "player.block", "value": 0 },
      { "ref": "OBS.FIXTURE.AXEBOT.HP", "path": "axebot.hp", "value": 17 },
      { "ref": "OBS.FIXTURE.AXEBOT.BLOCK", "path": "axebot.block", "value": 0 },
      { "ref": "OBS.FIXTURE.AXEBOT.STOCK", "path": "axebot.powers.stock", "value": 2 }
    ],
    "auditMetadata": [
      { "ref": "OBS.FIXTURE.AXEBOT.ACTION_ID", "kind": "enemy-action-id", "value": "HAMMER_UPPERCUT_MOVE" }
    ],
    "omittedVisibleFacts": ["hand", "energy"]
  },
  "belief": {
    "shape": "symbolic",
    "unresolved": ["axebotRespawnCount", "Stock ordered lifecycle hooks"]
  },
  "baseline": {
    "claimId": "FRAME.FIXTURE.BASELINE.END_NOW",
    "labels": ["derived"],
    "value": {
      "shape": "exact",
      "value": {
        "counterfactual": "END_NOW",
        "signature": {
          "orderedEffects": [
            {
              "kind": "damage",
              "target": { "side": "player", "selection": "single", "entityId": "player" },
              "amountPerHit": { "shape": "exact", "value": 18 },
              "hitCount": { "shape": "exact", "value": 1 },
              "timing": { "relativeToDecision": "before-next", "phase": "current enemy resolution" },
              "condition": null
            },
            {
              "kind": "power", "operation": "apply",
              "target": { "side": "player", "selection": "single", "entityId": "player" },
              "powerId": "POWER.WEAK", "stacks": { "shape": "exact", "value": 2 }, "duration": null,
              "timing": { "relativeToDecision": "before-next", "phase": "after damage" },
              "condition": null
            },
            {
              "kind": "power", "operation": "apply",
              "target": { "side": "player", "selection": "single", "entityId": "player" },
              "powerId": "POWER.FRAIL", "stacks": { "shape": "exact", "value": 2 }, "duration": null,
              "timing": { "relativeToDecision": "before-next", "phase": "after Weak" },
              "condition": null
            }
          ]
        },
        "rawThreat": { "shape": "exact", "value": 18 },
        "netThreat": { "shape": "exact", "value": 18 },
        "playerHpDelta": { "shape": "exact", "value": -18 }
      }
    },
    "support": {
      "ruleRefs": [
        "SOURCE.MOVE.MONSTER.AXEBOT.HAMMER_UPPERCUT_MOVE",
        "LEGACY.BODY.AXEBOTS_NORMAL.0"
      ],
      "inputRefs": [
        "OBS.FIXTURE.PLAYER.HP",
        "OBS.FIXTURE.PLAYER.BLOCK",
        "OBS.FIXTURE.AXEBOT.ACTION_ID"
      ],
      "laneRefs": [
        { "lane": "sourceFacts", "refs": ["SOURCE.MOVE.MONSTER.AXEBOT.HAMMER_UPPERCUT_MOVE"] },
        { "lane": "legacyAnnotations", "refs": ["LEGACY.BODY.AXEBOTS_NORMAL.0"] },
        { "lane": "observedFacts", "refs": ["OBS.FIXTURE.PLAYER.HP", "OBS.FIXTURE.PLAYER.BLOCK", "OBS.FIXTURE.AXEBOT.ACTION_ID"] }
      ]
    }
  },
  "breakpoints": [
    {
      "lever": "block",
      "threshold": { "shape": "exact", "value": 18 },
      "availability": "unknown",
      "delta": { "netThreat": -18, "playerHpDelta": 18 },
      "labels": ["derived"],
      "support": {
        "ruleRefs": ["SOURCE.MOVE.MONSTER.AXEBOT.HAMMER_UPPERCUT_MOVE", "LEGACY.BODY.AXEBOTS_NORMAL.0"],
        "inputRefs": ["OBS.FIXTURE.PLAYER.BLOCK"],
        "laneRefs": [
          { "lane": "sourceFacts", "refs": ["SOURCE.MOVE.MONSTER.AXEBOT.HAMMER_UPPERCUT_MOVE"] },
          { "lane": "legacyAnnotations", "refs": ["LEGACY.BODY.AXEBOTS_NORMAL.0"] },
          { "lane": "observedFacts", "refs": ["OBS.FIXTURE.PLAYER.BLOCK"] }
        ]
      }
    },
    {
      "lever": "kill",
      "threshold": { "shape": "exact", "value": 17 },
      "availability": "unknown",
      "delta": { "shape": "unknown", "missingInputs": ["Stock ordered lifecycle hooks", "respawn state"] },
      "labels": ["derived", "unknown"],
      "support": {
        "ruleRefs": ["SOURCE.STATE_RULES", "UNKNOWN.BROADER_WORLD_MODEL"],
        "inputRefs": ["OBS.FIXTURE.AXEBOT.HP", "OBS.FIXTURE.AXEBOT.BLOCK", "OBS.FIXTURE.AXEBOT.STOCK"],
        "laneRefs": [
          { "lane": "sourceFacts", "refs": ["SOURCE.STATE_RULES"] },
          { "lane": "observedFacts", "refs": ["OBS.FIXTURE.AXEBOT.HP", "OBS.FIXTURE.AXEBOT.BLOCK", "OBS.FIXTURE.AXEBOT.STOCK"] }
        ]
      }
    }
  ],
  "focus": null,
  "next": {
    "claimId": "FRAME.FIXTURE.NEXT",
    "labels": ["derived"],
    "value": {
      "shape": "exact",
      "value": {
        "branches": [
          {
            "condition": null,
            "signature": {
              "orderedEffects": [
                {
                  "kind": "damage",
                  "target": { "side": "player", "selection": "single", "entityId": "player" },
                  "amountPerHit": { "shape": "exact", "value": 11 },
                  "hitCount": { "shape": "exact", "value": 2 },
                  "timing": { "relativeToDecision": "after-next", "phase": "next enemy resolution" },
                  "condition": null
                }
              ]
            }
          }
        ]
      }
    },
    "support": {
      "ruleRefs": ["SOURCE.GRAPH.AXEBOT", "LEGACY.BODY.AXEBOTS_NORMAL.0"],
      "inputRefs": ["OBS.FIXTURE.AXEBOT.ACTION_ID"],
      "laneRefs": [
        { "lane": "sourceFacts", "refs": ["SOURCE.GRAPH.AXEBOT"] },
        { "lane": "legacyAnnotations", "refs": ["LEGACY.BODY.AXEBOTS_NORMAL.0"] },
        { "lane": "observedFacts", "refs": ["OBS.FIXTURE.AXEBOT.ACTION_ID"] }
      ]
    }
  },
  "clocks": [
    {
      "claimId": "FRAME.FIXTURE.CLOCK.STOCK",
      "labels": ["observed", "unknown"],
      "value": { "shape": "unknown", "missingInputs": ["Stock trigger/production/lifecycle semantics"] },
      "support": { "ruleRefs": [], "inputRefs": ["OBS.FIXTURE.AXEBOT.STOCK"], "laneRefs": [{ "lane": "observedFacts", "refs": ["OBS.FIXTURE.AXEBOT.STOCK"] }] }
    }
  ],
  "unknowns": [
    {
      "claimId": "FRAME.FIXTURE.UNKNOWN.STOCK",
      "labels": ["unknown"],
      "value": { "shape": "exact", "value": "Kill/removal delta is gated on authoritative Stock and respawn lifecycle." },
      "support": { "ruleRefs": ["UNKNOWN.INITIAL_STATES", "UNKNOWN.BROADER_WORLD_MODEL"], "inputRefs": [], "laneRefs": [] }
    }
  ]
}
```

The example's `derived` next claim projects the unconditional graph edge as the
effect signature `player: 11×2`: graph sequence is supported by `sourceFacts`,
while the exact A9 amount is visibly supported by `legacyAnnotations`. A fully
source-authoritative amount still waits for E2 formula closure. The action ID in
`auditMetadata` and the source rule refs exist only to join and disambiguate the
trace in exact detail; neither is human explanation or collapsed content.
`derived` says that the baseline, threshold, or next envelope was computed—it
does not assign confidence or upgrade its inputs.

## 6. Phone DSL

The renderer is a projection of the typed claims, not a second inference engine.
The collapsed card has no source/lane badges. Tap-through MUST expose full labels
and lane refs.

### Static capsule available from the current knowledge boundary

This Axebot capsule is illustrative **primary static mechanics detail** that can
be built offline. It does not predict a current branch. Lack of live observation
forbids present-tense imperatives, but it does not suppress independently
qualified static conditional callouts; all use effect signatures and explicit
conditions:

```text
CAPSULE Axebot · Glory regular · A9/1P params · NOT LIVE
ROSTER  1 Axebot [source-certain]
OPEN    {you: 18 → Weak 2 → Frail 2 | self: 15 Block → Strength 4/8}; chooser not closed [source-conditional; values=legacyAnnotations:A9]
CYCLE   self:[15 Block → Strength 4/8] → you:[18 → Weak 2 → Frail 2] ↔ you:11×2 [sequence=source-certain; values=legacyAnnotations:A9]
CLOCK   max HP = base +10×respawnCount (0..2, pre-MP) [source-certain formula]
?       Stock trigger/timing/removal and turn state unknown [unknown]
```

The two graph initials and cycle are present in `SOURCE.GRAPH.AXEBOT`. E1's
Axebot state rule proves the cumulative `10 × axebotRespawnCount` maximum-HP
bonus before multiplayer scaling. It does not by itself prove that Stock starts
at 2, how its hooks order death/replacement, or the full spawn lifecycle. The A9
numbers and detailed Stock prose above are visibly from the legacy annotation
lane. They are useful reference material, not authoritative lifecycle closure.

### Future live micro-card, using the fictional JSON fixture

The fictional frame above contains all six internal query families. The default
surface selects only the answer that changes the immediate action class. For a
Block breakpoint that answer is two rows:

```text
BLOCK 18
0 HP loss · Weak/Frail remain
```

No `NOW`, baseline, next envelope, clock, source label, or general unknown row is
added merely because the frame contains one. Tapping the card opens those typed
claims and their support. If the Stock lifecycle instead becomes the material
fact blocking the current decision, the selected card fails closed:

```text
UNKNOWN
Stock removal effect unresolved
```

### Future multi-enemy `FOCUS` micro-cards

These are separate fictional cards, never simultaneous cards and never one card
per enemy. `A`, `B`, and `C` are compact observed target locators, not move names.
Each card uses one primary horizon at most; tapping anywhere opens the complete
`NOW/H2/H3/HN · LINK · COST · WINDOW · TRUTH` frontier and support refs.

Strict dominance has no runner-up:

```text
FOCUS A
−28 dmg by T2 · kill 34
```

A nondominated pair uses one differentiating coordinate per candidate:

```text
A ↔ B
A: −28 dmg · B: −6 Wounds
```

A non-removal result is an answer, not a synthetic target:

```text
NO FOCUS
defend survives · no kill reachable
```

Incomplete lifecycle authority fails closed without a caveat catalog:

```text
UNKNOWN
C death effect unresolved
```

### Tap-through `FOCUS` detail (never collapsed)

The rich frontier is retained exactly behind the card. For example, tapping the
tradeoff above may open this matrix; it MUST NOT appear on the collapsed surface:

```text
FOCUS DETAIL · H2=end enemy turn 2 · feasible cuts only
remove A before act → −28 team dmg by H2; +0 statuses; cost 34 effective HP
remove B by H2       → −6 team dmg; −6 Wounds to draw pile/rotation; cost 19 effective HP
LINK remove C → stun A next turn
no strict winner · user policy: survival-first favors A; clean-deck favors B
```

The policy conclusions appear only when those profiles were explicitly selected.
Without one, the final detail line stops at `no strict winner`. Exact detail
retains `remove A first`, `remove B first`, every other frontier candidate, and
any decision-sensitive `do not split` allocation as separate scenarios, with
per-player lethal margin, future Block/heal/scaling, body count, persistent
resource deltas, legal settled cuts, observation/policy inputs, and source/lane
support. None of these rows names an enemy move; move IDs/titles remain audit-only
join metadata.

## 7. Compiler and reducer pipeline

The pipeline is deterministic for a fixed authority manifest, observation set,
parameters, horizons, continuation/utility policy, throughput inputs, reducer
version, and renderer version.

### 7.1 Ingest and gate lanes

1. Validate the exact checked authority manifest and declared source-family
   readiness.
2. Load `sourceFacts`, `observedFacts`, and `legacyAnnotations` into separate
   stores. Never object-spread, coalesce, or apply lane precedence.
3. Retain conflicts and known unknowns as first-class inputs.
4. Bind ascension, player count, act, room class, game version, and mod/build
   identity explicitly. An absent parameter remains an input dimension; there
   is no product-wide default hidden in the compiler.

`legacyAnnotations` may produce visibly legacy reference prose. It MUST NOT
satisfy a source-required gate or turn a derived claim into source certainty.

### 7.2 Normalize the observation cut

1. Validate every observed wire identity against the exact source-derived
   adapter vocabulary; matching is case-sensitive with no fuzzy aliases.
2. Record `observedAt`, observation sequence/order, observer source, and temporal
   scope for every fact or atomic observation batch.
3. Separate encounter/model identity from state/phase and distinguish active
   observations from final completed-room history.
4. Reject mixed cuts that cannot be ordered. Do not carry a stale intent, HP,
   Power, or survivor forward by assumption.

`matchingPolicy.prefixStripping:false` applies inside the source observation-ID
domain: projection consumers MUST NOT strip a prefix to make an unrecognized
source identity match. The existing state reader has a separate, stable wire
boundary: `parseSave` converts an exact saved `MONSTER.*` wire ID to its
unprefixed state model-ID representation. The source adapter first validates
every checked projection mapping row, then applies that same pure reader
conversion to the row's exact `observedId` to build a collision-checked secondary
index. Looking up an already-normalized reader ID through that index is a
representation bridge, not projection prefix stripping, an alias, or fuzzy
matching. Output retains the reader ID, checked wire ID, and canonical model.

Today this stage can identify encounter lifecycle and model IDs only within the
limits described at the top of this document. It therefore routes to a capsule,
not a decision frame.

### 7.3 Construct the belief set

Define the belief set as all states satisfying authoritative static rules,
parameter bindings, and non-conflicting observed facts at the observation cut:

```text
B = { s | sourceRules(s, parameters) ∧ observedFacts(s, observedAt) }
```

This is constraint construction, not best-guess state estimation. Hidden state
stays symbolic or expands to a finite set. Correlation is retained. Random and
conditional choices retain eligibility/history. Realized lineup exists only
when observed or logically forced; possible/produced membership is never used as
co-presence. A summon operation does not imply successful creation, slot,
survival, timing, or later behavior beyond extracted rules.

If `B` is empty, observations and authority are inconsistent. Emit an explicit
contradiction and no predictions. If it is too large to enumerate, preserve a
symbolic belief set rather than sampling or selecting a representative state.

### 7.4 Close typed inputs

For every relevant operation or hook:

1. resolve its exact typed expression against parameters, state variables,
   source fields, and combat queries;
2. evaluate only when every required input, conversion, rounding mode, target,
   and operation order is closed; and
3. otherwise retain the normalized condition, correlated set/range, or unknown
   shape and name the missing inputs.

No UI-friendly scalar may replace an unresolved formula. In particular,
multiplayer HP rounding remains unresolved until the authoritative runtime chain
closes the current conflict.

### 7.5 Simulate bounded ordered traces

Simulate from each belief state through the declared horizon. Preserve:

- operation source order and hook order;
- target and hit count;
- conditions and false/true branches;
- random branches and exact eligibility/history;
- follow-ups and must-once flags;
- card-zone and persistent state changes;
- body/model/state/phase identity; and
- production, death, revive, escape, recurrence, survivor, and encounter
  lifecycle.

The default turn bound stops at the next player decision. A fight bound must be
explicit and must stop at an unresolved lifecycle edge rather than treating the
edge as a no-op. Counterfactual interventions may enter only at source-legal
operation boundaries; a removal trace continues through its complete ordered
lifecycle to the settled cut before projection. Trace-count/depth exhaustion
produces a named truncation unknown; it never silently drops branches.

### 7.6 Project consequence vectors and aggregate

Project each trace to an ordered player-relevant consequence vector. Distinct
moves may be grouped only when their full relevant consequence vectors are
equivalent through the declared horizon, including target, per-hit amount, hit
count, ordering, non-damage effects, timing/conditions, state transitions,
clock/window/removal behavior, and compatible displayed provenance. Equal names
or intents never justify coalescing. Grouping by title, intent icon, final damage
alone, or coincidentally equal HP is invalid; a different title alone also cannot
prevent otherwise valid full-vector coalescing.

A grouped branch retains the underlying trace/rule refs and unresolved branch
conditions. Exact branch probability may be attached only after the probability
closure rules below pass.

### 7.7 Reduce against END NOW

1. Simulate END NOW as the baseline.
2. Compute consequence deltas for mechanical counterfactual levers, not every
   possible card/action sequence.
3. Find threshold boundaries at which the consequence vector changes.
4. Mark feasibility `known`, `impossible`, or `unknown` only from observed hand,
   energy, target/timing legality, and authoritative action semantics.
5. Remove dominated duplicate breakpoints while retaining any distinct
   consequence, clock, persistence, or removal behavior.

The reducer does not choose a breakpoint through hidden utility. “Kill,”
“Block,” “strip,” and “interrupt” are counterfactual dimensions, not card
recommendations; a later focus comparison may still prove mechanical dominance
between their fully simulated removal scenarios.

### 7.8 Build the counterfactual removal frontier

This stage runs only for a realized decision-sensitive multi-enemy belief state:

1. Reuse the exact observation cut, belief set, END NOW baseline, authority
   manifest, and parameter bindings. Declare precise `H1/H2/H3/HN` boundaries,
   continuation policy, throughput inputs, feasibility set, and partial outcome
   ordering.
2. Enumerate each currently removable enemy body/state and only those candidate
   first-removal orders, `do-not-split` allocations, and non-removal intervention
   classes that can change a relevant coordinate. This bounds mechanical
   scenarios; it does not enumerate card sequences.
3. Locate the earliest legal intervention boundary for each candidate. Simulate
   the triggering operation and all on-damage, death, control, cross-body,
   replacement, survivor, phase, summon, and encounter-completion hooks until the
   cut settles. Never implement the cut by mutating HP directly.
4. Pair every counterfactual with its END NOW baseline branch and carry the same
   exogenous random choice/history where authoritative coupling permits. If the
   intervention changes eligibility or branch topology, retain the resulting
   correlated conditional/set structure; do not force a pair, take independent
   extrema, or manufacture a probability.
5. At every selected horizon project the paired delta across per-player HP loss
   and lethal margin, hostile damage, enemy Block/heal/Powers/scaling,
   card identity/zone/rotation, summons/body count, state/lifecycle/completion,
   cross-enemy effects, and persistent costs.
6. Compute removal cost and timing separately from value. Include current and
   generated Block, invulnerability, control immunity, required overkill,
   revive/replacement chains, resources, target legality, and observed or
   policy-declared throughput. Mark the cut `reachable`, `unreachable`, or
   `unknown` without promoting hypothetical impact to actionable value.
7. Re-simulate later legal cuts needed to establish `WINDOW`; do not extrapolate
   linear damage or status rates across a deadline, phase, or branch boundary.
8. Compare only feasible scenarios. Prove a dominance edge branch-wise over all
   declared coordinates/horizons or retain the nondominated Pareto rows. Apply a
   utility conclusion only from a visible user-selected policy. Emit `no-focus`
   or `unknown` only under the rules above.

Every scenario delta, cut, cost, link, window, feasibility result, and comparison
is a derived claim with exact rule/input/lane support. Candidate/action IDs and
titles remain exact-detail join metadata and cannot become focus explanations.

### 7.9 Apply the relevance predicate

Apply the five tests in [Relevance predicate](#relevance-predicate). Relevance is
state- and horizon-dependent and must be recomputed after every observation cut.
Facts used only to establish a displayed derivation remain available in its
tap-through support even if they are not rendered as their own row.

### 7.10 Compile the `0..N` collection and retain audit paths

Apply the seven gates in [Tactical callout collection and individual-card
budget](#tactical-callout-collection-and-individual-card-budget) independently to
every candidate. Validate language and basis refs, reject unsupported records,
deduplicate only exact declared semantic duplicates, and rank every remaining
record stably. Return all passing records; never stop after the first pass.

The collapsed renderer may show a ranked subset only while displaying `total`
and an expand control that reaches every passing record. The three-row,
one-horizon, two-coordinate, one-alternative, and one-condition limits apply to
each individual card, not to collection cardinality. Complete horizon/target
matrices remain per-card tap-through.

The renderer may abbreviate effect notation, but cannot calculate new outcomes,
scalarize a frontier, hide material unknowns behind a positive conclusion,
introduce enemy move titles as causal explanation, or change labels. Every
callout links to exact fact, condition, causal, lane, and observation refs as
applicable. Conflicts link to both sides; raw facts are the final audit layer.

### Collection schema and language contract

A future collection has this normative shape:

```text
CalloutCollection {
  all: Callout[]                 // every passing distinct record, cardinality 0..N
  total: integer                // exactly all.length
  collapsed: Callout[]          // stable prefix/ranked subset only
  collapsedCount: integer       // exactly collapsed.length
  hasMore: boolean              // total > collapsedCount
  expandPath: string | null     // required when hasMore
  rejected: { id, failedGates[] }[]
  deduplicated: { id, duplicateOf, distinctnessKey }[]
}

Callout {
  id: stable ID
  distinctnessKey: stable semantic key
  language: static-conditional | live-imperative
  headline: bounded text
  condition: bounded conditional/current-state statement
  causalBasis: bounded causal statement
  rank: non-negative stable integer
  qualifications: {
    playerControllable, nonObvious, materiallyUseful,
    ordinaryStateRobust, sourceSupported, causallyExplainable, distinct
  }
  basis: { factRefs[1..N], conditionRefs[1..N], causalRefs[1..N] }
  observationRefs: [] | [1..N]  // nonempty for live-imperative
  phaseControl?: {
    controllableChoice, staggeredEffect, synchronizedSpikeAvoided,
    mechanismRefs[1..N]
  }
}
```

Fixtures MUST cover 0, 1, and 3 passing records. The three-record fixture must
prove stable ranking, all-record retention, a visible collapsed total/expand
path, and exact distinctness dedup. Language fixtures must accept a supported
static conditional without live state, reject a live imperative without current
observation refs, accept it with those refs, and retain known runtime gaps only
on affected clauses. A phase-control fixture must cite the controllable choice,
staggering mechanism, avoided synchronization, and causal refs. The zero fixture
must say no source-qualified records passed, never imply a quota.

## 8. Uncertainty, provenance, and fail-closed rules

### Labels are orthogonal

| Label | Meaning |
|---|---|
| `observed` | Directly present in a time-stamped observation at the declared cut. It says nothing about static source certainty. |
| `source-certain` | An unconditional authoritative rule under bound parameters. It does not claim that the rule's state is current. |
| `source-conditional` | An authoritative rule whose condition or required runtime input is not fully selected. Preserve the condition/input in detail; show it collapsed only when selected as the one flip. |
| `source-random` | Multiple source-declared eligible branches remain. It does not imply equal likelihood. |
| `derived` | Computed from cited rules and inputs. This is provenance, not confidence. |
| `unknown` | A missing, stale, conflicting, unsupported, or unclosed fact can affect the claim. Name every gap in detail; the collapsed card may name only its one selected reason. |

A claim may have multiple labels, such as `derived` + `unknown`. Lane identity is
separate from labels. The visible `legacyAnnotations` badge in the examples is a
lane badge, not a seventh certainty label.

Every `derived` claim MUST carry:

- exact rule refs;
- exact observation/parameter input refs;
- lane refs for all supporting facts;
- observation cut and horizon via frame context; and
- trace/reducer refs in detailed output when aggregation occurred.

`observed` does not upgrade a rule, and `source-certain` does not invent current
state. A legacy value participating in arithmetic remains visibly legacy at the
result.

### Branches and probabilities

A structured branch set is the default. A numeric probability is allowed only
when all of the following are authoritative and current:

1. selection semantics and exact branch weights;
2. current eligibility of every branch;
3. move/branch history and must-once/exclusion state;
4. all conditioning state and player-count/ascension parameters; and
5. no unmodeled hook can alter selection before it occurs.

Weights alone are not probabilities. If any item is missing, show eligible
branches with conditions and `source-random`/`unknown`; do not normalize known
weights over an incomplete set, assume uniformity, or use empirical frequency as
source probability.

### Required failure behavior

| Condition | Required output |
|---|---|
| No live turn observation (the current product) | Keep the practical static combat guide primary. Retain supported `static-conditional` callouts; reject only present-tense/live imperatives that require current state. Never emit `NOW`, incoming prediction, or a current threshold without observation refs. |
| Authority manifest/version mismatch or mod ambiguity | No source-derived live frame. A safety-critical card says `UNKNOWN` with one mismatch reason; version detail remains in Technical audit. |
| Missing typed formula input | Preserve conditional/set/range/unknown and list the input; never use zero, midpoint, or legacy default. |
| Unknown numeric/effect semantics | Preserve the known target/order/condition coordinates and mark the unresolved coordinates unknown; MUST NOT fall back to a move ID or title. |
| Unsupported operation/hook/lifecycle | Stop affected traces at that boundary and mark downstream consequences unknown; never treat it as a no-op. |
| Unknown branch condition/eligibility/history | Structured branch set without probability. |
| Source/reference disagreement | A genuinely closed checked source value supersedes the retained fallback; otherwise show the exact retained value. Keep both values, closure state, merge reason, and conflict refs in Technical audit. |
| Stale or unordered observations | Exclude the stale claim or reject the cut; do not carry it forward. |
| Empty belief set | Contradiction diagnostic and no derived prediction. |
| Trace limit reached | Explicit truncated/symbolic remainder; never renormalize surviving traces. |
| Missing state/phase behind a known model ID | Set of possible states or unknown; model ID is not a state alias. |
| Removal lifecycle incomplete | No “kill cancels move/ends fight” claim and no priority/dominance edge; show `removal delta unknown` at the affected cut. |
| Cross-enemy/death/survivor hook unresolved | Preserve the known cut/candidate, stop the paired traces at the hook, and mark `LINK` plus downstream horizons unknown. |
| Future continuation policy or throughput absent | H1 may remain mechanical; affected H2/H3/HN deltas, costs, and feasibility are conditional or unknown, never extrapolated. |
| Hand/energy/target/timing absent | Mechanical impact may remain, but feasibility is `unknown` and the scenario cannot become an actionable dominance conclusion. |
| Removal cut known unreachable | Keep decision-sensitive impact visibly `unreachable`; exclude it from the feasible frontier. |
| Outcome coordinate incomparable or unknown | Preserve Pareto/unknown output; do not emit “best target” or synthesize a scalar score. |

Unknown is not zero damage, “probably no effect,” an empty list, or an enemy
move name presented as explanation. Conditions, targets, hit structure, ordering,
and ranges MUST remain machine-readable through rendering and tap-through. The
failure table governs the rigorous frame and expanded detail; it does not require
a collapsed caveat list. Safety-critical contradiction or staleness selects an
`UNKNOWN` card with one decisive reason. If several material gaps remain, the
card still says `UNKNOWN` and the tap-through lists them all.

## 9. Validation and usability criteria

### Semantic validation

A future implementation is acceptable only when automated fixtures establish:

1. lane objects remain separate and every conflict keeps both refs/values;
2. an input with no live turn observation still produces the practical static guide
   and any qualifying source-backed conditional callouts, while live imperatives
   are rejected and no static text uses current language;
3. END NOW means no further actions from the exact observation cut;
4. ordered operations produce ordered consequences, including between-hit hooks;
5. missing HP/Block suppresses lethal/Block thresholds that require it;
6. Axebot Stock lifecycle gaps suppress the kill/removal delta even when the
   lethal damage threshold itself is known;
7. possible/produced monsters never become observed co-present bodies;
8. model identity never selects a hidden phase/state;
9. distinct actions coalesce only by complete relevant consequence-vector
   equivalence for the declared horizon, never by equal name or intent;
10. an unknown number or effect remains unknown instead of becoming a named-action
    fallback;
11. correlated branches do not become independent numeric ranges;
12. probabilities appear only under the five closure conditions;
13. stale, contradictory, unsupported, and trace-truncated inputs fail closed;
14. every derived claim resolves all rule/input/lane refs;
15. ascension, player count, act, and room parameters alter frames only through
    cited formulas/rules, with no hidden defaults;
16. a focus candidate is drawn only from the realized lineup and its legal cut
    includes atomic-hit boundaries plus all ordered death, replacement, survivor,
    cross-body, and encounter-completion hooks;
17. internal H1/H2/H3/HN focus rows compare paired scenario-minus-baseline deltas
    and retain cumulative per-player HP/lethal, damage, card zone/rotation,
    Power/scaling, body/lifecycle, cross-enemy, and persistent-cost coordinates;
18. a fixture where removing C stuns A changes A's later branch and `LINK`, while
    a revive/replacement fixture charges every required removal event to `COST`;
19. invulnerability, Block, overkill, control immunity, target legality, and
    observed/policy throughput can independently make cost or feasibility differ;
20. delaying a cut across an act, spawn, scaling, or status-production boundary
    recomputes `WINDOW` rather than linearly extrapolating the earliest delta;
21. mechanical dominance appears only for the declared horizons, feasible set,
    partial outcome ordering, and branch-wise closed comparison—never from an
    additive threat/HP score;
22. incomparable reachable scenarios remain a complete Pareto frontier internally;
    “best target” is absent unless dominance is proven or a user-selected policy
    is applied in expanded detail;
23. a declared AoE/setup/defense/split/wait scenario can produce `no-focus` only
    when it dominates every immediate removal scenario, while a nondominated
    non-removal case remains a tradeoff;
24. high hypothetical impact plus unknown/unreachable throughput never becomes an
    actionable focus conclusion;
25. unknown state, formula, branch coupling, lifecycle, or survivor behavior
    blocks only affected deltas/comparisons and retains every truth gap in detail;
    and
26. `FOCUS` is eligible for card selection only for a decision-sensitive realized
    multi-enemy frame; target/action titles cannot affect frontier membership or
    selection, and enemy move IDs/titles never become human explanation.

Closed trace fixtures should be compared with an independently reviewed oracle
or captured deterministic game traces only after the observation and E2 source
contracts permit that comparison. Empirical traces are time-stamped
`observedFacts`, not patches to `sourceFacts`.

### Projection invariants

Schema validation MUST reject unknown value shapes/labels, unlabeled legacy
support, a derived claim without support, probability without closure evidence,
current wording in a capsule, a focus horizon without an exact boundary, a
removal cut without a settled lifecycle boundary, and a dominance/policy
conclusion without its feasibility set, outcome ordering, and policy provenance.
Property tests SHOULD verify that adding a previously unknown belief branch
cannot make the displayed envelope narrower or create a new dominance edge
unless a cited observation/rule excludes that branch. They SHOULD also verify
that every focus delta is paired to the same END NOW baseline cut and that
permuting enemy move titles cannot change grouping, frontier membership,
card selection, or rendered text.

Golden tests SHOULD lock the authoritative reducer, card selector, collapsed
renderer, and expanded renderer separately. A renderer golden cannot substitute
for trace correctness; a correct trace dump cannot substitute for cognitive
usability.

### Collection, selector, and renderer validation

Automated fixtures MUST establish that:

1. collections with 0, 1, and 3 passing records return exactly those cardinalities;
2. each candidate is evaluated on controllability, non-obviousness, material
   usefulness, ordinary-state robustness, source support, causal explanation,
   and distinctness, independent of every other candidate;
3. stable rank and ID ordering affect collapsed order but never remove a passing
   record from `all`;
4. exact semantic duplicates retain a dedup audit mapping, while merely similar
   candidates remain distinct;
5. a collapsed subset exposes `total`, `collapsedCount`, `hasMore`, and an expand
   path whenever records are hidden from the collapsed view;
6. a supported static conditional is accepted without live observation, while a
   live imperative is rejected unless current observation refs are present;
7. every callout has nonempty fact, condition, and causal basis refs;
8. phase-control guidance names and cites the controllable choice, mechanism that
   keeps attacks staggered, and synchronized spike avoided;
9. zero passing candidates yields an honest no-qualified-record outcome rather
   than filler or a target quota; and
10. the practical static combat guide remains available regardless of callout
    cardinality and never implies current HP, intent, phase, or move prediction.

Individual-card renderer fixtures MAY enforce three visible rows, one primary
horizon, two coordinates, one alternative, and one visible condition. Those are
cognitive budgets for one card only. Tests MUST fail any implementation that uses
those limits to discard candidate cards from the collection. Enemy move IDs,
full proof, and full target frontiers remain expansion data, not collapsed causal
prose.

### Phone usability

At a representative narrow phone viewport, without horizontal scrolling, a
player should be able to:

- use the practical static combat guide even when the callout count is zero;
- see the total passing callout count and whether the collapsed subset has more;
- expand once to reach every passing callout and its exact support;
- distinguish static conditions from observed live imperatives;
- understand each displayed condition and causal mechanism without reading enemy
  move titles; and
- never mistake possibility for prediction or a possible roster for simultaneous
  observed bodies.

Usability tests SHOULD measure mechanics comprehension, callout discovery,
condition interpretation, scrolling, and support reachability. A card that
exceeds its individual cognitive budget fails, but multiple independently useful
cards do not fail merely because the collection contains more than one. Extra
terse output is not a defense for silently dropping passing candidates.

## 10. Staged implementation plan

This plan follows source migration gates and does not modify their artifacts or
ownership.

### Current practical combat guide and offline contract work

- `/sts2`, its bounded state payload, and browser client require the checked
  compact projection through one fail-closed adapter. The adapter performs an
  exact-ID best-available presentation merge with the retained guide: checked
  source wins only when closed; otherwise the exact reference value is visible
  with provenance. Raw source/reference authority, symbolic expressions, merge
  reasons, conflicts, and evidence are reachable through Technical audit.
- No alternate HTML product is part of this contract. A projection failure returns
  503 on the guide and its implementation endpoints rather than substituting
  unvalidated community/wiki facts.
- `src/checked-callouts.mjs` is an editorial registry separate from extraction. It
  currently supplies one Axebot Stock replacement `WATCH` record and one
  Decimillipede shared-finish-window `TACTIC` record. Both are static conditional,
  body-addressable, pass all seven gates, and carry fact/condition/causal refs;
  encounters absent from the registry remain honestly empty without filler.
- Additional static conditional records may be added only after independent
  seven-gate review and nonempty exact basis refs. The extractor remains
  editorially neutral.
- Do not expose a live decision frame, current threshold, current intent, or
  present-tense `FOCUS` without the observation gate.

### E2 source gates

Enable reducer features family by family; an unrelated completed family does not
make the whole frame ready.

1. **E2a — ordered initial state and Power hooks:** close starts-with state,
   ordering, and hook semantics needed by initial branches and Powers such as
   Stock. Until then, starts and hook-dependent consequences stay conditional or
   unknown.
2. **E2b — HP chain:** close runtime HP/scaling/rounding and current HP semantics
   before authoritative lethal, removal-cost, and HP-race thresholds.
3. **E2c — event graphs/lifecycle:** enable event encounter traces only for
   covered graphs and lifecycle edges.
4. **E2d — production and lifecycle:** enable spawn/replacement/survivor/removal
   consequences and cross-enemy `LINK` deltas only when the complete
   operation-through-settled-cut chains close.
5. **E2e — remaining formulas/runtime contracts:** enable exact consequence
   arithmetic only for expressions whose runtime inputs and observation
   contracts close.

Each stage adds capability flags at the family/claim level. There is no single
“mostly ready” fallback that guesses uncovered semantics. A focus coordinate may
be enabled only when all source families on both its baseline and counterfactual
traces are green; an unrelated closed damage formula cannot close status-card,
Power, summon, or lifecycle deltas.

### Observation gate for live frames

E2 static authority is necessary but not sufficient. A live `DecisionFrame`
also waits for a reviewed observer contract that supplies an atomic or ordered,
time-stamped cut for every input used by a claim: turn/decision phase, HP, Block,
Powers, intents, move history, counters, hand/deck/resource and target legality
when feasibility matters, model states/phases, bodies/survivors, and relevant
lifecycle events. Horizons, continuation/utility policies, and throughput
assumptions are explicit user/compiler inputs, not facts inferred by the
observer. Partial observation yields partial symbolic claims or a capsule; it
does not trigger state inference from screen conventions or model IDs.

### C1/C2/C3 consumer gates

- **C1 static guide:** render the validated compact checked projection without
  unsupported confidence/probability metrics. It does not compile live frames or
  invent editorial tactics.
- **C2 staged authority UI:** render only claim families whose E2 and observation
  gates are green; a partially green frontier retains typed unknowns and cannot
  become a positive focus conclusion. Exact authority boundaries remain available
  in Technical audit without becoming a second user-facing product.
- **C3/default switch (completed for the static guide):** semantic fixtures,
  phone hierarchy/usability safeguards, version/mismatch behavior, fail-closed
  adapter tests, and reviewed route tests gate the canonical `/sts2` surface.
  Future live-frame or editorial features remain subject to their own gates.

The current encounter lifecycle/identity reader can support guide selection
and version context, not a live turn frame. Adding source authority without live
state improves the guide; adding live state without closed source semantics
still must fail closed. Accurate decision prediction requires both.
