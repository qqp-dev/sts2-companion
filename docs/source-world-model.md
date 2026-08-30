# Source world model schema

`data/game-v0.111.0-source.json` is a deterministic, presentation-independent
world model for exact public-beta v0.111.0 inputs. It contains identities,
localization joins, formulas, roster selections, membership sets, and state
facts—not UI sentences or layout. Schema 11 is the E2d1a boundary and remains
runtime-incomplete until independently gated later E2 and consumer waves land.

## Three-wave boundary

| Wave | Scope | Current status |
|---|---|---|
| A | Monster/state identity and names; HP/state formulas; HP multiplayer scaling; encounter roster/pool/production facts | Complete for explicit denominators |
| B | Move registration/title/intent; operations and helpers; move/Power scaling; selection and phase graphs | Complete for explicit denominators, with 18 classified missing titles |
| C0/E1 | Compact fact references plus source placement, observation identity, and behavior applicability | Landed; no runtime consumer change |
| E2a | Initial generator/constructor state, effective addition hooks, intrinsic Power hooks, runtime contracts, and 57 lane comparisons | Complete for exact denominators; no runtime consumer change |
| E2b | Integer HP selection, Decimal multiplayer arithmetic, explicit assignment conversion/cap/clamp, special callers, Int32 storage and network wire joins | Complete for exact denominators; no runtime consumer change |
| E2c1 | Event-inclusive physical turn graphs, inherited/reused applicability, event titles/intents/operations/no-op proofs, and helper-call closure | Complete for exact turn-machine denominators; scripted event and lifecycle dependencies remain |
| E2c2a | Five linked event owners, 12 option/delegate constructions, seven exact combat transitions/outcomes, Foul Potion dispatch, and common framework closure | Complete for the non-Architect linked slice |
| E2c2b | Architect placement, dialogue selection/line graph, structural localization, visual-only layout, presentation closure, and terminal sink/order | Script component complete; lifecycle producers/order and formulas remain dependencies |
| E2d1a | Generic random repeat/float-weight repair; closed Add/Osty census; current producer roots/helper sites; shared core Add lifecycle contract | Complete for exact discovery/core denominators; per-producer E2d1b semantics and E2d2 lifecycle remain pending |

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

`behavior.applicability` is the exact metadata inheritance closure for all 105
behavior graph owners. Every graph and registration repeats the resulting
canonical model list for referential validation. The abstract
`DecimillipedeSegment` owner has three concrete descendants. The concrete
`FlailKnight` owner has direct applicability to itself plus inherited applicability
to exact descendant `MysteriousKnight`; this remains one physical graph. Unrelated
names do not join.

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
rounding or truncation. This helper-level statement is not the final stored-HP
contract. E2b separately proves explicit `Decimal -> Int32` truncation toward zero
at assignment; for non-negative HP only, that is equivalent to floor. The pure
test evaluator runs only normalized ASTs and never game code.

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

Intent constructors use the same decoded-signature stack contract. The 393
constructor sites contain 316 required arguments: numeric expressions, typed
boolean constants, or the closed `sourceDelegate` shape. A source delegate keeps
its `(object, nativeInt)` constructor signature, receiver binding, exact target
method and body/slice hashes, and a normalized `resultExpression` derived from
all reachable return stacks. Array indices and neighboring constants/getters are
not constructor arguments. Unknown signatures, delegate bindings/targets,
return stacks, or non-unique expressions fail extraction. The two complete
coverage families separately count 393 classified constructors and 316 resolved
arguments, so a site census cannot conceal an unresolved Func overload.

Intent templates from `intents.json` are localization facts; their numerals are
not effect authority.

### Closed invocation classification

Every one of the 6,418 direct `call`, `callvirt`, and `newobj` sites in the 305
current `MoveNext` bodies, plus 368 unique recursively reached helper
sites, has an evidence-bearing census record and exactly one outcome:
`normalizedGameplayOperation`, `traversedGameplayHelper`, or
`provenNonGameplayPlumbing`; an unresolved fourth outcome aborts extraction and
is never serialized as complete. The combined 6,786-site census contains 1,172 exact source symbols and resolves
514 / 1,101 / 5,171 sites respectively; separate direct/helper denominators are
retained (6,418 and 368). Exact command declarations
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

