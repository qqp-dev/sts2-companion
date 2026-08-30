# Source world model schema

`data/game-v0.111.0-source.json` is a deterministic, presentation-independent
world model for exact public-beta v0.111.0 inputs. It contains identities,
localization joins, formulas, roster selections, membership sets, and state
facts—not UI sentences or layout. Schema 6 is the E2a boundary and remains
runtime-incomplete until independently gated later E2 and consumer waves land.

## Three-wave boundary

| Wave | Scope | Current status |
|---|---|---|
| A | Monster/state identity and names; HP/state formulas; HP multiplayer scaling; encounter roster/pool/production facts | Complete for explicit denominators |
| B | Move registration/title/intent; operations and helpers; move/Power scaling; selection and phase graphs | Complete for explicit denominators, with 18 classified missing titles |
| C0/E1 | Compact fact references plus source placement, observation identity, and behavior applicability | Landed; no runtime consumer change |
| E2a | Initial generator/constructor state, effective addition hooks, intrinsic Power hooks, runtime contracts, and 57 lane comparisons | Complete for exact denominators; no runtime consumer change |

The current app does not import this artifact or the compact projection and still displays the
wiki-derived book. Source extraction changes no routes, renderer output, event display, or
`data/encounters.json` bytes.

## Identities and state

Canonical model references have the form `MONSTER.<ModelDb entry>`. Source type,
canonical model, display identity, and state identity are separate fields.
Consequently:

- `MONSTER.TOUGH_EGG#HATCHED` remains the `TOUGH_EGG` model but uses shipped
  `HATCHLING.name` and the hatch HP expression;
- Test Subject phases remain states of `MONSTER.TEST_SUBJECT`; its title is the
  localized template plus an explicit save-progress input expression;
- Front, middle, and back Decimillipede segments are separate canonical models
  whose title getter uses `DECIMILLIPEDE_SEGMENT.name`; and
- aliases from the old presentation book are never used to generate source
  facts. Current save `monster_ids` are exact canonical `ModelId` strings; hatch
  and phase state cannot be recovered from the model ID alone.

Reachability classification is likewise separate: ordinary-reachable,
event-only, deprecated placeholder, helper/test, helper/obsolete, or obsolete.

## E1 placement and identity schemas

`placement.acts` is derived from the owning `ModelDb.get_Acts` registry, not an
expected ID list. For v0.111.0 it contains Overgrowth, Underdocks, Hive, and
Glory in source order, with exact source act indices. Each act contributes
weak, regular, elite, boss, and event pools. Encounter room class comes only
from exact `EncounterModel.RoomType`; `IsWeak` separates weak from regular
monster rooms. No encounter suffix, C# spelling convention, legacy act/kind,
or wiki value participates in the join.

The source denominators are four acts, 20 pools, 192 pool registry members, 89
current encounter placements, 90 current encounter memberships, and eight
event links. Placement retains source registry/pool order, equal `1.0` weights,
draw structure, no-immediate-repeat tag filtering and fallback, event
act-local/shared origin, pre-shuffle order, dynamic eligibility, and repeat
behavior. Unknown collection, weight, selection, or condition shapes abort the
family. The complete negative registry witness classifies `TUNNELER_NORMAL` as
non-pool. `RunManager.EnterNextAct` and `TheArchitect.CanonicalEncounter` prove
the Architect event encounter's separate scripted transition.

`observationIdentities.entries` contains exactly 108 unique current canonical
monster IDs. `ModelId.ToString`, the run-save converter, initial/summoned combat
history writers, and encounter log writers define separate wire contracts.
Matching is exact and case-sensitive. The contract has no generic lowercase,
strip-prefix, suffix, or fuzzy path. `stateObservationContracts` covers all
eight extracted states but records `separateStateIdEmitted: false`; it is not an
alias table. `resourceRepresentations` separately records the 108 exact
`MonsterModel.VisualsPath` values derived by `ModelId.Entry.ToLowerInvariant` and
`SceneHelper.GetScenePath`; resource paths are never accepted by model-ID lookup.

`behavior.applicability` is the exact metadata inheritance closure for all 100
behavior graph owners. Every graph and registration repeats the resulting
canonical model list for referential validation. The abstract
`DecimillipedeSegment` owner has three concrete descendants; unrelated names do
not join.

## Normalized AST grammar

All objects are closed: unknown node kinds, fields, operations, numeric types,
or excessive depth fail validation. JSON numbers are used only for integers.
Decimal constants are canonical strings so serialization never introduces
binary floating-point ambiguity.

