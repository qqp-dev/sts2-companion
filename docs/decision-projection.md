# Decision projection contract

> **Status:** design contract for a future source-first consumer. This document
> does not describe current runtime output. The checked E1 projection is static,
> `runtimeReady: false`, and is not imported by the app. Current observation has
> encounter lifecycle/identity only, plus final completed-room encounter, model,
> act, and room IDs. It does **not** observe a live turn, HP, Block, Powers,
> intents, move history, counters, hand/deck, model state/phase, or survivors.
> Stable `/sts2` remains legacy-backed and is outside this design change.

This contract defines how an authoritative decoded combat blueprint should be
reduced into the smallest useful human **thinking window**. Normative words such
as MUST and MUST NOT apply to a future decision projection implementation.
Examples are fixtures, not captured gameplay or current API responses.

## 1. Problem and non-goals

The E1 compact projection is compact for storage and audit. It still asks a
reader to interpret roster ASTs, typed expressions, move operations, behavior
graphs, applicability, evidence, and authority machinery. A decision surface has
a different job: expose the few consequences and counterfactual breakpoints that
can change a choice within a declared horizon.

A universal static monster summary cannot do that job. Whether a fact matters
depends on the realized lineup and state, current HP/Block/Powers, move history,
ordered hooks, hidden/random branches, available interventions, and the horizon.
For example, an on-death replacement rule may dominate a lethal-damage decision
but be irrelevant to a pure Block threshold; a Frail application matters before
a later defense window but not after the fight ends. Listing every move is too
large, while choosing one move without state turns possibility into prediction.
Static material can supply encounter grammar, never the missing temporal cut.

This design therefore separates:

1. a safe **encounter capsule** when only static authority is available; and
2. a future live **decision frame** when authoritative rules can be joined to a
   sufficiently complete, time-stamped observation.

### Non-goals

The projection is not:

- a card, target, or line recommendation, an optimizer, or an autoplay API;
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
  player policy and closed production/lifecycle semantics; otherwise the surface
  shows clocks, windows, and removal deltas instead; or
- a change to `/sts2`, its state reader, source migration artifacts, or the
  C1/C2/C3 cutover plan.

## 2. Cognitive budget and information hierarchy

The game screen is external memory. The HUD SHOULD NOT repeat visible HP, hand,
energy, Block, intent, or Power rows merely to look complete. `NOW` repeats an
observed value only when the value is needed to understand a derived threshold,
resolve ambiguity, establish freshness, or identify a less-visible state.

The collapsed phone surface targets one viewport and six stable chunks. A chunk
may wrap, but the order and meaning remain stable:

| Chunk | Question answered | Content |
|---|---|---|
| `NOW` | What observation cut makes these claims valid? | Only required observation context, parameters, freshness, and state ambiguity. Absent in a static capsule. |
| `IN` | What happens before I can decide again under the baseline? | Source-ordered raw/net threat and non-damage consequences, including cards, Powers, summons, state, and lifecycle. |
| `BREAK` | Which counterfactual boundary changes that result? | Kill, Block, strip, or interrupt thresholds and their consequence deltas. These are levers, not recommendations. |
| `OUT/NEXT` | Where does the baseline leave the fight, and what follows? | Post-turn deltas and the next-move envelope with conditions or branch structure. |
| `CLOCK` | Which timer/window changes the fight? | Escalation, phase, spawn, escape, revive, recurrence, and expiring opportunity clocks. |
| `?` | What unresolved fact could change a decision? | Hidden, stale, random, conflicting, unsupported, or unobserved inputs, named rather than guessed. |

`IN` and `OUT` may render as separate rows when space allows. Otherwise
`OUT/NEXT` is one chunk. A renderer SHOULD prefer one baseline, at most the few
non-dominated decision-sensitive breakpoints, and a branch envelope over a move
catalog. It MUST NOT remove uncertainty merely to meet the viewport budget.
Overflow becomes a tap-through layer, not silent omission.

Information is progressively disclosed:

1. **Decision surface:** the six chunks, consequence-first and terse.
2. **Fight expansion:** race only under a declared policy; otherwise windows,
   clocks, removal consequences, recurrence, and persistent/irreversible costs.
3. **Exact detail:** ordered operations, formulas, branch conditions, missing
   inputs, and rule/input references for each displayed claim.
4. **Audit:** untouched lane facts, conflicts, checked evidence pointers, and raw
   source projection objects.

Suppression at a higher level is view compression only. It MUST NOT delete or
rewrite lower-level facts.

## 3. The two products

### 3.1 Encounter capsule: honest static degradation

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

The capsule is useful now as a design/offline projection target because E1 can
support identity, placement, roster structure, applicability, move operations,
and behavior graphs within its declared coverage. It must still expose E1 gaps,
including initial-state/Power coverage, event behavior, HP rounding conflict,
and broader lifecycle families. Legacy annotations may decorate it only with a
visible `legacyAnnotations` lane badge and may not close an authoritative gap.
No capsule is a new `/sts2` runtime surface in the current stage.

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

If the live observation cannot identify a required state, the result remains a
set, conditional, range, or unknown. If no safe live frame can be formed, the UI
falls back to the capsule with a visible reason; it does not make the capsule
look current.

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
- conditions under which the next-move envelope changes.

It prefers clocks/windows/removal deltas to a speculative TTK. A TTK or race in
turn counts is permitted only when a named player policy, its input observations,
and all relevant enemy production/lifecycle behavior are explicit. “Assume
average damage” and hidden default inputs are forbidden.

### Relevance predicate

A fact or trace distinction survives the collapsed reducer only when, before the
declared horizon, it:

1. changes a player-relevant consequence;
2. crosses a relevant HP, Block, lethal, hand-size, energy, or other mechanical
   threshold;
3. creates, advances, expires, or changes an important clock/window;
4. creates a persistent or irreversible cost; or
5. changes what removal of a body/state does.