The 6,786-site combined invocation census (6,418 direct plus 368 helper),
497 direct-operation census, and each
operation-kind denominator are reported separately from 1,094/1,094 required
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
eligible player cards before combat. Tough Egg preserves the exact
`(CurrentSide == 2) ? Hatch 2 : Hatch 1` amount and restored-hatched helper
branch. Its `CurrentSide` contract derives the closed `CombatSide` enum domain
`None=0`, `Player=1`, and `Enemy=2` from CLI metadata rather than inventing a
range. Decimillipede's
shared HP algorithm remains a dynamic source contract rather than a fabricated
static number.

All 57 legacy starts-with rows produce separate source/legacy lane comparisons.
Statuses distinguish exact agreement, source supersets, dynamic non-comparability,
state-not-model annotations, and unmatched legacy identity. Decimillipede
shortcuts remain `identityJoin: none`; Hatchling and Test Subject phases remain
states. No comparison promotes an alias or selects lane precedence.

The expected Dense Vegetation “stunned setup” did not match source. Its generator
writes `Wriggler.StartStunned = false`; Wriggler selects `SPAWNED_MOVE` only for
true. Schema 7 records this source-proven result as an investigated audit
difference.

Extraction fails before replacement on unknown overload/opcode/target joins,
helper repetition/cycles, omitted Power hooks, unsupported field types or
conditions, unregistered runtime inputs, missing owners/roots/sites, broken
applicability/evidence refs, or changed provenance. The compact projection keeps
facts/contracts/owner/hook summaries and excludes the 1,092-call and initializer
proof tables.

## E2b HP assignment schema

`hpPipeline` begins with `Creature(MonsterModel, CombatSide, slot)`: min and max
getters are `Int32`, `min > max` throws, and initial max/current both receive max.
For `CombatSide.Enemy`, `CreateCreature` calls `SetUniqueMonsterHpValue` before
`ScaleMonsterHpForMultiplayer`. Candidate construction is exactly
`Enumerable.Range(min, max + 1 - min)`, so the base domain is inclusive and
discrete. Existing teammate max values are removed when possible; an exhausted
set falls back to `Rng.NextInt(min, max + 1)`. The run's Niche RNG supplies the
choice. Selection remains separate from transformation: scaled endpoint values
do not assert that every intervening integer is attainable.

The multiplayer wrapper returns immediately for one player. Otherwise the helper
evaluates Decimal `base × playerCount × actRoomFactor` with no rounding, then
`SetMaxHpInternal` checks `< Decimal.Zero`, explicitly invokes
`Decimal.op_Explicit` to `Int32`, and applies `Math.Min(converted, 999999999)`.
Thus checked conversion/overflow precedes the cap. Max is stored before current is
reduced to `min(previousCurrent, newMax)`. `SetCurrentHpInternal` computes
`Decimal.Min(requested, Decimal(maxHp))`, then performs the explicit conversion and
stores `Int32`; it has no source-proven lower clamp. The normalized conversion AST
uses `truncateTowardZero`. Because assigned monster HP is source-proven
non-negative, the derived final result equals floor in that domain only.

The complete direct target census is 19 sites: eight helper calls, one multiplayer
wrapper call, six current-setter calls, three max-setter calls, and one unique-value
call. The command census is 44 callers across five exact wrappers. `GainMaxHp` and
`LoseMaxHp` join `SetMaxHp`; `SetMaxAndCurrentHp` awaits max before current. Tough
Egg joins helper to max/current, Test Subject joins helper to max then heal, and
Decimillipede joins helper to max/current. Unknown overloads or unjoined special
paths fail extraction.