### Typed expressions

Every expression declares `valueType`. Parameterized numeric method
references must carry one typed `arguments` expression per exact CLI signature
parameter; a missing, extra, non-projectable, or incorrectly typed argument
fails extraction and AST validation. The exact
`AscensionHelper.GetValueIfAscension` call is normalized to `ascensionSelect`
after all three stack arguments are resolved. Instance receivers are
distinguished from signature parameters rather than being miscounted as
arguments.

| `kind` | Meaning |
|---|---|
| `constant` | Typed integer, Decimal string, or boolean literal |
| `stateVariable` | Named external input with an explicit bounded domain |
| `sourceField` | Exact compiler/source field symbol with a numeric type; evaluation requires an explicit supplied field context |
| `reference` | Exact source method signature; every metadata-signature parameter is retained in ordered `arguments`, and a separately compiled full result may be carried in `compiled` |
| `combatQuery` | Typed runtime query input; the pure evaluator requires it to be supplied |
| `ascensionSelect` | Select `below` or `atOrAbove` at an observed threshold |
| `arithmetic` | Reviewed `add`, `subtract`, `multiply`, `divide`, or CLI truncating `remainder` operation |
| `compare` | Typed comparison producing boolean |
| `conditional` | Typed condition with equal-typed branches |
| `actRoomFactor` | Reviewed act-index and boss-context Decimal factor table |
| `convert` | Explicit exact integer-to-Decimal conversion or named Decimal-to-integer rounding |
| `range` | Integer minimum/maximum expression pair |

Example (abridged Axebot minimum HP):

```json
{
  "kind": "arithmetic",
  "operator": "add",
  "valueType": "integer",
  "operands": [
    {
      "kind": "ascensionSelect",
      "threshold": 8,
      "below": { "kind": "constant", "valueType": "integer", "value": 70 },
      "atOrAbove": { "kind": "constant", "valueType": "integer", "value": 76 },
      "valueType": "integer"
    },
    {
      "kind": "arithmetic",
      "operator": "multiply",
      "valueType": "integer",
      "operands": [
        {
          "kind": "stateVariable",
          "name": "axebotRespawnCount",
          "valueType": "integer",
          "domain": { "minimum": 0, "maximum": 2 }
        },
        { "kind": "constant", "valueType": "integer", "value": 10 }
      ]
    }
  ]
}
```

HP multiplayer scaling accepts Decimal `baseHp`. One player returns it
unchanged. More players evaluate `baseHp × Decimal(playerCount) × factor`.
The observed factor input domain is act index 0 through 2 plus boss context;
out-of-domain acts fail. The source method returns Decimal and performs no
rounding or truncation. The pure test evaluator runs only normalized ASTs and
never game code.

### Roster selections

| `kind` | Meaning |
|---|---|
| `fixed` | One canonical model |
| `sequence` | Ordered children; order is fixed or RNG-selected as declared |
| `uniformChoice` | One uniformly selected child |
| `weightedChoice` | One child selected by explicit integer weights |
| `repeat` | Independent or without-replacement repeated draws |
| `permutation` | RNG-selected ordering of a child selection |
| `filteredChoice` | Repeated selection under a reviewed count/exclusion constraint |

Each initial roster is separate from `possibleMonsters`, `producedMonsters`,
and `productionPools`. Candidate membership is never flattened into a lineup.
For example, Flyconid is represented as a two-slot sequence: a uniform medium
slime choice followed by fixed Flyconid. Fabricator initially contains only
Fabricator; its four bots are produced membership split into aggressive and
defensive pools.

Dependent choices are represented structurally. Slimes Weak is a uniform choice
between the two complete small-slime orders, with an independent medium choice
in the middle. This proves exactly three bodies and exactly one of each small
slime without pretending the four candidates are one lineup.

Fixed rosters are compiled by a bounded stack/data-flow interpreter over a
strict opcode, call-signature, and collection-builder allowlist; model call
sites alone are not treated as bodies. Reviewed loops require an exact CFG and
a separately proven finite input. Dense Vegetation, for example, iterates its
source-defined four-entry `get_Slots` array and therefore emits an ordered
four-Wriggler sequence. An unknown or dynamic slot cardinality fails extraction
instead of being flattened to the loop body's single `ModelDb.Monster` call.

## Provenance

Raw facts use `authority: "rawSource"` (directly or through the artifact-level
default) and bind to:

- exact assembly/PCK SHA-256;
- fully qualified type/method signature;
- exact method-body and CIL instruction hashes;
- normalized instruction and semantic/expression witness hashes;
- localization PCK path, entry MD5/SHA-256, key, and key/value witness; and
- diagnostic metadata tokens only as exact-build locators, never identities.