The consequence vector is ordered and at minimum spans per-creature HP/Block,
Powers, card zones/deck mutation, summons/bodies, model state/phase, and
lifecycle/encounter status. Implementations may add typed coordinates, but MUST
NOT merge traces that differ on any relevant coordinate. Move title equality is
never an equivalence rule.

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
  "observation": { "facts": ObservedFact[], "omittedVisibleFacts": string[] },
  "belief": { "shape": "singleton" | "finite-set" | "symbolic",
              "unresolved": string[] },
  "baseline": Claim<ConsequenceVector>,
  "breakpoints": Breakpoint[],
  "next": Claim<MoveEnvelope>,
  "clocks": Claim<Clock>[],
  "unknowns": Claim<string>[]
}
```

Ranges may be used only when intermediate values are all possible and
correlation does not matter. Otherwise a set of tuples or conditional cases is
required. `probability` is intentionally absent from the base branch type; a
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
      { "ref": "OBS.FIXTURE.AXEBOT.INTENT", "path": "axebot.intent", "value": "HAMMER_UPPERCUT_MOVE" },
      { "ref": "OBS.FIXTURE.AXEBOT.STOCK", "path": "axebot.powers.stock", "value": 2 }
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
        "ordered": ["damage 18", "apply Weak 2", "apply Frail 2"],
        "rawThreat": 18,
        "netThreat": 18,
        "playerHpDelta": -18
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
        "OBS.FIXTURE.AXEBOT.INTENT"
      ],
      "laneRefs": [
        { "lane": "sourceFacts", "refs": ["SOURCE.MOVE.MONSTER.AXEBOT.HAMMER_UPPERCUT_MOVE"] },
        { "lane": "legacyAnnotations", "refs": ["LEGACY.BODY.AXEBOTS_NORMAL.0"] },
        { "lane": "observedFacts", "refs": ["OBS.FIXTURE.PLAYER.HP", "OBS.FIXTURE.PLAYER.BLOCK", "OBS.FIXTURE.AXEBOT.INTENT"] }
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
  "next": {
    "claimId": "FRAME.FIXTURE.NEXT",
    "labels": ["derived", "source-certain"],
    "value": { "shape": "exact", "value": { "move": "ONE_TWO_MOVE" } },
    "support": {
      "ruleRefs": ["SOURCE.GRAPH.AXEBOT"],
      "inputRefs": ["OBS.FIXTURE.AXEBOT.INTENT"],
      "laneRefs": [
        { "lane": "sourceFacts", "refs": ["SOURCE.GRAPH.AXEBOT"] },
        { "lane": "observedFacts", "refs": ["OBS.FIXTURE.AXEBOT.INTENT"] }
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

The example's `derived` + `source-certain` next claim selects an unconditional
graph edge from an observed Hammer Uppercut. It intentionally carries no damage
value because the source formula is not closed here. `derived` says that the
baseline, threshold, or next edge was computed—it does not assign confidence or
upgrade its inputs.

## 6. Phone DSL

The renderer is a projection of the typed claims, not a second inference engine.
Badges may be abbreviated visually, but tap-through MUST expose their full labels
and lane refs.

### Static capsule available from the current knowledge boundary

This six-line Axebot capsule is illustrative output that could be built offline
from E1. It never says which branch is current:

```text
CAPSULE Axebot · Glory regular · A9/1P params · NOT LIVE
ROSTER  1 Axebot [source-certain]
OPEN    {Hammer Uppercut | Boot Up}; Stock chooser not closed [source-conditional]
CYCLE   Boot Up → Uppercut ↔ One-Two [source-certain]
VALUES  Uppercut 18 + Weak 2/Frail 2; One-Two 11×2; Boot Up 15 Block + 4/8 Str [legacyAnnotations:A9]
CLOCK/? max HP = base +10×respawnCount (0..2, pre-MP) [source-certain formula]; trigger/timing/removal and turn state unknown [unknown]
```

The two graph initials and cycle are present in `SOURCE.GRAPH.AXEBOT`. E1's
Axebot state rule proves the cumulative `10 × axebotRespawnCount` maximum-HP
bonus before multiplayer scaling. It does not by itself prove that Stock starts
at 2, how its hooks order death/replacement, or the full spawn lifecycle. The A9
numbers and detailed Stock prose above are visibly from the legacy annotation
lane. They are useful reference material, not authoritative lifecycle closure.

### Future live frame, using the fictional JSON fixture

```text
NOW      fixture only · obs #42 @ 00:00:00Z · A9/1P · you 50 HP/0 Block · Axebot 17 HP/0 Block, Stock 2
IN       END NOW → 18 raw / 18 net, then Weak 2 + Frail 2 [derived; damage=legacyAnnotations:A9]
BREAK    Block ≥18 → net 0; deal ≥17 → removal delta ? (Stock hooks) [derived, not advice]
OUT/NEXT baseline you 50→32; then One-Two, 11×2 [edge=source-certain; value=legacyAnnotations:A9]
CLOCK    Stock 2 observed; replacement/Boot Up window is legacy-only until lifecycle gates close [observed, unknown]
?        current app cannot observe these facts; formula closure, respawn count, Stock ordering, hand/feasibility missing [unknown]
```

`NOW` repeats HP/Block here only because those values explain both thresholds and
the baseline delta. A real screen should omit any visible value that does not do
such explanatory work.

## 7. Compiler and reducer pipeline

The pipeline is deterministic for a fixed authority manifest, observation set,
parameters, horizon, reducer version, and renderer version.

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
edge as a no-op. Trace-count/depth exhaustion produces a named truncation
unknown; it never silently drops branches.

### 7.6 Project consequence vectors and aggregate

Project each trace to an ordered player-relevant consequence vector. Traces may
be grouped only when they have the same vector through the horizon, the same
relevant clock/window/removal behavior, and compatible displayed provenance.
Grouping by move title, intent icon, final damage alone, or coincidentally equal
HP is invalid.

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

The reducer does not choose a breakpoint. “Kill,” “Block,” “strip,” and
“interrupt” are counterfactual dimensions, not recommendations.

### 7.8 Apply the relevance predicate

Apply the five tests in [Relevance predicate](#relevance-predicate). Relevance is
state- and horizon-dependent and must be recomputed after every observation cut.
Facts used only to establish a displayed derivation remain available in its
tap-through support even if they are not rendered as their own row.

### 7.9 Render and retain audit paths

Render the stable six chunks from typed claims. The renderer may abbreviate
names and combine rows, but cannot calculate new outcomes, collapse uncertainty,
or change labels. Every derived surface claim links to exact rule/input refs;
every lane badge links to lane facts; conflicts link to both sides. Raw facts are
the final audit layer.

## 8. Uncertainty, provenance, and fail-closed rules

### Labels are orthogonal

| Label | Meaning |
|---|---|
| `observed` | Directly present in a time-stamped observation at the declared cut. It says nothing about static source certainty. |
| `source-certain` | An unconditional authoritative rule under bound parameters. It does not claim that the rule's state is current. |
| `source-conditional` | An authoritative rule whose condition or required runtime input is not fully selected. Show the condition/input. |
| `source-random` | Multiple source-declared eligible branches remain. It does not imply equal likelihood. |
| `derived` | Computed from cited rules and inputs. This is provenance, not confidence. |
| `unknown` | A missing, stale, conflicting, unsupported, or unclosed fact can affect the claim. Name it. |

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
| No live turn observation (the current product) | Encounter capsule with `NOT LIVE`; no `NOW`, incoming prediction, or current threshold. |
| Authority manifest/version mismatch or mod ambiguity | No source-derived live frame; show mismatch and capsule only if its version is explicit. |
| Missing typed formula input | Preserve conditional/set/range/unknown and list the input; never use zero, midpoint, or legacy default. |
| Unsupported operation/hook/lifecycle | Stop affected traces at that boundary and mark downstream consequences unknown; never treat it as a no-op. |
| Unknown branch condition/eligibility/history | Structured branch set without probability. |
| Unresolved lane conflict | Retain both lane values and conflict refs; do not choose via precedence. |
| Stale or unordered observations | Exclude the stale claim or reject the cut; do not carry it forward. |
| Empty belief set | Contradiction diagnostic and no derived prediction. |
| Trace limit reached | Explicit truncated/symbolic remainder; never renormalize surviving traces. |
| Missing state/phase behind a known model ID | Set of possible states or unknown; model ID is not a state alias. |
| Removal lifecycle incomplete | No “kill cancels move/ends fight” claim; show removal delta unknown. |
| Hand/energy/timing absent | Mechanical threshold may remain, but feasibility is `unknown`. |

Unknown is not zero damage, “probably no effect,” or an empty list. Conditions
and ranges MUST remain machine-readable through rendering and tap-through.

## 9. Validation and usability criteria

### Semantic validation

A future implementation is acceptable only when automated fixtures establish:

1. lane objects remain separate and every conflict keeps both refs/values;
2. an input with no live turn observation produces a `NOT LIVE` capsule and
   never current language;
3. END NOW means no further actions from the exact observation cut;
4. ordered operations produce ordered consequences, including between-hit hooks;
5. missing HP/Block suppresses lethal/Block thresholds that require it;
6. Axebot Stock lifecycle gaps suppress the kill/removal delta even when the
   lethal damage threshold itself is known;
7. possible/produced monsters never become observed co-present bodies;
8. model identity never selects a hidden phase/state;
9. traces merge by complete relevant consequence vector, not move title;
10. correlated branches do not become independent numeric ranges;
11. probabilities appear only under the five closure conditions;
12. stale, contradictory, unsupported, and trace-truncated inputs fail closed;
13. every derived claim resolves all rule/input/lane refs; and
14. ascension, player count, act, and room parameters alter frames only through
    cited formulas/rules, with no hidden defaults.

Closed trace fixtures should be compared with an independently reviewed oracle
or captured deterministic game traces only after the observation and E2 source
contracts permit that comparison. Empirical traces are time-stamped
`observedFacts`, not patches to `sourceFacts`.

### Projection invariants

Schema validation MUST reject unknown value shapes/labels, unlabeled legacy
support, a derived claim without support, probability without closure evidence,
and current wording in a capsule. Property tests SHOULD verify that adding a
previously unknown belief branch cannot make the displayed envelope narrower
unless a cited observation/rule excludes that branch.

Golden tests SHOULD lock the reducer and renderer separately. A renderer golden
cannot substitute for trace correctness; a correct trace dump cannot substitute
for cognitive usability.

### Phone usability

At a representative narrow phone viewport, without horizontal scrolling, a
player should be able to:

- identify END NOW raw/net incoming threat and ordered non-damage effects;
- find the smallest displayed breakpoint and its delta without reading move ASTs;
- distinguish a condition/random set from a prediction;
- identify the one or two missing facts that can change the immediate decision;
- inspect fight clocks/windows/removal consequences without encountering a fake
  TTK; and
- tap from a derived number to its rule, observed inputs, lane, and raw evidence.

The collapsed view should fit roughly one viewport and six chunks. This is not a
license to conceal a seventh decision-changing unknown: combine or abbreviate
presentation, or expose a clear overflow indicator. Tests with experienced and
new players should measure answer correctness first and speed/scrolling second.
A surface that is terse but causes possibility to be read as prediction fails.

## 10. Staged implementation plan

This plan follows source migration gates and does not modify their artifacts or
ownership.

### Now: E1 design/offline capsule work only

- Freeze this logical contract and build schema/golden fixtures outside the
  stable consumer when implementation work is authorized.
- Compile only a static `EncounterCapsule` from E1-covered families: exact
  identity/placement, roster grammar, applicability, graph topology, operations,
  formulas that actually close, and explicit known unknowns.
- Keep exact legacy prose/values visibly in `legacyAnnotations`; do not use them
  to pass readiness gates.
- Do not expose a decision frame, live thresholds, or current intent. Do not
  import the projection into `/sts2`.

### E2 source gates

Enable reducer features family by family; an unrelated completed family does not
make the whole frame ready.

1. **E2a — ordered initial state and Power hooks:** close starts-with state,
   ordering, and hook semantics needed by initial branches and Powers such as
   Stock. Until then, starts and hook-dependent consequences stay conditional or
   unknown.
2. **E2b — HP chain:** close runtime HP/scaling/rounding and current HP semantics
   before authoritative lethal and HP-race thresholds.
3. **E2c — event graphs/lifecycle:** enable event encounter traces only for
   covered graphs and lifecycle edges.
4. **E2d — production and lifecycle:** enable spawn/replacement/survivor/removal
   consequences only when operation-through-lifecycle chains close.
5. **E2e — remaining formulas/runtime contracts:** enable exact consequence
   arithmetic only for expressions whose runtime inputs and observation
   contracts close.

Each stage adds capability flags at the family/claim level. There is no single
“mostly ready” fallback that guesses uncovered semantics.

### Observation gate for live frames

E2 static authority is necessary but not sufficient. A live `DecisionFrame`
also waits for a reviewed observer contract that supplies an atomic or ordered,
time-stamped cut for every input used by a claim: turn/decision phase, HP, Block,
Powers, intents, move history, counters, hand/deck when feasibility matters,
model states/phases, bodies/survivors, and relevant lifecycle events. Partial
observation yields partial symbolic claims or a capsule; it does not trigger
state inference from screen conventions or model IDs.

### C1/C2/C3 consumer gates

- **C1 shadow:** run capsule/frame compilation only in the migration architect's
  approved shadow path, compare structured outputs and fail-closed reasons, and
  collect no unsupported confidence/probability metric. Stable output remains
  unchanged.
- **C2 staged source-first UI:** render only claim families whose E2 and
  observation gates are green; retain immediate rollback and visible legacy
  lane boundaries.
- **C3/default switch:** require semantic fixtures, trace-oracle validation,
  phone usability results, version/mismatch behavior, and QA approval before any
  default change.

The current encounter lifecycle/identity reader can support capsule selection
and version context, not a live turn frame. Adding source authority without live
state improves the capsule; adding live state without closed source semantics
still must fail closed. Accurate decision prediction requires both.