Creature `_currentHp`/`_maxHp` and `NetFullCombatState.CreatureState`
`currentHp`/`maxHp` all have CLI field signature `06 08` (`Int32`). Network capture
reads current then max; serialization calls `WriteInt` with 32 bits for each; and
deserialization calls `ReadInt(32)` and stores current then max. Decimal wire
fields or changed order fail before replacement.

Coverage records 4 base-chain methods, 9 wrapper/helper sites, 11 setter
method/sites, 52 command/special applicability records, 8 cap/clamp/precondition
fields, 10 storage/network joins, and 85 semantic fields, all with zero unresolved.
The compact projection removes call/provenance bulk but retains the semantic
contract, source denominators, regression witnesses, fact/evidence refs, and exact
input/payload digests.

The earlier helper-only statement, the assignment conversion, and the stable
legacy consumer's `Math.floor` remain separate lanes in
`AUDIT.RESOLVED.HP_ASSIGNMENT_ROUNDING`. The audit resolves agreement for
non-negative final assigned HP without selecting precedence, erasing history, or
generalizing floor equivalence to negative values.

## E2c1 event-turn behavior schema

`behavior.eventTurnMachines` is enumerated from all eight source event encounters,
their exact roster model, E1 event link, and the single applicable behavior owner.
The physical domain is 105 owners/graphs and 315 registrations. Five owners and
eight registrations are event additions; Mysterious Knight inherits the existing
Flail Knight owner/graph/three registrations. Dense Vegetation and Punch Off reuse
Wriggler and Punch Construct. No behavior is inferred from a model or encounter ID.

The closed classifications are `normalTurnMachine`, `inheritedTurnMachine`,
`noOpTurnMachineWithLifecycle`, and `scriptedNonTurnCombat`. Three Battle Friends
have one read-only-collection `NOTHING_MOVE` self-loop each and exact
`Task.CompletedTask` no-op proof. Their initial timeout Power facts and exact
`BattlewornDummyTimeLimitPower.AfterSideTurnEnd` root are retained as unresolved
lifecycle dependencies. Architect has one hidden no-op self-loop. At E2c1 its exact
`TheArchitect.OnRoomEnter`, `AdvanceDialogue`, and `WinRun` roots were an unresolved
scripted dependency; schema 10 resolves that dependency only through the separate
E2c2b component. The no-op graph itself is never represented as complete event
semantics.

Fake Merchant contributes four localized moves, two random nodes/seven random
branches, five intent sites/five arguments, three attacks, one attack hit-count,
Frail, and Strength. Recursive helper closure reaches `GetLinesForMove`.
`System.String.Concat` is accepted only for the exact four-argument dialogue
localization-key construction context; any other context remains unclassified and
fails extraction. The event subset classifies 103 calls (six gameplay, 21 traversed
helpers, 76 narrow non-gameplay plumbing). Generic graph collection state records
the exact constructor, `MoveState` element type, source order, and cardinality;
unknown constructors, overloads, types, elements, or joins fail.

The compact `eventTurnBehavior` projects eight classification facts, three unresolved lifecycle dependency facts and one source-complete Architect component ref, title/applicability/graph/registration/initial-state refs, event
source denominators, and the invocation summary. It omits method proof and decision
bulk. `AUDIT.RESOLVED.EVENT_TURN_MACHINES` marks only this physical turn component
source-complete. Schema 10 retires `UNKNOWN.EVENT_SCRIPTED_BEHAVIOR` through the
separate Architect audit. The aggregate `UNKNOWN.EVENT_BEHAVIOR` remains alongside
`UNKNOWN.EVENT_LIFECYCLE`; later lifecycle work must close timeout/escape/result and
run-end ordering before the aggregate blocker can be removed.

## E2c2a linked-event script schema

Raw `eventScripts` starts only from E1 owner/method/link provenance and contains five
owners, 12 exact options/delegates, seven transition calls, seven outcomes, 25 nodes,
20 edges, 10 direct semantic effects, 10 state/runtime contracts, six dependency refs,
three independently decoded Battle display calls, 76 owner methods, 14 Foul Potion
support methods, 53 common framework roots/async bodies, and 1,549 classified call
sites. Every denominator is emitted by discovery and validated before replacement.