Selection roots and possible/produced membership facts carry their own method
and semantic witnesses. Whole-method hashes do not replace normalized formula
or selection witnesses.

Future non-raw observations must use an explicit `community` or `empirical`
kind with URL, revision or retrieval date, claimed version, confidence, and
status. A raw/community disagreement is a conflict requiring review; it cannot
be silently merged or relabeled. No such fallback is ingested in Wave A.

## Failure and durability rules

Extraction hashes every manifest input before parsing facts and writes only
after the complete build succeeds. Unknown required-slice opcodes, calls,
signatures, branches, localization joins, arithmetic, state inputs, model
references, recursion, or depth fail extraction. No previous artifact facts and
no wiki values are used to fill a failed raw extraction.

Authority applies only to the embedded exact manifest for unmodded v0.111.0.
A game update needs a new manifest plus regeneration and review. Mods and live
combat/save values are outside this static artifact. Checked bytes and unit
tests provide regression/integrity evidence; exact-file regeneration under the
extractor trusted computing base provides source-strength evidence.

## Commands

```sh
GAME_ROOT="/home/qqp/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Slay the Spire 2"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT"
.venv-source/bin/python tools/extract-source.py --game-root "$GAME_ROOT" --check
npm test
```

## Regression comparison with the current book

These checks are discrepancy fixtures, never extraction inputs or source proof:

- after mapping current-book compatibility aliases and display states, all 105
  current non-Doormaker A8 body/state HP facts compare equal to the raw-derived
  values;
- the raw build has eight event encounters that the current runtime book does
  not display, while the runtime book retains the removed Doormaker entry;
- the current flat Flyconid lineup fixes Leaf Slime (M), but raw selection is
  uniform Leaf Slime (M)/Twig Slime (M);
- the current flat Slimes Weak candidates do not express the exact three-body
  rule (one of each small slime and one random medium slime);
- the current Slithering Strangler lineup does not express its three secondary
  categories or the independent draws in the two-small category; and
- current presentation names may differ from shipped encounter titles.

A mismatch in these fixtures is surfaced for review. It cannot supply, replace,
or override a missing raw fact.


## Combat operations and graphs

Wave B adds closed operation and graph grammars. Unknown operation kinds, graph
node/edge kinds, helper names, or missing provenance fail validation.

### Operations

| `kind` | Meaning |
|---|---|
| `attack` | `DamageCmd.Attack` amount/target |
| `attackHitCount` | `AttackCommand.WithHitCount` |
| `applyPower` | `PowerCmd.Apply` with canonical Power |
| `gainBlock` | `CreatureCmd.GainBlock` |
| `addStatusCard` / `addGeneratedCard` | card pile sinks |
| `summon` | `CreatureCmd.Add` |
| `heal` / `escape` / `removeCard` | remaining reviewed command sinks |
| `kill` | exact `CreatureCmd.Kill` target and play-death-effects argument |
| `removePower` | generic canonical Power removal or an exact runtime-selected Power-instance contract |
| `stateWrite` | typed monster property write with exact setter identity |
| `helperEffect` | Reattach, Fabricator spawn, ChooseCurse, Tough Egg hatch, Waterfall pressure |
| `transition` | explicit no-op or nonnumeric/state update |

Amounts are typed expressions. A `reference` node retains an exact source method
signature; a `sourceField` retains an exact typed compiler/source field without
inventing a domain. The pure evaluator only evaluates either when a compiled
expression or explicit context is supplied.

Intent constructors use the same decoded-signature stack contract. The 387
constructor sites contain 311 required arguments: numeric expressions, typed
boolean constants, or the closed `sourceDelegate` shape. A source delegate keeps
its `(object, nativeInt)` constructor signature, receiver binding, exact target
method and body/slice hashes, and a normalized `resultExpression` derived from
all reachable return stacks. Array indices and neighboring constants/getters are
not constructor arguments. Unknown signatures, delegate bindings/targets,
return stacks, or non-unique expressions fail extraction. The two complete
coverage families separately count 387 classified constructors and 311 resolved
arguments, so a site census cannot conceal an unresolved Func overload.

Intent templates from `intents.json` are localization facts; their numerals are
not effect authority.

### Closed invocation classification