The normalized graph preserves asynchronous completion versus exception propagation.
It derives stage predecessors from the method that constructs each option: Dense Rest,
Lantern Keep, and Punch Off Take precede their Fight options. Fake Merchant instead
uses the Foul Potion event-instance fan-out and `Task.WhenAll`; no hidden option is
invented. Transition facts retain exact overload, encounter, added rewards, and
Boolean resume argument and join the existing E1 link fact.

Dense eligibility and damage retain the runtime input
`event.dynamicVars.HpLoss.baseValue`. Battle `Resume` retains the Boolean
`encounter.RanOutOfTime` read and V1/V2/V3 success branches. The timeout write, Power
decrement/removal, escape, and terminal combat result remain lifecycle refs. Exact
stack extraction shows the three Battle display calls use monster V1/V2/V3 and the
V1 encounter argument at each site; no expected polarity or argument was seeded.

The schema 8 compact projection includes semantic owners/options/transitions/outcomes/
nodes/edges/effects/contracts/dependencies and fact evidence, but excludes raw method
censuses and the 1,549 call decisions. Its linked-event component is complete.
At the E2c2a boundary Architect remained `UNKNOWN.EVENT_SCRIPTED_BEHAVIOR`. E2c2b
retires that blocker, while Battle timeout/escape/common terminal and Architect
OnEnded/forced-kill/order refs remain `UNKNOWN.EVENT_LIFECYCLE`; aggregate and global
blockers remain. No readiness outside the bounded projection is changed.

Evidence grade: exact pinned CLI metadata and CIL for all normalized script facts;
explicit unresolved refs for lifecycle/formula contracts; no runtime observation or
community fallback is silently merged.


## E2c2b Architect scripted component

Raw `eventScripts.architect` starts from the exact E1 non-pool owner/link and discovers
its own source denominators before regression pins. For pinned v0.111.0 those
distributions are five character groups, 17 templates, 39 lines/control nodes, 39
outgoing line edges (22 continuation and 17 terminal-proceed), two option/delegate
sites, 96 deduplicated methods, 715 classified invocations, 13 presentation-closure
methods, eight runtime contracts, six semantic effects, and five dependency refs.
These values are discovered output, not an input table.

`DefineDialogues` supplies generic character identities, visit indices, line-array
cardinalities, and all source attacker enum variants. `PopulateLocKeys` and
`PopulateLines` define repetition, line order, speaker suffix, and continuation-key
control. The extractor reads only the exact pinned `localization/eng/ancients.json`
entry and emits 64 selected structural key records with entry/path/PCK and per-key/value
digests. It emits no localized line or button values. Missing/duplicate keys, unknown
speaker/suffix, inconsistent repetition, wrong order, malformed values, or a PCK digest
mismatch fails before replacement.

Selection is a typed runtime contract over character ID, per-character wins or the
source zero branch, global progress wins, exact-match candidates, repeating fallback,
and event RNG choice. A selected template is never flattened to a constant.
`NCombatEventLayout.SetEvent` passes source enum value 2 (`VisualOnly`) to
`NCombatRoom.Create`; the component classifies this as `notActiveCombat` and references
the hidden no-op turn fact without treating it as sufficient.

Room entry records `ScoreUtility.CalculateScore(event.owner.runState, true)` by exact
overload/arguments and leaves its formula/value to E2e. Line control retains local,
null dialogue, index, line, speaker, node, and animation early-return branches plus
separate async success/exception edges. The presentation closure contains animation,
Talk, wait, TriggerAnim, hit/fire and damage-number VFX; exact closure contains no
HP/gameplay damage. `DivideWildly` retains score/count/RNG inputs and is never rendered
as a deterministic split.