Every one of the 6,332 direct `call`, `callvirt`, and `newobj` sites in the 301
current `MoveNext` bodies, plus 351 unique sites in 29 recursively reached helper
bodies, has an evidence-bearing census record and exactly one outcome:
`normalizedGameplayOperation`, `traversedGameplayHelper`, or
`provenNonGameplayPlumbing`; an unresolved fourth outcome aborts extraction and
is never serialized as complete. The combined 6,683-site census contains 1,156 exact source symbols and resolves
508 / 1,080 / 5,095 sites respectively; separate direct/helper denominators are
retained (6,332 and 351). Exact command declarations
form a closed boundary. A newly observed command method, unknown Godot/framework
member, missing signature, or unsupported local side-effecting method receives a
stable `UNRESOLVED.INVOCATION.<sha256>` identifier and fails the family.

Local monster, Power, and card helpers resolve by exact owner/member/signature.
Async helpers are followed through `AsyncStateMachineAttribute` to generated
`MoveNext` bodies; abstract helper calls traverse every concrete CLI
`InterfaceImpl`/override. Their nested calls are classified recursively, exposing
helper-contained effects such as Stun, bot spawning and Minion application,
card selection/Power application, HP reset/heal, deck-card removal, and gold
loss. SFX, animation, waits, task awaiters, collections, and presentation nodes
use narrow declaration/member recognizers and remain visible in the census; no
unknown-prefix ignore can claim completeness.

Schema 5 obtains every sink stack contract by decoding the exact ECMA-335
signature, including static versus instance receivers and generic signatures.
A bounded CFG abstract interpreter carries constants, arguments, locals,
fields, getters, arithmetic, conversions, and fluent command receivers across
branches and async resume plumbing. Equal joins collapse; unequal required
values remain unresolved and abort generation. Unknown stack effects, call
signatures, branch targets, target classes, or expression types likewise fail
before atomic replacement. No positional instruction window or “last getter”/
“last constant” fallback is used.

Operation fields are closed by kind. In particular, attack amounts come from
the sole `DamageCmd.Attack` argument, hit counts from the argument consumed by
`WithHitCount`, Block from `GainBlock.amount` rather than its trailing props
enum, and Power amount/target from the selected `Apply` overload. Summon,
escape, and card removal do not receive dummy numeric values. `CreatureCmd.Kill`
retains its exact creature and boolean arguments; the two explosion moves are
source-monster self-kills with play-death-effects false. Generic `PowerCmd.Remove`
retains canonical Power type arguments (including Soar, Adaptable, and Painful
Stabs). The sole non-generic removal is explicitly a runtime-selected iterator
Power instance rather than an invented model. Attack target
classification is backed by a separately hashed slice of
`AttackCommand.FromMonster -> TargetingAllOpponents`, producing
`allOpponentsOfSourceMonster`; `FromMonster` attacker evidence by itself is not
a target fact. Other observed targets remain distinct (`sourceMonster`,
`registeredTargets`, `iteratedCreature`, teammates, or an awaited summoned
creature), as do slot and card selections.

### Graphs

Nodes are `move`, `random`, or `conditional`. Edges are `followUp`,
`randomBranch`, or `conditionalBranch`. Weights are emitted only from AddBranch
integers. Predicate callbacks remain `reference` expressions unless a later
wave compiles them. Branched initial states (Decimillipede `StarterMoveIdx % 3`,
Axebot stock override, Chomper `_screamFirst`) are recorded as multiple proven
initials rather than a guessed single start.

Monster Block scaling and Power opt-in/override formulas are separate from
ordinary `DamageCmd.Attack` amounts. Ordinary monster attacks do not inherit
HP or Block multiplayer multipliers.

The 6,683-site combined invocation census (6,332 direct plus 351 helper),
491 direct-operation census, and each
operation-kind denominator are reported separately from 1,081/1,081 required
semantic fields. A physical site is not counted as
semantic completion unless its required arguments, target/selection, model,
expression type, and normalized slice resolve.

18 move titles are classified `missingLocalization`. That is complete
classification, not complete localized coverage, and is reserved for an
explicit, visibly cited later community fallback if useful. Wave B never
imports community/wiki data into the raw artifact and makes no XML migration
claim.


## E2a initial-state schema

`initialState` starts before the monster addition hook. Its stage chain is
`GenerateMonsters`/constructor defaults, `CombatState.CreateCreature`,
`EncounterModel.OnCreatureSpawned`, `StartCombatInternal` and the exact called
`AfterCreatureAdded` overload, `Creature.AfterAddedToRoom`, effective virtual
monster hooks, Power apply hooks, and finally `Hook.BeforeCombatStart`.
Facts never flatten those stages or treat later `CreatureCmd.Add` calls as
initial population.