Terminal order is player animation, Architect animation, locally guarded
`RunManager.WinRun`, await, then empty-option finished state. No reward, resume, or
active event-combat transition is claimed. `RunManager.OnEnded(true)`, forced player
kills, serialization/stat/history work, and run-end ordering remain E2d2 dependency
refs rather than duplicated dialogue effects. `AUDIT.RESOLVED.ARCHITECT_SCRIPT` closes
the script component; aggregate event, event lifecycle, global lifecycle,
formula/runtime-contract, title/provenance, and broader-world gaps remain. All global,
root, encounter-companion, and source runtime readiness remains false.

## E2d1a random and production contracts

Every reachable `RandomBranchState.AddBranch` call is decoded from its exact CLI
signature and named parameter metadata. The schema no longer permits an enum
integer in `weight` or a float callback in `predicate`. Each of the 61 branches
has target/source order, exact `MoveRepeatType` name/value, overload-supplied
maximum/cooldown values, and either an exact float constant or a parameterless
float delegate with receiver, target method, expression/runtime contract, and
provenance. Boolean predicates remain a separate conditional-branch concept only.
The complete repeat distribution is 4 forever, 10 bounded, 45 cannot-repeat, and
2 use-once, with eight delegate weights. Rat Call is independently
`UseOnlyOnce`; the other three Rat branches are individually `CannotRepeat`, and
Screech alone supplies cooldown 3.

The runtime component traces `StateWeight.GetWeight`, `GetStateWeight`, and
`GetNextState`: callback evaluation is float; repeat, maximum, cooldown, and
state-log history independently suppress effective weight; effective float
weights are summed; and `Rng.NextFloat(total)` is consumed by source-order
cumulative subtraction. Normalization and zeroing remain dynamic, so no callback
constant is presented as a state-independent probability.

Production discovery starts from the exact behavior registrations and their
closed invocation decisions. It yields 6 owners/7 roots, 3 helper methods/5 helper
edges, 6 current direct Add sinks, and 6 owner/encounter applicability joins.
The assembly census classifies all 14 `CreatureCmd.Add` calls: six current enemy,
two core forwarding, four death-Power, one mock, and one player-pet. All 17
`OstyCmd.Summon` calls are separately classified and never merged. The earlier
behavior extractor already traversed Fabricator's defensive/aggressive wrappers
and shared `SpawnBot`, including Fabricating Strike. E2d1a reuses those exact
invocation IDs and deduplicates them; it does not claim newly visible helpers.

The core three-overload Add chain proves model/body construction, combat/side/slot
propagation, `CreateCreature` then `EncounterModel.OnCreatureSpawned`, live and
in-progress branches, combat/manager/room insertion, E2a addition-hook dispatch,
unique canonical-model history, awaited `AfterCreatureAddedToCombat`, and exact
created-body result identity. Spawn history is reward/progress model membership,
not body count, cap, or pool depletion. Core Add has no slot validation and no
`AfterSummon`; the latter belongs to Osty. Exceptions propagate with no rollback
or cancellation. Producer-specific pool, availability, no-slot, cardinality, cap,
repeat-state, and post-add facts are explicitly pending E2d1b; lifecycle outcomes
remain E2d2.

## E2 projection boundary

The checked source artifact above remains the full static evidence artifact.
C0 introduced, E1 extended, and E2a/E2b/E2c1/E2c2a/E2c2b/E2d1a extend `data/encounter-facts-v0.111.0.json`, built by
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
pointed-value hashes instead of repeating CIL proof or the 6,786-invocation
census. This makes the projection substantially smaller while retaining an
auditable path to the full checked source artifact.

E2d1a declares only the bounded encounter projection complete. The encounter
companion remains hard-false/incomplete: event turn machines are source-complete,
but scripted event behavior, event lifecycle/timeout/result semantics, broader lifecycle
closure, and companion-wide formula/runtime contracts remain blockers. Global readiness also remains false
pending the independent product-family source waves. No `src/` file imports the projection,
so `/sts2` continues to use byte-identical `data/encounters.json`.