The source-discovered denominators are:

- 89 generator roots, 137 model construction sites, 38 RNG call sites, five
  non-roster RNG roots, and 25 setter sites in 13 roots;
- four reachable constructors with five explicit writes;
- 108 model owners, 59 effective addition implementations, 48 exact base no-op
  models, and one shared Decimillipede implementation applying to three models;
- 54 direct Power applications, one Block site, one max/current-HP site, and one
  current-HP site before helper expansion;
- 1,092 classified required invocations, 111 ordered facts, 41 initially
  reachable Power hook closures, 29 external-boundary declarations, and 53
  runtime contracts.

Each fact has a stable ID, owner and exact applicability, stage/trigger/source
order, a closed condition, effect and recipient kind, typed base expression and
unit, scaling/runtime modifiers, source-state contract refs, and exact method
and normalized-slice provenance. Runtime contracts retain source member/type,
ownership, type/domain, read/update sites, and consumer meaning. Source-derived
external listeners are `externalRuntimeOwned`; they are not silently omitted
from an intrinsic baseline.

Helper traversal is mandatory. Lagavulin's `Sleep` writes awake state and
applies Plating/Asleep. Illusion `AfterApplied` applies Minion conditionally;
Plating writes a player-count dynamic variable. Galvanic and Vital Spark afflict
eligible player cards before combat. Tough Egg preserves both the current-side
conditional Hatch amount and restored-hatched helper branch. Decimillipede's
shared HP algorithm remains a dynamic source contract rather than a fabricated
static number.

All 57 legacy starts-with rows produce separate source/legacy lane comparisons.
Statuses distinguish exact agreement, source supersets, dynamic non-comparability,
state-not-model annotations, and unmatched legacy identity. Decimillipede
shortcuts remain `identityJoin: none`; Hatchling and Test Subject phases remain
states. No comparison promotes an alias or selects lane precedence.

The expected Dense Vegetation “stunned setup” did not match source. Its generator
writes `Wriggler.StartStunned = false`; Wriggler selects `SPAWNED_MOVE` only for
true. Schema 6 records this source-proven result as an investigated audit
difference.

Extraction fails before replacement on unknown overload/opcode/target joins,
helper repetition/cycles, omitted Power hooks, unsupported field types or
conditions, unregistered runtime inputs, missing owners/roots/sites, broken
applicability/evidence refs, or changed provenance. The compact projection keeps
facts/contracts/owner/hook summaries and excludes the 1,092-call and initializer
proof tables.

## E2a projection boundary

The checked source artifact above remains the full static evidence artifact.
C0 introduced, E1 extended, and E2a extends `data/encounter-facts-v0.111.0.json`, built by
`tools/generate-encounter-facts.py` from that artifact and
`data/encounters.json` only. It is a projection, not a replacement extractor
and not a runtime consumer input.

The projection schema is closed and independently validated. Validation pins
schema/extractor/game/assembly identity, both projection input bytes, the
embedded four-row source manifest, raw-only/patch-none authority, every
projected denominator, AST kinds/operators/numeric types and depth, IDs,
encounter/model/state/owner/graph/operation/legacy/evidence joins, lane
comparisons, and both canonical digests. Validation and serialization complete
before atomic replacement. `--check` compares exact bytes without writing.

Source facts and legacy/community annotations are separate objects. Exact-ID
legacy encounter links are explicit; no save/log/model alias is inferred.
Observed samples remain absent, but the source-derived exact adapter vocabulary
and save/log wire contracts are now projected. Legacy identity strings are
compared by exact equality only and unmatched strings remain explicit lane
comparisons. Legacy move
names associated with the same exact model are candidate sets only and never
selected as source-title replacements. Disagreements are unresolved conflict
records, while absent or dynamic semantics are stable reason-coded
known-unknowns.

The payload digest excludes all metadata and hashes compact canonical JSON of
`payload`; the embedded source-input-manifest digest hashes compact canonical
JSON of the exact manifest list. Evidence stores stable JSON pointers and
pointed-value hashes instead of repeating CIL proof or the 6,683-invocation
census. This makes the projection substantially smaller while retaining an
auditable path to the full checked source artifact.

E2a declares only the bounded encounter projection complete. The encounter
companion remains hard-false/incomplete pending event behavior, lifecycle
closure, companion-wide formula/runtime contracts, and E2b downstream HP
conversion/rounding. Global readiness also remains false
pending the independent product-family source waves. No `src/` file imports the projection,
so `/sts2` continues to use byte-identical `data/encounters.json`.
